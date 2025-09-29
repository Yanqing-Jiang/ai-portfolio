# Analytics Concurrency Implementation TODO (September 29, 2025)

## Overview
- Deliver Mode 1 (Single Agent + Tool Fan-Out) and Mode 2 (Multi-Agent Orchestration) without regressing today's sequential UX.
- Land shared plumbing first (MemoryGate, SSE schema, internal analytics logging, test harnesses) so both modes inherit the same foundations.
- Keep all changes behind feature flags so we can fall back to the current deterministic executor instantly if needed.

## Shared Foundations
1. **Memory Gate & SessionState plumbing**
   - Stand up the `MemoryGate` policy service with adapters for transcript embeddings, tool output cache, and routing rules.
   - Persist `SessionState` in Redis only (conversation-scoped TTL, purge on idle/close) with typed repositories; keep TTL short by default (5 minutes, configurable 1-15) and drop keys as soon as the chat ends.
   - Log gate decisions and state mutations to the internal analytics event store so support can inspect timelines without external tooling.
2. **Internal observability**
   - Extend existing analytics event logging to capture `fanout_*` events, tool/agent latencies, web-search usage, and routing context.
   - Update internal dashboards to surface P50/P95 tool latency, agent handoffs, SSE retry counts, Redis hit/miss rates, and stock widget load failures; wire alert thresholds that feed the current on-call process.
   - Reuse the established metrics ingestion path-no OpenTelemetry or LangSmith; only add the new fields required for concurrency diagnosis.
3. **SSE & Event Schema updates**
   - Update `backend/analytics/core/events.py` with heartbeat envelopes, `tool_group`/`parallel_group` fields, sequence IDs, and merge metadata for multi-track payloads.
   - Patch `useAnalyticsMemoryStream`, `ProcessPanel`, and `WorkflowCanvas` to accept parallel metadata while defaulting to sequential rendering when flags are off.
4. **Testing scaffolds**
   - Build async harness utilities plus deterministic fake adapters/agents under `backend/tests/analytics/` for TaskGroup scenarios.
   - Prepare Vitest reducers and Playwright fixtures that replay concurrent SSE payloads for both tool stacks and agent swimlanes.

## Cohesive Multi-Tool Response Assembly (Mode 1)
- `ToolScheduler` runs adapters concurrently but funnels outputs through `ResultMerge`, which aligns payloads by `stepId` and timestamp before emitting combined SSE frames.
- The result serializer stitches together validated SQL summaries, chart specs, narrative snippets, stock snapshot metadata, and (when used) web context excerpts so the UI can render analysis, charts, stock visuals, and web callouts in one coherent timeline.
- Auto-generated "source badges" identify which adapter produced each chunk, mirroring multi-surface agent UI patterns from recent Microsoft Build multi-agent demos so stacked cards stay readable for end users.

## Mode 1: Single Agent + Tool Fan-Out (=5 tools)
**Phase 1 - Planner refactor & gating**
- Break `PlannerExecutorFlow.events` into phase coroutines and insert `MemoryGate` hooks.
- Introduce feature flag `ANALYTICS_TOOL_PARALLELISM` (default off).

**Phase 2 - ToolTaskGroup and adapters**
- Create `backend/analytics/flows/tooling.py` with TaskGroup scheduling, shared semaphores, and adapter registration.
- Register five adapters (tentative ordering) with policy metadata:
  1. **SQL Planner/Executor** - generate validated SQL, execute against warehouse connectors, and produce structured frames for downstream consumers.
  2. **Chart Builder** - transform result frames into exisiting ECharts specs and enforce theme presets for the frontend.
  3. **Responses API Web Retriever** - call OpenAI Responses API web search on the first turn for fresh context; MemoryGate suppresses subsequent calls for follow-up tweaks unless intent scoring flags stale data (rate limiting handled via `rate_limiter.py`).
  4. **Stock Price Tracker** - embed the TradingView Symbol Overview widget so the UI can display recent price moves for any ticker with a single script include; return normalized series to the planner for reasoning.
  5. **Narrative Synthesizer** - collate SQL + web findings into analyst-ready bullet points that SoloAgent can surface as tool reasoning or final response seeds.

**Phase 3 - Event merge & UI integration**
- Emit per-tool reasoning/status events, log them to the internal analytics store, and merge results into the existing response serializer so charts, analysis, web snippets, and stock visuals arrive in a single cohesive SSE frame.
- Implement the TradingView Symbol Overview widget with minimal styling overrides (branding tweaks not required per latest guidance); document optional hooks in case design requests future theme changes.

**Phase 4 - Rollout & safeguards**
- Staging: enable parallelism with a max of two concurrent tools, validate load, UX, and logging output.
- Production: gradually raise concurrency as metrics stay green (ceiling = five concurrent adapters) while keeping the feature flag ready for full rollback.
- Guardrails: keep automated guardrails off for v1; rely on internal event logs plus manual sampling while telemetry stabilizes.

## Mode 2: Multi-Agent Orchestration (<5 agents)
**Phase 1 - Orchestrator skeleton**
- Implement `AgentExecutionOrchestrator` with shallow DAG support (max depth 3) and TaskGroup fan-out.
- Define the agent registry with capability metadata, evaluation hooks, and latency budgets.

**Phase 2 - Agent roles, data flow, and heuristics**
- **Planner Agent**: expands the user prompt into structured tasks, triggers SQL Planner/Executor, and creates a shared context package (SQL results, tool plans, timeline). Publishes payloads into `SessionState` and the orchestration bus.
- **Analyst Agent**: consumes planner outputs plus narrative seeds, blends them with cached web context, and drafts analysis paragraphs; feeds summaries back to the bus for display and for Chart/Market agents to reference.
- **Chart Agent**: ingests planner SQL outputs and analyst highlights, chooses visual encodings, and emits Vega-Lite specs plus annotations that tie back to the narrative.
- **Market Agent**: reads planner output (ticker metadata) and analyst context, invokes the shared stock tracker adapter, then emits transient stock insights and chart overlays for the same turn (no persistence beyond the response).
- The conductor orchestrates message passing via lightweight envelopes (context IDs, revision numbers) so each specialist knows when to update or reuse prior artifacts; Redis keys deliver cross-agent state during the active session window.
- Heuristics inspired by Kairos decide whether to reuse prior SQL/chart assets or trigger new work when user intent references existing outputs (e.g., "make that chart a bar chart").

**Phase 3 - Frontend visualization**
- Render swimlanes with role colors, confidence chips, and internal replay links for debugging (ties into the analytics event viewer).
- Provide a collapse-to-sequential toggle to reduce cognitive load when fewer agents participate.

**Phase 4 - Operationalization**
- Instrument the existing logging pipeline with agent handoff counts, retries, and evaluation scores.
- Gate expensive reruns (planner re-execution or market refreshes) on policy scores; maintain runbooks for abort/resume flows.
- Guardrails remain manual for v1; rely on market telemetry and internal event logs to spot anomalies.

## Adaptive Agent & Tool Selection
- Build a routing guard ahead of `FlowSelect` that evaluates session policy context and chooses Mode 1, Mode 2, or a minimal single-tool replay.
- Store decisions and summaries in Redis with the short per-session TTL (default 5 minutes, configurable 1-15) and expire immediately when chats close to honor the ephemeral requirement.
- Surface routing choices in the UI (banner or chip) so users understand why the system stayed solo vs. escalated to orchestration.

## Validation & QA
- **Pytest**: simulate TaskGroup fan-outs, cancellation paths, Redis memory expiry, and orchestrator DAG ordering; assert internal logs contain the expected merge metadata.
- **Vitest**: cover reducer logic for `tool_group`/`parallel_group` payloads and stacked tool/agent renders.
- **Playwright**: capture end-to-end demos validating swimlanes, chart embeds, stock widget rendering, and memory reuse prompts.
- **Load**: compare sequential vs. parallel runs (Locust/k6) to ensure latency goals hold without saturating I/O.

## Ops & Rollout Checklist
- Update IaC for Redis TTL defaults, feature flags, and any new logging fields.
- Extend existing dashboards with the new metrics/alerts; verify rate limiting remains governed by `rate_limiter.py` for Responses API usage.
- Draft support playbooks for enabling/disabling flags and interpreting merged tool/agent telemetry in the internal dashboards.

## Open Questions for Stakeholder
1. Do we need additional retention controls (e.g., maximum stored artifacts per session) on top of the 5-minute Redis TTL to keep memory lean?
2. Should the internal analytics event store expose downloadable timelines for support, or is in-app playback sufficient?
3. Are there compliance considerations for storing web-search excerpts in SessionState during the active session window?
4. When presenting multiple visual assets (chart + stock widget), do we want a defined ordering or leave it chronological by completion time?
5. Should we add a lightweight "tool summary" card in the UI to reinforce how the cohesive response was assembled, or is the existing stacked layout enough?
