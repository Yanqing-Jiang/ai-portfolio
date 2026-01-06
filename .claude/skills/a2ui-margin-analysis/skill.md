---
name: a2ui-margin-analysis
description: |
  Analyze profit margins (gross, operating, net) for one or more companies.
  Use this skill when the user asks about margins, profitability, "What are X's margins?",
  "X profitability analysis", "Gross/operating/net margin for X", "How profitable is X?",
  or margin-focused comparisons like "X vs Y margins" or "Compare margins for X and Y".
  DO NOT use for revenue comparisons without margin context or stock price comparisons.
tools:
  - query_database
  - generate_analysis
---

# Margin Analysis Skill

## Intent

Display profit margins (gross, operating, net) for a target company, with intelligent insights based on actual data.

## When to Invoke

This skill should be selected when the user:
- Asks "What are X's margins?"
- Asks "X profitability analysis"
- Asks "Gross/operating/net margin for X"
- Asks "How profitable is X compared to peers?"
- Asks "X margin vs industry average"
- Asks "X vs Y margins" or "X vs Y margin trend"
- Asks "Compare margins for X and Y"
- Asks "X vs Y profitability"

DO NOT use this skill for:
- Revenue comparisons without margin context
- Stock price comparisons
- General "compare X vs Y" without margin/profitability keywords

## Database Schema Reference

The `comp_financials` table contains these metrics for margin calculations:

| Metric Name | Description | Unit |
|-------------|-------------|------|
| `Revenue` | Total revenue | USD |
| `Net Income` | Bottom-line profit | USD |
| `Gross Profit` | Revenue minus Cost of Revenue | USD |
| `Operating Income` | Operating profit | USD |
| `Cost of Revenue` | Direct costs of goods sold | USD |
| `Gross Margin` | Gross profit as % of revenue (if directly available) | % |
| `Operating Margin` | Operating income as % of revenue (if directly available) | % |

### Margin Calculation Formulas

When direct margin percentages are not available, calculate from components:

```
Gross Margin = (Gross Profit / Revenue) × 100
            OR ((Revenue - Cost of Revenue) / Revenue) × 100

Operating Margin = (Operating Income / Revenue) × 100

Net Margin = (Net Income / Revenue) × 100
```

## Execution Steps

### Step 1: Extract Parameters

Extract the following from the user's question:
- **ticker**: Target company stock symbol (required)
- **peers**: List of peer tickers for comparison (optional)
- **period**: "quarter" or "year" (default: "quarter")

### Step 2: Query Financial Database

Execute a SQL query to fetch ALL margin-related metrics:

```sql
SELECT ticker, 
       calendar_year,
       calendar_quarter_num,
       calendar_quarter,
       metric, 
       value
FROM comp_financials
WHERE ticker = '{ticker}'
  AND metric IN ('Revenue', 'Net Income', 'Gross Profit', 
                 'Operating Income', 'Cost of Revenue',
                 'Gross Margin', 'Operating Margin')
ORDER BY calendar_year DESC, calendar_quarter_num DESC
LIMIT 80
```

### Step 3: Calculate Margins

For each period:
1. Try to use direct `Gross Margin` / `Operating Margin` values if available
2. Otherwise calculate: `(Gross Profit / Revenue) × 100`
3. Or calculate: `((Revenue - Cost of Revenue) / Revenue) × 100`
4. Always calculate Net Margin: `(Net Income / Revenue) × 100`

### Step 4: Generate Dynamic Factors

Based on the actual margin data, generate 3-4 insight factors:

**Factor Examples (based on real data):**
```json
{
  "factors": [
    {
      "title": "Gross Margin",
      "description": "{ticker} gross margin of {value:.1f}% indicates cost efficiency.",
      "impact": "positive" if value > 40 else "neutral" if value > 20 else "negative",
      "source": "Profitability Analysis",
      "icon": "💰"
    },
    {
      "title": "Net Profitability",
      "description": "Net margin of {value:.1f}% shows bottom-line profitability.",
      "impact": "positive" if value > 10 else "neutral" if value > 0 else "negative",
      "source": "Profitability Analysis",
      "icon": "📈"
    },
    {
      "title": "Operating Efficiency",
      "description": "Operating margin of {value:.1f}% reflects operational control.",
      "impact": "positive" if value > 20 else "neutral",
      "source": "Profitability Analysis",
      "icon": "⚙️"
    }
  ]
}
```

**DO NOT use generic placeholders like:**
- "Market Conditions"
- "Earnings & Guidance"
- "Sector Dynamics"

### Step 5: Generate Follow-Up Suggestions

Based on the analysis, generate contextual follow-up questions:

```json
{
  "follow_ups": [
    {
      "label": "Revenue breakdown",
      "query": "Show {ticker} revenue trend over 3 years",
      "icon": "📊",
      "category": "drill-down"
    },
    {
      "label": "Compare margins",
      "query": "Compare {ticker} margins to {peer1} and {peer2}",
      "icon": "📈",
      "category": "compare"
    },
    {
      "label": "Cost analysis",
      "query": "Why did {ticker} operating margin change?",
      "icon": "💵",
      "category": "explain"
    }
  ]
}
```

## Output Contract

The skill produces an A2UI dashboard with these components:

| Component | Type | Data Path |
|-----------|------|-----------|
| Gross Margin | `KpiCard` | `/data/kpis/gross_margin` |
| Operating Margin | `KpiCard` | `/data/kpis/operating_margin` |
| Net Margin | `KpiCard` | `/data/kpis/net_margin` |
| Margin History | `DataTable` | `/data/table` |
| Margin Chart | `MetricChart` | `/data/chart` |
| Explanation | `ExplainMovePanel` | `/data/explanation` |
| Follow-Ups | `FollowUpSuggestions` | `/data/follow_ups` |

## Data Model Schema

```json
{
  "ticker": "AMD",
  "tickers": ["AMD"],
  "kpis": {
    "gross_margin": 88.4,
    "operating_margin": 8.7,
    "net_margin": 20.5
  },
  "table": {
    "columns": [
      {"key": "period", "label": "Period", "type": "string"},
      {"key": "gross_margin", "label": "Gross Margin", "type": "percentage"},
      {"key": "operating_margin", "label": "Operating Margin", "type": "percentage"},
      {"key": "net_margin", "label": "Net Margin", "type": "percentage"}
    ],
    "rows": [
      {"period": "Q2 2025", "gross_margin": 88.4, "operating_margin": 8.7, "net_margin": 20.5}
    ]
  },
  "chart": {
    "series": [
      {"ticker": "Gross Margin", "data": [{"period": "Q2 2025", "value": 88.4}]},
      {"ticker": "Operating Margin", "data": [{"period": "Q2 2025", "value": 8.7}]},
      {"ticker": "Net Margin", "data": [{"period": "Q2 2025", "value": 20.5}]}
    ],
    "annotations": []
  },
  "explanation": {
    "title": "Insight: Margins for AMD",
    "text": "AMD demonstrates strong profitability with gross margin of 88.4%...",
    "factors": [
      {
        "title": "Gross Margin",
        "description": "AMD gross margin of 88.4% indicates excellent cost efficiency.",
        "impact": "positive",
        "source": "Profitability Analysis",
        "icon": "💰"
      }
    ],
    "citations": []
  }
}
```

## Guardrails

- Only use `comp_financials` table
- SELECT-only queries
- Always calculate margins when direct values unavailable
- Handle zero revenue (set margin to null/N/A)
- Percentages displayed with 1 decimal place (e.g., "45.2%")

## Example Queries

- "What are AMD's margins?"
- "NVDA profitability analysis"
- "Compare AMD gross margin to NVDA"
- "How profitable is QCOM?"
