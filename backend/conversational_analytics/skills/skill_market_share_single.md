---
name: Market Share (Single Company)
description: |
  Analyze market share for a semiconductor company versus peers.
  USE THIS SKILL WHEN the user asks about:
  - Market share, market position, share of market
  - How much of the market a company owns/controls
  - Competitive standing in terms of market percentage
  - Follow-ups like "show quarterly", "by quarter", "yearly breakdown" when discussing market share
  DO NOT USE for revenue comparisons without market share context.
---

# Skill: Market Share (Single Company)

## Intent
Calculate a company's market share vs the peer set for a given metric and time period.

## Inputs
- `ticker` (one ticker, required)
- `metric` (default: Revenue)
- `years_back` (default: 5)
- `period_filter` (quarter or year, required)

## Outputs
- SQL (SELECT-only) grouped by the chosen period returning `market_share_percent`
- Chart: **plot `market_share_percent` column as the Y-axis value** (NOT revenue)
- Narrative: brief explanation + highlight market share %

## Guardrails
- Only use `comp_financials`; SELECT-only; limit rows ≤ 500.
- Group by period; filter to peer tickers list.
- If no ticker given, ask for clarification.

## Chart Guidance
- **CRITICAL**: The chart must visualize `market_share_percent`, NOT raw revenue values.
- **Unit of Measure (UOM)**: percentage (%) — values range 0-100, display with 1 decimal (e.g., "23.5%").
- **Chart Title**: Must include "Market Share" (e.g., "NVDA Market Share (2020-2024)").
- **Y-axis label**: "Market Share (%)" — NOT "Revenue" or dollar amounts.
- Time series (multiple years/quarters) → line chart with `market_share_percent` on Y-axis.
- Single period comparison → horizontal bar chart with `market_share_percent`.
- When calling `generate_echarts`, set:
  - `value_unit: "percentage"` 
  - Y-axis column: `market_share_percent`
  - Title: Include "Market Share"

## News Hook
- If user asks "why" or "recent news", call `get_news_sentiment` with the ticker and surface citations.

## Example Prompt Snippet
"Use the Market Share (Single) skill. Metric=Revenue. Ticker=NVDA. Group by year. Chart the `market_share_percent` column as a line chart with Y-axis in percentage format. If user asks for news, call get_news_sentiment after the SQL."
