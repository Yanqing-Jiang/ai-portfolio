# Multi-Company Comparison Fixes (2025-10-22)

## Summary
- Investigated ledgers showing metric clarifications even when the user requested a two-company revenue comparison, and charts that defaulted to a single series.
- Implemented heuristic upgrades so intent detection extracts all tickers in "AMD vs NVDA" style queries, marks the comparison slot as `all`, and removes redundant clarifications.
- Extended fallback slot resolution and workflow auto-fill to reuse the heuristic comparison signal, ensuring planner execution no longer prompts for metric selection solely due to the missing comparison slot.
- Updated charting metadata to mark comparison mode, select all series by default, and surface comparison context through `meta.chartDesign`.

## Key Changes
- `backend/analytics/core/intent_impl/detection.py`: detect multiple companies per query, normalize tickers, default comparison to `all`, and strip comparison clarifications once resolved.
- `backend/analytics/core/intent_impl/models.py`: coerce ticker lists and auto-upgrade comparison to `all` when multiple tickers flow into SQL planning.
- `backend/analytics/flows/planner_executor.py`: auto-fill comparison slot during planning and expose comparison/comparison_mode in generated chart design metadata.
- `backend/analytics/core/charting.py`: propagate comparison metadata to chart specs and ensure multi-company legends start fully selected.
- Added regression coverage for comparison auto-fills and chart legend behaviour under `backend/tests/analytics/`.

## Tests
- `py -m pytest backend/tests/analytics/test_intent_slot_resolution.py backend/tests/analytics/test_chart_comparison.py`

## Follow-Ups
- Validate LLM-backed runs once the unified client is available to confirm the comparison heuristic aligns with structured resolver output.
- Review chart planning defaults for `revenue_comparison` to replace residual market-share nomenclature in meta payloads.
