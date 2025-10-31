# Next-Gen Analytics Agent Architecture - October 26, 2025

## 1. Project Overview
- The **next-gen analytics agent** delivers LangGraph-style orchestration on top of FastAPI (`backend/main.py`) using the Python modules under `backend/analytics`.
- The system supports three operating modes: deterministic planner-executor, single agent with explicit tool telemetry, and supervisor-led multi-agent. Each mode is exposed through SSE endpoints that feed the Vite UI.
- Product positioning (see `public/ai-projects.json`) highlights a unified UI that switches between direct, single-agent, and supervisor workflows, reuses cached SQL/RAG/chart artifacts, and targets a 60% improvement in clarification latency.
- The October 26 refresh folds in Gemini-planned multi-topic web fan-out (`flows/tooling.WebRetrieverAdapter.expand`), ranking and operating leverage intent heuristics (`core.intent_impl.detection.heuristic_intent` + `normalization`), and latency guardrails plus cache orchestration that span `flows/planner_executor.py`, `core/cache.py`, and `services/response_search.py`.
- This reference captures implementation details current to **October 26, 2025** and replaces the earlier agentic refactor notes.

## 2. Guiding Principles & Guardrails
- **Reuse the planner core.** `flows/planner_executor.PlannerExecutorFlow` stays the source of truth for SQL planning, execution, charting, and analysis so every mode shares identical business logic.
- **No legacy fallbacks.** Users only interact with agentic flows; sequential legacy pipelines were removed from runtime, though regression tests still compare against their outputs.
- **Observability first.** Flows annotate events via `flows.schedulers.apply_mode_metadata`, emit structured telemetry through `core.telemetry`, and now attach latency guardrail payloads (`planner_executor._evaluate_latency_guardrail`) so web fan-out breaches surface immediately.
- **Cache circuit-breakers.** `core.cache.CacheService` fronts Redis with warm handshakes, circuit-breaker thresholds, and in-process fallbacks, keeping `core.config_store.ConfigStore` responsive even when Redis is unavailable.
- **Explicit caching.** Hashed `ToolInvocationReceipt` objects, `SessionStateSnapshot` helpers, and lane metadata make reuse versus fresh work auditable; merged tool bundles tag topic counts and reuse flags so the UI can badge cached accessories.
- **Incremental rollout.** Flow selection, revision handling, and telemetry toggles live inside Python rather than ad-hoc environment flags to reduce operational drift.

## 3. Flow Entry Points & Selection
- FastAPI exposes `/api/analytics/stream` and `/api/analytics/memory/stream` (see `backend/main.py`), both of which wrap helpers in `backend/analytics/flows/workflow.py`.
- `analytics_memory_workflow()` selects a factory from `FLOW_FACTORIES`, primes the flow instance with revision context, and streams `EventEmitter` payloads. Instrumentation toggles are handled inline via `_env_flag("ANALYTICS_MEMORY_INSTRUMENT")`.
- Session snapshotting, follow-up routing, and revision lane targeting all funnel through this helper before the chosen flow's `.events()` coroutine runs.

| Flow name        | Class (module)                                        | `FlowMode`            | Default label      | Typical usage                                                |
|------------------|-------------------------------------------------------|-----------------------|--------------------|--------------------------------------------------------------|
| `planner-executor` | `PlannerExecutorFlow` (`flows/planner_executor.py`)   | `FlowMode.DIRECT`     | `planner-executor` | Deterministic, sequential pipeline for reproducible runs.    |
| `single-agent`   | `SingleAgentController` (`flows/single_agent_tools.py`) | `FlowMode.SINGLE_AGENT` | `single-agent`     | Single-agent UX with tool telemetry and cohesive synthesis.  |
| `multi-agent`    | `MultiAgentFlow` (`flows/multi_agent.py`)               | `FlowMode.MULTI_AGENT` | `multi-agent`      | Supervisor plus specialists orchestrated by the agent DAG.   |

The `FollowUpClassifier` (`routing/follow_up_classifier.py`) runs ahead of every session to decide whether to reuse SQL, run stock-only updates, or execute the full pipeline; flows receive the `FollowUpRoute` via `set_follow_up_route()`.

## 4. Shared Pipeline Stages
### 4.1 Intent Qualification & Clarification
- Classification and gating use `core.intent.classify_query_async`, `detect_intent`, and `post_process_slots`, with the revamped heuristic detector spotting ranking/peer comparisons (`heuristic_intent`) and falling back to LLM resolution only when confidence < 0.70.
- Slot resolution combines rule-based status (`core.intent_impl.models.SlotStatusModel`), LLM follow-ups (`core.intent_impl.detection.resolve_intent_slots_async`), and normalization helpers (`core.intent_impl.normalization.normalize_timeframe`, `normalize_metrics`, `normalize_granularity`, `timeframe_implies_quarterly`) to align slots with template expectations.
- `agents/schema_clarifier.decide_schema_clarification` validates template requirements (`sql.template_requirements`) and decides whether to clarify, assume, or decline missing fields; company defaults now leverage `normalization.get_default_tickers`.
- Clarification loops rely on `core.clarify` helpers (`compute_required_clarifications`, `validate_clarification_answer`, `wait_for_answer_blocking`) backed by the new in-memory `SessionStore`; telemetry still emits via `telemetry.intent_resolution` while cached answers expire after 10 minutes.

### 4.2 Planning, Templates & SQL Generation
- `sql.sql_planner.plan_sql_rule_based` builds a provisional plan using the semantic catalog (`semantic/catalog.py`) and normalized metrics, while new intents (`operating_leverage_yoy_vs_peers`, `eps_yoy_rank_latest`, `capex_intensity_latest_rank`, `rnd_intensity_vs_peers`) add comparison defaults and peer heuristics.
- Template lookup (`sql.templates.fetch_templates_for_intent`, `sql.sql_planner.choose_template`) surfaces YAML-backed plans stored in `core.config_store`, which now leans on `core.cache.CacheService` to avoid redundant YAML parsing.
- `PlannerPhaseContext` tracks candidate templates, criteria, tool receipts, and intent signatures for downstream reuse and revision detection; it also records seeded accessories (`web_search_seeded`, `stock_widget_seeded`), revision directives, and latency stats for guardrail evaluation.
- SQL code is compiled and validated through `sql.compiler.compile_sql_from_plan` and `sql.validator.validate_sql`; failures populate `PipelineArtifacts.sql_generation.attempts` and drive retry prompts.

### 4.3 Execution Lanes & Narrative Synthesis
- `flows/planner/sql_lane.stream_sql_lane` orchestrates SQL execution and reuse, emitting `sql_ready` with `lane: "sql"` plus `parallel_group: "core_sequential"` when cached payloads are replayed. Fresh runs call `sql.executor.execute_sql` to hydrate sample rows, tickers, and column metadata.
- `stream_chart_lane` blends `compose_chart_ready_payload` with `core.charting.plan_chart_rule_based`/`build_chart_spec`; recent updates normalize axis ordering, enforce quarterly granularity when intent slots demand it, and propagate legend colors for peer comparisons.
- `flows/planner/analysis_lane.stream_analysis_lane` now streams via `stream_insights_llm`, merging accessory bundles, applying latency guardrails (`latency_guardrail` payload), and emitting `analysis_revision` hooks when revision directives request insight-focused rewrites.
- Validators in `validators/cohesive_result.py` still gate the cohesive payload, while `mark_revision_completion` (from `flows/planner/revision.py`) marks lanes complete for revision-aware consumers and carries forward `analysis_revision_history` for audit.

### 4.4 Tool Fan-Out & Accessory Prefetch
- Tool fan-out starts via `flows/planner.fanout.start_tool_parallelism`, which buffers adapter output on an async queue while `derive_accessory_events` synthesizes `stock_ready`/`web_ready` deltas stamped with lane metadata.
- `PlannerPipeline._fanout_adapters_for_context()` selects adapters (e.g., `StockTrackerAdapter`, `WebRetrieverAdapter`) when `ModeConfig.parallelism_enabled` is true; the web adapter now calls `services.response_search.generate_search_topics` to split a single user query into multiple topic-specific adapters when an API key is present.
- Accessory payloads are merged through `collect_tool_bundle` and `_merge_web_payloads`, deduping snippets, aggregating topic annotations, and surfacing `topic_count`, `search_topics`, and `latency_ms` so downstream lanes have a single coherent context.
- `ensure_analysis_dependencies` backfills missing accessories by racing cached receipts with live tool invocations, emitting cache-hit telemetry when reused data short-circuits execution.
- Example accessory delta:
  ```json
  {
    "event": "web_ready",
    "data": {
      "schedule_stage": "hedged_accessories",
      "parallel_group": "tool_fanout",
      "lane": "web",
      "flow_mode": "direct",
      "reused": false,
      "web_context": {
        "query": "Nvidia margin outlook",
        "search_topics": [
          "Nvidia margin outlook 2025",
          "GPU peers operating leverage"
        ],
        "summary": "Topic 1 recaps Nvidia commentary...\n\nTopic 2 captures peer comparisons...",
        "topic_count": 2,
        "latency_ms": 1270,
        "from_cache": false
      }
    }
  }
  ```

### 4.5 Artifacts, Receipts & Snapshotting
- Artifacts are tracked via `artifacts/models.py` (`PipelineArtifacts`, `SQLGenerationArtifact`, `SQLExecutionArtifact`, `ChartArtifact`, `AnalysisArtifact`, `MarketArtifact`, `WebContextArtifact`); web artifacts now capture `latency_stats` and merged topic summaries for guardrail evaluation.
- Tool receipts use `ToolInvocationReceipt` (hashes, attempt counts, lane hints, metadata) attached to `PlannerPhaseContext` and persisted through `SessionStateSnapshot.record_tool_receipt`; metadata tracks guardrail outcomes and reused accessories.
- Session state (`core/session_state.py`) records last SQL, chart, analysis, tool cache, and schedule history with Redis (or in-memory) storage and a TTL bounded between 1 and 15 minutes, and now stores `analysis_revision_history`/`chart_revision_history` for audit.
- Revision snapshots (`core/revision_snapshot`) capture query signatures and artifact snapshots for targeted reruns; `flows/planner/revision.build_revision_plan` narrows reruns to the lanes that actually need fresh work and can trigger analysis-only revisions when `revision_targets` exclude SQL/chart.

## 5. Flow Implementations
### 5.1 Planner-Executor (Deterministic Mode)
- `PlannerExecutorFlow.events()` delegates to `PlannerPipeline` to run lane-specific helpers (`stream_sql_lane`, `stream_chart_lane`, `stream_analysis_lane`) after classification, applying `apply_mode_metadata` to every delta.
- Streaming pairs `TimedEventEmitter` with `ToolParallelRuntime` so mode configs can enable hedged accessories without blocking the core SQL lane; emitted artifacts include lane + parallel group metadata for the canvas.
- Cached snapshots seed the pipeline through `_seed_web_search_from_payload` and `_seed_stock_widget_from_payload`, allowing revision runs to reuse accessories before new fan-out kicks off.
- `PlannerExecutorFlow.get_prompt_versions()` exposes inline prompt registries (replacing `prompt_versions.py`) so downstream flows can display current prompt fingerprints.
- `run_planner_executor()` exposes a backwards-compatible helper for legacy callers and unit tests, while receipts update after each stage with `snapshot_age_seconds`, guardrail status, and reuse flags for UI badging.

### 5.2 Single-Agent Controller
- `SingleAgentController` composes the planner core with tool metadata from `pipeline_tools.get_planner_tool_registry()`, piggybacks on `PlannerPipeline.events`, and exposes a manifest consumed by the frontend.
- Fan-out adapters (`MarketQuestionAdapter`, `StockTrackerAdapter`, `WebRetrieverAdapter`) reuse the planner's `ToolParallelRuntime`; the web adapter expands into topic-specific adapters, while market adapters remain hedged but rate-limited to avoid Polygon throttling.
- Tool lifecycle events (`tool_call` start and end) include latency budgets, topic labels, output artifact hints, and follow-up routing info; telemetry mirrors these updates via `telemetry.tool_iteration`.
- Analysis completion (`analysis_complete`) triggers `_build_single_agent_cohesive_payload`, which now merges latency guardrail verdicts, topic-level snippets, and tool manifests into a single `cohesive_result`.
- Cached receipts respect `LANE_TOOL_MAP` and `LANE_CONCURRENCY_LIMITS`; receipts store prompt versions and guardrail outcomes so cache hits remain explainable.

### 5.3 Multi-Agent Supervisor Flow
- `MultiAgentFlow` orchestrates planner reuse with specialist agents coordinated by `AgentExecutionOrchestrator` (`flows/orchestrator.py`).
- Agent specifications are registered via `AgentSpec` entries with capability metadata, latency budgets, and evaluation hooks; tasks are declared in `AgentTaskPlan` and `AgentTaskStep`.
- The supervisor issues DAGs where planner, SQL, chart, market, web, and analyst agents run concurrently as dependencies allow. `ROLE_LANES` and `ROLE_PARALLEL_GROUPS` map events back to canvas lanes for the UI.
- Prompt fingerprints live on the `_PROMPT_VERSIONS` class attribute so agent manifests expose the same metadata as the planner.
- Cached receipts refresh when stale based on `RECEIPT_TTL_SECONDS` (default 600 seconds); hedged web tooling handles per-topic adapters (`web_retriever_topic-*`) by aggregating payloads before they hit the shared context.
- `analysis_revision` steps route through the insight reviewer agent when follow-ups request narrative tweaks, while planner reuse skips SQL/chart when `revision_plan.stock_only` or analysis-only targets are active.
- Final narratives pass through `CohesiveResultValidator` before emitting a single `cohesive_result`; errors surface as `cohesive_result_error` events with missing field diagnostics.

## 6. Tool Ecosystem & Data Providers
- `get_planner_tool_registry()` enumerates planner-accessible tools, aligning metadata with the `TOOL_METADATA_*` maps used by single- and multi-agent flows.
- `collect_tool_bundle()` aggregates stock widgets, web context, and tool results into reusable bundles stored on artifacts and emitted to the UI; merged web payloads now include deduped snippets, topic annotations, and latency stats.
- `flows/tooling.py` defines `ToolTaskGroup`, `ToolExecutionContext`, `ToolAdapterResult`, and adapters that call downstream services:
  - Polygon market data via `services/polygon.PolygonMarketDataClient` and `fetch_daily_snapshot`, with guardrails for stale quotes.
  - Web context via `services/response_search.generate_search_topics` + `perform_response_search`, producing topic plans before issuing Gemini-powered searches and surfacing cache hints/latency telemetry.
  - Stock widgets through the internal tracker adapter, ensuring symbols and metadata are normalized and can be reused for stock-only follow-ups.
- Supervisor-facing tools (`tools/registry.SupervisorTools`) expose function-call schemas for template lookup, metric search, company lookup, and analytics context retrieval so LLM agents stay deterministic.

## 7. Session Memory, Revisions & Follow-Ups
- `SessionStateRepository` lazily instantiates Redis clients (or logs an in-memory fallback) and enforces TTLs via `_read_ttl_from_env()`. Helper methods record queries, tool results, artifacts history, analysis/chart revision history, and schedule events for later fan-out decisions.
- Revision helpers (`flows/chart_revision.py`, `RevisionContext`, `flows/planner/revision.py`) enrich revision requests with prior SQL, dataset previews, and analysis history. `build_revision_plan` + `derive_revision_targets` decide which lanes re-run, while `mark_revision_completion` stops redundant delta emissions and `emit_analysis_revision` streams narrative-only patches.
- `analytics_memory_workflow()` detects revision intent with `chart_revision.is_chart_revision_query` and `analysis_revision` helpers before running the main flow, optionally short-circuiting to the stock-only lane when `revision_plan.stock_only` is set or reusing cached accessories when `ctx.web_search_seeded` is true.
- `FollowUpClassifier` inspects the latest snapshot (including which lanes have reusable artifacts) to choose `FollowUpRoute.STOCK_ONLY`, `REUSE_SQL`, or `FULL_PIPELINE`, trimming revision targets to lanes that actually exist in the snapshot.

## 8. Event Streaming & Telemetry
- `core.events.EventEmitter` and `TimedEventEmitter` standardize progress, result, error, and status payloads; data is sanitized through `validators.sanitize_for_json` and now includes prompt fingerprints via `prompt_versions`.
- `flows.instrumentation.instrument_events` wraps flows to attach timing metrics, SQL attempts, telemetry counters, and lane mappings without modifying the underlying pipeline; it maps `analysis_revision` into the analysis lane for dashboards.
- `core.telemetry` exposes structured log emitters (`intent_resolution`, `tool_iteration`, `tool_parallelism`, `analysis_chunk`, `analysis_revision`, `agent_handoff`, `policy_decision`), all routed to the `analytics.telemetry` logger alongside latency guardrail verdicts.
- Example payload emitted after a reused SQL replay (note the lane + parallel group metadata and prompt versions used by the canvas):
  ```json
  {
    "event": "sql_ready",
    "data": {
      "schedule_stage": "sql",
      "parallel_group": "core_sequential",
      "lane": "sql",
      "flow_mode": "direct",
      "reused": true,
      "row_count": 128,
      "snapshot_age_seconds": 42.0,
      "prompt_versions": {
        "schema_clarifier": "2025-10-16",
        "multi_agent.supervisor": "2025-10-16"
      },
      "ts": "2025-10-26T05:12:31.418176"
    }
  }
  ```
- Concurrency metadata (`batch_id`, `concurrency_level`, lanes) is included where available so the frontend canvases can render parallel stages faithfully.

## 9. API Surface & Frontend Contracts
- The SSE endpoints stream JSON events that the Vite frontend renders inside components such as `components/analytics/common/ProcessPanel` and `components/analytics/WorkflowCanvas`. Lanes are derived from the same mappings (`LANE_TOOL_MAP`, `ROLE_LANES`) used in the flows.
- Key events expected by the UI include `session_started`, `classification`, `intent_detection`, `clarification_request`, `revision_request`, `sql_ready`, `chart_ready`, `stock_ready`, `web_ready`, `analysis_revision`, `analysis_complete`, `cohesive_result`, `final_answer`, and `workflow_complete`; error paths mirror these (e.g., `analysis_revision_error`).
- `SessionStateSnapshot.schedule_history` mirrors `FlowSchedule` definitions from `flows/schedulers.py`, enabling ledger visualizations and follow-up heuristics.
- Revision flows annotate events with `{"reason": "revision_request", "source": "analytics_memory_workflow"}` so the frontend can badge revision responses, while accessory payloads ship `topic_count`, `search_topics`, `latency_stats`, and guardrail verdicts for richer UI indicators.

## 10. Testing, Quality & Operations
- Python tests live under `backend/tests/analytics/`. Recent suites cover comparison fans (`test_chart_comparison.py`), clarification heuristics (`test_clarify_comparison.py`, `test_intent_slot_resolution.py`), and telemetry (`test_intent_resolution_telemetry.py`); keep adding fan-out assertions to ensure multi-topic web payloads merge correctly.
- Run `pytest backend/tests/analytics` before shipping backend changes; tests rely on mocked services for Polygon and response search, and new cases should stub `ToolParallelRuntime` queues plus Gemini topic planners to avoid async flakiness.
- Frontend Vitest coverage (see `docs/analytics-canvas-overview.md`) should validate lane rendering, topic badges, latency guardrail indicators, and cohesive card updates.
- Logging relies on the `analytics.telemetry` logger; configure sinks via standard `logging` config or FastAPI startup hooks, and ensure guardrail outputs flow to your log aggregation.
- Environment variables: `REDIS_URL`, `WEB_SEARCH_GUARDRAIL_P50_MS`, `WEB_SEARCH_GUARDRAIL_P95_MS`, `WEB_SEARCH_TIMEOUT_SECONDS`, `WEB_SEARCH_MAX_TOPICS`, `WEB_SEARCH_RETRY_ATTEMPTS`, `GEMINI_SEARCH_MODEL`, `GEMINI_SEARCH_TEMPERATURE`, plus tool API keys handled in `.env`. The project expects `npm install` + `npm run dev` for the frontend and `py -m uvicorn main:app --reload --port 8000` for the backend.


---

## 12. Legacy Cleanup (Completed: October 31, 2025)
- Removed `backend/analytics/artifacts/spike_artifacts.py` along with the `classification_from_event` / `intent_from_event` shims so downstream code relies exclusively on the dataclass artifacts in `analytics.artifacts.models`.
- Deleted the placeholder `summarize` helper from `backend/analytics/core/analysis.py`, ensuring narrative streaming always flows through `stream_insights_llm`.
- Dropped compatibility aliases `backend/analytics/sql/db.py` and `backend/analytics/sql/sql_validate.py`, and inlined the unused `execute_sql_with_limit` / `quick_validate_sql_syntax` helpers; callers import directly from `analytics.sql.executor` / `analytics.sql.validator`.
- Retired unused convenience APIs (`core.events.emit_progress|emit_result|emit_error`, `core.telemetry.timed_metric`, `flows/workflow.run_flow`, `flows/workflow.get_available_flows`, `flows/workflow._extract_revision_snapshot`, `flows/planner_executor._env_flag`, `core.config_store.close_config_store`) to tighten the supported surface.
- Trimmed dead artifact utilities (`_clone_dict`, `_clone_list`) and refreshed documentation to note that `analytics_memory_workflow()` now orchestrates flow selection and instrumentation inline.


This architecture reference reflects the current state of the `next-gen-analytics-agent` project and should be updated alongside significant planner, tool, or telemetry changes.
