# Agentic Analytics – Concurrency & Cohesive Result Remediation Plan (Updated October 16, 2025)

## Objective
Align both single-agent and multi-agent execution paths with the expected professional “triad” workflow (structured SQL pipeline, market telemetry, and web research) so that:
- Market research questions A/B, stock widgets/charts, and SQL generation/visualization run once, in parallel where appropriate.
- Supervisors emit a single sanitized `cohesive_result` that blends SQL output, web insights, and market data, with specialists surfacing their own interim cards.
- Revision flows target the correct subsystem (e.g., chart reruns reissue the SQL chart) and the Financial Analysis card is deduplicated with rich context.

## Diagnostic Summary
- **Single-agent stall** (`docs/agent-process-ledger (26).json`): stream halts after `schema_validation`. SQL fan-out never starts, the ledger truncates, and the frontend cuts off mid-run.
- **Multi-agent failure** (`docs/agent-process-ledger (25).json`): SQL + chart succeed, but the supervisor errors with `TypeError: unhashable type: 'slice'` while packaging `cohesive_result`. Downstream cards/charts never arrive.
- **Front-end state**: Financial Analysis card currently mirrors markdown only; it is not guaranteed to annotate which data sources were used. Specialist cards can duplicate if the same lane emits multiple events.

---

## Workstream S — Single-Agent Concurrency & Rerun Governance
| Item | Description | Owner | Success Metrics | Validation |
| --- | --- | --- | --- | --- |
| S1 | Refactor planner fan-out (`backend/analytics/flows/single_agent_tools.py:976-1238`) so SQL generation, market questions A/B, and stock tracker run under a coordinated TaskGroup. Ensure `sql_generation` starts without waiting for fan-out drains and that `market_question_a/b` share a concurrency budget of 2. | Backend | Ledger shows overlapping `parallel_group` values: `core_sequential` (SQL), `single_agent_market`, `single_agent_web` with interleaved timestamps; no stalled `tool_execution`. | `py -m pytest backend/tests/analytics/test_single_agent_flow.py::test_parallel_sql_market_web` *(new)* |
| S2 | Guarantee stock chart widget emission in the single-agent path. When the market lane completes, emit a distinct `stock_ready` event and persist `stock_widget` in the cohesive bundle. | Backend | Ledger contains `stock_ready` with `lane: market`, and ProcessPanel shows “Stock Chart” specialist card before supervisor synthesis. | pytest above + Vitest snapshot on reducer |
| S3 | Prevent duplicate Financial Analysis cards. Extend the reducer (`components/analytics/hooks/useAnalyticsMemoryStream.ts`) to collapse multiple `analysis_ready` events and enrich the card content with SQL/web/stock summaries extracted from the event payload. | Frontend | Only one “Financial Analysis” card renders; markdown references SQL columns, web summary, and stock highlights. | `npm test -- useAnalyticsMemoryStream.reducer.test.ts` *(new scenario)* |
| S4 | Implement targeted rerun policy. When the agent decides to refresh only the chart, route through `SingleAgentToolController.chart_revision` and ensure the SQL chart path re-runs (not accessories). Record decision telemetry for downstream analysis. | Backend | Ledger shows `agent_decision` noting rerun scope, followed by `chart_revision` events without reissuing `web_ready`/`stock_ready`. | `py -m pytest backend/tests/analytics/test_single_agent_chart_revision.py` *(new)* |

**Key Code Touchpoints**: `single_agent_tools.py`, `planner_executor.py`, `components/analytics/common/AnalysisCard.tsx`, `components/analytics/hooks/useAnalyticsMemoryStream.ts`.

---

## Workstream M — Multi-Agent Deduplication & Cohesive Result Hygiene
| Item | Description | Owner | Success Metrics | Validation |
| --- | --- | --- | --- | --- |
| M1 | Add guardrails in `MultiAgentFlow` so the orchestrator’s `query_phase` owns SQL execution and prevents duplicate planner tool runs (`_queue_artifact_event`, `_shared_context.tool_results`). Ensure `market_agent` and `web_research_agent` consult receipt freshness before rerunning. | Backend | Ledger shows a single `sql_compilation/sql_execution`, `market_question_a/b`, `web_retriever`; orchestration logs confirm TaskGroup concurrency. | `py -m pytest backend/tests/analytics/test_multi_agent_dedup.py` |
| M2 | Sanitize the cohesive payload before validation. Normalize slices, sets, and other non-JSON types within `collect_tool_bundle` and the supervisor packaging pipeline (`multi_agent.py:1861-2136`) to eliminate `unhashable type: 'slice'`. | Backend | `cohesive_result` emitted with SQL/web/stock data; no `cohesive_result_error` in ledger. | Same pytest + unit test for sanitizer |
| M3 | Ensure specialists publish their cards/chat messages prior to supervisor synthesis: SQL chart, stock chart, web context, generated SQL card. Update orchestrator outputs to include structured summaries for each specialist and surface them in the frontend stream. | Backend + Frontend | Chat log shows specialists posting individual results; ProcessPanel lists cards for SQL chart, Stock snapshot, Web insights before final analysis. | `npm test -- components/analytics/common/__tests__/ProcessPanel.specialists.test.tsx` *(new)* |
| M4 | Supervisor rerun strategy: add policy hook so the supervisor chooses which specialists to rerun (intent liaison, SQL chain, viz designer, market agent, web agent, insight reviewer). For chart rerun requests, confirm the SQL chart path executes, not cached assets. | Backend | Ledger shows `agent_decision` with rerun targets, `chart_generation` triggered accordingly, no duplicate accessory runs. | `py -m pytest backend/tests/analytics/test_multi_agent_rerun_policy.py` *(new)* |

---


**Progress Notes  2025-10-17**
- M1 *(in progress)*: Added artifact hashing + tool result fingerprints in backend/analytics/flows/multi_agent.py to suppress duplicate SQL/market/web emissions; pending TaskGroup concurrency validation and pytest coverage.
- M2 *(in progress)*: Cohesive payloads now sanitize bundle/tool metadata before validator checks, with structured logging for missing-key diagnostics.
- M3/M4 *(not started)*: Specialist pre-synthesis cards and supervisor rerun policies still outstanding; requires frontend reducer updates and orchestration hooks.

## Workstream U — UI/Telemetry Integration
| Item | Description | Owner | Success Metrics | Validation |
| --- | --- | --- | --- | --- |
| U1 | Update reducer & ProcessPanel to tag specialist cards with provenance (`sql`, `market`, `web`) and prevent duplicates via `(lane, source)` keys. Ensure the chat transcript surfaces explicit messages from each specialist. | Frontend | Cards display once with “SQL Chart / Stock Chart / Web Context” headings; chat window shows corresponding reasoning. | Targeted Vitest + manual smoke |
| U2 | Extend CSV export to include new concurrency metadata (`lane`, `parallel_group`, `reused`, `analysis_sources`). | Frontend | CSV export columns match backend schema; QA validated sample rows. | `npm test -- components/analytics/common/__tests__/ProcessPanelCsv.export.test.ts` *(recreated)* |
| U3 | Add ledger quick-filters for single vs multi-agent runs to assist QA in comparing concurrency traces. | Frontend | Toolbar toggle filters ledger entries by `flow_mode`. | `npm test -- components/analytics/common/__tests__/ProcessPanel.ledgerFilters.test.tsx` *(new)* |

---

## Workstream V — Validation, Tooling & Observability
| Item | Description | Owner | Success Metrics | Validation |
| --- | --- | --- | --- | --- |
| V1 | Restore exemplar fixtures (cached + decline) after regeneration and re-run `test_prompt_contracts.py`. | Prompts WG | Tests green; consolidated doc updated with new hashes. | `py -m pytest backend/tests/analytics/test_prompt_contracts.py` |
| V2 | Instrument logging around `_cohesive_validator.ensure` to capture offending payload keys during staging dry run. Remove instrumentation once sanitization passes. | Backend | Logs show sanitized payload summary; no type errors during dry run.| Staging dry-run checklist |
| V3 | Expand staging checklist to include new concurrency assertions (SQL/market/web timestamps), card counts, and cohesive result validation. | Docs Lead | Updated checklist stored in `docs/agentic-analytics-consolidated.md` with green status. | Manual peer review |

---

## Sequencing & Dependencies
1. **S1 + M1 groundwork** (concurrency + deduplication) must complete before frontend work (U1/U2) to avoid chasing unstable telemetry.
2. **S2/M2** (data emission & sanitization) rely on sanitized fan-out results; run in parallel once S1/M1 land.
3. **U1/U2** require stable payload shapes from S/M workstreams.
4. **S4/M4** (rerun policies) depend on earlier steps so reruns don’t resurrect duplicate runs.
5. **V1-V3** operate continuously; staging dry run.hould follow completion of at least S1–S4 and M1–M4.

**Suggested Cadence**
- Week 1: Complete S1, M1, M2; add logging instrumentation (V2).
- Week 2: Deliver S2, U1, U2, V1; start backend rerun policy work (S4/M4).
- Week 3: Finish S3/S4, M3/M4, V3; execute staging dry run.nd update consolidated doc.

---

## Test Matrix
- Backend:  
  - `py -m pytest backend/tests/analytics/test_single_agent_flow.py`  
  - `py -m pytest backend/tests/analytics/test_multi_agent_dedup.py`  
  - `py -m pytest backend/tests/analytics/test_multi_agent_rerun_policy.py`  
  - `py -m pytest backend/tests/analytics/test_prompt_contracts.py`
- Frontend:  
  - `npm test -- components/analytics/hooks/__tests__/useAnalyticsMemoryStream.reducer.test.ts`  
  - `npm test -- components/analytics/common/__tests__/ProcessPanel.specialists.test.tsx`  
  - `npm test -- components/analytics/common/__tests__/ProcessPanelCsv.export.test.ts`
- End-to-end (post-stabilization):  
  - `npm run dev` + manual ledger review  
  - Optional Playwright once fixtures restored: `PLAYWRIGHT_ANALYTICS=1 npx playwright test analytics/single-vs-multi.spec.ts`

---

## Next Actions
1. Finish M1 guardrails by wiring TaskGroup concurrency assertions plus backend pytest coverage (test_multi_agent_dedup.py), then validate M2 instrumentation during the upcoming staging dry run.
2. Kick off M3 specialist surfacing and outline supervisor rerun hooks for M4 before touching frontend reducers, ensuring provenance fields stay stable.
3. Refresh docs/agentic-analytics-consolidated.md once M1/M2 are green, then extend the staging checklist with the new logging fields ahead of the dry run.
