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

Explain significant price movements for a stock by combining financial data with news sentiment and AI-generated analysis.

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

## Database Schema Reference

The `comp_financials` table contains these relevant metrics:

| Metric Name | Description | Unit |
|-------------|-------------|------|
| `Revenue` | Total revenue | USD |
| `Net Income` | Bottom-line profit | USD |
| `Gross Margin` | Gross profit as % of revenue | % |
| `Operating Income` | Operating profit | USD |
| `EPS` | Earnings per share | USD |

### Standard Columns
- `ticker` - Stock symbol
- `calendar_year` - Year
- `calendar_quarter_num` - Quarter number (1-4)
- `calendar_quarter` - Quarter label (e.g., "Q2 2025")
- `metric` - Metric name
- `value` - Metric value

## Execution Steps

### Step 1: Extract Parameters

Extract the following from the user's question:
- **ticker**: The stock symbol mentioned (required)
- **time_period**: Time range if specified (default: "1M")

### Step 2: Query Financial Database

Execute a SQL query to fetch recent financial metrics:

```sql
SELECT ticker, 
       calendar_year, 
       calendar_quarter_num, 
       calendar_quarter, 
       metric, 
       value
FROM comp_financials
WHERE ticker = '{ticker}' 
  AND metric IN ('Revenue', 'Net Income', 'Gross Margin', 'EPS')
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

### Step 4: Generate Dynamic Factors

Based on financial data AND news, create meaningful factors:

```json
{
  "factors": [
    {
      "title": "Revenue Performance",
      "description": "{ticker} Q2 revenue of ${value/1e9:.2f}B ({yoy_change:+.1f}% YoY)",
      "impact": "positive" if yoy_change > 0 else "negative",
      "source": "Earnings Report",
      "icon": "📊"
    },
    {
      "title": "Earnings Impact",
      "description": "Net income {'beat' if beat else 'missed'} expectations by {delta:.1f}%",
      "impact": "positive" if beat else "negative",
      "source": "Earnings Analysis",
      "icon": "💰"
    },
    {
      "title": "News Sentiment",
      "description": "Recent news shows {sentiment} sentiment: \"{headline}\"",
      "impact": sentiment_to_impact(sentiment),
      "source": news_source,
      "icon": "📰"
    },
    {
      "title": "Market Reaction",
      "description": "Stock {'gained' if up else 'declined'} {abs(change):.1f}% following announcements",
      "impact": "positive" if up else "negative",
      "source": "Price Action",
      "icon": "📈" if up else "📉"
    }
  ]
}
```

**CRITICAL: Factors must be derived from actual data. DO NOT use:**
- "Market Conditions" (unless citing specific market event)
- "Earnings & Guidance" (unless citing specific earnings data)
- "Sector Dynamics" (unless comparing to sector metrics)

### Step 5: Generate Follow-Up Suggestions

```json
{
  "follow_ups": [
    {
      "label": "Revenue trend",
      "query": "Show {ticker} revenue trend over 2 years",
      "icon": "📊",
      "category": "drill-down"
    },
    {
      "label": "Compare to peers",
      "query": "How does {ticker} compare to {peer1} and {peer2}?",
      "icon": "📈",
      "category": "compare"
    },
    {
      "label": "Margin analysis",
      "query": "What are {ticker}'s profit margins?",
      "icon": "💵",
      "category": "related"
    }
  ]
}
```

## Output Contract

The skill produces an A2UI dashboard with these components:

| Component | Type | Data Path |
|-----------|------|-----------|
| Price Chart | `PriceChart` | `/data/ticker` |
| Revenue KPI | `KpiCard` | `/data/kpis/revenue` |
| Revenue Change | `KpiCard` | `/data/kpis/revenue_delta` |
| Net Income | `KpiCard` | `/data/kpis/net_income` |
| News Timeline | `NewsTimeline` | `/data/news/events` |
| Explanation Panel | `ExplainMovePanel` | `/data/explanation` |
| Follow-Ups | `FollowUpSuggestions` | `/data/follow_ups` |

## Data Model Schema

```json
{
  "ticker": "NVDA",
  "kpis": {
    "revenue": 22100000000,
    "revenue_delta": 265.3,
    "net_income": 12900000000,
    "net_income_delta": 580.0,
    "gross_margin": 74.5
  },
  "news": {
    "events": [
      {
        "date": "2025-05-28",
        "title": "NVIDIA Reports Record Q2 Revenue",
        "summary": "NVIDIA announced quarterly revenue of $22.1B...",
        "sentiment": "positive",
        "source": "Reuters",
        "url": "https://reuters.com/..."
      }
    ]
  },
  "explanation": {
    "title": "Why NVDA Rose",
    "text": "NVIDIA stock surged following Q2 earnings that beat expectations...",
    "factors": [
      {
        "title": "Revenue Performance",
        "description": "Q2 revenue of $22.1B (+265% YoY) exceeded analyst estimates.",
        "impact": "positive",
        "source": "Earnings Report",
        "icon": "📊"
      },
      {
        "title": "AI Demand Surge",
        "description": "Data center revenue up 171% driven by AI chip demand.",
        "impact": "positive",
        "source": "Segment Analysis",
        "icon": "🤖"
      }
    ],
    "citations": [
      {
        "title": "NVIDIA Reports Record Q2 Revenue",
        "url": "https://reuters.com/...",
        "date": "2025-05-28"
      }
    ]
  }
}
```

## Guardrails

- Only use `comp_financials` table for SQL queries
- SELECT-only queries, no mutations
- Limit news to 5 most recent items
- ExplainMovePanel MUST cite news sources when available
- If no news found, display "No recent news available" but still show financial factors
- All factors must reference actual data values

## Example Queries

- "Why did NVDA drop today?"
- "What caused AMD to rise?"
- "Explain the INTC price movement"
- "What happened to QCOM stock?"
