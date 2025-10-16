# Agentic Analytics Update Plan - October 16, 2025 (13:19 EDT)

## 1. Confirmed Progress Since Last Update
- Backend receipt persistence (Workstream 2.1) closed on Oct 16: `backend/tests/analytics/test_session_state_receipts.py` guards Redis snapshots that reuse `market_question_a`, `market_question_b`, and `web_retriever` receipts while honoring TTL expiry.
- Frontend telemetry wiring (Workstream 2.2) closed on Oct 16: `useAnalyticsMemoryStream` normalizes `lane`, `parallel_group`, `reused`, and `final_answer_only`; `ProcessPanel`, `WorkflowCanvas`, and `ProcessNode` render cached badges and lane chips with Vitest coverage in `useAnalyticsMemoryStream.reducer.test.ts` and `ProcessPanel.finalAnswer.test.tsx`.
- Prompt governance (Workstream 2.3) delivered on Oct 16: `analytics.agents.schema_clarifier` and `SUPERVISOR_AGENT_SYSTEM_PROMPTS` now spell out cached-receipt etiquette, decline heuristics (`insufficient_inputs`), and rerun directives, with `backend/tests/analytics/test_prompt_contracts.py` snapshotting the required language and prompt version telemetry.
- Reuse regression scaffolding (Workstream 2.4) kicked off on Oct 16: `backend/tests/analytics/test_async_reuse_flow.py` validates cached lane events preserve `lane`, `parallel_group`, and `prompt_versions`, and `backend/tests/analytics/test_session_state_receipts.py` now asserts web-cache TTL expiry.
- Dual cached lane coverage (Workstream 2.4) closed on Oct 17: `components/analytics/hooks/__tests__/useAnalyticsMemoryStream.reducer.test.ts` now asserts both market and web lanes surface `reused=true`, and ProcessPanel renders `Market Insights (cached)` / `Web Insights (cached)` ledger labels in tandem.
- Documentation refreshed: the ledger captures the prompt milestone, and this plan is now aligned with the remaining gaps.

## 2. Active Objectives
- Workstream 2.4: regression and QA expansion for mixed cached/fresh lanes.
- Workstream 2.5: telemetry visuals, exports, and banner persistence to highlight reuse.
- Workstream 2.6: prompt exemplars, stakeholder enablement, and rollout comms.

## 3. Detailed Workstreams and Actions

### 3.1 Regression & QA Expansion (Workstream 2.4)
Goals:
- Demonstrate that cached receipts are reused correctly across async fan-out paths and that UI guidance survives reruns.

Execution Steps:
1. (Completed Oct 16) Land `backend/tests/analytics/test_async_reuse_flow.py` covering cached lane events and prompt-version metadata without invoking live tool runs.
2. (Completed Oct 16) Extend `backend/tests/analytics/test_session_state_receipts.py` with web TTL expiry coverage.
3. (Completed Oct 17) Extend Vitest reducer specs to cover dual cached lanes, asserting both `market` and `web` cache hits and verifying the ledger renders `"Market Insights (cached)"` / `"Web Insights (cached)"`.
4. Stand up `frontend/tests/playwright/analytics/agentic-reuse.spec.ts` that runs a baseline analytics session, repeats the query, and verifies the ProcessPanel banner displays `Final answer uses cached market lane - rerun chart to refresh visuals`.
5. Update `.github/workflows/analytics.yml` so `pytest backend/tests/analytics/test_async_reuse_flow.py` runs by default and the Playwright suite runs when `PLAYWRIGHT_ANALYTICS=1` is set (document the flag in the workflow help text).

Deliverables:
- Deterministic pytest and Vitest suites that exercise cached vs stale receipts.
- Playwright flow proving users see cached badges and rerun guidance after reuse.
- CI wiring documenting how to enable the heavier browser run.

### 3.2 Telemetry Visuals & Exports (Workstream 2.5)
Goals:
- Make reuse obvious inside WorkflowCanvas and downstream exports while keeping guidance dismissible.

Execution Steps:
1. Adjust `components/analytics/visualization/WorkflowCanvas.tsx` to render reused edges with `strokeDasharray="6 3"` and add a tooltip message such as `Reused market insight from run #42 (receipt mkt-42)`.
2. Persist the `final_answer_only` banner dismissal in `components/analytics/common/ProcessPanel.tsx` by storing `localStorage.setItem("aa.finalAnswerOnlyDismissed", "true")` and reading it on mount so analysts do not see repetitive prompts.
3. Update CSV export logic in `components/analytics/common/exporters/ProcessPanelCsv.ts` to append `lane`, `reused`, and `finalAnswerOnly` columns; include a sample row like `chart_lane,false,false` in the unit test fixture.
4. Capture Storybook stories (or Chromatic snapshots) that display side-by-side fresh vs cached edges and validate the tooltip copy.
5. Smoke-test downstream exporters by invoking `node scripts/dump-latest-analytics-event.js` (or equivalent helper) and confirming the new fields appear without breaking existing consumers.

Deliverables:
- Canvas visuals and ProcessPanel UX that clearly distinguish reused artifacts.
- CSV/Storybook assets demonstrating the enhanced metadata.
- Notes on downstream exporter verification for analytics stakeholders.

### 3.3 Prompt Exemplars & Stakeholder Enablement (Workstream 2.6)
Goals:
- Document the new prompt behavior and socialize rerun directives before rollout.

Execution Steps:
1. Capture JSON exemplars (e.g. `examples/prompts/rerun_directive_market_cached.json`) that show a supervisor response with `{"rerun_directive":{"rerun":["chart_lane"],"reuse":["market_lane","web_lane"]},"guidance":{"decline_reason":null}}`.
2. Update `backend/analytics/TO_DO.md` and `docs/agentic-analytics-ledger-2025-10-15.md` with a dated entry summarizing the prompt changes and linking to the exemplar files.
3. Draft a short stakeholder brief in `docs/analytics-rollout/2025-10-analytics-reuse.md` describing how analysts should interpret `final_answer_only` and cached lane badges, including screenshots from the new WorkflowCanvas styling.
4. Coordinate with the telemetry/export owners to ensure schema changes are announced; schedule a dry-run in staging with `ANALYTICS_AGENTIC_SINGLE=1` but `ANALYTICS_AGENTIC_MULTI=0` to limit blast radius.

Deliverables:
- Example artifacts and documentation that explain rerun directives in practice.
- Updated ledger entries and rollout notes ready for stakeholder review.
- Staging validation checklist aligned with the new prompts.

## 4. Sequenced Next Actions (Through Oct 21)
1. Oct 17 (Completed): Expanded the Vitest reducer suite and validated ledger copy via `npx vitest run --passWithNoTests useAnalyticsMemoryStream.reducer.test.ts` plus `npx vitest run --passWithNoTests components/analytics/common/__tests__/ProcessPanel.finalAnswer.test.tsx`; capture CI notes for inclusion in PR summary.
2. Oct 18: Implement WorkflowCanvas dashed-edge styling plus ProcessPanel banner persistence; validate with `npm test -- ProcessPanel.finalAnswer.test.tsx` and manual Storybook review.
3. Oct 19: Add CSV export columns and Playwright `agentic-reuse` spec, then wire the optional CI job; execute `npx playwright test analytics/agentic-reuse.spec.ts` with `PLAYWRIGHT_ANALYTICS=1`.
4. Oct 20-21: Produce prompt exemplars, stakeholder brief, and ledger updates after verifying staging dry-run results; ensure docs mention the dashed-edge visuals and cached badge behavior.

## 5. Testing & Verification Checklist
- `pytest backend/tests/analytics/test_prompt_contracts.py`
- `pytest backend/tests/analytics/test_async_reuse_flow.py`
- `npm test -- components/analytics/hooks/__tests__/useAnalyticsMemoryStream.reducer.test.ts`
- `npm test -- components/analytics/common/__tests__/ProcessPanel.finalAnswer.test.tsx`
- `npm test -- components/analytics/common/__tests__/ProcessPanelCsv.export.test.ts`
- `npx playwright test analytics/agentic-reuse.spec.ts` (run with `PLAYWRIGHT_ANALYTICS=1`)

## 6. Risks and Mitigations
- **Async cache drift:** If Redis is unavailable in CI, fall back to the in-memory repo within the new pytest; document the override via `USE_IN_MEMORY_CACHE=1`.
- **CSV schema changes:** Coordinate with BI exporters before adding columns; provide a sample row in the PR description to ease validation.
- **Playwright flakiness:** Gate the suite behind `PLAYWRIGHT_ANALYTICS=1`, capture HAR traces on failure, and fail fast if cached badges do not render.
- **Stakeholder misalignment:** Share the prompt exemplar brief ahead of staging tests so analysts understand `final_answer_only` messaging and cached badge semantics.

## 7. Coordination Notes
- Keep `ANALYTICS_AGENTIC_SINGLE` and `ANALYTICS_AGENTIC_MULTI` disabled in production until regression suites, visuals, and documentation deliverables ship.
