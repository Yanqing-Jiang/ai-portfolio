# Unified Intent & Clarification Plan (Updated 2025-10-18)

> Consolidated from `intent-clarification-execution-plan-2025-10-18.md` and earlier revisions.

## Objective
Deliver a unified, LLM-led intent resolution workflow that powers single-agent, single-agent fan-out, and multi-agent analytics flows. The system lets the model determine which slots are filled, flags missing information for clarification, and keeps YAML-driven configuration flexible without rigid, deterministic validation.

## Current Status (2025-10-18)
- **Phases A�"D complete.**  
  - Slot catalog service (`backend/analytics/core/slot_catalog.py`) parses YAML sources and is covered by `backend/tests/analytics/test_slot_catalog.py`.
  - `resolve_intent_slots` now feeds the planner with structured slot status, confidence, and follow-ups. Planner context persists `slot_statuses` and `slot_followups`, halting runs with `SLOTS_MISSING` when required slots remain unanswered.
  - Frontend `ClarificationOptions` renders follow-up cards, ChatHistory records selections, and ProcessPanel badges surface slot status across workflows.
  - `intent_resolution` telemetry is emitted with timing metadata; pytest guards (`test_intent_slot_resolution.py`, `test_intent_resolution_telemetry.py`, `test_template_requirements.py`) and Vitest suites cover backend/UX behaviour.
- **Phase E in progress.**  
  - `scripts/report_slot_catalog_usage.py` produces usage reports, but `backend/config/schemas/query_requirements.yaml` is still present pending audit.
  - YAML consolidation and pruning decisions are unresolved.

## Phase Breakdown
### Phase A �" Catalog & Prompt Foundations ✅
- Built slot catalog from `queries.yaml`, `metrics.yaml`, `companies.yaml`, and `query_requirements.yaml`.
- Added catalog-aware prompt hints; regression tests verify alias merging and defaults.

### Phase B �" Planner & Workflow Wiring ✅
- Planner executor invokes `resolve_intent_slots`, stores slot context, and halts on unresolved required slots.
- Multi-agent supervisor and single-agent tools consume shared slot state; `_has_company` checks replaced with slot-status lookups.
- Pytest coverage asserts company/timeframe/metric follow-ups for canonical prompts.

### Phase C �" Frontend Clarification UX ✅
- `ClarificationOptions` enables catalog suggestions plus custom entries; selections flow through ChatHistory.
- ProcessPanel shows slot status chips per workflow, keeping clarification transcript visible.
- Vitest ensures picker interactions dispatch the expected payloads.

### Phase D �" Telemetry, Tests, Documentation ✅
- `intent_resolution` analytics event logs confidence, slot states, and latency.
- Docs (`agentic-analytics-next-phase-plan.md`, consolidated analytics notes) describe new behaviour and QA recipes.
- Targeted pytest/Vitest matrices run green after integrations.

### Phase E �" YAML Optimization & Slot Schema Migration 🟡 In Progress
- Usage reporting script exists; next step is to run it across representative ledgers and commit a pruning plan.
- Decision still pending on merging or deleting `query_requirements.yaml`; dependent code paths need verification before removal.
- Catalog caching/performance benchmarks not yet captured.


### Detailed Remediation Plan (2025-10-18)
- **Curate metric suggestions** - Replace the 16-item metric prompt list with nine canonical measures (`Revenue`, `Net Income`, `Capital Expenditures`, `EPS Basic`, `Income Before Tax`, `Operating Income`, `Stockholders'' Equity`, `R&D Expense`, `Gross Profit`). Example: a prompt like "Show NVDA income before tax trends" should preselect `Income Before Tax` instead of forcing the user through aliases such as "earnings" or "net profit".
- **Natural-language timeframe presets** - Present presets as `last 4 quarters`, `last 8 quarters`, `last 5 years`, and `year to date` while still mapping back to the canonical values (`last_4_quarters`, etc.) that SQL templates expect. For example, selecting "last 5 years" should deserialize to `{ "years_back": 5 }`.
- **Structured custom inputs** - Normalize free-text timeframe entries into structured payloads where possible (e.g., "2019-2023" ? `{ "start_year": 2019, "end_year": 2023 }`; "past 6 quarters" ? `{ "quarters_back": 6 }`) so downstream planners receive validated numbers.
- **Intent routing nudges** - Ensure R&D expense questions ("How is R&D expense compared to industry average?") are routed straight to `rnd_expense_vs_peers` with `R&D Expense` pre-filled, and market-share questions default to `Revenue` unless a different metric is explicitly named ("What�s NVDA gross margin market share?" should flip the metric).
- **Frontend alignment** - Keep the "Financial Analysis ? TL;DR" copy inside the main chat bubble, pin the status/updates bar above charts, and persist structured values when a user confirms custom inputs so UI and backend stay in sync.
- **Revenue growth visualization** - Trace the YAML-driven chart spec and frontend renderer so `revenue_growth_vs_avg` charts actually render the SQL rows (target: confirm the data array is non-empty in `ChartCard`, add fallback logging if not).

## 2025-10-18 Implementation Notes
- Multi-agent workflow nodes now resolve to dedicated lanes (``planner``, ``sql``, ``market``, ``web``, ``chart``, ``analysis``) underneath a single supervisor hub. The start node feeds ``agent_coordination``, which in turn fans tasks into the vertical specialist stacks so the canvas mirrors the Untitled.png reference.
- The chat transcript keeps the streaming status badge anchored inside the most recent assistant bubble. Progressive updates and the final answer reuse the same ``result`` message instead of spawning an extra assistant reply.
- Metric and timeframe clarifications flow through normalized payloads: ``normalize_timeframe`` tracks the ``source``, slot statuses remain ``missing`` until the user responds, and the SQL planner/templates honour the curated metric list through the ``{primary_metric}`` placeholder.
- Added ``backend/tests/analytics/test_timeframe_normalization.py`` to guard the new timeframe semantics.
- Chart revision fast-paths now skip re-running market or web lanes; the UI clears cached SQL/analysis artifacts so chart-only tweaks render in the existing bubble without duplicate cards.
- Market share templates surface a single ``Market Share`` series with percent-only axes, and the dropdown honours ``displayNames`` metadata to avoid alias clutter. Regression coverage lives in ``backend/tests/analytics/test_chart_market_share.py`` and the updated ``ChartCard`` unit test.


## Remaining Work to Call This Initiative Complete
1. **Finalize YAML Audit**
   - Run `PYTHONPATH=backend py scripts/report_slot_catalog_usage.py --days 7` (or similar) on recent ledgers.
   - Document unused intents/metrics/aliases and decide whether to prune or merge into a single `slot_catalog.yaml`.
   - If `query_requirements.yaml` becomes redundant, remove it and update imports/tests accordingly.
2. **Catalog Performance & Caching**
   - Add lazy-loading or memoisation so repeated planner invocations do not re-read YAML from disk unnecessarily.
   - Capture before/after timing (e.g., average planner init in ms) and note results in docs.
3. **End-to-End Verification Across Workflows**
   - Re-run single-agent, fan-out, and multi-agent scenarios covering:  
     - “AMD market share analysis” → timeframe follow-up.  
     - “NVDA stock analysis” → metric + timeframe follow-ups.  
     - A fully specified query (no clarifications) to confirm direct progression.  
   - Ensure resulting ledgers capture clarification cards and no unintended halts.
4. **Documentation & Change Log Wrap-Up**
   - Update `docs/agentic-analytics-next-phase-plan.md` and `docs/agentic-analytics-consolidated.md` with Phase E outcomes, test evidence, and final QA checklist.  
   - Record decisions about retired YAML entries and provide rollback instructions.
5. **Operational Readiness Checks**
   - Confirm telemetry dashboards/alerts monitor `intent_resolution` volumes and slot-missing rates.  
   - Hand off UX guidelines (slot prompts, default styling) to design/research stakeholders.

## Definition of Done
- YAML audit complete with unused entries pruned or justified, and `query_requirements.yaml` either absorbed into the catalog or explicitly retained with rationale.
- Slot catalog cached or memoised with documented performance improvement.
- All three workflows validated end-to-end with updated ledgers demonstrating clarification loops and successful completion.
- Documentation updated and linked from analytics roadmap, including QA steps and telemetry pointers.
- No outstanding TODOs remain in code or docs referencing the legacy clarification path.

## Design References
- Dynamic prompt sections inspire catalog-fed planner prompts, enabling the LLM to reason about missing slots without rigid validators.
- Conversational UX from dialog slot-filling systems guided the decision to surface missing slot prompts explicitly with quick-pick buttons and optional “Other” free text.
- Agentic clarification loops favour explicit “clarify → ground → continue” cycles, mirrored in our follow-up list and planner halt/resume semantics.

## Document History
- **2025-10-17:** Initial unified plan drafted.  
- **2025-10-18:** Slot catalog, planner integration, frontend UX, telemetry, and testing completed; execution plan merged into this document; Phase E marked in progress.

