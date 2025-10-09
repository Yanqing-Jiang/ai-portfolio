# Option B - Schedule + Cohesive Stabilization Plan
_Drafted: October 9, 2025_

## Snapshot
Multi-agent ledger (17) still loops: hedged accessories never resolve, schedule annotations remain `unknown`, and cohesive emission stalls. Single-agent flow completes cleanly (ledger 16). Next phase focuses on locking hedged completion, logging canonical stages, and surfacing the metadata in the UI before re-enabling automation.

## Backend objectives
1. **Ledger annotation plumbing**
   - Pipe `schedule_stage`, `parallel_group`, and `mode` into serialized ledger rows (via `instrumentation._enrich_event`) so replay CLI and frontend consumers see canonical stages.
   - Add a daily replay job (PowerShell script + `analytics.scripts.schedule_replay` helper) that flags ledgers missing schedule annotations.
2. **Hedged accessory completion guard**
   - Track cached/live web retriever completion explicitly and emit `hedged_accessories_complete` before orchestration continues.
   - If hedged tools fail, emit `cohesive_result_error` with a `retryable` guard and expose the error via ProcessPanel.
3. **Cohesive payload sanitization**
   - Sanitize non-JSON objects (slice, Decimal, datetime) ahead of ledger persistence.
   - Record sanitized bundle snapshots for revisions in `SessionStateSnapshot` and surface warnings when fields drop.
4. **Follow-up routing telemetry**
   - Persist schedule history with flow mode and stage ordering to support multi-agent follow-up classifiers.
   - Expose `/api/analytics/schedules/<session_id>` for manual inspection.

## Frontend objectives
1. **ProcessPanel badge updates**
   - Display schedule stage + mode pills for every ledger entry (done for ChartCard, extend to panel entries and WorkflowCanvas nodes).
   - Add lane filters (core / tool_fanout / specialist_fanout) to isolate stalled stages.
2. **WorkflowCanvas instrumentation**
   - Render canonical stage ordering across the canvas, with hedged accessory nodes labeled `cached web` / `live web` to show completion state.
   - Provide zoom presets for supervisor vs. accessory lanes to address the existing zoom complaint.
3. **Status indicator for cohesive payloads**
   - Add a cohesive badge on AnalysisCard/ProcessPanel when chart/sql/stock/web artifacts are present; highlight missing artifacts in amber.

## Rollout plan
- **Week 1**: backend ledger annotations, hedged completion guard, CLI integration.
- **Week 2**: frontend ProcessPanel/WorkflowCanvas badges, cohesive indicator, Storybook updates.
- **Week 3**: staging bake (manual multi-agent runs, replay CLI reporting, finalize docs).
- Update `current_identified_issues.md` once hedged guard and UI badges ship.
\n### Backend updates (Oct 9, 2025 late)\n- Flow schedule emits now map planner/clarifier/tool_fanout/agent lanes so replay CLI resolves canonical stages.\n- Instrumentation sanitizes all SSE payloads and records per-event schedule history (flow mode included) for ledger exports.\n- Multi-agent flow emits explicit 'hedged_accessories_complete' and sanitizes tool bundles to prevent slice-related bundle errors.\n
- Partial artifact streaming: multi-agent now queues sanitized sql/chart/stock/web ready events so frontend can render artifacts as soon as specialists finish.

