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

Display profit margins (gross, operating, net) for a target company, optionally compared to peer averages.

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

## Execution Steps

### Step 1: Extract Parameters

Extract the following from the user's question:
- **ticker**: Target company stock symbol (required)
- **peers**: List of peer tickers for comparison (default: NVDA, AMD, INTC, QCOM, MU, AVGO)
- **period**: "quarter" or "year" (default: "year")

### Step 2: Query Target Company Margins

Execute a SQL query to get target company margins:

```sql
SELECT ticker, 
       metric,
       value,
       period_end
FROM comp_financials
WHERE ticker = '{ticker}'
  AND metric IN ('Gross Margin', 'Operating Margin', 'Net Margin')
  AND period_type = '{period}'
ORDER BY period_end DESC
LIMIT 12
```

### Step 3: Query Peer Average Margins

Execute a SQL query to calculate peer averages:

```sql
SELECT metric,
       AVG(value) as peer_avg
FROM comp_financials
WHERE ticker IN ({peer_list})
  AND metric IN ('Gross Margin', 'Operating Margin', 'Net Margin')
  AND period_type = '{period}'
  AND period_end = (SELECT MAX(period_end) FROM comp_financials WHERE ticker = '{ticker}')
GROUP BY metric
```

### Step 4: Calculate Deltas

Compute: Target margin - Peer average for each margin type.

### Step 5: Generate Analysis

Call generate_analysis to provide insight on margin performance.

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

## Data Model Schema

```json
{
  "ticker": "NVDA",
  "tickers": ["NVDA", "AMD", "INTC"],
  "kpis": {
    "gross_margin": 64.2,
    "operating_margin": 45.1,
    "net_margin": 38.5,
    "gross_vs_peer": 12.3,
    "op_vs_peer": 20.4,
    "net_vs_peer": 15.8
  },
  "peer_count": 5,
  "table": {
    "columns": [
      {"key": "period", "label": "Period"},
      {"key": "gross", "label": "Gross %"},
      {"key": "operating", "label": "Operating %"},
      {"key": "net", "label": "Net %"}
    ],
    "rows": [...]
  },
  "chart": {
    "series": [...]
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
- Exclude target ticker from peer average calculation
- Require revenue > 0 when computing margins (null otherwise)
- Delta shows +/- percentage points vs peer average

## Chart Guidance

- KpiCard delta shows green if above peer avg, red if below
- DataTable sorted by period_end descending (most recent first)
- Percentages displayed with 1 decimal place (e.g., "45.2%")

## Example Queries

- "What are NVDA's margins?"
- "INTC profitability analysis"
- "Compare AMD gross margin to peers"
- "How profitable is QCOM vs industry?"
