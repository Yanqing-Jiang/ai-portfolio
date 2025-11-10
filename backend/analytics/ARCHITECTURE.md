# Next-Gen Analytics Agent Architecture - November 6, 2025

## 1. Project Overview
- The **next-gen analytics agent** delivers LangGraph-style orchestration on top of FastAPI (`backend/main.py`) using the Python modules under `backend/analytics`.
- The system supports three operating modes: deterministic planner-executor, single agent with explicit tool telemetry, and supervisor-led multi-agent. Each mode is exposed through SSE endpoints that feed the Vite UI.
- Product positioning (see `public/ai-projects.json`) highlights a unified UI that switches between direct, single-agent, and supervisor workflows, reuses cached SQL/RAG/chart artifacts, and targets a 60% improvement in clarification latency.
- The November 6 refresh layers the shared `flows/sequencer.PlannerSequencer` + `PlannerEventBus` lane governance, `flows/orchestrator_adapter.PlannerOrchestratorAdapter`, the OpenAI `AgentsStreamBridge`, and `flows/supervisor_retry_manager.SupervisorRetryManager` guardrails so sequencer events, agents, and supervisor retries stay aligned across modes.
- This reference captures implementation details current to **November 6, 2025** and replaces the earlier agentic refactor notes.

## 2. Guiding Principles & Guardrails
- **Reuse the planner core.** `flows/planner_executor.PlannerExecutorFlow` stays the source of truth for SQL planning, execution, charting, and analysis so every mode shares identical business logic.
- **No legacy fallbacks.** Users only interact with agentic flows; sequential legacy pipelines were removed from runtime, though regression tests still compare against their outputs.
- **Observability first.** Flows annotate events via `flows.schedulers.apply_mode_metadata`, emit structured telemetry through `core.telemetry`, and now attach latency guardrail payloads (`planner_executor._evaluate_latency_guardrail`) so web fan-out breaches surface immediately.
- **Cache circuit-breakers.** `core.cache.CacheService` fronts Redis with warm handshakes, circuit-breaker thresholds, and in-process fallbacks, keeping `core.config_store.ConfigStore` responsive even when Redis is unavailable, and now persists per-session agent run metadata (run IDs, retry counts, failure flags) via `CacheService.set_agent_metadata` so supervisors can resume or audit long-running tasks.
- **Explicit caching.** Hashed `ToolInvocationReceipt` objects, `SessionStateSnapshot` helpers, and lane metadata make reuse versus fresh work auditable; merged tool bundles tag topic counts and reuse flags so the UI can badge cached accessories.
- **Agentic gating.** Flow selection stays centralized, while agentic revision modes are now toggled via explicit env flags (`AGENTIC_REVISIONS_ENABLED`, `AGENTIC_REVISION_*`) so rollouts remain auditable and reversible.

## 3. Flow Entry Points & Selection
- FastAPI exposes `/api/analytics/stream` and `/api/analytics/memory/stream` (see `backend/main.py`), both of which wrap helpers in `backend/analytics/flows/workflow.py`.
- `analytics_memory_workflow()` selects a factory from `FLOW_FACTORIES`, primes the flow instance with revision context, and streams `EventEmitter` payloads. Instrumentation toggles are handled inline via `_env_flag("ANALYTICS_MEMORY_INSTRUMENT")`.
- Session snapshotting, follow-up routing, and revision lane targeting all funnel through this helper before the chosen flow's `.events()` coroutine runs.
- `get_available_flows()` is exposed again to surface the active registry to the frontend and CLI tools, mirroring the keys in `FLOW_FACTORIES`.
- The helper resolves lane TTLs via `_resolve_lane_ttls()`, applies lane refresh requirements (`set_lane_refresh_requirements`) / analysis refresh modes, and enables agentic revisions per `_agentic_revision_enabled()` based on overrides such as `ANALYTICS_ANALYSIS_REFRESH_TTL_SECONDS` and `AGENTIC_REVISION_SINGLE_AGENT`.
- When the selected flow exposes `_prepare_sequencer_state()` (single- and multi-agent controllers), `analytics_memory_workflow()` builds a `PlannerOrchestratorAdapter`, instantiates a `PlannerSequencer`, and forwards its `PlannerEventBus` to the flow so lane transitions/retries surface as SSE events with `pending_lanes` metadata.
- Instrumented executions pass the sequencer, lane refresh hints, and optional prefill summary flags into `flows.instrumentation.instrument_events`, ensuring planner, agent, and supervisor streams emit consistent `planner_lane_transition`, `planner_lane_retry`, and cached-lane annotations.

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
- Validators in `validators/cohesive_result.py` still gate the cohesive payload, while `mark_revision_completion` (from `flows/planner/revision.py`) marks lanes complete for revision-aware consumers and relies on the session artifact history (`tool_cache["analytics"]["artifacts_history"]`) for audit trails.

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
- Tool receipts use `ToolInvocationReceipt` (hashes, attempt counts, lane hints, metadata) attached to `PlannerPhaseContext` and persisted through `SessionStateSnapshot.record_tool_receipt`; metadata tracks guardrail outcomes, reused accessories, and now cross-links to Agents SDK runs via `record_agent_run`.
- Session state (`core/session_state.py`) records the latest SQL/chart/analysis outputs, tool cache entries, schedule history (capped at 50), per-lane timestamps, and Agents metadata (`agents_run_id`, `agents_trace_id`, `agents_manager_trace_id`, `agents_tool_attempts`, `agents_retry_counts`, sanitized `agents_tool_receipts`, `agents_recorded_at`, `agents_parallel_groups`, `agents_delegation_policy_version`, `agents_delegation_decisions`). TTL now defaults to 10 minutes (configurable via `AGENTS_SESSION_TTL_MINUTES`, falling back to `ANALYTICS_SESSION_TTL_MINUTES`) and expired snapshots are purged on load before new runs seed cache entries; the fallback store mirrors the same expiry and keeps artifact snapshots capped at `MAX_ARTIFACT_HISTORY = 5`.
- Revision snapshots (`core/revision_snapshot`) capture query signatures and artifact snapshots for targeted reruns; `flows/planner/revision.build_revision_plan` narrows reruns to the lanes that actually need fresh work and can trigger analysis-only revisions when `revision_targets` exclude SQL/chart.

### 4.6 Sequencer & Lane Governance
- `flows/sequencer.PlannerSequencer` drives lane order using `LaneState` objects for `intent`, `sql`, `web`, `market`, and `analysis`, honoring optional lanes plus `lane_refresh_required` overrides computed in `PlannerPhaseContext`.
- Lifecycle telemetry is fanned out through `PlannerEventBus.emit_lane_transition()` / `emit_lane_retry()`, yielding `planner_lane_transition` and `planner_lane_retry` SSE payloads with timestamps, reuse flags, and reasons for cached skips.
- Concrete flows implement `flows.orchestrator_protocol.FlowOrchestrator`; the shared `PlannerOrchestratorAdapter` decorates stage generators with flow metadata, tracks `pending_lanes`, and delegates completion callbacks back to controllers or supervisors.
- Tool-to-lane mappings (`LANE_TOOL_MAP`, `LANE_TOOL_LOOKUP`) ensure receipts, retries, and cache hits stay aligned with sequencer state, while helper callbacks such as `_skip_lane()` and `lane_complete()` short-circuit cached lanes without rerunning adapters.

## 5. Flow Implementations
### 5.1 Planner-Executor (Deterministic Mode)
- `PlannerExecutorFlow.events()` boots `PlannerPipeline` with the shared `PlannerToolRegistry`, invoking registered tools like `classification`, `intent_detection`, and `plan_generation` so the stage order stays declarative while `apply_mode_metadata` annotates every delta.
- Streaming pairs `TimedEventEmitter` with `ToolParallelRuntime`/`run_tool_parallelism()`, emitting `tool_parallel_start`/`tool_parallel_result`/`tool_parallel_complete` for adapters (e.g., web, market) so telemetry and cached receipts remain aligned even when lanes run hedged.
- Snapshot-aware helpers (`prime_with_snapshot()`, `set_follow_up_route()`, `set_revision_targets()`, `set_analysis_refresh_mode()`) hydrate `PlannerPhaseContext` with cached artifacts, lane refresh hints, and follow-up directives before stage generators run.
- Cached snapshots seed the pipeline through `_seed_web_search_from_payload` and `_seed_stock_widget_from_payload`, allowing revision runs to reuse accessories before new fan-out kicks off.
- Revision runs rely on `set_revision_directive()`, `set_lane_refresh_requirements()`, and `set_analysis_refresh_mode()` so explicit targets, lane TTL heuristics, and agentic directives (`agentic_revision_mode`) govern which lanes refresh versus reuse cached receipts; `emit_chart_patch()` / `emit_analysis_revision()` stream post-build patches when revision directives call for deferred updates.
- `PlannerExecutorFlow.get_prompt_versions()` exposes inline prompt registries (replacing `prompt_versions.py`) so downstream flows can display current prompt fingerprints.
- `_capture_artifacts()` + `latest_artifacts` maintain authoritative `PipelineArtifacts` snapshots that `flows.instrumentation.instrument_events` persists back into `SessionStateSnapshot` after streaming completes.
- `run_planner_executor()` exposes a backwards-compatible helper for legacy callers and unit tests, while receipts update after each stage with `snapshot_age_seconds`, guardrail status, lane refresh hints, and reuse flags for UI badging.

### 5.2 Single-Agent Controller
- `SingleAgentController` composes the planner core with tool metadata from `pipeline_tools.get_planner_tool_registry()`, calls `_prepare_sequencer_state()` to hydrate lane refresh hints, and exposes `build_planner_orchestrator()` so `analytics_memory_workflow()` can drive a shared `PlannerSequencer` without duplicating lane logic.
- Fan-out adapters (`MarketQuestionAdapter`, `StockTrackerAdapter`, `WebRetrieverAdapter`) reuse the planner's `ToolParallelRuntime`; the web adapter expands into topic-specific adapters, while market adapters remain hedged but rate-limited to avoid Polygon throttling.
- When `ANALYTICS_ENABLE_AGENTS` is true, the controller delegates SQL/chart/analysis lanes to the OpenAI Agents SDK; `AgentsStreamBridge.forward()` converts `RunResultStreaming` events into planner-style SSE payloads (`tool_call_delta`, `tool_call_arguments`, `agent_reasoning`) stamped via `apply_mode_metadata`.
- Tool lifecycle events (`tool_call`, `tool_parallel_*`) include latency budgets, topic labels, output artifact hints, and follow-up routing info; telemetry mirrors these updates via `telemetry.tool_iteration`, while sequencer-fed metadata adds `pending_lanes`, reuse flags, and planner lane transitions to the stream.
- Analysis completion (`analysis_complete`) triggers `_build_single_agent_cohesive_payload`, which now merges latency guardrail verdicts, topic-level snippets, and tool manifests into a single `cohesive_result`.
- Cached receipts respect `LANE_TOOL_MAP` and the per-mode concurrency budgets in `get_mode_config()`; receipts store prompt versions, guardrail outcomes, and planner lane reuse decisions so cache hits remain explainable.

### 5.3 Multi-Agent Supervisor Flow
- `MultiAgentFlow` orchestrates planner reuse with `AgentExecutionOrchestrator` (`flows/orchestrator.py`); `_prepare_sequencer_state()` seeds lane refresh hints, `build_planner_orchestrator()` delivers stage runners to the shared `PlannerSequencer`, and `set_planner_event_bus()` relays planner lane telemetry to supervisor listeners.
- Agent specifications are registered via `AgentSpec` entries with capability metadata, latency budgets, and evaluation hooks; `AgentTaskPlan.build_from_context()` + `AgentTaskStep.apply_guardrails()` enforce schema guardrails before tasks execute.
- The supervisor issues DAGs where planner, SQL, chart, market, web, and analyst agents run concurrently as dependencies allow. `ROLE_LANES` and `ROLE_PARALLEL_GROUPS` map events back to canvas lanes for the UI.
- Retry governance flows through `SupervisorRetryManager.should_retry()` and the configured `DelegationPolicy`, recording audit payloads that `SessionStateSnapshot.record_agent_run()` persists (`agents_delegation_policy_version`, `agents_delegation_decisions`) for downstream inspection.
- `supervisor_orchestrator.build_supervisor_bundle()` constructs the supervisor agent and lane-specific tools from `SupervisorSpecialistConfig`, aligning tool bindings with sequencer lanes.
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
- `services/response_search.SearchTopicPlan`, `TopicSearchResult`, and `ResponseSearchResult.to_payload()` structure multi-topic web payloads; `has_search_api_key()` gates topic fan-out so cached receipts can short-circuit Gemini calls while preserving latency/model metadata.

## 7. Session Memory, Revisions & Follow-Ups
- `SessionStateRepository` lazily instantiates Redis clients (or logs an in-memory fallback) and enforces a 10-minute default TTL via `_read_ttl_from_env()`; stale snapshots are evicted on load so new runs don't reuse aged receipts. Helper methods record queries, tool results, artifact history (`tool_cache["analytics"]["artifacts_history"]`), lane timestamps, and schedule events for later fan-out or follow-up decisions.
- `SessionStateSnapshot.record_agent_run()` persists agent run metadata (run/trace IDs, receipts, parallel groups, delegation policy versions, decisions) and exposes `agent_run_metadata()` for downstream consumers; `core.cache.CacheService.set_agent_metadata()` / `get_agent_metadata()` / `clear_agent_metadata()` mirror the same payloads for resumable supervisor sessions.
- Revision helpers (`flows/chart_revision.py`, `flows/revision_directive.py`, `flows/planner/revision.py`) enrich revision requests with prior SQL, dataset previews, and analysis history. `build_revision_plan` + `derive_revision_targets` decide which lanes re-run, while `mark_revision_completion` stops redundant delta emissions and `emit_analysis_revision` streams narrative-only patches.
- `analytics_memory_workflow()` detects revision intent with `chart_revision.is_chart_revision_query` and `analysis_revision` helpers before running the main flow, optionally short-circuiting to the stock-only lane when `revision_plan.stock_only` is set or reusing cached accessories when `ctx.web_search_seeded` is true.
- `FollowUpClassifier` inspects the latest snapshot (including which lanes have reusable artifacts) to choose `FollowUpRoute.STOCK_ONLY`, `REUSE_SQL`, or `FULL_PIPELINE`, trimming revision targets to lanes that actually exist in the snapshot.

## 8. Event Streaming & Telemetry
- `core.events.EventEmitter` and `TimedEventEmitter` standardize progress, result, error, and status payloads; data is sanitized through `validators.sanitize_for_json` and now includes prompt fingerprints via `prompt_versions`.
- `flows.instrumentation.instrument_events` wraps flows to attach timing metrics, SQL attempts, telemetry counters, lane mappings, and sequencer metadata without modifying the underlying pipeline; it accepts `sequencer`, `lane_states`, `revision_targets`, `emit_prefill_summary`, and `sequencer_state` so dashboards can visualize pending lanes and cached prefill summaries.
- `core.telemetry` exposes structured log emitters (`intent_resolution`, `tool_iteration`, `tool_parallelism`, `analysis_chunk`, `analysis_revision`, `agent_handoff`, `agent_run`, `policy_decision`), all routed to the `analytics.telemetry` logger alongside latency guardrail verdicts.
- Planner lane events originate from `PlannerEventBus.emit_lane_transition()` / `emit_lane_retry()`, then flow through `apply_mode_metadata()` to produce `planner_lane_transition`/`planner_lane_retry` SSE payloads with reuse flags and reasons (e.g., cached lanes).
- Agents SDK streams traverse `AgentsStreamBridge`, which converts `RunResultStreaming` updates into `tool_call_delta`, `tool_call_arguments`, and `agent_reasoning` payloads so planner canvases can visualize step-by-step reasoning.
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
- Key events expected by the UI include `session_started`, `classification`, `intent_detection`, `clarification_request`, `revision_request`, `planner_lane_transition`, `planner_lane_retry`, `sql_ready`, `chart_ready`, `stock_ready`, `web_ready`, `analysis_revision`, `analysis_complete`, `cohesive_result`, `final_answer`, `workflow_complete`, plus supervisor telemetry (`agent_turn_start`, `agent_turn_end`, `tool_retry`, `tool_call_delta`, `tool_call_arguments`, `agent_reasoning`); error paths mirror these (e.g., `analysis_revision_error`).
- `SessionStateSnapshot.schedule_history` mirrors `FlowSchedule` definitions from `flows/schedulers.py`, enabling ledger visualizations and follow-up heuristics.
- Revision flows annotate events with `{"reason": "revision_request", "source": "analytics_memory_workflow"}` so the frontend can badge revision responses, while accessory payloads ship `topic_count`, `search_topics`, `latency_stats`, and guardrail verdicts for richer UI indicators.

## 10. Testing, Quality & Operations
- Python tests live under `backend/tests/analytics/`. Recent suites cover comparison fans (`test_chart_comparison.py`), clarification heuristics (`test_clarify_comparison.py`, `test_intent_slot_resolution.py`), and telemetry (`test_intent_resolution_telemetry.py`); keep adding fan-out assertions to ensure multi-topic web payloads merge correctly.
- Run `pytest backend/tests/analytics` before shipping backend changes; tests rely on mocked services for Polygon and response search, and new cases should stub `ToolParallelRuntime` queues plus Gemini topic planners to avoid async flakiness.
- Extend coverage to `flows/sequencer.PlannerSequencer`/`PlannerEventBus` and `flows/supervisor_retry_manager.SupervisorRetryManager` to lock in lane retry semantics and delegation guardrails; use `PlannerOrchestratorAdapter` and synthetic `AgentTaskPlan` payloads when unit testing.
- Frontend Vitest coverage (see `docs/analytics-canvas-overview.md`) should validate lane rendering, topic badges, latency guardrail indicators, and cohesive card updates.
- Logging relies on the `analytics.telemetry` logger; configure sinks via standard `logging` config or FastAPI startup hooks, and ensure guardrail outputs flow to your log aggregation.
- Environment variables: `REDIS_URL`, `WEB_SEARCH_GUARDRAIL_P50_MS`, `WEB_SEARCH_GUARDRAIL_P95_MS`, `WEB_SEARCH_TIMEOUT_SECONDS`, `WEB_SEARCH_MAX_TOPICS`, `WEB_SEARCH_RETRY_ATTEMPTS`, `GEMINI_SEARCH_MODEL`, `GEMINI_SEARCH_TEMPERATURE`, `ANALYTICS_SESSION_TTL_MINUTES`, lane TTL overrides (`ANALYTICS_ANALYSIS_REFRESH_TTL_SECONDS`, `ANALYTICS_WEB_REFRESH_TTL_SECONDS`, `ANALYTICS_CHART_REFRESH_TTL_SECONDS`, `ANALYTICS_MARKET_REFRESH_TTL_SECONDS`), agent/flow toggles (`AGENTIC_REVISIONS_ENABLED`, `AGENTIC_REVISION_SINGLE_AGENT`, `AGENTIC_REVISION_MULTI_AGENT`, `AGENTIC_REVISION_PLANNER_EXECUTOR`, `ANALYTICS_ENABLE_AGENTS`, `ANALYTICS_FLOW_MODE`, `ANALYTICS_MEMORY_INSTRUMENT`, `ANALYTICS_SUPERVISOR_BETA_ENABLED`, `SUPERVISOR_REASONING_EFFORT`, `AGENTS_DELEGATION_POLICY_VERSION`), plus tool API keys handled in `.env`. The project expects `npm install` + `npm run dev` for the frontend and `py -m uvicorn main:app --reload --port 8000` for the backend.


## 11. Consolidated Project Outline
### Agent Orchestration & Memory
- `agent_orchestrator/agent_plan.py` defines `PlanNodeStatus`, `PlanNode`, `PlanTemplateNode`, `PlanTemplate`, and `PlanState` so every flow works from the same versioned DAG description, complete with dependency tracking, serialization, and ready-node selection for retries and resumptions.
- `agent_orchestrator/agent_runtime.py` couples `AgentRuntimeConfig`, `AgentRuntime`, and `AgentRuntimeResult` to drive the plan ? act ? observe loop, execute specialist tools via `ToolParallelRuntime`, and emit structured turn summaries.
- `agent_orchestrator/event_bus.py` wraps the shared SSE queue with `AgentEventBus`, applying `FlowMode` metadata and `sanitize_for_json` before events reach frontend subscribers.
- `agent_orchestrator/memory.py` exposes `AgentMemory`, which stores `PlanState` payloads and tool caches inside `SessionStateSnapshot` so successive planner or supervisor passes can resume mid-run.

### Clarification & Intent Intelligence
- `agents/schema_clarifier.py` uses `ClarifierDecision`, `ClarifierAgentResponse`, and helpers like `decide_schema_clarification`, `_run_agent`, and `_fallback_decision` to decide whether templates need schema questions, blending Gemini/OpenAI prompts with deterministic fallbacks.
- `core/intent.py` keeps the main entry points (`detect_intent`, `detect_intent_with_clarifications`, `detect_intent_llm`, async variants) that orchestrators call before every run regardless of flow mode.
- `core/intent_impl/detection.py` and `core/intent_impl/models.py` host `heuristic_intent`, `_build_company_clarification`, `resolve_intent_slots`/`resolve_intent_slots_async`, and typed slot models so low-latency heuristics and LLM paths share the same schema.
- `core/intent_impl/normalization.py`, `core/slot_catalog.py`, and `core/margins.py` converge on helpers like `normalize_timeframe`, `build_metric_lookup`, `normalize_metrics`, `_collect_company_suggestions`, and `resolve_margin_metric` to standardize slot payloads.
- `core/clarify.py` combines `SessionStore`, `detect_missing_slots`, `_detect_*` heuristics, and `merge_answers` to coordinate interactive clarifications; `core/companies.py` (`resolve_alias_to_ticker`, `validate_and_resolve_company`) and `routing/follow_up_classifier.py` (`FollowUpClassifier`, `_contains_any`) round out the pre-run intelligence.

### Core Data, Cache & Telemetry
- `core/cache.py` delivers `CacheService`, `get_cache_service`, `close_cache_service`, and agent metadata helpers so config, template, metric, and session caches share Redis with circuit breakers and JSON fallbacks.
- `core/config.py` and `core/config_store.py` wrap structured settings (`Configs`, `ConfigStore`) with cached fetch/set semantics; `core/context.py` + `core/state.py` pair `AnalyticsContext` and `AnalyticsState` so flows have immutable request metadata plus mutable run state.
- `core/session_state.py` (`SessionStateSnapshot`, `SessionStateRepository`, `get_session_state_repository`) and `core/revision_snapshot.py` (`build_intent_signature`, `extract_revision_snapshot`) own durable session storage, hashing, and revision comparison.
- `core/analysis.py`, `core/charting.py`, and `core/charting_impl.py` contain `_prepare_data_preview`, `_summarize_chart_spec`, `stream_insights_llm`, `plan_chart_rule_based`, `build_chart_spec`, and `generate_descriptive_title`, providing the shared analytics narrative + visualization stack.
- `core/openai_client.get_openai_client`, `core/events.EventEmitter`, `core/telemetry` (`catalog_trace`, `intent_resolution`, `_emit`) and `core/types.py` form the shared integration, event, and type system used across flows and tests.

### Flow Controllers, Sequencer & Runtime Glue
- `flows/workflow.py` exposes `get_available_flows`, `_agentic_revision_enabled`, `_lane_available`, `_resolve_lane_ttls`, and the async `analytics_memory_workflow` entry point that FastAPI hits to stream SSE events for any registered flow.
- `flows/orchestrator.py`, `flows/orchestrator_adapter.py`, and `flows/orchestrator_protocol.py` provide `AgentExecutionOrchestrator`, `PlannerOrchestratorAdapter`, and the `FlowOrchestrator` protocol so deterministic planner lanes, single-agent tools, and supervisors can plug into the same sequencer contract.
- `flows/planner_executor.py`'s `PlannerExecutorFlow`, `_evaluate_latency_guardrail`, `PlannerExecutorRequest`, and caching helpers drive the deterministic pipeline reused by every mode.
- `flows/sequencer.py`, `flows/schedulers.py`, `flows/agents_stream_bridge.py`, and `flows/hooks.py` coordinate `PlannerSequencer`, `PlannerEventBus`, `apply_mode_metadata`, `AgentsStreamBridge`, and hook dispatch so instrumentation and retries stay consistent.
- `flows/pipeline_tools.py`, `flows/task_plan.py`, and `flows/instrumentation.py` round out the glue with `PlannerToolRegistry`, `AgentTaskPlan`, and `instrument_events` to register tool bundles, normalize plan steps, and emit cohesive telemetry.

### Planner Lanes, Tools & Supervisors
- `flows/planner` modules (`analysis_lane.ensure_analysis_dependencies`, `fanout.MultiTopicFanout`, `sql_lane.SQLPlannerLane`, `revision.RevisionPlannerLane`, `intent_templates`) describe how topics split, SQL lanes hydrate, and revisions reuse cached work.
- `flows/single_agent_tools.py` and `flows/tool_bundle.py` house `SingleAgentController`, `ToolParallelRuntime`, `ToolInvocationReceipt`, `ToolBundle`, and inventory helpers that execute LLM tools with structured retries and telemetry.
- `flows/multi_agent.py`, `flows/supervisor_orchestrator.py`, `flows/supervisor_retry_manager.py`, and `flows/revision_directive.py` provide `MultiAgentFlow`, `SupervisorOrchestrator`, `SupervisorRetryManager`, and directive builders so supervisor-led fan-outs can delegate, retry, and summarize specialists.
- `flows/tooling.py`, `flows/workflow.py` (lane sorting), `flows/planner_executor.py` (prefill caching), and `flows/schedulers.apply_mode_metadata` keep accessories, tool wiring, and metadata in sync across planner, single-agent, and supervisor modes.

### SQL, Artifacts & Semantic Catalog
- `artifacts/models.py`'s dataclasses (`ClassificationArtifact`, `PlanArtifact`, `SQLGenerationArtifact`, `SQLExecutionArtifact`, `ChartArtifact`, `AnalysisArtifact`, etc.) define the persisted payloads that UI and regressions consume.
- `sql/compiler.py`, `sql/prompt_builder.py`, `sql/sql_planner.py`, `sql/template_requirements.py`, `sql/templates.py`, `sql/executor.py`, and `sql/validator.py` cover prompt wiring, safety checks, template hydration, execution, and validation so planner lanes and single-agent controllers share the same SQL toolchain.
- `semantic/catalog.py` maintains topic metadata reused by planner fan-out + accessories, while `core/charting` and `core/analysis` convert SQL outputs into chart specs, insights, and cached artifacts that the frontend replays.

### Services, Validators & Ops Utilities
- `services/polygon.py` and `services/response_search.py` wrap external data providers (`PolygonService`, `ResponseSearchService`, `search_with_clauses`) so flows request market data and response snippets through typed clients.
- `tools/registry.py` registers reusable tool bundles, while `streaming/__init__.py` and `flows/instrumentation` prep SSE wiring.
- `validators/cohesive_result.py` enforces narrative/visual alignment before emitting final answers, and `routing/follow_up_classifier.py` (`FollowUpRoute`, `FollowUpClassifier`) decides whether a request should reuse cached SQL, jump to stock-only lanes, or execute the full planner.
- `scripts/schedule_replay.py` (`annotate_events`, `summarize_events`, `render_summary`) and backend-ledger tooling replay SSE logs for audits.


---



## 12. Legacy Code
- **Regression-only sequential pipelines.** The legacy deterministic pipeline harness still lives under `backend/tests/analytics/test_pipeline_*` so we can diff JSON ledgers against the new flows. No runtime code calls those modules, but they must stay green until the regression suite is rewritten around `PlannerSequencer`.
- **Fallback environment switches.** `flows/workflow._env_flag` still honors `ANALYTICS_ENABLE_AGENTS`, `AGENTIC_REVISION_SINGLE_AGENT`, and `AGENTIC_REVISION_PLANNER_EXECUTOR` so dark-launch toggles remain reversible. Once supervisors are the sole path these flags (and their branching) can be removed.
- **Session/tool cache compatibility.** `core.session_state.SessionStateSnapshot` and `AgentMemory` still store `tool_cache["agent"]` payloads so pre-agent snapshots deserialize cleanly. When all active sessions run on the new schema we can drop the legacy key paths.
- **Artifact schema bridges.** `artifacts.models.BaseArtifact` retains helper methods used by earlier payloads; UI components still accept the old shape, so remove only after the React canvases switch to the normalized models.

## 13. Optimization Opportunities
- **Sequencer/Planner DAG dedupe.** `flows.planner.fanout.MultiTopicFanout` and `flows.sequencer.PlannerSequencer` each rebuild dependency graphs; sharing a cached `PlanTemplate` snapshot would cut redundant topological sorts during retries.
- **Cache + telemetry integration.** `core.cache.CacheService.get_stats` already emits Redis metrics-forward those numbers through `core.telemetry.catalog_trace` so operations can auto-scale Redis or fall back before circuit breakers trip.
- **Follow-up routing acceleration.** `routing.FollowUpClassifier` still re-tokenizes prompts for every request; memoizing `_contains_any` against normalized intents (or caching results in `CacheService`) would shave milliseconds off planner selection.
- **Tool bundle warm starts.** `flows.single_agent_tools.ToolParallelRuntime` repeatedly rebuilds `ToolBundle` wiring; pooling tool registries from `flows.tool_bundle` per session would reduce cold-start reasoning time for the single-agent controller.

This architecture reference reflects the current state of the `next-gen-analytics-agent` project and should be updated alongside significant planner, tool, or telemetry changes.
