# Analytics Modes Update Plan (Oct 14, 2025)

## Objectives
- Remove the duplicate **Financial Analysis** card from the single-agent ledger while keeping the collapsible _Market Research_ and _Generated SQL Query_ cards intact.
- Reshape the multi-agent ledger so that it emits the same cohesive payload structure (analysis + SQL + chart + stock + web) as the single-agent flow, ensuring the stock widget renders at full width.
- Audit the React stream adapter to confirm both ledgers hydrate the chat + ProcessPanel views consistently, adjusting parsing if field names differ.

## Step 1 - Single-Agent Ledger Cleanup (`docs/agent-process-ledger (32).json`)
- Cull the early `analysis_generation` record that currently produces the first Financial Analysis card; this removes the redundant market-only card.
- Ensure the terminal `short_financial_analysis` object keeps the combined payload. Example target structure:
```json
{
  "id": "short_financial_analysis",
  "details": {
    "analysis": { "tldr": "TL;DR.", "bullets": ["SQL insight", "Market insight", "Stock insight"] },
    "tool_results": [
      { "tool": "sql_executor", "payload": { "row_count": 24, "sample_rows": [...] } },
      { "tool": "chart_builder", "payload": { "chart_spec_id": "analytics:chart:abcd1234" } },
      { "tool": "stock_tracker", "payload": { "symbol": "NVDA", "latest_close": 188.32 } },
      { "tool": "web_retriever", "payload": { "summary": "Industry growth still ~11% YoY", "snippets": [...] } }
    ]
  }
}
```
- Verify upstream references (manifests, stage emissions) no longer list the removed `analysis_generation` node.

## Step 2 - Multi-Agent Ledger Harmonization (`docs/agent-process-ledger (31).json`)
- Promote the streaming supervisor notes into a finished `short_financial_analysis` record with TL;DR plus bullet trio tying together SQL deltas, stock move, and web intel.
- Copy the existing specialist payloads into `tool_results` so the UI can surface identical collapsible cards. Example snippet:
```json
{
  "tool": "web_retriever",
  "status": "completed",
  "payload": {
    "search_id": "HdLtaNaqM9ygz7IPvLmB0QU",
    "summary": "NVIDIA revenue +114% YoY vs industry low double digits",
    "snippets": [{ "title": "macrotrends.net", "snippet": "NVIDIA's revenue ." }]
  }
}
```
- Mark `analysis_generation` as "completed" and drop the stray `unknown` error block so the ProcessPanel timeline reads cleanly.
- Confirm chart and SQL artifacts reference the same IDs as the single-agent example to keep downstream hydration predictable.

## Step 3 - Frontend Parsing Review
- Inspect `components/analytics/hooks/useAnalyticsMemoryStream.ts` to ensure the multi-agent branch maps `tool_results` -> `toolFanoutResults` and `stock_widget` -> `stockWidgetConfig`. Patch any gaps (e.g., specialist-specific `tool` names) so both flows populate `TradingViewSymbolOverview`, `WebSearchCard`, and `SqlCard`.
- Cross-check `ChatHistory.tsx` by replaying mocked data using the refreshed ledgers to verify the stock card takes the standard width and the Market Research section stays collapsed by default.

## Step 4 - Validation
- Run targeted tests once updates are in place:
  1. `pytest backend/tests/analytics/test_single_agent_flow.py -q`
  2. `pytest backend/tests/analytics/test_multi_agent_flow.py -q`
  3. `npm test -- components/analytics`
- Manually open both ledgers in the ProcessPanel demo to confirm card ordering: SQL chart, Stock tracker, Market Research (collapsed), Generated SQL (collapsed), final Financial Analysis.

## Risks & Mitigations
- **Schema drift**: keep `tool` identifiers (`stock_tracker`, `web_retriever`, `sql_executor`) identical across modes to avoid conditional parsing in React.
- **Oversized JSON**: pruning duplicate analysis nodes reduces payload weight; prune unused telemetry fields if the diff grows beyond expected bounds.
- **Testing gaps**: add lightweight fixture-based assertions in the targeted pytest modules if existing coverage fails to load the new ledger shape.