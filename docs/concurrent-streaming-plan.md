# Concurrent Streaming Investigation

Progress update: October 21, 2025

### Latest progress
- Repaired the revision-request emission so the fan-out lane classifier can stream `revision_request` packets without syntax errors and preserved the persisted `follow_up_route`.
- Hardened `ToolParallelRuntime` teardown by tolerating `None` runner/dispatcher tasks; future modularization can reuse the data class in slimmer helpers.
- Verified the async tool fan-out still streams ordered results (`test_tool_parallelism_streams_results_immediately`) and the staged concurrency regression (`test_concurrent_lanes_emit_before_sql`) via single-test pytest runs (see Testing and validation checklist).
- Added `_stream_with_tool_state` coverage (`test_stream_with_tool_state_emits_queue_events_during_sql`) to prove accessory deltas surface while the SQL generator is mid-flight; verified with `python -m pytest backend/tests/analytics/test_planner_executor_sql.py -k stream_with_tool_state_emits_queue_events_during_sql`.
- Normalised revision-ready events in `planner_executor.py` (new `_REVISION_EVENT_ALIASES`) so stock/web/sql/chart/analysis deltas inherit `*_revision_ready` names, emit without SQL reruns, and propagate revision metadata downstream.
- Implemented stock-only revision streaming (honours `revision_targets={"stock"}`) by draining queued accessory results immediately and avoiding redundant SQL/analysis work; added regression coverage `test_stock_revision_targets_emit_without_sql` and `test_sql_revision_ready_events_are_renamed`.
- Frontend stream hook now hydrates cards on accessory deltas regardless of SQL status, dedupes identical payloads via `payloadHash`, preserves lane priority ordering, and surfaces revision badges + revision mode updates (`useAnalyticsMemoryStream.ts` + expanded tests).
- Memory UI teaches the revision banner about the new `market` fast-path and exposes specialist-card order/metadata for debugging; Vitest suite extended with revision-focused assertions (`useAnalyticsMemoryStream` revisions block).
- Added a specialist card ordering regression so accessory deltas landing ahead of SQL still render in the mandated priority stack; verified via `npx vitest run components/analytics/hooks/useAnalyticsMemoryStream.test.tsx -t "card ordering"`.
- Added multi-agent supervisor reuse regression so planner fan-out caches prevent duplicate SQL, stock, or web re-execution (`test_multi_agent_supervisor_reuses_planner_fanout`).

## Ledger Timeline Snapshot

Evidence from `docs/agent-process-ledger (98).json` shows the three accessory adapters finish well before SQL, yet their cards render only after the SQL lane is complete.

| Sequence | Event Source | Ledger Timestamp (UTC) | Tool Completion (`completed_at`) | Notes |
|----------|--------------|------------------------|----------------------------------|-------|
| 32 | `tool_fanout` | 20:45:10.354 | N/A | Fan-out launches; queue primed. |
| n/a | `market_question_a` | N/A | 20:45:04.244 | Adapter finishes ~15 s before SQL ready. |
| n/a | `market_question_b` | N/A | 20:45:04.246 | Same as above. |
| n/a | `stock_tracker` | N/A | 20:45:04.243 | Same as above. |
| n/a | `web_retriever` | N/A | 20:45:10.352 | Web lane returns ~9 s before SQL ready. |
| 42 | `tool_execution` (`sql_executor` end) | 20:45:19.183 | 20:45:19.183 | SQL chain finishes. |
| 44 | `sql_lane` / `sql_ready` | 20:45:19.187 | N/A | First rendered event after SQL completes. |
| 45 | `market_lane` | 20:45:19.187 | N/A | Market card recorded only after SQL lane. |
| 46 | `web_lane` | 20:45:19.188 | N/A | Web card recorded only after SQL lane. |

Additional observations:
- Ledger search returns **no standalone `tool_parallel_result`, `stock_ready`, or `web_ready` entries**, so the accessory deltas never reach the consumer telemetry even though the adapters completed.
- The queue payloads confirm each adapter set `payload.ready = true` with fresh data; the issue lies in when those deltas are drained and emitted, not in tool execution itself.

## Backend Flow Diagnosis

Code review focused on `backend/analytics/flows/planner_executor.py` and `tooling.py`:

- `PlannerPipeline.events` starts tool fan-out via `_start_tool_parallelism` (lines `3528-3537`), which enqueues each `tool_parallel_result` plus derived deltas (`stock_ready`, `web_ready`) into an async queue.
- The queue flushes only at explicit checkpoints. Inside the SQL phase the code awaits `_stream_with_tool_state(registry.invoke("sql_generation", ...), tool_state)` (lines `3561-3565`), but the generator emits a dense sequence of SQL progress events. Because `_collect_tool_deltas_now(tool_state)` runs only before SQL begins and after it ends (lines `3538-3539`, `3558-3559`, and `3613-3614`), any accessory events that arrive mid-SQL remain buffered until the SQL coroutine yields.
- `_derive_accessory_events` (lines `2100-2155`) fires as soon as the queue receives a `tool_parallel_result`, so the deltas exist, but they are tagged with `delta=True` and never leave the queue while SQL is active.
- `_ensure_analysis_dependencies` (lines `3078-3122`) is invoked only **after** the SQL ready event (line `3641`), reinforcing the gating: even remediation fan-out runs after SQL, so late consumers still wait on the SQL lane.
- Net effect: accessory results are computed early, yet the orchestrator delivers them only once the sequential SQL stage unwinds, so the UI hydrates all cards at once.

## Change Scope to Enable True Concurrent Lanes

Delivering "market research (dual questions) + stock chart generation + SQL lane" concurrently, with immediate UI updates, requires coordinated backend and frontend work:

### Backend orchestration
- Add a dedicated queue drainer: keep `_start_tool_parallelism` but spin a lightweight async task that consumes `tool_state["queue"]` and pushes deltas to the emitter immediately instead of relying on `_collect_tool_deltas_now` inside the SQL loop.
- Split SQL progress from fan-out streaming: wrap the SQL coroutine so progress events do not monopolise `_stream_with_tool_state`. One option is to stream SQL in its own task while a dispatcher awaited by `PlannerPipeline.events` multiplexes accessory deltas in real time.
- Guard against duplicate execution: write final results into `ctx.tool_parallel_results` once and ensure `_ensure_analysis_dependencies` skips adapters when the queue already emitted success payloads.
- Propagate cached state upstream: emit merged payload snapshots (SQL artifact summary + market widget + web context) so supervisors and multi-agent flows can reuse instead of reissuing SQL/stock/web calls.

#### Planner modularisation roadmap
1. **Stabilise behaviour with tests.** Finish the pending backend coverage (`test_planner_executor_sql.py` streaming assertions, revision rerun cases) and Vitest card-order snapshots so we can refactor aggressively without losing the concurrency guarantees.
2. **Introduce a planner package.** Create `backend/analytics/flows/planner/` (folder lives alongside the existing flows) and move the lightweight structures first:  
   - `context.py` -> `PlannerPhaseContext`, `ToolParallelRuntime`, receipts/helpers.  
   - `events.py` -> `_cached_event`, `_compose_*`, `_mark_delta_event`, revision tagging.  
   This trims imports in the main module without touching control flow.
3. **Extract lane executors iteratively.**  
   - Step 3A: carve out `_start_tool_parallelism`, `_stream_with_tool_state`, queue draining, and accessory derivation into `fanout.py`. Export a small API (`start_tool_parallelism`, `drain_tool_queue`, `ToolDelta` type) so `single_agent_tools.py` and `multi_agent.py` can share the same logic.  
   - Step 3B: move SQL pipeline plus chart/analysis helpers into `sql_lane.py` and `analysis_lane.py`, returning async generators that the orchestrator calls. Keep signatures identical to avoid churn in tests.  
   - Step 3C: isolate revision orchestration (`set_revision_targets`, `_annotate_revision`, cached reuse) into `revision.py`, feeding both planner and supervisor flows.
4. **Thin the orchestrator.** Rewrite `PlannerExecutorFlow.events` to read as a high-level pipeline that imports functions from the new modules (classification -> plan -> fan-out -> sql lane -> accessories -> analysis). Ensure telemetry wiring stays in this module so log schemas remain stable.
5. **Update dependents & cleanup.** Adjust `single_agent_tools.py`, `multi_agent.py`, and `workflow.py` to import from the new package, remove duplicated helpers (`_build_tool_metadata`, cached events), and re-run the full backend + frontend suite. Once green, document the new layout in `ARCHITECTURE.md` and mark the modularisation TODOs complete below.

### Frontend streaming
- ✅ Update `components/analytics/hooks/useAnalyticsMemoryStream.ts` to hydrate cards on `stock_ready` / `web_ready` delta packets, not `sql_ready`, and continue streaming while SQL runs.
- ✅ Apply the required priority ordering after every delta: `SQL Chart` -> `Financial Analysis (3 data sources)` -> `Stock Chart` -> collapsed `Market Research` -> collapsed `Generated SQL Query`.
- ✅ Treat duplicate deltas as no-ops when the payload hash matches the current card to avoid flicker once the SQL lane reconciles state; revision badges now leverage `revisionId` metadata and set the page-level `revisionMode` (`chart` / `analysis` / `market` / `mixed`).

### Testing and validation
- Completed Oct 21: Added `test_stream_with_tool_state_emits_queue_events_during_sql` to `backend/tests/analytics/test_planner_executor_sql.py`, locking in queue draining while SQL events stream (`python -m pytest backend/tests/analytics/test_planner_executor_sql.py -k stream_with_tool_state_emits_queue_events_during_sql`).
- Completed Oct 21: Added `test_stock_revision_targets_emit_without_sql` and `test_sql_revision_ready_events_are_renamed` covering stock-only revisions and aliasing (`python -m pytest backend/tests/analytics/test_planner_executor_sql.py -k revision`).
- Completed Oct 21: Extended Vitest coverage for specialist-card ordering/deduplication under revisions (`npx vitest run components/analytics/hooks/useAnalyticsMemoryStream.test.tsx -t revisions`).
- Completed Oct 21: Added a specialist-card priority regression ensuring accessory-first deltas reorder into the mandated stack (`npx vitest run components/analytics/hooks/useAnalyticsMemoryStream.test.tsx -t "card ordering"`).
- Completed Oct 21: Added multi-agent supervisor reuse regression to confirm planner fan-out caches are reused (`python -m pytest backend/tests/analytics/test_multi_agent_flow.py -k "supervisor_reuses_planner_fanout"`).

### Follow-up Revision Flow (Round 2+ Requests)

Once the first full pipeline has streamed, the supervisor should treat later user prompts as targeted revision requests instead of replaying every lane. The goal is to let the agent single out the market research card, the stock chart, or the SQL chart (change to bar chart or run full chain intent -> planning -> generation -> visualization) and refresh only what changed while keeping results streaming immediately.

#### Agent decision tree
1. Classify the follow-up prompt into one (or more) revision intents. Examples:
   - `market_focus`: "Zoom in on competitor chatter for Q4" -> rerun both market questions with updated framing.
   - `stock_refresh`: "Update the Apple stock chart with today's close" -> rerun the stock adapter with the latest window.
   - `sql_revision`: "Can you graph revenue vs. churn instead?" -> replans SQL, regenerates the query, and streams a new chart. " OR can you change the chart to a bar chart?" -> just chart type change with previous state.
2. Build a lane run list that includes only the affected adapters. When multiple intents appear ("Refresh the stock chart and tighten the SQL filters"), dispatch the selected lanes concurrently so they can stream independently.
3. Carry forward cached results for untouched lanes and annotate the emitted deltas with a `revision_id` so downstream agents and the UI can distinguish the new payload from the initial run.

#### Backend orchestration adjustments
- Introduce a lightweight `revision_request` event that enqueues immediately when the intent classifier fires. This keeps the async queue drainer pushing revision deltas even while another lane (for example a long SQL regeneration) is active.
- Allow each lane runner to accept optional context (prior SQL plan AST, previous stock ticker/timeframe, prior market question prompt) so it can compute a diff or reuse cached artifacts instead of starting cold.
- Emit `*_revision_ready` events as soon as the lane finishes, reusing the same payload schema as the first run but tagging `context.revision = true`. This lets the frontend preserve ordering (`SQL Chart` -> `Financial Analysis` -> `Stock Chart` -> collapsed `Market Research` -> collapsed `Generated SQL Query`) while still surfacing the fresh card instantly.
- Record revision completions in shared tool state so supervisors avoid kicking off duplicate refreshes if another agent already serviced the request.

#### Frontend updates
- `useAnalyticsMemoryStream` should hydrate the affected card as soon as a `*_revision_ready` delta arrives, updating the card body while leaving the existing order intact. Cards that are not part of the revision should stay pinned with their prior payloads.
- Display a subtle "Updated" badge keyed by `revision_id` so users understand which card just refreshed, and collapse market/SQL cards automatically if the revision intent did not target them.
- When multiple revision deltas land close together, apply the same ordering rule after each insertion to avoid jitter (e.g., a new SQL chart should still float to the top, even if the stock chart revision landed a moment earlier).

#### Example timeline (follow-up round)
| Sequence | Event | Timestamp (UTC) | Notes |
|----------|-------|-----------------|-------|
| 58 | `revision_request(stock_refresh)` | 20:52:11.002 | User asks for the latest price action; agent flags the stock lane only. |
| 59 | `stock_revision_inflight` | 20:52:11.010 | Stock adapter starts; market + SQL lanes remain idle. |
| 60 | `stock_revision_ready` | 20:52:11.642 | New chart payload streams; frontend swaps the card without waiting for SQL. |
| 61 | `revision_request(sql_revision)` | 20:52:12.004 | User immediately follows up: "also add churn to the SQL chart". |
| 62 | `sql_revision_ready` | 20:52:17.931 | Revised SQL plan + chart stream in; priority ordering keeps this card on top, stock revision remains second, market card stays collapsed. |
