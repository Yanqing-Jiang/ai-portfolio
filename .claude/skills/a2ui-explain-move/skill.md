---
name: a2ui-explain-move
description: |
  Analyze why a stock price changed significantly. Use this skill when the user asks
  "Why did X drop/rise/fall/surge?", "What caused X to drop?", "Explain the X price movement",
  or "What happened to X stock?". DO NOT use for general price queries without "why" intent.
tools:
  - query_database
  - get_news_sentiment
  - generate_analysis
---

# Price Movement Analysis Skill

## Intent

Explain significant price movements for a stock by combining price data with news sentiment and AI-generated analysis.

## When to Invoke

This skill should be selected when the user:
- Asks "Why did {ticker} drop/rise/fall/surge?"
- Asks "What caused {ticker} to drop/rise?"
- Asks "Explain the {ticker} price movement"
- Asks "What happened to {ticker} stock?"
- Expresses curiosity about the reasons behind price changes

DO NOT use this skill for:
- Simple price lookup queries
- General financial data queries
- Comparison requests (use peer-compare instead)
- Margin or revenue trend analysis

## Execution Steps

### Step 1: Extract Parameters

Extract the following from the user's question:
- **ticker**: The stock symbol mentioned (required)
- **time_period**: Time range if specified (default: "1M")

### Step 2: Query Financial Database

Execute a SQL query to fetch recent financial metrics:

```sql
SELECT ticker, calendar_year, calendar_quarter_num, calendar_quarter, metric, value
FROM comp_financials
WHERE ticker = '{ticker}' AND metric IN ('Revenue', 'Net Income', 'Gross Margin')
ORDER BY calendar_year DESC, calendar_quarter_num DESC
LIMIT 24
```

### Step 3: Fetch News Sentiment

Call get_news_sentiment with:
- ticker: The extracted ticker symbol
- limit: 5 (most recent articles)

Extract from results:
- Article titles and summaries
- Sentiment scores and labels
- Publication dates
- Source URLs

### Step 4: Generate Analysis Narrative

Call generate_analysis with:
- data_summary: Summary of recent metrics and news
- key_findings: List of key observations (revenue change %, sentiment, etc.)
- trend_direction: "mixed" (or derived from data)

The analysis should explain the price movement in 2-3 sentences.

## Output Contract

The skill produces an A2UI dashboard with these components:

| Component | Type | Data Path |
|-----------|------|-----------|
| Price Chart | `PriceChart` | `/data/ticker` |
| Current Price | `KpiCard` | `/data/kpis/price` |
| Change % | `KpiCard` | `/data/kpis/change_pct` |
| Volume | `KpiCard` | `/data/kpis/volume` |
| News Timeline | `NewsTimeline` | `/data/news/events` |
| Explanation Panel | `ExplainMovePanel` | `/data/explanation` |

## Data Model Schema

```json
{
  "ticker": "string",
  "kpis": {
    "revenue": "number",
    "revenue_delta": "number",
    "net_income": "number",
    "net_income_delta": "number",
    "gross_margin": "number"
  },
  "news": {
    "events": [
      {
        "date": "string",
        "title": "string",
        "summary": "string",
        "sentiment": "string",
        "source": "string",
        "url": "string"
      }
    ]
  },
  "explanation": {
    "title": "string",
    "text": "string",
    "factors": [
      {
        "title": "string",
        "description": "string",
        "impact": "positive|negative|neutral",
        "source": "string"
      }
    ],
    "citations": [
      {
        "title": "string",
        "url": "string",
        "date": "string"
      }
    ]
  }
}
```

## Guardrails

- Only use `comp_financials` table for SQL queries
- SELECT-only queries, no mutations
- Limit news to 5 most recent items
- ExplainMovePanel MUST cite news sources
- If no news found, display "No recent news available" message

## Example Queries

- "Why did NVDA drop today?"
- "What caused AMD to rise?"
- "Explain the INTC price movement"
- "What happened to QCOM stock?"
