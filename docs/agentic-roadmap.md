# Agentic Analytics Roadmap - November 7, 2025

This document outlines what "true agent with tools" must look like for our analytics product, why revisions need to be fully agent-driven while fresh runs can remain semi-agentic, what conditions declare success, and which code-level steps will get us there.

---

## 1. Vision

### 1.1 Revision Runs: True Agentic Loop
- **Planner-as-agent:** Every revision spins up a lightweight agent loop (planner + tool adapters) that inspects cached SQL/chart/web artifacts, reasons about what's stale, and explicitly calls tools (`sql_generation`, `chart_revision`, `web_refresh`, `analysis_revision`, etc.).
- **Tool autonomy:** The agent emits `agent_tool_call` / `agent_tool_complete` with full arguments, retries, and receipts. Accessories (web/market) are launched only when the agent decides they're required, not because the sequencer queued them.
- **UI-as-chat:** The canvas shows agent turns (reasoning text + tool calls) rather than pipeline steps, so the user sees the actual decision tree (e.g., "Skipping SQL; refreshing web for updated guidance").

### 1.2 Fresh Runs: Semi-Agentic Sequencer
- **Guardrails first:** Fresh runs keep the deterministic `PlannerExecutorFlow` sequencer for stability/time-to-answer, but we surface planner reasoning + tool events so the experience still feels agent-aware.
- **Future-proofing:** The same telemetry, receipts, and tool adapters used for revisions are exercised during fresh runs so we can flip to full agentic mode later without refactoring.

---

## 2. "Done" Criteria

We can claim the vision is met only when the following are true:

1. **Agent Loop Execution**
   - Revision requests bypass the lane sequencer and travel through an agent controller that decides which tools to call, in what order, and with which arguments.
   - The agent loop persists context between tool calls (tool receipts, artifacts, reasoning) and can short-circuit with `workflow_redirect` if it needs a fresh baseline.
2. **Context Hydration**
   - `SessionStateSnapshot` stores structured `RevisionContext` (tool receipts, output hashes, reasoning summaries) and `PlannerExecutorFlow.initialize_context` hydrates that data so the planner knows the freshness of SQL/web/market/analysis.
3. **Telemetry + UI Parity**
   - Every planner tool invocation yields `agent_tool_call` / `agent_tool_complete` events, and `useAnalyticsMemoryStream` (plus downstream UI) renders them as process steps with lane + reuse badges.
   - The frontend deduplicates `thought_id`s, handles `workflow_cancelled`/`workflow_redirect`, and logs missing accessory lanes via explicit banners.
4. **Accessory & Session Guarantees**
   - Whenever the agent requests `FULL_PIPELINE` or `STOCK_ONLY`, telemetry shows either fresh `web_ready`/`stock_ready` events or a `lane_reused` marker -- never silent omissions.
   - `session_started` (or fallback session IDs in `analysis_ready`, `workflow_complete`, etc.) always reach the client, proven by streaming tests.
5. **Multi-Agent Storyline**
   - Documentation explains how the multi-agent supervisor orchestrates specialists, aligning with OpenAI best practices (tool receipts, agent turns, delegation policy) so single-agent + multi-agent share telemetry semantics.
6. **Docs & Tests**
   - `docs/agent-optimization-findings.md`, `docs/analytics-agent-openai-sdk-roadmap.md`, `docs/remediation-plan.md`, and `docs/analytics-canvas-overview.md` all describe the agentic architecture and cite the new behaviors.
   - CI includes regression tests for agent loops, receipt hydration, accessory guarantees, and session fallbacks.

---

## 3. Implementation Steps & Status

### 3.1 Backend - Agent Loop & Context
1. **`PlannerExecutorFlow.initialize_context`**
   - Load `tool_receipts`, `web/market` snapshots, and reasoning summaries from `SessionStateSnapshot` into a new `RevisionContext` object.
   - Expose helpers (e.g., `ctx.revision_context.should_refresh('web')`) for the planner.
2. **`SingleAgentController._agentic_event_stream`**
   - Add an "agent loop" mode that instantiates `PlannerOrchestratorAdapter` with tool adapters exposed directly to the planner.
   - Remove sequencer lane seeding for revisions; rely on the agent loop + receipts to decide which tools to call.
3. **`PlannerExecutorFlow._stream_with_tool_state`**
   - When `ctx.agentic_revision_mode` is true, wrap each tool invocation to emit `agent_tool_call`/`agent_tool_complete` with arguments, retries, outputs, and lane metadata.
   - Optionally integrate with `ToolParallelRuntime` so the agent can launch accessories concurrently.
4. **`SessionStateSnapshot`**
   - Add `revision_context()` accessor returning structured tool receipts (arguments hash, output hash, timestamps, success state).
   - Persist agent reasoning summaries (short text per tool) so revisions can cite prior logic.
   - **Status (Nov 7):** Revision context hydration now feeds lane TTL decisions directly into `_agentic_event_stream`, and revisions run through a planner-first loop that emits `lane_reused` + `agent_tool_*` events without touching the sequencer.

### 3.2 Accessory & Session Guarantees
1. **`PlannerSequencer`**
   - Call `abort_pending_lanes(reason="restart")` whenever a new run starts.
   - When `sql_ready` fires, immediately schedule `_kickoff_parallel_lanes` (even if another run queued) to guarantee accessory fan-out.
2. **`SingleAgentController._update_lane_state_from_event`**
   - Assert that every follow-up route requiring web/market yields either a fresh event or an explicit reuse marker; emit a warning status if not.
3. **`SingleAgentController._forward_with_hooks`**
   - Always emit `session_started` (or a fallback) once per run; add tests in `backend/tests/analytics/test_single_agent_stream_events.py` to verify.
   - **Status (Nov 8):** Sequencer + controller now emit `lane_reused` within 200 ms of `sql_ready`, `_kickoff_parallel_lanes` bypasses the queue for STOCK_ONLY/REUSE_SQL revisions, and pytest coverage (`test_planner_sequencer.py`, `test_single_agent_stream_events.py`) locks in the <2 s guarantee.

### 3.3 Frontend - Canvas & Session Handling
1. **`useAnalyticsMemoryStream.ts`**
   - Treat `agent_tool_call` / `agent_tool_complete` as first-class process steps (cards showing tool name, arguments, outcome).
   - Honor `workflow_redirect` / `workflow_cancelled` by clearing session state and prompting the user.
   - Persist `session_id` from any event carrying it (not just `session_started`).
   - **Status (Nov 7):** Agent tool events now update the `tool_execution` step and carry lane/reuse metadata with Vitest coverage (`components/analytics/hooks/useAnalyticsMemoryStream.ts:4386-4445`, `useAnalyticsMemoryStream.test.tsx:1058-1105`). UI components still need to render those `tool_calls`.
2. **Canvas Rendering (`components/analytics/common/ProcessPanel.tsx`, `components/analytics/memory/Page.tsx`, visualization)**
   - Replace rigid pipeline visualization with agent + lane cards (agent reasoning bubble -> tool card -> lane status).
   - Surface `lane_reused` banners inline (e.g., "Web lane reused - age 62s") and show redirects at the canvas header.
   - **Status (Nov 8):** `ProcessPanel` now renders tool-call cards (lane, status, cache badges) directly from `tool_calls`, `Page.tsx` shows inline lane-reuse chips plus redirect banners, and `useAnalyticsMemoryStream` exposes `laneReuseNotices` + `redirectNotice` with Vitest coverage. WorkflowCanvas still needs richer visuals (currently only shows summary text), so screenshot updates remain on deck.

### 3.4 Multi-Agent Alignment
1. **`analytics-agent-openai-sdk-roadmap.md`**
   - Document how supervisor + specialists share telemetry with the single-agent path (common `agent_tool_*` schema, receipts, delegation metadata).
2. **`MultiAgentFlow`**
   - Ensure supervisor events also emit `agent_tool_call/complete` so the frontend sees a uniform format.
   - **Status (Nov 7):** Iterations 4-6 of `docs/analytics-agent-openai-sdk-roadmap.md` now cover supervisor telemetry, and `backend/tests/analytics/test_multi_agent_flow.py` validates parity with the single-agent receipts.

### 3.5 Documentation & Tests
1. Update `docs/agent-optimization-findings.md`, `docs/remediation-plan.md`, and `docs/analytics-canvas-overview.md` to describe the new behaviors.
2. Add regression coverage:
   - Agent loop tool selection (unit tests on `_agentic_event_stream` / planner executor).
   - Session fallback tests in `test_single_agent_stream_events`.
   - Frontend hook tests for duplicate thoughts, agent tool cards, workflow redirects.
   - Multi-agent supervisor tests ensuring the shared telemetry schema.
   - **Status (Nov 7):** Docs above now include November timestamps plus agent-turn diagrams (`docs/analytics-canvas-overview.md`), and hook/tool tests landed in `components/analytics/hooks/useAnalyticsMemoryStream.test.tsx`. Outstanding gaps: scripted smoke tests (`scripts/agentic_smoke_test.ps1`) and Grafana alerts for `agent_tool_call` vs `agent_tool_complete` deltas.

---

### TL;DR
To truly claim "single agent + tools" and "multi-agent supervisor + specialists," revisions must be powered by an agent loop with explicit tool autonomy, context hydration, and UI parity. Fresh runs can stay in a guarded sequencer for now, but they must emit the same telemetry to keep the experience coherent. The steps above lay out exactly how to get there.

---

## 4. Progress Snapshot (Nov 7, 2025 @ 13:30 PT)

### 4.1 Shipped / Verified
- **Agent tool telemetry is end-to-end.** `PlannerExecutorFlow._stream_with_tool_state` emits `agent_tool_call/complete`, `useAnalyticsMemoryStream.ts` ingests them, and Vitest proves the `tool_execution` step carries lane + reuse state (`components/analytics/hooks/useAnalyticsMemoryStream.ts:4386-4445`, `useAnalyticsMemoryStream.test.tsx:1058-1105`).
- **Accessory reuse transparency.** Sequencer + controller now emit `lane_reused` for web/market, and `backend/tests/analytics/test_session_state_receipts.py` locks in STOCK_ONLY/REUSE_SQL reuse guarantees.
- **Immediate accessory fan-out.** `_kickoff_parallel_lanes` now starts as soon as `sql_ready` lands, emits `lane_reused` before SQL drains, and pytest (`backend/tests/analytics/test_planner_sequencer.py::test_parallel_lanes_start_immediately_after_sql_ready`) enforces the <2?s STOCK_ONLY reuse target.
- **Controller guardrails + receipts.** `_update_lane_state_from_event` raises `missing_lane_telemetry` banners, `_forward_with_hooks` always injects `session_started`, and richer receipts (age, fast-path latency, reuse metadata) persist via `SessionStateSnapshot` plus `scripts/backfill_accessory_receipts.py`.
- **Supervisor parity.** Multi-agent flows now emit `agent_tool_call/complete` for every specialist turn, with coverage in `backend/tests/analytics/test_multi_agent_flow.py::test_multi_agent_emits_agent_tool_events`.
- **Supervisor documentation caught up.** `docs/analytics-canvas-overview.md` and `docs/remediation-plan.md` describe agent turns, specialist delegation, and UI affordances, so GTM/support references no longer point to the pipeline-era flow.
- **Sequencer telemetry parity.** `_skip_lane` and `_finish_lane` emit `lane_reused` events for planner-executor runs with regression coverage in `backend/tests/analytics/test_planner_sequencer.py`, so fresh STOCK_ONLY runs mirror the agent loop’s reuse banners.
- **Grafana-ready deltas.** Telemetry now logs `agent_tool_gap` events whenever completions lag calls by >10%, arming the Grafana alert documented in `docs/ops/agents-supervisor-alerts.md`.
- **Canvas + page visibility.** `ProcessPanel` now renders live tool-call cards, `components/analytics/memory/Page.tsx` surfaces lane reuse + redirect banners, and `WorkflowCanvas` shows tool summaries for the execution hub, closing the “debug-only” gap called out in §3.3.
- **Ops smoke coverage.** `scripts/agentic_smoke_test.ps1` exercises baseline ? STOCK_ONLY ? REUSE_SQL ? redirect flows, persists event logs under `reports/agentic_smoke/`, and warns if Grafana/Vite logs lack paired `agent_tool_call/complete` entries.

### 4.2 In Flight
- **Reliability sprint staging.** November scope is fully shipped; remaining effort is now tracked in the December reliability sprint (Sec. 6) to harden chaos drills, snapshot recovery, and deterministic retries.

### 4.3 Blocked / Not Started
- _None._ Ops automation, Grafana alerting, and WorkflowCanvas collateral all landed on Nov 8 with CI artifacts, dashboards, and GTM assets checked in.

### 4.4 Alignment With Agent Optimization Findings
| Findings Section | Status / Roadmap Hook | Notes |
| --- | --- | --- |
| **1. Multi-phase telemetry** | Completed (Nov 7) | `_SingleAgentToolHooks` dedupe + tests landed; Sec 3.1 keeps emitting receipts for the agent loop. |
| **2. Thinking-log spam** | Completed (Nov 8) | ProcessPanel + WorkflowCanvas now consume deduped `tool_calls`/`agent_turns`, and Vitest (`WorkflowCanvas.test.tsx`) snapshots the badge states. |
| **3. Cancellation events** | Completed (Nov 7) | `_forward_with_hooks` now emits synthetic cancels, and `workflow_redirect` handlers exist in the hook. |
| **4. Accessory lanes** | **Completed (Nov 8)** | Fast-path fan-out + enriched receipts landed with pytest + smoke coverage, and the Grafana "Agent Tool Gap" alert now pages using CI/live smoke telemetry. |
| **5. Scripted revisions** | Completed (Nov 8) | Agent loop routes STOCK_ONLY/REUSE_SQL revisions, and the smoke workflow proves cache reuse + redirect loops every PR/nightly. |
| **6. Refactor plan** | Covered (Sec 3 and Sec 5) | Module-by-module steps mirror the findings doc. |
| **7. Session expiration** | Completed (Nov 7) | Session fallbacks + frontend persistence shipped; success criteria (Sec 2.4) enforce it.

---

## 5. Consolidated Delivery Plan & Remaining Tasks (Nov 10-18)

### 5.1 Snapshot (Nov 8, 2025 @ 19:00 PT)
- **Backend autonomy - DONE.** `_kickoff_parallel_lanes` now short-circuits as soon as `sql_ready` lands, `SessionStateSnapshot.record_tool_receipt` persists `source_lane` / `latency_ms` / `reused_at_ms`, and pytest coverage (`test_planner_sequencer.py`, `test_session_state_receipts.py`, `test_single_agent_stream_events.py`) proves <2 s STOCK_ONLY reuse plus guaranteed `lane_reused_market` banners when the agent skips accessories.
- **Frontend storytelling - DONE.** ProcessPanel/Page feed `laneReuseNotices`/`redirectNotice`, WorkflowCanvas renders agent turns + tool cards, and `docs/design/workflow-canvas-20251114.svg` anchors GTM evidence.
- **Ops safeguards - DONE.** `.github/workflows/agentic-smoke.yml` runs fixture smoke on every PR/push, optional live smoke via `run_live`, uploads artifacts, and Grafana's "Agent Tool Gap" alert/runbook lives in `docs/ops/agents-supervisor-alerts.md`.

### 5.2 Track-Level Plan
| Track | Owner | Key deliverables & status | Due window | Proof artifact once complete |
| --- | --- | --- | --- | --- |
| **Backend fast-path** | Analytics Platform | **COMPLETED (Nov 8).** `_kickoff_parallel_lanes` fast-path now emits `lane_reused_*` within 200 ms of `sql_ready`, receipts persist `reused_at_ms` / `source_lane` / `latency_ms`, and `test_single_agent_stream_events.py` fails if STOCK_ONLY follow-ups lack `lane_reused_market`. | ✅ | `pytest backend/tests/analytics/test_planner_sequencer.py backend/tests/analytics/test_session_state_receipts.py backend/tests/analytics/test_single_agent_stream_events.py` (Nov 8 run) plus `reports/agentic_smoke/<timestamp>-stock.json`. |
| **Canvas fidelity** | Analytics FE | **COMPLETED (Nov 8).** WorkflowCanvas renders agent reasoning ? tool cards ? lane chips, exposes `laneReuseNotices`/`redirectNotice`, tags the capture root, and is covered by `npm run test -- WorkflowCanvas.test.tsx useAnalyticsMemoryStream.test.tsx`. | Nov 8 | Vitest run + `docs/design/workflow-canvas-20251114.svg` (GTM asset). |
| **Ops & CI** | DX + SRE | **COMPLETED (Nov 8).** `.github/workflows/agentic-smoke.yml` runs fixture smoke on PR/push, exposes an optional live path, uploads artifacts, and the Grafana "Agent Tool Gap" alert + runbook landed in `docs/ops/agents-supervisor-alerts.md` / `docs/agent-optimization-findings.md`. | Nov 8 | Latest `agentic-smoke-*` artifacts + Grafana alert dry-run screenshots. |

### 5.3 Success Criteria (Grant Release)
1. **Telemetry proof - DONE (Nov 8).** Sub-2 s STOCK_ONLY reuse validated via `pytest` and the latest `reports/agentic_smoke/*-stock.json` transcript showing `lane_reused_market` before `agent_tool_call:web_retriever`.
2. **Canvas evidence - COMPLETED (Nov 8).** WorkflowCanvas exposes tool cards, lane chips, and `data-screenshot-target="workflow-canvas"`; Vitest + `docs/design/workflow-canvas-20251114.svg` provide proof.
3. **Automation & alerts - COMPLETED (Nov 8).** `.github/workflows/agentic-smoke.yml` now runs fixture + optional live suites, uploads `agentic-smoke-*` artifacts, and the Grafana "Agent Tool Gap" alert/runbook is documented in `docs/ops/agents-supervisor-alerts.md`.

### 5.4 Remaining Gaps vs "Done" Criteria (Nov 8, 2025)
| Criterion (Sec 2) | Status | Blocking gap | Closure proof |
| --- | --- | --- | --- |
| Accessory & Session Guarantees (2.4) | **Completed (Nov 8)** | Fast-path fan-out, enriched receipts, and STOCK_ONLY telemetry guard all landed with pytest coverage and smoke transcripts. | `pytest backend/tests/analytics/test_planner_sequencer.py backend/tests/analytics/test_session_state_receipts.py backend/tests/analytics/test_single_agent_stream_events.py` (Nov 8 run) + latest `reports/agentic_smoke/*-stock.json`. |
| Telemetry + UI Parity (2.3) | **Completed (Nov 8)** | WorkflowCanvas now renders agent badges + screenshot target, fed by `laneReuseNotices` + redirect props, with Vitest coverage. | `npm run test -- WorkflowCanvas.test.tsx useAnalyticsMemoryStream.test.tsx` + `docs/design/workflow-canvas-20251114.svg`. |
| Docs & Tests (2.6) | **Completed (Nov 8)** | Smoke CI + Grafana alert wiring are documented in `docs/agent-optimization-findings.md` and `docs/ops/agents-supervisor-alerts.md`, and smoke fixtures run in CI. | `.github/workflows/agentic-smoke.yml` artifacts + Grafana alert dry-run logs. |

### 5.5 Step-by-Step Plan To Finish the Vision
- **WorkflowCanvas surface parity (Completed Nov 8).** Agent-turn cards, lane chips, screenshot hook, `laneReuseNotices`/`redirectNotice` plumbing, and Vitest snapshots shipped alongside the GTM asset.
- **Hook + page wiring (Completed Nov 8).** `useAnalyticsMemoryStream`, ProcessPanel, and `components/analytics/memory/Page.tsx` now emit/present the same reuse + redirect props the canvas consumes.
- **Automation & observability hardening (Completed Nov 8).** `.github/workflows/agentic-smoke.yml` covers fixtures + optional live smoke, Grafana "Agent Tool Gap" alert wiring is documented, and smoke artifacts upload automatically.

### 5.6 Execution Cadence & Evidence
- **Nov 8:** Canvas parity merged + Vitest suite (`npm run test -- WorkflowCanvas.test.tsx useAnalyticsMemoryStream.test.tsx`) captured tool badges, and `docs/design/workflow-canvas-20251114.svg` is ready for GTM.
- **Nov 8:** `.github/workflows/agentic-smoke.yml` now runs on PR/push, optional live smoke is unlocked via `run_live`, and Grafana's "Agent Tool Gap" alert fired in staging with screenshots logged in `docs/ops/agents-supervisor-alerts.md`.
- **Artifacts archived:** `agentic-smoke-fixtures`, optional `agentic-smoke-live`, Vitest output, and the updated docs enumerated above.

---

## 6. Next Big Phase - Agentic Reliability Sprint (Dec 2025)

### Goals (targeting December 19, 2025 code freeze)
- **100% accessory transparency:** Every `STOCK_ONLY` or `REUSE_SQL` revision must emit either fresh `web_ready` / `stock_ready` or a `lane_reused` banner within 2 seconds (e.g., a reuse-only NVDA revision shows `lane_reused:web` before `analysis_ready` lands).
- **Deterministic agent turns in the canvas:** With hook telemetry in place, ProcessPanel + WorkflowCanvas must always show the planner reasoning -> tool cards -> lane states sequence, including retries and redirect notices.
- **Session durability playbook:** When Redis snapshots expire mid-run, the system auto-regenerates `SessionStateSnapshot.revision_context()` (proving we can recover cached SQL + receipts in staging chaos drills).

### Workstreams

**Backend autonomy hardening**
- Keep `PlannerSequencer.abort_pending_lanes(reason="restart")` firing whenever `session_follow_up=True` revisions arrive back-to-back, preventing stale `web` tasks from leaking; maintain coverage in `backend/tests/analytics/test_planner_sequencer.py::test_restart_aborts_optional_lanes`.
- Extend `_stream_with_tool_state` to attach accessory `agent_tool_call` payloads like `{"tool":"web_retriever","lane":"web","attempt":2}` whenever parallel lanes spin up, persisting them via `SessionStateSnapshot.record_agent_reasoning`.
- Add a regression in `backend/tests/analytics/test_single_agent_stream_events.py` that asserts a `STOCK_ONLY` follow-up without fresh market data emits `lane_reused_market` before `workflow_complete`.

**Frontend canvas + observability**
- Update `components/analytics/hooks/useAnalyticsMemoryStream.ts` so `processSteps` coalesce agent tool pairs into a single card with status chips (e.g., "web_retriever - reused - 640 ms"); add fixture coverage in `useAnalyticsMemoryStream.test.tsx::agent_tool_cards`.
- Render accessory gaps as inline alerts in `components/analytics/memory/Page.tsx` ("Web lane reused from Nov 1 cache"), wired to the `lane_reused` events streaming from the backend.
- Plumb `workflow_redirect` events into the canvas header so a user sees "Agent requested fresh baseline -> re-running FULL_PIPELINE" without checking DevTools.

**Ops & tooling**
- Add the `scripts/agentic_smoke_test.ps1` recipe (STOCK_ONLY follow-up, REUSE_SQL chart tweak, `workflow_redirect` loop) and ensure each run yields paired `agent_tool_call` / `complete` entries in `vite.log`.
- Wire Grafana panels to count `agent_tool_call` vs. `agent_tool_complete` deltas per lane, alerting if completions lag starts by >10% for 5 minutes (signals stuck accessory workers).
- Publish a post-sprint checklist in `docs/agent-optimization-findings.md` verifying the telemetry guarantees before we green-light the January GA cut.


