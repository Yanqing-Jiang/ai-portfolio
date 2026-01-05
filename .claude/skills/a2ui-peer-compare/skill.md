---
name: a2ui-peer-compare
description: |
  Compare revenue, stock price, or general performance across multiple companies.
  Use this skill when the user asks "Compare X vs Y", "How does X stack up against Y?",
  "X vs Y revenue", "Side-by-side comparison of X and Y", or "Stock price comparison".
  DO NOT use for single-company analysis or margin/profitability comparisons.
tools:
  - query_database
  - generate_analysis
---

# Peer Comparison Skill

## Intent

Compare financial metrics across 2-6 companies with overlaid charts, data tables, and correlation analysis.

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

## Execution Steps

### Step 1: Extract Parameters

Extract the following from the user's question:
- **tickers**: Array of 2-6 stock symbols (required)
- **metric**: Primary metric for comparison (default: "Revenue")
- **period**: "quarter" or "year" (default: "year")

### Step 2: Query Financial Database

Execute a SQL query to fetch metrics for all tickers:

```sql
SELECT ticker, metric, value, period_end,
       LAG(value) OVER (PARTITION BY ticker ORDER BY period_end) as prev_value
FROM comp_financials
WHERE ticker IN ({tickers_list})
  AND metric = '{metric}'
  AND period_type = '{period}'
ORDER BY ticker, period_end DESC
LIMIT 100
```

### Step 3: Calculate Correlation Matrix

Compute price/metric correlations between all tickers:
- Generate NxN matrix where N = number of tickers
- Values range from -1 (inverse correlation) to 1 (perfect correlation)

### Step 4: Format DataTable Rows

Build comparison table with:
- Each row: { ticker, latest_value, yoy_change_pct }
- Columns: [Ticker, {Metric}, YoY Change]

### Step 5: Generate Analysis (Optional)

Call generate_analysis to provide insight on the comparison.

## Output Contract

The skill produces an A2UI dashboard with these components:

| Component | Type | Data Path |
|-----------|------|-----------|
| Price Chart | `PriceChart` | `/data/primary_ticker`, `/data/tickers` |
| Correlation Matrix | `CorrelationMatrix` | `/data/correlation` |
| Metrics Table | `DataTable` | `/data/table` |
| Explanation Panel | `PeerComparePanel` | `/data/explanation` |

## Data Model Schema

```json
{
  "tickers": ["AMD", "INTC", "NVDA"],
  "primary_ticker": "AMD",
  "metric": "Revenue",
  "kpis": {
    "leader": "string",
    "leader_value": "number",
    "avg_growth": "number"
  },
  "correlation": {
    "tickers": ["AMD", "INTC", "NVDA"],
    "matrix": [[1, 0.85, 0.92], [0.85, 1, 0.78], [0.92, 0.78, 1]]
  },
  "table": {
    "columns": [
      {"key": "ticker", "label": "Ticker"},
      {"key": "value", "label": "Revenue ($B)"},
      {"key": "yoy_change", "label": "YoY Change"}
    ],
    "rows": [
      {"ticker": "AMD", "value": 5.6, "yoy_change": "+15.2%"},
      {"ticker": "INTC", "value": 14.2, "yoy_change": "-8.1%"}
    ]
  },
  "chart": {
    "series": [
      {"ticker": "AMD", "data": [...]},
      {"ticker": "INTC", "data": [...]}
    ]
  },
  "explanation": {
    "title": "string",
    "text": "string",
    "factors": [],
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

## Example Queries

- "Compare AMD vs INTC"
- "How does NVDA stack up against AMD and QCOM?"
- "Side-by-side INTC vs AMD vs NVDA revenue"
- "Compare semiconductor companies"
