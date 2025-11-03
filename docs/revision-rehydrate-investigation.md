# Analysis Revision Rehydrate Investigation Notes

## Current Status
- Planner persistence now reconstructs intent and plan before saving, and `_persist_session_state` logs both the input receipts as well as the snapshot payload (`[REVISION_SNAPSHOT] stored` / `[TOOL_RECEIPTS] persisted`).
- End-to-end replays complete without surfacing the prior `rehydrate_revision_plan` error, and the agent stream finishes with "Revision complete" events.
- Despite the new plumbing, the debug endpoint `/api/debug/session/{id}` still omits `tool_cache.tool_receipts` and `tool_cache.analytics.revision_snapshot`, so rehydrate telemetry cannot yet rely on persisted state.
- `[REHYDRATE]` instrumentation inside `PlannerPipeline.rehydrate_revision_plan` remains silent even though the helper is invoked from `single_agent_tools`; we only capture the upstream `[ANALYSIS_REFRESH] pre-rehydrate` messages.

## Latest Replay Evidence (2025-11-03)
- Baseline ledger: `docs/agent-process-ledger-debug-20251103T063715-baseline.json`
- Revision ledger: `docs/agent-process-ledger-debug-20251103T063717-revision.json`
- Session dump (`/api/debug/session/7ac52bf2-71ee-4075-bce5-710f3cfea052`): `docs/session-debug-7ac52bf2-71ee-4075-bce5-710f3cfea052.json`
- Backend log excerpt (`backend_uvicorn.log`):
  ```text
  [TOOL_RECEIPTS] ensured baseline receipts session=7ac52bf2-… intent=True plan=True before=[] after=['intent_detection','plan_generation']
  [TOOL_RECEIPTS] persisted session=7ac52bf2-… keys=['intent_detection','plan_generation','sql_chain']
  [REVISION_SNAPSHOT] stored session=7ac52bf2-… intent_signature=True plan_keys=['comparison','derived_metrics','filters','granularity','group_by','limit','metrics','statistic','timeframe']
  [DEBUG_SESSION] cache_keys session=06ba1ae2-… tool_cache=['analytics','web_search'] analytics=['artifact_version','artifacts','artifacts_history'] receipts=None
  ```
  These lines confirm that receipts and revision snapshots exist on the in-process snapshot, yet they disappear by the time the debug endpoint reloads the session.

## Outstanding Gaps
1. **Missing persisted payloads** – the repository load used by the debug endpoint returns only `tool_cache.analytics.artifacts*`; `tool_cache.tool_receipts` and `tool_cache.analytics.revision_snapshot` are absent even after successful persistence logs.
2. **Rehydrate telemetry** – `[REHYDRATE]` success/no-replay logs still never emit, so we cannot confirm whether the helper short-circuits or succeeds.
3. **Frontend visibility** – the UI still receives a generic `rehydrate_revision_plan` error when the helper fails, and does not yet expose the richer diagnostics.

## Next Steps
1. **Trace snapshot serialization**
   - Inspect `SessionStateRepository.save/load` to ensure `snapshot.snapshot()` includes `tool_receipts` and `revision_snapshot`; add unit coverage that serializes+deserializes and checks these keys.
   - Capture the serialized JSON emitted by `_fallback_set` (in-memory store) and verify that `tool_receipts` survives round-trips.
2. **Surface rehydrate outcomes**
   - Double-check logger configuration; if the helper never runs, instrument `single_agent_tools` to log the boolean returned from `rehydrate_revision_plan`.
   - If the helper is returning before the logging block, tighten `_log_state` instrumentation to emit on every exit path.
3. **Expose receipts/snapshot via API**
   - Update `/api/debug/session/{id}` to include `tool_receipts` so downstream scripts no longer depend on internal state.
   - Once snapshots reliably load, extend the doc with before/after diffs and add regression coverage to guard the fallback path.
4. **Frontend follow-up**
   - After backend fixes land, wire the frontend to display actionable messages instead of the helper name when rehydrate fails.
