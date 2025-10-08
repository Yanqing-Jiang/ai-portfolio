# Analytics Architecture (October 2025)

## Goals
- Provide a single artifact-centric pipeline that powers planner-executor, single-agent, and multi-agent delivery modes.
- Stream structured telemetry (progress, tool fan-out, agent reasoning, cohesive results) that the frontend ProcessPanel and WorkflowCanvas can render without mode-specific branches.
- Persist SQL, chart, analysis, and auxiliary context in `SessionStateSnapshot` so follow-up revisions have the same data surface across modes.

## Entry Points
1. **`analytics.flows.workflow.analytics_memory_workflow(query, flow?, session_id?)`** – resolves the active flow (`planner-executor`, `single-agent`, `multi-agent`) and guarantees a session id.
2. **Flow instances (`PlannerExecutorFlow`, `SingleAgentToolsFlow`, `MultiAgentFlow`)** – share the same `PlannerPipeline` core and expose `events()` async generators that yield SSE-compatible dictionaries.
3. **Event emitters** – all flows push through `analytics.core.events.EventEmitter`, so telemetry, errors, and final results keep a common schema.

## Shared Components
- **PlannerPipeline** (`backend/analytics/flows/planner_executor.py`) – artifact pipeline that replaces the mutable `PlannerPhaseContext` with typed artifacts for classification, intent, SQL, chart, analysis, and market context.
- **Tool registry** (`backend/analytics/flows/pipeline_tools.py`) – declarative map of tool metadata (latency budgets, concurrency limits, output artifacts) consumed by Agents SDK flows and frontend fan-out visualizations.
- **Tool adapters** (`backend/analytics/flows/tooling.py`) – fan-out helpers (SQL planner preview, chart stub, web retriever, stock tracker, narrative synthesizer) invoked in parallel before analysis.
- **Session state** (`backend/analytics/core/session_state.py`) – Redis-backed snapshot with in-memory fallback. `record_outputs` now persists SQL, chart specs, and analysis after every phase; `record_tool_result("planner_bundle", ...)` stores sanitized bundle payloads for revisions.

## Baseline Planner Pipeline (PlannerExecutorFlow)
1. **Classification** – `core.intent.classify_query_async` identifies the analytics topic and financial flags.
2. **Intent detection** – `core.intent_impl` fills slot metadata; `detect_missing_slots` triggers clarification when confidence or required fields fall short.
3. **Clarification loop** – `core.clarify` merges user responses; the built-in schema clarifier decides whether additional prompts are necessary before planning.
4. **Template + plan** – `sql.sql_planner` selects YAML patterns; `PlannerResultModel` stores metrics, comparison, and template metadata for downstream reuse.
5. **SQL generation** – `sql.prompt_builder` + OpenAI Responses client iterate up to three attempts; every attempt is recorded in `ctx.sql_attempts` and the planner result.
6. **SQL validation** – `sql.validator.validate_sql` enforces guardrails; failed validation short-circuits with `SQL_VALIDATION_FINAL` telemetry.
7. **Execution** – `sql.executor.execute_sql` fetches data, emits `execution_stats` and `data_retrieved`, and sets artifacts for later phases.
8. **Chart planning + generation** – `core.charting.plan_chart_rule_based` chooses encodings, `build_chart_spec` emits the ECharts option; `_set_chart_artifact` stores spec and metadata.
9. **Web search** – `analytics.services.response_search.perform_response_search` (Gemini 2.5 Flash) produces `web_context` snippets when credentials exist; otherwise a disabled payload keeps downstream logic consistent.
10. **Analysis** – `core.analysis.stream_insights_llm` streams TL;DR + bullets and merges tool bundles (stock widget, web context) into the final `analysis_complete` payload.
11. **Persistence** – `PlannerPipeline._persist_session_state` writes SQL, chart, analysis artifacts and tool bundles into `SessionStateSnapshot` after each phase.

## Tool Fan-Out (Single & Multi-Agent)
- Triggered for financial intents when parallelism is enabled.
- Adapters: `sql_planner`, `chart_builder`, `web_retriever`, `stock_tracker`, `narrative_synthesizer`.
- Telemetry: `tool_parallel_start`, `tool_parallel_result`, `tool_parallel_complete` include concurrency limits, tool summaries, and payload previews so the frontend ledger shows live fan-out status.

## Flow Modes
### Planner-Executor
- Runs the baseline pipeline sequentially and emits the full telemetry stream (`classification_*`, `intent_*`, `sql_*`, `chart_*`, `analysis_*`, `workflow_complete`).
- Ideal for deterministic, non-agent deployments or backend-only usage.

### Single-Agent + Tools (`SingleAgentToolsFlow`)
- Wraps the planner pipeline with `_SingleAgentToolHooks` that translate pipeline steps into `tool_call` events for the Agents SDK UI.
- When revisions are requested, individual planner tools (chart_revision, analysis_revision) are invoked directly via the registry, reusing persisted session snapshots.
- Tool metadata is resolved from the registry so latency budgets and concurrency limits stay consistent with fan-out previews.

### Multi-Agent Orchestration (`MultiAgentFlow`)
- Supervisor agent reuses the planner pipeline to seed shared context, then executes a task graph through `AgentExecutionOrchestrator`:
  - `planner_agent` – seeds bundle and task plan.
  - `intent_analyst`, `user_liaison` – finalize slots or surface clarifications.
  - `sql_specialist`, `risk_controller`, `data_engineer` – generate SQL, validate, and confirm row counts / samples.
  - `viz_designer` – produce the chart spec (ECharts option + metadata).
  - `market_agent` – map stock tracker outputs to TradingView widgets.
  - `web_research_agent` – normalize Gemini snippets into the shared `web` context.
  - `insight_reviewer` – stream and finalize the narrative analysis.
- After orchestration, the supervisor emits a sanitized `cohesive_result` containing:
  - Final analysis text & length.
  - Chart spec + chart ID.
  - SQL text, row count, sampled rows, column metadata.
  - Stock widget configuration.
  - Web context (summary, snippets, provider metadata).
  - Tool manifest/results for the upstream fan-out.
- To prevent prior serialization crashes, `_sanitize_for_transport` converts slices, dataclasses, and datetime objects before the bundle or cohesive payload is emitted.

## Session State & Revisions
- `SessionStateSnapshot.record_outputs(...)` now executes after every planner phase so `last_sql`, `last_chart_spec`, and `last_analysis` are always populated.
- Chart/analysis revisions (`chart_revision.py`) rely on the snapshot; missing snapshots previously triggered `CHART_REVISION_MISSING_SESSION`. Persisting artifacts resolves that error path for multi-step sessions.
- The multi-agent flow also writes a `planner_bundle` entry under `tool_cache` so downstream tools and UI panes can reconstruct context without recomputing the bundle.

## Frontend Contract Highlights
- **Progress events**: `classification_*`, `intent_detection_*`, `clarification_*`, `sql_*`, `chart_*`, `analysis_*` mirror planner steps across all modes.
- **Tool fan-out**: `tool_parallel_start/result/complete` include `concurrency_limit`, tool summaries, and timestamps for ProcessPanel’s “Tool Fan-Out” ledger.
- **Agent telemetry** (multi-agent only): `agent_turn` and `agent_reasoning` describe role transitions and reasoning snippets for WorkflowCanvas lanes.
- **Cohesive result**: single payload with SQL/chart/stock/web/analysis artifacts ensures the frontend can render the TL;DR analysis card, SQL data viewer, ECharts visualization, and TradingView widget in one step.
- **Workflow completion**: `workflow_complete` emits when all dependencies finish, regardless of flow mode; errors are surfaced via `EventEmitter.error(...)` with codes for the ledger.

## Testing & Monitoring
- **Unit / integration**:
  - `backend/tests/analytics/test_pipeline_tools.py` – registry metadata coverage.
  - `backend/tests/analytics/test_pipeline_classification_intent.py` – clarification and intent regression tests.
  - `backend/tests/analytics/test_multi_agent_flow.py` – validates cohesive result payloads and web context handling.
  - `backend/tests/analytics/test_tool_metadata_flows.py` – ensures latency/concurrency metadata propagates to telemetry consumers.
- **Manual QA**: run `/api/analytics/memory/stream` for each flow, verify ProcessPanel ledger (progress + tool fan-out), WorkflowCanvas (hub-and-spoke layout), and cohesive result cards (TL;DR bullets, chart, SQL sample, stock widget, web snippets).
- **Monitoring**: `analytics.core.telemetry.analysis_chunk` logs streaming fragments; `SessionStateRepository` warns when Redis is unavailable and falls back to in-memory storage.
