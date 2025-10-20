# Concurrent Streaming & Ordering Fix Plan

Progress update: October 20, 2025

1. **Audit Current Event Timing** — Status: Completed  
   - Planner queue drains confirm `tool_parallel_result` events precede downstream SQL milestones. Ledgers 88 and 89 still match the documented timeline, so no additional instrumentation is required.

2. **Flush Accessory Lanes Immediately (Single-Agent)** — Status: Completed  
   - `_flush_tool_events` now drains adapter queues as soon as work finishes. Single-agent ledgers (84, 88) show `stock_ready` and `web_ready` landing ahead of `sql_ready`, validating the change.

3. **Mirror Early Emission in Multi-Agent Orchestrator** — Status: Completed  
   - `MultiAgentFlow._capture_event` now invokes `_maybe_queue_stock_ready` and `_maybe_queue_web_ready` inside the `tool_parallel_result` branch, so accessory cards broadcast as soon as specialists report back. Lane metadata (`lane`, `parallel_group`, reuse flags) flows through the shared payload, and ledger 89 should now display market/web updates before SQL completes.

4. **Enforce Annual Granularity for "Years" Requests** — Status: Completed  
   - `compile_sql_from_plan` supports `sql_template_annual/sql_template_quarterly` overrides and chooses the annual variant when `plan.granularity === "annual"`. The revenue-growth template in `backend/config/schemas/queries.yaml` now ships annual SQL that drops quarter columns, ensuring “last 5 years” produces yearly buckets and the chart hydrates on `calendar_year` only.

5. **Stream Cards Incrementally With Priority Ordering** — Status: Completed  
   - `useAnalyticsMemoryStream` seeds the assistant bubble at `tool_parallel_start`, updates lane attachments as soon as each `*_ready` event arrives, and ranks specialist cards via `chart → analysis → market → web → sql`. Stock/web cards now surface immediately (pending backend timing), and duplicate accessory cards are coalesced by lane/topic.

6. **Live Status Bubble Placement** — Status: Completed  
   - `ChatHistory` shows a left-aligned status bubble that persists above the card stack until artifacts replace it; ledger 85 still matches the target layout.

7. **Regression Coverage** — Status: In Progress  
   - New code paths need automated coverage: multi-agent accessory fan-out, annual SQL compilation, and the refreshed card-ordering logic. Test updates remain queued because the current directive is to defer execution.

8. **Verification** — Status: Blocked  
   - Pytest/Vitest suites were not rerun per instruction. Manual ledger validation is recommended once test execution is permitted.

Immediate focus once testing is greenlit:
- Add backend integration coverage that proves `stock_ready`/`web_ready` precede `sql_ready` in multi-agent flows.
- Extend SQL planner/compiler tests for the annual revenue-growth template.
- Add Vitest snapshots covering lane-priority rendering and ensure the assistant bubble still anchors correctly with real-time data.
