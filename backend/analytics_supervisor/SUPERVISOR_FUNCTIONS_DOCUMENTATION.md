# Analytics Supervisor Functions Documentation

## Overview

The supervisor module orchestrates a single-agent workflow that prepares intent, validates required inputs, and either executes a deterministic SQL fast lane or guides an OpenAI tool loop for richer reasoning. All public functions live in `backend/analytics_supervisor` and lean on shared helpers in `analytics_shared`.

**LATEST UPDATE (v2.4)**
- Added an optional `FAST_LANE_SQL` path that calls planning, validation, and execution deterministically when intent slots are complete.
- Replaced the LLM-based classification phase with a lightweight keyword sieve (`_looks_financial`) plus an intent result cache.
- Emits a `criteria_ready` event (with timestamp) whenever `intent_to_sql_criteria` finishes, allowing the UI to render compiled slot state instantly.
- Normalised tool events: every SQL path now emits `plan_built`, `template_selected`, `sql_generated`, and per-tool latency metadata.

---

## SupervisorWorkflow class

`SupervisorWorkflow` in `supervisor.py` is the primary entry point. It owns session state, intent caching, SSE event emission, and coordination of either the fast lane or the agent-facing tool loop.

### Core workflow

#### `events(query: str, session_id: Optional[str] = None) -> AsyncGenerator[Dict[str, Any], None]`
Pipeline overview:
1. **Session bootstrap** – generate/track `session_id`, initialise `WorkflowState`.
2. **Small-talk guard** – `_is_small_talk` returns early with `workflow_complete` if the query is conversational.
3. **Financial sieve** – `_looks_financial` scans for finance keywords. Non-financial queries deliver a polite decline.
4. **Intent cache** – a 60s in-memory cache (`INTENT_CACHE`) avoids repeat LLM calls for identical queries.
5. **Intent detection** – calls `detect_intent_with_clarifications_async` (alias of `detect_intent_fast_async`) which heuristically short-circuits unless an LLM call is necessary. Post-processing emits:
   - `intent_detection_started`
   - `intent_detection_complete`
   - `schema_validation_started`
   - `clarification_*` events as required
   - `criteria_ready` including the `SqlCriteriaModel` payload + `ts`
6. **Fast lane evaluation** – if `FAST_LANE_SQL_ENABLED` is `true`, no clarifications remain, and intent slots satisfy schema requirements, `_run_fast_lane_sql` executes planning → validation → execution synchronously. All generated events stream to the frontend; success skips the agent loop entirely.
7. **Agent fallback** – when the fast lane is disabled or incomplete, the workflow emits `tool_planning_started`/`tool_selection_reasoning` and enters `_execute_tools_direct` (OpenAI Responses tool loop). Frontend events mirror each tool’s lifecycle (`tool_selected`, `tool_start`, `tool_end`, `tool_error`).
8. **Analysis & finalisation** – once data exists, the supervisor streams analysis chunks, calls `_finalization_turn`, and pushes `final_summary` plus `workflow_complete`.

Key metadata stored in `WorkflowState.session_metadata`:
- `intent_cache_hit`
- `criteria` (latest `SqlCriteriaModel` dict)
- `fast_lane_sql` usage + issues
- `fast_lane_plan` / `fast_lane_template` when available

`FAST_LANE_SQL_ENABLED` is derived from the `FAST_LANE_SQL` environment variable (default "true").

#### `_run_fast_lane_sql(query, session_id, intent)`
Deterministic path that avoids the agent loop. It:
- Calls `SupervisorTools.plan_and_select_template` (bundled plan + SQL) and emits `plan_built`, `template_selected`, `sql_compiled`, `sql_generated` with elapsed timing.
- Runs `SupervisorTools.validate_sql`; any failure emits a warning and returns to agent mode.
- Executes SQL via `SupervisorTools.apply_execute_sql`, streaming `sql_executed` and `data_retrieved` (with row counts/sample).
- Plans/builds charts with `plan_chart`/`build_chart`, emitting `chart_planned` and `chart_generated`.
- Produces a `short_financial_analysis` result and emits `analysis_complete`.
- Returns a structure indicating success plus collected events so callers can yield them verbatim.

#### `_execute_tools_direct(query, session_id)` and `_tool_calling_loop(...)`
When the fast lane is unavailable, the supervisor falls back to the OpenAI tool loop:
- `tool_selection_reasoning` now transitions from the planning phase and highlights the chosen strategy.
- Each model-selected tool emits `tool_selected`, `tool_start`, and `tool_end`/`tool_error` with animations, timing, and preview arguments.
- `_execute_single_tool` handles result plumbing. For `plan_and_select_template` and `compile_sql` it synthesises SQL events identical to the fast lane so the frontend stays in sync.

#### `_execute_single_tool(tool_name, tool_args, session_id)`
Routes individual tool calls to `SupervisorTools`. Enhancements:
- Returns combined plan/template/sql payloads for `plan_and_select_template` with `combined=True`.
- Logs SQL compilation/validation analytics and emits structured SSE updates.
- Keeps `WorkflowState` caches (`executed_tools`, `sql_executed`, `data_retrieved`, etc.) up to date for later phases or follow-up queries.

### Clarification utilities
- `_pending_clarifications` + `_clarification_events` gate asynchronous UI responses.
- `submit_clarification` hydrates workflow state and releases `_wait_for_clarification`.
- `criteria_ready` is always re-emitted after clarifications update slots to guarantee the UI sees the final schema.

### Heuristic helpers
- `_is_small_talk(query)` – simple greeting/small-talk detection for early exits.
- `_looks_financial(query)` – keyword-driven sieve that replaces the previous LLM classification step.
- `_get_options_for_slot` / `_get_default_for_slot` – supply clarification UI defaults when intent slots remain empty.

### Fast-lane toggles and caching
- `FAST_LANE_SQL_ENABLED` environment toggle (string truthy check).
- `INTENT_CACHE` with 60 second TTL (per lowercased query key) prevents repeated LLM calls across sessions.

---

## SupervisorTools (`backend/analytics_supervisor/tools.py`)
The tools façade still mirrors deterministic helpers from `analytics_shared` and `analytics_memory`, but a few functions gained additional responsibilities.

- `plan_and_select_template(intent)` – returns `{ plan, template, sql, granularity, combined: True }` and is used by both the fast lane and the agent loop to emit uniform events.
- `validate_sql(sql, granularity, max_limit)` – delegates to `analytics_shared.sql.validator` (limits tables, enforces `LIMIT`, upper-bounds row counts).
- `apply_execute_sql(sql)` – runs validation, enforces SELECT-only queries, truncates results to 50 rows, and logs execution details.
- `plan_chart` / `build_chart` – unchanged wrappers around shared chart planners/builders; results are surfaced in fast-lane and agent modes alike.
- `short_financial_analysis(data, query, sql)` – quick statistical summary stored alongside dataset metadata for streaming analysis or fast lane responses.

All other RAG helpers (`retrieve_templates_rag`, `search_metrics_rag`, etc.) continue to return structured contexts but are now typically bypassed when the fast lane succeeds.

---

## Key SSE events

Pre-agent:
- `classification_started`, `classification_reasoning`, `classification_complete`, `classification_fallback`
- `intent_detection_started`, `intent_detection_complete`
- `schema_validation_started`, `schema_validation_complete`
- `criteria_ready` (new) – final `SqlCriteriaModel`

Clarifications:
- `clarification_loop_start`, `clarification_request`, `clarification_acknowledged`, `clarification_loop_complete`, `clarification_skipped`

Execution:
- `tool_planning_started`, `tool_selection_reasoning`, `tool_selected`, `tool_start`, `tool_end`, `tool_error`
- `plan_built`, `template_selected`, `sql_compiled`, `sql_generated`, `sql_executed`, `data_retrieved`
- `chart_planned`, `chart_generated`
- `analysis_streaming`, `analysis_complete`
- `final_summary`, `workflow_complete`

Fast-lane events reuse the same names so frontend consumers do not need mode-specific handling.

---

## Environment & configuration knobs

- `FAST_LANE_SQL` (default `true`) – enables the direct SQL pipeline when intent slots are complete.
- `INTENT_CACHE_TTL` (default 60s) – in-memory cache lifetime for intent detection results.
- Supervisor relies on shared configuration via `analytics_memory.config.CONFIGS` for company defaults, intent patterns, and SQL safeguards.

---

## Summary

Supervisor now follows a two-tier execution model:
1. **Deterministic fast lane** for common, well-specified financial questions.
2. **LLM-driven agent loop** for ambiguous or exploratory requests.

Both paths share the same SSE event surface, leverage `analytics_shared` utilities, and keep frontend UX informed through `criteria_ready`, detailed tool telemetry, and richer analysis streaming.
