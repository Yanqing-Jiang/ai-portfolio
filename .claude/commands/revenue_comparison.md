# Command: Revenue Comparison

- **Intent:** Compare revenue across tickers or periods with clear unit formatting.
- **Inputs:** `tickers` (list), `periods` (range or list), optional `currency_unit` (default millions USD).
- **Flow:** Database Admin runs batched SQL → Chart Builder builds grouped bar/line with legend on right → annotate YOY/QOQ deltas.
- **Guardrails:** Keep rows capped for streaming; include `value_unit: "millions_usd"`; avoid web search unless user requests news follow-up.

