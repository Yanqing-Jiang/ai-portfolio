# Structured Resolver Payload

## Response Fields
- `intent` (object)
  - `key`: string | null — selected intent identifier.
  - `confidence`: number — resolver confidence in the selection.
  - `mode`: string — resolver mode (`single_agent`, `fanout`, or `multi_agent`).
- `slots` (object map)
  - Keys are slot names (`company`, `metric`, `metrics`, `timeframe`, ...).
  - Values follow `LLMSlotStatusModel` with:
    - `status`: `filled` | `missing` | `defaulted` | `assumed`.
    - `value`: string | number | bool | list[str] | timeframe object | null.
    - `reason`: string | null.
    - `suggestions`: list[str].
    - `allow_custom`: bool | null.
- `followups` (array of objects)
  - `slot`: slot name needing clarification.
  - `prompt`: user-facing clarification prompt.
  - `suggestions`: list[str].
  - `allow_custom`: bool.
  - `reason`: string | null.
- `notes` (string | null) — free-form resolver commentary.

## Normalisation & Call Flow
1. `unified_responses_client._wrap_response_model` subclasses every structured model so the generated JSON Schema satisfies the Responses API contract (required lists, no defaults, explicit `additionalProperties`).
2. `create_structured` enforces schema normalisation before invoking `client.responses.parse` so downstream planners continue receiving `LLMIntentResolutionModel` instances with identical shapes.
3. On `invalid_json_schema` the client currently falls back to heuristic intent resolution; additional work remains to reconcile the API requirement with dictionary-valued slots.

## Newly Added Intents (2025-10-23)
- `eps_yoy_rank_latest` &mdash; ranks latest-quarter EPS Basic YoY growth across the semiconductor peer set.
- `operating_leverage_yoy_vs_peers` &mdash; traces a company’s YoY operating leverage versus the peer average over the last five fiscal years.
- `capex_intensity_latest_rank` &mdash; compares latest-quarter CapEx intensity (CapEx ÷ Revenue) to highlight the most capital-intensive peers.

## Follow-On Work
- Capture the outgoing schema payload to confirm the Responses endpoint still flags `slots` as invalid despite normalisation.
- Evaluate transforming `slots` into a list of `{slot, status}` pairs for schema compliance.


The required-slot mapping in backend/config/schemas/query_requirements.yaml ultimately feeds two runtime paths:

  - backend/analytics/core/config.py:19-43 (inner _load inside Configs.load) reads this YAML into CONFIGS.query_requirements.
  - backend/analytics/sql/template_requirements.py:11-32 (get_required_slots) looks up each intent’s required slots from that structure at execution time.
  - backend/analytics/core/slot_catalog.py:227-275 (SlotCatalog._build_intent_map) iterates the same mapping to build each intent’s required_slots/optional_slots definitions that the clarification UI consumes.