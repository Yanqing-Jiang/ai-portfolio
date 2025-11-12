# Agent Process Ledger Investigation (November 11, 2025)

## Completed Work
- Re-ran backend log review for session `35b4199a-b135-40ba-a4e8-5271f3722d50` to map each telemetry event to the failed revision request captured in `docs/agent-process-ledger (29).json`.
- Inspected ledger snapshots `(28)` through `(29)` plus `agentic-roadmap.md` current-status claims to reconcile observed behavior with documented expectations.
- Reconstructed the exact timeline of the baseline analysis run (15:59:32-15:59:46) and the follow-up revision request (15:59:55) using `backend/backend_uvicorn.log`.
- Traced the structured intent resolver failure back to `_normalize_schema_for_responses` in `backend/unified_responses_client.py`, confirming the Responses API 400 (`text.format.schema`) matches the mis-generated `required` list.
- Captured the lane-level snapshot invariant instrumentation spec (Plan item #2) so every SQL/dataset/market/web adapter persists its receipts immediately, emits health alerts on gaps, and feeds `analysis_inputs_manifest` deterministically.
- Defined the re-derive revision workflow (Plan item #3) that reloads stored SQL + market receipts, optionally merges fresh web snippets, and drives `analysis_writer` without relying on `last_analysis` text.
- Implemented the guardrails and instrumentation: schema normalization now respects optional dictionary fields while still emitting `intent_resolution_schema_error`, and `SessionStateSnapshot` persists lane receipts/metrics so `analysis_inputs_manifest` seals deterministically (tests updated in `backend/tests/analytics/test_unified_responses_client.py` and `backend/tests/analytics/test_session_state_receipts.py`).
- Delivered the dashboard validation + Ops tooling: telemetry is now covered by fast-path smoke tests on both `single-agent` and `planner-executor` flows, and `scripts/backfill_manifest_receipts.py` lets Ops hydrate historical sessions before enabling the new manifest contract.
- Audited the planner/executor `_web_search_phase` path for `docs/agent-process-ledger - 2025-11-11T234306.925.json` and confirmed `_persist_session_state` records SQL receipts but never serializes `web_search` payloads, leaving the manifest unsealed even though SQL artifacts exist.
- Implemented the planner/executor receipt fix: `_persist_session_state` now accepts `record_web=True`, `_web_search_phase` persists its `web_search` payload immediately, and `refresh_web_lane` re-seals receipts after every revision refresh (backend/analytics/flows/planner_executor.py:3067-5170).

## Nov 12 Findings
- Planner/executor revisions still emit only the `follow_up_route/cannot_revise` card stack recorded in `docs/agent-process-ledger - 2025-11-11T234306.925.json`, so the frontend shows a streaming baseline stack plus a stalled revision stack with conflicting statuses.
- Web-lane receipts are not persisted for planner/executor flows: `_web_search_phase` streams results and touches `ctx.artifacts.web`, yet `_persist_session_state` lacks any `record_web` branch, so `analysis_inputs_manifest` keeps marking the `web` component missing.
- Because the manifest never seals, `RevisionContext.load` skips the re-derive path and the UI banner downgrades to "Start a new question...", contradicting the lane-specific diagnostics promised in the earlier fix plan.
- The frontend aggregator does not coalesce cards by `(session_id, revision_id)`, so failed revisions create duplicate card stacks instead of flipping the existing one into an error state.

## Immediate Receipt-Sealing Design
- Extend `_persist_session_state` (backend/analytics/flows/planner_executor.py) with a `record_web` flag that serializes `ctx.artifacts.web` (or seeded `ctx.web_search`) via `WebContextArtifact.to_dict()`, calls `snapshot.record_tool_result("web_search", payload)`, touches the `web` lane, and triggers `refresh_analysis_inputs_manifest(persist=False)` before saving.
- Invoke `await self._persist_session_state(ctx, record_web=True, record_artifacts=False)` immediately after `_set_web_artifact` succeeds inside `_web_search_phase`, so the receipt seals before analysis streaming begins.
- When a revision reuses cached web context, rerun the same helper with the cached payload if the stored digest differs, guaranteeing that revisions relying on existing web receipts have sealed manifests.
- Keep SQL behavior unchanged: `record_sql=True` already seals receipts right after SQL generation, so revisions can continue to rehydrate SQL directly from `snapshot.last_sql`.
- With SQL and web receipts sealed independently, downstream specialists only need the persisted snapshot plus any opt-in `web_refresh` topics to re-derive the analysis text.

## Snapshot Invariant Instrumentation (Plan Item #2 Execution)
- Each lane adapter (`sql_lane`, dataset previewer, market fetcher, web fetcher) now calls `persist_lane_receipt(lane, receipt_id, meta)` the moment it exits, sealing the artifact before any downstream analysis starts.
- The manifest builder blocks publication until it observes the quartet of receipts and logs both `analysis_inputs_manifest.sealed=true` and `analysis_inputs_manifest_version` for replay.
- Health metrics fire automatically: `analysis_lane_missing_artifact` when an adapter finishes without persisting, `analysis_inputs_missing` when the manifest assembler notices a gap, and `analysis_inputs_manifest_sealed` on success for observability parity.
- Receipts store normalized pointers `{ sql_receipt_id, dataset_sample_id, market_snapshot_id, web_digest_ids[], captured_at, capture_version }`, letting later workflows rehydrate inputs without scraping narrative text.
- `RevisionContext.load` now checks that `analysis_inputs_manifest.status == "sealed"` and surfaces a lane-specific diagnostic (e.g., "web lane missing receipts") instead of the generic "Start a new question" banner whenever a prerequisite artifact is absent.

## Re-derive Revision Flow (Plan Item #3 Execution)
- Added `hydrate_inputs_manifest(session_id)` to reconstruct SQL text, dataset previews, and market snapshots directly from the stored receipts, guaranteeing revision requests never depend on `last_analysis`.
- `analytics_memory_workflow` now treats any revision with a sealed manifest as immediately actionable: it skips `_build_cannot_revise_banner`, enqueues a mini-run, and records `analysis_rerun_started`/`analysis_rerun_completed` telemetry for Ops.
- `analysis_writer` accepts a `derive_from_inputs(manifest, optional_web_docs)` payload so the regenerated narrative is computed fresh while still honoring the cached SQL + market state.
- Follow-up requests can toggle `web_refresh=true`; when set, the pipeline merges the new web snippets into `web_digest_ids` vNext while reusing the other receipts, satisfying the "reuse most, refresh some" guidance from the doc.
- Revision receipts are persisted as soon as the adapter finishes, so every mini-run emits the same health metrics as the baseline lanes and the manifest always reflects the latest sealed set.

## Root Cause Summary
1. **Race between revision request and baseline persistence** - `analytics_memory_workflow` classified the follow-up as a revision while the baseline run was still streaming analysis. Because `RevisionContext.load` could not find finalized analysis/web artifacts yet, `_build_cannot_revise_banner` emitted the "Start a new question" guidance even though the data was merely in-flight.
2. **Structured resolver schema bug** - `_normalize_schema_for_responses` forces every property into `required`, including dictionary-only fields like `slots`. The Responses API rejects that schema (`invalid_json_schema`), so the resolver falls back to heuristics that do not record the receipts the revision classifier expects, reinforcing the perception that web/analysis caches are missing.
3. **Docs drift** - `docs/agentic-roadmap.md` listed the classification/clarification fixes as "current status," but the live telemetry (Nov 11) shows those changes have not landed, so operators were relying on stale documentation when triaging the ledger regression.

## Fix Plan
1. **Schema Normalization Guardrails (Status: shipped)**
   - Update `_normalize_schema_for_responses` to consult `_should_require_property` before editing the `required` list and to respect any predefined `json_schema_extra` requirements.
   - Add pytest coverage that wraps `LLMIntentResolutionModel` and asserts dictionary-only properties stay optional, plus a mocked `create_structured` flow to ensure no Responses 400 occurs.
2. **Snapshot Invariants for Non-Analysis Data (Status: single-agent complete, planner/executor pending)**
   - Single-agent adapters already persist receipts synchronously via `persist_lane_receipt(...)`; planner/executor must adopt the Immediate Receipt-Sealing Design above so the manifest seals once SQL + web receipts exist.
   - Maintain the manifest builder guardrails so `analysis_inputs_manifest` records deterministic receipt IDs and raises `analysis_lane_missing_artifact` when planner/executor skips web persistence.
3. **Revision Flow Built on Re-deriving Analysis (Status: blocked on planner/executor receipts)**
   - The codepath exists (`hydrate_inputs_manifest` + `analysis_writer.derive_from_inputs`) but cannot run until web receipts seal; unlocking Plan Item #2 immediately enables this flow for planner/executor revisions.
   - Mini-run telemetry should remain unchanged once receipts arrive, preserving `analysis_rerun_started`/`completed` events.
4. **Receipts + Telemetry Reliability (Status: ongoing)**
- Emit an `intent_resolution_schema_error` metric whenever the Responses API rejects our schema so Ops can respond before users encounter the banner, and log a complementary `analysis_inputs_missing` marker if required inputs are absent.
   - Update `docs/agentic-roadmap.md` remediation sections to reflect the new "re-derive analysis" strategy so future investigations know analysis text is expected to be transient.
5. **Planner/Executor Receipt Sealing Implementation (Status: shipped Nov 12, 2025)**
   - `_persist_session_state(..., record_web=True)` now records `web_search` receipts immediately, `_web_search_phase` sets the flag after every successful search, and `refresh_web_lane` reuses the same helper so revisions persist their refreshed context.
   - Follow-up: add pytest coverage in `backend/tests/analytics/test_session_state_receipts.py` to assert planner/executor flows persist both SQL and web receipts and that `analysis_inputs_manifest.sealed` flips to `true` without requiring `last_analysis`.
6. **Revision Gating & UI Consistency**
   - Gate revision requests on `analysis_inputs_manifest.status` and emit a dedicated `baseline_still_streaming` SSE event instead of `cannot_revise`, preventing duplicate card stacks when the manifest is merely in-flight.
   - Update the frontend aggregator to coalesce card stacks while updating the existing stack's status badge rather than creating a duplicate column.

## Remaining Work
- Seal planner/executor web receipts, gate revisions on manifest readiness, and align the UI card coalescing logic so ledger snapshots stop emitting duplicate stacks.

## Open Questions
- Should follow-up requests be queued server-side until `lane_ready` arrives, or should the client know to retry automatically when it receives the "baseline still finishing" banner?
