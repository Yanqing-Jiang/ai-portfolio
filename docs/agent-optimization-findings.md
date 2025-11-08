# Agent Optimization Findings — 2025‑11‑07

Looking at `docs/agent-process-ledger - 2025-11-06T223142.136.json` reveals a few systemic inefficiencies that drive duped status bubbles, wasted tool calls, and hung UI states. Below are the primary offenders, their root causes, and proposed fixes.

---

## 1. Multi-Phase Tools Emit Duplicated Telemetry

**Evidence**

- The ledger logs *three* `chart_designer` completions for a single run without matching `start` events (`lines 4095-4112`), and similarly logs double `sql_generator completed` entries (`lines 4073-4104`). The UI therefore shows “Planning chart…” multiple times and repeats SQL progress bubbles.

**Root Cause**

- `_SingleAgentToolHooks` only deduplicates the intent classifier. Other aliases (SQL generator, chart designer, analysis writer) still map multiple `TOOL_END_EVENTS` (e.g., `chart_generated`, `chart_patch`) to the same alias, so every event drains the timer queue and emits another `tool_end`. The frontend faithfully renders each one, which looks like rework.

**Fix Plan**

1. Extend `MULTI_PHASE_TOOL_CONFIG` to include `sql_generator`, `chart_designer`, and `analysis_writer`, specifying their terminal events (`sql_validated`, `chart_generated`, `analysis_complete`).
2. Reuse `_build_tool_call_event` to aggregate metadata (SQL summary, chart spec, analysis length) across the intermediate events before emitting a single completion payload.
3. Add regression tests (mirroring `test_tool_telemetry_dedup`) that simulate `sql_generated` + `sql_validated` and assert only one telemetry `tool_end` is emitted per alias.  

*Outcome:* telemetry/UI show one cohesive completion per tool, eliminating the repeated “Planning chart…” phases and giving us cleaner SLA metrics.

---

## 2. Status Bubbles Re-Emit Identical “Thinking” Logs

**Evidence**

- Steps like “Query Classification” and “Requirements Clarification” list the same sentences 5–7 times in the ledger (`lines 6-23` and `lines 30-41`). Users see scrolling bubbles repeating “Starting query classification…” even though nothing new happened.

**Root Cause**

- Every SSE chunk replays the entire `thinking` array, and the frontend blindly appends each copy. There is no deduplication key (sequence ID or checksum) on the backend, nor does the UI check whether it already surfaced the identical log line for the same step.

**Fix Plan**

1. Include a monotonically increasing `thought_id` (e.g., `f"{step}:{sequence}"`) inside each `progress` payload so the UI can ignore repeats.
2. Alternatively (preferred for bandwidth), have `_SingleAgentToolHooks` only emit *diffs* by keeping a per-step hash of the last `thinking` array and sending new entries only.
3. Update `useAnalyticsMemoryStream` to keep a `Set<string>` per step so it doesn’t re-render duplicate logs if older servers are still replaying the full array.

*Outcome:* the “Planning chart” bubble only updates when new information appears, cutting visual noise and reducing DOM churn during longer runs.

---

## 3. Missing Cancellation Events Leave Lanes “In Progress” Forever

**Evidence**

- The ledger ends with `sql_generator`, `chart_designer`, `analysis_writer`, and `planner` stuck in `status: "in_progress"` with `elapsed_ms: 0`, and there is no `workflow_complete` entry anywhere in the file tail (`lines 4830-4877`). That’s why the Output CTA kept animating (three dots) and process steps 21‑24 never settled.

**Root Cause**

- When a client disconnects or the backend restarts mid-run, `_forward_with_hooks` never emits a terminal event; the stream simply ends, so the UI never learns that lanes should be marked as “skipped/cancelled.”

**Fix Plan**

1. Hook the `finally` block in `SingleAgentController._forward_with_hooks` to emit a synthetic `workflow_complete` with `status: "cancelled"` (and mark each pending lane as `LANE_STATUS_SKIPPED`).
2. Teach the frontend hook to treat `cancelled` as a terminal state: stop the spinner, flag steps as `skipped`, and expose a “Run again” CTA.
3. Add an integration test that aborts a stream mid-SQL and asserts both sides emit/consume the cancellation event so process bubbles never stall indefinitely.

*Outcome:* even if a user closes the tab or the backend restarts, the UI settles gracefully (no infinite “in progress”), and telemetry accurately records cancelled runs.

---

## 4. Accessory Lanes Never Ran in Parallel

**Evidence**

- `pending_lanes` remains `["sql","web","market","analysis"]` deep into the run (`lines 56-65`), and there are zero `web_ready` / `stock_ready` events in the entire ledger. That means the accessory fan-out never kicked off, even though the planner requested a “fully refreshed answer.”

**Root Cause**

- When SQL finished, the sequencer immediately restarted another run (see the second batch of `Tool sql_generator started` events) before ever calling `_kickoff_parallel_lanes`. Because the second run never progressed past the intent stage (due to the disconnect above), the first set of accessory lanes remained pending forever.

**Fix Plan**

1. When issuing a new run, call `sequencer.abort_pending_lanes(reason="restart")` so any leftover `web/market` lanes from the previous attempt are marked as skipped (preventing duplicate pending entries).
2. In `_run_sql_stage`, enqueue a task to kick off accessories as soon as SQL reaches `sql_ready`, even if another run is queued, so cached data can still be reused.
3. Add telemetry assertions that every time `follow_up_route` requests `STOCK_ONLY` or `FULL_PIPELINE`, we eventually see either `web_ready`/`stock_ready` or an explicit `lane: ... reused` event.

*Outcome:* accessory work either runs or is explicitly marked “reused/skipped,” eliminating the long-lived pending bars and shaving seconds off end-to-end latency.

---

## 5. Revision Runs Still Feel Scripted Instead of Agentic

**Evidence**

- Even after the remediation work, revision turns reuse cached intent but still march through the same sequenced SQL → chart → analysis pipeline. The ledger never shows the agent reasoning about *why* a tool is needed; all steps are pre-scheduled, and tool telemetry only reflects pipeline stages, not autonomous choices. Users therefore continue to see repetitive bubbles (“Planning chart…”, “Running SQL…”) even when a revision only needs one lane.

**Root Cause**

- The single-agent controller owns a fixed sequencer that decides ahead of time which lanes to run. The planner doesn’t have the ability to call tools opportunistically or parallelize accessories based on context, so the revision path is just a cached baseline rerun with different flags.

**True-Agent Fix Plan**

1. **Agent-driven tool orchestration**
   - Replace the revision sequencer with an “agent loop” that exposes tool adapters (SQL, chart, analysis, web, market) directly to the planner.
   - When `session_follow_up=True`, the planner receives a `RevisionContext` containing:
     - Cached artifacts (SQL result set hash, chart spec, analysis text)
     - Tool receipts from the initial run (arguments + outputs)
     - Diff metadata (e.g., user focus, revised tickers, chart changes)
   - The planner inspects that context and explicitly invokes the tools it needs (`invoke_tool("sql_generation")`, `invoke_tool("chart_revision")`, etc.), emitting tool call SSEs just like the multi-agent supervisor.

2. **Persist & hydrate context from the fresh run**
   - Extend `SessionStateSnapshot` to store per-tool receipts (inputs, hashes, output fingerprints) plus agent reasoning summaries.
   - On every revision request, hydrate the planner’s `RevisionContext` with those receipts so the agent knows:
     - Which SQL query and chart were used
     - Whether web/stock accessories succeeded, with their payloads
     - What analysis conclusions were delivered
   - This lets the agent decide, for example, “SQL is still valid; skip it, but regenerate the chart with a new focus,” or “Web data is stale; fire the web tool only.”

3. **Expose genuine chain-of-thought to the UI**
   - Each tool invocation yields `agent_tool_call` / `agent_tool_complete` events, so the frontend shows “Agent: regenerating SQL to add NVDA” instead of repeating “Running SQL” banners.
   - If the agent halts (e.g., decides a brand-new baseline is required), emit `workflow_redirect` so the UI can prompt the user to start over.

4. **Adaptive concurrency & retries**
   - Give the agent the option to spin up accessory lanes via `run_tool_parallelism` when it determines both web + market need refresh—mirroring multi-agent behavior but within the single-agent flow.
   - Surface retry metadata so the agent can re-run SQL or chart with new parameters instead of restarting the entire sequencer.

*Outcome:* revision turns now look and feel like a real agent session—context from the initial run is reused intelligently, tool invocations are chosen on the fly, and the UI shows authentic reasoning instead of scripted pipeline stages. This also lays the groundwork for migrating the single-agent path onto the same telemetry model as multi-agent flows, closing the gap between the current implementation and the “single agent + multiple tools” vision.

---

## 6. Function-by-Function Refactor Plan

To deliver the true-agent revision experience (and clean up lingering technical debt), here’s the targeted refactor plan by module/function. Each entry lists the current issue, what to refactor, and the expected outcome.

### `backend/analytics/flows/single_agent_tools.py`

1. **`_SingleAgentToolHooks.before_event/after_event`**  
   *Issue:* Only intent-classifier events support multi-phase dedupe.  
   *Refactor:* Extend `MULTI_PHASE_TOOL_CONFIG` and reuse `_build_tool_call_event` for SQL/Chart/Analysis. Persist per-tool `run_state` objects so we can merge details and emit one completion.  
   *Outcome:* Clean telemetry + groundwork for agent-driven tool loops.

2. **`SingleAgentController._prepare_sequencer_state`**  
   *Issue:* Always pre-seeds lane states for revisions, preventing agent autonomy.  
   *Refactor:* When `session_follow_up=True`, create a `RevisionContext` with cached artifacts/tool receipts and skip sequencer lane seeding.  
   *Outcome:* Planner gains control over which tools to rerun.

3. **`SingleAgentController.sequencer_stream` / `_agentic_event_stream`**  
   *Issue:* Sequencer enforces fixed SQL→chart→analysis flow.  
   *Refactor:* Introduce an “agent loop” executor (flagged) where the planner itself invokes tools. Sequencer remains as fallback for legacy mode.  
   *Outcome:* Revision runs become agent-driven without destabilizing baseline runs.

### `backend/analytics/flows/planner_executor.py`

4. **`PlannerExecutorFlow.initialize_context`**  
   *Issue:* Stores limited data about prior tool invocations.  
   *Refactor:* Load tool receipts, chart specs, and accessory payload hashes from `SessionStateSnapshot`, and attach them to `PlannerPhaseContext.revision_context`.  
   *Outcome:* Agent has full knowledge of what happened in the baseline run.

5. **`PlannerExecutorFlow._stream_with_tool_state`**  
   *Issue:* Lacks hooks for emitting agent tool SSEs.  
   *Refactor:* When running in agentic revision mode, wrap tool invocations with `agent_tool_call`/`agent_tool_complete` events (mirroring multi-agent).  
   *Outcome:* Frontend can display true chain-of-thought logs.

### `backend/analytics/flows/sequencer.py`

6. **`PlannerSequencer.mark_lane_complete` & `_run_lane`**  
   *Issue:* Doesn’t understand agent-initiated lane skips/cancels.  
   *Refactor:* Allow the agent loop to mark optional lanes as `skipped` or `completed` without running `_run_lane`. Add explicit `cancel_lane` helper triggered on run restart.  
   *Outcome:* No ghost “pending” lanes when the agent bypasses accessories.

### `backend/analytics/core/session_state.py`

7. **`SessionStateSnapshot` (tool receipts)**  
   *Issue:* Only stores high-level metadata.  
   *Refactor:* Persist per-tool `Receipt` objects (arguments, output hashes, timestamps) and expose `revision_context()` to hydrate planners.  
   *Outcome:* Future revisions can reason about deltas (e.g., “SQL hash unchanged, reuse result”).

### Frontend (`components/analytics/hooks/useAnalyticsMemoryStream.ts`)

8. **`handleStreamEvent` (agent telemetry)**  
   *Issue:* Only knows about pipeline-style events.  
   *Refactor:* Add handlers for `agent_tool_call`/`agent_tool_complete`, render them as steps, and collapse duplicate progress logs using event IDs.  
   *Outcome:* UI mirrors true agent reasoning and avoids repetitive bubbles.

9. **`handleQuery` (revision control)**  
   *Issue:* Automatically appends `session_id` but can’t detect backend redirects.  
   *Refactor:* Listen for `workflow_redirect`/`workflow_cancelled` and prompt the user to start a new baseline if the agent requests a reset.  
   *Outcome:* Smooth UX when the agent decides a fresh run is required.

### `backend/analytics/flows/multi_agent.py` (reference)

10. **`SupervisorAgentOrchestrator.on_tool_call`**  
    *Issue:* Already supports agent loops—use as blueprint.  
    *Refactor:* Extract common helpers for emitting agent events so single-agent mode can reuse the same telemetry format.  
    *Outcome:* Consistent behavior between single-agent and multi-agent flows.

By executing this refactor plan, we turn revision runs into genuine agent-driven sessions, reduce duplicate work, and provide the UI with accurate, meaningful telemetry.

---

## 7. Session Expiration Errors on Every Revision

**Evidence**

- The UI now blocks every follow-up with: “The previous analysis session expired. Please start a new analysis run before requesting revisions.” (seen in both single- and multi-agent modes at ~22:43 on Nov 6).  
- The latest `agent-process-ledger - 2025-11-06T223142.136.json` contains **no** `session_started` events nor any `session_id` fields, so the frontend never learns the session identifier to reuse.  
- `backend/backend_uvicorn.log` likewise shows no `session_started` telemetry, confirming the backend isn’t emitting that SSE anymore.

**Root Cause**

- During the refactor, `SingleAgentController.events` and `MultiAgentFlow.events` stopped yielding `EventEmitter.session_started(...)`. The planner still creates a `SessionStateSnapshot`, but the SSE stream never exposes the ID to the client. Our updated frontend logic now *requires* that event before it sends revisions, so every follow-up fails locally before even calling the backend.

**Fix Plan**

1. **Restore `session_started` emission in every flow**
   - In `SingleAgentController.events`, after `_prepare_sequencer_state` resolves the context, immediately yield `EventEmitter.session_started(ctx.session_id)` (and ensure hooks see it so telemetry stays consistent).
   - Do the same inside `MultiAgentFlow.events` (or its orchestrator) before any planner work begins.
   - Update `_forward_with_hooks` so even cached runs (agentic revisions, accessory refreshes, etc.) always push one `session_started` event per request.

2. **Include session fallbacks in downstream events**
   - Add `session_id` to the data payload of key milestones (`follow_up_route`, `analysis_ready`, `workflow_complete`) so the frontend can recover even if the initial event drops.
   - Extend `useAnalyticsMemoryStream` to capture `session_id` from those payloads as a backup (without waiting on the dedicated event).

3. **Regression tests**
   - Add a streaming test in `backend/tests/analytics/test_single_agent_stream_events.py` (and the multi-agent suite) that collects the first few SSEs and asserts `session_started` is present with a non-empty ID.
   - Add a frontend hook test that feeds a stream missing `session_started` but including `analysis_ready.session_id` and verifies we still store it, preventing the “session expired” toast.

4. **Manual verification**
   - After the fix, run a full baseline + revision in both single- and multi-agent modes to confirm the UI stores the session, the revision request includes `session_id`, and the earlier error no longer appears.

*Outcome:* Revisions once again reuse the correct session context automatically, and the UI never strands users with the “session expired” message unless the backend truly purges the session.

---

Addressing the four items above will remove the duplicated chart/planning spam, stop the UI from showing ghost “thinking” entries, and ensure lane states always settle—even when runs restart mid-flight. Let me know which fix you’d like prioritized first.  

---

## Progress Update – 2025‑11‑07 @ 11:15 PT

**Shipped:** Session lifecycle telemetry + frontend fallbacks.

- `_forward_with_hooks` in both **SingleAgentController** and **MultiAgentFlow** now synthesizes a `session_started` event whenever the upstream stream fails to emit one, and every `follow_up_route`, `analysis_ready`, `analysis_complete`, and `workflow_complete` payload inherits the active `session_id`. Cancellation emitters attach the ID too, so the UI never loses track of the run.
- All streaming entry points (`events`, `chart_revision`, `run_web_refresh`, `run_market_refresh`, `analysis_revision`, etc.) were updated to pass `ensure_session_event=True`, guaranteeing consistent telemetry even for cached tool invocations and accessory refreshers.
- Added backend regression coverage:
  - `backend/tests/analytics/test_single_agent_final_answer.py::test_session_metadata_attached_to_analysis_ready`
  - `backend/tests/analytics/test_single_agent_final_answer.py::test_forward_with_hooks_emits_session_started_once`
  - `backend/tests/analytics/test_multi_agent_flow.py::test_multi_agent_forward_with_hooks_tags_session_metadata`
- Frontend hook (`components/analytics/hooks/useAnalyticsMemoryStream.ts`) persists any fallback `session_id`, dedupes “thinking” logs with a single helper, and clears the cache between turns. Vitest coverage (`useAnalyticsMemoryStream.session reuse`) now asserts that follow-ups always include the cached `session_id`, even if the original `session_started` dropped.

**Impact:** The app no longer surfaces the “session expired” toast unless the backend truly deleted the session, and every follow-up query automatically reuses the correct context—closing Issue #7 from this findings doc.
## 5. Accessory Fast-Path Validation (Nov 8, 2025)

**Fixes**
- `_kickoff_parallel_lanes` now dispatches as soon as `sql_ready` lands, emitting `lane_reused` within the first tool turn. `backend/tests/analytics/test_planner_sequencer.py::test_parallel_lanes_start_immediately_after_sql_ready` guards the <2 s SLA.
- `SessionStateSnapshot` receipts store `age_seconds` and `fast_path_latency_ms`; lane reuse warnings flow through `_update_lane_state_from_event`, and `_forward_with_hooks` synthesizes `session_started` even on cache-only runs.
- Multi-agent flows output `agent_tool_call/complete` alongside `agent_turn_*`, keeping supervisor telemetry in lock-step with the single-agent schema.
- `scripts/backfill_accessory_receipts.py` upgrades legacy sessions so Redis contains the richer reuse metadata.
- Grafana can now key off `agent_tool_gap` telemetry emitted whenever completions lag calls by >10%.

**Proof**
- Pytest: `backend/tests/analytics/test_session_state_receipts.py` (reuse metadata) and `backend/tests/analytics/test_single_agent_stream_events.py` (session fallback + warnings).
- Telemetry log excerpt (`agent_tool_gap`): `{ "event": "agent_tool_gap", "lane": "web", "outstanding": 2, "total_calls": 12, "threshold": 0.1 }`.
- Backfill dry-run: `python scripts/backfill_accessory_receipts.py --session SESSION_ID --dry-run` prints the number of upgraded snapshots before writing, so ops can rehearse before touching prod Redis.

## 6. Canvas Telemetry Parity (Nov 8, 2025)

- `components/analytics/visualization/WorkflowCanvas.tsx` now consumes the same `laneReuseNotices` / `redirectNotice` payloads as ProcessPanel, renders tool badges sourced from `tool_calls` / `agent_turns`, and tags the capture root with `data-screenshot-target="workflow-canvas"`.
- ProcessPanel + Memory page pipe the new props straight through so GTM sees the same badges the debugger sees; WorkflowCanvas test coverage (`npm run test -- WorkflowCanvas.test.tsx useAnalyticsMemoryStream.test.tsx`) snapshots the tool-badge + reuse-pill states.
- `docs/design/workflow-canvas-20251114.svg` illustrates the new header (agent badge, lane reuse chip, redirect banner) and serves as the single asset for GTM decks.

## 7. Automation & Alerting Hooks (Nov 8, 2025)

- `.github/workflows/agentic-smoke.yml` now runs the fixture suite on every push/PR, publishes `agentic-smoke-fixtures` artifacts, and exposes an optional `run_live` switch (plus the `AGENTIC_SMOKE_BACKEND_URL` secret) to replay STOCK_ONLY / REUSE_SQL / redirect flows against staging.
- Grafana’s “Agent Tool Gap” alert wires to the same telemetry (`analytics.agent_tool_gap`) while the workflow artifacts provide the runbook evidence called out in `docs/ops/agents-supervisor-alerts.md`.
