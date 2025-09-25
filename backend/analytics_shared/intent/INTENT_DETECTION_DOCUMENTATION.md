# Intent Detection Documentation (v2.4)

The intent subsystem transforms a natural-language finance query into a structured `IntentModel` and, ultimately, a `SqlCriteriaModel`. Shared logic lives under `backend/analytics_shared/intent` so both the supervisor and memory workflows behave identically.

---

## Module overview

### `analytics_shared/intent/detection.py`
Core responsibilities:
- Provide a heuristic detector that can satisfy the query without using an LLM when confidence is high.
- Offer a fast async path that performs 6 0 or 1 structured OpenAI call.
- Normalise slots, resolve companies, and prune redundant clarifications.

Key constructs:

| Symbol | Description |
|--------|-------------|
| `HEURISTIC_CONFIDENCE_THRESHOLD = 0.70` | Minimum confidence for bypassing the LLM. |
| `heuristic_intent(query, configs)` | Returns an `IntentModel` with detected slots (`company`, `timeframe`, `granularity`, `tickers`) and optional clarifications. Uses keyword rules plus `detect_company_from_query`. |
| `detect_intent_fast_async(...)` | Fast path used by both products. Runs `heuristic_intent`; if confidence 70% it returns immediately, otherwise it calls the OpenAI Responses API once (default model `gpt-5-mini-2025-08-07`, `reasoning_effort="low"`). |
| `detect_intent_with_clarifications_async` | Alias of `detect_intent_fast_async` for backwards compatibility. |
| `post_process_slots(...)` | Applies normalisation, resolves company aliases, and injects default tickers. |
| `cleanup_clarifications_after_company_detection(...)` | Removes obsolete clarification suggestions once a company is discovered during post-processing. |

The OpenAI call uses a single structured prompt: a system message describing the schema followed by a user message listing supported intents, available tickers, and the user query. The helper handles transient failures by falling back to the heuristic result and logs each phase for observability.

### `analytics_shared/intent/normalization.py`
- `normalize_timeframe(tf_raw, query_text, configs)` now copies dict inputs before applying defaults, ensuring configuration bounds (e.g., `max_years_back`) are still enforced.
- `normalize_granularity` infers annual vs quarterly cadence from textual hints.
- `get_default_tickers` reads `configs.companies.selection_rules.default_companies.tickers`, defaulting to a semiconductor-heavy basket.

### `analytics_shared/intent/models.py`
- `IntentModel` provides the shared schema for intent, confidence, detected slots, clarifications, etc.
- `SqlCriteriaModel` (intent key, company, comparison, timeframe, granularity, tickers, metrics) is produced by `intent_to_sql_criteria(intent, configs)` and used downstream for SQL compilation.

---

## Integration summary

### Supervisor workflow
- Calls `detect_intent_with_clarifications_async` up front and caches results per lowercased query for 60 seconds.
- Emits `criteria_ready` immediately after converting the `IntentModel` via `intent_to_sql_criteria`.
- If required slots are satisfied, `_run_fast_lane_sql` executes plan → validate → execute deterministically.

### Analytics memory workflow
- Performs a keyword classification (`_looks_financial`) instead of a dedicated LLM classifier.
- Uses `detect_intent_with_clarifications` (sync wrapper over the async fast path) and follows up with `intent_to_sql_criteria` to stream `criteria_ready` before SQL compilation.
- Shares the same clarification logic and emits identical SSE events.

Both flows now make at most one LLM call per query for intent extraction, drastically reducing latency compared with the prior classification + intent sequence.

---

## Runtime sequence

1. **Heuristic pass**  
   - Pattern matching (`market share`, `margin`, `growth`, `r&d`) + alias-driven company detection.  
   - Populates `slots_detected` with defaults (tickers, timeframe, granularity).  
   - Suggests clarifications for required slots (e.g., missing `company`).

2. **Structured LLM call (only when necessary)**  
   - Single `create_structured` request using `LLMIntentModel`.  
   - Returns intent key, confidence, slots, optional clarifications, and reasoning.  
   - Post-processing normalises data and removes redundant clarifications.

3. **Criteria conversion**  
   - `intent_to_sql_criteria` produces the canonical `SqlCriteriaModel`.  
   - Downstream systems validate and, if applicable, cache the criteria for fast lane execution.

---

## Configuration dependencies

- `configs.queries.query_patterns` – list of supported intents surfaced in the prompt.
- `configs.companies.selection_rules.default_companies.tickers` – fallback ticker universe.
- `configs.database.query_defaults` – `default_years_back` and `max_years_back` bounds for timeframe normalization.

---

## Testing guidance

- `backend/tests/test_intent_detection.py` covers heuristic detection and the criteria conversion helper, ensuring timeframe bounds and list coercion behave as expected.
- Heuristic-only scenarios should be unit-tested via direct calls to `heuristic_intent` with mocked configs.
- End-to-end tests should assert that `detect_intent_with_clarifications_async` returns identical outputs when invoked repeatedly (intent cache) and that `criteria_ready` reflects merged clarifications.

---

## Summary

The intent detection system now prioritises speed:
- A single async helper with heuristic short-circuiting and a 0/1 LLM pattern.
- Consistent slot normalisation via shared utilities.
- Immediate `SqlCriteriaModel` generation for downstream planners.
- Identical behaviour across supervisor and memory workflows, enabling features like the fast-lane SQL path to operate without additional glue code.
