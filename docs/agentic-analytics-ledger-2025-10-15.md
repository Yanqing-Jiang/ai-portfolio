# Agentic Analytics Ledger — October 15, 2025

Single source of truth for the agentic analytics refactor. Update this ledger whenever scope, status, or deliverables change.

## 1. Program Status
- Completion sits at **≈62 %**. Remaining work spans UI telemetry/rendering, prompt refresh, broader regression coverage, and rollout playbooks.
- All agent flows (single + multi) now default to `gpt-5-mini-2025-08-07`; the GPT‑5 nano classifier and controller-driven fallback have been removed.
- Backend telemetry emits lane-aware metadata (`lane`, `parallel_group`, `flow_mode`, `reused`, `ts`) for cached and fresh fan-out events, narrowing the gap to ProcessPanel/WorkflowCanvas parity.
- Single- and multi-agent controllers emit `final_answer_only` guidance whenever cohesive data is incomplete, ensuring analysts receive actionable rerun instructions instead of a silent stall.

## 2. Delivered Milestones
- **Model standardization:** All prompts/agents call `gpt-5-mini-2025-08-07`; configs and regression tests reflect the shared default.
- **Fallback removal:** `_SingleAgentToolHooks.on_flow_end` no longer forces controller-level reruns; agents decide whether to request revisions or emit results.
- **Lane-aware telemetry:** Fan-out emissions (`sql_ready`, `stock_ready`, `web_ready`, `chart_ready`, lane summaries, agent turns) now include `lane`, `parallel_group`, `flow_mode`, `reused`, and timestamps across single- and multi-agent flows.
- **Guided final answers:** Controllers synthesize `final_answer_only` payloads that list missing components (`sql`, `stock`, `web`) and preserve analysis context when `cohesive_result` cannot be produced.
- **Regression coverage:** Updated `backend/tests/analytics/test_multi_agent_flow.py` to assert lane metadata + fallback messaging and added `backend/tests/analytics/test_single_agent_final_answer.py` to guard the single-agent guidance path.
- **Documentation trail:** Prior notes were consolidated into this ledger to track status, open items, and next actions.

## 3. Remaining Scope & Rationale
1. **Receipt-aware single-agent fan-out**
   - Persist `market_question_a`, `market_question_b`, and `web_retriever` receipts alongside SQL receipts so follow-up sessions can skip fresh runs while TTL permits.
   - Revision flows (`chart_revision`, `analysis_revision`) must inspect those receipts (e.g., “Swap the pie chart for a bar chart” should only rerun chart + narrative lanes while reusing market/web receipts).
2. **Supervisor DAG refresh**
   - Replace `_base_plan` with an explicit DAG honoring `intent_liaison → sql_chain → {viz, market, web, stock} → insight_reviewer`, while enabling concurrency for market/web/stock lanes.
   - Ensure component receipts gate reruns so “Refresh the chart” only replays SQL + viz lanes when inputs change.
3. **Telemetry & UI alignment**
   - Front-end reducers, hooks, and canvases must render the new metadata, dedupe specialist cards, and surface cached badges.
   - Add UI handling for `final_answer_only` payloads so off-topic or partial runs show guidance without cohesive content.
4. **Prompt refresh**
   - Update single-agent and supervisor blueprints with decline/reuse guidance, JSON exemplars, and rerun directives that mirror the new concurrency model.
5. **Regression & QA expansion**
   - Author async fan-out + receipt reuse pytest suites, bring up Playwright coverage for accessory cards, and extend Jest reducers for new telemetry fields.
6. **Staging rollout checklist**
   - Keep `ANALYTICS_AGENTIC_SINGLE` / `ANALYTICS_AGENTIC_MULTI` disabled until UI parity lands.
   - Document dual-run validation, monitoring dashboards, and on-call runbooks for `final_answer_only` sessions prior to enabling flags.

## 4. Detailed Execution Plan
### Step 1 — Consolidate receipts in single-agent flows
- Track market/web receipts in session state.
- Add helper to validate TTL and mark lanes as reused.
- Gate revision entry points so SQL changes trigger dependent reruns; pure narrative tweaks reuse cached lanes.

### Step 2 — Supervisor orchestration redesign
- Refactor `backend/analytics/flows/multi_agent.py` orchestration to follow the documented specialist order with explicit dependencies.
- Preserve concurrency for `market_agent`, `web_research_agent`, and `stock_chart` once SQL completes.
- Emit agent turns and receipts tagged with `parallel_group="multi_supervisor_fanout"` and lane metadata.

### Step 3 — Telemetry & UI updates
- **Backend complete:** emitters attach `lane`, `parallel_group`, `flow_mode`, and `reused` to cached/fan-out events and lane summaries; `final_answer_only` payloads surface missing lanes.
- **Frontend pending:** update `useAnalyticsMemoryStream.ts`, ProcessPanel reducers, and WorkflowCanvas nodes to render:
  - A single `Financial Analysis` card when SQL + web + stock artifacts are available.
  - Specialist cards (`Stock Chart`, `Web Chart`, `SQL Chart`, `Generated SQL`) as soon as their events arrive.
  - Clear handling for cached events and `final_answer_only` messages.

### Step 4 — Prompt & QA refresh
- Revise blueprint prompts with decline/rerun guidance and cached-lane exemplars.
- Add pytest coverage for prompt contracts and orchestrator reuse flows; bring up Playwright scaffolding for accessory card rendering.

## 5. Detailed Plans for Remaining Scope (Telemetry/UI + Rollout)

### 5.1 Telemetry & UI Alignment
- **Backend SSE schema**
  - ✅ Controller emitters now include `parallel_group`, `lane`, `flow_mode`, and `reused` metadata across cached fan-out events.
  - ☐ Add complementary assertions in `backend/tests/analytics/test_pipeline_tools.py` (and other suites) to guard future regressions.
- **ProcessPanel state machines**
  - Update reducers/selectors (`components/analytics/processPanel/ProcessPanelSlice.ts`, `ProcessPanelTimeline.tsx`) to group entries by `parallel_group`, badge cached lanes, and display `final_answer_only` guidance.
- **WorkflowCanvas rendering**
  - Patch `components/analytics/workflowCanvas/WorkflowCanvasStore.ts` / `.tsx` to dedupe accessory cards, annotate nodes with reuse metadata, and add Storybook snapshot coverage.
- **Validation**
  - Run `npm test -- analytics` after reducer updates; extend Jest cases for new telemetry fields and cached badges.

### 5.2 Prompt Refresh
- **Single-agent blueprint**
  - Inject decline/reuse guidance, cached-lane exemplars, and explicit rules for when SQL vs market/web vs chart reruns are required.
- **Supervisor blueprint**
  - Document the revised DAG order, concurrency rules, and `cohesive_result`/`final_answer_only` expectations; add JSON exemplars for decline paths.
- **Prompt QA**
  - Expand `backend/tests/analytics/test_prompt_contracts.py` (or new suite) to guarantee required keys (`analysis`, `tool_manifest`, `rerun_directive`) remain stable.

### 5.3 Regression & QA Expansion
- **Backend**
  - Add async fan-out integration covering TaskGroup concurrency, receipt reuse, and selective reruns.
  - Extend `test_multi_agent_flow.py` and new suites for chart-only revisions, cached accessory reuse, and telemetry assertions.
- **Frontend**
  - Introduce Jest coverage for ProcessPanel/WorkflowCanvas reducers with cached metadata and guidance cards.
  - Add Playwright flow under `frontend/tests/playwright/analytics/` for: (1) fresh single-agent run, (2) reuse follow-up, (3) supervisor orchestration with specialist cards preceding final summary.
- **Tooling**
  - Update `.github/workflows/analytics.yml` to run the expanded suites (pytest + Jest + Playwright) behind feature flags.

### 5.4 Staging Rollout Checklist
- Maintain feature flags off until telemetry/UI parity and prompt refresh land.
- Build `backend/scripts/compare_agentic_runs.py` for dual-run validation against legacy controllers (seed list of top staging queries).
- Capture Datadog/Grafana dashboards for `parallel_group` metrics and `final_answer_only` frequency; attach snapshots to launch review.
- Document on-call troubleshooting in `docs/oncall/agentic-analytics.md` (e.g., missing cohesive results, cached lane reuse issues).
- Expand this ledger (or Confluence) with go/no-go checklist, including prompt QA sign-off, UI approvals, latency benchmarks, and monitoring readiness.

## 6. Risk Log
- **Receipt drift:** Missing persistence risks redundant tool execution. Mitigation: add pytest assertions once receipt storage lands.
- **Supervisor race conditions:** Concurrency bugs could leave `cohesive_result` waiting forever. Mitigation: enforce TaskGroup joins + completion markers when DAG work begins.
- **Telemetry regressions:** UI components may ignore new `parallel_group`/`lane` values until reducers are updated. Mitigation: coordinate frontend work and add snapshot tests before rollout.

## 7. Next Checkpoints
- Land single-agent receipt persistence + supervisor DAG refresh with regression coverage.
- Follow with telemetry/UI updates and prompt refresh.
- Draft rollout documentation and dual-run tooling prior to enabling feature flags.

_Maintained by the agentic analytics working group. Update this ledger whenever milestones or scope change._
