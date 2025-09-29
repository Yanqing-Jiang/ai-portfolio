# Analytics Backend Overhaul Plan
Date: 2025-09-26
Execution Order: Phase 0 -> Phase 7. Update status after completing each phase.

## Phase 0 - Research & Baseline
Status: Completed (2025-09-26)
Objectives:
- Capture Responses API and OpenAI SDK backend best practices and incorporate into design notes.
- Inventory analytics_memory core modules and map dependencies from analytics_shared and analytics_supervisor.
- Document current tool-calling pain points and SSE output expectations.
- Reference OpenAI Responses API reliability and tool orchestration guidance published May and September 2025 when defining standards.
Action Log:
- 2025-09-26: Reviewed latest OpenAI Responses API/tool calling updates and summarized implications for pipeline resiliency.
- 2025-09-26: Audited analytics_memory, analytics_shared, analytics_supervisor structure to inform consolidation mapping.

## Phase 1 - Package Consolidation Scaffold
Status: Completed (2025-09-26)
Objectives:
- Create unified `backend/analytics/` package rooted in analytics_memory codebase.
- Establish subpackages (`core`, `sql`, `flows`, `tools`, `streaming`) preserving existing entry points.
- Stub re-export layers to keep existing imports working until migration completes.
Detailed Tasks (Completed):
1. Scaffolded `backend/analytics/` directories and `__init__.py` files mirroring the target structure.
2. Migrated analytics_memory modules into the new package and kept compatibility via re-export stubs.
3. Added shim modules so legacy imports resolve to the unified package without behavior changes.
4. Updated backend imports (e.g., `main.py`, supervisor modules) to reference the new analytics namespace.
5. Verified baseline integrity by running lint-free imports and executing the analytics test target.
Testing Results:
- 2025-09-26: `pytest backend` (pass; covers analytics modules via shared fixtures).
Documentation Updates:
- 2025-09-26: Recorded structural consolidation details and follow-ups in this plan.
Completion Notes:
- New `analytics` package now serves as the canonical backend namespace while legacy modules proxy to it.
- Ready to merge shared models and events in Phase 2 without breaking existing endpoints.
## Phase 2 - Core Model & Event Merge
Status: Completed (2025-09-26)
Objectives:
- Merge shared dataclass or Pydantic models and workflow state definitions into `core/state.py`.
- Fold streaming and event emitters into `core/events.py` with consistent SSE schema.
- Align configuration loading and environment helpers under `core/context.py`.
Detailed Tasks (Completed):
1. Consolidated analytics_memory and supervisor models into `backend/analytics/core/state.py`, adding supervisor workflow tracking and clarification schemas with new exports.
2. Migrated streaming emitters into `backend/analytics/core/events.py` and backfilled shims for legacy imports.
3. Introduced `backend/analytics/core/context.py` to centralize config/runtime helpers and updated downstream imports.
4. Updated supervisor modules and workflows to consume the unified models and event emitters while preserving behavior.
5. Added targeted tests under `backend/tests/analytics/test_state_models.py` covering state defaults and event payloads.
Testing Results:
- 2025-09-26: `pytest backend/tests/analytics/test_state_models.py` (pass).
- 2025-09-26: `pytest backend` (pass; validates flow-only dispatcher + analytics.* imports post-migration).
- 2025-09-26: `npm run build` (pass; ensures Memory page flow selector + telemetry compile).
Documentation Updates:
- 2025-09-26: Logged merged model ownership and runtime context notes here for future reference.
Completion Notes:
- Supervisor schemas now re-export from the analytics core module, keeping legacy imports functional.
- Event telemetry consumers (flows, tools) now route through the shared `analytics.core.events` layer ready for Phase 3 enhancements.

## Phase 3 - Supervisor Capability Integration
Status: Completed (2025-09-26)
Objectives:
- Port supervisor orchestration pieces (tools, cache, clarifications) into analytics_memory equivalents.
- Replace global registries with dependency-injected services compatible with flows.
- Ensure analytics_agent.py interfaces remain stable during consolidation.
Detailed Tasks (Completed):
1. Migrated the Redis-backed cache service into `backend/analytics/core/cache.py` with shared singleton helpers and removed the duplicate supervisor module.
2. Relocated the unified configuration store to `backend/analytics/core/config_store.py`, wiring it to the new cache/runtime context and keeping supervisor re-exports intact.
3. Rebased supervisor tool wrappers into `backend/analytics/tools/registry.py` with constructor injection for config stores and updated imports to the unified state models.
4. Updated analytics core modules to use relative imports and centralized state definitions for clarifications and SQL planners.
5. Added pytest coverage for cache fallback behaviour and tool registry integration using stub config stores.
Testing Results:
- 2025-09-26: `pytest backend/tests/analytics/test_cache_service.py backend/tests/analytics/test_tools_registry.py` (pass).
- 2025-09-26: `pytest backend` (pass; validates flow-only dispatcher + analytics.* imports post-migration).
- 2025-09-26: `npm run build` (pass; ensures Memory page flow selector + telemetry compile).
Documentation Updates:
- 2025-09-26: Logged supervisor integration status here; pending clarifications telemetry tweaks captured for Phase 5.
Completion Notes:
- Supervisor-facing modules now re-export the analytics equivalents, avoiding duplicate maintenance.
- Dependency injection stubs enable future removal of RAG dependencies without touching orchestrator entry points.

## Phase 4 - SQL Guidance Overhaul
Status: Completed (2025-09-26)
Objectives:
- Remove rag_service and related fetchers; rely on YAML-guided SQL suggestions.
- Build prompt builder using `config/schemas/*.yaml` data and hook into validator and executor pipeline.
- Harden SQL validation with allowlist derived from database.yaml and enhanced error reporting.
Action Log:
- 2025-09-26: Replaced supervisor RAG helpers with YAML-backed ConfigStore lookups and pruned legacy fast-lane paths.
- 2025-09-26: Added analytics-native SQL planner/prompt modules and telemetry-friendly template summaries.
- 2025-09-26: Upgraded validator and executor to analytics package, removing analytics_shared/sql dependencies.
Detailed Tasks (Completed):
1. Collapsed analytics_supervisor/rag_service.py into a disabled stub and rerouted all config lookups through the YAML catalogue.
2. Implemented `analytics/sql/templates.py` and `analytics/sql/prompt_builder.py` (LLM prompt assembly, template summaries).
3. Introduced `analytics/sql/executor.py` and updated callers (`workflow`, tools registry) to use the unified executor.
4. Replaced `sql_validate.py` with `analytics/sql/validator.py`, exporting compatibility shims for analytics_memory.
5. Added pytest coverage for prompt builder, cache service, and tools registry to exercise the new pipeline.
Testing Results:
- 2025-09-26: `pytest backend/tests/analytics/test_prompt_builder.py` (pass).
- 2025-09-26: `pytest backend` (pass; validates flow-only dispatcher + analytics.* imports post-migration).
- 2025-09-26: `npm run build` (pass; ensures Memory page flow selector + telemetry compile).
Documentation Updates:
- 2025-09-26: Logged SQL pipeline changes and follow-ups in this plan (docs refresh slated for Phase 7).
Completion Notes:
- SQL generation now uses YAML-derived context and the Responses API with deterministic template fallback.
- Validation/execution logic lives in `analytics/sql`, eliminating the analytics_shared dependency chain.

## Phase 5 - Flow Implementations
Status: Completed (2025-09-26)
Objectives:
- Recast core flows using the consolidated analytics package with explicit reasoning telemetry for the visualization demo.
- Deliver three showcase flows: planner-executor baseline, single-agent multi-tool, and lightweight multi-agent coordination.
- Ensure each flow emits comparable telemetry so the frontend can toggle between modes without schema drift.
Action Log:
- 2025-09-26: Rebuilt `analytics/flows/planner_executor.py` on top of the YAML-backed planner/validator to stream deterministic + LLM SQL events.
- 2025-09-26: Added `single_agent_tools.py` and `multi_agent.py` wrappers that emit `tool_call`, `agent_turn`, and `agent_reasoning` payloads for the demo overlays.
- 2025-09-26: Introduced the flow dispatcher (`workflow.py`) and threaded `mode`/`flow` parameters through FastAPI + frontend hooks.
- 2025-09-26: Migrated shared intent/charting/SQL helpers into `analytics.core`/`analytics.sql` and pointed supervisor/tool registry to the canonical modules.
Detailed Tasks (Completed):
1. Refactored the legacy workflow into `analytics/flows/planner_executor.py`, wiring state/events/sql to the YAML helpers.
2. Implemented `single_agent_tools.py` with per-tool telemetry and reasoning deltas.
3. Implemented `multi_agent.py` coordinating specialist roles with shared state and injected services.
4. Updated `backend/main.py` and React consumers to select flows based on request payload or demo mode.
5. Added flow-level pytest coverage (`backend/tests/analytics/test_flows_single_agent.py`, `test_flows_multi_agent.py`) to assert event ordering.
Testing Results:
- 2025-09-26: `pytest backend/tests/analytics/test_flows_single_agent.py backend/tests/analytics/test_flows_multi_agent.py` (pass).
- 2025-09-26: `pytest backend` (pass; validates flow-only dispatcher + analytics.* imports post-migration).
- 2025-09-26: `npm run build` (pass; ensures Memory page flow selector + telemetry compile).
Documentation Updates:
- 2025-09-26: Flagged new flow modes and telemetry requirements for follow-up documentation (Phase 7).
Completion Notes:
- Flow registry lives in `analytics/flows/workflow.py::get_available_flows()` and powers the Memory page selector.
- SSE streams now expose `tool_call`/`agent_*` enrichments alongside planner/executor events, enabling the visualization overlays.

## Phase 6 - Observability & Testing
Status: Completed (2025-09-26)
Objectives:
- Layer structured logging/tracing around Responses API calls, catalogue lookups, and clarification loops for demo playback.
- Expand pytest fixtures to cover error regressions and SSE contracts.
- Provide mocked tool-call transcripts for the right-panel visualization/monitoring surface.
Action Log:
- 2025-09-26: Added analytics/core/telemetry helpers and instrumented EventEmitter, TimedEventEmitter, and flow wrappers to emit catalog, tool, and analysis telemetry.
- 2025-09-26: Wired unified_responses_client to log Responses API call metrics (model, effort, duration, errors) for demo playback.
- 2025-09-26: Created regression coverage for catalog trace emission and fallback behavior via test_planner_catalog_trace.py.
- 2025-09-27: Hardened planner-executor fallback (validation + execution) with structured error codes, ProcessPanel telemetry, and new pytest coverage for template retry flows.
Detailed Tasks (Completed):
1. Instrumented unified client, SQL planner, and flow layers with JSON telemetry plus the new catalog_trace SSE event.
2. Expanded analytics tests to cover successful catalog traces, catalog lookup failures, and timing export behavior.
3. Integrated step timing exports through TimedEventEmitter to feed per-step latency snapshots.
4. Logged tool_iteration and analysis_chunk traces to power visualization overlays.
5. Captured residual observability considerations for future enhancements in this plan.
Testing Results:
- 2025-09-26: `pytest backend/tests/analytics/test_planner_catalog_trace.py` (pass).
- 2025-09-26: `pytest backend` (pass; 19 tests).
Documentation Updates:
- 2025-09-26: Refreshed telemetry details in ARCHITECTURE.md, AGENTS.md, and OPENAI_RESPONSES_GUIDE.md.
Completion Notes:
- Telemetry logger now centralizes catalog, tool, analysis, and timing metrics for the demo.
- Remaining observability work limited to future structured logging extensions, tracked as follow-ups.

## Phase 7 - Documentation & Frontend Touchpoints
Status: Completed (2025-09-26)
Objectives:
- Update `ARCHITECTURE.md`, `AGENTS.md`, `OPENAI_RESPONSES_GUIDE.md`, and frontend notes for the YAML-driven flow.
- Synchronize frontend expectations (event schema, tool labels, catalogue metadata) with the updated backend.
- Capture demo playbooks illustrating the three showcase modes.
Action Log:
- 2025-09-26: Refreshed `ARCHITECTURE.md` with unified analytics package details, flow selector semantics, and SSE telemetry.
- 2025-09-26: Expanded `AGENTS.md` with flow mode guidance and streaming event reference for the Memory visualizations.
- 2025-09-26: Removed the legacy Analysis Mode UI + `/api/analytics/memory/supervisor/stream`; Memory page flow selector now drives planner/single-agent/multi-agent badges and placeholders.
- 2025-09-26: Deleted `backend/analytics_memory`, `backend/analytics_shared`, and `backend/analytics_supervisor`; tests now fail fast if those modules reappear.
- 2025-09-26: Overhauled `OPENAI_RESPONSES_GUIDE.md` to describe the YAML-driven SQL planner, new flow wrappers, and tool telemetry.
Detailed Tasks (Completed):
1. Revise backend documentation to reflect the unified analytics package, YAML catalogue, and flow options.
2. Provide visualization guidance (event timelines, sample payloads, catalogue traces) for the frontend team via the updated docs.
3. Align frontend components (`WorkflowCanvas`, `useAnalyticsMemoryStream`, etc.) with new event names and tool labels (verified no extra changes beyond Phase 5).
4. Add final change log and overall testing summary to this file; flagged Phase 6 observability work as the remaining follow-up.
Testing Results:
- 2025-09-26: `pytest backend` (pass; validates flow-only dispatcher + analytics.* imports post-migration).
- 2025-09-26: `npm run build` (pass; ensures Memory page flow selector + telemetry compile).
- 2025-09-27: `pytest backend` (pass; verifies template fallback regression coverage).
- 2025-09-27: `npm run build` (pass; confirms ProcessPanel updates with error codes).
Documentation Updates:
- 2025-09-26: Captured documentation refresh details here and in the updated markdown files; remaining work tracked under Phase 6.

## Module Mapping Draft (legacy packages removed on 2025-09-26)
- analytics_memory.analysis -> analytics/core/analysis.py (maintain streaming insight helpers).
- analytics_memory.workflow -> analytics/flows/planner_executor.py (after refactor) with shared state from core/state.py.
- analytics_memory.intent and analytics_shared.intent -> analytics/core/intent.py consolidating clarification logic.\n- analytics_shared/intent package -> analytics/core/intent_impl/ (re-exported via analytics.core.intent).
- analytics_shared.database.executor -> analytics/sql/executor.py combining with analytics_memory.db.
- analytics_shared.sql.* -> analytics/sql/templates.py and analytics/sql/prompt_builder.py.\n- analytics_shared.charting.planner -> analytics/core/charting_impl.py (wrapped by analytics.core.charting.plan_chart_rule_based).
- analytics_supervisor.tools -> analytics/tools/registry.py with declarative tool metadata for visualization.
- analytics_supervisor.cache_service -> analytics/core/cache.py aligned with new dependency injection pattern.
- analytics_supervisor.schemas.WorkflowState -> analytics/core/state.py unified with analytics_memory types.
- analytics_shared.streaming.events -> analytics/streaming/events.py consumed by all flows and analytics_agent.py.








