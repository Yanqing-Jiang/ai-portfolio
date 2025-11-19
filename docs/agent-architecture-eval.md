<!-- Analytics agent evaluation authored November 19, 2025 -->

# Analytics Agent Architecture Evaluation

## Purpose & Lens
- **Objective:** Replace the split between deterministic fresh runs and agentic revisions by running every analytics flow (fresh + revision, single + supervisor) directly on the OpenAI Agent SDK. This aligns session memory, telemetry, and UI evidence while retiring bespoke planners.
- **Vision tie-in:** `backend/analytics/ARCHITECTURE.md`, `docs/agentic-roadmap.md`, `docs/agent-process-ledger-investigation.md`, and `docs/revision-card-handoff.md` already describe the desired “agent everywhere” behavior. This doc translates that vision into a concrete refactor plan grounded in today’s code.
- **Scope:** Analytics backend flows, shared telemetry/SSE contracts, and the analytics UI surfaces (ProcessPanel, LiveArtifacts, topic cards). Other demos remain untouched unless they reuse analytics plumbing.

## Current Architecture Snapshot
- **Deterministic planner vs agent controllers:** Fresh runs still call `flows/planner_executor.PlannerExecutorFlow.events()`, which enforces SQL → chart → accessory → analysis lanes. Revisions switch to `SingleAgentController`/`MultiAgentFlow`, which wrap `agent_orchestrator.AgentRuntime` and already consume OpenAI Agent SDK streams via `flows/agents_stream_bridge.AgentsStreamBridge`.
- **Shared artifacts + routing:** `SessionStateSnapshot`, `ToolInvocationReceipt`, `FollowUpClassifier`, and revision snapshots enforce cache reuse, TTLs, and follow-up routing, but today they sit outside the agent loop for fresh runs.
- **Frontend expectations:** `components/analytics/hooks/useAnalyticsMemoryStream.ts`, `ProcessPanel`, and `LiveArtifacts` now rely on revision-only telemetry (e.g., `agent_coordination`, `web_topics_pending/ready`). Fresh runs can’t emit those events because they never enter the agent runtime, which is why demos still show mismatched badges.
### Mode Boundaries
- **Direct workflow (FlowMode.DIRECT):** Must keep the deterministic pipeline for predictable “instant answer” demos described in `backend/analytics/ARCHITECTURE.md` §1. Fresh SQL/chart/web execution still flows through `PlannerExecutorFlow` here; the refactor intentionally leaves this mode untouched so direct workflows remain cache-independent and latency-optimized.
- **Single-agent workflow:** Currently agentic only for revisions. Goal is to route both fresh + revision requests through the Agent SDK so telemetry, guardrails, and receipts stay aligned.
- **Supervisor workflow:** `MultiAgentFlow` already emits SSE-compatible telemetry for revisions; the refactor extends that parity to fresh runs while preserving the deterministic direct mode.
- 

## OpenAI Agent SDK Primitives That Unlock the Refactor
- **Runner + run hooks:** `Runner.run` / `run_streamed` emit `run_step` deltas for reasoning, tool calls, and outputs. Hooking these into `AgentsStreamBridge` gives a single telemetry feed for every flow. citeturn0search8
- **Sessions:** SDK sessions persist context and artifacts between invocations, so a fresh agent run can seed the exact state revisions already load from `SessionStateSnapshot`. citeturn0search0
- **Guardrails:** Input/output guardrails attach to each agent, letting us move `FollowUpClassifier`, latency guards, and “stock-only” gates inside the SDK rather than as separate Python helpers. citeturn0search1turn0search3
- **Multi-agent orchestration:** SDK guides describe manager-as-tool vs handoff patterns; both match existing `SupervisorSpecialistConfig`. We can keep a manager (planner) agent that calls specialists as tools, or let the supervisor hand off control entirely, depending on the UI evidence we want. citeturn0search6turn0search4turn0search5

## Refactor Plan: Unify Fresh + Revision on Agents SDK
This plan intentionally targets only the Single-Agent and Supervisor modes; FlowMode.DIRECT keeps the deterministic pipeline for “instant answers.” Each step reuses existing modules to avoid a ground-up rewrite.
1. **Wrap existing lane adapters as reusable tools.**
   - Extract thin tool wrappers around `flows/planner/sql_lane.stream_sql_lane`, `chart_lane`, `analysis_lane`, `fanout`, and accessory adapters. Each wrapper simply orchestrates the current async generator, captures its receipts via `_persist_session_state`, and returns the payload already streamed to SSE. No business logic changes—just repackaging for the Agent SDK.
   - Benefit: the same tool list powers both controllers, so there is no duplicate implementation when we retire deterministic fresh runs outside FlowMode.DIRECT.
2. **Define dual instruction sets for the same agent runtime.**
   - `FreshRunPlannerAgent`: instruct to always run SQL → chart → accessories → analysis regardless of cached artifacts, mirroring today’s deterministic contract.
   - `RevisionPlannerAgent`: instruct to hydrate `SessionStateSnapshot`, evaluate `revision_targets`, and call only the necessary tools. Both instruction sets live next to the existing `AgentRuntimeConfig` so the change is localized.
   - Guardrails: convert `FollowUpClassifier` outputs into SDK guardrail verdicts (e.g., short-circuit to stock-only) so the Python classifier can be deleted later without changing tool signatures. citeturn0search1turn0search3
3. **Controller shim, not replacement.**
   - Keep `PlannerExecutorFlow.events()` for FlowMode.DIRECT. For other modes, replace the current deterministic fresh path with a shim that configures `agent_orchestrator.AgentRuntime` using the “fresh” instruction set and the existing `PlannerToolRegistry`.
   - Result: Single-Agent and Supervisor controllers share the same runner; the only branching is whether the supervisor also spawns specialists (see next section).
4. **Telemetry + evaluation alignment.**
   - Subscribe to Agent SDK `run_step` events for both fresh and revision runs, translating them to SSE via `AgentsStreamBridge`. This instantly fixes the ProcessPanel/LiveArtifacts parity issues documented in `docs/revision-card-handoff.md`.
   - Update the five-stage eval pipeline (ledger replay, telemetry gates, UI capture, metrics) so it expects identical evidence from fresh and revision sessions, simplifying Ops sign-off.
5. **Incrementally migrate tests.**
   - Mirror a representative deterministic fresh test (e.g., `test_sql_lane_emits_receipts`) to an Agent SDK run, then deprecate deterministic coverage only after the agent path is stable. This avoids a risky “big bang” drop of planner tests.

## Multi-Agent Orchestration Options (Supervisor vs Planner Agent)
| Pattern | Repo alignment | Frontend evidence & effort | Trade-offs |
| --- | --- | --- | --- |
| **Supervisor + specialists as tools** | Mirrors today’s `MultiAgentFlow` and `SupervisorSpecialistConfig`: supervisor stays in `agent_orchestrator.AgentRuntime`, invokes SQL/Chart/Web/Analysis specialists as tools, and streams results through `AgentsStreamBridge`. Minimal backend churn beyond registering each specialist as an Agent SDK tool. citeturn0search6turn0search4 | ProcessPanel already shows a single timeline; simply label card headers with the specialist name (from `tool_call_id` metadata). LiveArtifacts can add “Produced by Chart Specialist” badges without layout changes. | Guardrails remain centralized, retries stay under supervisor control. Specialists can share cache state because the supervisor never relinquishes control. |
| **Supervisor handoff** | Uses SDK handoffs so the supervisor yields control to a specialist until it finishes. Requires `AgentsStreamBridge` to display nested `run_step` spans and `SessionStateSnapshot` to record which agent owned each artifact. citeturn0search6turn0search5 | Needs stacked or expandable ProcessPanel entries to visualize handoff start/end, plus LiveArtifacts footers showing which agent actually produced the artifact. | Provides higher perceived autonomy but increases frontend + telemetry complexity; retries become harder to attribute. |
| **Planner agent coordinating supervisors** | Introduce a lightweight planner agent (aligned with the roadmap’s “planner-as-agent” vision) that decides lane order and passes directives to either the single-agent or supervisor. Planner can be optional (only for multi-topic prompts). | UI can highlight “Planner chose SQL → Web → Analysis,” reusing the existing plan snapshots logged in `docs/agentic-roadmap.md`. | Adds another agent to monitor; best used once the supervisor-as-tool path is stable so we can prove the incremental value (dynamic ordering, topic-driven tool selection). |

**Recommendation grounded in the current codebase:** Start with the supervisor + specialists-as-tools pattern. It keeps `MultiAgentFlow` close to its existing behavior, minimizes frontend churn, and still lets you showcase specialist attribution (the roadmap already calls for highlighting SQL/chart/web badges). After that’s reliable, consider layering in a planner agent specifically for complex prompts so you can demonstrate “true” multi-agent planning without destabilizing the core flow. citeturn0search6turn0search4turn0search5

## Frontend Considerations
- Extend `useAnalyticsMemoryStream.ts` to treat all `run_step` payloads uniformly. Specialists should tag their outputs with lane + specialist name so ProcessPanel cards can show “Chart Specialist” vs “Analysis Specialist.”
- LiveArtifacts already hydrates SQL/chart/web cards; add optional badges or color-coding to indicate which specialist produced them. Use the emitted `tool_call_id` as the key so ledger screenshots remain auditable (per `docs/agent-process-ledger-investigation.md` requirements).
- Ensure revision cards continue to buffer until `web_topics_ready` or `analysis_revision_ready` arrives; fresh runs should now emit those fields as well, eliminating the current muted-state hacks.

## Updated Evaluation Plan (Fresh vs Revision)
1. **Stage 0 – Roadmap checklist:** Fresh and revision runs must both satisfy the `docs/agentic-roadmap.md` “Done Criteria” (agent loop, context hydration, telemetry parity, accessory guarantees, multi-agent story, docs/tests).
2. **Stage 1 – Ledger parity:** Replay ledgers for fresh + revision and confirm identical evidence structure (`flow_mode`, `run_step.type`, `guardrail_result`, `specialist_id`). No deterministic-only events should remain.
3. **Stage 2 – Telemetry evidence gates:** Enforce the `docs/revision-card-handoff.md` expectations for `agent_coordination`, `web_topics_pending/ready`, and (new) specialist attribution. Runs fail if any pending event lacks a matching ready event.
4. **Stage 3 – UI capture:** Collect screenshots showing the same badges for fresh and revision flows; store ledger hashes + timestamps alongside them as required in `docs/agent-process-ledger-investigation.md`.
5. **Stage 4 – Metrics:** Compare latency, retries, guardrail trip rates, and cache reuse for (a) legacy deterministic (baseline), (b) Agent SDK single-agent fresh, (c) Agent SDK supervisor fresh. Publish the table within this doc for demo prep.

## Recommendations Summary
1. **Decommission deterministic planner during fresh runs;** route every request through the Agent SDK with lane tools that reuse existing Python modules.
2. **Unify controllers and caching;** a single `AgentRuntime` path chooses between “fresh” and “revision” instructions but otherwise shares tool registration, guardrails, and telemetry.
3. **Adopt manager + specialist-as-tool multi-agent pattern first;** it best fits current supervisor code and keeps UI work contained while still showcasing specialist outputs.
4. **Enhance frontend telemetry consumption;** rely exclusively on Agent SDK `run_step` data so badges, charts, and cards show specialist attribution for both fresh and revision contexts.
5. **Refresh eval & ops playbooks;** update the ledger replay scripts and manual badge capture steps to assume Agent SDK evidence, ensuring Ops/support no longer juggle multiple telemetry formats.

## Status Snapshot (Task-Oriented)
- **Completed:** Revision flows already run on the Agent SDK; telemetry + docs describe desired behaviors; SDK research summarized here.
- **Outstanding:** Tool extraction, `FreshRunPlannerAgent` instructions, guardrail migration, supervisor agent refactor, UI telemetry updates, and eval harness consolidation (owners TBD).

## References
1. OpenAI Docs, “Agents API: Sessions,” November 2025. citeturn0search0
2. OpenAI Docs, “Agent guardrails overview,” November 2025. citeturn0search1
3. OpenAI Docs, “Guardrails: input/output policies,” November 2025. citeturn0search3
4. OpenAI Docs, “Running agents with `run_streamed`,” November 2025. citeturn0search8
5. OpenAI Cookbook, “Collaborative agents (manager + specialists),” November 2025. citeturn0search6
6. OpenAI Cookbook, “Parallel agent orchestration & handoffs,” November 2025. citeturn0search5
7. OpenAI Cookbook, “Agents API from scratch (tool orchestration patterns),” November 2025. citeturn0search4
