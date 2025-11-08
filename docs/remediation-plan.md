# Single-Agent Remediation Plan

This document summarizes the validated issues from `docs/plan.txt` and lays out the concrete remediation work.

## 1. Deduplicate Single-Agent Telemetry _(Completed - Nov 7, 2025)_

Problem  
`_SingleAgentToolHooks` emits two `tool_end` records for a single invocation because both `classification` and `intent_detection` steps share the `intent_classifier` alias, and two separate `*_complete` events decrement the same timer queue (`backend/analytics/flows/single_agent_tools.py:710-741`). The ledger at `docs/agent-process-ledger (25).json:4130-4167` shows consecutive `Tool sql_executor completed ...` entries for the same work unit.

Approach  
1. Added multi-phase bookkeeping inside `_SingleAgentToolHooks` so shared aliases (currently `intent_classifier`) keep a single active timer and only flush once the configured terminal event (`intent_detection_complete`) fires.  
2. Introduced `_build_tool_call_event` plus `_drain_pending_multi_phase_events` helpers so the end payload is constructed in one place and any buffered metadata is emitted at flow end without double-counting.  
3. Extended `_extract_tool_details` aggregation so the final `tool_call` carries merged `intent_key`, `confidence`, and `clarifications_needed` data from both planner events.  
4. Added `test_tool_telemetry_dedup` to prove two intent events now yield exactly one `tool_end`, protecting downstream telemetry dashboards.

### Function-level work
- `flows/single_agent_tools.py::_SingleAgentToolHooks.before_event / after_event / _drain_pending_multi_phase_events`: maintain per-tool run state, buffer intermediate completion events, and emit one merged telemetry payload per alias.  
- `flows/single_agent_tools.py::_build_tool_call_event`: centralizes timer drain plus metadata attachment so future multi-phase tools can opt in declaratively.  
- `flows/single_agent_tools.py::SingleAgentController.MULTI_PHASE_TOOL_CONFIG`: documents `intent_classifier` as a multi-phase alias with `intent_detection_complete` as the terminal signal.  
- `backend/tests/analytics/test_single_agent_final_answer.py::test_tool_telemetry_dedup`: regression coverage to ensure the hook now yields one `tool_end`.

Outcome Example  
Before: log shows `Tool intent_classifier completed (...)` twice. After the fix, only one completion appears while both planner events still surface through their native channels (with merged metadata).

## 2. Respect Prefetched Accessory Lanes _(Completed - Nov 7, 2025)_

Problem  
`ensure_analysis_dependencies` can finish `web_retriever` and `stock_tracker` during the SQL lane, yet the sequencer still drives the same lanes later because their `LaneState.completed` flag never becomes true. `_kickoff_parallel_lanes` therefore schedules duplicate runs, increasing latency and wasting budget.

Approach  
1. `PlannerSequencer.mark_lane_complete` now finalizes pending lanes immediately; if a cached `web_ready` / `stock_ready` arrives before `_run_lane`, the lane transitions to `completed` with `reused=True` and is skipped later.  
2. `_SingleAgentToolHooks._update_lane_state_from_event` inspects the accessory `schedule_stage`; hedged-accessories events are treated as cache hits and forwarded to the sequencer with the reused hint.  
3. Added `test_prefetched_accessories_not_reran` to assert that prefilling both lanes results in zero downstream runner invocations while lane presentations show `reused`.

### Function-level work
- `flows/sequencer.py::PlannerSequencer.mark_lane_complete`: finalizes pending/skipped lanes when cache hits arrive early, ensuring later `_run_lane` calls no-op.  
- `flows/single_agent_tools.py::_update_lane_state_from_event`: passes hedged-accessories cache hits to the sequencer with proper reuse signals.  
- `backend/tests/analytics/test_single_agent_stream_events.py::test_prefetched_accessories_not_reran`: covers the fan-out reuse flow end-to-end.

Outcome Example  
If `ensure_analysis_dependencies` emits `web_ready` with `reused: true`, the sequencer now marks the web lane as completed, skips the later runner, and surfaces `web: reused` in its lane snapshot.

## 3. Session-Turn Revision Mode (New Requirement) _(Completed - Nov 7, 2025)_

Problem  
Revision routing currently depends on keyword heuristics in multiple layers: `analytics_memory_workflow` only flips into fast-path revision mode when the classifier detects chart/analysis cues or the route is `REUSE_SQL`/`STOCK_ONLY` (`backend/analytics/flows/workflow.py:824-1015`), `FollowUpClassifier` inspects specific substrings (`backend/analytics/routing/follow_up_classifier.py:8-96`), and the frontend historically blocked requests unless `looksLikeRevisionFollowUp` fired (`components/analytics/hooks/useAnalyticsMemoryStream.ts:120-174, 2570-2610`). The requirement is to drop keyword gating entirely so every post-result prompt reuses cached intent/plan and only refreshes the lanes the planner deems necessary.

Approach  
1. **Track session turns explicitly.** `PlannerExecutorFlow.initialize_context` (and `PlannerPhaseContext`) now emit a `session_follow_up` flag whenever cached artifacts exist; `analytics_memory_workflow` propagates it through the sequencer so telemetry knows we're in revision mode.  
2. **Skip redundant intent work.** `SingleAgentController` and `MultiAgentFlow` seed the executed set with `classification`, `intent_detection`, and `clarification`, logging `skip_reason=session_follow_up` so downstream process charts understand why those steps were bypassed.  
3. **Let agents decide lane coverage.** The revision planner still computes targets, allowing SQL or accessories to rerun when the user meaningfully changes scope mid-session.  
4. **Frontend request flow.** `useAnalyticsMemoryStream` now automatically appends the stored `session_id` after the first successful response, removes the `looksLikeRevisionFollowUp` heuristic, and surfaces a helpful error if a revision arrives after the session has expired.  
5. **Testing & telemetry.** Added `useAnalyticsMemoryStream session reuse` coverage to assert every follow-up query includes `session_id`, alongside the existing backend tests for revision routing.

### Function-level work
- `flows/planner_executor.py::PlannerExecutorFlow.initialize_context`: compute `turn_index` / `session_follow_up` based on cached artifacts and persist on the returned `PlannerPhaseContext`.  
- `flows/planner_executor.py::PlannerPhaseContext`: add the new fields and make sure `SessionStateSnapshot` serialization/deserialization includes them.  
- `flows/workflow.py::analytics_memory_workflow`: rely on `session_follow_up` instead of keyword heuristics when choosing revision routing, propagate the flag into sequencer state, and emit updated `follow_up_route` events.  
- `flows/single_agent_tools.py::_prepare_sequencer_state` & `_intent_stage`: when `session_follow_up` is true, mark `classification`, `intent_detection`, and `clarification` as executed (with `skip_reason=session_follow_up`) before persisting context so `_intent_stage` returns immediately.  
- `flows/multi_agent.py::_prepare_sequencer_state` & `_intent_stage`: mirror the single-agent behavior and seed the execution set with cached steps, emit supervisor telemetry showing `agent_turn_start`/`agent_turn_end` as `skipped`, and avoid re-running clarifications.  
- `flows/planner/revision_directive.py::derive_revision_targets` / `build_revision_plan`: accept the new session flag so SQL lanes are pulled back in when the follow-up actually changes the dataset.  
- `components/analytics/hooks/useAnalyticsMemoryStream.ts`: after the first successful response, automatically append the stored `session_id` to every subsequent request, drop the keyword gating, and return a clear error if a revision arrives without an active session.  
- Tests:  
  - `backend/tests/analytics/test_revision_routing.py`: verify `session_follow_up` skips classification yet still re-runs SQL when the revision plan requires it.  
  - `backend/tests/analytics/test_single_agent_stream_events.py` / `test_multi_agent_flow.py`: assert telemetry logs `skip_reason=session_follow_up`.  
  - `frontend/components/analytics/hooks/useAnalyticsMemoryStream.test.tsx::useAnalyticsMemoryStream session reuse`: confirm the hook always forwards `session_id` on follow-up turns.

Outcome Example
1. User: "Pull AMD revenue from 2020-2024." -> full pipeline runs, session `abc`.
2. User: "Now make the chart a stacked bar and add NVDA." -> request includes `session_id=abc`, backend flags `session_follow_up=True`, skips classification, and lets the revision plan rerun SQL + chart. The UI now automatically includes the stored session id without keyword gating, so the follow-up route banner appears immediately.

## 4. Session Lifecycle Telemetry _(Completed - Nov 7, 2025)_

Problem  
When `session_started` failed to arrive (e.g., due to cached planner shortcuts or dropped SSE chunks), neither the backend nor the React hook surfaced the active `session_id`. Follow-up queries therefore errored out with “session expired” despite the session still being valid.

Approach  
1. **Backend tagging.** Both `SingleAgentController._forward_with_hooks` and `MultiAgentFlow._forward_with_hooks` now synthesize a `session_started` event (when necessary) and stamp `session_id` onto every `follow_up_route`, `analysis_ready`, and `workflow_complete` payload. Sequencer streams mirror the same behavior so multi-agent runs always advertise their session.  
2. **Event emitters updated.** Direct `EventEmitter` callers (follow-up banners, accessory warnings, revision-ready events, workflow cancellation payloads) now include `session_id` pulled from the active context. Multi-agent lane summaries inherit the identifier as well.  
3. **Frontend persistence.** `useAnalyticsMemoryStream` deduplicates thought logs without duplicate helper definitions and stores any `session_id` seen on fallback events (e.g., `analysis_ready`, `workflow_complete`). Thus, the hook can recover even if `session_started` drops, and every follow-up request still carries the correct session.

Function-level work  
- `backend/analytics/flows/single_agent_tools.py::_forward_with_hooks / _emit_cancellation_event / analysis_revision`: session metadata helper + explicit `session_id` injection.  
- `backend/analytics/flows/multi_agent.py::_forward_with_hooks / sequencer_stream / run_web_refresh / analysis_revision`: guaranteed `session_started` emission and payload tagging.  
- `components/analytics/hooks/useAnalyticsMemoryStream.ts`: single `markThoughtIfNew` helper, `persistSessionId` wired to fallback payloads.  
- Tests:  
  - `backend/tests/analytics/test_single_agent_final_answer.py::test_session_metadata_attached_to_analysis_ready`.  
  - `backend/tests/analytics/test_multi_agent_flow.py::test_multi_agent_forward_with_hooks_tags_session_metadata`.  
  - `components/analytics/hooks/useAnalyticsMemoryStream.test.tsx::useAnalyticsMemoryStream session reuse` block now covers fallback persistence.

Outcome Example  
Even if the SSE stream skips `session_started`, the first `analysis_ready` carries `session_id=xyz`, the hook caches it, and the next user revision automatically includes `session_id=xyz`—no more false “session expired” toasts.





## 3. Accessory Fan-Out Fast-Path (Nov 8, 2025)
- `_kickoff_parallel_lanes` and `_update_lane_state_from_event` now coordinate so STOCK_ONLY + REUSE_SQL runs emit `lane_reused` before SQL drains, and warnings surface as `missing_lane_telemetry` events when web/market telemetry never arrives.
- Session fallbacks are automatic: `_forward_with_hooks` always injects `session_started`, and `_SingleAgentToolHooks` persists reuse receipts with latency metadata for Redis + canvas parity.
- Supervisor flows emit the same `agent_tool_call/complete` schema, closing the UI/documentation gap called out in §1.
- Ops can backfill previously recorded sessions via `python scripts/backfill_accessory_receipts.py --session <id>` or feed curated lists via `--session-list`.
