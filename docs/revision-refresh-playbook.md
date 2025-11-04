# Revision Refresh Playbook

## Objectives
- Restore tool fan-out during legacy revision runs by guaranteeing planner context always carries intent, plan, and slot metadata before any refresh work begins.
- Guarantee refreshed web snippets flow into the reused analysis narrative without re-emitting unrelated lane payloads.
- Prevent frontend revision bubbles (`analysis_only` route) from resurfacing stale chart/SQL/stock content while keeping the collapsed web card available.
- Backfill automated coverage so snapshots lacking planner scaffolding cannot regress silently.

## Snapshot Reliability (Stabilization Completed November 3, 2025)
- Added the merge-aware `_merge_revision_snapshot` helper so `_persist_session_state` preserves `tool_cache.analytics.revision_snapshot` even when stale writers save later.
- Wrapped the helper in a three-attempt optimistic retry loop with warning telemetry when merges cannot stick.
- Expanded `backend/tests/analytics/test_analysis_revision.py` to cover stale saves and concurrent writers.
- Removed temporary `[REVISION_DEBUG]`, `[SESSION_SAVE]`, and `[SESSION_LOAD]` instrumentation logs after persistence stabilized.

## Current Status & Evidence
- Planner persistence now reconstructs intent and plan before saving, logging both input receipts and snapshot payloads (`[REVISION_SNAPSHOT] stored`, `[TOOL_RECEIPTS] persisted`).
- End-to-end replays finish with “Revision complete” events, but `/api/debug/session/{id}` still omits `tool_cache.tool_receipts` and `tool_cache.analytics.revision_snapshot`, so rehydrate telemetry cannot rely on persisted state.
- `[REHYDRATE]` instrumentation inside `PlannerPipeline.rehydrate_revision_plan` remains silent; only upstream `[ANALYSIS_REFRESH] pre-rehydrate` messages appear.
- Latest replay artifacts (2025-11-03):
  - Baseline ledger: `docs/agent-process-ledger-debug-20251103T063715-baseline.json`
  - Revision ledger: `docs/agent-process-ledger-debug-20251103T063717-revision.json`
  - Session dump: `docs/session-debug-7ac52bf2-71ee-4075-bce5-710f3cfea052.json`
  - Backend log snippet illustrates receipts + revision snapshot stored, but debug endpoint reload drops them.

## Outstanding Gaps
1. **Missing persisted payloads** — repository load used by the debug endpoint only returns `tool_cache.analytics.artifacts*`; `tool_cache.tool_receipts` and `tool_cache.analytics.revision_snapshot` disappear after persistence.
2. **Rehydrate telemetry** — helper logs never emit, so success/failure is inferred indirectly.
3. **Frontend visibility** — UI shows a generic `rehydrate_revision_plan` error on helper failure and lacks richer diagnostics.
4. **Web refresh propagation** — refreshed snippets are not copied onto `ctx.web_search` before persisting, allowing stale web banners to return.

## Backend Fix Backlog
1. **Planner Context Rehydration Helper**
   - Implement `PlannerPipeline.rehydrate_revision_plan(ctx)` in `backend/analytics/flows/planner_executor.py`.
   - If `_hydrate_context_from_snapshot` leaves intent/plan empty, replay `intent_detection` and/or `plan_generation` via the planner tool registry, persisting artifacts after each tool.
   - Update tool receipts (status/timestamps) and copy derived fields (intent signature, slot statuses, follow-ups) onto `ctx`.
2. **Integrate Helper Before Web Refresh**
   - In `run_analysis_refresh` for single- and multi-agent flows, invoke the helper immediately after `initialize_context` and before `_reset_revision_accessories`.
   - Fail fast with a warning when rehydration cannot restore intent/plan.
3. **Dual-Topic Seeding Without Truncation**
   - Only synthesize fallback topics when `revision_directive.search_topics` is empty; append to existing topics without dropping more than five.
   - When no directive exists, store fallback topics on `ctx.revision_search_topics` so `WebRetrieverAdapter.expand` consumes them.
4. **Web Context Propagation**
   - After `refresh_web_lane`, assign the newest web payload to `ctx.web_search` before persisting.
   - Mark untouched lanes (`sql`, `chart`, `market`) as reused via `ctx.lane_refresh_required`.
5. **Follow-up Emission Hygiene**
   - Ensure `analysis_revision` emits only analysis text plus refreshed web payload by clearing chart/market artifacts and `ctx.tool_parallel_results` prior to `_persist_session_state`.
6. **Session Snapshot Serialization**
   - Update `SessionStateRepository.save/load` so `tool_receipts` and `analytics.revision_snapshot` survive round-trips; add unit coverage that serializes/deserializes these keys.
7. **Testing**
   - Extend `backend/tests/analytics/test_analysis_revision.py` with scenarios covering helper replay, fallback topics, and web payload propagation.

## Frontend Fix Backlog
1. **Stream Sanitization**
   - In `components/analytics/hooks/useAnalyticsMemoryStream.ts`, when `follow_up_route === 'analysis_only'`, null out `workflowDataRef.current` attachments and matching React state before `refreshResultMessage`.
   - Preserve the latest web payload or create the lightweight stub expected by ChatHistory.
2. **Result Bubble Updates**
   - Update `appendResultSnapshot` so `replacePriorResult` clears attachment arrays for analysis-only revisions.
   - Ensure `refreshResultMessage` respects sanitized refs to prevent stale attachments from reappearing.
3. **Tests**
   - Add UI tests (e.g., `ChatHistory.test.tsx`) verifying analysis-only revisions render the analysis plus collapsed web card with empty chart/sql widgets.
   - Add hook-level tests to confirm stream sanitization works.

## Verification Workflow
1. Run a baseline analytics query (single-agent).
2. Immediately fetch the Redis entry to confirm `revision_snapshot` exists.
3. Trigger an analysis-only revision; confirm the run avoids `rehydrate_revision_plan` errors.
4. Validate the ledger shows `web_revision_ready` and `analysis_revision` events instead of the failure banner.
5. Re-run pytest suites (`pytest backend`) to confirm no regressions.

## Cleanup & Monitoring
- Remove legacy debug instrumentation once the fixes are validated.
- Document completed steps in this playbook, and consider a nightly health check that executes baseline + revision and asserts snapshot persistence.
