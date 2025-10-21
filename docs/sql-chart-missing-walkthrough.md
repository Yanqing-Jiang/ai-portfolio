# SQL Chart Missing Walkthrough

This note documents what we observed in `agent-process-ledger (4).json` for the “SQL ran but chart never rendered” report, plus the follow-up actions we recommended.

## 1. Timeline From the Ledger
- Run produced 19 events; the last payload-bearing event was `sql_execution` at `2025-10-21T22:38:54Z` with six rows returned.
- No `chart_ready`, `analysis_ready`, or `planner_result` events were emitted after SQL completion, so the stream stalled before chart synthesis.

## 2. Backend Control Flow
- `workflow.analytics_memory_workflow` dispatches to `PlannerExecutorFlow.events`, which derives revision targets via `planner.revision.build_revision_plan`.
- `stream_sql_lane` in `planner/sql_lane.py` persisted fresh SQL artifacts and raised `sql_ready` (if the lane ran); however, the absence of any `chart_ready` event indicates either the chart lane was skipped (`run_chart_lane == False`) or the chart tool generated no spec.

## 3. Frontend Impact
- `useAnalyticsMemoryStream` only hydrates chart UI when a `chart_ready` event arrives; without it the panel stays empty, even though SQL output is present.
- No timeout or fallback banner fired, so the user only saw table/narrative updates.

## 4. Suggested Next Diagnostics
1. Log the derived revision targets (`revision_plan.targets`) to verify the planner truly requested a chart update for this session.
2. Enable debug logging around `registry.invoke("chart_generation", …)` to capture silent failures from the chart specialist.
3. Add a frontend guardrail: if `sql_ready` arrives and no chart data follows within a short window, surface a “chart unavailable” banner instead of leaving the slot blank.

