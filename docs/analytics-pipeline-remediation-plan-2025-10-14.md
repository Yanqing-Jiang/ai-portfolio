# Analytics Pipeline Remediation Plan (2025-10-14 — Ledgers 21 & 23 Follow-up)

## Observed Regressions
- **Market share series hides itself**: In `docs/agent-process-ledger (21).json` the `Interactive Visualization` legend exposes `"Market Share Percent"`, but selecting that option blanks the chart. `components/analytics/common/ChartCard.tsx:34-110` resets every legend entry and only re-enables names that match `"Company - Metric"` patterns, so plain labels like `"Market Share Percent"` never toggle back on.
- **Quarterly output despite annual requirement**: The same ledger shows an `xAxis.data` sequence of `"2024 Q1" ... "2025 Q2"`, because `backend/config/schemas/metrics.yaml:434-452` sets `default_granularity: "quarterly"` and the SQL template in `backend/config/schemas/queries.yaml:3-47` always injects quarter fields. This conflicts with the request to make the market share template default to annual aggregates.
- **ECharts incompatibility in multi-agent run**: `docs/agent-process-ledger (23).json` captures `chart_generation.details.chart_spec.series[0].data` as a single string (`"24803000320 53774999552 …"`), which echarts cannot plot. The sanitiser in `backend/analytics/validators/cohesive_result.py:26-60` converts `Decimal` samples into strings instead of floats, collapsing the list into a space-delimited string in downstream serialisation.
- **Missing / duplicated specialist cards**: In `docs/agent-process-ledger (23).json` there is no `Generated SQL` or `Online Research` card before the supervisor summary, while the stock and web cards surface twice. `MultiAgentFlow._queue_artifact_event` (around `backend/analytics/flows/multi_agent.py:1024-1105`) queues plain payloads without `specialist_card` metadata and stores both `web_retriever_cached` and `web_retriever_live` results verbatim, so the frontend renders duplicates and skips the SQL card entirely.
- **Fan-out canvas lacks usable zoom & drag affordances**: The orchestration view relies on `<Controls showInteractive={false} showFitView={false}>` in `components/analytics/visualization/WorkflowCanvas.tsx:740-772` and immediately reapplies layout positions, so users cannot zoom with UI buttons or freely reposition nodes—even though power users expect to drag the agent nodes while inspecting concurrency.
- **Long waits before analysis finishes**: The user reports ~99 s idle time. In ledger (21) `tool_execution.elapsed_ms` is `38742` and the accessory fan-out does not start until after `chart_generation` completes (compare sequences 39 vs 44). `PlannerExecutorFlow.events` (lines `2330-2415`) still invokes `chart_generation` before running `_ensure_analysis_dependencies`, so stock/web collectors only kick off once the analysis phase begins. This sequential ordering keeps the analysis writer blocked on upstream latency.

## Remediation Steps
1. **Stabilise chart dropdown & numeric payloads**
   - Update `ChartCard.handleMetricChange` to recognise exact legend labels plus `meta.displayNames`, defaulting to the first `meta.defaultColumns` entry. Preserve previous selections when the option matches directly (e.g., `"Market Share Percent"`), and keep multi-series patterns (YoY, margin change) intact.
   - Extend `components/analytics/common/__tests__/ChartCard.test.tsx` with a regression that simulates selecting `"Market Share Percent"` and asserts the legend retains a true entry after the change.
   - Normalise numeric series before hydration: when hydrating `chartSpec` on the frontend, coerce stringified floats back into numbers to avoid stale caches.
   - Tests: `npm test -- ChartCard.test.tsx`.

2. **Default market share intent to annual aggregates**
   - Change `backend/config/schemas/metrics.yaml` for `market_share_single` (and `market_share_all` for parity) to `default_granularity: "annual"` and extend `allowed_granularities` to `["annual","quarterly"]`. Replace hard-coded quarter filters (`granularity_filter`) with conditional logic so annual runs don’t exclude rows.
   - Amend `backend/config/schemas/queries.yaml` to drop quarter-specific filters when `{granularity}` resolves to annual (rely on `_granularity_clauses` to inject `calendar_year`). Add an example clause that shows yearly roll-ups (`calendar_year` and `SUM(...) AS market_share_percent`).
   - Strengthen `backend/tests/analytics/test_planner_executor_sql.py` with an assertion that the compiled SQL for `market_share_single` uses `calendar_year` when no granularity override is provided.
   - Tests: `pytest backend/tests/analytics/test_planner_executor_sql.py -q`.

3. **Fix JSON sanitisation for chart data**
   - Introduce `Decimal` handling in `sanitize_for_json` so numeric payloads are emitted as floats (`float(Decimal)`), keeping list structures intact. Guard against scientific notation drift by rounding only when necessary.
   - Add a unit test in `backend/tests/analytics/test_multi_agent_flow.py` (or a new focused test) that feeds a mock chart spec with `Decimal` values and asserts the sanitised output preserves a numeric list.

4. **Surface deduplicated specialist artifacts in multi-agent flow**
   - When capturing tool results in `MultiAgentFlow._capture_event`, normalise tool aliases (`web_retriever_cached`/`web_retriever_live` → `web_retriever`) and keep only the freshest payload per tool.
   - Extend `_queue_artifact_event` to attach `specialist_card` metadata mirroring the single-agent flow (SQL, chart, stock, web) so ProcessPanel renders `Generated SQL`, `Stock Tracker`, and `Online Research` exactly once.
   - Ensure `cohesive_result.tool_results` contains the final deduplicated entries and that `web_context` is populated before the supervisor analysis stage.
   - Tests: `pytest backend/tests/analytics/test_multi_agent_flow.py -k cohesive_result` plus a new assertion that no duplicate `web_retriever` entries appear.

5. **Launch accessories concurrently and instrument latency**
   - Refactor `PlannerExecutorFlow.events` so that after `sql_generation` succeeds it immediately launches `run_tool_parallelism` for `stock_tracker` and `web_retriever` (subject to reuse flags) before `chart_generation`. Update `_ensure_analysis_dependencies` to short-circuit if the parallel run already finished.
   - Emit telemetry describing overlap (e.g., inject `tool_parallel_start` before `chart_generation`) and add a latency marker to measure time between SQL completion and first streaming chunk; persist it in `tool_execution.details.tool_calls`.
   - Validation: extend `backend/tests/analytics/test_planner_executor_sql.py` (or add a new async test) to assert the emitted event order is `sql_ready` → `tool_parallel_start` → `chart_ready`, proving accessories now run alongside charting.

6. **Expose zoom/drag controls on the orchestration canvas**
   - Enable interactive controls in `WorkflowCanvas` (`showInteractive`, `showZoom`, `showFitView`), add +/- buttons, and keep manual node moves by storing the last dragged position before applying layout diffs. Document the new UI affordances.

7. **Documentation & verification**
   - Update `backend/analytics/ARCHITECTURE.md` (and `docs/analytics-pipeline-root-cause-plan-2025-10-14.md` if needed) to describe annual defaults, accessory concurrency, and the sanitisation fix.
   - Follow the project’s testing cadence: run `pytest backend/tests/analytics/test_planner_executor_sql.py backend/tests/analytics/test_multi_agent_flow.py` after backend changes and `npm test -- ChartCard.test.tsx` after frontend updates. Repeat targeted tests after each major change before attempting a broader suite.

## Execution Order
1. Chart dropdown + sanitisation fixes (Steps 1 & 3 together, shared ChartCard impact).
2. Market share SQL default adjustments (Step 2).
3. Multi-agent artifact dedupe & specialist cards (Step 4).
4. Planner concurrency & latency instrumentation (Step 5).
5. Workflow canvas controls (Step 6).
6. Documentation updates and final validation (Step 7).

This ordering unblocks the visible chart regression first, then hardens backend data and multi-agent outputs before tackling concurrency and UX polish.
