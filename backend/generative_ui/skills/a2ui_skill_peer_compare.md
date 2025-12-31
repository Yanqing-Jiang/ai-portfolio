---
name: Peer Comparison
skill_id: a2ui_peer_compare
description: |
  Compare revenue, stock price, or general performance across multiple companies.
  USE THIS SKILL WHEN the user asks:
  - "Compare X vs Y" (general comparison)
  - "How does X stack up against Y?"
  - "X vs Y revenue" or "X vs Y performance"
  - "Side-by-side comparison of X and Y"
  - "Stock price comparison" or "price correlation"
  DO NOT USE for:
  - Single-company analysis
  - Margin/profitability comparisons (use margin_analysis skill instead)
  - "X vs Y margins" or "X vs Y margin trend" → use margin_analysis
widgets:
  - PriceChart
  - DataTable
  - CorrelationMatrix
layout: grid-3
---

# A2UI Skill: Peer Comparison

## Intent
Compare financial metrics across 2-6 companies with overlaid charts, data tables, and correlation analysis.

## Widget Layout (A2UI Surface Structure)

Surface: `dashboard_main`
Root: `layout_root` (Column)

```
Column (layout_root)
├── Row (header_row)
│   └── Text (title): "Comparing {tickers_joined}"
├── Row (charts_row)
│   ├── Card (chart_card, weight: 2)
│   │   └── PriceChart (price_overlay)
│   │       props: { ticker: /data/primary_ticker, interval: "3M" }
│   │       NOTE: Multi-ticker overlay handled by ticker array
│   └── Card (correlation_card, weight: 1)
│       └── CorrelationMatrix (correlation)
│           props: { tickers: /data/tickers, matrix: /data/correlation/matrix }
└── Card (table_card)
    └── DataTable (metrics_table)
        props: { columns: /data/table/columns, data: /data/table/rows, sortable: true }
```

## Inputs (Slots)
- `tickers` (required, array): List of 2-6 stock symbols to compare
- `metric` (optional, default: "Revenue"): Primary metric for comparison
- `period` (optional, default: "year"): quarter or year

## Data Model Paths

| Path | Type | Source Tool |
|------|------|-------------|
| `/data/tickers` | array | Input extraction |
| `/data/primary_ticker` | string | First ticker in list |
| `/data/correlation/tickers` | array | Same as /data/tickers |
| `/data/correlation/matrix` | array[array] | Calculated from price data |
| `/data/table/columns` | array | Generated: [Ticker, {Metric}, YoY Change] |
| `/data/table/rows` | array | query_database |

## Tool Execution Sequence

1. **Extract tickers** from user question
   - Example: "Compare AMD vs INTC" → tickers=["AMD", "INTC"]
   - Minimum 2, maximum 6 tickers

2. **query_database**: Fetch metrics for all tickers
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

3. **Calculate correlation matrix** (in-agent processing)
   - Use historical revenue/price data
   - Generate NxN matrix where N = len(tickers)

4. **Format DataTable rows**
   - Each row: { ticker, latest_value, yoy_change_pct }

## A2UI Message Sequence

```
1. beginRendering { surfaceId: "dashboard_main", root: "layout_root" }
2. dataModelUpdate { path: "/data/tickers", contents: ["AMD", "INTC", "NVDA"] }
3. surfaceUpdate { components: [header_row, charts_row skeleton, table_card skeleton] }
4. surfaceUpdate { components: [price_overlay, correlation] }
5. dataModelUpdate { path: "/data/correlation", contents: {...} }
6. surfaceUpdate { components: [metrics_table] }
7. dataModelUpdate { path: "/data/table", contents: {columns, rows} }
```

## Guardrails
- Minimum 2 tickers required; if only 1 provided, suggest adding peers
- Maximum 6 tickers for readability
- Only use `comp_financials` table
- SELECT-only queries
- Correlation values must be -1 to 1

## Example User Queries
- "Compare AMD vs INTC"
- "How does NVDA stack up against AMD and QCOM?"
- "Side-by-side INTC vs AMD vs NVDA revenue"
- "Compare semiconductor companies"
