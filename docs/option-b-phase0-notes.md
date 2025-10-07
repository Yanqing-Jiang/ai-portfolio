# Option B – Phase 0 Spike Notes (Oct 7, 2025)

## 1. PlannerPhaseContext Inventory
Source: `backend/analytics/flows/planner_executor.py`

The existing `PlannerPhaseContext` dataclass bundles mutable state across every pipeline phase. Below is the current field list with the phases that produce/consume each value.

| Field | Type | Produced by | Consumed by / Notes |
| --- | --- | --- | --- |
| `query` | `str` | Initialization | Used everywhere as immutable input. |
| `session_id` | `str` | Initialization | Telemetry & session persistence. |
| `workflow_start` | `float` | Initialization | Timing metrics (SQL/analysis). |
| `timed_emitter` | `TimedEventEmitter` | Initialization | All phases emit SSE metrics. |
| `configs` | `Dict[str, Any]` | Initialization | SQL planning/templates. |
| `classification` | `OffTopicClassifierSchema?` | `_classification_phase` | Intent/clarifier logic. |
| `is_financial_query` | `bool` | `_classification_phase` | Legacy guard; still toggles telemetry. |
| `intent` | `IntentModel?` | `_intent_phase` | Clarification, planning, SQL. |
| `provisional_plan` | `QueryPlanModel?` | `_plan_phase` (early) | Clarification fallback, comparisons. |
| `template` | `Any?` | `_plan_phase` | SQL generation (template hints). |
| `clarifications` | `List[ClarifyRequestModel]` | `_clarification_phase` | Clarifier + planner result. |
| `assumptions` | `List[str]` | `_clarification_phase` | Surface to analysis + UX. |
| `clarification_rounds` | `int` | `_clarification_phase` | Telemetry guard. |
| `clarifier_agent_invoked` | `bool` | `_clarification_phase` | Planner result metadata. |
| `schema_clarifier_decision` | `ClarifierDecision?` | `_clarification_phase` | Downstream risk controller. |
| `plan` | `QueryPlanModel?` | `_plan_phase` | SQL generation inputs. |
| `candidate_templates` | `List[Dict[str, Any]]` | `_plan_phase` | SQL attempt metadata. |
| `selected_template_id` | `str?` | `_plan_phase` | Telemetry (sql_compiled). |
| `sql` | `str` | `_sql_pipeline` | Execution, analysis context. |
| `llm_used` | `bool` | `_sql_pipeline` | Planner result + telemetry. |
| `sql_attempt` | `int` | `_sql_pipeline` | Telemetry. |
| `sql_attempts` | `List[Dict[str, Any]]` | `_sql_pipeline` | Planner result payload. |
| `validation_attempt` | `int` | `_sql_pipeline` | Validation telemetry. |
| `data` | `List[Dict[str, Any]]` | `_execute_sql_phase` | Chart + analysis phases. |
| `exec_elapsed_ms` | `int?` | `_execute_sql_phase` | Telemetry (execution_stats). |
| `chart_spec` | `Dict[str, Any]?` | `_chart_phase` | Analysis + frontend snapshot. |
| `web_search` | `ResponseSearchResult?` | `_web_search_phase` | Analysis enrichment. |
| `analysis` | `str` | `_analysis_phase` | Planner result + snapshot. |
| `parallelism_enabled` | `bool` | Initialization | Tool fan-out logic. |
| `planner_result` | `PlannerResultModel` | Aggregated across phases | SSE `planner_result` event. |
| `halted` | `bool` | Any phase on failure | Controls cleanup. |
| `halt_reason` | `str?` | Failure handlers | Telemetry + UX messaging. |

**Observation:** The context mixes immutable inputs, phase outputs, telemetry helpers, and derived planner summaries. Option B will decompose this into per-phase artifacts so that state hand-off happens explicitly instead of mutating a single object.

## 2. Artifact Spike (Classification & Intent)
- Prototype module added at `backend/analytics/artifacts/spike_artifacts.py` defining:
  - `ClassificationArtifact` capturing classifier category, confidence, financial flag, and raw payload.
  - `IntentArtifact` capturing the detected intent key, slots, and provenance details.
  - Helper functions (`classification_from_event`, `intent_from_event`) that convert existing SSE event payloads into artifacts. These will be swapped to use direct phase outputs when the pipeline refactor lands.
- Both artifacts rely only on standard library + existing type hints (no runtime dependency on planner context).

## 3. OpenAI Agents SDK Integration Notes
Sources reviewed:
- Multi-agent supervisor patterns and guardrails: OpenAI Dev Guide, “Orchestrating multi-agent workflows” citeturn0search1
- Tool/agent registration guidance: OpenAI Dev Guide, “How to build better agents” (Agent SDK track) citeturn0search3
- SDK capabilities overview and tracing/guardrail features: OpenAI announcement “New tools for building agents” (Agents SDK) citeturn0search6

Key takeaways:
1. **Tool definition:** The SDK expects tools with explicit JSON schemas; our artifact functions can register as tools once they accept/return dict payloads.
2. **Supervisor model:** Multi-agent orchestration can be declaratively configured so the supervisor routes to specialist agents with policy checks (latency budgets, retries).
3. **Tracing:** SDK emits structured traces compatible with our ProcessPanel telemetry; we can forward traces into existing SSE channels.
4. **Guardrails:** SDK policies support validation of tool outputs (schema + custom logic). We should embed artifact validation here to stop bad SQL/analysis earlier.

## 4. Open Questions
1. How do we expose streaming analysis chunks as artifacts while preserving incremental SSE updates?
2. Should chart + analysis artifacts keep raw datasets or references only (spec IDs)?
3. How do we version artifacts for session persistence (e.g., revision history vs. overwrite)?
4. How do we gracefully handle optional dependencies (e.g., `google.genai`) so tests run offline while production keeps full functionality?

These items will be addressed in Phase 1 when formal artifact models are defined.
