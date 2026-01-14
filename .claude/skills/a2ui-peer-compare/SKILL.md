---
name: a2ui-peer-compare
description: |
  Compares revenue, stock price, or general performance across multiple companies.
  Use when the user asks "Compare X vs Y", "How does X stack up against Y?",
  "X vs Y revenue", "Side-by-side comparison of X and Y", or "Stock price comparison".
  DO NOT use for single-company analysis or margin/profitability comparisons.
---

# Peer Comparison Skill

## Intent

Compare financial metrics across 2-6 companies with overlaid charts, data tables, correlation analysis, and intelligent insights.

## When to Invoke

This skill should be selected when the user:
- Asks "Compare X vs Y" (general comparison)
- Asks "How does X stack up against Y?"
- Asks "X vs Y revenue" or "X vs Y performance"
- Asks "Side-by-side comparison of X and Y"
- Asks "Stock price comparison" or "price correlation"
- Wants to compare multiple tickers on any metric (except margins)

DO NOT use this skill for:
- Single-company analysis (use explain-move or revenue-trend)
- Margin/profitability comparisons (use margin-analysis skill)
- "X vs Y margins" or "X vs Y margin trend" → use margin-analysis

## Database Schema Reference

The `comp_financials` table contains these relevant metrics:

| Metric Name | Description | Unit |
|-------------|-------------|------|
| `Revenue` | Total revenue | USD |
| `Net Income` | Bottom-line profit | USD |
| `Gross Profit` | Revenue minus costs | USD |
| `Operating Income` | Operating profit | USD |
| `Total Assets` | Total company assets | USD |
| `Total Liabilities` | Total company liabilities | USD |

### Standard Columns
- `ticker` - Stock symbol (e.g., "AMD")
- `calendar_year` - Year (e.g., 2025)
- `calendar_quarter_num` - Quarter number (1-4)
- `calendar_quarter` - Quarter label (e.g., "Q2 2025")
- `metric` - Metric name
- `value` - Metric value

## Execution Steps

### Step 1: Extract Parameters

Extract the following from the user's question:
- **tickers**: Array of 2-6 stock symbols (required)
- **metric**: Primary metric for comparison (default: "Revenue")
- **period**: "quarter" or "year" (default: "quarter")

### Step 2: Query Financial Database

Execute a SQL query to fetch metrics for all tickers:

```sql
SELECT ticker, 
       calendar_year, 
       calendar_quarter_num, 
       calendar_quarter, 
       metric, 
       value
FROM comp_financials
WHERE ticker IN ('{ticker1}', '{ticker2}', ...)
  AND metric = '{metric}'
ORDER BY ticker, calendar_year DESC, calendar_quarter_num DESC
LIMIT 200
```

### Step 3: Process Results

For each ticker:
1. Extract time series data (period, value)
2. Calculate latest value
3. Calculate YoY change: `((latest - year_ago) / year_ago) * 100`
4. Identify leader (highest latest value)
5. Identify laggard (lowest latest value)

### Step 4: Calculate Correlation Matrix

Compute Pearson correlation between all ticker pairs:
- Values range from -1 (inverse) to 1 (perfect correlation)
- Matrix is NxN where N = number of tickers

### Step 5: Generate Dynamic Factors

Based on the actual data, generate meaningful insight factors:

```json
{
  "factors": [
    {
      "title": "{primary_ticker} Revenue",
      "description": "Latest Revenue: ${value/1e9:.2f}B ({yoy_change:+.1f}% YoY)",
      "impact": "positive" if yoy_change > 0 else "negative",
      "source": "Financial Data",
      "icon": "📊"
    },
    {
      "title": "Market Leader",
      "description": "{leader_ticker} leads the peer group in {metric}.",
      "impact": "positive" if leader == primary else "neutral",
      "source": "Peer Analysis",
      "icon": "🏆"
    },
    {
      "title": "Year-over-Year Trend",
      "description": "{primary_ticker} {metric} {'grew' if yoy > 0 else 'declined'} {abs(yoy):.1f}% YoY.",
      "impact": "positive" if yoy > 5 else "negative" if yoy < -5 else "neutral",
      "source": "Historical Analysis",
      "icon": "📈" if yoy > 0 else "📉"
    },
    {
      "title": "Correlation Analysis",
      "description": "{ticker1} and {ticker2} show {corr:.0%} correlation in {metric}.",
      "impact": "neutral",
      "source": "Statistical Analysis",
      "icon": "🔗"
    }
  ]
}
```

**CRITICAL: Do NOT use generic placeholders like:**
- "Market Conditions" 
- "Earnings & Guidance"
- "Sector Dynamics"

These must be replaced with data-driven insights.

### Step 6: Generate Follow-Up Suggestions

Based on findings, generate contextual follow-ups:

```json
{
  "follow_ups": [
    {
      "label": "Deeper on {leader}",
      "query": "Why is {leader} outperforming in {metric}?",
      "icon": "🔍",
      "category": "drill-down"
    },
    {
      "label": "Compare margins",
      "query": "Compare {ticker1} vs {ticker2} profit margins",
      "icon": "📊",
      "category": "compare"
    },
    {
      "label": "Add {related_ticker}",
      "query": "Add {related_ticker} to {ticker1} vs {ticker2} comparison",
      "icon": "➕",
      "category": "expand"
    },
    {
      "label": "5-year trend",
      "query": "Show {primary_ticker} {metric} trend over 5 years",
      "icon": "📈",
      "category": "time"
    }
  ]
}
```

## Output Contract

The skill produces an A2UI dashboard with these components:

| Component | Type | Data Path |
|-----------|------|-----------|
| Comparison Chart | `MetricChart` | `/data/chart` |
| Correlation Matrix | `CorrelationMatrix` | `/data/correlation` |
| Metrics Table | `DataTable` | `/data/table` |
| Insight Panel | `ExplainMovePanel` | `/data/explanation` |
| Follow-Ups | `FollowUpSuggestions` | `/data/follow_ups` |

## Data Model Schema

```json
{
  "tickers": ["AMD", "NVDA", "INTC"],
  "primary_ticker": "AMD",
  "metric": "Revenue",
  "kpis": {
    "primary_value": 7690000000,
    "primary_yoy": -32.0,
    "leader": "NVDA",
    "leader_value": 22100000000
  },
  "correlation": {
    "tickers": ["AMD", "NVDA", "INTC"],
    "matrix": [[1, 0.85, 0.72], [0.85, 1, 0.78], [0.72, 0.78, 1]]
  },
  "table": {
    "columns": [
      {"key": "ticker", "label": "Ticker", "type": "string"},
      {"key": "latest_value", "label": "Latest Revenue", "type": "currency"},
      {"key": "yoy_change", "label": "YoY %", "type": "percentage"}
    ],
    "rows": [
      {"ticker": "AMD", "latest_value": 7690000000, "yoy_change": -32.0},
      {"ticker": "NVDA", "latest_value": 22100000000, "yoy_change": 265.3}
    ]
  },
  "chart": {
    "series": [
      {"ticker": "AMD", "data": [{"period": "Q2 2025", "value": 7690000000}]},
      {"ticker": "NVDA", "data": [{"period": "Q2 2025", "value": 22100000000}]}
    ],
    "annotations": []
  },
  "explanation": {
    "title": "Insight: Revenue for AMD",
    "text": "AMD latest Revenue of $7.69B (down 32.0% YoY). NVDA leads peers...",
    "factors": [
      {
        "title": "AMD Revenue",
        "description": "Latest Revenue: $7.69B (-32.0% YoY)",
        "impact": "negative",
        "source": "Financial Data",
        "icon": "📊"
      },
      {
        "title": "Market Leader",
        "description": "NVDA leads the peer group in Revenue.",
        "impact": "neutral",
        "source": "Peer Analysis",
        "icon": "🏆"
      }
    ],
    "citations": []
  }
}
```

## Guardrails

- Minimum 2 tickers required; if only 1 provided, suggest adding peers
- Maximum 6 tickers for readability
- Only use `comp_financials` table
- SELECT-only queries
- Correlation values must be -1 to 1
- Handle null/missing values gracefully (display "N/A")

## Example Queries

- "Compare AMD vs INTC"
- "How does NVDA stack up against AMD and QCOM?"
- "Side-by-side INTC vs AMD vs NVDA revenue"
- "Compare semiconductor companies"
