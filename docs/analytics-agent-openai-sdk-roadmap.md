# Analytics Agent -> OpenAI Agents SDK Migration

This roadmap translates the architecture in backend/analytics/ARCHITECTURE.md into a function-by-function plan for delivering (1) a true single-agent experience with expansive tool coverage and (2) a supervisor-led team of specialists powered by the OpenAI Agents SDK. The plan preserves the existing planner core, telemetry, and cache semantics while ensuring long-running tasks remain resumable.

## Context
- Keep PlannerExecutorFlow as the execution spine and let Agents SDK runs drive tool calls so deterministic planner behavior and existing SSE payloads stay intact.
- Exhaust single-agent capabilities before introducing extra agents; split responsibilities only when instructions and tool catalogs become unwieldy (OpenAI Agents Quickstart, 2025-10-21).
- Represent planner tools as Agents SDK function tools with strict JSON schemas to guarantee auditability and structured outputs (Agents SDK Function Tool reference, 2025-10-28).
- Follow the manager-as-tool orchestration pattern so a single supervisor coordinates specialists without losing control (Agents-as-tools guide, 2025-10-18; Run modern agents tutorial, 2025-10-17).
- Apply Claude Code subagent practices - focused roles and least-privilege tool grants - to every specialist we register (Claude Code tool best practices, 2025-10-28).
- All flows must run intent classification and clarification (core.intent.classify_query_async, detect_intent, resolve_intent_slots_async) before any tool fan-out so long-running work always starts with validated queries.

### Status — November 4, 2025 (Iteration 1)
- ✅ Added `backend/config/schemas/agents.yaml` with first-class instruction, retry, and model metadata for `single_agent` and `supervisor` modes so runtime code can hydrate Agents SDK runners without hardcoded strings. (Pulled model/runner defaults from OpenAI Agents SDK README, refreshed 2025-11-03.)
- ✅ Extended config hydration (`backend/analytics/core/config.py`, `.../config_store.py#get_agent_mode_config`) to surface agent manifests alongside existing YAML schemas.
- ✅ Enriched `PlannerToolRegistry` definitions with JSON parameter/response schemas, retryable error codes, and telemetry metadata to meet Agents SDK function tool contract.
- ✅ Declared `openai-agents>=0.3.3` in `backend/requirements.txt`, aligning with the current PyPI release that ships `Runner.run`, `Runner.stream`, and tracing hooks referenced in the latest OpenAI Agents documentation (2025-11-03).
- 🔄 Next in-flight: wrap `SingleAgentController` around an Agents SDK runner that converts the enriched planner tools into `function_tool` exports and streams outputs back through existing SSE hooks.
- 📌 Research artifact: `docs/references/openai-agents-python-readme-2025-11-03.md` (new) captures the sections on `Runner.run`, `Runner.stream`, session handling, and function tool decoration for traceability.

### Status — November 4, 2025 (Iteration 2)
- ✅ Converted every planner tool into an Agents SDK `FunctionTool`, added strict schema enforcement, and exposed receipts/summaries per invocation so the single-agent runner can return structured deltas.
- ✅ Materialized the single-agent controller’s OpenAI `Agent` instance using the new YAML instructions/model metadata; seeded per-run context objects to stream tool outputs into the existing SSE channel.
- ✅ Queued telemetry helpers (`_extract_tool_receipt`, `_summarize_tool_result`, `_collect_artifacts_snapshot`) to ensure agent runs emit cache, retry, and artifact payloads without duplicating planner logic.
- 📄 Captured external research highlights in `docs/references/openai-agents-patterns-2025-11-04.md` (new) to document orchestration trade-offs, manager-as-tool best practices, and evaluation guidance.
- 🚧 Remaining single-agent work: wire `Runner.run` / streaming queue into `analytics_memory_workflow`, add retry accounting, and backfill smoke tests before shifting focus to supervisor orchestration.

## Supervisor & Specialist Operating Model (User Decisions)
- The supervisor agent owns task decomposition, orchestrates retries, and can invoke a specialist up to two additional times when the specialist returns an explicit error code; once retries are exhausted the supervisor logs the failure and advances the schedule.
- Specialists stream directly into existing lanes while the supervisor supplies ordering metadata so the current card stack contract is preserved.
- Keep the roster minimal: one SQL lane agent with multiple planner tools, one web lane agent, one stock lane agent, and one analysis agent that synthesizes after upstream lanes finish.
- SQL, web, and stock specialists may run concurrently; the analysis specialist waits for all upstream lanes (success or error) before producing the final narrative and card stack.
- The supervisor retains session cache and passes relevant context to specialists; each specialist stores lane-specific cache for the active session. Caches reset after 10 minutes of inactivity or when the user starts a new chat.
- The supervisor handles all revision reassignments; user feedback always routes through the supervisor before triggering specialist reruns.
- Errors never block downstream execution - after the retry limit, the supervisor marks the lane status and continues so the analysis specialist can incorporate partial results.
- Specialists operate autonomously during their turn; the supervisor intervenes only on errors. No additional human approval loop is required.
- Automated evaluation stays minimal (smoke tests only); production validation happens manually post-deployment.

---

## Single-Agent Mode (true single agent + multiple tools)

### backend/analytics/flows/workflow.py
- FLOW_FACTORIES / get_available_flows: register the Agents-backed SingleAgentController variant and expose mode metadata (model alias, tool policy) for the frontend picker.
- _agentic_revision_enabled: extend env toggles so single-agent runs can request critique/self-review passes while honoring retry and cache guardrails.
- analytics_memory_workflow(): wrap Agents Runner.run(...); translate streamed responses into SSE events, attach session IDs, record tool receipts, and ensure intent clarification runs before invoking any tools.
- _resolve_lane_ttls / set_lane_refresh_requirements: keep TTL logic in sync with supervisor directives so cached accessories remain consistent across retries.

### backend/analytics/flows/single_agent_tools.py
- SingleAgentController.__init__: instantiate the Agents SDK agent with planner-aware instructions, default tool manifest, and run config sourced from ConfigStore.
- _build_single_agent_cohesive_payload: embed Agents run metadata (run ID, model, tool calls) alongside artifacts so the UI can badge cache reuse vs. fresh work.
- _agentic_event_stream / events: execute the Agents runner, forward streamed response.output items after the intent clarification stage, and translate tool deltas into lane summaries for the SSE stream.
- _invoke_planner_tool: call Agents function tools with strict schemas, pass retryable error codes back to the supervisor, and enforce planner guardrail hooks.
- chart_revision, run_web_refresh, run_market_refresh: issue scoped Agents tool calls while tagging revision directives for cache reconciliation and retry tracking.
- _forward_with_hooks: enrich telemetry (core.telemetry.tool_iteration) with Agents message IDs, retry counts, and error codes to support long-running diagnostics.

### backend/analytics/flows/planner_executor.py
- PlannerExecutorFlow.events: host planner stages inside an Agents execution context; emit tool start/complete metadata compatible with Agents streaming and record retry outcomes.
- _seed_web_search_from_payload / _seed_stock_widget_from_payload: prepopulate tool outputs to skip redundant invocations when receipts are fresh.
- _evaluate_latency_guardrail: surface guardrail verdicts via Agents hooks and include retry context when thresholds are breached.
- run_planner_executor(): expose a helper that spins up the Agents runner for deterministic testing.
- Propagate tool error codes to the supervisor so retries can execute without halting the pipeline.

### backend/analytics/flows/pipeline_tools.py
- get_planner_tool_registry: rebuild planner tools as Agents function tools with JSON schemas, retryable error codes, and severity levels.
- build_planner_manifest: add tool descriptions, concurrency hints, and guardrail policies so the single agent can select tools intelligently.

### backend/analytics/flows/tool_bundle.py
- collect_tool_bundle: merge Agents tool outputs (including run IDs and error retries) into the reusable bundle for cohesive payload reuse.

### backend/analytics/core/session_state.py
- SessionStateSnapshot.record_tool_receipt: persist Agents call signatures, arguments, run IDs, structured output hashes, and retry counts; associate them with lane TTL data.
- SessionStateRepository._read_ttl_from_env: enforce the 10-minute session timeout and clear caches when sessions expire or restart.

### backend/analytics/core/telemetry.py
- tool_iteration, agent_handoff, analysis_chunk: include Agents run identifiers, retry counts, and error codes so traces can be replayed for long-running tasks.

### backend/analytics/services/response_search.py
- generate_search_topics / perform_response_search: accept Agents tool context, return schema-compliant payloads, surface guardrail verdicts, and emit retryable errors when needed.

### backend/analytics/services/polygon.py
- fetch_daily_snapshot: align responses with structured tool schemas, attach freshness metadata, and surface retryable error codes for market data lapses.

### backend/main.py
- /api/analytics/stream: annotate streamed events with Agents mode details (model, supervisor on/off) and expose retry/error metadata for the frontend.

### Tests
- backend/tests/analytics/test_single_agent_*: mock Agents runs to validate schema enforcement, retry handling, and telemetry fields.
- Vitest suites under components/analytics: update SSE mocks to include Agents metadata, retry counts, and lane summaries.

---

## Supervisor + Specialists Mode (true supervisor with tool use)

### backend/analytics/flows/workflow.py
- analytics_memory_workflow(): route multi-agent sessions through the Agents supervisor runner after intent clarification; manage parallel specialist runs and stream results in lane order.
- _agentic_revision_enabled: honor AGENTIC_REVISION_MULTI_AGENT flags while keeping retry policies aligned with supervisor rules.

### backend/analytics/flows/multi_agent.py
- MultiAgentFlow.__init__: create the supervisor agent and register specialists (SQL, web, stock, analysis) as callable tools following the manager-as-tool pattern.
- _prepare_context: load planner context, cache receipts, and retry budgets into the supervisor agenda before issuing tasks.
- _run_agent_orchestration: execute supervisor plans, capture tool invocations, enforce the two-retry limit, and map outputs to ROLE_LANES for the SSE stream.
- _maybe_agent_turn_start / _maybe_agent_turn_end: emit explicit agent_turn_start/stop events with retry metadata for observability.
- _agent_reasoning: surface supervisor critiques and retry rationales as analysis_revision events when loops occur.
- events: merge supervisor outputs with planner artifacts, ensure SQL/web/stock specialists finish (success or failure) before handing context to the analysis specialist, and continue despite errors once retries are exhausted.
- chart_revision / apply_chart_revision: direct targeted revisions to the chart specialist, honoring cache state and retry policies.

### backend/analytics/flows/orchestrator.py
- AgentExecutionOrchestrator.run: coordinate supervisor and specialist calls via the Agents runner, enforce concurrency limits, and manage retryable errors without duplicating completed work.
- AgentResult.to_events: tag SSE payloads with agent roles, run IDs, retry counts, and error codes to aid downstream analysis.
- AgentSpec: tighten instructions, allowed tools, and guardrail hooks per specialist, reflecting least-privilege guidance.

### backend/analytics/flows/task_plan.py
- AgentTaskPlan.build_from_context: translate planner outputs into supervisor task queues with cache hints and retry budgets per lane.
- AgentTaskStep.apply_guardrails: validate structured outputs, log retry attempts, and mark steps as continuable when errors persist so the supervisor can proceed.

### backend/analytics/flows/schedulers.py
- apply_mode_metadata: augment events with flow_mode, agent_role, agents_run_id, retry counts, and error codes.
- FlowMode.MULTI_AGENT config: define concurrency limits, default models, retry ceilings, and guardrail policies per specialist lane.

### backend/analytics/flows/hooks.py
- AnalyticsFlowHooks: register Agents lifecycle callbacks (on_tool_started, on_tool_completed, on_tool_error) to keep telemetry synchronized with supervisor retries.

### backend/analytics/core/revision_snapshot.py
- extract_revision_snapshot: store supervisor task outcomes, retry attempts, and specialist error codes for future revision planning.

### Tests
- backend/tests/analytics/test_multi_agent_flow.py: simulate supervisor runs, assert retry behavior, and verify SSE events include agent roles, retry counts, and error statuses.
- Add integration coverage for concurrent SQL/web/stock execution followed by analysis synthesis.

---

## Shared Tooling & Infrastructure
- flows/tooling.WebRetrieverAdapter.expand: emit structured summaries, latency stats, and retryable error codes that comply with Agents schemas.
- flows/tooling.MarketQuestionAdapter / StockTrackerAdapter: ensure adapters operate both as planner tools and as supervisor specialists, returning structured payloads with retry metadata.
- core/cache.CacheService: store Agents run hashes, retry counts, and failure markers; reset caches on session timeout or new session start.
- core/events.EventEmitter: support new event types (agent_turn_start, agent_turn_end, tool_retry) while keeping existing enums unchanged for UI compatibility.
- core/config_store.ConfigStore: manage agent instruction templates, tool allowlists, retry policies, and model selections per flow mode.
- services/response_search.generate_search_topics: allow the supervisor to request multi-topic fan-out via structured inputs and cache topic metadata for reuse.
- core/session_state.SessionStateRepository: enforce the 10-minute session timeout and clear receipts when sessions expire or restart, ensuring long-running tasks do not reuse stale state.
- docs/analytics-canvas-overview.md: update the UI contract to describe Agents metadata, retry signals, and agent role indicators.

---

## Evaluation, Telemetry & Ops
- Integrate Agents SDK tracing so every run logs tool calls, retries, guardrail verdicts, and handoffs; forward trace IDs via core.telemetry.
- Incorporate OpenAI agent evaluation recipes into CI for smoke coverage of single-agent tool selection and supervisor delegation.
- Extend logging sinks to capture supervisor critiques, retry rationales, and structured outputs for post-run audits.
- Update docs/ARCHITECTURE.md once migration lands, noting Agents SDK dependencies, intent gating requirements, retry policies, session timeouts, and new telemetry fields.

This function-by-function plan keeps the existing analytics experience intact while enabling long-running, updateable tasks to run under the OpenAI Agents SDK with a supervisor and specialist team.

---

## External Research Highlights (November 4, 2025)
- OpenAI’s orchestration guide reiterates that hierarchical “agent-as-tool” designs keep a single thread of control while still supporting parallel specialist execution—ideal for our supervisor delegating SQL, web, and market lanes before synthesis. citeturn0search0turn0search3turn0search10
- Manager patterns complement deterministic code orchestration; combining LLM-driven planning with explicit scheduling delivers predictable latency while retaining adaptive rerouting when specialists fail. citeturn0search1turn0search5turn0search8
- Handoff-based delegation remains a fallback for peer agents, but the manager-as-tool pattern offers better observability and aligns with our session cache + retry rules where the supervisor must log every tool result. citeturn0search3turn0search11

Research dumps:
- `docs/references/openai-agents-python-readme-2025-11-03.md` – canonical Runner/function-tool notes.
- `docs/references/openai-agents-patterns-2025-11-04.md` – curated excerpts on manager vs handoff and multi-agent portfolio patterns (new).

---

## Outstanding Work (Tracking to MVP)
1. **Single-agent streaming parity**
   - Replace planner event loop with `Runner.run`/`RunResultStreaming.stream_events` and translate queue items into SSE payloads.
   - Fold retry/error metadata into `EventEmitter` data and ensure planner receipts reconcile with Agents trace IDs.
   - Add pytest smoke covering: intent gate → tool selection → SSE lane ordering (cached vs fresh).
2. **Supervisor + specialists over Agents SDK**
   - Instantiate supervisor agent with manager-as-tool pattern; expose SQL/web/market/analysis specialists via `as_tool()`.
   - Implement concurrency gates (await all upstream lanes before analysis) and enforce two-retry policy with structured error codes.
   - Extend multi-agent flow hooks to broadcast `agent_turn_start|end` and retry events back to the UI.
3. **Shared infrastructure + cache discipline**
   - Persist Agents run IDs, tool attempts, and retry counters in `SessionStateSnapshot` + cache TTL logic.
   - Augment telemetry sinks (`core.telemetry`, tracing exporters) to include manager trace IDs for audits.
   - Document new fields and dependency bumps in `backend/analytics/ARCHITECTURE.md` and frontend SSE schemas.
4. **Validation & Observability**
   - Add evaluations for single-agent tool selection and supervisor delegation (OpenAI eval recipes).
   - Smoke test revision lanes (chart/analysis/market) under both single-agent and supervisor modes.
   - Prepare rollout checklist (env flags, cache warmers, evaluation scripts) before prod launch.
