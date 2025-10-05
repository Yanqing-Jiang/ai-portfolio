# Schema Clarifier Agent Rollout Plan

## Stage 1 - Harden Template Requirements
- Add `required_slots` arrays to every query template entry in `backend/config/schemas/queries.yaml` (or a new `queries_requirements.yaml` manifest) to enumerate placeholders like `company`, `comparison`, and `timeframe`.
- Update the template loader in `backend/analytics/sql/sql_planner.py` to attach `required_slots` data when returning a template object.
- Create `backend/tests/analytics/test_query_template_integrity.py` that scans each SQL template for `{placeholder}` tokens and asserts they are covered by `required_slots`.

## Stage 2 - Build Requirement Inspector
- Add `backend/analytics/sql/template_requirements.py` with helpers to extract requirements and evaluate satisfaction using normalized slots and `QueryPlanModel` fields.
- Reuse semantic defaults from `backend/config/schemas/metrics.yaml` and `SemanticCatalog.query_defaults()` to treat auto-filled values as satisfied.
- Expose a cached accessor so planners retrieve requirement metadata without reparsing YAML.

## Stage 3 - Implement Schema Clarifier Agent
- Create `backend/analytics/agents/schema_clarifier.py` that receives intent, plan, template, required slots, and `slots_detected`.
- Return `{"action": "skip"}` when all requirements are met; otherwise craft a minimal structured prompt for `get_unified_client()` asking for exactly one missing slot.
- Guard against repeated execution by tracking `(session_id, intent_key, template_id)` and defaulting to heuristic clarifications on exceptions.

## Stage 4 - Integrate Into Planner Workflow
- Invoke the clarifier agent immediately after `choose_template` inside `_intent_phase` (`backend/analytics/flows/planner_executor.py`).
- When the agent returns `skip`, bypass `compute_required_clarifications`; on `clarify`, convert the payload into a `ClarifyRequestModel` and emit existing SSE events.
- Log telemetry events like `clarifier_agent_skip` / `clarifier_agent_prompt` via `EventEmitter` for observability.

## Stage 5 - Prevent Recursive Clarifications
- Store a per-session flag (e.g., `ctx.clarifier_agent_invoked`) so `_clarification_phase` cannot re-run the agent once user feedback arrives.
- Limit automatic retries to a single pass; additional missing slots should fall back to deterministic `compute_required_clarifications` logic.

## Stage 6 - Testing and Validation
- Add unit tests for the clarifier agent (`backend/tests/analytics/test_schema_clarifier_agent.py`) covering skip, clarify, and failure fallbacks.
- Extend planner flow tests (e.g., `test_flows_single_agent.py`) with a "Show Nvidia market share in the past 5 years" scenario ensuring no redundant clarification.
- Ensure the template integrity test runs in CI to fail builds when a template lacks explicit requirements.

## Stage 7 - Documentation and Telemetry Surfacing
- Update `backend/analytics/ARCHITECTURE.md` and `backend/analytics/TO_DO.md` with the new decision point and telemetry signals.
- Optional: surface clarifier agent status in `components/analytics/useAnalyticsMemoryStream.tsx` for QA visibility.

## Stage 8 - Rollout and Monitoring
- Introduce an `ANALYTICS_SCHEMA_CLARIFIER_ENABLED` flag in `backend/analytics/core/config.py` for staged deployment.
- Enable in staging, monitor clarification skip rates via telemetry, then roll out to production once metrics stabilize.
