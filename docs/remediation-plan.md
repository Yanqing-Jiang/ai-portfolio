# Single-Agent Remediation Plan

This document summarizes the validated issues from `docs/plan.txt` and lays out the concrete remediation work.

## 1. Deduplicate Single-Agent Telemetry

Problem  
`_SingleAgentToolHooks` emits two `tool_end` records for a single invocation because both `classification` and `intent_detection` steps share the `intent_classifier` alias, and two separate `*_complete` events decrement the same timer queue (`backend/analytics/flows/single_agent_tools.py:710-741`). The ledger at `docs/agent-process-ledger (25).json:4130-4167` shows consecutive `Tool sql_executor completed ...` entries for the same work unit.

Approach  
1. Give each planner step its own telemetry alias (for example `intent_classifier_ingest` and `intent_classifier_refine`) or add a per-step completion flag so only the first matching `TOOL_END_EVENTS` entry drains `_tool_active_counts`.  
2. Update `TOOL_METADATA_*` maps so dashboards still group both phases under a human friendly label.  
3. Teach `_extract_tool_details` to merge data from both events (classification vs intent detection) so the surviving `tool_end` carries the combined metadata.  
4. Extend `backend/tests/analytics/test_single_agent_final_answer.py` with a fixture that feeds duplicated planner events and asserts every tool only yields one `status: "end"` entry. Use `sql_executor` as the regression example by emitting two `execution_stats` events but expecting a single telemetry record.

Outcome Example  
Before: log shows `Tool sql_executor completed (638ms)` followed immediately by `Tool sql_executor completed (674ms)`. After the fix, only one completion appears while both planner events still surface through their native channels.

## 2. Respect Prefetched Accessory Lanes

Problem  
`ensure_analysis_dependencies` can finish `web_retriever` and `stock_tracker` during the SQL lane, yet the sequencer still drives the same lanes later because their `LaneState.completed` flag never becomes true. `_kickoff_parallel_lanes` therefore schedules duplicate runs, increasing latency and wasting budget.

Approach  
1. When `_update_lane_state_from_event` handles `web_ready` or `stock_ready`, immediately call `sequencer.mark_lane_complete` with `reused=True` so the lane transitions to `completed` status (`backend/analytics/flows/single_agent_tools.py:2468-2525`).  
2. Add a guard in `_run_lane` to skip launching a lane whose state is already completed (defensive recheck in `backend/analytics/flows/sequencer.py:499-526`).  
3. Add unit tests that pre-populate `tool_parallel_result` events for web/market and assert `run_web_stage` and `run_market_stage` mocks are never awaited.  
4. Optionally emit a dedicated telemetry event (for example `tool_fanout_cache_hit`) so the UI can label these accessories as reused rather than pending.

Outcome Example  
If `ensure_analysis_dependencies` emits `web_ready` with `reused: true`, the sequencer should now mark the web lane as completed, skip the later runner, and show `web: reused` in its lane snapshot.

## 3. Session-Turn Revision Mode (New Requirement)

Problem  
Revision routing currently depends on keyword heuristics in multiple layers: `analytics_memory_workflow` only flips into fast-path revision mode when the classifier detects chart/analysis cues or the route is `REUSE_SQL`/`STOCK_ONLY` (`backend/analytics/flows/workflow.py:824-1015`), `FollowUpClassifier` inspects specific substrings (`backend/analytics/routing/follow_up_classifier.py:8-96`), and the frontend blocks requests unless `looksLikeRevisionFollowUp` fires (`components/analytics/hooks/useAnalyticsMemoryStream.ts:120-174, 2570-2610`). The new requirement is to drop keyword gating entirely: after the first successful run in a session, every subsequent prompt must be treated as a revision, with the single- or multi-agent flow deciding which lanes (SQL, chart, analysis, web, market) to refresh. We must also skip the classification / intent / clarification stages on these follow-up runs to cut latency. For example, today a user can say "start over with cash flow instead" and we rerun the entire pipeline as if it were a new question; going forward the same message should reuse cached intent/plan automatically and only rerun the lanes the agent deems necessary.

Approach  
1. **Track session turns explicitly.** Extend `PlannerPhaseContext` with a `turn_index` or `is_follow_up_turn` flag populated inside `_initialize_context` (`backend/analytics/flows/planner_executor.py:4398-4462`). When `session_id` is provided *and* the session snapshot already holds chart/analysis artifacts (baseline ready), set `is_follow_up_turn=True`. Persist this flag on the context so both single-agent and supervisor flows can key off it. Example: first query “Show TSLA revenue” (no `session_id`) → `turn_index=1`; follow-up “now include GOOG” with the stored `session_id` → `turn_index=2`.
2. **Force revision routing after turn 1.** In `analytics_memory_workflow` (`backend/analytics/flows/workflow.py:794-1055`), replace the keyword-driven `should_take_revision` logic with a simple check: `if turn_index > 1 and baseline_ready` then operate in revision mode. Keep the revision fast path for pure chart/analysis tweaks, but otherwise feed the request back into the normal sequencer with `ctx.revision_targets` prefilled. Remove the `needs_sql_lane` guard so revisions can include SQL when the agent asks to “rebuild the dataset”. Emit `follow_up_route` events that reflect the agent’s chosen scope (e.g., “multi_lane_revision”) instead of the old `chart_revision`/`analysis_revision` labels.
3. **Skip classification / intent / clarification automatically.** In `SingleAgentController._prepare_sequencer_state` (`backend/analytics/flows/single_agent_tools.py:928-1185`) and `MultiAgentFlow._prepare_supervisor_state` (`backend/analytics/flows/multi_agent.py:3394-3530`), short-circuit the entire intent stack whenever `ctx.is_follow_up_turn` is true. Concretely, mark `classification`, `intent_detection`, and `clarification` as executed with reason `session_follow_up`, emit the corresponding `log_tool_iteration` skip events, and persist cached planner state to ensure downstream lanes have the latest receipts. This guarantees the sequencer jumps straight to SQL/chart lanes on second and later turns.
4. **Let agents decide lane coverage.** Rather than relying on keyword buckets, feed the raw follow-up query plus prior artifacts into the existing `RevisionDirective` + `derive_revision_targets` pipeline (`backend/analytics/flows/planner/revision.py:150-239`). For typical prompts:  
   - “Make the chart a bar chart” → derived targets `{chart}`; revision plan keeps SQL cached, reruns chart/analysis.  
   - “Add AWS revenue too” → no explicit target, so default to `{sql, chart, analysis, web}` while still skipping intent/clarification.  
   - “Just refresh the market data” → follow-up classifier can still suggest `{market}`, and the plan collapses to stock-only lane.  
   Both SingleAgent and MultiAgent flows should respect these targets via `build_revision_plan / apply_revision_plan`, ensuring multi-lane revisions remain coherent without re-entering classification.
5. **Frontend request flow.** Remove the guard that refuses revisions without a `session_id` (`components/analytics/hooks/useAnalyticsMemoryStream.ts:2570-2590`). Instead, treat any query after the first completed response (`resultSentRef.current === true`) as a follow-up: always append `session_id`, surface a banner such as “Revision run scheduled”, and rely on backend routing. This means queries like “Compare it to NVDA now” no longer get blocked just because they lack keywords.
6. **Testing & telemetry.**  
   - Update `backend/tests/analytics/test_revision_routing.py` so that a second-turn generic question emits `revision_request` and *does not* log `classification_started`.  
   - Add coverage for SQL-included revisions (second-turn query requesting new filters) to ensure the pipeline still runs SQL while classification stays skipped.  
   - On the frontend, add a hook test verifying that two sequential queries automatically send the stored `session_id` with no keyword checks.  
   - Expand telemetry dashboards to bucket `skip_reason=session_follow_up` so ops can confirm the new behavior is active.

Outcome Example  
1. User: “Pull AMD revenue from 2020-2024.” → full pipeline runs, session `abc`.  
2. User: “Now make the chart a stacked bar and add NVDA.” → request includes `session_id=abc`, backend flags `turn_index=2`, skips classification, derives revision targets `{chart, analysis, web}` plus `{sql}` because the user asked to “add NVDA”. Single-agent sequencer reruns SQL + chart concurrently, logs `intent_classifier` skip with reason `session_follow_up`, and the UI shows a “Revision run scheduled” banner instead of reissuing the “start a new analysis” error.

## Unresolved Questions

1. When a user explicitly wants a brand-new baseline mid-session (“forget the previous run and start over”), should we introduce a “reset session” affordance or automatically spawn a new session id? Aligning on this UX will determine whether the backend ever needs to re-enable the full classification stack inside an existing session.
