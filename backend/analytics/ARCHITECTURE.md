# Analytics Package Architecture

## Purpose
The analytics package powers the next-generation analytics memory experience. It orchestrates multi-step agent flows, builds SQL with the OpenAI Responses API using YAML templates as guidance, validates and executes warehouse queries, enriches results with Gemini-powered market research, and streams structured telemetry to the frontend for visualization.

## Execution Path Overview
1. **Entry point** - `analytics.flows.workflow.analytics_memory_workflow` resolves the requested flow (planner-executor, single-agent, multi-agent) and seeds a session identifier.
2. **Flow orchestration** - each flow instance wires shared `EventEmitter` streams so progress, results, and errors surface uniformly to the UI.
3. **LLM preflight** - `_classification_phase` calls `classify_query_async` with `gpt-5-nano-2025-08-07`; non-financial prompts emit a short `final_answer` decline and the workflow stops before generating SQL.
4. **Intent + clarification** - `core.intent` and `core.intent_impl` detect the canonical analytics intent, derive slot assumptions, and surface clarification requests through `core.clarify` when required.
5. **Template context** - `sql.sql_planner`, `core.config_store`, and the new `PlannerResultModel` track YAML-derived patterns so downstream flows receive consistent metadata.
6. **SQL generation & retry loop** - `sql.prompt_builder` builds Responses prompts; `unified_responses_client` runs up to three attempts (via `build_sql_retry_messages(...)`) and records each in `ctx.sql_attempts`.
7. **Validation & execution** - `sql.validator` enforces table/limit guardrails; `sql.executor` runs the final statement once validation passes, otherwise emits `SQL_VALIDATION_FINAL` telemetry and aborts.
8. **Real-time research** - `_web_search_phase` now invokes Gemini 2.5 Flash with the Google Search grounding tool to fetch late-breaking headlines, earnings notes, and regulatory filings for the detected tickers. The normalized payload travels through `EventEmitter.result("web_search", ...)` so downstream flows and the UI receive `web_context` snippets.
9. **Insights & visualization** - `core.analysis`, `core.charting`, and `plan_chart_rule_based` transform result sets into chart specs and narrative output, enriching payloads with tool bundles when parallel adapters run; the summary lands in `PlannerResultModel.analysis` for reuse by downstream modes.
10. **Telemetry & cleanup** - `core.events.EventEmitter` streams SSE events end-to-end, `collect_tool_bundle` attaches auxiliary data, and `core.clarify` prunes expired session state.

## Flow Mode Execution Diagram

```
                  +-----------------------------------------------+
                  | analytics_memory_workflow(query, flow?)       |
                  |   picks flow arg or ANALYTICS_FLOW_MODE env   |
                  +-----------------------+-----------------------+
                                          |
                                  +-------v--------+
                                  | LLM preflight  |
                                  | (gpt-5-nano)   |
                                  +-------+--------+
                                          |
                      +-------------------v-------------------+
                      | Baseline planner pipeline             |
                      | intent -> clarification -> SQL -> ... |
                      +---------+---------------+-------------+
                                |               |
              +-----------------v-+       +-----v-----------+       +-----------------+
              | PlannerExecutor    |       | SingleAgentTools |       |   MultiAgent     |
              | emits core events  |       | adds tool_call   |       | adds agent_turn  |
              +--------------------+       | & parallel tools |       | + reasoning SSE  |
                                            +-----------------+       +-----------------+
```

The repository in `core/session_state.py` now falls back to an in-memory store when Redis is unavailable while keeping the 5-minute TTL semantics for analytics sessions.

## Analytics Memory Flow Modes
Use `/api/analytics/memory/stream?flow=<flow>` to select the demo experience surfaced in the Memory page (legacy `mode` query param is still accepted for backwards compatibility).
Flow metadata comes from `backend/analytics/flows/workflow.py::get_available_flows()`; keep frontend selectors in sync with that mapping.
- `planner-executor`: baseline pipeline that streams `classification_*`, emits `final_answer` when the LLM gate declines a prompt, and records `sql_attempts`/`sql_generated` metadata for every Responses retry before analysis/`done`.
- `single-agent`: wraps each baseline step with `tool_call` start/end telemetry, durations, and SQL template metadata; when `ANALYTICS_TOOL_PARALLELISM` is enabled it also streams `tool_parallel_*` fan-out events from the new TaskGroup adapters. Prompt contract lives in `backend/analytics/solo_agent.md`; consult that doc for tool policy, cache reuse rules, and safety guardrails.
- `multi-agent`: wraps the same baseline steps with persona `agent_turn` start/complete envelopes, adds `agent_reasoning` for analysis deltas, and attaches role-specific summaries.
When `ANALYTICS_TOOL_PARALLELISM` is disabled, the adapters stay dormant and the deterministic sequential behaviour remains unchanged.

## Streaming Telemetry Reference
- Core SSE events across all flows: `classification_*`, `intent_*`, `clarification_*`, `progress`, `status`, `sql_generated`, `analysis_streaming`, `result`, `final_answer`, `done`, and `error`.
- `web_search`: emitted once Gemini returns fresh headlines; payload includes `web_context` with summary, snippets, latency, and cache metadata for the UI.
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
- `prompt_builder.py` - `build_sql_messages(...)` assembles the initial Responses prompt while `build_sql_retry_messages(...)` summarizes failures for follow-up attempts; `extract_sql_from_response(...)` parses fenced SQL blocks.
- `compiler.py` - legacy helper that can still hydrate templates for experiments, though the default planner now leans on Responses retries instead of deterministic compilation.
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
`unified_responses_client.py` wraps the async OpenAI Responses API with reasoning support, streaming deltas, structured outputs, and embeddings helpers. All flows request instances via `get_unified_client()` to maintain session continuity and reasoning effort policies, while `analytics.services.response_search` issues Gemini 2.5 Flash search calls (requires `GOOGLE_API_KEY` or `GEMINI_API_KEY` / `GEMIN_API_KEY`).

## Supporting Tests
Backend regression tests live under `backend/tests/analytics/` and cover:
- Flow event ordering (`test_flows_single_agent.py`, `test_flows_multi_agent.py`).
- SQL prompt/template handling (`test_flow_modes_queries.py`, `test_prompt_builder.py`).
- Clarification behaviour (`test_clarify_timeframe.py` exercises the new fiscal-year prompt path and single-year template selection).
- Cache/config behaviour (`test_cache_service.py`).

Frontend analytics components consume the SSE payloads described here; see `components/analytics/` for the hook (`useAnalyticsMemoryStream`) and visualization panels that mirror the telemetry contract.

## Operational Notes
- **Configuration** - YAML files in `backend/config/schemas/` (e.g., `queries.yaml`) drive template selection and metric metadata.
- **Environment** - `DATABASE_URL`, `OPENAI_API_KEY`, `GOOGLE_API_KEY` (or `GEMINI_API_KEY` / `GEMIN_API_KEY` for Gemini search), and optional reasoning overrides (`SUPERVISOR_REASONING_EFFORT`) must be set before running flows.
- **API integration** - `/api/analytics/memory/stream` (FastAPI) maps query parameters to `analytics_memory_workflow` and streams events directly to the frontend `EventSource` client.





