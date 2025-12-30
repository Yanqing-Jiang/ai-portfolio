---
name: Revenue Trend
skill_id: a2ui_revenue_trend
description: |
  Show revenue trends over time for a company.
  USE THIS SKILL WHEN the user asks:
  - "X revenue trend"
  - "How has X revenue grown?"
  - "X sales history"
  - "X quarterly/annual revenue"
  - "Show me X revenue over time"
  DO NOT USE for revenue comparisons across multiple companies.
widgets:
  - PriceChart
  - KpiCard
  - DataTable
layout: standard
---

# A2UI Skill: Revenue Trend

## Intent
Display revenue trends over time with growth metrics and quarterly/annual breakdown.

## Widget Layout (A2UI Surface Structure)

Surface: `dashboard_main`
Root: `layout_root` (Column)

```
Column (layout_root)
├── Row (header_row)
│   └── Text (title): "{ticker} Revenue Trend"
├── Row (main_content)
│   ├── Card (chart_card, weight: 2)
│   │   └── PriceChart (revenue_chart)
│   │       props: { ticker: /data/ticker, interval: "5Y" }
│   │       NOTE: Rendered as area/line chart, not candlestick
│   └── Column (kpi_column, weight: 1)
│       ├── KpiCard (latest_revenue)
│       │   props: { label: "Latest Revenue", value: /data/kpis/latest_revenue, unit: "$B" }
│       ├── KpiCard (yoy_growth)
│       │   props: { label: "YoY Growth", value: /data/kpis/yoy_growth, unit: "%", delta: /data/kpis/yoy_growth, deltaType: "percentage" }
│       └── KpiCard (cagr_5y)
│           props: { label: "5Y CAGR", value: /data/kpis/cagr, unit: "%" }
└── Card (table_card)
    └── DataTable (quarterly_data)
        props: { columns: /data/table/columns, data: /data/table/rows, sortable: true }
```

## Inputs (Slots)
- `ticker` (required): Stock symbol to analyze
- `years_back` (optional, default: 5): Number of years to show
- `period` (optional, default: "quarter"): quarter or year

## Data Model Paths

| Path | Type | Source Tool |
|------|------|-------------|
| `/data/ticker` | string | Input extraction |
| `/data/kpis/latest_revenue` | number | query_database (most recent) |
| `/data/kpis/yoy_growth` | number | Calculated: (current - prior_year) / prior_year |
| `/data/kpis/cagr` | number | Calculated: ((end/start)^(1/n) - 1) * 100 |
| `/data/chart/data` | array | query_database time series |
| `/data/table/columns` | array | [Period, Revenue, QoQ %, YoY %] |
| `/data/table/rows` | array | query_database |

## Tool Execution Sequence

1. **Extract ticker and period** from user question
   - Default: 5 years, quarterly

2. **query_database**: Get revenue time series
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

3. **Calculate KPIs**:
   - Latest revenue: Most recent value
   - YoY growth: (latest - year_ago) / year_ago * 100
   - 5Y CAGR: ((latest / 5_years_ago) ^ (1/5) - 1) * 100

4. **Format DataTable**:
   - Each row: { period, revenue, qoq_change, yoy_change }

## A2UI Message Sequence

```
1. beginRendering { surfaceId: "dashboard_main", root: "layout_root" }
2. surfaceUpdate { components: [header_row, main_content skeleton] }
3. dataModelUpdate { path: "/data/ticker", contents: [{key: "ticker", valueString: "NVDA"}] }
4. surfaceUpdate { components: [revenue_chart, kpi_column] }
5. dataModelUpdate { path: "/data/kpis", contents: [...] }
6. surfaceUpdate { components: [table_card, quarterly_data] }
7. dataModelUpdate { path: "/data/table", contents: {columns, rows} }
```

## Guardrails
- Only use `comp_financials` table
- SELECT-only queries
- Limit to 20 quarters (5 years) by default
- Revenue values in billions (divide by 1e9)
- Growth percentages with 1 decimal place

## Chart Guidance
- PriceChart styled as area chart (not candlestick) for revenue
- Y-axis: Revenue in billions with "$" prefix and "B" suffix
- DataTable sorted by period_end descending
- Positive growth shown in green, negative in red

## Example User Queries
- "NVDA revenue trend"
- "How has AMD revenue grown?"
- "Show me INTC quarterly revenue"
- "QCOM sales history over 3 years"
