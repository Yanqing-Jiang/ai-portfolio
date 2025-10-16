# Agentic Analytics Ledger - October 15, 2025

Single source of truth for the agentic analytics refactor. Update this ledger whenever scope, status, or deliverables change.

## 1. Program Status
- Completion sits at **~62%**. Remaining work spans UI telemetry polish, prompt governance follow-ups, broader regression coverage, and rollout playbooks.
- All agent flows (single + multi) now default to `gpt-5-mini-2025-08-07`; the GPT-5 nano classifier and controller-driven fallback have been removed.
- Backend telemetry emits lane-aware metadata (`lane`, `parallel_group`, `flow_mode`, `reused`, `ts`) for cached and fresh fan-out events, narrowing the gap to ProcessPanel and WorkflowCanvas parity.
- Single- and multi-agent controllers emit `final_answer_only` guidance whenever cohesive data is incomplete, ensuring analysts receive actionable rerun instructions instead of a silent stall.

## 2. Delivered Milestones
- **Model standardization:** All prompts and agents call `gpt-5-mini-2025-08-07`; configs and regression tests reflect the shared default.
- **Fallback removal:** `_SingleAgentToolHooks.on_flow_end` no longer forces controller-level reruns; agents decide whether to request revisions or emit results.
- **Lane-aware telemetry:** Fan-out emissions (`sql_ready`, `stock_ready`, `web_ready`, `chart_ready`, lane summaries, agent turns) now include `lane`, `parallel_group`, `flow_mode`, `reused`, and timestamps across single- and multi-agent flows.
- **Guided final answers:** Controllers synthesize `final_answer_only` payloads that list missing components (`sql`, `stock`, `web`) and preserve analysis context when `cohesive_result` cannot be produced.
- **Prompt reuse guidance:** Supervisor agent prompts and the schema clarifier system prompt now describe cached-receipt etiquette, decline heuristics, and rerun directives; `backend/tests/analytics/test_prompt_contracts.py` snapshots the required language and verifies prompt version telemetry.
- **Regression coverage:** Updated `backend/tests/analytics/test_multi_agent_flow.py` to assert lane metadata and fallback messaging and added `backend/tests/analytics/test_single_agent_final_answer.py` to guard the single-agent guidance path.
- **Documentation trail:** Prior notes were consolidated into this ledger to track status, open items, and next actions.

## 3. Remaining Scope & Rationale
1. **Supervisor DAG refresh**
   - Replace `_base_plan` with an explicit DAG honoring `intent_liaison` → `sql_chain` → `{viz, market, web, stock}` → `insight_reviewer`, while enabling concurrency for market, web, and stock lanes.
   - Ensure component receipts gate reruns so "Refresh the chart" only replays SQL plus viz lanes when inputs change.
2. **Telemetry and UI polish**
   - Front-end reducers, hooks, and canvases must finish rendering new metadata, dedupe specialist cards, and surface cached badges consistently.
   - Add UI handling for `final_answer_only` payloads so off-topic or partial runs show guidance without a silent blank state.
3. **Prompt documentation and downstream alignment**
   - Capture JSON exemplars of `rerun_directive` payloads for cached lanes, publish prompt version notes, and brief analytics stakeholders before rollout.
4. **Regression and QA expansion**
   - Author async fan-out plus receipt-reuse pytest suites, bring up Playwright coverage for accessory cards, and extend Vitest reducers for new telemetry fields.
5. **Staging rollout checklist**
   - Keep `ANALYTICS_AGENTIC_SINGLE` and `ANALYTICS_AGENTIC_MULTI` disabled until UI parity lands.
   - Document dual-run validation, monitoring dashboards, and on-call runbooks for `final_answer_only` sessions prior to enabling flags.

## 4. Detailed Execution Plan
### Step 1 - Consolidate receipts in single-agent flows
- Track market and web receipts in session state.
- Add helpers to validate TTL and mark lanes as reused.
- Gate revision entry points so SQL changes trigger dependent reruns; pure narrative tweaks reuse cached lanes.

### Step 2 - Supervisor orchestration redesign
- Refactor `backend/analytics/flows/multi_agent.py` orchestration to follow the documented specialist order with explicit dependencies.
- Preserve concurrency for `market_agent`, `web_research_agent`, and stock tooling once SQL completes.
- Emit agent turns and receipts tagged with `parallel_group="multi_supervisor_fanout"` and lane metadata.

### Step 3 - Telemetry and UI updates
- **Backend complete:** emitters attach `lane`, `parallel_group`, `flow_mode`, and `reused` to cached fan-out events and lane summaries; `final_answer_only` payloads surface missing lanes.
- **Frontend pending:** update `useAnalyticsMemoryStream.ts`, ProcessPanel reducers, and WorkflowCanvas nodes to render:
  - A single `Financial Analysis` card when SQL, web, and stock artifacts are available.
  - Specialist cards (`Stock Chart`, `Web Chart`, `SQL Chart`, `Generated SQL`) as soon as their events arrive.
  - Clear handling for cached events and `final_answer_only` messages.

### Step 4 - Prompt and QA refresh
- Revise blueprint prompts with decline and rerun guidance plus cached-lane exemplars (initial language landed; documentation and payload samples still pending).
- Add pytest coverage for prompt contracts and orchestrator reuse flows; bring up Playwright scaffolding for accessory card rendering.

## 5. Detailed Plans for Remaining Scope (Telemetry, UI, and Rollout)

### 5.1 Telemetry and UI Alignment
- **Backend SSE schema**
  - Controller emitters now include `parallel_group`, `lane`, `flow_mode`, and `reused` metadata across cached fan-out events.
  - Add complementary assertions in `backend/tests/analytics/test_pipeline_tools.py` (and other suites) to guard future regressions.
- **ProcessPanel state machines**
  - Update reducers and selectors (`components/analytics/processPanel/ProcessPanelSlice.ts`, `ProcessPanelTimeline.tsx`) to group entries by `parallel_group`, badge cached lanes, and display `final_answer_only` guidance.
- **WorkflowCanvas rendering**
  - Patch `components/analytics/workflowCanvas/WorkflowCanvasStore.ts` / `.tsx` to dedupe accessory cards, annotate nodes with reuse metadata, and add Storybook snapshot coverage.
- **Validation**
  - Run `npm test -- analytics` after reducer updates; extend Jest cases for new telemetry fields and cached badges.

### 5.2 Prompt Documentation and Contracts
- Publish decline and reuse exemplars alongside the supervisor blueprint and schema clarifier prompts.
- Expand `backend/tests/analytics/test_prompt_contracts.py` (and related suites) to guarantee required keys (`rerun_directive`, `cached_receipts`, `final_answer_only`) remain stable.

### 5.3 Regression and QA Expansion
- **Backend**
  - Add async fan-out integration covering TaskGroup concurrency, receipt reuse, and selective reruns.
  - Extend `test_multi_agent_flow.py` and new suites for chart-only revisions, cached accessory reuse, and telemetry assertions.
- **Frontend**
  - Introduce Jest coverage for ProcessPanel and WorkflowCanvas reducers with cached metadata and guidance cards.
  - Add a Playwright flow under `frontend/tests/playwright/analytics/` for: (1) fresh single-agent run, (2) reuse follow-up, (3) supervisor orchestration with specialist cards preceding the final summary.
- **Tooling**
  - Update `.github/workflows/analytics.yml` to run the expanded suites (pytest + Jest + Playwright) behind feature flags.

### 5.4 Staging Rollout Checklist
- Maintain feature flags off until telemetry/UI parity, prompt documentation, and regression suites land.
- Build `backend/scripts/compare_agentic_runs.py` for dual-run validation against legacy controllers (seed list of top staging queries).
- Capture Datadog and Grafana dashboards for `parallel_group` metrics and `final_answer_only` frequency; attach snapshots to the launch review.
- Document on-call troubleshooting in `docs/oncall/agentic-analytics.md` (for example, missing cohesive results or cached-lane reuse issues).
- Expand this ledger (or Confluence) with a go/no-go checklist, including prompt QA sign-off, UI approvals, latency benchmarks, and monitoring readiness.

## 6. Risk Log
- **Receipt drift:** Missing persistence risks redundant tool execution. Mitigation: add pytest assertions once receipt storage lands.
- **Supervisor race conditions:** Concurrency bugs could leave `cohesive_result` waiting forever. Mitigation: enforce TaskGroup joins and completion markers when DAG work begins.
- **Telemetry regressions:** UI components may ignore new `parallel_group` or `lane` values until reducers are updated. Mitigation: coordinate frontend work and add snapshot tests before rollout.

## 7. Next Checkpoints
- Land supervisor DAG refresh with regression coverage.
- Finish telemetry/UI polish and prompt documentation.
- Draft rollout documentation and dual-run tooling prior to enabling feature flags.

Maintained by the agentic analytics working group. Update this ledger whenever milestones or scope change.
