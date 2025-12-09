# Skill: Margin Growth vs Peers

## Intent
Track margin expansion/contraction (percentage points) and compare to peer average.

## Triggers
- "margin growth", "change in margin", "margin expansion", "vs peers"

## Inputs
- `target_ticker` (required)
- `ticker_list` (peers; default standard semis)
- `metric` (gross/operating/net margin; default net)
- `years_back` (default: 5)
- `period_filter` (quarter or year)

## Outputs
- SQL computing margin growth (delta vs prior period) and peer-average growth
- Chart intent: line showing target vs peer growth (pp)
- Narrative: direction, magnitude, divergence from peers

## Guardrails
- Only `comp_financials`; SELECT-only; limit rows ≤ 500.
- Use lag(1) for period-over-period growth; ensure revenue > 0 first.
- Exclude target from peer average calculation.

## Chart Guidance
- Line chart; x-axis = period; y-axis = margin growth (pp).
- Legend on the right; use `value_unit: "percentage"` so the chart shows data labels/axes in percentage points with one decimal place (e.g., -1.2%).

## News Hook
- If large swings or user asks “why,” call `get_news_sentiment` for target ticker.

## Example Prompt Snippet
“Use Margin Growth vs Peers skill. Target AMD. Metric operating margin. Chart = line of pp change vs peer avg. If notable swing, call get_news_sentiment for AMD.”

