# Agent Refactor Roadmap

## Phase 0 - Research & Alignment
- Document Claude simple-agent lessons (start with narrow objectives, add tools iteratively, enforce explicit guardrails) and map them to analytics needs.
- Inventory existing planner-executor dependencies the agents still rely on (clarifications, SQL retries, telemetry, caching).
- Baseline current latency/error metrics so we can compare once agents diverge from PlannerExecutorFlow.

### Findings (2025-10-04)
- Claude simple-agent playbook stresses **narrow initial scope**, stand-alone tool contracts, and explicit guardrails; mapping this to analytics means starting with revenue/margin workflows and codifying tool schemas before exposing broader KPIs.
- Existing dependencies: PlannerExecutor handles clarifications (`backend/analytics/core/clarify.py`), SQL retries (`build_sql_retry_messages`), telemetry (`responses_call`, SSE sequencing), and cache updates (`session_state`). These must be reimplemented or wrapped for tool-native agents.
- Before replacing the planner, capture baseline metrics (classification pass rate, average web search latency, SQL retry counts). Hook existing telemetry tables or logs so Phase 5 comparisons are possible.

## Phase 1 - Shared Tool Surface
- Create a lightweight `analytics.agents` package housing a `ToolRegistry`, `AnalyticsTool` interface, and typed payload schemas.
- Wrap existing capabilities (SQL builder, warehouse query, chart designer, web search, clarification) as concrete tools with deterministic inputs/outputs.
- Provide a tracing-aware `invoke` helper so tool usage is logged and recoverable if the agent loops.

### Progress (2025-10-04)
- Introduced `analytics.agents.tool_registry` with async-aware `AnalyticsTool`/`ToolRegistry` abstractions.
- Added default tools covering clarification, SQL planning/execution, charting, analysis summarization, and web search (all reuse planner helpers).
- `SingleAgentRuntime` auto-registers these tools and exposes `invoke_tool` for future Claude-style loops.

## Phase 2 - Single-Agent Runtime (Claude Simple-Agent Style)
- Author a system prompt that encodes the minimal flow (clarify -> build SQL -> execute -> summarize) and references the new tool names.
- Build a `SingleAgentRuntime` that handles chat state, tool invocation, and stop conditions (max tool calls, token budget) without PlannerExecutorFlow.
- Implement safety rails inspired by Claude practice (structured error replies, user-intent confirmation when low confidence).

### Progress (2025-10-04)
- Converted `SingleAgentRuntime.handle_user_message` into an async Claude-style loop that routes tool calls and final replies via an injectable Responses adapter.
- Added per-tool logging hooks, guardrails (max tool calls/turns), SSE-compatible events (`agent_turn`, `tool_call`, `analysis_streaming`), and helper APIs (`invoke_tool`, `set_llm_adapter`).
- Implemented `analytics.agents.llm_adapter.build_responses_llm_adapter` to call the Responses API with structured JSON output guidance.
- Tool invocations now emit `tool_iteration` telemetry with start/end/error envelopes, preserving the planner-era analytics stream.
- Promoted the runtime as the default single-agent flow (legacy wrapper remains available as `single-agent-legacy`).

## Phase 3 - Multi-Agent Orchestrator
- Define role prompts (planner, query, analyst, chart, market, web) that describe responsibilities and available tools.
- Implement an orchestration harness that takes planner output as tasks, parallelizes when safe, and persists shared context across agents.
- Add conflict-resolution rules (e.g., analyst waits for query results) and fallbacks when a specialist exhausts retries.

### Progress (2025-10-04)
- `analytics.agents.multi_runtime.MultiAgentRuntime` now orchestrates planner → query → chart / analyst / market / web specialists with structured context sharing.
- Chart, analyst, market, and web specialists execute in parallel with retry + fallback handling; agent turns emit `retry` / `failed` envelopes so telemetry captures recovery steps.
- Introduced the `market.snapshot` tool (Polygon-backed) and environment flag `ANALYTICS_MARKET_WIDGET` so market enrichment can be toggled independently.

## Phase 4 - Telemetry & UX Integration
- Mirror existing SSE envelopes (`tool_call`, `agent_turn`, `analysis_streaming`) so the frontend remains compatible.
- Capture per-tool metrics (latency, error category) and emit Claude-style reasoning traces for observability.
- Update ProcessPanel/WorkflowCanvas expectations to reflect the tool-native flows.

### Progress (2025-10-04)
- SSE payloads now carry per-session `sequence`, `responseId`, specialist metadata (`market`, `market_tickers`), and retry status so dashboards can line up runtime vs. planner events.
- Frontend hooks consume the additive fields without breaking legacy replay data; ProcessPanel lanes display market/web specialists alongside planner/query/analysis updates.

## Phase 5 - Rollout & Migration
- Run side-by-side experiments comparing the new runtimes against PlannerExecutorFlow on recorded conversations.
- Gate rollout behind feature flags (`ANALYTICS_AGENT_RUNTIME=planner|single|single-runtime|multi`) for staged deployment.
- Produce runbooks covering failure modes, manual override to legacy planner, and prompts maintenance.

### Progress (2025-10-04)
- Flow selection honours `ANALYTICS_AGENT_RUNTIME` (with planner/single/multi + legacy aliases) while retaining `ANALYTICS_FLOW_MODE` for backwards compatibility.
- Added `backend/analytics/flows/replay_benchmark.py` to run replay benchmarks and capture latency/tool-call metrics per flow.
- Authored `backend/analytics/analytics_rollout.md` documenting rollout checklists, flag toggles, rollback steps, and validation commands.
- Next: feed replay benchmark output into Grafana dashboards and add pytest coverage for SSE ordering + market snapshot fallbacks once mocks are ready.
