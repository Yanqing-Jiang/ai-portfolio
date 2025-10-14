# Analytics Architecture (October 2025)



## Goals
- Maintain a single artifact-centric pipeline that powers planner-executor, single-agent, and multi-agent delivery modes without diverging logic.
- Stream real-time specialist artifacts (SQL, chart, web, stock) directly into the chat transcript so users see the same intermediate progress in every mode.
- Persist SQL, chart, analysis, market, and tool metadata in `SessionStateSnapshot` to support revisions, follow-up routing, and cross-mode continuity.
- Guarantee sanitized, mode-agnostic telemetry (progress, fan-out, reasoning, cohesive result) for ProcessPanel, WorkflowCanvas, and chat visualizations.

## High-Level Outcomes
- Unified chat experience: Specialist outputs surface as inline chat messages (rather than preview-only panels) across all flows, while result bubbles show only consolidated analysis.
- Prompt & artifact guardrails: SQL prompts forbid formatting helpers (`ROUND`, `TRUNC`, `TO_CHAR`), and chart artifacts are normalized/sanitized before emission, preventing wrapper specs or serialization errors.
- Session continuity: Every flow writes sanitized artifacts and tool bundles to `SessionStateSnapshot`, enabling chart/analysis revisions and follow-up intent routing without recomputation.


## Entry Points

1. `analytics.flows.workflow.analytics_memory_workflow(query, flow?, session_id?)` resolves the active flow (`planner-executor`, `single-agent`, `multi-agent`) and guarantees a session id.

2. Flow instances (`PlannerExecutorFlow`, `SingleAgentToolsFlow`, `MultiAgentFlow`) share the same `PlannerPipeline` core and expose `events()` async generators that yield SSE-compatible dictionaries.

3. Event emitters: all flows push through `analytics.core.events.EventEmitter`, so telemetry, errors, and final results keep a common schema.



## Shared Components

- PlannerPipeline (`backend/analytics/flows/planner_executor.py`): artifact pipeline that replaces the mutable `PlannerPhaseContext` with typed artifacts for classification, intent, SQL, chart, analysis, and market context.

- Tool registry (`backend/analytics/flows/pipeline_tools.py`): declarative map of tool metadata (latency budgets, concurrency limits, output artifacts) consumed by flows and frontend fan-out visualizations.

- Tool adapters (`backend/analytics/flows/tooling.py`): helpers (SQL planner preview, chart stub, web retriever, stock tracker, narrative synthesizer) invoked in parallel before analysis where applicable.

- Session state (`backend/analytics/core/session_state.py`): Redis-backed snapshot with in-memory fallback. `record_outputs` persists SQL, chart specs, and analysis after every phase; `record_tool_result("planner_bundle", ...)` stores sanitized bundle payloads for revisions.



## Baseline Planner Pipeline (PlannerExecutorFlow)

1. Classification: `core.intent.classify_query_async` identifies the analytics topic and financial flags.

2. Intent detection: `core.intent_impl` fills slot metadata; `detect_missing_slots` triggers clarification when confidence or required fields fall short.

3. Clarification loop: `core.clarify` merges user responses; the built-in schema clarifier decides whether additional prompts are necessary before planning.

4. Template + plan: `sql.sql_planner` selects YAML patterns; `PlannerResultModel` stores metrics, comparison, and template metadata for downstream reuse.

5. SQL generation: `sql.prompt_builder` + OpenAI Responses client iterate up to three attempts; every attempt is recorded in the SQL generation artifact (`PipelineArtifacts.sql_generation.attempts`) and the planner result.
6. SQL validation: `sql.validator.validate_sql` enforces guardrails; failed validation short-circuits with `SQL_VALIDATION_FINAL` telemetry.

7. Execution: `sql.executor.execute_sql` fetches data, emits `execution_stats` and `data_retrieved`, and sets artifacts for later phases.

8. Chart planning + generation: `core.charting.plan_chart_rule_based` chooses encodings; `build_chart_spec` emits the ECharts option; `_set_chart_artifact` stores spec and metadata.

9. Web search: `analytics.services.response_search.perform_response_search` (Gemini 2.5 Flash) produces `web_context` snippets when credentials exist; otherwise a disabled payload keeps downstream logic consistent.

10. Analysis: `core.analysis.stream_insights_llm` streams TL;DR + bullets and merges tool bundles (stock widget, web context) into the final `analysis_complete` payload.

11. Persistence: `PlannerPipeline._persist_session_state` writes SQL, chart, analysis artifacts and tool bundles into `SessionStateSnapshot` after each phase.



## Tool Fan-Out (Single & Multi-Agent)

- Triggered for financial intents when parallelism is enabled.

- Adapters: `sql_planner`, `chart_builder`, `web_retriever`, `stock_tracker`, `narrative_synthesizer`.

- Telemetry: `tool_parallel_start`, `tool_parallel_result`, `tool_parallel_complete` include concurrency limits, tool summaries, and payload previews so the frontend ledger shows live fan-out status.



## Flow Modes

### Planner-Executor

- Fixed path workflow: runs the baseline pipeline sequentially and emits the full telemetry stream (`classification_*`, `intent_*`, `sql_*`, `chart_*`, `analysis_*`, `workflow_complete`).

- Ideal for deterministic, non-agent deployments or backend-only usage.



### Single-Agent + Tools (`SingleAgentToolsFlow`)

- Claude‑style single agent orchestrating two lanes:
  - Lane A (parallel): `stock_tracker` and `web_retriever` run concurrently. Concurrency target: `concurrency_limit >= 2`.
  - Lane B (sequential SQL): `sql_planner` → `sql_generator` → `sql_validator` → `sql_executor` → `chart_builder`.

- The agent emits `tool_call` for each step and `tool_parallel_*` for Lane A. Analysis runs last, merging artifacts from both lanes into a single cohesive result.

- Revisions: the agent may call a single tool for targeted updates (for example, `chart_revision` for “make it a bar chart”, `stock_tracker` for a symbol change, or `web_retriever` for a refresh) without re‑running the SQL lane. Scope changes (for example, new filters or symbols affecting the dataset) trigger the full SQL lane before re‑building the chart and analysis.

- Tool metadata, budgets, and dependencies are resolved from the registry so concurrency and durations stay consistent with fan‑out previews.



### Multi-Agent Orchestration (`MultiAgentFlow`)

- Supervisor seeds shared context with the PlannerPipeline, then dispatches to specialists. Roles are explicit and may be LLM‑backed or deterministic workers:

  - `intent_liaison` (LLM): clarify missing slots; decide if planning can proceed.

  - `sql_planner` (LLM) → `sql_generator` (LLM) → `sql_validator` (deterministic) → `sql_executor` (deterministic): sequential SQL chain that yields SQL text, columns, sample rows, and row count.

  - `viz_designer` (LLM): build or patch the ECharts spec; enforce non‑null primary series and set `chart_type`.

  - `market_agent` (deterministic, optional LLM commentary): produce TradingView widget configuration for requested symbols.

  - `web_research_agent` (LLM): normalize search snippets into the shared `web` context.

  - `insight_reviewer` (LLM): compose TL;DR and bullets from SQL/Chart/Stock/Web artifacts.

- Market and web research typically run in parallel with the SQL chain. Visualization waits on SQL rows. The supervisor emits `agent_turn` and short `agent_reasoning` snippets for LLM roles, then merges all artifacts into one sanitized cohesive result.

- Follow‑ups: the supervisor may invoke only the pertinent specialist (for example, `viz_designer` for chart edits, `market_agent` for symbol changes, `web_research_agent` for refresh) or rerun the full SQL chain when the request implies a data/scope change.

- After orchestration, the supervisor emits a sanitized `cohesive_result` containing:

  - Final analysis text & length.

  - Chart spec + chart ID.

  - SQL text, row count, sampled rows, column metadata.

  - Stock widget configuration.

  - Web context (summary, snippets, provider metadata).

  - Tool manifest/results for the upstream fan-out.

- To prevent prior serialization crashes, `_sanitize_for_transport` converts slices, dataclasses, and datetime objects before the bundle or cohesive payload is emitted.



## Session State & Revisions

- `SessionStateSnapshot.record_outputs(...)` executes after every planner phase so `last_sql`, `last_chart_spec`, and `last_analysis` are always populated.

- Chart/analysis revisions (`chart_revision.py`) rely on the snapshot; missing snapshots previously triggered `CHART_REVISION_MISSING_SESSION`. Persisting artifacts resolves that error path for multi‑step sessions.

- The multi‑agent flow also writes a `planner_bundle` entry under `tool_cache` so downstream tools and UI panes can reconstruct context without recomputing the bundle.

### Follow‑Up vs Re‑Run

- Detection: classify each follow‑up as `revision` (presentation‑only) or `new_scope` (data/scope change). Reuse the active `session_id` to load `last_sql`, `last_chart_spec`, and `last_analysis`.

- Targeted revisions (no data change):
  - Chart: `chart_revision` mutates the prior ECharts option (for example, “switch to bar; add AMD”).
  - Stock: `stock_tracker` refreshes widget config for new symbols.
  - Web: `web_retriever` refreshes snippets.
  Single‑agent performs a single tool call; multi‑agent activates only the pertinent specialist. SQL is not recomputed.

- Re‑run (data/scope change):
  - Re‑enter the SQL sequence (plan → generate → validate → execute), then rebuild the chart. Market/web may refresh in parallel; analysis is updated; snapshot rolls forward.



## Frontend Contract Highlights

- Progress events: `classification_*`, `intent_detection_*`, `clarification_*`, `sql_*`, `chart_*`, `analysis_*` mirror planner steps across all modes.

- Tool fan-out: `tool_parallel_start/result/complete` include `concurrency_limit`, tool summaries, and timestamps for ProcessPanels Tool Fan-Out ledger.

- Agent telemetry (multi-agent only): `agent_turn` and `agent_reasoning` describe role transitions and reasoning snippets for WorkflowCanvas lanes.

- Cohesive result: single payload with SQL/chart/stock/web/analysis artifacts ensures the frontend can render the TL;DR analysis card, SQL data viewer, ECharts visualization, and TradingView widget in one step.

- Workflow completion: `workflow_complete` emits when all dependencies finish, regardless of flow mode; errors are surfaced via `EventEmitter.error(...)` with codes for the ledger.



## Testing & Monitoring

- Unit / integration:

  - `backend/tests/analytics/test_pipeline_tools.py` — registry metadata coverage; chart non‑null primary series.

  - `backend/tests/analytics/test_pipeline_classification_intent.py` — clarification, follow‑up classification, and intent regression tests.

  - `backend/tests/analytics/test_single_agent_flow.py` — lane A concurrency, lane B sequencing, cohesive payload.

  - `backend/tests/analytics/test_multi_agent_flow.py` — supervisor + specialists orchestration; cohesive payload; sanitized transport.

  - `backend/tests/analytics/test_tool_metadata_flows.py` — latency/concurrency metadata propagates to telemetry consumers; `tool_parallel_*` envelopes.

- Manual QA: run `/api/analytics/memory/stream` for each flow, verify ProcessPanel ledger (progress + tool fan-out), WorkflowCanvas (hub-and-spoke layout), and cohesive result cards (TL;DR bullets, chart, SQL sample, stock widget, web snippets).

- Monitoring: `analytics.core.telemetry.analysis_chunk` logs streaming fragments; `SessionStateRepository` warns when Redis is unavailable and falls back to in-memory storage.

