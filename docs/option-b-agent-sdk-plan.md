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

### Phase 4 – Mode Integration (1 week)
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

### Phase 6 – Testing & Rollout (1 week)
- Backend: expand pytest suites for artifact generation, tool registry, single/multi-agent integration.
- Frontend: adjust mocks in `useAnalyticsMemoryStream` tests to reflect artifact-shaped SSE payloads; add regression tests for multi-result revisions.
- Manual QA: end-to-end runs for direct, single-agent, and multi-agent flows; follow-up revision scenarios; failure injection tests (missing artifacts, tool timeouts).
- Rollout plan:
  1. Ship behind a feature flag (`ANALYTICS_ARTIFACT_PIPELINE`).
  2. Dogfood on staging with Agents SDK tracing enabled.
  3. Gradually enable in production flows, monitoring metrics (latency, error rate, revision success).
- Deliverable: launch checklist + monitoring dashboards.

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

## Next Steps
1. Review and approve this plan.
2. Kick off Phase 0 spike to validate artifact modeling + Agents SDK handshake.
3. Schedule weekly checkpoints to track progress and unblock cross-team needs.

