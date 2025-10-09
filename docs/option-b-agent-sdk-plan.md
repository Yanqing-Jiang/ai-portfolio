# Option B – Artifact-Centric Modularization with OpenAI Agents SDK
_Drafted: October 7, 2025_

## Goal
Refactor the analytics workflow so every core phase (classification, intent, SQL, chart, analysis, revisions) is a stateless tool that produces/consumes explicit artifacts. All three delivery modes—direct planner, single-agent, and multi-agent—compose these tools differently, and the OpenAI Agents SDK coordinates orchestration, tracing, and guardrails for the agent-based modes.

## High-Level Outcomes
- Replace the shared mutable `PlannerPhaseContext` with composable artifact models.
- Expose each phase as an SDK-compatible tool with structured inputs/outputs.
- Direct workflow remains deterministic but runs through the same artifact pipeline.
- Single-agent flow becomes an agent with a fixed plan of tool invocations.
- Multi-agent flow uses the Agents SDK supervisor + specialists; each specialist calls the appropriate tool handlers.
- Telemetry, SSE events, and session persistence work off artifact payloads.

## Oct 9, 2025 Updates �?? Slot + Chart Directives
- **LLM slot guidance:** update the structured intent prompt so that when a user query starts with or contains “who”, “which”, or “what” plus verbs like “lead/leader/top/highest/rank”, the model must return `comparison="all"`, `statistic="ranking_latest"`, and include the configured default ticker list in `tickers`. This guarantees the SQL templates pull every peer before sorting.
- **Ranking chart expectation:** add a `ranking_bar` preset (horizontal bar, tickers on Y, metric on X) in `charts.yaml` and teach `charting_impl.plan_chart_rule_based` / `charting.build_chart_spec` to emit that preset whenever `statistic="ranking_latest"` and multi-ticker rows return a single numeric measure. This keeps leaderboard answers (EPS, dividend payout ratio, operating leverage, etc.) aligned between SQL output and visualization.

## Phase Breakdown

### Phase 0 – Discovery & Spike (1–2 days)
- Inventory current phase boundaries in `PlannerPipeline`.
- Identify all mutable fields in `PlannerPhaseContext` and classify them by phase.
- Spike: refactor classification + intent phases to return simple artifacts and prove Agents SDK tool integration in isolation (unit test with mocked LLM responses).
- Deliverable: spike branch + write-up documenting artifact interfaces, SDK integration notes, open questions.

### Phase 1 – Artifact Modeling & Utilities (3–4 days)
- Create `backend/analytics/artifacts/` with dataclasses or Pydantic models:
  - `ClassificationArtifact`, `IntentArtifact`, `ClarificationArtifact`
  - `SQLPlanArtifact`, `SQLExecutionArtifact`, `ChartArtifact`, `AnalysisArtifact`
  - `RevisionArtifact` variants for chart/analysis adjustments
- Provide helper functions to merge artifacts into session snapshots.
- Update tests to cover serialization/deserialization of each artifact.
- Deliverable: artifact module + test coverage.
**Status (Oct 8, 2025):** Streaming analysis artifacts now persist chunk fragments while SSE continues (`AnalysisArtifact.fragments`), chart and analysis artifacts retain spec IDs plus dataset summaries instead of full datasets, session snapshots capture bounded artifact history/versions via `SessionStateSnapshot.record_artifacts`, and optional Gemini/Search dependencies stay guarded with stubs so tests remain offline-friendly.


### Phase 2 – Pipeline Refactor (1 week)
- Refactor each method in `PlannerPipeline` to accept explicit artifact inputs and return artifacts without mutating shared state.
- Replace `PlannerPhaseContext` with a lightweight `PipelineRunState` that just aggregates the latest artifacts for convenience (no in-place mutation).
- Maintain SSE emission by passing artifacts through existing hook interfaces.
- Update revision helpers to consume persisted artifacts.
- Deliverable: refactored pipeline + unit tests ensuring identical SSE output (golden-event comparisons).

### Phase 3 – Tool Registry Revamp (3–4 days)
- Redesign `pipeline_tools.py` so every handler wraps a single artifact-producing function.
- Define tool metadata for Agents SDK registration (name, description, input schema, output schema).
- Add latency budgets and telemetry metadata per tool.
- Deliverable: new registry with Artifact-aware handlers + updated documentation.
**Status (Oct 8, 2025):** Planner tool registry now exposes `latency_budget_ms` and `output_artifacts` metadata via `PlannerToolDefinition` and `describe_tools()` for Agents SDK integration, with regression coverage in `backend/tests/analytics/test_pipeline_tools.py`.


### Phase 4 – Mode Integration (1 week)
**Status (Oct 8, 2025):** PlannerExecutor flow now streams through the tool registry sequence (classification -> analysis) while single- and multi-agent telemetry surfaces registry latency budgets/output artifacts.
**Focus items (Oct 8, 2025):**
- Harden the multi-agent orchestration path so SQL execution, chart generation, stock snapshots, and web context are bundled before `analysis_complete`. The latest AMD run (`agent-process-ledger (13).json`) surfaced missing chart/SQL/stock cards and an `unhashable type: 'slice'` error while serializing the planner bundle.
- Sanitize orchestrator outputs (convert slices/non-hashable objects to lists) before calling `_create_planner_bundle` and `collect_tool_bundle`, then emit a consolidated result payload that the frontend maps to SQL/Chart/Stock components.
- Prevent duplicate planner phase replays by gating the post-analysis agent loop; add regression coverage asserting `MultiAgentFlow.events()` emits `execution_stats`, `chart_generated`, and a JSON-safe planner bundle for the AMD scenario.
- Status: cohesive result emission and bundle sanitization landed (Oct 8, 2025); follow up with FE validation once canvas updates ship.
- **Direct flow**: rewrite `PlannerExecutorFlow.events()` to sequentially call tool handlers, passing artifacts between them.
- **Single-agent flow**: build an Agents SDK “single executor” agent whose policy calls the tools in fixed order, emitting tool_call telemetry via hooks.
- **Multi-agent flow**:
  - Define supervisor agent and specialist agents (intent analyst, SQL specialist, viz designer, insight reviewer, market context).
  - Each specialist maps to one or more tool handlers using Agents SDK’s orchestration API (leveraging the SDK’s guardrails and tracing).
- Ensure SSE events align with current contract across all modes.
- Deliverable: updated flows + scenario tests (baseline run, follow-up query, chart revision).

### Phase 5 – Telemetry, Persistence & Docs (3–4 days)
- Update session snapshot persistence to store artifacts instead of raw context blobs.
- Rewire tracing and logging to include tool names and Agents SDK conversation IDs.
- Document the new architecture (`ARCHITECTURE.md`, `analytics-flow-overview.md`, `docs/revision-tools.md`).
- Deliverable: telemetry parity verified, docs updated.
**Pending work (Oct 8, 2025):**
- ? (Oct 8, 2025) Persist chart specs, analyses, and fan-out manifests/results after each phase so single-agent revisions no longer hit `CHART_REVISION_MISSING_SESSION` (see `planner_executor.py`).
- Capture stock widgets and web context inside the persisted bundle to keep ProcessPanel and WorkflowCanvas synchronized once the frontend zoom/hub updates ship.
- Document the analysis TL;DR + bullet contract so backend prompt formatting and React rendering stay aligned.

### Phase 6 – Testing & Rollout (1 week)
- Backend: expand pytest suites for artifact generation, tool registry, single/multi-agent integration.
- Frontend: adjust mocks in `useAnalyticsMemoryStream` tests to reflect artifact-shaped SSE payloads; add regression tests for multi-result revisions.
- Manual QA: end-to-end runs for direct, single-agent, and multi-agent flows; follow-up revision scenarios; failure injection tests (missing artifacts, tool timeouts).
- Rollout plan:
  1. Ship behind a feature flag (`ANALYTICS_ARTIFACT_PIPELINE`).
  2. Dogfood on staging with Agents SDK tracing enabled.
  3. Gradually enable in production flows, monitoring metrics (latency, error rate, revision success).
- Deliverable: launch checklist + monitoring dashboards.
**Status (Oct 8, 2025):** Executed targeted backend suites (`backend/tests/analytics/test_artifacts_models.py`, `test_pipeline_classification_intent.py`) to validate artifact persistence and pipeline phases; plan to rerun these after backend changes and add registry/golden-event tests before enabling `ANALYTICS_ARTIFACT_PIPELINE`.


## Integration with OpenAI Agents SDK
- Register each artifact tool with the SDK, providing strict JSON schemas for inputs/outputs.
- Use the SDK’s supervisor/specialist orchestration for the multi-agent flow:
  - Supervisor interprets user intent, schedules specialists, and monitors guardrails.
  - Specialists wrap tool handlers (e.g., SQL specialist calls `run_sql_tool`).
- Leverage SDK tracing to feed ProcessPanel/WorkflowCanvas telemetry via webhook or file export.
- Guardrails: configure the SDK’s policy hooks to enforce latency budgets and retry backoffs per tool.
- Deployment considerations: ensure API credentials/feature flags are managed via environment variables; update infra scripts to include Agents SDK dependencies.

## Resource & Timeline Estimate
- Total duration: ~4 weeks (backend-heavy, with 1 backend lead + 1 frontend/QA support).
- Critical path: Phases 2–4 (pipeline refactor, registry rewrite, flow integration).
- Dependencies: Agents SDK availability in our environment, updated unit test harness supporting async tools.

## Risks & Mitigations
- **Artifact drift**: Misaligned inputs/outputs between tools → add contract tests and type hints.
- **Telemetry regressions**: SSE consumers expect old payloads → maintain compatibility layer during transition and update frontend parsers.
- **Agents SDK learning curve**: Allocate spike time (Phase 0) for SDK prototyping; pair with OpenAI docs/examples.
- **Performance**: Artifact serialization overhead → benchmark during Phase 2 and optimize (e.g., reuse dataclasses, avoid deep copies).


## Additional Requirements (Added Oct 8, 2025)
- Preserve existing single-agent tool fan-out semantics end-to-end: artifact-producing tools must continue emitting `tool_parallel_*` telemetry so the ProcessPanel fan-out canvas renders without regression.
- Treat async tool execution as a first-class constraint in the Agents SDK integration; verify that the artifact-aware tool registry exposes concurrency limits and latency budgets that map directly onto SDK scheduling.
- Extend multi-agent visualizations to a supervisor-centric "hub and spoke" layout where the supervisor node anchors the diagram, specialists occupy labeled lanes, and their downstream tool calls are represented as nested branches for clarity in the Agent Thinking panel.
- Concurrency metadata is now exported with each planner tool, propagated through single-agent fan-out events and multi-agent `agent_turn` telemetry, and the WorkflowCanvas renders the supervisor hub with concurrent specialist branches.
- Multi-agent orchestration must emit a JSON-safe planner bundle (SQL sample, chart spec ID/payload, stock widget, web context) before `analysis_complete` so the frontend renders all artifacts.
- Analysis outputs must follow the TL;DR + 3-5 bullet narrative format that blends SQL metrics, stock movement, and headline context; enforce this in both prompt construction and frontend rendering.
- Persist session snapshots after each artifact phase to unblock follow-up chart/analysis revisions and guard against `CHART_REVISION_MISSING_SESSION`.

## Plan Evaluation & Next Steps (October 9, 2025)

### Mode-specific scheduling differentiation
- **Shared DAG, mode-specific scheduling:** The proposal keeps the artifact DAG fixed (`Classification → Intent → SQL → Chart → Analysis`) while differentiating concurrency per delivery mode. This aligns with Phases 2 and 4—codify the DAG once, then inject mode schedulers (`DirectScheduler`, `SingleAgentScheduler`, `MultiAgentScheduler`) that live alongside the registry. Example: for the AMD market-share run, the direct mode will run sequentially while the single-agent path can trigger `web_retriever` + `stock_tracker` as soon as `SQLPlanArtifact` is available.
- **Direct (Deterministic) mode:** Sequential execution plus post-analysis accessories reinforces the “Deterministic” badge already planned for the ProcessPanel. Action: add a `deterministic=true` flag to direct-mode SSE payloads and assert in golden-event tests (`tests/analytics/test_planner_executor_direct.py`).
- **Single agent mode:** Early fan-out plus artifact-scoped revisions map directly to the persistence fixes already queued. Example follow-up: “Show AMD chart in stacked area” should replay only `ChartArtifact` using `SessionStateSnapshot.last_sql`, not re-run the SQL compiler. Requires: persisted manifests + revision router (Phase 4 focus).
- **Multi agent mode:** Supervisor + specialist concurrency is consistent with the Agents SDK plan; add hedged tasks (e.g., dual SQL prompts) guarded by latency budgets already exposed via `PlannerToolDefinition`. Update WorkflowCanvas to label hedged tasks (`cache_hit`, `hedged_web`) for transparency.
- **Current progress (Oct 9):** Introduced a shared `FlowMode` infrastructure and annotated SSE with `mode`/`follow_up_route` badges. Direct mode now defers accessory fan-out until post-analysis, while single- and multi-agent flows keep concurrency badges surfaced through hooks. Cohesive result validation and follow-up routing metadata are wired into planner, single-agent, and multi-agent flows.
- **Scheduler registry (Oct 9):** Added `FlowStage`/`FlowSchedule` helpers plus `get_mode_schedule()` summaries in `backend/analytics/flows/schedulers.py`, delivering canonical ordering for direct/single/multi-agent modes and surfacing hedged accessory details (e.g., cached vs. live web retrievers). Regression coverage lives in `backend/tests/analytics/test_planner_schedulers.py`.

### Cohesive result contract and sanitization
- Promote the cohesive-result guardrail into a hard contract: no `analysis_complete`/`workflow_complete` without `{sql_sample, chart_spec_id, stock_widget, web_context}` populated. Implement a `CohesiveResultValidator` that fails fast when any artifact is missing or non-JSON-serializable.
- Serialization fixes: extend bundle sanitization to coerce slices/datetimes/dataclasses before `_create_planner_bundle`. Regression: replay `agent-process-ledger (14).json` through `MultiAgentFlow.events()` to ensure `unknown/error` disappears and `cohesive_result` emits once.
- Allow accessory deltas: web/stock updates can continue streaming after the initial cohesive payload; annotate ProcessPanel entries as `delta_web`, `delta_stock` so cards patch in place instead of re-rendering.
- Chart sanity checks: guard Chart artifacts with axis/data validation (e.g., AMD run currently set `["Q1","Q2","Q3","Q4"]` against multi-year data). Add `validate_axis_bindings(raw_data, chart_spec)` before emit and cover with snapshot tests.
- **Current progress (Oct 9):** Added reusable `CohesiveResultValidator` and JSON sanitization helpers, updated `MultiAgentFlow` to gate `cohesive_result` emission on the validator, emitted explicit `cohesive_result_error`, and layered chart scope banners plus artifact snapshots to persist across revisions.

### Persistence, revisions, and follow-up routing
- Persistence: treat `SessionStateSnapshot.record_outputs()` as blocking for every phase; fail revisions if persistence errors occur rather than falling back silently. Add coverage (`test_revision_snapshot_reuse.py`) that issues a chart tweak immediately after a run and asserts success.
- Follow-up routing classifier: implement lightweight heuristics (`stock_only`, `reuse_sql`, `full_pipeline`) keyed off artifact diffs. Example: prompt “How did AMD stock move last year?” should reuse `SQLExecutionArtifact` while re-running stock + analysis only. Surface chosen route in telemetry lane badges.
- Model/latency tuning: switch default Gemini helper to `gemini-2.5-flash-lite` for cached/parallel research and issue two parallel `web_retriever` calls (cached + live) using the new concurrency metadata.
- **Current progress (Oct 9):** Session persistence now records artifacts after each phase, context hydration pulls cached artifacts from snapshots, and a `FollowUpClassifier` + routing metadata thread follow-up intent through planner, single-agent, and multi-agent flows.

### Narrative output + UX framing
- Enforce TL;DR plus 3–5 bullet layout across all modes; ensure Markdown normalizer strips JSON remnants and attaches inline citations `[1]` etc. Add backend prompt unit covering NVDA 5-year scenario verifying TL;DR + bullet contract.
- Add a scoped banner above charts (`Basis: Revenue share across AMD, AVGO, INTC, MU, NVDA, QCOM, TXN`) so users can reconcile dataset membership with the TL;DR narrative.

### Updated next steps
1. **Scheduler abstraction (Phase 4 extension):** Wire the new `FlowSchedule` registry into planner/multi-agent timeline emitters and expand ledger snapshots so golden tests assert sequential vs. fan-out groupings (direct vs. single/multi). Example acceptance: direct NVDA run emits sequential timestamps; multi-agent shows parallel groupings with `hedged_web`.
2. **Cohesive-result validator:** Add guard + regression replay for the AMD ledger to prove JSON-safe payloads and absence of `unknown` errors.
3. **Persistence & routing:** Finish artifact persistence guarantees and introduce the follow-up classifier backed by targeted pytest coverage for chart revision + stock-only follow-ups.
4. **Narrative polish:** Ship TL;DR formatter, Markdown normalizer, and scope banner update, validating via Storybook snapshot and backend prompt test.

### Execution playbook (Updated Oct 9, 2025)
- **Progress log:** Mode-aware events now ship `mode`/`follow_up_route` badges; snapshot hydration keeps reuse_sql/stock_only paths fast; cohesive bundle validator protects multi-agent payloads; chart artifacts embed a scope banner derived from persisted tickers; Gemini defaults to `gemini-2.5-flash-lite` and sanitizer regressions are covered by unit tests.
- **Focus area 1 – Mode scheduler abstraction:** Harden `backend/analytics/flows/schedulers.py` and add golden-ledger tests ensuring direct runs stay sequential while single/multi-agent show early fan-out and hedged branches (`test_planner_schedulers.py`).
- **Focus area 2 – Cohesive result contract:** Leverage `backend/analytics/validators/cohesive_result.py` in planner + multi-agent flows, replay the AMD ledger to prove JSON safety, and extend pytest coverage for validator errors vs. sanitized emits.
- **Focus area 3 – Persistence & follow-up routing:** Persist artifacts after every phase via `SessionStateSnapshot.record_artifacts`, expose `FollowUpClassifier` heuristics, and add telemetry assertions (`test_follow_up_classifier.py`, upcoming `test_follow_up_routing.py`).
- **Focus area 4 – Narrative & chart fidelity:** Enforce TL;DR + Key points via `backend/analytics/core/analysis.py`, add chart scope banners, and line up frontend banner + Markdown snapshot coverage.
- **Focus area 5 – Research latency guardrails:** Default to `gemini-2.5-flash-lite`, parallelize cached/live searches, and validate hedged telemetry plus merged snippets in `backend/tests/analytics/test_web_research.py`.
- **Acceptance checklist:** deterministic direct ledger; single-agent revision reuse; multi-agent cohesive payload with all artifacts; TL;DR card + scope banner; hedged web searches with improved p50 latency.
- **Testing cadence:** targeted pytest modules per feature (validators, bundles, routing, schedulers), weekly `pytest backend/tests/analytics -m "not slow"`, and focused frontend Jest suites (`WorkflowCanvas`, scope banner, AnalysisCard) once UI hooks land.
### Oct 9, 2025 instrumentation update
- Scheduler helpers now expose stage indexes so instrumentation and downstream ledger writers can key events by `schedule_stage`.
- Analytics instrumentation streams apply the schedule metadata when enriching SSE payloads (parallel_group, schedule_stage, hedged awareness) without dropping the legacy fallback.
- Regression coverage: `pytest backend/tests/analytics/test_planner_schedulers.py tests/analytics/test_instrumentation_schedule.py -q` captures mode schedule summaries and instrumentation annotations.
- `apply_mode_metadata` consumes the cached stage index so all modes emit `parallel_group`, `schedule_stage`, and `stage_allows_parallel` without relying on instrumentation helpers.


### Oct 9, 2025 delivery increments
- Added `analytics.scripts.schedule_replay` CLI for annotating event exports with scheduler metadata to support manual ledger reviews.
- Session snapshots now retain up to 50 schedule-stage checkpoints so follow-up routing can reuse cached artifacts without replaying earlier phases.
- Follow-up classifier heuristics tap cached schedule history in addition to SQL/chart artifacts when deciding between `reuse_sql`, `stock_only`, and `full_pipeline` routes.

