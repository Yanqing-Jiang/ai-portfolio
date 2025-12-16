---
name: Revenue Comparison (Peers)
description: |
  Compare revenue across multiple semiconductor companies over time.
  USE THIS SKILL WHEN the user asks about:
  - Revenue comparison between companies (e.g., "compare NVDA vs AMD revenue")
  - Revenue trends across peers, revenue vs, revenue between tickers
  - Side-by-side revenue analysis for multiple companies
  - Follow-ups like "add INTC", "show quarterly", "last 3 years" when comparing revenue
  DO NOT USE for single-company market share analysis.
---

# Skill: Revenue Comparison (Peers)

## Intent
Compare revenue totals across selected peer tickers over a time period.

## Inputs
- `ticker_list` (2-6 tickers; default peer set if missing, required)
- `years_back` (default: 5)
- `period_filter` (quarter or year, required)

## Outputs
- SQL (SELECT-only) grouping by period and ticker
- Chart intent: multi-series line for trends; grouped bar for single period snapshots
- Narrative: call out leaders, laggards, and range

## Guardrails
- Only `comp_financials`; SELECT-only; limit rows ≤ 500.
- Require ≥2 tickers; if missing, ask for clarification.
- Use consistent period grouping (quarter/year) and ordering.

## Chart Guidance
- Time series → multi-line.
- Single period snapshot → grouped bar.
- Always place the legend on the right.
- **UOM (Unit of Measure) Formatting:**
  - Set `value_unit: "millions_usd"` in `value_meta` when calling `generate_echarts`.
  - This tells the frontend to format y-axis, data labels, and tooltips with `$` prefix and `M` suffix.
  - Example: `10670` → `$10,670.0M` or `$10.7B` depending on scale.
  - Always enable data labels (`label: { show: true }`) for readability.
- **Axis Formatting:**
  - The y-axis should show abbreviated values (e.g., `$10B`, `$50B`) for large numbers.
  - Use `axisLabel.formatter` to apply scaling (divide by 1,000,000 for millions).
  - Include the unit in the axis name: `yAxis.name: "Revenue (Millions USD)"`.
- **Tooltip Formatting:**
  - Tooltips should show full formatted values with currency and unit.
  - Include ticker name and period in tooltip for clarity.

## News Hook
- If user asks for context/why, call `get_news_sentiment` for the top 1–2 tickers mentioned.

## Example Prompt Snippet
"Use Revenue Comparison skill. Tickers: NVDA, AMD, INTC. Period: yearly. Provide chart intent (line). If user asks for reasons, call get_news_sentiment for NVDA and AMD."
