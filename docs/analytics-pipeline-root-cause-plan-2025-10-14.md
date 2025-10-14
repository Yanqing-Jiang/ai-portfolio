# Analytics Pipeline Root-Cause Plan (2025-10-14)

## Context Recap
- **Single-agent run** (`docs/agent-process-ledger (33).json`): Market share chart dropdown hides the “Market Share Percent” series, SQL template emits quarterly data, accessories appear sequential after chart finish.  
- **Single-agent follow-up** (`docs/agent-process-ledger (34).json`): Chart revision fails with `CHART_REVISION_MISSING_SESSION`.  
- **Multi-agent run** (`docs/agent-process-ledger (35).json` and revision `(36).json`): Missing SQL/Stock/Web cards before supervisor summary, repeated `cohesive_result_error`, chart spec data arrives as serialized strings, duplicate accessory executions, unnecessary “Web Context Ready” card, revision flow replays earlier agents.

## Findings & Root Causes
1. **Chart dropdown logic drops base series**  
   - `components/analytics/common/ChartCard.tsx:30-88` hides every legend entry then only re-selects names that match hard-coded patterns like `"Company - Metric"`. Plain labels (e.g., `"Market Share Percent"`) never re-enable, so the chart renders empty even though `chart_spec.series[0].data` contains values in `agent-process-ledger (33)` (`market_share_percent` array).  
   - Result: dropdown appears but toggling “Market Share Percent” blanks the chart and the legend loses its primary series.

2. **Market share template defaults to quarterly granularity**  
   - `backend/config/schemas/metrics.yaml:376-404` defines `market_share_single` with `default_granularity: "quarterly"` and `allowed_granularities: ["quarterly"]`. The SQL template (`backend/config/schemas/queries.yaml:6-45`) expects the `{select_clause}` to include quarter columns, so the generated SQL in ledger (33) returns `calendar_quarter` rows instead of annual aggregates.  
   - This contradicts the requirement to “pull annual aggregate” by default.

3. **Accessory scheduling diverges from declared plan**  
   - Single-agent schedule (`backend/analytics/flows/schedulers.py:210-260`) claims the `accessories_pre_analysis` fan-out occurs before `chart_generation`. In practice, `PlannerExecutorFlow.events` (`backend/analytics/flows/planner_executor.py:1700-1710`) runs chart generation immediately after SQL and only afterwards calls `_ensure_analysis_dependencies`, which replays `run_tool_parallelism` / `_web_search_phase`.  
   - Outcome: chart completes before the web/stock results surface, giving a sequential feel despite the earlier manifest event.

4. **Follow-up chart revision lacks a persisted session snapshot**  
   - Follow-up failure in ledger (34) shows `chart_revision` hitting `missing_session`. `SingleAgentFlow.chart_revision` (`backend/analytics/flows/single_agent_tools.py:460-495`) delegates to planner tooling, but `useAnalyticsMemoryStream.resetState()` (`components/analytics/hooks/useAnalyticsMemoryStream.ts:2733-2736`) clears `sessionId` between runs.  
   - Without reusing the prior session ID (or hydrating from storage), revisions cannot locate artifacts to patch.

5. **Multi-agent accessories & cohesive result gaps**  
   - Accessory readiness requires tool results (`_hedged_accessories_ready` in `backend/analytics/flows/multi_agent.py:979-1010`), but the orchestrator emits `cohesive_result_error` repeatedly (`docs/agent-process-ledger (35).json` contains multiple `cohesive_result_error`). This prevents a sanitized `cohesive_result` with SQL, stock, and web data, and triggers redundant specialist replays.  
   - The captured chart spec (`chart_generation.details.chart_spec.series[0].data`) is a space-separated string, implying that somewhere between `planner_executor` and `_capture_event` the numeric list is coerced to a single string—likely during sanitizer passes for `Decimal` values.  
   - `specialistCards` and chat lanes show duplicate “Web Context Ready” payloads because both the tool fan-out result and `_web_search_phase` feed into the shared web context without dedupe.

6. **Multi-agent revision replays full pipeline**  
   - Revision ledger `(36)` shows agents rerunning with new chart patch plus an extra financial analysis. The orchestrator currently rebuilds `_base_plan` on every revision; there is no guard to reuse existing artifacts or skip agents whose outputs are already current.

## Remediation Plan
1. **Fix Chart Dropdown Handling (Single Agent & Multi Agent UI)**  
   - Update `handleMetricChange` to recognise exact legend labels and series meta, falling back to direct matches when the `" - "` convention is absent.  
   - Add a unit test in `components/analytics/common/__tests__/ChartCard.test.tsx` covering simple labels (e.g., `Market Share Percent`).  
   - Manual check: load single-agent run, switch dropdown, confirm primary series stays visible.

2. **Default Market Share Template to Annual Aggregates**  
   - Adjust `metrics.yaml` for `market_share_single` (and `market_share_all` if needed) to `default_granularity: "annual"` and widen `allowed_granularities` to include `"annual"`.  
   - Update `queries.yaml` template to aggregate by `calendar_year` when `{granularity}` resolves to annual (e.g., swap quarter columns with year-only projections when `{group_by_clause}` collapses to year).  
   - Extend `backend/tests/analytics/test_planner_executor_sql.py` with a case asserting the generated SQL includes `SUM(...) AS market_share_percent` and omits quarter columns under default parameters.

3. **Align Accessory Scheduling With Plan**  
   - Refactor `PlannerExecutorFlow.events` so that, after SQL execution, it launches accessory fan-out and waits for their completion (or at least emits `stock_ready` / `web_ready`) before `chart_generation`.  
   - Ensure `_ensure_analysis_dependencies` no longer re-runs accessories when `tool_parallel_results` already contain fresh outputs.  
   - Add telemetry assertions in `backend/tests/analytics/test_single_agent_cohesive_payload.py` ensuring `tool_parallel_start` precedes `chart_generated`.

4. **Persist Session Context for Follow-ups**  
   - Retain the last non-empty `sessionId` across runs in `useAnalyticsMemoryStream`, and only reset on explicit user clear. Alternatively, request a fresh session via backend but hydrate necessary artifacts before revisions.  
   - Add a regression test (Cypress/playwright or Jest mock) to confirm `chartRevision` calls include the persisted session ID after an initial run.

5. **Stabilize Multi-Agent Artifact Surfacing**  
   - Investigate sanitizer pipeline in `_capture_event` (`multi_agent.py:1325-1375`) to preserve numeric arrays—confirm whether decimals from `chart_ctx` require conversion to `float` prior to `sanitize_for_json`.  
   - Ensure `_maybe_queue_sql_ready` / `_maybe_queue_chart_ready` fire once and surface cards before supervisor analysis.  
   - Gate redundant “Web Context Ready” cards by checking `web_ctx.from_cache` & timestamps prior to enqueuing.

6. **Ensure `cohesive_result` Contains Required Keys**  
   - Populate fallback values if an accessory is missing but optional, or delay supervisor synthesis until `_hedged_accessories_ready()` confirms both stock and web payloads.  
   - Add a unit test in `backend/tests/analytics/test_multi_agent_flow.py` asserting `cohesive_result` includes `sql`, `chart_spec_id`, `stock_widget`, and `web_context` in the successful path.

7. **Revision Flow Optimisation (Options for User)**
   - Option **A**: Implement dependency-aware replay—only rerun agents whose upstream inputs changed (e.g., chart revision should invoke `chart_agent` + `insight_reviewer`, skip planner/SQL).  
   - Option **B**: Introduce state snapshots so the supervisor can patch existing artifacts without triggering full orchestration.  
   - Option **C**: Allow user to choose between “quick patch” (chart-only) and “full rerun”, wiring the selection through the follow-up UI and orchestrator plan builder.

## Verification Checklist
- Front-end: `npm test -- ChartCard.test.tsx` plus manual dropdown sanity check.
- Backend: `pytest backend/tests/analytics/test_planner_executor_sql.py backend/tests/analytics/test_multi_agent_flow.py`.
- End-to-end: Trigger single-agent and multi-agent runs in dev env, confirm timeline shows concurrent accessory completion and cohesive result card with SQL/Web/Stock before supervisor summary.

