# Next-Gen Analytics Agent Architecture - October 20, 2025

## 1. Project Overview
- The **next-gen analytics agent** delivers LangGraph-style orchestration on top of FastAPI (`backend/main.py`) using the Python modules under `backend/analytics`.
- The system supports three operating modes: deterministic planner-executor, single agent with explicit tool telemetry, and supervisor-led multi-agent. Each mode is exposed through SSE endpoints that feed the Vite UI.
- Product positioning (see `public/ai-projects.json`) highlights a unified UI that switches between direct, single-agent, and supervisor workflows, reuses cached SQL/RAG/chart artifacts, and targets a 60% improvement in clarification latency.
- This reference captures implementation details current to **October 20, 2025** and replaces the earlier agentic refactor notes.

## 2. Guiding Principles & Guardrails
- **Reuse the planner core.** `flows/planner_executor.PlannerExecutorFlow` stays the source of truth for SQL planning, execution, charting, and analysis so every mode shares identical business logic.
- **No legacy fallbacks.** Users only interact with agentic flows; sequential legacy pipelines were removed from runtime, though regression tests still compare against their outputs.
- **Observability first.** Flows annotate events via `flows.schedulers.apply_mode_metadata`, emit structured telemetry through `core.telemetry`, and persist tool receipts for replay or debugging.
- **Explicit caching.** Hashed `ToolInvocationReceipt` objects, `SessionStateSnapshot` helpers, and lane metadata make reuse versus fresh work auditable.
- **Incremental rollout.** Flow selection, revision handling, and telemetry toggles live inside Python rather than ad-hoc environment flags to reduce operational drift.

## 3. Flow Entry Points & Selection
- FastAPI exposes `/api/analytics/stream` and `/api/analytics/memory/stream` (see `backend/main.py`), both of which wrap helpers in `backend/analytics/flows/workflow.py`.
- `run_flow()` selects a factory from `FLOW_FACTORIES`, instantiates the requested flow, and streams `EventEmitter` payloads; instrumentation can be toggled per request.
- `analytics_memory_workflow()` adds follow-up routing, chart and analysis revision detection, and primes the flow with persisted session state before streaming results.

| Flow name        | Class (module)                                        | `FlowMode`            | Default label      | Typical usage                                                |
|------------------|-------------------------------------------------------|-----------------------|--------------------|--------------------------------------------------------------|
| `planner-executor` | `PlannerExecutorFlow` (`flows/planner_executor.py`)   | `FlowMode.DIRECT`     | `planner-executor` | Deterministic, sequential pipeline for reproducible runs.    |
| `single-agent`   | `SingleAgentController` (`flows/single_agent_tools.py`) | `FlowMode.SINGLE_AGENT` | `single-agent`     | Single-agent UX with tool telemetry and cohesive synthesis.  |
| `multi-agent`    | `MultiAgentFlow` (`flows/multi_agent.py`)               | `FlowMode.MULTI_AGENT` | `multi-agent`      | Supervisor plus specialists orchestrated by the agent DAG.   |

The `FollowUpClassifier` (`routing/follow_up_classifier.py`) runs ahead of every session to decide whether to reuse SQL, run stock-only updates, or execute the full pipeline; flows receive the `FollowUpRoute` via `set_follow_up_route()`.

## 4. Shared Pipeline Stages
### 4.1 Intent Qualification & Clarification
- Classification and gating use `core.intent.classify_query_async`, `detect_intent`, and `post_process_slots`, with intermediate state captured on `PlannerPhaseContext`.
- Slot resolution combines rule-based slot status (`core.intent_impl.models.SlotStatusModel`), LLM intent resolution (`core.intent_impl.detection.resolve_intent_slots_async`), and clarifier prompts.
- `agents/schema_clarifier.decide_schema_clarification` validates template requirements (`sql.template_requirements`) and decides whether to clarify, assume, or decline missing fields.
- Clarification loops rely on `core.clarify` helpers (`compute_required_clarifications`, `validate_clarification_answer`, `wait_for_answer_blocking`) with telemetry emitted via `telemetry.intent_resolution`.

### 4.2 Planning, Templates & SQL Generation
- `sql.sql_planner.plan_sql_rule_based` builds a provisional plan using the semantic catalog (`semantic/catalog.py`) and normalized metrics.
- Template lookup (`sql.templates.fetch_templates_for_intent`, `sql.sql_planner.choose_template`) surfaces YAML-backed plans stored in `core.config_store`.
- `PlannerPhaseContext` tracks candidate templates, criteria, and intent signatures for downstream reuse and revision detection.
- SQL code is compiled and validated through `sql.compiler.compile_sql_from_plan` and `sql.validator.validate_sql`; failures populate `PipelineArtifacts.sql_generation.attempts` and drive retry prompts.

### 4.3 Execution, Charting & Narrative Synthesis
- `sql.executor.execute_sql` runs queries against analytics sources, producing sample rows, tickers, and column metadata for artifacts.
- Charting logic (`core.charting.plan_chart_rule_based`, `core.charting.build_chart_spec`, `core.charting_impl`) translates datasets into ECharts-friendly specs, including legend ordering and metric-specific defaults.
- Narrative generation leverages `core.analysis.stream_insights_llm` and `summarize` to fuse SQL, chart, market, and web findings into analysis chunks.
- Validators in `validators/cohesive_result.py` ensure the final cohesive payload contains required sections before emission.

### 4.4 Artifacts, Receipts & Snapshotting
- Artifacts are tracked via `artifacts/models.py` (`PipelineArtifacts`, `SQLGenerationArtifact`, `SQLExecutionArtifact`, `ChartArtifact`, `AnalysisArtifact`, `MarketArtifact`, `WebContextArtifact`).
- Tool receipts use `ToolInvocationReceipt` (hashes, attempt counts, reused flags) attached to `PlannerPhaseContext` and persisted through `SessionStateSnapshot.record_tool_receipt`.
- Session state (`core/session_state.py`) records last SQL, chart, analysis, tool cache, and schedule history with Redis (or in-memory) storage and a TTL bounded between 1 and 15 minutes.
- Revision snapshots (`core/revision_snapshot`) capture query signatures and artifact snapshots for targeted reruns.

## 5. Flow Implementations
### 5.1 Planner-Executor (Deterministic Mode)
- `PlannerExecutorFlow.events()` wraps the planner pipeline, annotates events with `apply_mode_metadata`, and yields sequential progress: classification -> intent -> SQL -> chart -> analysis.
- Streaming uses `TimedEventEmitter` for consistent timestamps and latency metrics; key artifact events include `sql_ready`, `chart_ready`, `stock_ready`, `web_ready`, and `analysis_ready`.
- `run_planner_executor()` exposes a backwards-compatible helper for legacy callers and unit tests.
- Receipts are updated after each stage, enabling downstream flows to reuse results; when reused, payloads include `{"reused": true, "snapshot_age_seconds": ...}`.

### 5.2 Single-Agent Controller
- `SingleAgentController` composes the planner core with tool metadata from `pipeline_tools.get_planner_tool_registry()` and exposes a manifest consumed by the frontend.
- Fan-out adapters (`MarketQuestionAdapter`, `StockTrackerAdapter`, `WebRetrieverAdapter`) run inside `ToolTaskGroup` with lane-aware concurrency: the market lane allows three parallel calls (two questions plus the stock tracker), while the web lane is serialized.
- Tool lifecycle events (`tool_call` start and end) include latency budgets, output artifact hints, and follow-up routing info; telemetry mirrors these updates via `telemetry.tool_iteration`.
- Analysis completion (`analysis_complete`) triggers `_build_single_agent_cohesive_payload`, which merges planner artifacts, web context, stock widgets, and tool manifests into a single `cohesive_result`.
- Cached receipts respect `LANE_TOOL_MAP` and `LANE_CONCURRENCY_LIMITS`; cache TTL defaults to 600 seconds to keep market data fresh without thrashing APIs.

### 5.3 Multi-Agent Supervisor Flow
- `MultiAgentFlow` orchestrates planner reuse with specialist agents coordinated by `AgentExecutionOrchestrator` (`flows/orchestrator.py`).
- Agent specifications are registered via `AgentSpec` entries with capability metadata, latency budgets, and evaluation hooks; tasks are declared in `AgentTaskPlan` and `AgentTaskStep`.
- The supervisor issues DAGs where planner, SQL, chart, market, web, and analyst agents run concurrently as dependencies allow. `ROLE_LANES` and `ROLE_PARALLEL_GROUPS` map events back to canvas lanes for the UI.
- Cached receipts refresh when stale based on `RECEIPT_TTL_SECONDS` (default 600 seconds); hedged web tooling (`HEDGED_WEB_TOOLS`) lets live and cached web retrieval race safely.
- Final narratives pass through `CohesiveResultValidator` before emitting a single `cohesive_result`; errors surface as `cohesive_result_error` events with missing field diagnostics.

## 6. Tool Ecosystem & Data Providers
- `get_planner_tool_registry()` enumerates planner-accessible tools, aligning metadata with the `TOOL_METADATA_*` maps used by single- and multi-agent flows.
- `collect_tool_bundle()` aggregates stock widgets, web context, and tool results into reusable bundles stored on artifacts and emitted to the UI.
- `flows/tooling.py` defines `ToolTaskGroup`, `ToolExecutionContext`, and adapters that call downstream services:
  - Polygon market data via `services/polygon.PolygonMarketDataClient` and `fetch_daily_snapshot`.
  - Web context via `services/response_search.perform_response_search`, with guardrails (`ResponseSearchError`, latency buckets, cache hints).
  - Stock widgets through the internal tracker adapter, ensuring symbols and metadata are normalized.
- Supervisor-facing tools (`tools/registry.SupervisorTools`) expose function-call schemas for template lookup, metric search, company lookup, and analytics context retrieval so LLM agents stay deterministic.

## 7. Session Memory, Revisions & Follow-Ups
- `SessionStateRepository` lazily instantiates Redis clients (or logs an in-memory fallback) and enforces TTLs via `_read_ttl_from_env()`. Helper methods record queries, tool results, artifacts history, and schedule events.
- Revision helpers (`flows/chart_revision.py`, `RevisionContext`) enrich revision requests with prior SQL, dataset previews, and analysis history. Chart and analysis revisions emit events via `PlannerExecutorFlow.emit_chart_patch` and `emit_analysis_revision`.
- `analytics_memory_workflow()` detects revision intent with `chart_revision.is_chart_revision_query` and `analysis_revision` helpers before running the main flow.
- `FollowUpClassifier` inspects the latest snapshot to choose `FollowUpRoute.STOCK_ONLY`, `REUSE_SQL`, or `FULL_PIPELINE`, optimizing reruns for follow-up questions.

## 8. Event Streaming & Telemetry
- `core.events.EventEmitter` and `TimedEventEmitter` standardize progress, result, error, and status payloads; data is sanitized through `validators.sanitize_for_json`.
- `flows.instrumentation.instrument_events` wraps flows to attach timing metrics, SQL attempts, and telemetry counters without modifying the underlying pipeline.
- `core.telemetry` exposes structured log emitters (`intent_resolution`, `tool_iteration`, `tool_parallelism`, `analysis_chunk`, `agent_handoff`, `policy_decision`), all routed to the `analytics.telemetry` logger.
- Example payload emitted after a reused SQL replay:
  ```json
  {
    "event": "sql_ready",
    "data": {
      "schedule_stage": "sql",
      "reused": true,
      "row_count": 128,
      "snapshot_age_seconds": 42.0,
      "ts": "2025-10-20T05:12:31.418176"
    }
  }
  ```
- Concurrency metadata (`batch_id`, `concurrency_level`, lanes) is included where available so the frontend canvases can render parallel stages faithfully.

## 9. API Surface & Frontend Contracts
- The SSE endpoints stream JSON events that the Vite frontend renders inside components such as `components/analytics/common/ProcessPanel` and `components/analytics/WorkflowCanvas`. Lanes are derived from the same mappings (`LANE_TOOL_MAP`, `ROLE_LANES`) used in the flows.
- Key events expected by the UI include `session_started`, `classification`, `intent_detection`, `clarification_request`, `sql_ready`, `chart_ready`, `stock_ready`, `web_ready`, `analysis_complete`, `cohesive_result`, `final_answer`, and `workflow_complete`.
- `SessionStateSnapshot.schedule_history` mirrors `FlowSchedule` definitions from `flows/schedulers.py`, enabling ledger visualizations and follow-up heuristics.
- Revision flows annotate events with `{"reason": "revision_request", "source": "analytics_memory_workflow"}` so the frontend can badge revision responses.

## 10. Testing, Quality & Operations
- Python tests live under `backend/tests/analytics/`. Existing suites cover revision routing (`test_revision_routing.py`) and should be expanded to assert multi-agent DAG orderings, cohesive result validation, and cache reuse logic.
- Run `pytest backend/tests/analytics` before shipping backend changes; tests rely on mocked services for Polygon and response search.
- Frontend Vitest coverage (see `docs/analytics-canvas-overview.md`) should validate lane rendering, telemetry overlays, and cohesive card updates.
- Logging relies on the `analytics.telemetry` logger; configure sinks via standard `logging` config or FastAPI startup hooks.
- Environment variables: `REDIS_URL` (session state), `WEB_SEARCH_GUARDRAIL_P50_MS`, `WEB_SEARCH_GUARDRAIL_P95_MS`, and tool API keys handled in `.env`. The project expects `npm install` + `npm run dev` for the frontend and `py -m uvicorn main:app --reload --port 8000` for the backend.

## 11. Roadmap & Focus Areas
- **Supervisor parity:** Finalize multi-agent telemetry so planner, market, web, and chart lanes emit consistent `tool_call` metadata and cohesive payloads before expanding agent roles.
- **Cache diagnostics:** Surface diagnostics for stale receipts (age, hash mismatches) to ease debugging of `RECEIPT_TTL_SECONDS` decisions.
- **Test coverage:** Backfill pytest suites for multi-agent DAG evaluation and single-agent cohesive payloads, plus Vitest snapshots for revision flows.
- **Operational hardening:** Instrument Polygon and response search latency guardrails with alerts, and monitor Redis fallback logs to catch misconfigurations early.

---

This architecture reference reflects the current state of the `next-gen-analytics-agent` project and should be updated alongside significant planner, tool, or telemetry changes.
