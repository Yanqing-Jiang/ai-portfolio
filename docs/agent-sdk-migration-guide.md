# Integrating the OpenAI Agent SDK into Next-Gen Analytics

This revision explains how to evolve the existing analytics flow into “true agents” across both runtime modes: a single agent that wields multiple tools, and a supervisor that orchestrates a bench of specialists. The guidance leans on the current `planner_executor` pipeline and surfaces the concrete engineering effort, informed by recent OpenAI and Anthropic agency best practices.citeturn0search0turn0search1turn0search3turn0search5

---

## 0. Difficulty snapshot

| Target architecture | FlowMode entry points | Difficulty | What changes |
|---------------------|-----------------------|-----------|--------------|
| Single agent, multi-tool (`FlowMode.SINGLE_AGENT`) | `backend/analytics/flows/planner_executor.py` → `PlannerExecutorFlow.events` | **Medium (1 sprint)** | Wrap the existing sequential phases in an `AgentRunner`, translate `SupervisorTools` into SDK tool definitions, and swap custom telemetry for SDK traces. |
| Supervisor + specialists (`FlowMode.MULTI_AGENT`) | `backend/analytics/flows/multi_agent.py` → `MultiAgentFlow._run_agent_orchestration` | **High (2–3 sprints)** | Replace bespoke orchestrator/manifest logic with Supervisor + delegate agents, shared scratchpad state, guardrails, and retry policies while preserving cached receipts. |

The direct mode can remain as a regression safety net while both agentic implementations stabilize.

---

## 1. How the planner_executor flow maps to Agent SDK constructs

### Single-agent lane (FlowMode.SINGLE_AGENT)
- `PlannerExecutorFlow.events` already emits a linear sequence of lane events: classification → intent/clarification → SQL → chart → analysis. Each phase calls deterministic helpers (SQL planner, validator, chart builder) through `SupervisorTools`, making them natural candidates for Agent SDK tool registrations (`analytics/tools/registry.py`). 
- The existing event envelope (`apply_mode_metadata`, `follow_up_route`, prompt versions) can migrate into the Agent SDK’s `trace` metadata and custom context payloads; use the emitted context to hydrate `AgentRunner.stream()` events instead of the bespoke `EventEmitter` pipeline.
- Slot resolution and clarification logic (`decide_schema_clarification`, `_auto_fill_missing_slots`) become specialized tool calls or guarded reasoning steps within a single agent prompt.

### Multi-agent lane (FlowMode.MULTI_AGENT)
- `MultiAgentFlow` presently wraps `PlannerExecutorFlow` but injects an orchestration layer that manages cached receipts, rerun directives, and lane hedging. The metadata map (`SUPERVISOR_AGENT_SYSTEM_PROMPTS`) illustrates the existing “role prompts” for planner, analyst, chart, market, and web specialists.
- `AgentExecutionOrchestrator` and `AgentTaskPlan` already encode task graphs; migratation consists of swapping the manually scheduled specialist invocations with Agent SDK handoffs while preserving cache-aware bookkeeping (`_drain_artifact_events`, `_maybe_agent_turn_start/_end`). 
- The hedged tool list (`HEDGED_WEB_TOOLS`) should translate into retry policies or redundant specialist delegates within the Agent SDK’s supervisor workflow.

---

## 2. Recommended single-agent multi-tool design (medium lift)

1. **Define a canonical runner** – Implement `backend/analytics/agents/runner.py` that builds an `AgentRunner` with the project guardrail profile (`GuardrailConfig`) and registers all analytics tools from a shared registry. Use the SDK context object to carry the planner metadata currently attached to events.citeturn0search2
2. **Register deterministic tools** – Port each `SupervisorTools` function into SDK-compliant tool adapters (`@tool` or `ToolSpec`) with precise input/output JSON schemas mirroring the current function signatures; deterministic behavior satisfies Claude’s agency guidance on reliable tool execution.citeturn0search5
3. **Prompt design** – Move the existing planner prompt scaffolding into a single-agent system prompt that enumerates the lane order and tool usage contract. Follow GPT‑5 handbook advice: label each instruction step, declare required outputs, and highlight when the agent must call a tool versus respond directly.citeturn0search6
4. **Clarification workflow** – Convert `decide_schema_clarification` into a structured sub-task: the agent first inspects slot completeness, then either emits a `clarification_request` tool call or writes a reasoned assumption. Guardrails enforce that red-team questions or missing slots trigger clarifications rather than silent assumptions.citeturn0search0
5. **Telemetry swap** – Replace the custom `EventEmitter` stream with `runner.stream()` traces. Forward `agent_turn`, `tool_call`, and `handoff` events to `useAnalyticsMemoryStream.ts`, mapping SDK event payloads onto existing UI states. Store trace IDs alongside the existing revision signatures for cross-run debugging.citeturn0search1
6. **Risk mitigation** – Keep `FlowMode.DIRECT` behind a feature flag (`ANALYTICS_AGENT_SDK_MODE`) and run shadow comparisons using captured inputs to detect regressions before flipping traffic.

Outcome: the single agent retains current UX semantics while gaining native guardrails, structured tool calling, and trace observability without rewriting downstream consumers.

---

## 3. Supervisor + specialists orchestration (high lift)

1. **Supervisor agent** – Translate `MultiAgentFlow._run_agent_orchestration` into an SDK supervisor agent whose system prompt mirrors `SUPERVISOR_AGENT_SYSTEM_PROMPTS["planner"]`. It should build a task list, attach cached receipt metadata, and decide which specialists to invoke.citeturn0search0
2. **Specialist lineup** – Instantiate SDK agents for `query`, `chart`, `market`, `web_research`, and `analyst` roles, reusing their existing prompt text but augmenting with explicit tool budgets and quality gates (e.g., SQL specialist must call `sql_validate` before `sql_execute`). Claude’s agency playbook stresses clearly bounded responsibilities, sandboxed tool usage, and zero-trust handling of tool outputs; adopt the same review checkpoints here.citeturn0search3turn0search5
3. **Shared scratchpad** – Use the Agent SDK shared state (or an injected memory tool) to store receipts, rerun directives, and follow-up routes. The supervisor hands annotated context to specialists and ingests their outputs before emitting a consolidated narrative.citeturn0search1
4. **Hedging & retries** – Encode `HEDGED_WEB_TOOLS` as redundant specialists or fallback tool invocations. Supervisor policies should specify retry budgets and escalation paths, matching OpenAI’s guidance on failure containment and deterministic replays for multi-agent systems.citeturn0search0turn0search7
5. **Termination contract** – Specialists respond with structured payloads (status, artifacts, cache keys). The supervisor collates these into the final `analysis_complete` event while updating revision state. Any missing artifacts trigger automated rerun requests, keeping parity with existing logic (`set_follow_up_route`, `_artifact_flush_pending`).

Expect to retire much of `AgentExecutionOrchestrator` once handoffs move into the SDK, but retain its caching utilities until the SDK-based exchange supports differential reruns.

---

## 4. Implementation roadmap tied to planner_executor

1. **Week 1: Tool registry parity**
   - Generate SDK tool adapters for SQL, chart, clarification, and market helpers; host them in `analytics/agents/tools.py`.
   - Build `AgentRunner` and prove single-agent parity by routing `FlowMode.SINGLE_AGENT` through it behind a feature flag.
2. **Week 2: Trace integration + clarifier**
   - Swap `PlannerExecutorFlow.events` to emit SDK trace events; adapt `useAnalyticsMemoryStream.ts` to the new schema.
   - Convert schema clarifier into an SDK-enforced structured response and delete bespoke guardrail switches.
3. **Week 3–4: Supervisor rollout**
   - Create specialist agent configs, wire supervisor orchestration, and feed receipts/hedges through shared state.
   - Shadow multi-agent runs, diffing artifacts (`PipelineArtifacts`) and telemetry to ensure cache reuse semantics survive.
4. **Week 5: Hardening**
   - Implement automated regression suites that replay saved sessions through both legacy and SDK pathways, comparing SQL, chart specs, and narratives.
   - Finalize config knobs (guardrail YAML, retry budgets, evaluation thresholds) before deprecating the legacy orchestrator.

---

## 5. Direct-mode safeguards

- Keep `FlowMode.DIRECT` routing exactly as it is today; do not instantiate the Agent SDK runner when `mode == FlowMode.DIRECT`, and leave `PlannerExecutorFlow`'s deterministic event emitter untouched (`apply_mode_metadata`, `EventEmitter`).
- Gate all Agent SDK code paths behind explicit flags (for example `ANALYTICS_AGENT_SDK_MODE` and `AGENT_SUPERVISOR_ENABLED`) so direct sessions never opt into the new runners accidentally, even if teams toggle the global rollout.
- Preserve the existing SSE contract for direct mode by continuing to stream events from `PlannerExecutorFlow.events` without trace remapping; smoke-test UI expectations using captured direct sessions before and after deployments.
- Maintain the legacy telemetry and latency guardrails (`_evaluate_latency_guardrail`) for direct sessions to avoid shifts in dashboards or alert thresholds while the agentic flows iterate.

---

## 5. Testing, evaluation, and observability

- **Regression harness** – Leverage the SDK’s evaluation hooks and OpenAI’s recommended regression runners to replay agent sessions and capture divergence scores automatically.citeturn0search7
- **Prompt audits** – Apply GPT‑5 prompt linting rules (explicit instructions, role separation, bounded memory) before launch; store prompts under revision control to track drift.citeturn0search6
- **Guardrail telemetry** – Pipe guardrail decisions and tool safety verdicts into the existing `analytics/core/telemetry.py` sinks so policy incidents share the same alerting dashboards.
- **Sandbox enforcement** – Maintain Claude-style sandboxing discipline: deterministic tools, sanitized inputs, and explicit review of tool output before acting, especially for SQL execution and web retrieval.citeturn0search5
- **Incident playbooks** – Document rollback steps that reinstate `FlowMode.DIRECT` paths if guardrail violations spike.

---

## 6. Risks & mitigations

| Risk | Mitigation |
|------|------------|
| Tool schema drift between legacy SupervisorTools and SDK adapters | Align JSON Schemas, add contract tests that call both implementations with golden fixtures. |
| Increased latency from guardrails and handoffs | Pre-warm agents at service startup and cache expensive tool responses; supervisors can reuse receipts or short-circuit lanes when cache is valid. |
| Specialist disagreement on cached receipts | Supervisor maintains the single source of truth for cache validity; failing specialists must emit retry directives instead of overwriting receipts. |
| Prompt sprawl across modes | Centralize prompts in `analytics/agents/prompts/` with shared macros so single-agent and supervisor share terminology and stop words.citeturn0search6 |

---

## 7. Recommended resources

- **OpenAI multi-agent orchestration guides** – Supervisor/delegate patterns, failure handling, streaming telemetry.citeturn0search0turn0search1
- **OpenAI Agent Framework quickstart** – Reference implementation for registering Python tools and wiring `AgentRunner`.citeturn0search2
- **OpenAI GPT‑5 prompting handbook** – Detailed instructions for structured prompts, tool usage cues, and memory constraints.citeturn0search6
- **OpenAI evaluation playbook** – Test harnesses, trace diffing, and regression workflows.citeturn0search7
- **Anthropic Claude agency best practices** – Deterministic tool wrappers, sandboxing, and multi-agent case studies.citeturn0search3turn0search5

These references, combined with the planner_executor architecture notes above, provide a concrete path to replace bespoke orchestration with the Agent SDK while preserving analytics fidelity.
