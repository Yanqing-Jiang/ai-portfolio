# Revision Fast-Path Plan

## Goals
- Ensure the first query in a session executes the full analytics pipeline so downstream artifacts (SQL, chart spec, analysis, web context, stock data, guardrails) are persisted.
- Route every subsequent request in the same session through a revision-only path that reuses cached artifacts and emits only the targeted cards.
- Suppress SQL/intent/planning events during revisions while preserving telemetry, guardrails, and follow-up routing signals expected by the frontend.
- Present revision responses that include only the updated components (chart, analysis + web, market) to avoid UI flicker and keep context clear.

## Consolidated Takeaways from Existing Plans
### Keep from both documents
- Treat chart, analysis, and market revisions as distinct lanes that can be combined when a follow-up asks for multiple updates.
- Persist and hydrate revision directives so flows know which artifacts to reuse and which helpers to invoke.
- Update the frontend stream hook to stop wiping unrelated cards during revisions and to align banners/prompt suggestions with the targeted lane.

### Avoid / Mitigate
- Do not introduce parallel "initial_build_complete" flags; rely on existing snapshot artifacts (`last_sql`, `last_chart_spec`, `last_analysis`, cached tool payloads) to detect baseline completion.
- Do not bypass instrumentation blindly. When skipping `flow_instance.events`, inject lightweight telemetry so guardrails, latency stats, and follow-up banners remain accurate.
- Prevent double-emitting `revision_request` events or losing classifier fallbacks by centralizing decision logic inside `analytics_memory_workflow`.

## Backend Plan
1. **Baseline Detection & Routing**
   - Infer `baseline_ready = bool(snapshot.last_chart_spec and snapshot.last_analysis)` from the loaded `SessionStateSnapshot` so both visual and narrative artifacts are required before enabling revision fast-paths.
   - Execute the full pipeline only when `baseline_ready` is false or when the classifier routes to `FollowUpRoute.FULL_PIPELINE` (e.g., the first user question or an explicit fresh intent). Persist the snapshot at completion as today.
   - For follow-ups where `baseline_ready` is true and `FollowUpClassifier.detect_revision_targets` returns any lane, branch into the revision dispatcher.

2. **Revision Dispatcher (`analytics_memory_workflow`)**
   - Emit the existing status and `revision_request` events before branching so telemetry stays consistent.
   - Build/record a `RevisionDirective` with explicit targets, requested focus, and generated search topics; persist it alongside the appended user message so future revisions inherit context.
   - Derive `follow_up_route` values (`reuse_sql`, `analysis_only`, `market_only`, `mixed_revision`) and emit them immediately so the UI can adjust copy.
   - Invoke targeted helpers in sequence based on requested lanes:
     - `apply_chart_revision` (chart lane)
     - `run_analysis_refresh` (analysis + web lane)
     - `refresh_market_lane` / `run_market_refresh` (market lane)
   - Wrap each helper with the revision instrumentation utility that timestamps start/end, stamps `reason`/`source`, and produces status events (for example `EventEmitter.status("analysis_revision", ...)`).
   - When combining multiple lanes, sequence chart updates before analysis/web refreshes so downstream components receive events in a consistent order.
   - If the snapshot lacks the artifacts needed for the requested lane, emit a banner guiding the user to start a new session instead of silently replaying the full pipeline.

3. **Single-Agent Helper Enhancements**
   - Expose `run_web_refresh`, `run_market_refresh`, and `run_analysis_refresh` on `SingleAgentController`, each delegating to the planner tool registry and the new pipeline helpers.
   - Seed revision search topics from the directive and refresh helpers before dispatching tool parallelism, ensuring live web snippets are fetched on narrative revisions.
   - Reset accessory state (`web_search`, cached tool receipts/results, guardrail seeds) before invoking revision-only adapters, then persist refreshed artifacts back into the snapshot.

4. **Multi-Agent Helper Enhancements**
   - Mirror the single-agent helpers using the orchestrator: short-circuit planner scheduling on revision-only runs, forward events through `_forward_with_hooks`, and reuse the planner tool registry for web/market refreshes.
   - Respect `RevisionDirective.agentic` so future agentic revisions can opt into richer behavior without planner replay while still benefiting from cached context.

5. **Telemetry & Guardrails**
   - Extend `instrumentation.instrument_events` with `emit_revision_lane(flow, lane, coro)` (and recognize `web_refresh` / `market_refresh`) so latency and core telemetry continue to publish even without planner replay.
   - Scope guardrail evaluators per lane by clearing accessory state and rebuilding tool receipts before emitting revision results.

## Status Update (October 30, 2025)
- **Snapshot hydration restored.** `_build_revision_snapshot_payload()` now captures intent, plan, slot statuses, follow-ups, assumptions, and contextual messages; `_hydrate_context_from_snapshot()` reconstructs those models before planner execution, eliminating redundant classification passes.
- **Search topics auto-seeded.** `analytics_memory_workflow` synthesizes revision topics using follow-up text (and cached directives when necessary) and stores them on `RevisionDirective.search_topics`, so both single- and multi-agent refresh helpers request fresh web context.
- **Dedicated refresh helpers.** Planner pipelines expose `refresh_web_lane` and `refresh_market_lane`, and both controllers call them via the tool registry. Accessory state resets ahead of each run, preventing stale cache reuse and guardrail misfires.
- **Revision telemetry aligned.** Instrumentation recognizes the new `web_refresh` / `market_refresh` steps, ensuring latency and lane status events remain in the stream without replaying the full pipeline.
- **Follow-up prompts persisted.** Each revision appends the user message to `SessionStateSnapshot.messages`, keeping downstream directives aware of the conversation history.
- **Regression coverage added.** `backend/tests/analytics/test_revision_routing.py` seeds realistic snapshots and asserts routing, search topic generation, and snapshot persistence for analysis and market fast-paths.

### October 30, 2025 Hotfix Recap
- **Finalization gate now respects applied patches.** Planner flow skips the non-financial decline path when a revision is in-flight, allowing successful chart updates to surface instead of fallback refusals.
- **Clarification suppressed for revisions.** Revision follow-ups bypass the clarification loop, trimming extra chatter while keeping plan generation in place.
- **Chart patch telemetry richer.** `_build_patch_event` records `chart_type`, `stack`, and `stack_mode` so supervisors and UI hooks can confirm the applied spec.
- **Market agent budget relaxed.** Multi-agent `market` specialist latency budget increased to 1500 ms to prevent premature guardrail aborts during mixed revisions.
- **Web research budget tuned.** Multi-agent `web_research` specialist now has 2000 ms to finish targeted lookups, eliminating premature timeouts during analysis revisions.
- **Analysis refresh wired through workflow.** `analytics_memory_workflow` now calls `run_analysis_refresh` (or falls back with `refresh_web=True`) and passes the requested focus so revisions trigger fresh web context before recombining cached SQL/analysis.
- **Revision flag plumbed through context.** `PlannerExecutorFlow` sets `ctx.is_revision_follow_up` so classification decline checks and downstream helpers use the flag without runtime errors.
- **Banner copy sanitized.** Reuse SQL banner now renders ASCII hyphenation (`"Skipping the SQL rerun - updating visuals..."`) to avoid mojibake in follow-up guidance.
- **Test attempt noted.** `py -m pytest backend/tests/analytics/test_chart_revision.py backend/tests/analytics/test_planner_executor_sql.py` (PowerShell) failed early because `pytest` is not installed in the environment; rerun once dependencies are available.

## Validation Plan
- **Unit tests:** ? `python -m pytest backend/tests/analytics/test_revision_routing.py -q` verifies revision routing, topic seeding, snapshot persistence, and market lane refreshes.
- **Integration smoke:** ? Still recommended: manual run of baseline ? chart tweak ? analysis follow-up in the playground using both single- and multi-agent flows to observe SSE sequencing.
- **Snapshot sanity:** ? Covered by unit tests that inspect `SessionStateSnapshot.tool_cache` and appended message history.
- **Guardrail checks:** ?? Pending deeper soak once Polygon/web latency telemetry is aggregated post-deploy.
- **Frontend hook test:** ?? Coordinate with FE owners to expand Vitest coverage for `useAnalyticsMemoryStream` using the lean revision event stream.

## Remediation Steps
1. **Persist full planner state.** ? Implemented in `_build_revision_snapshot_payload` / `_hydrate_context_from_snapshot`.
2. **Seed follow-up topics.** ? `analytics_memory_workflow` now generates and persists revision search topics.
3. **Add true refresh helpers.** ? Planner pipeline exposes `refresh_web_lane` / `refresh_market_lane`; controllers call them via the tool registry.
4. **Reset accessory state.** ? `_reset_revision_accessories` clears cached tool receipts/results before revision helpers execute.
5. **Record follow-up prompts.** ? `_append_session_message` invoked for each revision; messages stored in the snapshot.
6. **Update tests.** ? Revision routing tests expanded to cover analysis and market fast-path scenarios.
