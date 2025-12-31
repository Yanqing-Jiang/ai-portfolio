---
name: Margin Analysis
skill_id: a2ui_margin_analysis
description: |
  Analyze profit margins (gross, operating, net) for one or more companies.
  USE THIS SKILL WHEN the user asks:
  - "What are X's margins?"
  - "X profitability analysis"
  - "Gross/operating/net margin for X"
  - "How profitable is X compared to peers?"
  - "X margin vs industry average"
  - "X vs Y margins" or "X vs Y margin trend" (margin-focused comparisons)
  - "Compare margins for X and Y"
  - "X vs Y profitability"
  DO NOT USE for:
  - Revenue comparisons without margin context
  - Stock price comparisons
  - General "compare X vs Y" without margin/profitability keywords
widgets:
  - KpiCard
  - DataTable
layout: compact
---

# A2UI Skill: Margin Analysis

## Intent
Display profit margins (gross, operating, net) for a target company, optionally compared to peer averages.

## Widget Layout (A2UI Surface Structure)

Surface: `dashboard_main`
Root: `layout_root` (Column)

```
Column (layout_root)
├── Row (header_row)
│   └── Text (title): "{ticker} Margin Analysis"
├── Row (kpi_grid)
│   ├── KpiCard (gross_margin)
│   │   props: { label: "Gross Margin", value: /data/kpis/gross_margin, unit: "%", delta: /data/kpis/gross_vs_peer, deltaType: "percentage" }
│   ├── KpiCard (operating_margin)
│   │   props: { label: "Operating Margin", value: /data/kpis/operating_margin, unit: "%", delta: /data/kpis/op_vs_peer, deltaType: "percentage" }
│   └── KpiCard (net_margin)
│       props: { label: "Net Margin", value: /data/kpis/net_margin, unit: "%", delta: /data/kpis/net_vs_peer, deltaType: "percentage" }
├── Text (peer_context): "Compared to peer average ({peer_count} companies)"
└── Card (table_card)
    └── DataTable (margin_history)
        props: { columns: /data/table/columns, data: /data/table/rows, sortable: true }
```

## Inputs (Slots)
- `ticker` (required): Target company stock symbol
- `peers` (optional): List of peer tickers for comparison (default: semiconductor peers)
- `period` (optional, default: "year"): quarter or year

## Data Model Paths

| Path | Type | Source Tool |
|------|------|-------------|
| `/data/ticker` | string | Input extraction |
| `/data/kpis/gross_margin` | number | query_database |
| `/data/kpis/operating_margin` | number | query_database |
| `/data/kpis/net_margin` | number | query_database |
| `/data/kpis/gross_vs_peer` | number | Calculated delta |
| `/data/kpis/op_vs_peer` | number | Calculated delta |
| `/data/kpis/net_vs_peer` | number | Calculated delta |
| `/data/peer_count` | number | Count of peer tickers |
| `/data/table/columns` | array | [Period, Gross %, Operating %, Net %] |
| `/data/table/rows` | array | query_database |

## Tool Execution Sequence

1. **Extract ticker and peers** from user question
   - Default peers: NVDA, AMD, INTC, QCOM, MU, AVGO

2. **query_database**: Get target company margins
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

3. **query_database**: Get peer average margins
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

4. **Calculate deltas**: Target margin - Peer average

## A2UI Message Sequence

```
1. beginRendering { surfaceId: "dashboard_main", root: "layout_root" }
2. surfaceUpdate { components: [header_row, kpi_grid skeleton] }
3. dataModelUpdate { path: "/data/ticker", contents: [{key: "ticker", valueString: "NVDA"}] }
4. surfaceUpdate { components: [gross_margin, operating_margin, net_margin] }
5. dataModelUpdate { path: "/data/kpis", contents: [...] }
6. surfaceUpdate { components: [peer_context, table_card, margin_history] }
7. dataModelUpdate { path: "/data/table", contents: {columns, rows} }
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

## Example User Queries
- "What are NVDA's margins?"
- "INTC profitability analysis"
- "Compare AMD gross margin to peers"
- "How profitable is QCOM vs industry?"
