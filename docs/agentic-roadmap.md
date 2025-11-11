# Agentic Analytics Roadmap - November 7, 2025



This document outlines what "true agent with tools" must look like for our analytics product, why revisions need to be fully agent-driven while fresh runs can remain semi-agentic, what conditions declare success, and which code-level steps will get us there.



---



## 1. Vision



### 1.1 Revision Runs: True Agentic Loop

- **Planner-as-agent:** Every revision spins up a lightweight agent loop (planner + tool adapters) that inspects cached SQL/chart/web artifacts, reasons about what's stale, and explicitly calls tools (`sql_generation`, `chart_revision`, `web_refresh`, `analysis_revision`, etc.).

- **Tool autonomy:** The agent emits `agent_tool_call` / `agent_tool_complete` with full arguments, retries, and receipts. Accessories (web/market) are launched only when the agent decides they're required, not because the sequencer queued them.

- **UI-as-chat:** The canvas shows agent turns (reasoning text + tool calls) rather than pipeline steps, so the user sees the actual decision tree (e.g., "Skipping SQL; refreshing web for updated guidance").

- **Session-memory hydration:** Revisions always hydrate the latest `SessionStateSnapshot` revision context before choosing tools, so planner decisions about skips, reuse, or restarts are grounded in persisted receipts rather than heuristics.



### 1.2 Fresh Runs: Deterministic Full Pipeline

- **Full tool sweep:** Every fresh run executes the entire tool chain (SQL planning/execution, SQL charting, stock charting, web research, and analysis writing) via the deterministic `PlannerExecutorFlow` sequencer, regardless of prior cache state.

- **Stateless execution:** Fresh runs do not extract or rely on session memory; they only emit new receipts so revisions can consume them later, keeping first answers predictable even when revision contexts exist.



---



## 2. "Done" Criteria



We can claim the vision is met only when the following are true:



1. **Agent Loop Execution**

   - Revision requests bypass the lane sequencer and travel through an agent controller that decides which tools to call, in what order, and with which arguments.

   - The agent loop persists context between tool calls (tool receipts, artifacts, reasoning) and can short-circuit with `workflow_redirect` if it needs a fresh baseline.

   - Fresh runs stay on the deterministic sequencer and always execute SQL, chart (SQL + stock), web research, and analysis tools in sequence without skipping lanes, ensuring a full refresh independent of cache hints.

2. **Context Hydration**

   - `SessionStateSnapshot` stores structured `RevisionContext` (tool receipts, output hashes, reasoning summaries) and `PlannerExecutorFlow.initialize_context` hydrates that data for revisions so the planner knows the freshness of SQL/web/market/analysis.

   - Fresh runs skip session-memory extraction entirely; they only write receipts that revisions can hydrate later.

3. **Telemetry + UI Parity**

   - Every planner tool invocation yields `agent_tool_call` / `agent_tool_complete` events, and `useAnalyticsMemoryStream` (plus downstream UI) renders them as process steps with lane + reuse badges.

   - The frontend deduplicates `thought_id`s, handles `workflow_cancelled`/`workflow_redirect`, and logs missing accessory lanes via explicit banners.

4. **Accessory & Session Guarantees**

   - Whenever the agent requests `FULL_PIPELINE` or `STOCK_ONLY`, telemetry shows either fresh `web_ready`/`stock_ready` events or a `lane_reused` marker -- never silent omissions.

   - `session_started` (or fallback session IDs in `analysis_ready`, `workflow_complete`, etc.) always reach the client, proven by streaming tests.

5. **Multi-Agent Storyline**

   - Documentation explains how the multi-agent supervisor orchestrates specialists, aligning with OpenAI best practices (tool receipts, agent turns, delegation policy) so single-agent + multi-agent share telemetry semantics.

6. **Docs & Tests**

   - `docs/agent-optimization-findings.md`, `docs/analytics-agent-openai-sdk-roadmap.md`, `docs/remediation-plan.md`, and `docs/analytics-canvas-overview.md` all describe the agentic architecture and cite the new behaviors.

   - CI includes regression tests for agent loops, receipt hydration, accessory guarantees, and session fallbacks.



---



## 3. Task Backlog



This backlog replaces the standalone remediation, findings, SDK roadmap, and canvas overview docs so every task lives in one place.



### 3.1 Backend Agent Loop & Context

- Default classification now runs through **Gemini Flash 2.5 Lite** with automatic OpenAI fallback, so `_classification_phase` emits the new provider/model metadata without adding extra tool steps (completed November 11, 2025).
- Implement `SessionStateSnapshot.revision_context()` so every tool invocation records arguments hash, output hash, timestamps, success state, and reasoning; hydrate this inside `PlannerExecutorFlow.initialize_context` and expose helpers such as `ctx.revision_context.should_refresh('web')`.

- Route revisions through `SingleAgentController._agentic_event_stream`, drop sequencer lane pre-seeding for cached runs, and let the planner decide which tools to call via adapters supplied by `PlannerOrchestratorAdapter`.

- Enhance `PlannerExecutorFlow._stream_with_tool_state` to wrap tools with `agent_tool_call` / `agent_tool_complete` payloads (arguments, retries, lane metadata, elapsed_ms) and to feed accessory launches through `ToolParallelRuntime` when parallel fan-out is requested.

- Extend `_SingleAgentToolHooks` multi-phase bookkeeping to cover SQL generator, chart designer, and analysis writer so telemetry emits exactly one completion per alias while still merging contextual metadata (intent key, chart spec, analysis summary).

- Emit `agent_tool_call` / `agent_tool_complete` events **per child tool** during fan-out (every market question, every web retriever branch, etc.) so the thinking panel can render horizontal fan-outs for single-agent runs and vertical stacks for multi-agent supervisors.

- Teach `PlannerSequencer.mark_lane_complete`, `_run_lane`, and `abort_pending_lanes` to respect agent-directed lane skips, cache hits, and restart requests, including honoring early accessory completions from `ensure_analysis_dependencies`.

- Configure planner/model invocations according to GPT-5 best practices: pin fresh runs to `gpt-5-mini-2025-08-07` and revisions to `gpt-5-mini-2025-08-07` with higher-effort prompts only when multi-tool synthesis is required. **Do not** emit `reasoning.effort` fields in telemetry; configuration can stay internal to the orchestration layer.



### 3.2 Telemetry, Receipts & Session Reliability

- **Completed (November 11, 2025):** Emit deduplicated `thinking` logs by having `PlannerExecutorFlow._attach_thought_metadata` attach per-step `delta_text` payloads, reset caches whenever `clarification_complete/failed/skipped` fire, and teach `useAnalyticsMemoryStream` to consume those deltas so UI bubbles never replay the full transcript.

- **Completed (November 11, 2025):** Normalize supervisor receipts by making `MultiAgentFlow._receipt_is_fresh` tolerate timezone-aware timestamps (logging parse failures) and extending `scripts/agentic_smoke_test.ps1` + `.github/workflows/agentic-smoke.yml` with a supervisor fresh-run probe that fails CI unless SQL, web, and analysis lanes (or `lane_reused` equivalents) stream successfully.

- Guarantee every run emits `session_started` (or a fallback `session_id` carried in `analysis_ready` / `workflow_complete`) and surface `lane_reused_*` before `analysis_ready` whenever cached accessories satisfy `FULL_PIPELINE`, `STOCK_ONLY`, or `REUSE_SQL`.

- Synthesize cancellation events inside `_forward_with_hooks` so aborted SSE streams mark all pending lanes as `skipped` and finish with `workflow_complete` status `cancelled`, letting the frontend stop spinners instantly.

- Persist accessory receipts with `age_seconds`, `fast_path_latency_ms`, and `source_lane`, and run `scripts/backfill_accessory_receipts.py` to upgrade historical sessions so reuse heuristics stay accurate.

- Instrument telemetry with `agent_tool_gap` metrics (difference between starts/completions) for every lane and ensure Grafana alerts monitor those counts.

- Capture Guardrails verdicts (prompt-injection, hallucination, off-topic, and custom policy checks) alongside every `agent_tool_call/complete`, emitting tripwire events (`guardrail_trip`, `guardrail_recovered`) so the UI and smoke tests can prove when a run was blocked vs streamed past protections, with verdict data embedded inside the lane/node payloads rather than surfaced as separate badges.



### 3.3 Frontend Canvas & UI

- Update `components/analytics/hooks/useAnalyticsMemoryStream.ts` to ingest `agent_turn_*`, `agent_tool_*`, `lane_reused`, `workflow_redirect`, and cancellation events; coalesce `agent_tool_call`/`complete` pairs into single process cards with lane chips, retry badges, and reuse tooltips, and render fan-out as horizontal rows for single-agent runs vs. vertical columns for supervisor specialists in the thinking panel (completed November 11, 2025 with `delta_text` fallbacks so classification/clarification bubbles stay concise).

- Ensure `components/analytics/memory/Page.tsx` renders inline accessory notices ("Web lane reused - cached 64 s ago, replay 420 ms") and banners when `workflow_redirect` or `workflow_cancelled` events stream in.

- Keep WorkflowCanvas aligned with the contract in this document: lane pill states (`queued`, `running`, `fresh`, `reused`, `error`), supervisor timelines showing `agent_turn_start/end`, and tool cards annotated with planner vs. specialist roles. Fan-out children (horizontal for single-agent, vertical for multi-agent) and Guardrails verdicts should load into the Canvas/node data model without adding new badge styles.

- Maintain Vitest coverage (`WorkflowCanvas.test.tsx`, `useAnalyticsMemoryStream.test.tsx`) so every new event shape, reuse badge, or redirect banner has a golden snapshot.



### 3.4 Agents SDK & Multi-Agent Supervisor

- Keep `backend/config/schemas/agents.yaml`, `ConfigStore.get_agent_mode_config`, and `agents_stream_bridge.py` synchronized with the OpenAI Agents SDK so both single-agent and supervisor flows share tool manifests, retry policies, and SSE encoding.

- Model planner tools as Agents SDK `FunctionTool`s with strict JSON schemas, and surface `agent_tool_call/complete` events from the SDK's `Runner.stream` for SQL, chart, web, market, and analysis specialists.

- Ensure supervisor orchestration (`multi_agent.py`, `supervisor_orchestrator.py`) emits `agent_supervisor_started`, `agent_turn_start/end`, delegation summaries, and tool receipts that mirror the single-agent schema, enabling a unified UI.

- Document supervisor roles, accessory hedging, and delegation rules inline here so separate references are unnecessary.

- Use Agents SDK tracing hooks to export per-turn spans (Guardrails gating results, retries, model metadata) so we can correlate SDK traces with our ledger events—`reasoning.effort` does not need to appear in those payloads.



### 3.5 Ops, Tooling & Tests

- Keep `.github/workflows/agentic-smoke.yml` running fixture and optional live suites, archiving `agentic-smoke-*` artifacts plus ledger excerpts that prove STOCK_ONLY reuse, redirect loops, and paired `agent_tool_call/complete` entries. Each archive must include the raw SSE logs so support can replay streams without relying on derived summaries.

- Maintain the PowerShell workflow in `scripts/agentic_smoke_test.ps1` (baseline -> STOCK_ONLY follow-up -> REUSE_SQL tweak -> redirect cycle) and fail the script if telemetry lacks session IDs or lane reuse banners.

- Expand pytest coverage (`backend/tests/analytics/test_planner_sequencer.py`, `test_session_state_receipts.py`, `test_single_agent_stream_events.py`, `test_agent_orchestrator.py`, `test_multi_agent_flow.py`) plus Vitest suites so every task above is regression-tested.

- Keep Grafana alert definitions (`docs/ops/agents-supervisor-alerts.md`) aligned with the telemetry emitted here, and document the support playbook steps (session dump script, trace correlation, supervisor reset) within this roadmap for quick reference.

- Integrate OpenAI Guardrails Evaluation Tool runs into CI (comparing prompt-injection, hallucination, off-topic, and custom policy datasets) and capture the resulting reports alongside smoke ledgers so stakeholders can confirm protections are enforced for both fresh and revision flows.



---



## 4. Remediation Plan



Recent single-agent and supervisor ledgers (November 10, 2025) still lack `agent_tool_call`, `agent_turn`, `lane_reused`, and session identifiers, so we cannot prove that revisions honor the agent loop nor that fresh runs execute the full tool chain. We must close the following gaps before declaring the roadmap complete:



1. **Lock Fresh Runs to the Full Deterministic Pipeline**

   - Teach `PlannerExecutorFlow` to always schedule SQL planning/execution, SQL charting, stock charting, web research, and analysis lanes for fresh runs, even when caches exist.

   - Emit explicit telemetry (e.g., `fresh_sql_started`, `fresh_web_ready`) plus smoke-test assertions so ledgers prove every lane ran and no session memory was hydrated—no `reasoning.effort` logging is required.

   - **Function-by-function plan**

     - `backend/analytics/flows/planner_executor_flow.py:PlannerExecutorFlow.run_fresh` - hard-code the SQL -> SQL chart -> stock chart -> web -> analysis queue for fresh runs and tag each lane with `fresh_*` events.

     - `backend/analytics/telemetry/events.py:emit_fresh_lane_events` - helper that stamps `session_follow_up=false` and the lane id right after every lane completion (omit `reasoning.effort`).

     - `scripts/agentic_smoke_test.ps1` and `.github/workflows/agentic-smoke.yml` - extend the fresh-run scenario to assert all five `fresh_*` markers and fail if any session context appears.
   - **Current status (Nov 10, 2025)**
     - `PlannerPipeline._initialize_context` now skips snapshot hydration whenever `session_follow_up` is false, guaranteeing stateless fresh runs. (`backend/analytics/flows/planner_executor.py`)
     - Fresh runs tag `ctx.force_full_fresh_pipeline`, forcing SQL → chart → accessory → analysis lanes plus accessory fan-out even when caches exist. (`backend/analytics/flows/planner_executor.py`)
     - `telemetry.fresh_pipeline_lane` and `EventEmitter` markers now stream `fresh_sql_started/completed`, `fresh_web_started/completed`, etc., without including `reasoning.effort` fields. (`backend/analytics/core/telemetry.py`)
     - `test_fresh_pipeline.py` regression covers (1) snapshot-skipping fresh contexts, (2) accessory completion markers, and (3) telemetry deduping per lane change. (`backend/tests/analytics/test_fresh_pipeline.py`)
     - `scripts/agentic_smoke_test.ps1` now fails the baseline scenario whenever any `fresh_*` lane marker is missing or a `session_follow_up=true` flag leaks into the stream, giving CI concrete evidence that deterministic fresh runs avoid session hydration. (Updated November 11, 2025)


2. **Hydrate Revision Context & Enforce Agent Loop Control**

   - Extend `SessionStateSnapshot` with per-tool receipts and reasoning, hydrate that context inside `PlannerExecutorFlow.initialize_context`, and ensure revisions always enter `SingleAgentController._agentic_event_stream` (or the supervisor) instead of the sequencer.

   - Require the planner to emit `agent_tool_call/complete` for every SQL, chart, market, web, and analysis adapter decision, including skips justified via revision context.

   - **Function-by-function plan**

     - `backend/core/session_state_snapshot.py:SessionStateSnapshot.revision_context` - persist argument/output hashes, timestamps, and reasoning text per tool plus helpers like `should_refresh("web")`.

     - `backend/analytics/flows/planner_executor_flow.py:initialize_context` - hydrate the revision context and branch into either the single-agent controller or `SupervisorOrchestrator.run_revision` based on workspace mode so both revision paths stay separate.

     - `backend/analytics/controllers/single_agent_controller.py:_agentic_event_stream` - emit `agent_tool_call/complete` (with skip reasons from receipts) for every adapter invocation while keeping execution single-agent.

     - `backend/analytics/flows/multi_agent.py:SupervisorOrchestrator.run_revision` - mirror the telemetry contract for specialists and tag SSE payloads with `mode="supervisor"`.



3. **Guarantee Telemetry & Session Signals Across Modes**

   - Always stream `session_started` (or a fallback `session_id`), and surface `lane_reused_*` before `analysis_ready` whenever revisions reuse cached accessories.

   - Persist accessory receipts with freshness metadata, synthesize cancellation/redirect events, log Guardrails verdicts, and add Grafana alerts plus automated smoke checks for missing `agent_tool_gap` parity.

   - **Function-by-function plan**

     - `backend/analytics/hooks/stream_hooks.py:_forward_with_hooks` - enforce `session_started`/fallback injection, synthesize `workflow_cancelled` or `workflow_redirect`, and normalize `lane_reused_*` events.

     - `backend/analytics/accessory_receipts.py` - capture freshness metadata (`age_seconds`, `fast_path_latency_ms`, Guardrails verdicts) and expose it to Canvas and telemetry.

     - `.github/workflows/agentic-smoke.yml` plus Grafana dashboards - block deploys when `agent_tool_gap`, `lane_reused`, or `session` events go missing.



4. **Unify Supervisor & Single-Agent Event Schemas**

   - Wire `multi_agent.py`, `supervisor_orchestrator.py`, and the Agents SDK bridge so supervisor runs emit `agent_supervisor_started`, `agent_turn_start/end`, delegation summaries, and specialist tool receipts identical to the single-agent schema.

   - Ensure hedged accessories still report the same reuse/fresh markers so UI layers can treat both modes the same.

   - **Function-by-function plan**

     - `backend/analytics/telemetry/schema.py` - centralize dataclasses for `agent_turn`, `agent_tool_call`, `lane_reused_*`, and `mode` metadata consumed by both controllers.

     - `backend/analytics/sse/stream_adapter.py` - stamp SSE envelopes with `mode="single_agent"` or `mode="supervisor"` while keeping payload structures identical.

     - `backend/analytics/flows/multi_agent.py` and `backend/analytics/controllers/single_agent_controller.py` - call the shared telemetry emitters instead of bespoke logging so execution diverges but events stay uniform.

   - **Current status (Nov 10, 2025)**

    - `analytics_memory_workflow` now tags every `follow_up_route` telemetry record with `agentic_revision=true` and forces both `SingleAgentController` and `MultiAgentFlow` to bypass `PlannerSequencer` when that flag is set, so deterministic fresh-lane runs remain unaffected while supervisor-led revisions stay inside the agent loop (`backend/analytics/flows/workflow.py`, `backend/analytics/flows/multi_agent.py`).

    - `test_agentic_revision_emits_follow_up_flag` and the new `test_multi_agent_agentic_revision_skips_sequencer` guard this routing behavior, failing CI if either controller tries to spin a sequencer or drops the flag during an agentic revision (`backend/tests/analytics/test_revision_routing.py`).

    - `MultiAgentFlow._queue_artifact_event` now flows through the shared `analytics.accessory_receipts` helpers so `lane_reused` fires before `web_ready` / `stock_ready` with `age_seconds`, `fast_path_latency_ms`, and guardrail context; `test_queue_artifact_event_emits_lane_reuse_metadata` proves the metadata shows up in telemetry (`backend/analytics/accessory_receipts.py`, `backend/tests/analytics/test_multi_agent_flow.py`).



5. **Surface & Test the Experience End-to-End**

   - Update `useAnalyticsMemoryStream`, ProcessPanel, WorkflowCanvas, and related Vitest suites to display deterministic fresh-run pipelines and agentic revision turns (including banners for reused lanes or stateless fresh runs).

   - Keep `.github/workflows/agentic-smoke.yml` and `scripts/agentic_smoke_test.ps1` publishing proof artifacts that capture both a fresh full-pipeline run and a revision that hydrates session memory, so regressions are caught within CI.

   - **Function-by-function plan**

     - `src/hooks/useAnalyticsMemoryStream.ts` - parse the shared event schema, label entries with `mode`, and render deterministic fresh-run pills plus revision agent turns.

     - `src/components/WorkflowCanvas/WorkflowCanvas.tsx` and ProcessPanel - add badges for `laneReuse`, `mode`, and deterministic pipeline evidence, highlighting reused accessories with freshness metadata.

     - `src/components/WorkflowCanvas/__tests__/WorkflowCanvas.test.tsx` and `src/hooks/useAnalyticsMemoryStream.test.ts` - snapshot fresh vs single-agent vs supervisor revision transcripts.

     - `scripts/agentic_smoke_test.ps1` - archive both transcript bundles and upload them via CI for support review.
   - **Current status (Nov 10, 2025)**
     - `PlannerExecutorFlow` hard-locks fresh runs to the SQL → chart → stock → web → analysis sequence, emits `fresh_*` markers plus `telemetry.fresh_pipeline_lane`, and the frontend (`useAnalyticsMemoryStream`, ProcessPanel, WorkflowCanvas) now renders the resulting deterministic pills alongside the `Agentic Revision` badge using the shared telemetry schema. (`backend/analytics/flows/planner_executor.py`, `backend/analytics/core/telemetry.py`, `components/analytics/hooks/useAnalyticsMemoryStream.ts`, `components/analytics/common/ProcessPanel.tsx`, `components/analytics/visualization/WorkflowCanvas.tsx`)
     - `backend/tests/analytics/test_fresh_pipeline.py`, `components/analytics/hooks/useAnalyticsMemoryStream.test.tsx`, and `components/analytics/visualization/WorkflowCanvas.test.tsx` snapshot both the backend events and the UI pills so CI fails if fresh-lane or agentic evidence regresses.




### 4.6 Remaining Gaps (Function-by-Function)

- `backend/analytics/controllers/single_agent_controller.py:_agentic_event_stream` and `backend/analytics/flows/planner_executor_flow.py:_stream_with_tool_state` now follow **Option A**: `_stream_with_tool_state` emits the canonical `agent_tool_call` and `agent_tool_complete` events for every adapter (`sql_generation`, `chart_revision`, `stock_refresh`, `web_refresh`, `analysis_revision`). The payload includes `arguments_digest`, `output_digest`, `elapsed_ms`, `lane`, `mode`, and a structured `retries` array (`[{error, elapsed_ms}]`). Adaptors simply raise errors or return payloads; telemetry is centralized in the stream helper so both single-agent and supervisor runs share one choke point.
- `backend/core/session_state_snapshot.py:SessionStateSnapshot.revision_context` plus `backend/analytics/flows/planner_executor_flow.py:initialize_context` store receipts inline within the snapshot document to keep hydration fast. Each entry matches `{tool:"web", arguments_hash:"sha256(...)", output_hash:"sha256(...)", guardrail:{verdict:"pass", checks:["prompt_injection"]}, completed_at:"2025-11-10T15:04:03Z", reasoning:"Web cached 90s ago; safe to reuse"}`. Compaction strategy: receipts persist only while a session is active; `_maybe_trim_revision_context` drops entries after 20 minutes of inactivity or immediately when the user closes the chat so stale receipts never leak into fresh runs.
- `backend/analytics/hooks/stream_hooks.py:_forward_with_hooks` and `backend/analytics/accessory_receipts.py:AccessoryReceipt.store` synthesize all accessory freshness events. `_forward_with_hooks` unconditionally injects `session_started` for every stream (no feature flags) and stamps `lane_reused_*`, `workflow_cancelled`, and `workflow_redirect` events, while `AccessoryReceipt.store` records `age_seconds`, `fast_path_latency_ms`, and guardrail verdicts so Canvas shows how recently a reuse occurred.
- `backend/analytics/flows/multi_agent.py:SupervisorOrchestrator.run_revision`, `backend/analytics/orchestrators/supervisor_orchestrator.py:run`, and `backend/analytics/telemetry/schema.py:AgentTurnEvent` now stamp `mode:"supervisor"` on every SSE frame. Specialist tool records reuse the exact single-agent fields (`lane`, `elapsed_ms`, `retry_count`) and append `role:"sql_specialist"` (or similar) so Canvas timelines remain identical regardless of delegation. Hedged accessories are not modeled separately; the supervisor always issues one winning tool call.
- `src/hooks/useAnalyticsMemoryStream.ts`, `src/components/WorkflowCanvas/WorkflowCanvas.tsx`, and ProcessPanel consume the new event envelope using `agent_turn_id` as the coalescing key. Guardrail verdicts render as inline badges (“Guardrails: pass”), deterministic fresh-run pills live in the timeline header, and agent turns (single-agent or supervisor) render beneath with lane chips, reuse tooltips, and retry badges.


### 4.7 Path to Done Criteria (Non-Docs/Test)

- **Criterion 1 - Agent Loop Execution:** Fully deprecate `PlannerSequencer` for revisions. All post-answer chat traffic routes through `SingleAgentController._agentic_event_stream` (or `SupervisorOrchestrator.run_revision`), and `_stream_with_tool_state` emits `agent_tool_call/complete` for each adapter invocation. `workflow_redirect` remains available when receipts prove that a new deterministic fresh sweep is required.
- **Criterion 2 - Context Hydration:** After a fresh pipeline completes, every follow-up is strictly a revision run that hydrates the stored `SessionStateSnapshot.revision_context`. Fresh runs never extract context, and revisions always reuse the prior session memory instead of rerunning the deterministic flow; no mid-thread refresh occurs unless the agent explicitly redirects back to a full fresh run.
- **Criterion 3 - Telemetry + UI Parity:** Duplicate `thinking` events are treated as bugs. `_SingleAgentToolHooks`, `_forward_with_hooks`, and telemetry tests enforce unique `thought_id`s; if a duplicate surfaces, the backend logs the root cause (tool replay, SDK glitch, etc.) before the UI receives anything. WorkflowCanvas therefore renders a single clean reasoning bubble per planner thought without extra UX affordances.
- **Criterion 4 - Accessory & Session Guarantees:** `_forward_with_hooks` injects `session_started` in-line with every stream—no feature flags or rollout toggles—and the PowerShell smoke workflow (`scripts/agentic_smoke_test.ps1`) fails if the marker is missing. `AccessoryReceipt.store` supplies `age_seconds`/`fast_path_latency_ms` so the frontend can badge reuse freshness while maintaining Guardrails context.
- **Criterion 5 - Multi-Agent Storyline:** `agents_stream_bridge.py` emits dedicated `agent_supervisor_started` and `agent_supervisor_summary` events so Canvas can render a supervisor lane alongside specialist turns. `backend/analytics/sse/stream_adapter.py` propagates the `mode` flag plus delegation summaries, ensuring both the supervisor overview and the specialist cards share the canonical schema.


With these remediation steps in place, we can verify that every new answer starts from a stateless, complete tool sweep while every revision decision is grounded in session memory and exposed through consistent telemetry.

### 4.8 Status Update (November 11, 2025)

**Completed work**

1. **Backend agent loop & context** — `SessionStateSnapshot.record_tool_receipt` now persists argument/output digests, guardrail verdicts, lane reuse metadata, and timing digests so `_agentic_event_stream` can justify skips without replaying adapters (`backend/analytics/core/session_state.py`, `backend/tests/analytics/test_session_state_receipts.py`). `PlannerSequencer` honors agent-provided `lane_refresh_required` overrides for both optional and mandatory lanes, keeping revisions off the deterministic sequencer unless the agent explicitly redirects (`backend/analytics/flows/sequencer.py`, `backend/tests/analytics/test_planner_sequencer.py`).
2. **Telemetry, receipts & session reliability** — `_forward_with_hooks` emits `lane_reused_*` immediately after receipts hydrate, fails fast when `session_started` is absent, and propagates guardrail payloads through every `agent_tool_call/complete` envelope (`backend/analytics/flows/single_agent_tools.py`, `backend/tests/analytics/test_single_agent_stream_events.py`). Planner receipts now inject guardrail metadata into `ToolInvocationReceipt.metadata`, powering Canvas badges without extra fetches (`backend/analytics/flows/planner_executor.py`).
3. **Frontend Canvas & UI** — `useAnalyticsMemoryStream`, ProcessPanel, WorkflowCanvas, and ProcessNode consume `agent_turn_id`, guardrail badges, and the horizontal/vertical fan-out layouts introduced in Section 3.3 while deduplicating agent turns and surfacing lane reuse chips with guardrail context (`components/analytics/hooks/useAnalyticsMemoryStream.ts`, `components/analytics/visualization/WorkflowCanvas.tsx`, `components/analytics/visualization/ProcessNode.tsx`, plus updated Vitest suites).
4. **Agents SDK & supervisor parity** - `backend/config/schemas/agents.yaml` and `agents_stream_bridge.py` are regenerated from the November 2025 Agents SDK so supervisor flows emit `agent_supervisor_started` / `agent_supervisor_summary` envelopes identical to single-agent telemetry, with regression coverage in `backend/tests/analytics/test_agents_stream_bridge.py`.
5. **Ops, tooling & tests** - `.github/workflows/agentic-smoke.yml` now uploads fixture and live SSE bundles (guardrail extracts included) via the enhanced PowerShell harness, and new pytest/Vitest coverage locks down `_forward_with_hooks` guardrail telemetry plus Canvas reuse badges (`scripts/agentic_smoke_test.ps1`, `backend/tests/analytics/test_single_agent_stream_events.py`, `components/analytics/visualization/WorkflowCanvas.test.tsx`).
6. **Classification + clarification optimizations** - `_classification_phase` now runs `classify_query_async` in parallel with `resolve_intent_slots_async`, enforcing a 2.5 s timeout/fallback before caching the slot resolution on `ctx.intent_resolution`; `_intent_phase` consumes the cached slots without rerunning the resolver, and `_clarification_phase` emits explicit `clarification_complete/failed` events so `_SingleAgentToolHooks` (updated multi-phase config) flushes exactly one tool turn. Frontend ingestion (`useAnalyticsMemoryStream.ts`) dedupes `thinking` payloads via `thought_id`, and new regression tests (`backend/tests/analytics/test_pipeline_classification_intent.py`, `backend/tests/analytics/test_single_agent_stream_events.py`, `components/analytics/hooks/useAnalyticsMemoryStream.test.tsx`) cover the concurrency path plus the telemetry contract.
7. **Telemetry dedupe & supervisor receipts** - `PlannerExecutorFlow._attach_thought_metadata` now emits `delta_text` snippets for every progress/status/classification reasoning event, clears caches when `clarification_complete/failed/skipped` fire, and stamps classification events with `step` metadata so Vitest + pytest suites keep thinking bubbles from duplicating (`backend/analytics/flows/planner_executor.py`, `backend/tests/analytics/test_pipeline_classification_intent.py`, `components/analytics/hooks/useAnalyticsMemoryStream.test.tsx`). `MultiAgentFlow._receipt_is_fresh` normalizes timezone-aware timestamps and logs parse failures, while the smoke harness + GitHub workflow add a supervisor fresh-run probe and regression tests (`backend/tests/analytics/test_multi_agent_flow.py`, `backend/tests/analytics/test_agents_stream_bridge.py`, `scripts/agentic_smoke_test.ps1`, `.github/workflows/agentic-smoke.yml`) to ensure SQL/web/analysis lanes continue streaming even when cached receipts age out.

**Open items**

- None; the backlog above is cleared as of November 11, 2025. Continue monitoring CI smoke artifacts for regressions.

---



## 5. Embedded Findings, Evidence & Operational References



### 5.1 OpenAI Agents SDK Migration (Complete - November 6, 2025)

- **Execution spine preserved:** `PlannerExecutorFlow` remains the orchestrator while the OpenAI Agents SDK performs tool calls, keeping SSE payloads stable. Planner tools (SQL, chart, web, market, analysis) are modeled as strict JSON `FunctionTool`s with least-privilege manifests in `backend/config/schemas/agents.yaml`.

- **Telemetry parity:** Single-agent and supervisor runs emit identical `agent_tool_call` / `agent_tool_complete` payloads (including `tool_call.id`, `lane`, `parallel_group`, and `elapsed_ms`), so `useAnalyticsMemoryStream` renders the same cards regardless of delegation.

- **Iteration summary:**

  1. Added Agents manifests, config plumbing, and `openai-agents>=0.5.0`.

  2. Converted planner tools to function tools and streamed via `Runner.stream`.

  3. Introduced `AgentRuntime`, plan snapshots, SSE bridges, and regression tests (for example, `backend/tests/analytics/test_agent_orchestrator.py`).

  4. Synced instrumentation hooks and frontend consumers for canonical lanes.

  5. Registered supervisor specialists with least-privilege tool bundles and telemetry.

  6. Implemented revision fast paths (skip classification/clarification, hydrate `RunConfig` reasoning knobs, enforce session-based routing) plus retry ceilings and session transcript pruning.

- **Implementation footprint & readiness:** Key modules include `backend/analytics/flows/multi_agent.py`, `.../orchestrator.py`, `.../task_plan.py`, `.../hooks.py`, `core/revision_snapshot.py`, and tracing via `core.telemetry.agent_run`. Launch artifacts (`docs/ops/analytics-agents-rollout-checklist.md`, staging verification reports, Grafana monitors) are signed off for the November 10 rollout.





### 5.2 Canvas & UI Contract (Analytics Canvas Overview - November 2025)

- **Event contract:** WorkflowCanvas consumes `agent_turn_start/end`, `planner_lane_transition`, `agent_tool_*`, `analysis_streaming`/`analysis_complete`, and session metadata (`run_id`, `trace_id`, manager trace, `parallel_groups`, retry maps, delegation decisions).

- **Lane and badge behavior:** Pills display `queued/running/fresh/reused/error`, reuse tooltips (for example, "Web lane reused - cached 64 s ago, 420 ms fast-path"), and retry badges keyed off `retry_count`. Header exposes `laneReuseNotices` and sets `data-screenshot-target="workflow-canvas"` for GTM captures.

- **Supervisor timeline and tool cards:** Timeline lists each specialist's `agent_turn` with role, lane, elapsed_ms, and retry markers; tool cards label planner vs. specialist roles and reflect structured `tool_call_arguments`.

- **Final-answer and error UX:** `analysis_complete` then `final_answer` drive CTA state, while lane errors surface sequencer `failure_markers`.

- **Support playbook:** Troubleshooting flow pulls session dumps via `scripts/dump_agents_stream.py`, inspects `agent_retry_rate` alerts, and resets sessions via `/admin/sessions/<id>/reset`. Reference asset `docs/design/workflow-canvas-20251114.svg` documents badge/layout standards.





### 5.3 Agent Optimization Findings (Root-Cause Log - November 7, 2025)

1. **Multi-phase tool duplication:** `_SingleAgentToolHooks` emitted multiple completions for SQL/chart/analysis. Fix includes extending `MULTI_PHASE_TOOL_CONFIG`, aggregating metadata in `_build_tool_call_event`, and shipping `test_tool_telemetry_dedup`.

2. **Repeated "thinking" bubbles:** SSE replayed entire `thinking` arrays. Backend now attaches monotonic `thought_id`s / diffs, while `useAnalyticsMemoryStream` dedupes per-step logs to cut bubble spam.

3. **Missing cancellation events:** `_forward_with_hooks` now emits synthetic `workflow_complete status=cancelled` and marks pending lanes as skipped whenever streams abort, preventing ghost "in progress" spinners.

4. **Accessory fan-out gaps:** Sequencer respects prefetched `web_ready/stock_ready`, dispatches accessories immediately after `sql_ready`, and emits `lane_reused` with `age_seconds` / `fast_path_latency_ms`.

5. **Accessory fast-path validation (Nov 8):** `SessionStateSnapshot` receipts store reuse metadata, Grafana alerts monitor `agent_tool_gap`, and `scripts/backfill_accessory_receipts.py` upgrades legacy sessions.

6. **Canvas telemetry parity (Nov 8):** WorkflowCanvas and ProcessPanel share reuse banners, redirect notices, tool badges, and Vitest snapshots.

7. **Automation and alerting hooks (Nov 8):** `.github/workflows/agentic-smoke.yml` publishes fixture artifacts and optional live runs; the Grafana "Agent Tool Gap" alert ties to telemetry.

8. **Session lifecycle fixes:** Restored `session_started`, injected fallback IDs into `analysis_ready` / `workflow_complete`, and taught the frontend to persist session context-eliminating false "session expired" errors.



7. **Automation and alerting hooks (Nov 8):** `.github/workflows/agentic-smoke.yml` publishes fixture artifacts and optional live runs; the Grafana "Agent Tool Gap" alert ties to telemetry.

8. **Session lifecycle fixes:** Restored `session_started`, injected fallback IDs into `analysis_ready` / `workflow_complete`, and taught the frontend to persist session context-eliminating false "session expired" errors.



### 5.4 Single-Agent Remediation Outcomes (Completed - November 7, 2025)

- **Telemetry deduplication:** `_SingleAgentToolHooks` buffers intermediate planner events so each alias emits exactly one completion; `_drain_pending_multi_phase_events` and `test_tool_telemetry_dedup` guard regressions.

- **Prefetched accessory lanes:** `PlannerSequencer.mark_lane_complete` and `_update_lane_state_from_event` finalize recycled `web` / `market` lanes immediately, preventing duplicate executions and surfacing `reused` pills.

- **Session-turn revision mode:** `PlannerExecutorFlow` tracks `session_follow_up`, seeds executed steps with `skip_reason=session_follow_up`, and lets agents decide which lanes rerun; the frontend automatically appends the stored `session_id` to every follow-up request.

- **Session telemetry guarantees:** `_forward_with_hooks` (single and multi-agent) always emits `session_started` or stamps IDs onto downstream events, while `useAnalyticsMemoryStream` stores fallback IDs so revisions never fail due to missing telemetry.



