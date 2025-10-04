# Analytics Package Architecture

## Purpose
The analytics package powers the next-generation analytics memory experience. It orchestrates multi-step agent flows, builds SQL with the OpenAI Responses API using YAML templates as guidance, validates and executes warehouse queries, and streams structured telemetry to the frontend for visualization. The runtimes described below now cover planner-executor legacy flows, a Claude-style single agent, and the specialist multi-agent orchestrator introduced in Phases 3 and 4.

## Runtime Entry Points
- `analytics.flows.workflow.analytics_memory_workflow` is the public entry point. It inspects the `flow` query parameter (or the `ANALYTICS_AGENT_RUNTIME` feature flag) to choose between planner-executor, single-agent, and multi-agent implementations.
- Every invocation seeds a `session_id`, attaches shared `EventEmitter` instances, and primes telemetry so SSE packets remain compatible with the legacy PlannerExecutor timeline.
- Both runtime flavours reuse the shared tool registry (`analytics.agents.tool_registry.ToolRegistry`) and default tool catalog registered in `analytics.agents.tools.register_default_tools`.

## Shared Execution Stages
1. **Intent bootstrap** – incoming prompt + configs from `core.context.get_configs()` and cached session hints are bundled before any LLM work starts.
2. **Classification / gating** – only the planner-executor flow runs `_classification_phase` to decline non-financial requests. Runtime flows bypass this gate and rely on clarification rounds when the planner detects ambiguity.
3. **Clarification + intent detection** – `core.intent.detect_intent_with_clarifications_async` derives the canonical intent, prompts for missing slots through `clarification.ask_missing_slots`, and establishes timeframe/entity defaults.
4. **SQL template selection** – `sql.sql_planner.plan_sql_rule_based` turns the intent into a `QueryPlanModel`, selecting YAML templates and comparison hints for downstream steps.
5. **SQL drafting** – `sql.build_messages` prepares Responses prompts; runtimes call `unified_responses_client.tool_calling_turn` to draft SQL, persisting `response_id` values for telemetry.
6. **Execution & validation** – `sql.execute` runs asyncpg queries with guardrails from `sql.validator` and emits `tool_iteration` telemetry for start/end/error envelopes.
7. **Analysis & charting** – `analysis.summarize` and `chart.generate` transform rows into narrative takeaways and Vega-Lite chart specs. Fan-out adapters honour the `ANALYTICS_TOOL_PARALLELISM` flag.
8. **Web & market enrichment** – optional specialists fetch supplemental data (Polygon, web search) when the query shows recency keywords or `ANALYTICS_ENABLE_WEB_SEARCH` is enabled.
9. **Streaming & completion** – `EventEmitter` sends `agent_turn`, `tool_call`, `analysis_streaming`, and final `agent_reply` events with per-session `sequence` counters before emitting the terminal `workflow` completion packet.

## Flow Mode Reference
- **planner-executor** – retains the legacy sequential pipeline (`classification_*`, `_sql_phase`, etc.) and streams telemetry identical to historical PlannerExecutorFlow sessions.
- **single-agent (runtime)** – wraps the baseline stages inside `analytics.agents.runtime.SingleAgentRuntime`. The loop streams `agent_turn` events for user/assistant turns, emits `tool_call` start/end packets around registry invocations, and preserves `tool_iteration` metrics. SSE payloads include `sequence` and `responseId` fields so the frontend can correlate deltas with chat history.
- **multi-agent (runtime)** – routes work through `analytics.agents.multi_runtime.MultiAgentRuntime`. Persona specialists hand off context (planner, query, chart, analyst, market, web) while emitting `agent_turn` envelopes for each role plus shared `tool_call` telemetry; chart/analyst/market/web runs now execute in parallel with retry + fallback handling so a single specialist failure no longer tears down the session.

## Multi-Agent Orchestration (Phase 3)
- Specialists are declared via `SpecialistConfig` objects. Defaults cover planner orchestration, SQL drafting/execution, charting, narrative analysis, Polygon-backed market snapshots, and recency web checks.
- `run(...)` orchestrates planner -> query -> parallel chart/analyst/market/web stages. Shared context carries SQL rows, templates, clarifications, and response IDs between specialists while retry metadata is appended to `agent_turn` events for observability.
- Specialists emit `agent_turn` events with `status` values (`thinking`, `completed`, `skipped`, `retry`, `failed`) and metadata such as row counts, clarification totals, or snapshot ticker lists.
- Tool invocations go through `_invoke_tool`, which wraps registry calls with start/end/error telemetry (`tool_iteration`) and mirrored SSE packets. Retryable specialists route through `_run_with_retry`; when attempts are exhausted the runtime emits a fallback payload instead of aborting the workflow.
- Final replies are assembled via `_build_final_payload`, ensuring charts, analysis text, market/web snippets, and clarifications are coalesced before the terminal SSE events fire.

## Telemetry & UX Integration (Phase 4)
- Both runtimes maintain per-session `sequence` counters. `SingleAgentRuntime` also tracks a global counter so multiple sessions never clash when multiplexed.
- LLM replies (`agent_reply` events) include the most recent `response_id`, enabling transcript reconciliation and debugging in ProcessPanel and WorkflowCanvas.
- `components/analytics/hooks/useAnalyticsMemoryStream` consumes the expanded metadata: specialist lanes, retry states, tool telemetry, progressive analysis text, and additive payloads such as `market` and `market_tickers`.
- `components/analytics/types.ts` models additive fields (`responseId`, `analysisSections`, `toolFanoutManifest`, `market`, `web`) so UI components can render richer context without bespoke plumbing.
- Legacy SSE contracts remain intact; new fields are additive (e.g., `sequence`, `responseId`, `market`, `market_tickers`) and gated so historical replays remain compatible.

## Rollout & Operational Controls (Phase 5)
- Feature flags: `ANALYTICS_AGENT_RUNTIME` (`planner|single|single-runtime|multi`) selects the active runtime, `ANALYTICS_TOOL_PARALLELISM` toggles TaskGroup fan-out, `ANALYTICS_ENABLE_WEB_SEARCH` forces the web specialist, and `ANALYTICS_MARKET_WIDGET` enables market snapshot specialists.
- API toggles allow side-by-side comparisons between planner and runtime flows; telemetry parity (`tool_iteration`, SSE envelopes) is monitored so dashboards stay aligned across cohorts.
- Replay benchmarking lives in `backend/analytics/flows/replay_benchmark.py`; use it when comparing flows pre/post rollout. Operational guidance resides in `backend/analytics/analytics_rollout.md`.
- Baseline metrics for Phase 0 (classification accuracy, web latency, SQL retry counts) remain TODO items that should be instrumented ahead of GA.

## Package Map Highlights
- `analytics/agents/runtime.py` – Claude-style single agent loop with per-session history, guardrails (max tool calls/turns), sequencing, and `response_id` propagation (low-confidence confirmation guardrail still pending).
- `analytics/agents/multi_runtime.py` – specialist orchestrator managing planner/query/chart/analyst/market/web roles, sequencing, retry/fallback logic, parallel execution, and final response assembly.
- `analytics/agents/tool_registry.py` & `analytics/agents/tools/__init__.py` – central registry plus default tool wrappers (clarifications, SQL, chart, analysis, web, market). All flows share these implementations.
- `analytics/flows/workflow.py` – flow resolver and legacy compatibility wiring for `/api/analytics/memory/stream` with runtime feature-flag support.
- `analytics/flows/replay_benchmark.py` – CLI + helpers for running replay benchmarks across flows and exporting telemetry summaries.
- `core/events.py` / `core/telemetry.py` – SSE emission helpers and `tool_iteration` / `agent_handoff` logging used by both runtimes.
- `components/analytics/hooks/useAnalyticsMemoryStream.ts` – frontend hook that fans SSE metadata into ProcessPanel lanes, progressive transcripts, and chart panes.
- `components/analytics/memory/Page.tsx` – surfaces flow selection options and exposes the single- vs multi-agent runtime choices in the UI.

## Open Items & Follow-Ups
- Instrument baseline metrics (Phase 0 TODO) to quantify improvements post-runtime rollout.
- Implement the low-confidence confirmation guardrail in `SingleAgentRuntime` before enabling autonomous follow-ups.
- Feed replay benchmark output into dashboards/alerting so rollout comparisons are automated.
- Expand pytest coverage for runtime SSE ordering + market fallback behaviour once mock fixtures are restored.
- Coordinate with analytics telemetry owners to ensure ProcessPanel and WorkflowCanvas continue surfacing the new metadata fields without regressing legacy replays.



