# Agentic Revision Rollout Plan (Single-Agent & Multi-Agent)

## 1. Goal & Scope
- **Objective**: allow the single-agent (`SingleAgentController`) and multi-agent (`MultiAgentFlow`) modes to interpret revision instructions themselves, selecting the minimal tool reruns instead of relying on the hard-coded revision helpers in `analytics_memory_workflow` / `chart_revision.py`.
- **Out of Scope**: planner-executor flow, legacy revision shortcuts, UI overhaul beyond prompt nudges already updated.

---

## 2. Current State Recap
1. **Revision shortcut**: `analytics_memory_workflow()` checks `is_chart_revision_query` / `is_analysis_revision_query` and directly invokes `flow_instance.chart_revision()` or `analysis_revision()` before the main streaming. (See `backend/analytics/flows/workflow.py` lines ~90-180.)
2. **Single-agent**: `SingleAgentController.analysis_revision()` simply invokes the planner pipeline with cached artifacts and emits `analysis_revision` events. The controller itself does not reason about which lanes to touch. (`backend/analytics/flows/single_agent_tools.py` lines ~1060-1080.)
3. **Multi-agent**: `_build_revision_plan` decides to reuse or rerun lanes; supervisor planners schedule `analysis` run + `chart` reuse when `analysis_revision_text` is present. (`backend/analytics/flows/multi_agent.py` around lines 288-330.)
4. **Session snapshot**: `SessionStateSnapshot` stores last analysis/chart/sql so revision shortcuts can reuse them, but agents are not handed the revision intent explicitly.
5. **frontend**: revision prompts (chips) now say “Rewrite the analysis to highlight …”, but the backend still bypasses the agent.

---

## 3. Implementation Plan (Step-by-Step)

### Phase A – Infrastructure Prep
1. **Persist raw revision directives**  
   - Extend `SessionStateSnapshot.record_query()` or add a new helper to retain the most recent “revision instruction” alongside timestamp and follow-up metadata (e.g., `last_revision_request`).  
   - Update `analytics_memory_workflow()` to record the directive before any flow branching (only when a session_id exists).  
   - Ensure `get_session_state_repository()` persists this key for Redis and in-memory fallback.  

2. **Expose revision context to flows**  
   - Add a lightweight dataclass (e.g., `RevisionDirective`) with fields: `raw_text`, `parsed_targets`, `requested_focus`.  
   - Pass this directive through `run_flow()` → `flow.events()` via new kwarg `revision_directive`. For flows that do not care, default to `None`.  
   - Update `PlannerPhaseContext` (in `planner_executor._initialize_context`) to stash the directive, so both single-agent and multi-agent can access it without re-parsing.  

3. **Telemetry flagging**  
   - Add a simple enum or boolean on the directive indicating whether we are in *agentic* revision mode, for metrics and rollback toggles (e.g., env var `AGENTIC_REVISIONS_ENABLED`).  

### Phase B – analytics_memory_workflow adjustments
1. **Skip hard-coded revision branches for targeted flows**  
   - Modify the shortcut checks so they only run when the chosen flow is **not** single-agent or multi-agent (still keep them for planner-executor).  
   - Instead of returning early, attach `revision_directive` to the flow instance and set a status event like “Revision requested (agentic)”.  
   - Emit the same `revision_request` event currently produced by the planner so the UI badges remain consistent, but mark `source: "agentic_revision"`.  

2. **Directive parsing**  
   - Reuse the enhanced `infer_analysis_revision_from_query()` and `infer_chart_patch_from_query()` to populate directive metadata (`requested_focus`, `chart_ops`).  
   - Derive tentative lane hints (analysis/chart/web) for the agent but do not enforce them; they become soft guidance.  

### Phase C – Single-Agent Flow updates
1. **Planner hook**  
   - Extend `_initialize_context` in `single_agent_tools.py` to read `ctx.revision_directive`.  
   - Update the system prompt (likely in `core/config_store` or inline prompt template) so the agent sees: previous analysis excerpt, directive text, and cached artifact availability (from `ctx.revision_snapshot`).  

2. **Decision loop**  
   - Within `_ agentic_event_stream`, before `planner.events`, inject a synthetic “revision deliberation” step:  
     - Provide the directive and cached artifacts to the agent via a `planner` tool call (or a new `revision_planner` tool) that returns which lanes to rerun (`analysis`, `chart`, `market`, etc.).  
     - Cache decision inside `ctx` (e.g., `ctx.agent_revision_plan`).  
   - Update lane summary / telemetry to respect the agent decision: set `ctx.reuse_sql`, `ctx.reused_chart`, etc., based on the agent’s response instead of the deterministic `build_revision_plan`.  

3. **Fallbacks & guardrails**  
   - If the agent responds with an empty plan or errors, fall back to the current deterministic logic (`build_revision_plan`). Log a warning event with `status: "fallback_plan"` for observability.  
   - Enforce a timeout/short circuit to prevent prolonged deliberation.  

### Phase D – Multi-Agent Flow updates
1. **Shared context injection**  
   - In `_prepare_context` or `prime_with_snapshot`, inject the directive into `_shared_context['revision_directive']`. Ensure worker agents (analysis, chart) can see it.  

2. **Supervisor planning**  
   - Modify `_MultiAgentHooks.on_flow_start` or the supervisor agent’s system prompt so the planning phase decides which agents to activate for a revision.  
   - Replace the hard-coded `plan.add_step("analyst", "run", reason="analysis_revision")` logic with reading `revision_directive`. If the agent decides chart reuse is sufficient, skip scheduling chart generation.  
   - Update `AgentTaskPlan` serialization so telemetry records the agent’s rationale.  

3. **Agent prompts**  
   - Enhance the analyst and chart agent prompts to mention when they are acting under a revision directive, referencing `revision_directive.raw_text` and cached artifacts.  

4. **Safety net**  
   - As with single-agent, keep deterministic fallback: if the supervisor emits no plan, call existing `_planner.set_revision_targets`.  

### Phase E – Frontend touchpoints
1. **Status messaging**: surface “Agent-managed revision” vs “Manual revision shortcut” using `revision_directive.mode` in `useAnalyticsMemoryStream`.  
2. **Process panel**: show the agent’s chosen lanes (from `revision_request` event) to confirm why certain cards reran.  
3. **Optional**: add tooltip on revision chips hinting that natural language instructions (“focus on customer retention”) are now accepted.  

### Phase F – Testing & Verification
1. **Unit tests**  
   - Add tests under `backend/tests/analytics` to confirm `analytics_memory_workflow` passes directives correctly and skips shortcuts for targeted flows.  
   - Mock agent responses in single-agent tests to assert lane reuse vs rerun (e.g., ensure SQL isn’t executed when agent selects analysis-only).  
   - Multi-agent tests to ensure supervisor plan honors agent directive.  

2. **Integration / smoke tests**  
   - Record Playwright or Vitest scenario for revised prompts -> verify `revision_mode` updates to `analysis`.  
   - Backend integration test streaming events to confirm `revision_request` shows `source: agentic_revision`.  

3. **Telemetry dashboards**  
   - Add metrics counters (e.g., `revision.agentic.requests`, `revision.agentic.fallbacks`) for monitoring during rollout.  

### Phase G – Rollout Strategy
1. **Feature flag**: gate the agentic revision behavior behind `AGENTIC_REVISIONS_ENABLED` and per-flow toggles (`AGENTIC_REVISION_SINGLE_AGENT`, `AGENTIC_REVISION_MULTI_AGENT`).  
2. **Shadow mode**: initially compute both the agent decision and deterministic plan, but execute only the deterministic path while logging differences. Switch to agentic execution after validation.  
3. **Gradual exposure**: enable for internal tenants first, monitor telemetry, then expand.  

---

## 4. Dependencies & Open Questions
- **Prompt storage**: confirm where single-agent / supervisor prompts live (`core/config_store` vs inline). Plan assumes they are editable without rebuild.  
- **Session TTL**: revisions rely on cached artifacts; ensure TTL (default 30 min) is sufficient for anticipated revision timelines.  
- **LLM determinism**: evaluate whether current models support the added reasoning reliably; might need temperature clamps or rubric scoring.  
- **Tool schema**: consider adding an explicit `revision_decision` tool schema so the agent returns structured JSON (lanes, reasons).  

---

## 5. Deliverables Checklist
- [ ] Data model & directive passing (`RevisionDirective` class, session persistence).  
- [ ] `analytics_memory_workflow` flow-mode gating and directive emission.  
- [ ] Single-agent agentic revision (prompts, planning, fallbacks).  
- [ ] Multi-agent agentic revision (supervisor planning, agent prompts).  
- [ ] Telemetry + feature flags.  
- [ ] Frontend UX updates for status/tooltip.  
- [ ] Automated tests & docs updates (`ARCHITECTURE.md` revision section).  
- [ ] Rollout plan executed with monitoring.  

---

## 6. Timeline (Rough)
| Week | Focus | Key Outputs |
|------|-------|-------------|
| 1 | Phase A + B | Directive pipeline, feature flag scaffolding |
| 2 | Phase C | Single-agent agentic revision, unit tests |
| 3 | Phase D | Multi-agent agentic revision, supervisor prompt tuning |
| 4 | Phase E–F | Frontend polish, integration tests, telemetry dashboards |
| 5 | Phase G | Shadow mode, rollout, documentation refresh |

---

**Next Action**: confirm product priorities for telemetry & feature flags, then start Phase A with a short RFC validating the directive schema.  

---

## Progress Update — 2025-10-26

What changed today:
- Planner‑executor now respects revision directive targets:
  - Implemented in `backend/analytics/flows/planner_executor.py:set_revision_directive()`. When a directive includes targets (e.g., `{analysis, web}` or `{chart}`), we seed `revision_targets` and set `revision_hint_active=True`, so the revision plan skips unrelated lanes. This avoids unintended fresh SQL executions on chart‑only or analysis‑only revisions.
  - In `backend/analytics/flows/workflow.py`, merged classifier‑detected targets with directive targets before calling `set_revision_targets()` to preserve explicit user intent.
- Analysis revision no longer short‑circuits the pipeline:
  - We still emit an `analysis_revision` event for audit, but we do not return early. The pipeline continues so web retrievers fan out and analysis is regenerated with fresh context.
- Removed redundant “Pending lanes…” cards in single‑agent and multi‑agent fallback payloads.

Why this was needed:
- Backend logs showed revision requests triggering full fresh runs (SQL + chart) even when the user asked for analysis- or chart‑only revisions. Root cause was planner‑executor ignoring `revision_directive.targets` and defaulting to the full pipeline in `derive_revision_targets()`.

Verification plan:
- Issue a chart‑only revision (e.g., “Change the chart to stacked bar”) and confirm backend logs do not show `Starting SQL pipeline`.
- Issue an analysis‑only revision (e.g., “Rewrite the analysis to emphasize AMD capex drivers”) and confirm: web fan‑out runs, SQL/Chart lanes are skipped, analysis regenerates.

Next hardening steps:
- Add unit tests asserting lane booleans for chart‑only and analysis‑only cases.
- Emit a `revision_plan` telemetry snapshot (targets + lane booleans) for quick log validation.
- Keep behind `AGENTIC_REVISIONS_ENABLED` family while monitoring.

---

## Revision Triggers and Flow (Updated 2025-10-26)

### Trigger Conditions
- Chart revision
  - Condition: the user query contains the word “chart” and a change verb (e.g., revise, update, change, convert, switch, make).
  - Heuristics: chart-type phrases like “stacked bar”, “line chart”, “area chart” are recognized for patch planning.
  - Implementation: `is_chart_revision_query(query)`, with optional ops from `infer_chart_patch_from_query(query)`.

- Analysis revision
  - Condition: the query mentions “analysis”/“summary”/“insight(s)” and includes a revise/refresh verb (rewrite, revise, update, refresh, etc.).
  - Focus extraction: `infer_analysis_revision_from_query(query)` parses snippets like “rewrite the analysis to …”, “analysis focus: …”.
  - Implementation: `is_analysis_revision_query(query)` + focus inference.

- Precedence and session
  - Precedence: if both could apply, chart revision takes priority for that turn; analysis revision is only considered if chart revision is not requested.
  - Session requirement: revision routing requires an active `session_id` with a prior snapshot; otherwise the system treats it as a fresh run to rebuild artifacts.

### Execution Flow by Revision Type
- Analysis revision (targets = {analysis, web})
  - Apply analysis revision event for audit/history (no early return).
  - Accessories prefetch: web retrievers run (concurrent, topic‑planned when a Search API key is configured) to refresh context.
  - Analysis generation runs using refreshed web context; SQL and chart lanes are skipped/reused when prior artifacts exist.
  - Typical events: `analysis_revision` → `tool_fanout/web_ready` → `analysis_generation` → `analysis_complete`.

- Chart revision (targets = {chart})
  - Skip SQL and analysis; run the chart lane to update the visualization using the existing dataset.
  - Optional: when a patch can be inferred, apply chart ops (e.g., change chart type) to the last saved spec; if no snapshot exists, a full rebuild may be needed.
  - Typical events: `revision_request` → `chart_generation` → `chart_ready`.

### Examples
- Chart: “Switch the chart to stacked bar”, “Convert the chart to a line chart”.
- Analysis: “Rewrite the analysis to emphasize AMD capex drivers”, “Analysis focus: customer retention signals.”

### Notes
- Agentic flags: per‑flow flags (`AGENTIC_REVISIONS_ENABLED`, `AGENTIC_REVISION_*`) can gate agent‑managed routing; current implementation continues through the pipeline after emitting the revision event so web fan‑out and analysis can run without unnecessary SQL.
