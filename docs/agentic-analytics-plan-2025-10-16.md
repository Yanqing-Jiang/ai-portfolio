# Agentic Analytics Update Plan - October 16, 2025 (20:05 EDT)

## 1. Confirmed Progress Since Last Update
- Backend receipt persistence (Workstream 2.1) closed on Oct 16: `backend/tests/analytics/test_session_state_receipts.py` now guards Redis snapshots that reuse `market_question_a`, `market_question_b`, and `web_retriever` receipts while honoring TTL expiry.
- Frontend telemetry wiring (Workstream 2.2) closed on Oct 16: `useAnalyticsMemoryStream` normalizes `lane`, `parallel_group`, `reused`, and `final_answer_only`; `ProcessPanel`, `WorkflowCanvas`, and `ProcessNode` render cached badges and lane chips with Vitest coverage in `useAnalyticsMemoryStream.reducer.test.ts` and `ProcessPanel.finalAnswer.test.tsx`.
- Documentation: ledger and plan files recorded the completed backend + frontend milestones; remaining tasks below mirror the Oct 15 ledger gaps.

## 2. Objectives In Flight
- Workstream 2.3: refresh agent prompts with explicit decline and reuse guidance that matches cached-lane behavior.
- Workstream 2.4: broaden regression coverage (pytest, Vitest, Playwright) for mixed fresh/reused lanes and UI guidance.
- Workstream 2.5: polish telemetry visuals and exports so cached lanes are distinguishable in analytics tooling.

## 3. Detailed Workstreams and Actions

### 3.1 Prompt Revamp (Workstream 2.3)
Goals:
- Ensure supervisor and single-agent prompts describe how to treat cached receipts, when to decline, and how to surface `final_answer_only`.
- Version prompts so contract tests detect drift.

Execution Steps:
1. Snapshot current copy  
   `Get-Content backend/analytics/agents/supervisor_blueprint.json`  
   `Get-Content backend/analytics/agents/schema_clarifier.py`
2. Draft reuse wording using concrete examples, e.g. instruct agents to respond with `{"rerun_directive": {"rerun": ["chart_lane"], "reuse": ["market_lane","web_lane"]}}` when only the chart needs refreshing.
3. Introduce decline heuristics such as: "If no cached receipts exist for a requested lane and inputs are missing, return `guidance.decline_reason = "insufficient_inputs"` and request a rerun."
4. Update loading utilities to expose `prompt_version` metadata surfaced in the emitted telemetry payload.
5. Regenerate fixtures and extend `backend/tests/analytics/test_prompt_contracts.py` to assert the new tokens (`cached_receipts`, `decline_reason`, `rerun_directive`).
6. Log the prompt changes in `backend/analytics/TO_DO.md` and append a summary row to the ledger after merge.

Deliverables:
- Updated prompt files with inline comments referencing reuse directives.
- Passing contract tests covering the new language.
- Example payloads captured in docs for analyst review.

### 3.2 Regression and QA Expansion (Workstream 2.4)
Goals:
- Prove that cached receipts are reused correctly and that UI guidance remains accurate under concurrency.

Execution Steps:
1. **Backend async fan-out pytest:** create `backend/tests/analytics/test_async_reuse_flow.py` that seeds Redis with a cached market receipt, runs a follow-up planner invocation, and asserts emitted events such as `{"lane":"market","reused":true,"parallel_group":"single_followup"}` while the chart lane reruns fresh.
2. Add TTL rollover coverage to ensure expired receipts force reruns; example assertion: `assert not event["reused"]` when `ttl=timedelta(seconds=0)`.
3. Plug the new suite into `pytest backend/tests/analytics/test_async_reuse_flow.py` and confirm it runs under CI.
4. **Playwright flow:** scaffold `frontend/tests/playwright/analytics/agentic-reuse.spec.ts` that (a) executes a fresh run, (b) triggers a cached rerun by replaying Markdown instructions, and (c) checks for the `Final answer uses cached market lane` banner.
5. **CI wiring:** amend `.github/workflows/analytics.yml` so Vitest reducers and the optional Playwright job run behind `PLAYWRIGHT_ANALYTICS=1`.
6. Expand Vitest reducer coverage to handle multiple cached lanes (e.g., chart + market) and assert chips render with `(cached)` suffix.

Deliverables:
- New pytest suite with deterministic fixtures for cached vs stale receipts.
- Playwright scenario validating cached badges and `final_answer_only` messaging.
- CI job updates ensuring the suites execute on every PR when flags are active.

### 3.3 Visual and Telemetry Polishing (Workstream 2.5)
Goals:
- Make cached vs fresh telemetry visually obvious and ensure exports include the new metadata.

Execution Steps:
1. Update `components/analytics/visualization/WorkflowCanvas.tsx` to render reused edges with a dashed emerald stroke and a tooltip example such as "Reused market insight from run #42."
2. Persist dismissal state for the `final_answer_only` banner in `ProcessPanel` using `localStorage.setItem("finalAnswerOnlyDismissed", "true")` so analysts are not spammed.
3. Enhance CSV export (`components/analytics/common/exporters/ProcessPanelCsv.ts`) to include `lane`, `reused`, and `finalAnswerOnly` columns.
4. Add Storybook stories capturing cached vs fresh edge styling and export snapshots for QA review.
5. Coordinate with analytics exporters to verify downstream consumers ingest the new fields; provide an example JSON payload in the docs.

Deliverables:
- Visual differentiation for cached edges and persisted banner state.
- CSV exports with cached metadata for analysts.
- Storybook artifacts for design review.

## 4. Sequenced Next Actions (Through Oct 20)
1. Complete prompt revamp steps 1-5, raise PR with contract tests (target Oct 17).
2. Land backend async reuse pytest and TTL coverage (target Oct 18).
3. Wire Playwright analytics spec plus CI gating (target Oct 19).
4. Deliver WorkflowCanvas styling + ProcessPanel persistence polish (target Oct 20), then update ledger with completed items.

## 5. Testing and Verification Checklist
- `pytest backend/tests/analytics/test_prompt_contracts.py`
- `pytest backend/tests/analytics/test_async_reuse_flow.py`
- `npm test -- components/analytics/hooks/__tests__/useAnalyticsMemoryStream.reducer.test.ts`
- `npm test -- components/analytics/common/__tests__/ProcessPanel.finalAnswer.test.tsx`
- `npx playwright test analytics/agentic-reuse.spec.ts` (requires `PLAYWRIGHT_ANALYTICS=1`)

## 6. Risks and Mitigations
- **Prompt drift:** Mitigate with versioned prompts and contract tests that fail on missing reuse clauses.
- **Redis availability:** Provide in-memory fallback in tests so the async reuse suite passes offline.
- **Playwright flakiness:** Keep the new spec behind `PLAYWRIGHT_ANALYTICS=1` until CI stabilizes and capture network traces on failure.
- **Telemetry consumers lagging:** Coordinate with downstream dashboards before changing export schemas; share example payloads and schedule dry runs.

## 7. Coordination Notes
- Keep `ANALYTICS_AGENTIC_SINGLE` and `ANALYTICS_AGENTIC_MULTI` disabled until prompts, regression suites, and visual polish ship.
- Notify analytics stakeholders once prompts update so they can review `final_answer_only` language before rollout.
- Ensure `docs/agentic-analytics-ledger-2025-10-15.md` is amended after the prompt revamp to document the milestone.
