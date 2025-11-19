# Next-Gen Analytics Agent Architecture - November 18, 2025

## 1. Vision & Project Overview
### Vision alignment (Agentic Analytics Roadmap - November 7, 2025)
- **Revision runs = agent-first loops.** `SingleAgentController` hands revision traffic to `agent_orchestrator.AgentRuntime.run()` via `AgentRuntimeConfig` and `AgentMemory.load_plan_state()`, so the agent inspects cached SQL/chart/web artifacts before deciding which tools (`sql_generation`, `chart_revision`, `web_refresh`, `analysis_revision`) to rerun.
- **Tool autonomy + UI-as-chat.** Each OpenAI Agents SDK turn is converted by `AgentsStreamBridge._emit_tool_call_delta()` / `_emit_reasoning_delta()` into `agent_tool_call` / `agent_reasoning` SSE payloads, mirroring the roadmap requirement that the canvas shows the agent's thought process instead of opaque pipeline steps.
- **Session-memory hydration.** `SessionStateSnapshot` and `AgentMemory.record_tool_receipt()` keep the latest `ToolInvocationReceipt` hashes, while `RevisionDirective.from_payload()` carries requested focus plus search plans from `services.response_search.generate_search_topics`, giving revision loops the same context described in the roadmap vision.
- **Fresh runs stay deterministic.** `PlannerExecutorFlow.events()` always executes SQL -> chart -> accessory -> analysis lanes on fresh requests, recording receipts through `SessionStateSnapshot.record_outputs()` so revisions hydrate from authoritative artifacts while first answers remain cache-independent.

### Platform snapshot (November 14, 2025)
- The **next-gen analytics agent** delivers LangGraph-style orchestration on top of FastAPI (`backend/main.py`) while keeping all runtime logic inside `backend/analytics`, so deterministic, single-agent, and supervisor controllers reuse the same `PlannerPipeline` plus `PlannerToolRegistry`.
- The system supports three operating modes: deterministic planner-executor, single agent with explicit tool telemetry, and supervisor-led multi-agent. Each mode is exposed through SSE endpoints that feed the Vite UI.
- Product positioning (see `public/ai-projects.json`) highlights a unified UI that switches between direct, single-agent, and supervisor workflows, reuses cached SQL/RAG/chart artifacts, and targets a 60% improvement in clarification latency.
- Classification and routing now run through `core.intent_impl.detection.classify_query_async()`, which defaults to `_classify_with_gemini()` (Gemini Flash 2.5 Lite) and falls back to `_classify_with_openai()` so both fresh runs and revisions inherit the same gating metadata.
- `agent_orchestrator.AgentRuntime`, `agent_orchestrator.event_bus.AgentEventBus`, and `flows/agents_stream_bridge.AgentsStreamBridge` convert OpenAI Agents loops into planner-style SSE payloads, letting single-agent and supervisor flows emit identical telemetry badges, guardrails, and plan snapshots.
- This reference captures implementation details current to **November 14, 2025** and replaces the earlier agentic refactor notes.

## 2. Guiding Principles & Guardrails
- **Reuse the planner core.** `flows/planner_executor.PlannerExecutorFlow` stays the source of truth for SQL planning, execution, charting, and analysis so every mode shares identical business logic.
- **No legacy fallbacks.** Users only interact with agentic flows; sequential legacy pipelines were removed from runtime, though regression tests still compare against their outputs.
- **Observability first.** Flows annotate events via `flows.schedulers.apply_mode_metadata`, emit structured telemetry through `core.telemetry`, and now attach latency guardrail payloads (`planner_executor._evaluate_latency_guardrail`) so web fan-out breaches surface immediately.
- **Cache circuit-breakers.** `core.cache.CacheService` fronts Redis with warm handshakes, circuit-breaker thresholds, and in-process fallbacks, keeping `core.config_store.ConfigStore` responsive even when Redis is unavailable, and now persists per-session agent run metadata (run IDs, retry counts, failure flags) via `CacheService.set_agent_metadata` so supervisors can resume or audit long-running tasks.
- **Explicit caching.** Hashed `ToolInvocationReceipt` objects, `SessionStateSnapshot` helpers, and lane metadata make reuse versus fresh work auditable; merged tool bundles tag topic counts and reuse flags so the UI can badge cached accessories.
- **Agentic gating.** Flow selection stays centralized, while agentic revision modes are now toggled via explicit env flags (`AGENTIC_REVISIONS_ENABLED`, `AGENTIC_REVISION_*`) so rollouts remain auditable and reversible.
| `multi-agent`    | `MultiAgentFlow` (`flows/multi_agent.py`)               | `FlowMode.MULTI_AGENT` | `multi-agent`      | Supervisor plus specialists orchestrated by the agent DAG.   |

The `FollowUpClassifier` (`routing/follow_up_classifier.py`) runs ahead of every session to decide whether to reuse SQL, run stock-only updates, or execute the full pipeline; flows receive the `FollowUpRoute` via `set_follow_up_route()`.

## 4. Shared Pipeline Stages
### 4.1 Intent Qualification & Clarification
- Classification and gating use `core.intent.classify_query_async()` (backed by `core.intent_impl.detection.classify_query_async()`), which defaults to `_classify_with_gemini()` (Gemini Flash 2.5 Lite) and falls back to `_classify_with_openai()` before feeding into `detect_intent` and `post_process_slots`; the revamped heuristic detector (`heuristic_intent`) uses `_is_ranking_query` to spot ranking/peer comparisons and supports new intents like `revenue_growth_vs_avg`, `rnd_top_spender`, and `operating_leverage_yoy_vs_peers`.
- Slot resolution combines rule-based status (`core.intent_impl.models.SlotStatusModel`), LLM follow-ups (`core.intent_impl.detection.resolve_intent_slots_async`), and normalization helpers (`core.intent_impl.normalization.normalize_timeframe`, `normalize_metrics`, `normalize_granularity`, `timeframe_implies_quarterly`) to align slots with template expectations.
- `agents/schema_clarifier.decide_schema_clarification` validates template requirements (`sql.template_requirements`) and decides whether to clarify, assume, or decline missing fields; company defaults now leverage `normalization.get_default_tickers`.
- Clarification loops rely on `core.clarify` helpers (`compute_required_clarifications`, `validate_clarification_answer`, `wait_for_answer_blocking`) backed by the new in-memory `SessionStore`; telemetry still emits via `telemetry.intent_resolution` while cached answers expire after 10 minutes.

### 4.2 Planning, Templates & SQL Generation
- `sql.sql_planner.plan_sql_rule_based` builds a provisional plan using the semantic catalog (`semantic/catalog.py`) and normalized metrics, while new intents (`operating_leverage_yoy_vs_peers`, `eps_yoy_rank_latest`, `capex_intensity_latest_rank`, `rnd_intensity_vs_peers`, `revenue_growth_vs_avg`) add comparison defaults and peer heuristics.
- Template lookup (`sql.templates.fetch_templates_for_intent`, `sql.sql_planner.choose_template`) surfaces YAML-backed plans stored in `core.config_store`, which now leans on `core.cache.CacheService` to avoid redundant YAML parsing.
- `PlannerPhaseContext` tracks candidate templates, criteria, tool receipts, and intent signatures for downstream reuse and revision detection; it also records seeded accessories (`web_search_seeded`, `stock_widget_seeded`), revision directives, and latency stats for guardrail evaluation.
- SQL code is compiled and validated through `sql.compiler.compile_sql_from_plan` and `sql.validator.validate_sql`; failures populate `PipelineArtifacts.sql_generation.attempts` and drive retry prompts.

### 4.3 Execution Lanes & Narrative Synthesis
- `flows/planner/sql_lane.stream_sql_lane` orchestrates SQL execution and reuse, emitting `sql_ready` with `lane: "sql"` plus `parallel_group: "core_sequential"` when cached payloads are replayed. Fresh runs call `sql.executor.execute_sql` to hydrate sample rows, tickers, and column metadata.
- `stream_chart_lane` blends `compose_chart_ready_payload` with `core.charting.plan_chart_rule_based`/`build_chart_spec`; `_generate_chart_design` now produces smart chart design metadata (grouping, axis types, legend order) for frontend optimization.
- `flows/planner/analysis_lane.stream_analysis_lane` now streams via `stream_insights_llm`, merging accessory bundles, applying latency guardrails (`latency_guardrail` payload), and emitting `analysis_revision` hooks when revision directives request insight-focused rewrites.
- Validators in `validators/cohesive_result.py` still gate the cohesive payload, while `mark_revision_completion` (from `flows/planner/revision.py`) marks lanes complete for revision-aware consumers and relies on the session artifact history (`tool_cache["analytics"]["artifacts_history"]`) for audit trails.

### 4.4 Tool Fan-Out & Accessory Prefetch
- Tool fan-out starts via `flows/planner.fanout.start_tool_parallelism`, which buffers adapter output on an async queue while `derive_accessory_events` synthesizes `stock_ready`/`web_ready` deltas stamped with lane metadata.
- `PlannerPipeline._fanout_adapters_for_context()` selects adapters (e.g., `StockTrackerAdapter`, `WebRetrieverAdapter`) when `ModeConfig.parallelism_enabled` is true; the web adapter now calls `services.response_search.build_web_research_questions` (via `generate_search_topics`) to split a single user query into multiple topic-specific adapters when an API key is present.
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
- Tool receipts use `ToolInvocationReceipt` (hashes, attempt counts, lane hints, metadata) attached to `PlannerPhaseContext` and persisted through `SessionStateSnapshot.record_tool_receipt`; metadata tracks `latency_guardrail`, `guardrail` outcomes, reused accessories, and now cross-links to Agents SDK runs via `record_agent_run`.
- Session state (`core/session_state.py`) records the latest SQL/chart/analysis outputs, tool cache entries, schedule history (capped at 50), per-lane timestamps, and Agents metadata (`agents_run_id`, `agents_trace_id`, `agents_manager_trace_id`, `agents_tool_attempts`, `agents_retry_counts`, sanitized `agents_tool_receipts`, `agents_recorded_at`, `agents_parallel_groups`, `agents_delegation_policy_version`, `agents_delegation_decisions`). TTL now defaults to 10 minutes (configurable via `AGENTS_SESSION_TTL_MINUTES`, falling back to `ANALYTICS_SESSION_TTL_MINUTES`) and expired snapshots are purged on load before new runs seed cache entries; the fallback store mirrors the same expiry and keeps artifact snapshots capped at `MAX_ARTIFACT_HISTORY = 5`.
- Revision snapshots (`core/revision_snapshot`) capture query signatures and artifact snapshots for targeted reruns; `flows/planner/revision.build_revision_plan` narrows reruns to the lanes that actually need fresh work and can trigger analysis-only revisions when `revision_targets` exclude SQL/chart.

### 4.6 Sequencer & Lane Governance
- `flows/sequencer.PlannerSequencer` drives lane order using `LaneState` objects for `intent`, `sql`, `web`, `market`, and `analysis`, honoring optional lanes plus `lane_refresh_required` overrides computed in `PlannerPhaseContext`.
- Lifecycle telemetry is fanned out through `PlannerEventBus.emit_lane_transition()` / `emit_lane_retry()`, yielding `planner_lane_transition` and `planner_lane_retry` SSE payloads with timestamps, reuse flags, and reasons for cached skips.
- Concrete flows implement `flows.orchestrator_protocol.FlowOrchestrator`; the shared `PlannerOrchestratorAdapter` decorates stage generators with flow metadata, tracks `pending_lanes`, and delegates completion callbacks back to controllers or supervisors.
- Tool-to-lane mappings (`LANE_TOOL_MAP`, `LANE_TOOL_LOOKUP`) ensure receipts, retries, and cache hits stay aligned with sequencer state, while helper callbacks such as `_skip_lane()` and `lane_complete()` short-circuit cached lanes without rerunning adapters.

### 4.7 File-Level Function Maps
- Every analytics `.py` module now opens with a `Function Map` header that lists each function, which module calls it, what it invokes next, and why it exists (e.g., `Function: derive_revision_targets — called from flows/workflow.analytics_memory_workflow, forwards to flows/planner/revision.mark_revision_completion to bound reruns`). This mirrors the repo-wide guideline from `AGENTS.md`.
- Use these headers as the first stop when tracing behavior: the map points to upstream call sites (FastAPI endpoints, flows, or services) and downstream effects (sequencer lanes, telemetry, cache writes) so contributors can orient before reading implementations.
- Function entries flag runtime expectations such as `legacy-only`, `cache-hit`, or `agents-bridge` to keep disconnected helpers obvious; when pruning code, confirm that its function map no longer lists active inbound modules.
- The maps intentionally duplicate the high-level story in this architecture file—`ARCHITECTURE.md` explains lane orchestration, while the per-file maps document the micro call graph so reviewers can see how a change propagates without cross-referencing tooling.

### 4.8 Function Reference (Updated November 19, 2025)
The following catalog documents every function explicitly mentioned in this reference. Each item lists the module location, primary callers, downstream collaborators, and why the function matters in the current architecture.

#### Agent Runtime & Memory
- `agent_orchestrator.AgentRuntime.run()` (`backend/analytics/agent_orchestrator/agent_runtime.py`) — Called by `SingleAgentController` and `MultiAgentFlow` whenever a session delegates work to the OpenAI Agents SDK; it loads the last `PlanState`, streams through `Runner.stream/run_streamed`, emits SSE payloads via `AgentsStreamBridge.forward()`, and persists plan progress plus telemetry using `AgentMemory`.
- `AgentMemory.load_plan_state()` (`backend/analytics/agent_orchestrator/memory.py`) — Rehydrates `PlanState` from the snapshot’s `tool_cache["agent"]["plan_state"]`, ensuring resumed agent runs pick up whichever DAG node was left pending.
- `AgentMemory.persist_plan_state()` (`backend/analytics/agent_orchestrator/memory.py`) — Writes the latest `PlanState` back into the session snapshot (and timestamps it) so multi-turn agents and revisions share identical DAG progress.
- `AgentMemory.record_tool_receipt()` (`backend/analytics/agent_orchestrator/memory.py`) — Called from the agent runtime each time a tool finishes; it forwards the sanitized payload to `SessionStateSnapshot.record_tool_receipt()` so cached receipts stay in sync with planner telemetry.
- `AgentMemory.record_agent_run()` (`backend/analytics/agent_orchestrator/memory.py`) — Bridges agent run metadata (run/trace IDs, retries, receipts, delegation decisions) into `SessionStateSnapshot.record_agent_run()` for later audits and resumptions.
- `AgentsStreamBridge.forward()` (`backend/analytics/flows/agents_stream_bridge.py`) — Consumes `RunResultStreaming` events, re-labeling them as planner-style SSE payloads so the canvas shows tool arguments, completions, reasoning, and supervisor summaries in-line.
- `AgentsStreamBridge._emit_tool_call_delta()` (`backend/analytics/flows/agents_stream_bridge.py`) — Emits `tool_call_delta` SSE events whenever the Agents SDK streams argument fragments, preserving tool IDs, sequence numbers, and adapter metadata for UI replay.
- `AgentsStreamBridge._emit_reasoning_delta()` (`backend/analytics/flows/agents_stream_bridge.py`) — Sends `agent_reasoning` payloads for every reasoning delta surfaced by the SDK so supervisors and single-agent runs expose their chain-of-thought badges.

#### Planner Flow Setup & Execution
- `PlannerExecutorFlow.events()` (`backend/analytics/flows/planner_executor.py`) — Main async generator hit by FastAPI (`analytics_memory_workflow`), single-agent, and multi-agent flows; it wires `PlannerPipeline`, `PlannerEventBus`, `ToolParallelRuntime`, and `instrument_events` so SQL, accessories, and analysis stages stream deterministically.
- `PlannerExecutorFlow.prime_with_snapshot()` (`backend/analytics/flows/planner_executor.py`) — Injects the latest `SessionStateSnapshot` before sequencing so cached SQL, chart, market, and analysis artifacts seed the plan; `SingleAgentController` and `MultiAgentFlow` delegate to the same helper.
- `PlannerExecutorFlow.set_follow_up_route()` (`backend/analytics/flows/planner_executor.py`) — Stores the `FollowUpRoute` selected by `FollowUpClassifier`, allowing downstream stages to reuse SQL, run stock-only updates, or execute the full planner; wrappers in single- and multi-agent flows forward the route to this method.
- `PlannerExecutorFlow.set_revision_targets()` (`backend/analytics/flows/planner_executor.py`) — Normalizes explicit lane targets (chart, analysis, market, web, stock) so revision runs only refresh lanes that need new work; also toggles the `revision_hint_active` flag for telemetry.
- `PlannerExecutorFlow.set_revision_directive()` (`backend/analytics/flows/planner_executor.py`) — Attaches a `RevisionDirective` (manual or agentic) to the pipeline, records directive-derived lane targets, and toggles `agentic_revision_mode` to keep downstream hooks aware of agent-led revisions.
- `PlannerExecutorFlow.set_lane_refresh_requirements()` (`backend/analytics/flows/planner_executor.py`) — Accepts `{lane: bool}` maps from heuristics or directives so optional lanes can be skipped (marked reused) without re-queuing adapters.
- `PlannerExecutorFlow.set_analysis_refresh_mode()` (`backend/analytics/flows/planner_executor.py`) — Forces `analysis` lanes into `light` or `full` refresh modes when revision directives or policy demand reduced LLM cost.
- `PlannerPipeline._fanout_adapters_for_context()` (`backend/analytics/flows/planner_executor.py`) — Chooses the appropriate accessory adapters (market tracker, stock tracker, topic-specific web retrievers) based on `ModeConfig.parallelism_enabled` and revision directives.
- `PlannerExecutorFlow.emit_chart_patch()` (`backend/analytics/flows/planner_executor.py`) — Streams chart-only updates (often from agentic directives) back to the client and optionally through hooks, while persisting the patched spec to the snapshot.
- `PlannerExecutorFlow.emit_analysis_revision()` (`backend/analytics/flows/planner_executor.py`) — Emits `analysis_revision` deltas (e.g., narrative tweaks) when revisions skip SQL/chart lanes but still need fresh prose, again persisting outputs via hooks.
- `PlannerExecutorFlow.get_prompt_versions()` (`backend/analytics/flows/planner_executor.py`) — Returns the inline registry of planner prompt fingerprints so UI, telemetry, and tests can pin answers to specific prompt hashes without touching `prompt_versions.py`.
- `PlannerExecutorFlow._capture_artifacts()` (`backend/analytics/flows/planner_executor.py`) — Internal helper that snapshots the latest `PipelineArtifacts` so instrumentation and follow-up routing have a consistent view of SQL, chart, market, and analysis payloads.
- `run_planner_executor()` (`backend/analytics/flows/planner_executor.py`) — Backwards-compatible helper exposed to FastAPI and tests, instantiating `PlannerExecutorFlow` and yielding its `events()` stream for callers still expecting the legacy function signature.
- `pipeline_tools.get_planner_tool_registry()` (`backend/analytics/flows/pipeline_tools.py`) — Lazily constructs and caches the `PlannerToolRegistry`, bootstrapping registered tools (`classification`, `intent_detection`, `plan_generation`, etc.) for every flow; references to `get_planner_tool_registry()` in other modules point to this initializer.
- `set_planner_event_bus()` (`backend/analytics/flows/multi_agent.py`) — Allows `MultiAgentFlow` to attach the shared `PlannerEventBus`, mirroring deterministic planner telemetry into supervisor listeners before agent orchestration begins.
- `_prepare_sequencer_state()` (`backend/analytics/flows/single_agent_tools.py` and `backend/analytics/flows/multi_agent.py`) — Hydrates `PlannerPhaseContext`, prompt registries, cached artifacts, and lane readiness before creating a `PlannerSequencer`, ensuring both direct and agentic flows reuse identical state machines.
- `build_planner_orchestrator()` (`backend/analytics/flows/single_agent_tools.py` and `backend/analytics/flows/multi_agent.py`) — Returns a `PlannerOrchestratorAdapter` wired to the appropriate stage runners (planner lanes for deterministic flows, agent runtime for agentic lanes), letting the shared sequencer remain agnostic to flow mode.
- `get_mode_config()` (`backend/analytics/flows/schedulers.py`) — Resolves `FlowMode` into concurrency, hedging, accessory, and retry budgets; every SSE payload inherits these badges via `apply_mode_metadata()`.
- `apply_mode_metadata()` (`backend/analytics/flows/schedulers.py`) — Annotates SSE events (session, tool, lane, agent) with flow metadata, schedule badges, and accessory strategies so UI and logs display consistent run context regardless of controller.
- `_SingleAgentToolHooks._emit_tool_event()` (`backend/analytics/flows/single_agent_tools.py`) — Emits telemetry/SSE events for each tool attempt when the single-agent controller executes planner tools; it stamps attempts, retries, receipts, and flow metadata, piggybacking on `apply_mode_metadata()`.

#### Sequencer, Events & Parallel Tooling
- `PlannerEventBus.emit_lane_transition()` (`backend/analytics/flows/sequencer.py`) — Broadcasts `planner_lane_transition` events with lane status, reuse reasons, and timestamps for every stage, keeping supervisors, hooks, and UI canvases synchronized.
- `PlannerEventBus.emit_lane_retry()` (`backend/analytics/flows/sequencer.py`) — Surfaces retries with attempt counts, reasons, and metadata so telemetry and UI can flag hedged or retried lanes in near-real time.
- `PlannerSequencer.__init__()` (`backend/analytics/flows/sequencer.py`) — Configures required lanes, optional lanes, dependencies, and initial state (prefilling cached lanes via `_skip_lane`) while wiring the `PlannerEventBus` and orchestrator callbacks.
- `PlannerSequencer._skip_lane()` (`backend/analytics/flows/sequencer.py`) — Marks a lane as reused/skipped (e.g., due to cached artifacts), emits transition + reuse events, and notifies the orchestrator via `lane_complete()` so downstream dependencies unblock without re-running adapters.
- `lane_complete()` (`backend/analytics/flows/orchestrator_adapter.py` via the `FlowOrchestrator` protocol) — Callback invoked by the sequencer whenever a lane finishes or is skipped; implementations (`PlannerOrchestratorAdapter`, `SingleAgentController`, `MultiAgentFlow`) persist artifacts, enqueue retries, or emit agent telemetry.
- `run_tool_parallelism()` (`backend/analytics/flows/tooling.py`) — Executes accessory adapters concurrently, yielding telemetry for each tool result, checkpointing revision directives, and constructing fallback intents/plans if revision refreshes require them.
- `flows.planner.fanout.start_tool_parallelism()` (`backend/analytics/flows/planner/fanout.py`) — Wraps `run_tool_parallelism()` inside a `ToolParallelRuntime`, creating dispatcher queues so accessories stream results and derived events (e.g., `web_ready`, `stock_ready`) back to the sequencer.
- `flows.planner.fanout.derive_accessory_events()` (`backend/analytics/flows/planner/fanout.py`) — Converts adapter payloads into normalized SSE events across web/market lanes, tagging parallel groups, latencies, and cache status before instrumentation emits them.

#### Classification, Routing & Revisions
- `core.intent_impl.detection.classify_query_async()` (`backend/analytics/core/intent_impl/detection.py`) — Primary async classifier invoked by planner lanes; it orchestrates heuristic detectors, Gemini (via `_classify_with_gemini()`), and OpenAI fallbacks (`_classify_with_openai()`) before returning structured intents/slots.
- `_classify_with_gemini()` (`backend/analytics/core/intent_impl/detection.py`) — Calls Gemini Flash 2.5 Lite for high-recall routing, reformatting results into the shared intent model while logging latency + guardrails.
- `_classify_with_openai()` (`backend/analytics/core/intent_impl/detection.py`) — OpenAI fallback invoked when Gemini lacks coverage or errors; keeps downstream slot normalization consistent so planner lanes don’t branch on model choice.
- `core.intent.classify_query_async()` (`backend/analytics/core/intent.py`) — Thin async wrapper exported to flows/tests, delegating to the detection module while preserving the public API used throughout the repo.
- `RevisionDirective.from_payload()` (`backend/analytics/flows/revision_directive.py`) — Builds typed revision directives from agent or user payloads, normalizing lane targets, keyword focus, and `SearchTopicPlan` entries so revisions share a consistent schema.
- `FollowUpClassifier.classify()` (`backend/analytics/routing/follow_up_classifier.py`) — Reads the latest `SessionStateSnapshot`, cached web questions, and lane readiness to decide whether a follow-up should reuse SQL, run stock-only, or execute the full pipeline.
- `_contains_any()` (`backend/analytics/routing/follow_up_classifier.py`) — Small helper used by `FollowUpClassifier` to detect keywords (stock, chart, market, analysis, SQL) inside normalized user queries.
- `flows/planner/revision.derive_revision_targets()` (`backend/analytics/flows/planner/revision.py`) — Converts revision hints, directives, and follow-up routes into concrete lane targets (chart, analysis, market, web, stock), ensuring revisions rerun only what’s necessary.

#### Session Memory, TTL & Cache
- `SessionStateSnapshot.record_outputs()` (`backend/analytics/core/session_state.py`) — Persists SQL text, chart specs, analysis text, and dataset previews after each lane, providing the source of truth for revisions, follow-ups, and UI replays.
- `SessionStateSnapshot.record_agent_run()` (`backend/analytics/core/session_state.py`) — Stores normalized agent metadata (run/trace IDs, receipts, retry counts, delegation info) alongside legacy caches so agent resumptions work during rollout.
- `SessionStateSnapshot.agent_run_metadata()` (`backend/analytics/core/session_state.py`) — Returns a sanitized dict of the latest agent run data so SSE streams, telemetry, or UI badges can show which agent/model produced the current answer.
- `_read_ttl_from_env()` (`backend/analytics/core/session_state.py`) — Applies TTL overrides (`AGENTS_SESSION_TTL_MINUTES`, `ANALYTICS_SESSION_TTL_MINUTES`) to session snapshots so Redis + in-memory stores expire runs predictably.
- `core.cache.CacheService.set_agent_metadata()` (`backend/analytics/core/cache.py`) — Persists agent run metadata in Redis (`agent_run` namespace) so supervisors can resume or audit sessions outside the primary snapshot lifecycle.
- `core.cache.CacheService.get_agent_metadata()` (`backend/analytics/core/cache.py`) — Fetches cached agent metadata for resumptions or audits; used by flows that need to reattach delegation context after a restart.
- `core.cache.CacheService.clear_agent_metadata()` (`backend/analytics/core/cache.py`) — Deletes cached agent metadata once a session completes or is reset, preventing stale delegation details from leaking into new runs.
- `core.cache.CacheService.get_stats()` (`backend/analytics/core/cache.py`) — Surfaces Redis availability, fallback cache sizes, and hit ratios so telemetry dashboards and guardrails can factor cache health into rollout decisions.

#### Tool Ecosystem & Data Providers
- `collect_tool_bundle()` (`backend/analytics/flows/tool_bundle.py`) — Deduplicated here for emphasis: this helper collates manifests, stock widgets, merged web context, and tool result provenance; it feeds UI manifests, cached artifacts, and telemetry.
- `ResponseSearchResult.to_payload()` (`backend/analytics/services/response_search.py`) — Serializes Gemini + response-search results (topics, snippets, annotations, latency, cache status) for SSE payloads and cached artifacts.
- `has_search_api_key()` (`backend/analytics/services/response_search.py`) — Checks for configured Gemini keys (`GOOGLE_API_KEY`, `GEMINI_API_KEY`) so flows can decide whether to fan out new web topics or reuse cached receipts.

#### Workflow Controllers & Supervisors
- `analytics_memory_workflow()` (`backend/analytics/flows/workflow.py`) — FastAPI-facing entry point that chooses the right flow (planner-executor, single agent, multi-agent), handles chart/analysis revision detection, seeds snapshots, and streams SSE events back to the client.
- `flows/workflow._env_flag()` (`backend/analytics/flows/workflow.py`) — Shared helper for parsing boolean env toggles (e.g., `ANALYTICS_ENABLE_AGENTS`), guaranteeing consistent behavior across controllers.
- `_agentic_revision_enabled()` (`backend/analytics/flows/workflow.py`) — Uses `_env_flag()` plus per-flow overrides to determine whether agentic revisions are enabled for the current deployment, keeping rollout levers centralized.
- `AgentTaskPlan.build_from_context()` (`backend/analytics/flows/task_plan.py`) — Converts planner-emitted task step dicts into typed `AgentTaskPlan` entries, applying guardrails while retaining metadata for supervision.
- `AgentTaskStep.apply_guardrails()` (`backend/analytics/flows/task_plan.py`) — Validates required metadata, enforces disallowed statuses, and toggles retry/skip flags when supervisor guardrails flag an agent task.
- `SupervisorRetryManager.should_retry()` (`backend/analytics/flows/supervisor_retry_manager.py`) — Enforces delegation policy windows/day limits per lane, tracking attempts so supervisors don’t thrash on failing tasks; returns audit payloads for telemetry.
- `supervisor_orchestrator.build_supervisor_bundle()` (`backend/analytics/flows/supervisor_orchestrator.py`) — Builds the supervisor Agent plus lane-specific specialist tools using `SupervisorSpecialistConfig`, wiring them into the Agents SDK for multi-agent flows.
- `set_planner_event_bus()` (see the earlier entry) — Included here to highlight that supervisor flows depend on planner telemetry to align DAG progress with supervisor DAGs.

#### Legacy Pipelines
- `analytics_agent.AnalyticsWorkflow._build_market_share_sql()` (`backend/analytics_agent.py`) — Legacy helper used solely by regression tests to craft handcrafted SQL for market-share prompts.
- `analytics_agent.AnalyticsWorkflow._build_margins_sql()` (`backend/analytics_agent.py`) — Builds deterministic SQL for margin analyses in the sequential pipeline, again retained only for fixture parity.
- `analytics_agent.AnalyticsWorkflow._build_rnd_sql()` (`backend/analytics_agent.py`) — Generates R&D expense SQL used by the regression-only workflow.
- `analytics_agent.AnalyticsWorkflow._build_echarts_spec()` (`backend/analytics_agent.py`) — Creates the legacy ECharts payload consumed by old front-end fixtures; modern flows use the planner’s chart spec builders instead.

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
- Revisions invoke `agent_orchestrator.AgentRuntime` with `AgentRuntimeConfig`, `PlanTemplate`, and `AgentMemory.load_plan_state()` so agent loops resume unfinished DAG nodes; `agent_orchestrator.event_bus.AgentEventBus` mirrors plan updates onto the SSE queue, and `AgentMemory.record_agent_run()` persists run/trace IDs plus tool receipts for resumable sessions.
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
- `services/response_search.SearchTopicPlan`, `TopicSearchResult`, `WebResearchQuestionBundle`, and `ResponseSearchResult.to_payload()` structure multi-topic web payloads; `has_search_api_key()` gates topic fan-out so cached receipts can short-circuit Gemini calls while preserving latency/model metadata.

## 7. Session Memory, Revisions & Follow-Ups
- `SessionStateRepository` lazily instantiates Redis clients (or logs an in-memory fallback) and enforces a 10-minute default TTL via `_read_ttl_from_env()`; stale snapshots are evicted on load so new runs don't reuse aged receipts. Helper methods record queries, tool results, artifact history (`tool_cache["analytics"]["artifacts_history"]`), lane timestamps, and schedule events for later fan-out or follow-up decisions.
- `SessionStateSnapshot.record_agent_run()` persists agent run metadata (run/trace IDs, receipts, parallel groups, delegation policy versions, decisions) and exposes `agent_run_metadata()` for downstream consumers; `core.cache.CacheService.set_agent_metadata()` / `get_agent_metadata()` / `clear_agent_metadata()` mirror the same payloads for resumable supervisor sessions.
- `agent_orchestrator.memory.AgentMemory` wraps each snapshot so `load_plan_state()`, `persist_plan_state()`, and `record_tool_receipt()` maintain `PlanState` progress plus tool receipts under `tool_cache["agent"]` while also calling `SessionStateSnapshot.record_agent_run()` to keep the typed `agents_*` fields aligned for resumptions.
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
- `core/intent_impl/detection.py` adds `_is_ranking_query`, `_build_company_clarification`, and updated `heuristic_intent` logic to support broader intent coverage.

### Core Data, Cache & Telemetry
- `core/cache.py` delivers `CacheService`, `get_cache_service`, `close_cache_service`, and agent metadata helpers so config, template, metric, and session caches share Redis with circuit breakers and JSON fallbacks.
- `core/config.py` and `core/config_store.py` wrap structured settings (`Configs`, `ConfigStore`) with cached fetch/set semantics; `core/context.py` + `core/state.py` pair `AnalyticsContext` and `AnalyticsState` so flows have immutable request metadata plus mutable run state.
- `core/session_state.py` (`SessionStateSnapshot`, `SessionStateRepository`, `get_session_state_repository`) and `core/revision_snapshot.py` (`build_intent_signature`, `extract_revision_snapshot`) own durable session storage, hashing, and revision comparison.
- `core/analysis.py`, `core/charting.py`, and `core/charting_impl.py` contain `_prepare_data_preview`, `_summarize_chart_spec`, `stream_insights_llm`, `plan_chart_rule_based`, `build_chart_spec`, and `generate_descriptive_title`, providing the shared analytics narrative + visualization stack.
- `core/openai_client.get_openai_client`, `core/events.EventEmitter`, `core/telemetry` (`catalog_trace`, `intent_resolution`, `_emit`) and `core/types.py` form the shared integration, event, and type system used across flows and tests.

### Flow Controllers, Sequencer & Runtime Glue
- `flows/workflow.py` exposes `get_available_flows`, `_agentic_revision_enabled`, `_resolve_agentic_revision_flag`, `_lane_available`, `_resolve_lane_ttls`, `_build_revision_inputs_plan`, and the async `analytics_memory_workflow` entry point that FastAPI hits to stream SSE events for any registered flow.
- `flows/orchestrator.py`, `flows/orchestrator_adapter.py`, and `flows/orchestrator_protocol.py` provide `AgentExecutionOrchestrator`, `PlannerOrchestratorAdapter`, and the `FlowOrchestrator` protocol so deterministic planner lanes, single-agent tools, and supervisors can plug into the same sequencer contract.
- `flows/planner_executor.py`'s `PlannerExecutorFlow`, `_evaluate_latency_guardrail`, `PlannerExecutorRequest`, `_generate_chart_design`, and caching helpers drive the deterministic pipeline reused by every mode.
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
- `services/polygon.py` and `services/response_search.py` wrap external data providers (`PolygonService`, `ResponseSearchService`, `build_web_research_questions`, `generate_search_topics`) so flows request market data and response snippets through typed clients.
- `tools/registry.py` registers reusable tool bundles, while `streaming/__init__.py` and `flows/instrumentation` prep SSE wiring.
- `validators/cohesive_result.py` enforces narrative/visual alignment before emitting final answers, and `routing/follow_up_classifier.py` (`FollowUpRoute`, `FollowUpClassifier`) decides whether a request should reuse cached SQL, jump to stock-only lanes, or execute the full planner.
- `scripts/schedule_replay.py` (`annotate_events`, `summarize_events`, `render_summary`) and backend-ledger tooling replay SSE logs for audits.


---



## 12. Legacy Code (Disconnected Paths)
- **Regression-only sequential pipelines.** Functions such as `analytics_agent.AnalyticsWorkflow._build_market_share_sql()`, `_build_margins_sql()`, `_build_rnd_sql()`, and `_build_echarts_spec()` only power the JSON fixtures exercised by `backend/tests/analytics/test_pipeline_*`; runtime flows never import `AnalyticsWorkflow`, so these helpers remain solely for regression diffing until the suites migrate to `PlannerSequencer`.
- **Fallback environment switches.** `flows/workflow._env_flag()` and `_agentic_revision_enabled()` still parse `ANALYTICS_ENABLE_AGENTS`, `AGENTIC_REVISION_SINGLE_AGENT`, and `AGENTIC_REVISION_PLANNER_EXECUTOR` for rollback control, but the guarded branches no longer map to active deployments; keep them documented as rollback-only toggles until the env flags are retired.
- **Session/tool cache compatibility layers.** `core.session_state.SessionStateSnapshot.record_agent_run()` and `agent_orchestrator.memory.AgentMemory.record_tool_receipt()` continue writing the legacy `tool_cache["agent"]` schema (run IDs, receipts, retry counts) alongside the typed `agents_*` fields so historic snapshots remain readable; once old sessions expire we can delete the shim code.
- **Artifact schema bridges.** `artifacts.models.BaseArtifact.to_dict()` still emits the flattened payload the React canvases expect while also keeping the richer dataclass payload; after the UI drops the legacy props we can remove the dual-shape serialization.

## 13. Optimization Opportunities
- **Concurrent runs.** `flows.planner.fanout.start_tool_parallelism()` rebuilds adapter queues for every retry, and `flows.sequencer.PlannerSequencer.__init__()` recomputes `_lane_states`/dependencies even when a session reuses the same `PlanTemplate`. Caching per-session plan snapshots would let retries rehydrate the queue/lane graph instead of rebuilding them, unlocking higher concurrency without starving the event loop.
- **Shorter pipelines (no timeout hacks).** `routing.follow_up_classifier.FollowUpClassifier.classify()` re-tokenizes `_contains_any()` keywords on every query, and `flows.planner.revision.derive_revision_targets()` still walks every accessory lane even when `SessionStateSnapshot.lane_timestamps` prove they are fresh. Memoizing the normalized query + targets would shave seconds off revisions without relying on longer timeouts.
- **Shared components & telemetry.** `core.cache.CacheService.get_stats()` already surfaces Redis health, yet `flows.single_agent_tools._SingleAgentToolHooks._emit_tool_event()` rebuilds identical `ToolBundle` metadata per adapter and logs telemetry separately. Reusing a session-scoped `ToolBundle` plus piping `get_stats()` into the same `telemetry.tool_iteration` calls would shrink cold starts and give supervisors unified dashboards.
- **Reusable accessory bundles.** Accessory adapters still emit bespoke payloads before `flows/tool_bundle.collect_tool_bundle()` and `flows/planner/fanout.derive_accessory_events()` sanitize them. A shared response schema (web + market) would let both helpers pass the same structure downstream, reducing transform code and simplifying frontend hydration.

This architecture reference reflects the current state of the `next-gen-analytics-agent` project and should be updated alongside significant planner, tool, or telemetry changes.
