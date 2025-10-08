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

