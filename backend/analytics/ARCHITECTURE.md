# Analytics Package Architecture

## Purpose
The analytics package powers the next-generation analytics memory experience. It orchestrates multi-step agent flows, builds SQL through YAML-backed templates plus LLM assistance, validates and executes warehouse queries, and streams structured telemetry to the frontend for visualization.

## Execution Path Overview
1. **Entry point** - `analytics.flows.workflow.analytics_memory_workflow` resolves the requested flow (planner-executor, single-agent, multi-agent).
2. **Flow orchestration** - each flow class emits Server-Sent Events through the shared `EventEmitter` so the UI can animate progress.
3. **Intent & plan** - `core.intent` and `core.intent_impl` detect user intent, normalize slots, and assemble a provisional `QueryPlanModel`.
4. **Template selection** - `sql.sql_planner` and `core.config_store` fetch YAML templates from `backend/config/schemas/queries.yaml` to steer SQL generation.
5. **SQL generation** - `sql.prompt_builder` crafts OpenAI Responses API prompts; `unified_responses_client` streams candidate SQL; `sql.compiler` fills template variables or falls back to rule-based compilation.
5a. **Tool fan-out (flagged)** - When `ANALYTICS_TOOL_PARALLELISM` is enabled, `flows/tooling.py` runs TaskGroup-managed adapters (SQL planner summary, chart builder, web retriever stub, stock tracker stub, narrative primer) and emits `tool_parallel_*` telemetry alongside the sequential pipeline.
6. **Validation & execution** - `sql.validator` enforces guardrails; `sql.executor` runs the query against the configured warehouse.
7. **Insights & visualization** - `core.analysis`, `core.charting`, and `core.charting_impl` summarize data and build chart specs before telemetry streams to the UI.
8. **Clarifications & telemetry** - `core.clarify` issues slot prompts (for example `_detect_timeframe_slot` now asks for a specific fiscal year for the `rnd_top_spender` flow) and `core.events.EventEmitter` surfaces progress, status, and error payloads consumed by the redesigned Flow View.

## Flow Mode Execution Diagram

```
                  +-----------------------------------------------+
                  | analytics_memory_workflow(query, flow?)       |
                  |   - picks flow arg or ANALYTICS_FLOW_MODE env |
                  |   - instantiates matching flow class          |
                  +-----------------------+-----------------------+
                                          |
         +--------------------------------+--------------------------------+
         |                    PlannerExecutorFlow                          |
         |   Baseline SSE pipeline: intent -> clarification -> SQL -> ... |
         +-------------+----------------------+----------------------------+
                       |                      |
            +----------+----+         +-------+------------------+
            | Single-Agent  |         |       Multi-Agent        |
            | Tools Flow    |         |           Flow           |
            | wraps baseline|         | wraps baseline events    |
            | events with   |         | with agent_turn +        |
            | tool_call     |         | agent_reasoning telemetry|
            | telemetry     |         |                          |
            +---------------+         +--------------------------+
```

The repository in `core/session_state.py` now falls back to an in-memory store when Redis is unavailable while keeping the 5-minute TTL semantics for analytics sessions.

## Analytics Memory Flow Modes
Use `/api/analytics/memory/stream?flow=<flow>` to select the demo experience surfaced in the Memory page (legacy `mode` query param is still accepted for backwards compatibility).
Flow metadata comes from `backend/analytics/flows/workflow.py::get_available_flows()`; keep frontend selectors in sync with that mapping.
- `planner-executor`: deterministic baseline emitting shared SSE events (`progress`, `classification_*`, `sql_generated`, `analysis_streaming`, `result`, `done`).
- `single-agent`: wraps each baseline step with `tool_call` start/end telemetry, durations, and SQL template metadata; when `ANALYTICS_TOOL_PARALLELISM` is enabled it also streams `tool_parallel_*` fan-out events from the new TaskGroup adapters. Prompt contract lives in `backend/analytics/solo_agent.md`; consult that doc for tool policy, cache reuse rules, and safety guardrails.
- `multi-agent`: wraps the same baseline steps with persona `agent_turn` start/complete envelopes, adds `agent_reasoning` for analysis deltas, and attaches role-specific summaries.
When `ANALYTICS_TOOL_PARALLELISM` is disabled, the adapters stay dormant and the deterministic sequential behaviour remains unchanged.

## Streaming Telemetry Reference
- Core SSE events across all flows: `classification_*`, `intent_*`, `clarification_*`, `progress`, `status`, `sql_generated`, `analysis_streaming`, `result`, `final_answer`, `done`, and `error`.
- Demo-specific enrichments: `tool_call` (single-agent), `agent_turn` and `agent_reasoning` (multi-agent) augment the stream for visualization overlays.
- Planner flows emit `sql_attempts` events to log each generated query revision before execution.
- Parallel fan-out instrumentation emits `tool_parallel_*` envelopes whenever `ANALYTICS_TOOL_PARALLELISM` is enabled.
- Frontend consumers (`useAnalyticsMemoryStream`, `ProcessPanel`, `WorkflowCanvas`) subscribe to the stream and must handle these payloads.

## Directory Layout
```
analytics/
|-- __init__.py
|-- core/
|   |-- analysis.py
|   |-- cache.py
|   |-- charting.py / charting_impl.py
|   |-- clarify.py
|   |-- companies.py
|   |-- config.py / config_store.py
|   |-- context.py
|   |-- events.py
|   |-- intent.py
|   |-- intent_impl/
|   |   |-- detection.py
|   |   |-- normalization.py
|   |   `-- models.py
|   |-- openai_client.py
|   |-- state.py
|   |-- session_state.py
|   |-- telemetry.py
|   `-- types.py
|-- flows/
|   |-- planner_executor.py
|   |-- single_agent_tools.py
|   |-- multi_agent.py
|   |-- tooling.py
|   `-- workflow.py
|-- sql/
|   |-- compiler.py
|   |-- db.py
|   |-- executor.py
|   |-- prompt_builder.py
|   |-- sql_planner.py
|   |-- sql_validate.py
|   |-- templates.py
|   `-- validator.py
|-- streaming/
|   `-- __init__.py
|-- tools/
|   |-- registry.py
|   `-- __init__.py
`-- unified_responses_client.py
```

### core/
Foundational utilities that capture shared data models, config access, intent resolution, charting, telemetry, and caching.

**Key files and functions**
- `analysis.py` - `summarize(data, sql, query, intent)` condenses result sets into prose; `stream_insights_llm(...)` yields incremental analysis chunks for SSE streaming.
- `charting.py` - `plan_chart_rule_based(plan, data)` maps metrics to chart primitives; `build_chart_spec(...)` wraps ECharts options with metadata used by the frontend overlays.
- `charting_impl.py` - `_generate_chart_design(intent_key, plan, data, spec)` produces flow-specific colour palettes, annotations, and highlight rules consumed by `ProcessNode` overlays.
- `clarify.py` - `_detect_missing_slots`, `_detect_timeframe_slot`, and `merge_answers` drive clarification prompts. The fiscal-year branch now emits current-year-plus-five options for `rnd_top_spender`, and `merge_answers` persists `start_year`, `end_year`, and `years_back` while appending human-readable assumptions for telemetry.
- `companies.py` - `sanitize_ticker`, `validate_and_resolve_company`, and `resolve_alias_to_ticker` normalize user supplied tickers before SQL substitution.
- `config.py` / `config_store.py` - `CONFIGS.load()` bootstraps YAML schemas; `ConfigStore.get_query_pattern(intent_key)` exposes cached template metadata.
- `context.py` - `get_configs()` and `get_config_store()` provide singleton accessors used across flows.
- `events.py` - `EventEmitter.session_started`, `progress`, `result`, and `error` build the structured SSE payloads `ProcessPanel` subscribes to.
- `intent.py` - `detect_intent`, `detect_intent_with_clarifications`, and `detect_intent_llm` orchestrate heuristic and LLM-based routing.
  - `intent_impl/detection.py` now flags ranking superlatives (highest/top/most) in `heuristic_intent` so `rnd_top_spender` short-circuits without unnecessary company clarifications.
- `state.py` / `types.py` - Pydantic models such as `QueryPlanModel`, `TimeframeModel`, and `ProcessStep` define the contract between backend flows and the analytics UI.

### flows/
Implements user-facing agent experiences.

- `planner_executor.py` - `PlannerExecutorFlow.events(...)` is the deterministic baseline that emits `classification_*`, `intent_detection`, `clarification`, `sql_*`, `chart`, and `analysis` events; helper `_generate_chart_design` attaches visualization metadata.
- `single_agent_tools.py` - `SingleAgentToolsFlow.events(...)` wraps baseline steps with tool start/end markers (`tool_call`, `agent_turn`, `agent_reasoning`) that the new Flow View colours by flow mode.
- `multi_agent.py` - `MultiAgentFlow.events(...)` replays planner decisions through agent personas (planner, SQL specialist, risk controller, viz designer, insight reviewer).
- `workflow.py` - `analytics_memory_workflow(query, flow)` multiplexes flow objects, while `get_available_flows()` exposes the `/api/analytics/memory/stream?flow=` selector used by the UI.
- `solo_agent.md` - Deploy-time prompt blueprint enumerating tool affordances and cache guidance consumed by the single-agent flow.
- `tooling.py` - Hosts `ToolTaskGroup` and default adapters that emit preview telemetry when Mode 1 parallelism is toggled on.

### sql/
Handles YAML-driven SQL authoring and guardrails.

- `sql_planner.py` - `plan_sql_rule_based(intent)` composes metric lists, timeframe defaults, and comparison modes; `choose_template` now clones YAML patterns and swaps in the `single_year_template` when `timeframe.start_year` is locked, keeping multi-year leaderboards as the default.
- `templates.py` - `fetch_templates_for_intent(intent_key)` lists YAML candidates, while `choose_template(...)` (in `sql_planner`) selects the final pattern.
- `prompt_builder.py` - `build_sql_messages(...)` assembles Responses API prompts and `extract_sql_from_response(...)` parses fenced SQL blocks.
- `compiler.py` - `compile_sql_from_plan(plan, intent, template)` substitutes placeholders; it honours `{start_year}` and `{end_year}` so the single-year template targets an exact fiscal year.
- `validator.py` / `sql_validate.py` - `validate_sql(...)` applies whitelist and limit checks before execution.
- `executor.py` - `execute_sql(...)` runs asyncpg queries with cancellation and timeout guards.

### YAML templates
`backend/config/schemas/queries.yaml` houses reusable SQL patterns. The `rnd_top_spender` entry now includes both a multi-year leaderboard (with revenue and intensity columns) and a `single_year_template` that isolates one fiscal year once the clarification response supplies it.

### tools/
Defines reusable analytics tools exposed to agents.
- `registry.py` - `ToolRegistry.register(...)` ties tool metadata to dispatcher callables; helpers map telemetry (`ToolCallTelemetry`) back into the Flow View timeline.

### streaming/
Placeholder namespace for SSE-specific helpers; the primary event formatting lives in `core.events.EventEmitter` today.

### Shared OpenAI Client
`unified_responses_client.py` wraps the async OpenAI Responses API with reasoning support, streaming deltas, structured outputs, and embeddings helpers. All flows request instances via `get_unified_client()` to maintain session continuity and reasoning effort policies.

## Supporting Tests
Backend regression tests live under `backend/tests/analytics/` and cover:
- Flow event ordering (`test_flows_single_agent.py`, `test_flows_multi_agent.py`).
- SQL prompt/template handling (`test_flow_modes_queries.py`, `test_prompt_builder.py`).
- Clarification behaviour (`test_clarify_timeframe.py` exercises the new fiscal-year prompt path and single-year template selection).
- Cache/config behaviour (`test_cache_service.py`).

Frontend analytics components consume the SSE payloads described here; see `components/analytics/` for the hook (`useAnalyticsMemoryStream`) and visualization panels that mirror the telemetry contract.

## Operational Notes
- **Configuration** - YAML files in `backend/config/schemas/` (e.g., `queries.yaml`) drive template selection and metric metadata.
- **Environment** - `DATABASE_URL`, `OPENAI_API_KEY`, and optional reasoning overrides (`SUPERVISOR_REASONING_EFFORT`) must be set before running flows.
- **API integration** - `/api/analytics/memory/stream` (FastAPI) maps query parameters to `analytics_memory_workflow` and streams events directly to the frontend `EventSource` client.


