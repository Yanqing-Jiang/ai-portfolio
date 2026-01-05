---
name: a2ui-revenue-trend
description: |
  Show revenue trends over time for a company.
  Use this skill when the user asks "X revenue trend", "How has X revenue grown?",
  "X sales history", "X quarterly/annual revenue", or "Show me X revenue over time".
  DO NOT use for revenue comparisons across multiple companies - use peer-compare instead.
tools:
  - query_database
  - generate_analysis
---

# Revenue Trend Skill

## Intent

Display revenue trends over time with growth metrics and quarterly/annual breakdown.

## When to Invoke

This skill should be selected when the user:
- Asks "X revenue trend"
- Asks "How has X revenue grown?"
- Asks "X sales history"
- Asks "X quarterly/annual revenue"
- Asks "Show me X revenue over time"
- Wants to see historical revenue data for a single company

DO NOT use this skill for:
- Revenue comparisons across multiple companies (use peer-compare)
- Margin analysis (use margin-analysis)
- Price movement explanations (use explain-move)

## Execution Steps

### Step 1: Extract Parameters

Extract the following from the user's question:
- **ticker**: Stock symbol to analyze (required)
- **years_back**: Number of years to show (default: 5)
- **period**: "quarter" or "year" (default: "quarter")

### Step 2: Query Revenue Time Series

Execute a SQL query to get revenue history:

```sql
SELECT ticker,
       period_end,
       value as revenue,
       LAG(value, 1) OVER (ORDER BY period_end) as prev_quarter,
       LAG(value, 4) OVER (ORDER BY period_end) as prev_year
FROM comp_financials
WHERE ticker = '{ticker}'
  AND metric = 'Revenue'
  AND period_type = '{period}'
  AND period_end >= DATE_SUB(CURRENT_DATE, INTERVAL {years_back} YEAR)
ORDER BY period_end ASC
```

### Step 3: Calculate KPIs

Compute the following metrics:
- **Latest revenue**: Most recent value
- **YoY growth**: (latest - year_ago) / year_ago * 100
- **5Y CAGR**: ((latest / 5_years_ago) ^ (1/5) - 1) * 100

### Step 4: Format DataTable

Build rows with: { period, revenue, qoq_change, yoy_change }

### Step 5: Generate Analysis

Call generate_analysis to provide trend insights.

## Output Contract

The skill produces an A2UI dashboard with these components:

| Component | Type | Data Path |
|-----------|------|-----------|
| Revenue Chart | `MetricChart` | `/data/chart` |
| Latest Revenue | `KpiCard` | `/data/kpis/latest_revenue` |
| YoY Growth | `KpiCard` | `/data/kpis/yoy_growth` |
| 5Y CAGR | `KpiCard` | `/data/kpis/cagr` |
| Quarterly Data | `DataTable` | `/data/table` |
| Explanation | `ExplainMovePanel` | `/data/explanation` |

## Data Model Schema

```json
{
  "ticker": "NVDA",
  "kpis": {
    "latest_revenue": 22.1,
    "yoy_growth": 265.3,
    "cagr": 42.8
  },
  "chart": {
    "series": [
      {
        "name": "Revenue",
        "data": [
          {"period": "Q1 2024", "value": 22.1},
          {"period": "Q4 2023", "value": 18.1}
        ]
      }
    ],
    "annotations": []
  },
  "table": {
    "columns": [
      {"key": "period", "label": "Period"},
      {"key": "revenue", "label": "Revenue ($B)"},
      {"key": "qoq_change", "label": "QoQ %"},
      {"key": "yoy_change", "label": "YoY %"}
    ],
    "rows": [...]
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

- Only use `comp_financials` table
- SELECT-only queries
- Limit to 20 quarters (5 years) by default
- Revenue values in billions (divide by 1e9)
- Growth percentages with 1 decimal place

## Chart Guidance

- MetricChart styled as area chart for revenue
- Y-axis: Revenue in billions with "$" prefix and "B" suffix
- DataTable sorted by period_end descending
- Positive growth shown in green, negative in red

## Example Queries

- "NVDA revenue trend"
- "How has AMD revenue grown?"
- "Show me INTC quarterly revenue"
- "QCOM sales history over 3 years"
