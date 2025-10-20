# Stock Follow-Up and Live Streaming Changes

## Frontend
- Restyled the live status bubble in `ChatHistory` so it anchors on the left, drops the robot icon, and stays near the next robot card while results stream.
- Replaced the green LiveArtifacts container with production-style cards (chart, analysis, stock, market research, SQL, specialist spotlight) so live outputs render directly.
- Hardened `useAnalyticsMemoryStream` to deduplicate revision snapshots, surface custom clarification echoes (including timeframe free text), and reset status copy cleanly when runs close.
- Updated LiveArtifacts and hook vitest suites to cover the new layout, deduping logic, and timeframe presets.

## Backend
- Swapped default timeframe presets to `last 5 years`, `last 2 years`, `last 8 quarters`, and `year to date`; refreshed slot catalog, metrics config, and associated tests.
- Added quarterly coercion for clarification answers targeting multi-year windows (e.g., "last 2 years").
- Enhanced `PlannerExecutorFlow` stock-only follow-ups to reuse SQL/analysis, refresh the stock widget, emit reused analysis events, and short-circuit with a planner summary.
- Introduced helpers that convert stored analysis artifacts into reuse payloads plus regression tests for timeframe merging and cached analysis emission.

## Tests
- `pytest backend/tests/analytics/test_clarify_timeframe.py backend/tests/analytics/test_planner_executor_sql.py`
- `npx vitest run components/analytics/hooks/useAnalyticsMemoryStream.test.tsx components/analytics/memory/LiveArtifacts.test.tsx`
