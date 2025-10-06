# Analytics Memory Flow Modes Overview (Oct 6, 2025)

This note captures the current end-to-end shape of the analytics memory experience across the three selectable modes exposed in the Memory page.

## Direct Workflow (`planner-executor`)
- **Purpose**: Deterministic baseline that drives the full analytics pipeline without any telemetry overlays.
- **Core phases**: `classification ? intent_detection ? clarification ? plan/template ? sql_compilation ? sql_validation ? sql_execution ? chart_generation ? analysis_generation ? workflow_complete`.
- **Sample event timeline**: `session_started ? classification_started ? classification_complete ? intent_detection_started ? intent_detection_complete ? clarification_request (optional) ? plan_built ? sql_compilation progress ? sql_generated/sql_validated/execution_stats ? chart_generated ? analysis_streaming ? analysis_complete ? planner_result ? workflow_complete`.
- **Key modules reused elsewhere**: `PlannerExecutorFlow` (main orchestrator), `classify_query_async` for pre-flight, SQL helpers (`build_sql_messages`, `validate_sql`, `execute_sql`), chart/analysis builders, and the tool fan-out helper (`run_tool_parallelism`).

## Single Agent + Tools (`single-agent`)
- **Purpose**: Surface the same core pipeline while emitting explicit tool telemetry so the UI shows a Claude-style agent with structured tool calls.
- **How it works**: `SingleAgentToolsFlow` wraps `PlannerExecutorFlow.events` and injects `tool_call` events before/after specific planner steps (`intent_detection`, `sql_compilation`, `analysis_generation`, etc.).
- **Sample event timeline**: `session_started ? classification_started ? tool_call(intent_classifier:start) ? intent_detection_started ? intent_detection_complete ? tool_call(intent_classifier:end) ? … ? sql_generated ? tool_call(sql_generator:end) ? … ? analysis_complete ? tool_call(analysis_writer:end) ? workflow_complete`.
- **What is unique**: No extra reasoning branches; the difference is purely telemetry (`tool_call`) plus the `singleAgentFanout` payload the frontend renders in ProcessPanel.

## Multi-Agent Orchestration (`multi-agent`)
- **Purpose**: Layer multi-agent reasoning on top of the shared pipeline, introducing orchestrated specialist agents once baseline analysis finishes.
- **How it works**: `MultiAgentFlow` streams events from `PlannerExecutorFlow`, mirrors them into an agent context, and emits additional messages:
  - `agent_turn` start/end around planner steps (e.g., `intent_analyst`, `sql_specialist`).
  - `agent_reasoning` fragments during `analysis_streaming`.
  - Post-analysis orchestration via `AgentExecutionOrchestrator`, which dispatches planner/query/analyst/chart/market/web agents with their own telemetry (e.g., `orchestrator_plan`, `agent_turn`, `tool_parallel_result`).
- **Sample event timeline**: `session_started ? classification_started ? agent_turn(intent_analyst:start) ? intent_detection_started ? intent_detection_complete ? agent_turn(intent_analyst:end) ? … ? analysis_complete ? orchestrator_plan (planner_agent) ? agent_turn(chart_agent:start) ? agent_reasoning(chart_agent) ? agent_turn(chart_agent:end) ? agent_turn(web_research_agent:start) ? tool_call(web_retriever) ? …`.
- **What is unique**: Additional state capture (`_shared_context`) feeding specialist agents, Polygon market lookups, conditional web refresh, and more granular ProcessPanel lanes.

## Modularizing the Three Modes
- **Current sharing**: All three modes already rely on `PlannerExecutorFlow` as the core engine. `SingleAgentToolsFlow` and `MultiAgentFlow` are thin wrappers that subscribe to the same event stream and add telemetry/agent coordination.
- **Separating flows while sharing modules**: Creating an explicit "core pipeline" module (e.g., an `AnalyticsCorePipeline` class exposing `async generate_events(query, session_id, *, hooks)`), and letting each mode register hooks for telemetry or orchestration, would not be overly invasive because: 
  1. The planner phases are already grouped into helper coroutines (`_classification_phase`, `_intent_phase`, etc.), making them good candidates for extraction.
  2. Both wrapper flows currently mirror the planner event stream; replacing that with lifecycle callbacks would reduce duplication of start/end lookup tables (`TOOL_START_STEPS`, `AGENT_START_STEPS`).
  3. The frontend expects consistent event names, so as long as the shared module keeps emitting the existing events, the UI changes would be minimal.
- **What to watch**: You would need to shuffle some private helpers (e.g., `_maybe_tool_start`, `_maybe_agent_turn_start`, `_capture_event`) into mixins or strategy objects, and update tests that assert exact event ordering (`backend/tests/analytics/test_flows_single_agent.py`, `test_flows_multi_agent.py`). With careful extraction, the change remains manageable rather than fully invasive.
- **Suggested incremental path**: start by factoring a `BaseAnalyticsFlow` that owns `PlannerExecutorFlow` and exposes hook methods like `on_progress(step, data)` and `on_result(event, data)`. `SingleAgentToolsFlow` and `MultiAgentFlow` would override only the hooks they need, avoiding changes to the underlying planner logic.
