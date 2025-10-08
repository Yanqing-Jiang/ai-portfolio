# Current Identified Issues (October 8, 2025)

## Single-Agent Workflow Remediation Plan

## Current Symptoms
- **WorkflowCanvas lacks visible zoom controls**, so single-agent runs cannot quickly focus on dense supervisor/tool clusters.
- **Financial Analysis panel renders raw JSON fragments** instead of the requested TLDR + bullet narrative that blends SQL, stock, and research signals.
- **Chart revision retries fail with `CHART_REVISION_MISSING_SESSION`**, indicating session artifacts are not persisted between the initial run and revision requests.
- **Follow-up question routing is too coarse**: a narrow stock performance follow-up still reruns the full SQL/chart pipeline instead of targeting stock + analysis only.
- **Execution hotspots**: tool fan-out and web research consume ~34s, SQL compilation ~25s, delaying the final analysis.

> Example session (`agent-process-ledger (11).json`): **web_research_agent 33.9s**, **sql_compilation 25.4s**, **tool_execution 12.1s**, **plan_and_select_template 8.1s**, **analysis_generation 8.0s**, **classification 7.5s**.

## Workstreams & Action Items

### 1. Canvas Interaction & Telemetry Readability
- Add explicit zoom in/out + reset buttons pinned to the ProcessPanel header (or re-enable ReactFlow `Controls` with zoom toggles) so analysts can inspect the supervisor hub.
- Coordinate with `WorkflowCanvas` to expose `onZoomIn/onZoomOut` handlers and persist the zoom level in panel state (`processPanelState.zoom`).
- Extend canvas badges to surface `latency_budget_ms`/`concurrency_limit` tooltip copy for each node, reinforcing the new concurrency metadata path.

### 2. Narrative Synthesis Formatting
- Update `backend/analytics/core/analysis.py` prompt builder so the model always emits:
  1. `TL;DR:` heading (2-3 sentences).
  2. A bullet list (3-5 items) covering SQL metrics, stock move vs. requested period, and key headlines with `[n]` citations.
  3. Optional Watchouts paragraph when fundamentals diverge from news.
- Stream chunks through a Markdown normalizer that strips stray JSON braces before they reach `ReactMarkdown`.
- Cache the final cohesive payload as `analysis_markdown` in session snapshots for revisions.

### 3. Session Artifact Persistence & Revisions
- Ensure `PlannerExecutorFlow` saves chart + analysis artifacts via `SessionStateSnapshot.record_outputs()` immediately after each phase.
- On revision entry, hydrate session snapshots with `tool_parallel_manifest/results` so the revision adapters avoid `missing_session`.
- Add regression test: trigger chart revision after a completed single-agent run (`test_chart_revision_single_agent_followup`).

### 4. Follow-Up Query Specialization
- Introduce a lightweight follow-up classifier that compares the new query against the prior session context.
  - Example: Original "NVDA revenue growth (5y)" followed by "How did the stock perform last year?" should map to a **stock-only** branch (stock tracker + analysis refresh) without re-running SQL/chart.
  - Maintain guard rails: analysis generation still waits on SQL data when the follow-up requires it; otherwise reuse cached SQL artifacts.
- Surface routing decisions in telemetry (display lane badges: `reuse_sql`, `stock_only`, `full_pipeline`).

### 5. Hotspot Optimization & Instrumentation
- Web research: parallelize topic searches with stricter budget (target <12s) and prefetch cached Gemini snippets when `from_cache=true`.
- SQL compilation: investigate prompt construction overhead; consider caching template expansions or reusing compiled queries for adjacent follow-ups.
- Tool parallelism: throttle low-value adapters when latency budget is exceeded; expose per-tool timers in ProcessPanel ledger to monitor gains.
- Add a lightweight PowerShell script (`scripts/analyze-ledger.ps1`) to compute per-node averages across captured ledgers.

### 6. Validation Checklist
- Manual: run single-agent NVDA 5-year scenario, confirm zoom controls, TLDR markdown, and successful chart revision patch.
- Automated: extend `backend/tests/analytics/test_tool_metadata_flows.py` for follow-up routing, add UI snapshot for `WorkflowCanvas` zoom controls.
- Telemetry: verify SSE `tool_parallel_*` events include updated concurrency + routing flags; monitor via ProcessPanel.

## Multi-Agent Output Gaps (agent-process-ledger (13).json)

### Symptoms
- Multi-agent UI only surfaced the analysis card; SQL table, chart, stock widget, and search summaries were missing.
- Process ledger shows duplicated planner phases (classification, intent, plan) and lingering `schema_clarifier` step stuck `in_progress`.
- `sql_execution` remained `in_progress` with no `execution_stats`/`data_retrieved` events, so no dataset snapshot reached the frontend.
- Terminal `unknown` step raised `unhashable type: 'slice'`, indicating backend serialization failed near the end of the run.

### Telemetry Observations
- Tool fan-out succeeded (`stock_tracker` returned a ready widget, `web_retriever` supplied cached Gemini snippets), and chart generation produced an ECharts spec with ID `analytics:chart:e5f2b7d361d6`.
- Agent coordination emitted repeated `start` entries for SQL + chart tasks, suggesting the orchestrator replayed portions of the baseline flow after the direct planner finished.
- No `chart_generated`, `data_retrieved`, or bundle-style events were emitted before the error, so the React stream never captured chart/spec/sql payloads.

### Probable Causes
- Multi-agent orchestration re-enters planner phases post-analysis and hits `_create_planner_bundle` with an unserializable slice (likely originating from task metadata or adapter payload), triggering the `unhashable type: 'slice'` error before final emitters run.
- Without the final bundle/`analysis_complete` payload, frontend state never receives `chart_spec`, `sql`, `stock_widget`, or `web_context` even though intermediate tool telemetry succeeded.
- Duplicate planner steps imply hook ordering causes agents to execute while the baseline flow is still streaming, producing redundant status updates and race conditions around session snapshot persistence.

### Recommended Fixes
- Sanitize orchestrator outputs before calling `_create_planner_bundle` / `collect_tool_bundle` (convert slices and other non-hashable types to plain lists) and add regression coverage to ensure bundle serialization is JSON-safe.
- Emit a consolidated multi-agent result event (`planner_bundle` or reuse `cohesive_result`) that includes SQL sample, chart spec ID + payload, stock widget config, and web context; block `analysis_complete` until those artifacts are attached.
- Gate orchestrator replays so phases do not restart once the baseline planner sequence has completed, keeping `schema_clarifier` and `tool_fanout` from duplicating entries.
- Add targeted test: run `MultiAgentFlow.events()` on the AMD scenario and assert that `sql_execution` produces `execution_stats`, the planner bundle is JSON-serializable, and the final event exposes chart + stock metadata.

### Mitigation Progress (Oct 8, 2025)
- Multi-agent flow now sanitizes planner bundles and emits a `cohesive_result` payload with SQL samples, chart specs, stock widgets, and web context (see `backend/analytics/flows/multi_agent.py`).
- Session snapshots persist SQL, chart, and analysis artifacts immediately after each phase, reducing `CHART_REVISION_MISSING_SESSION` errors for follow-up revisions (`backend/analytics/flows/planner_executor.py`).
- Added regression coverage (`backend/tests/analytics/test_multi_agent_flow.py`) to assert the cohesive payload includes chart and stock metadata.

---

**Next Steps:** Prioritize Workstreams 1-3 in the upcoming sprint, then tackle the multi-agent bundle fixes above before adding follow-up routing and performance tuning. Document changes in `docs/option-b-agent-sdk-plan.md` after implementation.
