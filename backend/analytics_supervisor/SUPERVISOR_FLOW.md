# Supervisor Flow Reference (v2.4)

The supervisor orchestrates every analytics query by preparing intent, validating required slots, and either running a deterministic SQL fast lane or delegating to an OpenAI tool loop. This document captures the current control flow, event surface, and integration points for the refactored pipeline.

**LATEST UPDATE**
- Added a fast-lane SQL pipeline gated by the `FAST_LANE_SQL` environment variable; successful runs skip the agent loop entirely.
- Moved classification to a keyword-based sieve and introduced an in-process intent cache (60 s TTL) ahead of `detect_intent_fast_async`.
- `criteria_ready` is now emitted for every session, immediately exposing the finalised `SqlCriteriaModel` to the frontend.
- Normalised SSE events between fast-lane and agent paths (`plan_built`, `sql_generated`, `chart_generated`, etc.).

---

## High-level phases

1. **Session bootstrap**  
   - Create/restore `session_id`, allocate `WorkflowState`, and emit `session_started`.

2. **Conversation guards**  
   - `_is_small_talk` returns early with `workflow_complete` for greetings/small talk.  
   - `_looks_financial` runs a low-cost keyword sieve; non-financial queries reply with the default decline message.

3. **Intent cache lookup**  
   - Lowercased query key stored in `INTENT_CACHE` for 60 seconds. Cache hits emit `intent_detection_started` with `cache_hit=True` and reuse the saved payload.

4. **Intent detection & schema validation**  
   - `detect_intent_with_clarifications_async` delegates to `detect_intent_fast_async` (heuristic-first, single LLM call when required).  
   - Emits: `intent_detection_started`, `intent_detection_complete`, `schema_validation_started`.  
   - Schema requirements derived from intent metadata. Missing slots trigger `clarification_loop_start` → `clarification_request`/`clarification_acknowledged` → `clarification_loop_complete`.  
   - `criteria_ready` streams the `SqlCriteriaModel` (with timestamp) after consolidation.

5. **Fast-lane SQL (optional)**  
   - Enabled when `FAST_LANE_SQL` ≠ `false` and validation confirms all required slots.  
   - `_run_fast_lane_sql` performs:
     - `plan_and_select_template` → emits `plan_built`, `template_selected`, `sql_compiled`, `sql_generated`.
     - `validate_sql` → emits `sql_validated` (inside fast-lane payload) or warns + falls back to agent loop.
     - `apply_execute_sql` → emits `sql_executed`, `data_retrieved`.
     - `plan_chart`/`build_chart` → emits `chart_planned`, `chart_generated`.
     - `short_financial_analysis` → emits `analysis_complete`.
   - On success, the workflow skips the tool loop and proceeds directly to analysis/finalisation events.

6. **Agent tool loop (fallback)**  
   - Triggered when the fast lane is disabled or fails validation/SQL execution.  
   - Emits `tool_planning_started` followed by `tool_selection_reasoning` with the proposed strategy.  
   - `_execute_tools_direct` runs the OpenAI Responses loop, yielding `tool_selected`, `tool_start`, `tool_end`, and streaming tool outputs (`sql_generated`, `sql_executed`, etc.).  
   - `WorkflowState` tracks executed tools, retrieved data, chart specs, and analysis artefacts.

7. **Analysis & finalisation**  
   - Streams `analysis_streaming` chunks, then `analysis_complete`.  
   - `_finalization_turn` produces `final_summary`.  
   - `workflow_complete` closes the session, including total elapsed time.

---

## Event timeline snapshot

| Phase | Key SSE events |
|-------|----------------|
| Guardrail | `session_started`, `classification_started`, `classification_reasoning`, `classification_complete`, `classification_fallback` |
| Intent | `intent_detection_started`, `intent_detection_complete`, `schema_validation_started`, `schema_validation_complete`, `criteria_ready` |
| Clarifications | `clarification_loop_start`, `clarification_request`, `clarification_acknowledged`, `clarification_loop_complete`, `clarification_skipped` |
| Fast lane (if used) | `plan_built`, `template_selected`, `sql_compiled`, `sql_generated`, `sql_executed`, `data_retrieved`, `chart_planned`, `chart_generated`, `analysis_complete` |
| Agent loop | `tool_planning_started`, `tool_selection_reasoning`, `tool_selected`, `tool_start`, `tool_end`, `tool_error`, plus the same SQL/chart/analysis events emitted by the tools |
| Finale | `analysis_streaming`, `analysis_complete`, `final_summary`, `workflow_complete` |

Both execution paths produce identical downstream events, allowing the frontend to stay agnostic to the chosen strategy.

---

## Component interactions

```
Query
 ├─ Small talk / financial sieve
 ├─ INTENT_CACHE HIT?
 │    └─ yes → reuse cached intent
 └─ detect_intent_with_clarifications_async (heuristic-first)
        ├─ Clarification loop (if required)
        └─ intent_to_sql_criteria → criteria_ready
             ↓
     FAST_LANE_SQL enabled?
        ├─ yes → _run_fast_lane_sql → analysis/finalisation
        └─ no  → OpenAI tool loop (_execute_tools_direct)
```

`SupervisorTools` continues to wrap deterministic helpers (`plan_and_select_template`, `validate_sql`, `apply_execute_sql`, `plan_chart`, `build_chart`, `short_financial_analysis`). The fast lane and the agent loop share these implementations to keep behaviour identical.

---

## Configuration & tuning

- `FAST_LANE_SQL` – enable/disable the deterministic pipeline (default `true`).
- `INTENT_CACHE_TTL` – duration (seconds) for cached intents (default `60`).
- Shared configuration (`analytics_memory.config.CONFIGS`) supplies default tickers, intent patterns, SQL limits, and chart settings.

---

## Frontend implications

- The Process Panel should treat `schema_validation` as complete once `criteria_ready` arrives (even if the agent loop will run afterwards).
- Fast-lane sessions stream the same `sql_*`, `chart_*`, and `analysis_*` events, so UI components can remain mode-agnostic.
- `supervisorState` may now contain `criteria`, enabling criteria cards or debug surfaces to render the extracted slots immediately.

---

## Summary

The supervisor now prioritises deterministic execution for well-posed queries while preserving the rich agent experience for exploratory requests. Intent caching, the keyword sieve, and the fast-lane SQL path collectively reduce latency, and the harmonised event surface ensures the frontend stays responsive regardless of which path completes the workflow.
