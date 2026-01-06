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

Display revenue trends over time with growth metrics, quarterly/annual breakdown, and intelligent insights based on actual financial data.

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

## Database Schema Reference

The `comp_financials` table contains:

| Metric Name | Description | Unit |
|-------------|-------------|------|
| `Revenue` | Total revenue | USD |
| `Net Income` | Bottom-line profit | USD |
| `Gross Profit` | Revenue minus costs | USD |

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
- **ticker**: Stock symbol to analyze (required)
- **years_back**: Number of years to show (default: 5)
- **period**: "quarter" or "year" (default: "quarter")

### Step 2: Query Revenue Time Series

Execute a SQL query to get revenue history:

```sql
SELECT ticker,
       calendar_year,
       calendar_quarter_num,
       calendar_quarter,
       metric,
       value
FROM comp_financials
WHERE ticker = '{ticker}'
  AND metric = 'Revenue'
ORDER BY calendar_year DESC, calendar_quarter_num DESC
LIMIT 40
```

### Step 3: Calculate KPIs

Compute the following metrics:
- **Latest revenue**: Most recent value
- **YoY growth**: `((latest - year_ago) / year_ago) * 100`
- **QoQ growth**: `((latest - prev_quarter) / prev_quarter) * 100`
- **5Y CAGR**: `((latest / 5_years_ago) ^ (1/5) - 1) * 100`

### Step 4: Generate Dynamic Factors

Based on the actual revenue data, generate meaningful factors:

```json
{
  "factors": [
    {
      "title": "{ticker} Revenue",
      "description": "Latest quarterly revenue of ${value/1e9:.2f}B ({yoy_change:+.1f}% YoY)",
      "impact": "positive" if yoy_change > 5 else "negative" if yoy_change < -5 else "neutral",
      "source": "Financial Data",
      "icon": "📊"
    },
    {
      "title": "Growth Trajectory",
      "description": "Revenue has {'grown' if cagr > 0 else 'declined'} at {abs(cagr):.1f}% CAGR over 5 years",
      "impact": "positive" if cagr > 10 else "neutral" if cagr > 0 else "negative",
      "source": "Historical Analysis",
      "icon": "📈" if cagr > 0 else "📉"
    },
    {
      "title": "Quarterly Momentum",
      "description": "QoQ change of {qoq_change:+.1f}% shows {'acceleration' if qoq > 0 else 'slowdown'}",
      "impact": "positive" if qoq_change > 0 else "negative",
      "source": "Trend Analysis",
      "icon": "⚡"
    },
    {
      "title": "Scale",
      "description": "{ticker} is a ${annual_revenue/1e9:.0f}B annual revenue company",
      "impact": "neutral",
      "source": "Company Profile",
      "icon": "🏢"
    }
  ]
}
```

**CRITICAL: Generate factors based on ACTUAL calculated values. DO NOT use:**
- Generic "Market Conditions"
- Placeholder "Earnings & Guidance"
- Vague "Sector Dynamics"

### Step 5: Generate Follow-Up Suggestions

Based on the revenue analysis, suggest related queries:

```json
{
  "follow_ups": [
    {
      "label": "Profitability",
      "query": "What are {ticker}'s profit margins?",
      "icon": "💰",
      "category": "related"
    },
    {
      "label": "Compare to peers",
      "query": "Compare {ticker} revenue to {peer1} and {peer2}",
      "icon": "📊",
      "category": "compare"
    },
    {
      "label": "Segment breakdown",
      "query": "What drives {ticker}'s revenue growth?",
      "icon": "🔍",
      "category": "drill-down"
    },
    {
      "label": "10-year view",
      "query": "Show {ticker} revenue over 10 years",
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
| Revenue Chart | `MetricChart` | `/data/chart` |
| Latest Revenue | `KpiCard` | `/data/kpis/latest_revenue` |
| YoY Growth | `KpiCard` | `/data/kpis/yoy_growth` |
| 5Y CAGR | `KpiCard` | `/data/kpis/cagr` |
| Quarterly Data | `DataTable` | `/data/table` |
| Explanation | `ExplainMovePanel` | `/data/explanation` |
| Follow-Ups | `FollowUpSuggestions` | `/data/follow_ups` |

## Data Model Schema

```json
{
  "ticker": "NVDA",
  "kpis": {
    "latest_revenue": 22100000000,
    "yoy_growth": 265.3,
    "qoq_growth": 18.0,
    "cagr": 42.8
  },
  "chart": {
    "series": [
      {
        "ticker": "NVDA",
        "data": [
          {"period": "Q2 2025", "value": 22100000000},
          {"period": "Q1 2025", "value": 18720000000},
          {"period": "Q4 2024", "value": 22103000000}
        ]
      }
    ],
    "annotations": [
      {"period": "Q2 2025", "ticker": "NVDA", "label": "Record Revenue", "details": "Beat analyst estimates"}
    ]
  },
  "table": {
    "columns": [
      {"key": "period", "label": "Period", "type": "string"},
      {"key": "revenue", "label": "Revenue ($B)", "type": "currency"},
      {"key": "qoq_change", "label": "QoQ %", "type": "percentage"},
      {"key": "yoy_change", "label": "YoY %", "type": "percentage"}
    ],
    "rows": [
      {"period": "Q2 2025", "revenue": 22100000000, "qoq_change": 18.0, "yoy_change": 265.3}
    ]
  },
  "explanation": {
    "title": "Insight: Revenue for NVDA",
    "text": "NVIDIA's revenue reached $22.1B in Q2 2025, up 265% YoY driven by AI chip demand...",
    "factors": [
      {
        "title": "NVDA Revenue",
        "description": "Latest quarterly revenue of $22.1B (+265.3% YoY)",
        "impact": "positive",
        "source": "Financial Data",
        "icon": "📊"
      },
      {
        "title": "Growth Trajectory",
        "description": "Revenue has grown at 42.8% CAGR over 5 years",
        "impact": "positive",
        "source": "Historical Analysis",
        "icon": "📈"
      }
    ],
    "citations": []
  }
}
```

## Guardrails

- Only use `comp_financials` table
- SELECT-only queries
- Limit to 20 quarters (5 years) by default
- Revenue values in billions (divide by 1e9 for display)
- Growth percentages with 1 decimal place
- Handle missing periods gracefully (skip in calculations)

## Chart Guidance

- MetricChart styled as area chart for revenue
- Y-axis: Revenue in billions with "$" prefix and "B" suffix
- DataTable sorted by period descending (most recent first)
- Positive growth shown in green, negative in red
- Add news annotations where relevant

## Example Queries

- "NVDA revenue trend"
- "How has AMD revenue grown?"
- "Show me INTC quarterly revenue"
- "QCOM sales history over 3 years"
