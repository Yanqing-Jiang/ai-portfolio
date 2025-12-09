# Skill: Market Share (Single Company)

## Intent
Calculate a company's market share vs the peer set for a given metric and time period.

## Triggers
- "market share", "market position", "share of market", "market share of NVDA/AMD/…"

## Inputs
- `ticker` (one ticker, required)
- `metric` (default: Revenue)
- `years_back` (default: 5)
- `period_filter` (quarter or year, required)

## Outputs
- SQL (SELECT-only) grouped by the chosen period
- Chart intent: bar for snapshots, line for trends
- Narrative: brief explanation + highlight market share %

## Guardrails
- Only use `comp_financials`; SELECT-only; limit rows ≤ 500.
- Group by period; filter to peer tickers list.
- If no ticker given, ask for clarification.

## Chart Guidance
- Time series → line chart; single period comparison → horizontal bar.

## News Hook
- If user asks “why” or “recent news”, call `get_news_sentiment` with the ticker and surface citations.

## Example Prompt Snippet
“Use the Market Share (Single) skill. Metric=Revenue. Ticker=NVDA. Group by year. If user asks for news, call get_news_sentiment after the SQL.”

