# Command: Margin Growth vs Peers

- **Intent:** Analyze margin trends (gross/operating/net) over time and vs peers.
- **Inputs:** `tickers`, `periods`, `margin_type` (gross|operating|net), optional `compare_to` peer list.
- **Flow:** Database Admin pulls margins with `value_unit: "percentage"` → Chart Builder builds multi-series line/area → annotate inflections; optional News specialist if divergence detected.
- **Guardrails:** No TradingView; cap to recent 8-12 periods; ensure tool inputs note `margin_type`.

