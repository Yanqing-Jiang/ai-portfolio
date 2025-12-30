---
name: Price Movement Analysis
skill_id: a2ui_explain_move
description: |
  Analyze why a stock price changed significantly.
  USE THIS SKILL WHEN the user asks:
  - "Why did X drop/rise/fall/surge?"
  - "What caused X to drop?"
  - "Explain the X price movement"
  - "What happened to X stock?"
  DO NOT USE for general price queries without "why" intent.
widgets:
  - PriceChart
  - KpiCard
  - NewsTimeline
  - ExplainMovePanel
layout: split-view
---

# A2UI Skill: Price Movement Analysis

## Intent
Explain significant price movements for a stock by combining price data with news sentiment and AI-generated analysis.

## Widget Layout (A2UI Surface Structure)

Surface: `dashboard_main`
Root: `layout_root` (Column)

```
Column (layout_root)
├── Row (header_row)
│   └── Text (title): "{ticker} Price Analysis"
├── Row (main_content)
│   ├── Column (left_panel, weight: 2)
│   │   └── PriceChart (price_chart)
│   │       props: { ticker: /data/ticker, interval: "1M" }
│   └── Column (right_panel, weight: 1)
│       ├── Row (kpi_row)
│       │   ├── KpiCard (kpi_price)
│       │   │   props: { label: "Current Price", value: /data/kpis/price, unit: "$" }
│       │   ├── KpiCard (kpi_change)  
│       │   │   props: { label: "Change", value: /data/kpis/change, delta: /data/kpis/change_pct, deltaType: "percentage" }
│       │   └── KpiCard (kpi_volume)
│       │       props: { label: "Volume", value: /data/kpis/volume, unit: "M" }
│       └── NewsTimeline (news_timeline)
│           props: { events: /data/news/events }
└── ExplainMovePanel (explanation_panel)
    props: { title: /data/explanation/title, explanation: /data/explanation/text, factors: /data/explanation/factors, citations: /data/explanation/citations }
```

## Inputs (Slots)
- `ticker` (required): Stock symbol to analyze
- `time_period` (optional, default: "1M"): Chart time range

## Data Model Paths

| Path | Type | Source Tool |
|------|------|-------------|
| `/data/ticker` | string | Input extraction |
| `/data/kpis/price` | number | query_database |
| `/data/kpis/change` | number | query_database |
| `/data/kpis/change_pct` | number | query_database |
| `/data/kpis/volume` | number | query_database |
| `/data/news/events` | array | get_news_sentiment |
| `/data/explanation/title` | string | generate_analysis |
| `/data/explanation/text` | string | generate_analysis |
| `/data/explanation/factors` | array | generate_analysis |
| `/data/explanation/citations` | array | get_news_sentiment |

## Tool Execution Sequence

1. **Extract ticker** from user question (e.g., "Why did NVDA drop?" → ticker=NVDA)

2. **query_database**: Fetch recent financial metrics
   ```sql
   SELECT ticker, metric, value, period_end
   FROM comp_financials
   WHERE ticker = '{ticker}' 
     AND metric IN ('Revenue', 'Net Income', 'Gross Margin')
   ORDER BY period_end DESC 
   LIMIT 8
   ```

3. **get_news_sentiment**: Search recent news for the ticker
   - Query: "{ticker} stock price"
   - Limit: 5 articles
   - Extract: title, summary, sentiment, source URL, date

4. **generate_analysis**: Create explanation narrative
   - Input: Price data + news summaries
   - Output: Explanation text + contributing factors

## A2UI Message Sequence

```
1. beginRendering { surfaceId: "dashboard_main", root: "layout_root" }
2. surfaceUpdate { components: [header_row, main_content skeleton] }
3. surfaceUpdate { components: [price_chart, kpi_row] }
4. dataModelUpdate { path: "/data/ticker", contents: [{key: "ticker", valueString: "NVDA"}] }
5. surfaceUpdate { components: [news_timeline, explanation_panel] }
6. dataModelUpdate { path: "/data", contents: [kpis, news, explanation] }
```

## Guardrails
- Only use `comp_financials` table for SQL queries
- SELECT-only queries, no mutations
- Limit news to 5 most recent items
- ExplainMovePanel MUST cite news sources
- If no news found, display "No recent news available" message

## Example User Queries
- "Why did NVDA drop today?"
- "What caused AMD to rise?"
- "Explain the INTC price movement"
- "What happened to QCOM stock?"
