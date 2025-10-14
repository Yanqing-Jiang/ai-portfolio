# Option B Implementation Plan — Session Snapshot Reuse (2025-10-14)

## Goals
- Retain just-enough artifacts in Redis-backed session state so chart or narrative revisions can reuse prior results without triggering full reruns.
- Let single-agent and multi-agent supervisors decide whether to reuse snapshots or re-run specialists, based on whether intent criteria changed.
- Keep direct workflow behaviour unchanged (always reruns).

## Proposed Snapshot Schema (SessionStateSnapshot.tool_cache.analytics)
We already persist `analytics.artifacts` in Redis. We will extend that payload with a lightweight `revision_snapshot` that contains:

| Key | Example | Purpose |
| --- | --- | --- |
| `intent_signature` | `{ "key": "market_share_single", "slots": { "ticker": "NVDA", "scope": "market_share" }, "granularity": "annual" }` | Hashable summary used to detect whether criteria changed between runs. Slots are the normalized planner inputs relevant to rerun decisions. |
| `sql` | `"WITH market_revenue AS (...)"` | Raw SQL text for reuse / display. |
| `sql_row_count` | `240` | Allows quick validation that prior dataset is meaningful. |
| `data_sample` | First 50 rows | Enables read-only UI cards during revisions. |
| `columns` | `["calendar_year", "market_share_percent", ...]` | Maintains column labels for SQL card. |
| `chart_spec` / `chart_spec_id` | Last emitted chart | Lets chart revision start from latest spec. |
| `stock_widget` | Current ticker widget config | Avoids re-fetch if still fresh. |
| `web_context` | Latest web summary/snippets | Keeps web card populated when revision is chart-only. |
| `analysis` / `analysis_length` | Optional final analysis | Useful for supervisor quick patch messaging. |

We will store this under `snapshot["tool_cache"]["analytics"]["revision_snapshot"]` so existing history and TTL logic continue to apply.

## Intent Signature & Criteria Diff
- **Extraction**: After analysis completes, derive a normalized signature using planner context — intent key, slots (`ticker`, `peer_scope`, `metric_filters`, etc.), plan granularity, years_back, and comparison flags.
- **Storage**: Save this signature alongside the revision snapshot.
- **Comparison**: On follow-up requests, compute a fresh signature and compare. If any tracked field changes (e.g., ticker switches from `NVDA` to `AMD`), mark the run as “criteria changed”.
- **Agent Decision**:
  - Single-agent flow: before launching planner pipeline for a revision, check the stored signature. If unchanged, allow targeted revision (e.g., chart patch). If changed, proceed with a full rerun.
  - Multi-agent supervisor: same logic in orchestration bootstrapping (`_prepare_context`). If signature changed, flush cached artifact context and force planner/SQL/stock/web specialists to run.
  - Direct mode: skip signature check entirely because the user explicitly wants a fresh execution each time.

## Flow Integration
1. **Persistence Hooks**
   - During `PlannerExecutorFlow._capture_artifacts`, build the `revision_snapshot` object whenever SQL, chart, stock, or web artifacts update.
   - Call `SessionStateSnapshot.record_tool_result("revision_snapshot", payload)` so the data travels through Redis.
   - Ensure data is sanitized to handle `Decimal` types (convert to floats).

2. **Revision Bootstrapping**
   - Single-agent:
     - At `SingleAgentFlow.events` start, load session snapshot. If `revision_snapshot` exists and signature matches, pre-populate planner context (`ctx.reuse_sql`, `ctx.reuse_chart`, etc.).
     - Provide helper methods `should_rerun_sql(ctx)` etc. so downstream steps know whether to call specialists.
   - Multi-agent:
     - Extend `_prepare_context` in `multi_agent.py` to pull `revision_snapshot` and seed `self._shared_context['sql']`, `'chart'`, `'stock_widget'`, `'web'`, etc. when signature matches.
     - Mark accessories as ready when seeded (e.g., `_hedged_accessories_ready` should accept cached payloads flagged with `from_cache=True`).

3. **Agent Decision Logic**
   - Single-agent:
     - Before invoking `run_tool_parallelism`, check if cached web/stock data is still valid; skip launching those tools if reuse is allowed.
     - Chart revision endpoints can now locate the prior spec even when the UI resets.
   - Multi-agent:
     - In `_run_agent_orchestration`, avoid scheduling planner/query agents if reuse is allowed and cached SQL exists. Only run viz/analysis agents when patching chart/analysis.

4. **Session Reset Rules**
   - Continue clearing session snapshots when the user starts a brand-new chat (handled by current `setSessionId('')` in frontend).
   - Add backend guard: if the frontend sends an empty session ID, skip reuse and create a fresh snapshot to prevent cross-session bleed.

## Testing Strategy
- **Unit Tests**
  - Add snapshot serialization test in `backend/tests/analytics/test_planner_executor_sql.py` verifying `revision_snapshot` contains expected keys and sanitized values.
  - Expand `backend/tests/analytics/test_multi_agent_flow.py` to simulate chart-only revision using stored snapshot; assert no new SQL execution events fire when signature matches.
  - New single-agent test to confirm `chart_revision` succeeds after UI reset (no `missing_session` error).
- **Integration Smoke**
  - Manual: run single-agent query, then submit chart patch without changing ticker to ensure cached web/stock cards appear instantly.
  - Manual: change ticker to trigger full rerun and confirm pipeline executes all specialists.

## Next Steps
1. Implement snapshot builder & storage in `PlannerExecutorFlow` + shared models.
2. Wire reuse logic into single-agent and multi-agent flows (including accessory readiness fixes discussed earlier).
3. Update frontend session handling if necessary (e.g., keep session ID stable between follow-up actions).
4. Add the outlined tests and run targeted `pytest backend` suites.
