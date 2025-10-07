# Analytics Flow Modularization Plan (Oct 6, 2025)

## Goal
Enable Single Agent and Multi-Agent modes to call modular analytics tools (especially chart/card revisions) without replaying the full PlannerExecutor pipeline, while preserving existing SSE telemetry and UX.

## Phase 0 - Baseline & Guardrails
- **Inventory**: Confirm current event contracts and snapshot persistence (`backend/analytics/flows/planner_executor.py`, `single_agent_tools.py`, `multi_agent.py`, `instrumentation.py`).
- **Metrics/Telemetry**: Document required SSE events per mode (classification, tool_call, agent_turn, chart_patch) and add contract tests if missing.
- **Test coverage**: Record target suites (`backend/tests/analytics/test_multi_agent_flow.py`, `test_planner_executor_sql.py`, `test_schema_clarifier_agent.py`, `frontend` hooks) for regression.

## Phase 1 - Core Pipeline Extraction
- **Task**: Factor `PlannerExecutorFlow` into a `PlannerPipeline` class exposing high-level phase runners (run_classification, run_intent, run_clarification, run_plan, run_sql, run_chart, run_analysis) while keeping `events()` as the orchestration wrapper.
- **Deliverables**:
  - New `planner_pipeline.py` (or similar) exporting callable phase methods.
  - Refactored `PlannerExecutorFlow` delegating to `PlannerPipeline` but emitting the same SSE sequence (strict contract tests).
  - Updated `PlannerPhaseContext` as shared state object reusable by wrappers.
- **Risks**: Event ordering regressions; mitigate with golden-event tests and `pytest` snapshot comparisons.

## Phase 2 - Hookable Instrumentation Layer
- **Task**: Introduce a hook interface (e.g., `AnalyticsFlowHooks`) with callbacks `on_phase_start`, `on_phase_end`, `on_tool_event`, `on_result`.
- **Apply**:
  - `PlannerExecutorFlow` uses default hooks (no-op).
  - `SingleAgentToolsFlow` overrides hooks to emit `tool_call` start/end instead of inline logic (`single_agent_tools.py`).
  - `MultiAgentFlow` uses hooks to translate planner phases into `agent_turn` events and populate `_shared_context`.
- **Deliverables**:
  - Hook base class + tests ensuring callbacks fire.
  - Simplified wrappers with minimal duplication of telemetry tables.
- **Dependencies**: Phase 1 complete.
- **Status (Oct 6, 2025)**: Added `AnalyticsFlowHooks` lifecycle hooks, refactored single-agent and multi-agent flows to use hook implementations, and validated planner/multi-agent pytest suites.
- **Status (Oct 7, 2025)**: `PlannerPipeline` now exposes modular phase runners (`run_classification`, `run_intent`, `run_clarification`, `run_plan`, `run_sql_pipeline`, `run_chart_phase`, `run_analysis_phase`) with `PlannerExecutorFlow` delegating to them. SQL/chart/analysis stages stream identical events via the new methods; tool registry wiring deferred.

## Phase 3 - Tool Registry Integration
- **Task**: Register core phases as tool descriptors in `backend/analytics/flows/tooling.py` or a new `pipeline_tools.py`.
  - Define metadata (name, inputs, outputs) for `chart_revision`, `analysis_revision`, `sql_regen`, etc.
  - Provide dispatcher functions that invoke specific pipeline methods or cached revisions.
- **Deliverables**:
  - New registry entries with handlers.
  - Updated orchestrator to resolve tools dynamically instead of hard-coded method calls.
- **Status (Oct 7, 2025)**: Landed `backend/analytics/flows/pipeline_tools.py` with registry-backed handlers for planner phases plus `chart_revision`, `analysis_revision`, and `sql_regeneration`; single-agent and multi-agent flows now consume the registry for revision fast-paths and expose the planner tool manifest. Follow-up: extend metadata with latency budgets and surface registry output in telemetry payloads.
- **Risk**: Avoid circular imports between flow modules and tool registry.

## Phase 4 - Cached Revision Entry Points
- **Task**: Implement revision flows that operate on session snapshots without re-running SQL unless required.
  - Create `RevisionContext` helper to load last artifacts (`chart_spec`, `analysis`, `sql_attempts`) from `SessionStateSnapshot`.
  - Add `_chart_revision_phase` producing `chart_patch` events from `ChartOp` arrays.
  - Optionally include `_analysis_revision_phase` for narrative tweaks.
- **Changes**:
  - Extend `analytics_memory_workflow` to detect "revision" queries (using `_is_chart_revision` or new classifier) and route to revision tools.
  - Update `SingleAgentToolsFlow` hooks to label revisions as `tool=chart_designer` or `chart_reviser`.
  - Ensure `MultiAgentFlow` orchestrator triggers only relevant agent roles (`chart`, optional `web_research`).
- **Deliverables**:
  - Revision pipeline functions + SSE emissions.
  - **Status (Oct 7, 2025)**: Implemented shared revision helpers for charts and analysis (`emit_chart_patch`, `emit_analysis_revision`) so Single Agent and Multi-Agent flows call them directly without replaying the full pipeline. Added `pytest-asyncio` so the revision unit tests run under STRICT asyncio mode.
  - Session snapshot updates capturing revision history.
  - Unit tests for revision fast-path.

## Phase 5 - Frontend & UX Adjustments
- **Task**: Ensure Memory page and ProcessPanel handle revision-only sessions.
  - Update `STEP_NAME`/`STEP_ORDER` to include `chart_revision` if necessary.
  - Validate `useAnalyticsMemoryStream` processes `chart_patch` without preceding SQL events.
  - Add UI tests (React Testing Library) for second-round chart updates.

## Phase 6 - Integration & Validation
- **Testing**:
  - Backend: targeted pytest modules, plus new golden-event tests for revision paths.
  - Frontend: run `npm test -- analytics` suite; manual smoke with `npm run dev` + simulated SSE.
  - End-to-end: exercise `/api/analytics/memory/stream` with revision queries, verify SSE order.
- **Telemetry validation**: Confirm `tool_call` and `agent_turn` sequences match legacy behavior for full runs and only emit relevant events for revisions.

## Phase 7 - Rollout & Docs
- **Docs**: Update `ARCHITECTURE.md`, `docs/analytics-flow-overview.md`, and add `docs/revision-tools.md` describing new API.
- **Migration plan**: feature flag the revision fast-path (`ANALYTICS_REVISION_MODE`) for staged rollout.
- **Monitoring**: Instrument logging for revision usage, latency, and fallback counts.

## Estimated Effort
- Phase 0-2: 1 sprint (shared pipeline + hooks).
- Phase 3-4: 1.5 sprints (tool registry + revision entry points).
- Phase 5-7: 0.5 sprint (frontend, validation, docs).
- Total: ~3 sprints with two engineers (one backend, one frontend) plus QA support.

## Risks & Mitigations
- **Event order regressions**: Capture baseline SSE traces before refactor and add contract tests.
- **State desync**: Revision tools may operate on stale snapshots; add cache invalidation when data-changing tools run.
- **Tool explosion**: Keep registry minimal, reuse chart tool for both initial render and revisions via mode flag.
- **Complex orchestrator hooks**: Stage multipliers carefully; start with Single Agent before enabling Multi-Agent hook conversion.

## Open Questions
- Need lightweight classifier or rules to route revision queries vs. full reruns.
- Decide how to version chart specs (`chart_spec_id`) for audit and backoff.
- Determine if analysis revisions must update `planner_result` or append new messages only.











