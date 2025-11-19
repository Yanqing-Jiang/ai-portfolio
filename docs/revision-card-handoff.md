# Revision Card Handoff (November 18, 2025)

## Scope
- Consolidates the previous revision handoff brief with "Analytics Stream Refactor Summary & Plan" so all guidance for revisions, telemetry, and useAnalyticsMemoryStream now lives in one document.
- Tracks the outstanding issues uncovered on November 18, 2025 when single-agent and multi-agent revision requests replayed full deterministic runs before emitting revision cards.

## Goal
Keep the original fresh-run evidence visible for audit, but once a user triggers a revision question only stream the targeted revision cards (analysis + web) so neither single-agent nor multi-agent flows replay the deterministic pipeline or emit duplicate telemetry.

## Agent Behavior Vision
- **Single-agent authenticity.** `SingleAgentController` must rehydrate the `AgentRuntime` plan-act-observe loop for every revision, emit `agent_coordination` + `agent_turn_*` telemetry, and only fall back to deterministic planning when the runtime is offline and the UI shows `revision_agent_disabled`.
- **Multi-agent supervision.** `MultiAgentFlow` routes revision directives through the supervisor orchestration, records Gemini bundles per specialist, and guarantees the supervisor stream is the only source of cards or tool receipts during revision mode.
- **Evidence-first telemetry.** Both flows persist revision question bundles, agent run receipts, and tool spans so ledgers and UI artifacts can prove an agent (not the planner) produced the revision output.

## Regression Evidence (November 18, 2025)
- `docs/agent-process-ledger - 2025-11-18T180425.243.json` (single-agent) shows `Agent Tool Execution` invoking `web_retriever` with the original query before `analysis_revision`, and its `agent_coordination` block is empty, proving the deterministic planner reran despite the documentation change.
- `docs/agent-process-ledger - 2025-11-18T180527.762.json` (multi-agent) shows `tool_fanout` launching `web_retriever_*` with `questions.source = "planner_topics"` plus no `agent_turn_*` telemetry, meaning the supervisor never took ownership and the UI only saw a fresh replay.
- Neither ledger emits `revision_inputs_outcome`, `agent_turn_start`, or `agent_turn_end`, so the UI cannot distinguish cached vs. real revisions and keeps the redundant fresh cards.

## Legacy Analytics Stream Refactor Summary
### Overview
This section preserves the prior analytics_stream_refactor_summary.md content so the hook refactor history stays collocated with the revision plan. The refactor focused on `components/analytics/hooks/useAnalyticsMemoryStream.ts`, eliminating type errors, lint issues, and runtime instability tied to `updateStepStatus` argument limits.

### Summary of Actions Taken
#### 1. Type Definitions & Missing References
- Added the missing `workflowDataRef` definition with full typing for `revisionQuestions`, `webQuestions`, and `requestedGranularity`.
- Ensured `ToolFanoutManifest` exposes the `tool` property wherever it is accessed.

#### 2. Function Structure & Scope
- Fixed `normalizeWebContext` by moving helper functions (`mergeSnippetArrays`, `mergeWebContexts`) to the correct scope.
- Refined the `updateStep` wrapper so it no longer calls `stepsHook.updateStepStatus` with too many arguments and no longer sits inside the suppressedRevisionSteps set definition.

#### 3. Argument Count & Type Mismatches
- Updated every `stepsHook.updateStepStatus` call (market, web, etc.) to respect the seven-argument contract by folding optional metadata into the data object.
- Removed the stray comparison in the `mixed_revision` switch and explicitly typed callback parameters that previously defaulted to `any`.
- Fixed `sqlQuery` assignments so `null` is not written to string-only fields.

#### 4. Lint Error Fixes
- Added `requestedGranularity: null` during `workflowDataRef.current` resets and removed the duplicate `snapshotReuse` entry.
- Set `updateAgentCoordination` to write the allowed `completed` status instead of `stopped`.
- Declared `item` as `any` within `normalizeWebContext` snippet mapping and closed the `suppressedRevisionSteps` set before defining `updateStep`.

### Current Status
`useAnalyticsMemoryStream.ts` now compiles without the earlier type errors, `updateStep` is correctly defined, and `workflowDataRef` initialization aligns with the hook reset path.

### Outstanding Next Steps (from original refactor)
1. Run a final manual review or build check to ensure the hook changes introduced no regressions.
2. Exercise the analytics stream in the app to confirm the refactored `updateStepStatus` calls behave as expected.

## Step-by-Step Remediation Plan
### Backend � Single-Agent Flow
1. **Honor `_resolve_agentic_revision_flag`.** Short-circuit `SingleAgentController.run_analysis_refresh` once the flag is true by routing directly into `_run_agentic_revision_flow` and returning the resulting ready event.
2. **Agent-only lane execution.** Move both web refresh and analysis revision work under `_execute_revision_lane_from_agent`, passing `pre_refreshed_web` and `forced_web_ready_seen` into `analysis_revision` so telemetry reflects agent-sourced data.
3. **Guard deterministic fallbacks.** Raise `AgentRevisionLaneMissing` whenever the agent runtime fails to emit a lane decision; convert that into a single `revision_agent_disabled` guardrail and never call `_forward_with_hooks(_stream_lane())` afterward.
4. **Persist receipts.** Ensure `SessionStateSnapshot.record_agent_run` captures web + analysis turns and emit `agent_coordination`, `agent_turn_start`, and `agent_turn_end` events before streaming the revision card.

### Backend � Multi-Agent Flow
1. **Disable planner instrumentation.** Update `analytics_memory_workflow._stream_revision_fast_path` so any agentic revision sets a latch that prevents `PlannerExecutorFlow.events()` from emitting `fresh_*` steps after the revision question arrives.
2. **Supervisor ownership.** In `MultiAgentFlow.run_analysis_refresh`, call `_stream_agentic_revision` whenever `_agentic_revision_mode` is true, emitting deterministic lanes only when the revision directive is explicitly non-agentic.
3. **Outcome tracking.** Have `_stream_agentic_revision` persist `_revision_inputs_outcome`, the supervisor Gemini bundle, and per-specialist receipts before returning so the ledger proves which agent produced the card.
4. **Guardrail surfacing.** If the supervisor runtime fails to emit a lane decision, raise `AgentRevisionLaneMissing` so the caller surfaces `revision_agent_disabled` instead of replaying the deterministic manifests.

### Telemetry & Receipts
1. Write `revision_inputs_plan`, `revision_inputs_outcome`, and `agent_coordination` records for every revision request, along with explicit `web_topics_pending` / `web_topics_ready` events tied to Gemini progress.
2. Ensure the SSE stream carries `agent_turn_*`, `tool_start`, and `tool_end` spans before `analysis_revision_ready` so the UI can gate rendering on proven agent output.

### Frontend & UI Evidence
1. Extend `useAnalyticsMemoryStream` so it mutes `fresh_*` steps whenever `agenticRevisionActive` is true, buffers revision text until both Gemini topics finish, and emits topic progress state for each `WebSearchCard`.
2. Thread the topic progress object through `ProcessPanel`, `LiveArtifacts`, and `WebSearchCard`, displaying `Agent Verified`, `Agent Disabled`, or `Agent Fallback` badges based on the telemetry payload.
3. Add tests (`useAnalyticsMemoryStream.test.tsx`, `WebSearchCard.test.tsx`) that replay recent ledger captures to verify buffering, badge updates, and the absence of duplicate fresh cards after revisions.

### Validation & Documentation
1. Re-run both single-agent and multi-agent revision flows, capture fresh ledgers, and confirm they contain agent telemetry without planner reruns before closing the remediation items in `docs/agent-process-ledger-investigation.md`.
2. Once validated, attach screenshots/log excerpts to this document and the investigation brief so support can reference the evidence without reopening raw ledger JSON.

## Immediate Fix Plan (November 19, 2025 @ 20:05Z)
1. **Backend telemetry sequencing**
   - Update `_stream_revision_fast_path` so it only emits `web_topics_pending` when a revision starts and defers `web_topics_ready` until the corresponding `web_ready`/`web_research_agent` completion event arrives. Capture the final Gemini bundle (both user + industry prompts) at that point and re-emit the `revision_questions` payload alongside the ready event.
   - Ensure `run_web_refresh` (and its multi-agent analogue) forwards a signal when each topic branch completes so `_stream_revision_fast_path` can determine when the pair is done. If either branch errors, mark it `error` but still keep the other branch pending until it reports.
2. **Analysis gating**
   - Teach `SingleAgentController.analysis_revision` (and MultiAgentFlow) to defer the `analysis_revision_ready` SSE until `topicProgress.pending === 0`. Concretely, require `web_ready_seen` *and* `topic_status == ready` before emitting the ready card so the UI never renders partial prompts.
   - Persist the finalized `web_topics_ready` payload on `SessionStateSnapshot` so subsequent revisions or UI replays can recover the exact user/industry questions that shipped with the card.
3. **Frontend synchronization**
   - Update `useAnalyticsMemoryStream` to treat `web_topics_pending` as the start of a new topic batch (resetting `topicProgress` and holding analysis text in the buffer) and only flush the buffer when the `web_topics_ready` event arrives with `pending=0`.
   - Add regression tests that stream: pending -> single branch ready -> final ready. Assert that the hook keeps `analysis` empty until `pending=0` and that both user + industry prompts appear in `topicProgress.branches`.
4. **Validation**
   - Replay the failing ledger after the change, confirm both question types are present in `analysis`. Capture fresh back-to-back ledgers (single- and multi-agent) and attach them to this document plus `agent-process-ledger-investigation.md`.
## Progress Log (November 18, 2025)
- Replayed `docs/agent-process-ledger - 2025-11-18T180425.243.json` to confirm the single-agent flow still runs the deterministic planner before emitting revision cards.
- Compared `docs/agent-process-ledger - 2025-11-18T180527.762.json` to verify multi-agent revisions never hand off to the supervisor orchestration and therefore lack agent telemetry.
- Documented that earlier attempts to edit `components/analytics/hooks/useAnalyticsMemoryStream.ts` failed because `apply_patch` rejected the file encoding, so no code changes were actually committed despite the previous write-up.

## Immediate Fix Plan (November 19, 2025 @ 20:05Z)
1. **Backend telemetry sequencing**
   - Update `_stream_revision_fast_path` so it only emits `web_topics_pending` when a revision starts and defers `web_topics_ready` until the corresponding `web_ready`/`web_research_agent` completion event arrives. Capture the final Gemini bundle (both user + industry prompts) at that point and re-emit the `revision_questions` payload alongside the ready event.
   - Ensure `run_web_refresh` (and its multi-agent analogue) forwards a signal when each topic branch completes so `_stream_revision_fast_path` can determine when the pair is done. If either branch errors, mark it `error` but still keep the other branch pending until it reports.
2. **Analysis gating**
   - Teach `SingleAgentController.analysis_revision` (and MultiAgentFlow) to defer the `analysis_revision_ready` SSE until `topicProgress.pending === 0`. Concretely, require `web_ready_seen` *and* `topic_status == ready` before emitting the ready card so the UI never renders partial prompts.
   - Persist the finalized `web_topics_ready` payload on `SessionStateSnapshot` so subsequent revisions or UI replays can recover the exact user/industry questions that shipped with the card.
3. **Frontend synchronization**
   - Update `useAnalyticsMemoryStream` to treat `web_topics_pending` as the start of a new topic batch (resetting `topicProgress` and holding analysis text in the buffer) and only flush the buffer when the `web_topics_ready` event arrives with `pending=0`.
   - Add regression tests that stream: pending -> single branch ready -> final ready. Assert that the hook keeps `analysis` empty until `pending=0` and that both user + industry prompts appear in `topicProgress.branches`.
4. **Validation**
   - Replay the failing ledger after the change, confirm both question types are present in `analysis`. Capture fresh back-to-back ledgers (single- and multi-agent) and attach them to this document plus `agent-process-ledger-investigation.md`.
## Progress Log (November 19, 2025)
- Implemented durable revision-plan telemetry: SSE now emits `revision_inputs_plan`, `revision_inputs_outcome`, `web_topics_pending`, and `web_topics_ready`, while `SessionStateSnapshot` stores the same payloads for audit (`backend/analytics/core/session_state.py`, `backend/analytics/flows/workflow.py`, `backend/tests/analytics/test_revision_routing.py`).
- Hardened agent guardrails: SingleAgentController and MultiAgentFlow persist `agent_coordination` receipts, short-circuit deterministic fallbacks when `_resolve_agentic_revision_flag` is set, and raise `revision_agent_disabled` before any planner replay (`backend/analytics/flows/single_agent_tools.py`, `backend/analytics/flows/multi_agent.py`, `backend/analytics/flows/planner_executor.py`).
- Frontend now respects the topic-progress/evidence contract by muting fresh-lane badges during agentic revisions, buffering narrative text until Gemini topics finish, and surfacing agent evidence badges across LiveArtifacts/ProcessPanel (`components/analytics/hooks/useAnalyticsMemoryStream.ts`, related tests + WebSearchCard topic-progress coverage).
- Immediate Fix Plan (November 19, 2025 @ 20:05Z) executed: `_stream_revision_fast_path` only emits `web_topics_pending`/`ready` after real Gemini completions, the controllers stash topic-branch progress before raising `analysis_revision_ready`, and `useAnalyticsMemoryStream` buffers analysis text until `pending=0`. Regression coverage added via `test_revision_routing.py` + the new `buffers analysis updates until topic branches finish` vitest case (`backend/analytics/flows/workflow.py`, `backend/analytics/flows/single_agent_tools.py`, `backend/analytics/flows/multi_agent.py`, `components/analytics/hooks/useAnalyticsMemoryStream.test.tsx`).
## Unresolved Questions
- None.
