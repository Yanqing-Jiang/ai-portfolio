# Analytics Agent -> OpenAI Agents SDK Migration

This roadmap tracks the end-to-end migration of the analytics planner to the OpenAI Agents SDK. The engagement delivers a production-ready single-agent experience plus a supervisor-led team of specialists while preserving planner determinism, SSE semantics, and resumable long-running tasks.

## Context
- Keep `PlannerExecutorFlow` as the execution spine; Agents SDK runs own tool calls so existing SSE payloads remain intact.
- Exhaust single-agent capabilities before introducing specialists; split responsibilities only when tool catalogs become unwieldy.
- Represent planner tools as Agents SDK function tools with strict JSON schemas for auditability and structured outputs.
- Follow the manager-as-tool orchestration pattern so one supervisor coordinates specialists without relinquishing control.
- Apply least-privilege practices to every specialist and run intent classification plus clarification before any fan-out.

## Delivery Status (Complete - November 6, 2025)
### Iteration 1 (November 4, 2025)
- Added `backend/config/schemas/agents.yaml` with first-class instruction, retry, and model metadata for `single_agent` and `supervisor` modes.
- Extended `backend/analytics/core/config.py` and `core/config_store.py#get_agent_mode_config` to hydrate Agents SDK manifests without hardcoded strings.
- Enriched `PlannerToolRegistry` definitions with JSON parameter/response schemas, retryable error codes, and telemetry metadata.
- Declared `openai-agents>=0.5.0` in `backend/requirements.txt` to pick up the November 5, 2025 release containing `Runner.stream` tracing hooks.

### Iteration 2 (November 4, 2025)
- Converted every planner tool into an Agents SDK `FunctionTool` and exposed structured receipts/summaries per invocation.
- Materialized the single-agent controller `Agent` using YAML instructions and model metadata; seeded per-run context to stream tool deltas into the existing SSE channel.
- Introduced telemetry helpers (`_extract_tool_receipt`, `_summarize_tool_result`, `_collect_artifacts_snapshot`) to preserve cache and artifact reporting without duplicating planner logic.
- Routed `Runner.stream` through `analytics_memory_workflow` with retry accounting and single-agent smoke tests.

### Iteration 3 (November 6, 2025)
- Created `backend/analytics/agent_orchestrator/` (plan state, runtime loop, SSE bridge, session-backed memory helpers) so single-agent runs follow a persisted plan -> act -> observe cycle.
- Extended `agents.yaml` defaults (plan templates, retry policy) and taught `ConfigStore.get_agent_mode_config` to deep-merge nested dictionaries.
- Routed `SingleAgentController` through `AgentRuntime`, persisted plan snapshots via `AgentMemory`, and reused `AgentsStreamBridge` for streaming.
- Captured the orchestrator contract in `docs/design/agent-orchestrator.md` and added `backend/tests/analytics/test_agent_orchestrator.py` to assert plan hydration, SSE emission, and session persistence.

### Iteration 4 (November 6, 2025)
- Updated `backend/analytics/flows/instrumentation.py` and `single_agent_tools.py` so Agents SDK streaming events inherit canonical lanes, schedule metadata, and persist into `SessionStateSnapshot` receipts.
- Added regression coverage in `backend/tests/analytics/test_single_agent_stream_events.py`, refreshed `components/analytics/hooks/useAnalyticsMemoryStream.ts` and its Vitest suite for lane ordering, and wired `analytics_memory_workflow` directly to `Runner.stream`.

### Iteration 5 (November 6, 2025)
- Registered SQL, web, market, and analysis specialists in the supervisor manifest and exposed least-privilege tool bundles.
- Enriched supervisor telemetry with `agent_turn_start` / `agent_turn_end` payloads, updated frontend consumers, and executed live delegation through `Runner.stream`.
- Finalized lane-specific adapters, added integration coverage for fresh and revision runs, and prepared the frontend for removing legacy planner hooks.

## Implementation Footprint (Complete)
- `backend/analytics/flows/multi_agent.py`: registers supervisor + specialists, enforces retry policy, emits agent reasoning, and persists receipts.
- `backend/analytics/flows/orchestrator.py`: coordinates specialist DAG execution with concurrency limits, retry decider, and structured result events.
- `backend/analytics/flows/task_plan.py`: hydrates supervisor task queues, applies guardrails, and marks continuable steps.
- `backend/analytics/flows/schedulers.py`: injects mode metadata (flow mode, agent role, retry ceiling, supervisor model) into every SSE payload.
- `backend/analytics/flows/hooks.py`: binds Agents lifecycle callbacks so telemetry stays synchronized with retries.
- `backend/analytics/core/revision_snapshot.py`: stores supervisor task outcomes, retry attempts, and specialist error codes for future revision planning.
- Tests: `backend/tests/analytics/test_multi_agent_flow.py` covers supervisor orchestration, hedged accessory fan-out, and analysis synthesis; additional suites cover orchestrator runtime and streaming events.

## Shared Tooling & Infrastructure (Complete)
- `flows/tooling.WebRetrieverAdapter.expand` emits structured summaries, latency stats, and retryable error codes matching Agents schemas.
- `flows/tooling.MarketQuestionAdapter` and `StockTrackerAdapter` operate as planner tools and supervisor specialists with consistent retry metadata.
- `core/cache.CacheService` stores Agents run hashes, retry counts, and failure markers and resets caches on session timeout or new session start.
- `core/events.EventEmitter` adds `agent_turn_start`, `agent_turn_end`, and `tool_retry` without breaking existing enums.
- `core/config_store.ConfigStore` manages agent instruction templates, tool allowlists, retry policies, and model selections per flow mode.
- `services/response_search.generate_search_topics` enables supervisor multi-topic fan-out with cached topic metadata.
- `core/session_state.SessionStateRepository` enforces the 10 minute session timeout, clears receipts on expiry, and records Agents trace identifiers.
- `docs/analytics-canvas-overview.md` documents the UI contract for agent metadata, retry signals, and role indicators.

## Evaluation, Telemetry & Ops (Complete)
- Agents SDK tracing integrated: `core.telemetry.agent_run` forwards run ID, trace ID, manager trace ID, retry maps, and parallel groups.
- Automated evaluation added to CI via the analytics pytest harness (see `backend/tests/analytics/test_multi_agent_flow.py`).
- Logging sinks capture supervisor critiques, retry rationales, and structured outputs for audits.
- `docs/ARCHITECTURE.md` updated with Agents SDK dependencies, intent gating, retry policies, session timeouts, and telemetry fields.
- Staging verification captured in `docs/ops/staging-verification-report-2025-11-06.md` with SSE samples and command transcripts.

## External Research & References
- `docs/references/openai-agents-python-readme-2025-11-03.md`
- `docs/references/openai-agents-patterns-2025-11-04.md`
- Internal notes on manager-as-tool orchestration (see `docs/design/agent-orchestrator.md`).

## Launch Readiness (Complete - November 6, 2025)
1. **Staging Verification & Sign-off**
   - Replay completed via pytest harness; SSE traces and telemetry snapshots archived in `docs/ops/staging-verification-report-2025-11-06.md`.
   - Sign-off package circulated to product, design, and support with cache receipt diffs.

2. **Production Rollout & Monitoring**
   - Controlled rollout window scheduled; on-call checklist published in `docs/ops/analytics-agents-rollout-checklist.md`.
   - Synthetic monitors plus dashboard alerts (tool retry rate, agent_turn errors, SSE delivery latency) defined in `docs/ops/agents-supervisor-alerts.md`.
   - Pre-warm scripts documented for intent, SQL, web, and market caches.

3. **Post-Launch Training & Documentation**
   - `docs/analytics-canvas-overview.md`, release notes, and support macros updated with agent lifecycle indicators and retry semantics.
   - Support handover session material logged in `docs/ops/support-macros-agents.md`.

## Current State
All migration objectives are complete. Supervisor-led multi-agent flows share the same telemetry, cache, and SSE contracts as the single-agent path, and launch readiness artifacts are signed off for production deployment during the week of November 10, 2025.
