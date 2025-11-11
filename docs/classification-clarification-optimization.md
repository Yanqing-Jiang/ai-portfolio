# Classification & Clarification Optimization Plan — November 11, 2025

This document captures the telemetry issues observed in `docs/agent-process-ledger - 2025-11-10T224726.191.json`, the confirmed root causes, and the step-by-step fixes we will ship to make classification single-run, shorten its latency, and eliminate phantom clarification loops.

---

## 1. Observed Issues

- **Clarification loop noise:** Ledger sequences 243–244 show repeated `clarification_manager` “start” events even though the tool finished once. `_clarification_phase` (in `backend/analytics/flows/planner_executor.py`) emits multiple progress packets per slot, but `_SingleAgentToolHooks` does not treat `clarification_manager` as a multi-phase tool, so the UI renders each packet as a brand-new run.
- **Classification duplication:** The `classification` block logs five copies of “Starting query classification…” despite only one `classification_started → classification_complete` pair, because the `thinking` array simply accumulates every progress message. Operators interpret this as repeated classifier retries.
- **Fresh-run classification reruns:** Every follow-up (even when the query didn’t change) still schedules `_classification_phase`, adding ~2.5 s of latency that could be avoided by reusing receipts from `SessionStateSnapshot`.
- **Serial execution:** Slot resolution waits for classification to finish. Since both operations hit LLMs, doing them sequentially adds avoidable wall-clock time.

---

## 2. Root Causes

1. `backend/analytics/flows/single_agent_tools.py:MULTI_PHASE_TOOL_CONFIG` only lists `intent_classifier`, `sql_generator`, `chart_designer`, and `analysis_writer`. Clarification progress events therefore bypass the buffering logic and hit the ledger in real time.
2. Frontend hook `components/analytics/hooks/useAnalyticsMemoryStream.ts` still appends every `thinking` payload verbatim instead of deduping by the `thought_id` metadata the backend already attaches (see `planner_executor.py:_attach_thought_metadata`). This recreates the same message many times.
3. `SessionStateSnapshot.revision_context` persists tool receipts but `_run_intent_lane` never checks `should_refresh("classification")`, so revisions always rerun classification.
4. `_classification_phase` and `_intent_phase` run serially, even though the former only gates non-financial rejection while the latter resolves slots and templates. There is no concurrency or timeout guard around `classify_query_async`.

---

## 3. Remediation Plan (Function-by-Function)

### 3.1 Telemetry & Loop Fixes

| Function | Why it exists | Calls / Called by | Changes |
| --- | --- | --- | --- |
| `backend/analytics/flows/single_agent_tools.py:MULTI_PHASE_TOOL_CONFIG` | Declares multi-phase tools so `_SingleAgentToolHooks` buffers interim events. Called from `_stream_with_tool_state`. | Add `clarification_manager` entry with terminal events `{intent_resolved, clarification_skipped, clarification_error, clarification_timeout, clarification_missing_slots}` so only one `agent_tool_call/complete` pair appears per run. |
| `backend/analytics/flows/planner_executor.py:_clarification_phase` | Drives the clarification loop; invoked by `PlannerExecutorFlow` intent lane. | Emit a synthetic `clarification_complete` event (in addition to `intent_resolved`) whenever the loop ends, giving the multi-phase helper an explicit terminal marker. Update summary comment per AGENT instructions. |
| `components/analytics/hooks/useAnalyticsMemoryStream.ts:coalesceThoughts` | Consumes SSE events; used by WorkflowCanvas. | Deduplicate progress entries using `thought_id` and collapse multiple clarification progress packets into a single timeline card. |
| `backend/tests/analytics/test_single_agent_stream_events.py` | Guards telemetry contract. | Add a regression that simulates two clarification questions and asserts the ledger contains exactly one `clarification_manager` completion. |

**Execution flow (telemetry cleanup)**

1. Update `MULTI_PHASE_TOOL_CONFIG` and `_should_buffer_multi_phase_event` so that every clarification progress packet is buffered until a terminal event fires.
2. Teach `_clarification_phase` to emit `clarification_complete` (success) and `clarification_failed` (halt) events before returning; this keeps `_SingleAgentToolHooks` in sync with the planner’s loop state.
3. In `_forward_with_hooks`, assert that buffered clarification events flush exactly once; log and drop extras to avoid future loops.
4. Modify `useAnalyticsMemoryStream` so when it sees `agent_tool_call` for `clarification_manager`, it ignores raw `clarification_*` progress events except for tool badges, preventing duplicate UI pills.
5. Extend `test_single_agent_stream_events.py` with a fixture that emits two slot questions and verify the SSE transcript contains one completion plus deterministic guardrail metadata.

### 3.2 Classification / Intent Concurrency (No New Cache)

| Function | Why it exists | Calls / Called by | Changes |
| --- | --- | --- | --- |
| `backend/analytics/flows/planner_executor.py:_classification_phase` | Runs the off-topic classifier and decides whether the question is financial. Invoked by `_run_intent_lane`. | Launches `classify_query_async` (with `asyncio.wait_for` + fallback) and `resolve_intent_slots_async` simultaneously via `asyncio.gather`, caching the resolver output on `ctx.intent_resolution` so downstream phases skip the extra LLM call. |
| `backend/analytics/flows/planner_executor.py:_intent_phase` | Resolves slots/clarifications and sets up the plan. | Reuses the cached `ctx.intent_resolution` when present; only invokes `resolve_intent_slots_async` on revision paths that didn’t run the concurrent fresh step. |
| `backend/analytics/flows/planner_executor.py:_clarification_phase` | Consumes slot results to ask users for missing fields. | Emits `clarification_complete` / `clarification_failed` at the end of the loop so multi-phase buffering flushes once and downstream telemetry stays deterministic. |
| `components/analytics/hooks/useAnalyticsMemoryStream.ts` | SSE ingestion layer for the frontend. | Dedupe `thinking` events by `thought_id` (including clarification progress) so repeated payloads no longer spam WorkflowCanvas. |
| `backend/tests/analytics/test_pipeline_classification_intent.py` & `backend/tests/analytics/test_single_agent_stream_events.py` | Regression coverage. | Add tests proving (a) slot resolution and classification overlap without deadlocking, and (b) clarification telemetry emits exactly one completion even when multiple prompts fire. |

> **Note:** By relying on the existing session memory receipts rather than introducing a new cache, we satisfy the “run classification once per session” goal without increasing memory footprint. The concurrency refactor merely overlaps the runtime steps.

**Execution flow (concurrency)**

1. `_classification_phase` fires `classify_query_async` (with timeout + fallback) and `resolve_intent_slots_async` together via `asyncio.gather`.
2. The classifier result updates `ctx.classification`/`ctx.is_financial_query`, while the slot resolver output is cached on `ctx.intent_resolution` for reuse.
3. `_intent_phase` checks `ctx.intent_resolution` first; when populated, it skips re-running the resolver and flows straight into normalization, assumptions, and clarification prep.
4. `_clarification_phase` consumes the cached slots and emits the new completion/failure events so telemetry flushes buffered progress exactly once.
5. Tests add concurrency handshakes to prove the resolver starts while classification awaits, and confirm the new telemetry contract stays stable.

---

## 4. Expected Outcomes

1. **Clarification telemetry** collapses to a single tool turn per run, eliminating phantom loops in the ledger and Canvas.
2. **Classification latency** drops because slot resolution and classification overlap, and timeouts stop the lane from blocking fresh runs.
3. **Session-memory reuse** (without new caches) prevents redundant classifier invocations within a session while keeping memory usage flat.
4. **Frontend reasoning bubbles** show each step exactly once thanks to `thought_id` deduplication.

---

## 5. Conflict Check

- **Telemetry buffering vs. concurrency:** The multi-phase buffering applies purely to clarification events. No overlap with classifier concurrency because classification still emits a single `agent_tool_call` and completion (even when its work runs in a background task).
- **Session memory footprint:** We are reusing the existing session-memory receipts only; no new caches or storage formats are added, so the plan stays within the requested memory constraints.
- **Clarification sequencing:** Awaiting the classifier task before `_clarification_phase` starts prevents the concurrency refactor from re-introducing duplicate clarification prompts.

---

## 6. Open Questions / Follow-Ups

1. Should we surface a telemetry flag when the classifier runs concurrently vs. synchronously so ops can measure the new flow?
2. Should the heuristic classifier be logged distinctly when the nano model times out, so support can confirm which path answered the query?
