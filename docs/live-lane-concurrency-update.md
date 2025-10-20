# Live Lane Concurrency Update — October 20, 2025

## Backend
- Limited the planner fan-out to the accessory lanes only (`market_question_a`, `market_question_b`, `stock_tracker`, `web_retriever`) so SQL generation remains sequential while market and web lanes run in parallel.
- Exposed the shared `MarketQuestionAdapter` in `tooling.py` and wired both the single-agent flow and the planner pipeline to use it, keeping lane metadata consistent.
- Trimmed the scheduler metadata to drop the legacy `short_financial_analysis` stage and added a regression test to assert the captured fan-out manifest in `test_planner_executor_sql.py`.

## Frontend
- Hardened `useAnalyticsMemoryStream` so `analysis_ready` only emits once per run while still refreshing progressive content, preventing duplicate Financial Analysis cards.
- Reset the new analysis-ready guard when queries start, revisions apply, or result messages reset; added a Vitest case to cover duplicate `analysis_ready` events.

## Tests
- `python -m pytest backend/tests/analytics/test_planner_executor_sql.py`
- `npx vitest run components/analytics/hooks/useAnalyticsMemoryStream.test.tsx`
