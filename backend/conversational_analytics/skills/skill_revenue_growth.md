---
name: Revenue Growth (YoY/QoQ)
description: |
  Calculate and visualize revenue growth rates for semiconductor companies.
  USE THIS SKILL WHEN the user asks about:
  - Revenue growth, growth rate, YoY growth, QoQ growth
  - Year-over-year or quarter-over-quarter revenue changes
  - Growth trends, growth vs peers, which company is growing fastest
  - Follow-ups like "show QoQ instead", "last 8 quarters" when discussing growth
  DO NOT USE for absolute revenue comparisons (use Revenue Comparison instead).
---

# Skill: Revenue Growth (YoY / QoQ)

## Intent
Compute revenue growth rates (YoY and/or QoQ) for peer tickers.

## Inputs
- `ticker_list` (single or 2+ tickers, required)
- `years_back` (default: 5)
- `period_filter` (quarter; supports YoY with lag 4, required)

## Outputs
- SQL with growth calculations (lag-based) and a growth % column
- Chart intent: line chart (time series growth)
- Narrative: top movers, negative prints, volatility notes
- **value_unit:** `percentage` (frontend will format y-axis/labels/tooltips as %, auto-converting ratios)

## Guardrails
- Only `comp_financials`; SELECT-only; limit rows ≤ 500.
- Ensure growth uses correct lag (4 for YoY when quarterly).
- Keep null-safe division; avoid divide-by-zero.

## Chart Guidance
- Always line for growth over time; x-axis = period; y-axis = growth %.
- Encode `value_unit: "percentage"` and include `value_meta` so the frontend renders % labels (1 decimal) and converts ratios when needed.

## News Hook
- If sharp changes or user asks "why", call `get_news_sentiment` for the primary ticker(s).

## Example Prompt Snippet
"Use Revenue Growth skill. Peer set NVDA, AMD, AVGO. Quarterly growth with YoY % column. Chart = line. If user asks why, call get_news_sentiment for NVDA."
