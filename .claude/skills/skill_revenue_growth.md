---
name: revenue_growth
description: |
  Calculate and visualize revenue growth rates (YoY and/or QoQ) for semiconductor companies.
  
  USE THIS SKILL WHEN the user asks about:
  - Revenue growth, growth rate, YoY growth, QoQ growth
  - Year-over-year or quarter-over-quarter revenue changes
  - Growth trends, which company is growing fastest
  - Growth vs peers, growth comparison
  
  DO NOT USE for:
  - Absolute revenue comparisons without growth context (use revenue_comparison)
  - Market share analysis (use market_share_single)
  - Margin analysis (use margins_vs_peers)
tools:
  - query_database
  - generate_echarts
  - generate_analysis
  - get_news_sentiment
---

# Skill: Revenue Growth (YoY / QoQ)

## Intent
Compute revenue growth rates (YoY and/or QoQ) for peer tickers.

## Triggers
- "revenue growth", "growth rate", "growth vs peers", "yoy growth", "qoq growth"

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
- If sharp changes or user asks “why”, call `get_news_sentiment` for the primary ticker(s).

## Example Prompt Snippet
“Use Revenue Growth skill. Peer set NVDA, AMD, AVGO. Quarterly growth with YoY % column. Chart = line. If user asks why, call get_news_sentiment for NVDA.”

