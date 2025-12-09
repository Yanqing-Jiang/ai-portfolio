# Skill: Margins vs Peers

## Intent
Compare profit margins (gross, operating, net) for a target ticker versus peer averages.

## Triggers
- "margin", "profit margin", "vs peers", "industry average margin"

## Inputs
- `target_ticker` (required)
- `ticker_list` (peers; default standard semis)
- `metric` (gross/operating/net margin; default net)
- `years_back` (default: 5)
- `period_filter` (quarter or year)

## Outputs
- SQL computing revenue + margin %, plus peer averages
- Chart intent: line for trends; grouped bar for snapshot peer compare
- Narrative: company vs peer margin gap; improvement/decline

## Guardrails
- Only `comp_financials`; SELECT-only; limit rows ≤ 500.
- Require revenue > 0 when computing margins; null otherwise.
- Keep target separated from peer average; exclude target from peer avg.

## Chart Guidance
- Time series → line (target vs peer avg).
- Snapshot → grouped bar (target vs peer avg).
- Legend on the right; set `value_unit: "percentage"` for `generate_echarts` so data labels/axes show percentages with 1 decimal place (e.g., 12.3%). Keep labels on.

## News Hook
- If user asks for causes/why, call `get_news_sentiment` for the target ticker.

## Example Prompt Snippet
“Use Margins vs Peers skill. Target NVDA, peers default. Metric net margin. Chart = line vs peer avg. If asked for reasons, call get_news_sentiment for NVDA.”

