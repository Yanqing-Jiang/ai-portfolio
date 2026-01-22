# Command: Market Share (Single)

- **Intent:** Compare a single semiconductor company's market share vs peers for a period.
- **Inputs:** `ticker` (required), `period` (quarter/year), optional `metric` override.
- **Flow:** Route to Database Admin → fetch share metrics → Chart Builder renders bar/line with right-side legend → brief narrative.
- **Guardrails:** Keep SQL scoped to `comp_financials`; include `value_unit` metadata; avoid TradingView.

