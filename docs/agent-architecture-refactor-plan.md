<!-- Record progress by adding a bullet under each phase's task list-->

# Analytics Agent Architecture Evaluation

## Vision & Scope
- **Vision:** Adopt the “agent everywhere” architecture captured in `docs/New Text Document.txt` and `docs/refactor_roadmap_extracted.txt`: FlowMode.DIRECT stays deterministic via `PlannerExecutorFlow.events()` for instant answers, while FlowMode.SINGLE_AGENT and FlowMode.MULTI_AGENT run both fresh and revision requests on the OpenAI Agent SDK using a single canonical tool layer, shared session memory, and guardrails. Sessions pair Agent SDK sessions with `SessionStateSnapshot`, guardrails live at the agent level plus existing business policies, and no new feature flags are introduced (DIRECT remains the rollback path).
- **Scope:** Backend analytics controllers, shared tool registry, cache/session plumbing, SSE telemetry (`AgentsStreamBridge`), and analytics UI components (ProcessPanel, LiveArtifacts, WorkflowCanvas). DIRECT mode is left untouched; everything else transitions to the agentic pipeline described in the roadmap docs.

## Target State Overview

| Flow Mode | Orchestration | Notes |
| --- | --- | --- |
| **DIRECT** | Keep `PlannerExecutorFlow.events()` running SQL → chart → accessory → analysis deterministically with no agent session hydration. This mode powers “instant answer” demos and remains cache-independent. |
| **SINGLE_AGENT** | Both fresh and revision runs delegate to `agent_orchestrator.AgentRuntime` with a single planner agent. The agent invokes the same lane tools (`sql_lane`, `chart_lane`, `fanout`, `analysis_lane`, revision helpers). `PlannerSequencer` is an implementation detail only for DIRECT. |
| **MULTI_AGENT** | `MultiAgentFlow` hosts a supervisor/manager agent that calls lane specialists (`sql_specialist`, `chart_specialist`, `web_specialist`, `market_specialist`, `analysis_specialist`, `revision_specialist`) as OpenAI Agent SDK tools. Supervisors stream through `AgentsStreamBridge` so telemetry stays uniform. |

### Sessions & Guardrails
- Sessions pair OpenAI Agent sessions with `SessionStateSnapshot` to persist receipts and artifacts between fresh/revision runs.
- Guardrails live at the agent layer (input/output policies) plus our existing business guardrails (`SupervisorRetryManager`, `FollowUpClassifier`, latency guardrails). No new feature flags are required; FlowMode.DIRECT remains the rollback path.

## Current Architecture Snapshot
- Fresh DIRECT mode already executes the deterministic planner pipeline and records receipts through `SessionStateSnapshot`.
- Revisions in SINGLE_AGENT or MULTI_AGENT already stream Agent SDK events through `flows/agents_stream_bridge.AgentsStreamBridge`, but fresh runs in those modes still call the deterministic planner.
- Frontend code (`useAnalyticsMemoryStream.ts`, ProcessPanel, LiveArtifacts) depends on agent telemetry like `agent_coordination` and `web_topics_pending/ready`, so deterministic-only events force special cases whenever a fresh run isn’t agentic.


## Canonical Tool Layer (Shared Across Modes)
We need a single “golden” inventory that DIRECT, SINGLE_AGENT, and MULTI_AGENT all call. Each entry wraps existing Python modules; nothing new is invented.

| Tool | Implementation Source | Purpose |
| --- | --- | --- |
| `classification_tool` | `core.intent_impl.detection.classify_query_async` | Intent + routing metadata |
| `clarify_schema_tool` | `agents/schema_clarifier.decide_schema_clarification` + fallbacks | Template-required clarifications |
| `plan_sql_tool` | `sql.sql_planner.plan_sql_rule_based`, `sql.templates.fetch_templates_for_intent` | Build SQL plans |
| `compile_and_validate_sql_tool` | `sql.compiler.compile_sql_from_plan`, `sql.validator.validate_sql` | Render + validate SQL |
| `execute_sql_tool` | `sql.executor.execute_sql` + dataset preview/row-count normalization | Execute SQL and capture dataset artifacts |
| `build_chart_spec_tool` | `core.charting.plan_chart_rule_based`, `core.charting.build_chart_spec`, `PlannerExecutorFlow._generate_chart_design` | Create chart specs/metadata |
| `web_research_tool` | `services/response_search.build_web_research_questions`, `generate_search_topics`, `perform_response_search` | Multi-topic web searches |
| `market_data_tool` | `services/polygon.PolygonMarketDataClient` helpers | Fetch market data |
| `stock_widget_tool` | `StockTrackerAdapter` in `flows/tooling.py` | Stock cards |
| `analysis_writer_tool` | `flows/planner/analysis_lane.stream_analysis_lane` (fresh path) | Primary analysis writing |
| `analysis_revision_tool` | `analysis_lane` revision helpers + `emit_analysis_revision` | Narrative revisions |
| `chart_revision_tool` | `flows/chart_revision.py`, `PlannerExecutorFlow.emit_chart_patch` | Chart revisions |
| `lane_decision_tool` / `apply_revision_lane_tool` | `flows/planner/revision` helpers | Decide and apply revision targets |
| `follow_up_classifier_tool` | `routing/follow_up_classifier.py` | Decide stock-only / reuse / full pipeline |

These tools should be defined once (e.g., `tool_definitions.py`) and imported by the DIRECT planner, single-agent agent runtime, and multi-agent supervisor.

## Model & Guardrail Requirements
- **Pinned model:** All non-DIRECT modes must run on `gpt-5-mini-2025-08-07` (per `AGENTS.md`). This guarantees uniform reasoning/function-calling behavior and aligns with the existing project guidance.
- **Guardrails inside the SDK:** Migrate `FollowUpClassifier`, stock-only short-circuits, and latency guardrails into Agent SDK guardrail policies so business rules live alongside agent instructions. Tool wrappers should still emit `guardrail_trip` / `guardrail_recovered` metadata for ProcessPanel badges.
- **Session parity:** Combine Agent SDK sessions with `SessionStateSnapshot` so cached artifacts persist automatically between fresh and revision runs, while FlowMode.DIRECT stays stateless.

## Phase Roadmap
Only SINGLE_AGENT and MULTI_AGENT modes change; FlowMode.DIRECT remains deterministic. Log progress under each phase’s bullet list (date • owner • status) so the doc doubles as a status ledger.

### Phase 0 – Invariants & Scaffolding
- **Invariants**
  - DIRECT keeps running `PlannerExecutorFlow.events()` (SQL → chart → accessories → analysis) with zero agent hydration; it is the rollback path.
  - Every non-DIRECT mode (fresh + revision) must stream via the Agent SDK and `AgentsStreamBridge` so UI, telemetry, and ledgers stay identical.
- **Tasks**
  - Create `backend/analytics/tools/__init__.py` and `backend/analytics/tools/definitions.py` with `ToolId`, `ToolDefinition`, `TOOL_REGISTRY`, `schema_version`, optional `depends_on`, and `run_tool_by_id(...)`.
  - Make `flows/pipeline_tools.get_planner_tool_registry()` a thin adapter over the new registry; generate Agents manifests from the same data.
  - Add a CI check that the JSON schema for each tool in DIRECT’s adapter matches the Agents manifest byte-for-byte.
- **Progress (November 19, 2025 – Codex):** Delivered the shared `backend/analytics/tools/definitions.py`, rewired `pipeline_tools` and agent manifests to consume it (with schema_version + depends_on), exposed `run_tool_by_id`, and added a planner parity assertion so DIRECT and Agent SDK paths stay in lockstep.
- **Acceptance**
  - A single registry powers DIRECT, SINGLE_AGENT, and MULTI_AGENT; manifests are generated from it, guaranteeing schema parity.

### Phase 1 – Canonical Tool Layer
- **Tools to wrap:** classification, clarify, plan SQL, compile/validate SQL, execute SQL (plus preview normalization), build chart spec, web research, market data, stock widget, analysis writer, analysis revision, chart revision, lane decision/apply, follow-up classifier (temporary).
- **Tasks**
  - Define strict JSON schemas, `schema_version`, and `depends_on` (e.g., `build_chart_spec_tool` depends on `execute_sql_tool`) for every tool.
  - Populate `ToolInvocationReceipt.metadata = {schema_version, guardrail, elapsed_ms, retry_count, from_cache, lane}` and persist via `SessionStateSnapshot.record_tool_receipt`.
  - Add unit tests per wrapper to assert the underlying lane adapter ran and receipts contain the new metadata.
- **Progress (November 19, 2025 – Codex):** Shared tool schemas (`ToolDefinition` + `depends_on`) now feed DIRECT + agent flows; metadata persistence/tests remain to be implemented.
- **Acceptance**
  - Planner adapter, single-agent controller, and supervisor import the same `TOOL_REGISTRY`; CI enforces schema parity.

### Phase 2 – SINGLE_AGENT on AgentRuntime (fresh + revision)
- **Controller**
  - Route both fresh and revision SINGLE_AGENT flows through `agent_orchestrator.AgentRuntime.run(...)` (DIRECT untouched).
  - Introduce `FreshRunPlannerAgent` (force SQL → chart → accessories → analysis) and `RevisionPlannerAgent` (hydrate `SessionStateSnapshot`, honor `revision_targets`).
- **Guardrails & session**
  - Convert `FollowUpClassifier` into an Agent SDK input guardrail (stock-only / reuse / full). Persist verdicts until all consumers read guardrail metadata.
  - Apply latency budgets at the agent level; annotate per-tool verdicts in receipt metadata (`guardrail.latency`).
  - Treat Agent SDK sessions as execution state only; `SessionStateSnapshot` remains source of truth with TTL-based reuse.
- **Telemetry/UI**
  - Stream Agent SDK `run_step` as `agent_reasoning`, `agent_tool_call`, `agent_tool_complete` via `AgentsStreamBridge`.
  - Ensure `useAnalyticsMemoryStream.ts` handles SINGLE_AGENT fresh telemetry exactly as it already handles revisions.
- **Tests/Acceptance**
  - Fixed-prompt parity suite (DIRECT vs SINGLE_AGENT fresh) for SQL/Chart/Analysis artifacts.
  - SSE ordering checks (reasoning → tool_call_delta → tool_complete) and guardrail verdict presence.

### Phase 3 – MULTI_AGENT supervisor + specialists-as-tools
- **Orchestration**
  - Register specialists (SQL, chart, web, market, analysis, revision) as tools backed by Phase 1 wrappers; stick with manager + specialists-as-tools (handoffs later).
  - Keep retries under `SupervisorRetryManager`; persist `agents_delegation_policy_version` and decisions in the snapshot.
- **Metadata**
  - Emit `specialist_id`, `specialist_role`, `lane`, `schema_version`, `from_cache`, `elapsed_ms`, `retry_count`, `guardrail` on every tool event/receipt; forward through `AgentsStreamBridge`.
- **Telemetry/UI**
  - Forward `agent_turn_start/end`, supervisor summaries, and tool receipts using the same envelopes as SINGLE_AGENT.
- **Tests/Acceptance**
  - Supervisor E2E tests: revision prompts rerun only the needed tools; SQL lanes show reuse badges; delegation metadata present.
  - Acceptance = MULTI_AGENT fresh + revision run fully on the Agent SDK, emitting the same schema as SINGLE_AGENT with specialist tags.

### Phase 4 – Telemetry + Frontend Alignment
- **AgentsStreamBridge**
  - Emit unified envelopes: summarized `agent_reasoning`, streamed `agent_tool_call`/`tool_call_delta`, `agent_tool_complete`, `agent_turn_start/end`, `web_topics_pending/ready`, guardrail payloads (no new event types).
- **Hooks/Components**
  - `useAnalyticsMemoryStream.ts`: build ProcessPanel steps from Agent SDK events for SINGLE_AGENT + MULTI_AGENT; dedupe via `thought_id`/`agent_turn_id`; buffer analysis until `web_topics_ready`.
  - `ProcessPanel`/`WorkflowCanvas`: render specialist labels, reuse badges (`Reused • <age> • fast_path <ms>`), guardrail badges (pass/blocked/recovered); drop deterministic-only logic for non-DIRECT modes.
  - `LiveArtifacts`: attribute artifacts to specialists, show topic counts/latency, and reuse badges.
- **Tests/Acceptance**
  - Vitest snapshots + ledger replays verifying identical envelope consumption for single-agent vs supervisor runs.
  - Acceptance = UI shows the same evidence for fresh/revision in SINGLE_AGENT and MULTI_AGENT; DIRECT remains distinct.

### Phase 5 – Legacy deletion & config simplification
- **Delete**
  - Sequential helpers in `analytics_agent.AnalyticsWorkflow._build_*` (market_share, margins, R&D, echarts) and dependent tests.
  - Planner-only revision helpers once agents own revisions; legacy env toggles (`ANALYTICS_ENABLE_AGENTS`, `AGENTIC_REVISION_*`); compatibility shims (`tool_cache["agent"]`, dual artifact serialization).
- **Keep**
  - DIRECT planner/tests, `ANALYTICS_FLOW_MODE`, TTL + cache env vars.
- **Acceptance**
  - No planner-based code paths for agentic flows; env surface reduced to essentials; DIRECT remains the fallback.

### Frontend File-Level Work (Phases 2–4)
- `components/analytics/hooks/useAnalyticsMemoryStream.ts`: consume `agent_turn_*`, `agent_tool_*`, `lane_reused_*`, `workflow_redirect/cancelled`, `web_topics_*`; coalesce steps by `agent_turn_id`; hide fresh-lane pills during revision; render badges.
- `components/analytics/common/ProcessPanel.tsx`: key cards by `tool_call_id`; show reuse/retry/guardrail badges; label with `specialist_role`.
- `components/analytics/visualization/WorkflowCanvas.tsx`: display supervisor timelines (manager + specialists), attribute artifacts, and distinguish single-agent vs supervisor layouts.
- `components/analytics/memory/LiveArtifacts.tsx`: render specialist attribution, topic counts, guardrail badges, and cache-age indicators.

### Guardrails, Sessions, TTL, SSE Contract
- Guardrails live in the Agent SDK config; tool wrappers only annotate receipts.
- `SessionStateSnapshot` is source of truth; agent sessions are ephemeral; TTL enforcement gates reuse on snapshot freshness.
- No new SSE events: guardrail data rides inside `agent_tool_call/complete`; fatal agent errors reuse `workflow_error` with `error_code="agent_runtime_fatal"`.

### Kill List (Phase 5)
- Remove legacy functions in `backend/analytics_agent.py` (`_build_market_share_sql`, `_build_margins_sql`, `_build_rnd_sql`, `_build_echarts_spec`) and planner-only revision helpers.
- Delete env toggles (`ANALYTICS_ENABLE_AGENTS`, `AGENTIC_*`) and legacy cache bridges once UI consumes `agents_*` fields exclusively.

### Observability, CI, and Rollback Expectations
- **Logging:** always log run_id, manager_trace_id, parent_run_id, agent_role, tool_name, tool_call_id, argument/output digests, elapsed_ms, retry_count, model/version, delegation policy, flow_mode, session_id, cache info (age_seconds), topic_count, prompt fingerprints, guardrail verdicts.
- **CI/Regression:** nightly diff (DIRECT vs SINGLE_AGENT fresh) for artifacts + ledger schema parity; SSE sequence tests (e.g., `session_started` presence, `lane_reused_*` ordering); Playwright/Vitest snapshots for ProcessPanel/WorkflowCanvas.
- **Rollback:** runtime selector flips flow to DIRECT; agents may emit `workflow_redirect: "direct"` on fatal guardrail/tool bootstrap to rerun deterministically—no other feature flags needed.

## Evaluation & Ops Plan
1. **Stage 0 – Roadmap criteria:** Keep the “Done Criteria” from `docs/agentic-roadmap.md` (agent loop, context hydration, telemetry parity, accessory guarantees, multi-agent story, docs/tests). Fresh runs fail if they don’t emit Agent SDK evidence.
2. **Stage 1 – Ledger replay:** Use the ledger tooling from `docs/agent-process-ledger-investigation.md` to confirm fresh and revision sessions now share the same event schema (`flow_mode`, `run_step.type`, guardrail metadata).
3. **Stage 2 – Telemetry gates:** Enforce the `docs/revision-card-handoff.md` requirements (every `web_topics_pending` must have a matching `ready`, `agent_coordination` must precede downstream tools, guardrail badges must appear on cards).
4. **Stage 3 – UI capture:** Store screenshots of ProcessPanel + LiveArtifacts for each flow mode with ledger hashes attached. This replaces the manual badge-check to-do item from the ledger doc.
5. **Stage 4 – Metrics:** Publish latency, retry counts, guardrail trips, and cache reuse rates for DIRECT, SINGLE_AGENT (fresh + revision), and MULTI_AGENT. Keep this table inside this document for demo prep.

## Implementation Order (Checklist)
1. Common tool layer + registry.
2. SINGLE_AGENT fresh runs via AgentRuntime (reusing revision instructions).
3. MULTI_AGENT supervisor + specialists-as-tools.
4. Revision unification (ensure all revisions use the agent runtime; delete planner revision fallbacks).
5. Frontend telemetry cleanup.
6. Legacy code/flag removal.

At the end: DIRECT = deterministic baseline; SINGLE_AGENT = planner agent over shared tools (fresh + revision); MULTI_AGENT = supervisor + specialists-as-tools. All telemetry flows through Agent SDK events, tool receipts remain in `SessionStateSnapshot`, and revisions never depend on planner-only paths.

## Testing & Validation Strategy
1. **Tool wrapper unit tests:** Cover each new tool definition to ensure it invokes the underlying lane generator/adapter and records receipts correctly.
2. **Regression parity vs DIRECT:** For a representative prompt set, compare SINGLE_AGENT fresh outputs against FlowMode.DIRECT to confirm artifacts (SQL, chart, analysis) match within acceptable variance before retiring the deterministic path for non-DIRECT modes.
3. **SSE event sequence tests:** Extend `agents_stream_bridge`/telemetry tests to assert that fresh runs emit the full agent event sequence (reasoning, tool_call_delta, summaries) and that events appear in a logical order with matching IDs.
4. **Guardrail + performance tests:** Simulate scenarios like stock-only follow-ups or delayed web searches to verify guardrail verdicts, latency guardrails, and skip behavior still fire via the agent runtime.
5. **Direct mode regression tests:** Keep existing DIRECT tests untouched to ensure planner shims don’t affect the instant-answer path.
6. **End-to-end UI tests:** Refresh Playwright/Vitest suites to verify ProcessPanel and LiveArtifacts render the new timeline, badges, and specialist attribution for fresh and revision flows.
7. **Parallel/stress tests:** Exercise concurrent agent runs (especially supervisor mode) to ensure tool concurrency, retries, and SSE fan-out remain stable under load.

## Logging & Ops Considerations
- Record Agent SDK run IDs, success/failure status, and guardrail outcomes alongside existing telemetry so Ops can trace any incident.
- Enhance `AgentsStreamBridge` to emit error events if a tool or agent run fails, allowing the frontend to render actionable error states and backend logs to capture stack traces.
- Capture token usage or latency stats provided by the Agent SDK for future observability dashboards, mirroring the roadmap’s emphasis on evidence-backed demos.
- Maintain a ledger of manual badge/screenshots (as described in `docs/agent-process-ledger-investigation.md`) until the automated eval plan fully replaces those artifacts.

## Design & Architecture Decisions (from `docs/New Text Document.txt`, `docs/refactor_roadmap_extracted.txt`, and `docs/new answers.md`)
1. **Tool registry & schemas**
   - Home: `backend/analytics/tools/definitions.py` exposes `ToolDefinition`/`TOOL_REGISTRY`.
   - Keep granular tools (plan vs execute) for agent flows; optional macro wrappers only for DIRECT experiments.
   - Every tool includes `schema_version`; adapters, receipts, and SSE payloads must emit identical schemas across modes (CI enforces byte-equality).
2. **Guardrails**
   - Persist `FollowUpClassifier` verdicts in `SessionStateSnapshot` until all consumers read agent guardrail metadata, then retire the classifier artifact.
   - Latency guardrails live at the agent level; tool wrappers log latency verdicts into receipt metadata so UI badges reuse existing fields.
   - SSE never gains new event types; guardrail objects ride inside `agent_tool_call/complete`.
3. **Sessions & TTL**
   - Agent sessions are execution-only; `SessionStateSnapshot` remains the source of truth. Every tool completion persists artifacts/receipts immediately.
   - Snapshot TTL governs reuse; agent session TTL mirrors it but snapshot freshness decides cache eligibility.
4. **Controllers**
   - Maintain distinct entry points: DIRECT → `PlannerExecutorFlow.events()`, SINGLE_AGENT/MULTI_AGENT → AgentRuntime controllers.
   - Fresh vs revision selection derives from session follow-up state + revision directives, with an optional override flag (no env toggles).
5. **Supervisor metadata**
   - Each tool event/receipt records `run_id`, `manager_trace_id`, `tool_call_id`, `specialist_id`, `specialist_role`, `lane`, `arguments_digest`, `output_digest`, `elapsed_ms`, `retry_count`, `from_cache`, `guardrail`, `schema_version`.
   - Defer Agent SDK handoff semantics; start with specialists-as-tools before layering nested ownership.
6. **Planner agent outlook**
   - Planner agent augments SINGLE_AGENT/MULTI_AGENT; FlowMode.DIRECT stays deterministic forever.
   - Add optional `depends_on` lists to tool definitions now to unblock future planner-generated ordering without rewriting the registry.
7. **Frontend behavior**
   - show summarized reasoning (aggregated deltas) by default with a dev toggle for raw thoughts.
   - Cache badges format: `Reused • <age_s_or_min> • fast_path <ms>`, always shown when reuse occurs.
8. **Testing & rollback**
   - Nightly diff suite compares DIRECT vs SINGLE_AGENT fresh outputs on a fixed prompt corpus, logging differences as artifacts.
   - Rollback path = switch flow selection to DIRECT; additionally, agents can emit `workflow_redirect: "direct"` on fatal guardrail/tool bootstrap errors so controllers retry deterministically.
9. **Logging & observability**
   - Must log Agent SDK run IDs, trace IDs, model/version, tool IDs, arguments/output digests, guardrail verdicts, delegation policy, cache info, topic counts, prompt fingerprints.
   - Fatal agent errors reuse `workflow_error` with `error_code="agent_runtime_fatal"` plus run IDs; UI branches on `error_code` without new SSE types.
10. **Phase coupling**
   - Tool registry extraction is the only hard prerequisite; after that, SINGLE_AGENT migration, supervisor refactor, and frontend updates can proceed in parallel once the shared SSE schema is locked.
   - Legacy deletion (flags, sequential helpers, compatibility shims) happens only after the agentic paths are stable.

## Status Snapshot
- **Completed:** Revision-mode Agent SDK integration, telemetry requirements, ledger investigations, frontend buffering logic, and this merged evaluation plan.
- **Outstanding:** Tool registry extraction, SINGLE_AGENT fresh migration, supervisor rework, frontend telemetry consolidation, and legacy cleanup steps listed above.
