# Analytics Agent Orchestrator (OpenAI Agents SDK v0.5.0)

This brief captures how the new single-agent orchestrator will replace the planner/sequencer path while reusing streaming, telemetry, and session infrastructure that ships today.

## Current State Audit
- **Single-agent flow** – `backend/analytics/flows/single_agent_tools.py:1200-1350` wraps `Runner.run_streamed` with planner-specific context. Events are proxied through `AgentsStreamBridge` before being surfaced on the SSE queue.
- **Multi-agent flow** – `backend/analytics/flows/multi_agent.py` still relies on the planner/sequencer orchestrator, delegating to `AgentExecutionOrchestrator` for DAG fan-out.
- **Session storage** – `backend/analytics/core/session_state.py` persists receipts, lane metadata, and existing agent telemetry fields via `SessionStateSnapshot`.
- **Telemetry** – `backend/analytics/core/telemetry.py` exposes helpers (`tool_iteration`, `agent_handoff`, `analysis_chunk`) that the frontend dashboard expects.
- **Streaming contract** – `backend/analytics/flows/agents_stream_bridge.py` translates OpenAI Agents SDK stream events into planner-style SSE payloads (`tool_call_delta`, `analysis_streaming`, etc.).
- **Configuration** – `backend/config/schemas/agents.yaml` holds per-mode defaults (model, temperature, retries) that `ConfigStore.get_agent_mode_config` returns.

## Objectives
1. Drive the entire single-agent workflow through an adaptive plan → act → observe loop powered by OpenAI Agents SDK **v0.5.0**.
2. Persist plan state, receipts, retries, and reflections into session storage so revisions can reuse prior work.
3. Emit agent-native telemetry and SSE events without breaking existing frontend consumers.
4. Keep the planner pipeline intact as a guarded fallback until parity has been proven.

## Module Layout
```
backend/analytics/agent_orchestrator/
  agent_plan.py        # plan graph, node status, templating
  agent_runtime.py     # plan -> act -> observe loop, integrates Runner.stream
  event_bus.py         # bridges agent events into SSE using AgentsStreamBridge + EventEmitter
  memory.py            # AgentMemory backed by SessionStateSnapshot
  __init__.py
docs/design/agent-orchestrator.md
backend/tests/analytics/test_agent_orchestrator.py
```

## Plan Model (`agent_plan.py`)
- Represent plans as a DAG of `PlanNode` objects with fields:
  - `node_id` (stable UUID), `kind` (tool, analysis, reflection, clarification), `status`, `retries`, `max_retries`, `dependencies`, `inputs`, `artifacts`.
  - `status ∈ {pending, running, succeeded, failed, skipped, cancelled}`.
- Expose helpers:
  - `PlanTemplate` loader for YAML/JSON-defined defaults (loaded via `ConfigStore.get_agent_mode_config`).
  - `PlanState` for mutation-safe tracking of node status, retry counters, and timestamps.
- Guard invariants:
  - DAG validation (no cycles, dependencies exist).
  - Retry budget enforcement (`max_retries` from config or node override).
  - `mark_failed` decides between retry vs terminal failure.

## Runtime Loop (`agent_runtime.py`)
- Entry point `AgentOrchestratorRuntime.run(query, session_id, runner, agent, config, bridge)`:
  1. **Plan** – Seed a task graph from templates + live context (session receipts, revision directives, guardrails). When revisiting a session, preload previously succeeded nodes and pending lanes.
  2. **Act** – Dispatch tool nodes through OpenAI Agents SDK (`Runner.stream(agent=..., input=..., session=...)`) while streaming events into SSE:
     - Build function tool invocations from node metadata/schema registry.
     - Wrap `Runner.stream` in an async iterator; route events into `AgentsStreamBridge` + new event bus (below).
  3. **Observe** – Update plan state with outcomes, record retries / reflections, and decide next node(s) to schedule.
  4. **Reflect** – Allow nodes of kind `reflection` to update plan priorities or request clarifications; persist reasoning in memory.
  5. Loop until all runnable nodes reach a terminal status or retry budget is exhausted.
- Runtime responsibilities:
  - Hydrate config: default plan, retry ceilings (`max_tool_retries`), guardrail toggles (latency, cache reuse).
  - Enforce parallel group constraints and sequential ordering (analysis waits on SQL/web/market).
  - Surface structured telemetry via `telemetry.tool_iteration`, `telemetry.agent_handoff`, `telemetry.analysis_chunk`.
  - Emit terminal bundle (`analysis_bundle`) matching current frontend expectations.

## Event Bus (`event_bus.py`)
- Abstraction `AgentsStreamBridge` already normalizes OpenAI stream events; the event bus will:
  - Translate plan mutations into SSE events:
    - `agent_plan_updated` – includes node statuses, retry counts, dependency summaries.
    - `tool_attempt` – emitted on tool node start, including `plan_node_id`, `tool_name`, `attempt`, `parallel_group`.
    - `agent_reflection` – reasoning deltas/reflections for UI "thinking" panes.
  - Reuse `EventEmitter` for heartbeats, completion, and errors so existing listeners remain compatible.
- Provide an async `publish` API for runtime to enqueue events without direct queue coupling.

## Agent Memory (`memory.py`)
- Wraps `SessionStateSnapshot` to expose:
  - `load_receipts()` / `record_receipt(tool_name, payload)`.
  - `load_plan_state()` / `persist_plan_state()` storing serialized DAG metadata under `snapshot.tool_cache["agent"]["plan_state"]`.
  - `record_run_metadata(run_id, trace_id, model, retry_counts, receipts)` delegating to existing `SessionStateSnapshot.record_agent_run`.
- Guarantees backward compatibility:
  - Additional fields live under `tool_cache["agent"]` or new namespaced keys.
  - Updates call `snapshot.touch()` so TTL/updated_at semantics stay intact.
  - Provide migration guard that tolerates absent agent sections.

## Configuration
- Extend `backend/config/schemas/agents.yaml`:
  - `defaults.plan_templates` – list of node definitions with required/optional lanes.
  - `defaults.retry_policy` – `max_attempts`, `backoff_seconds`, `retryable_error_codes`.
  - Mode-specific overrides (`single_agent.plan_templates`, `single_agent.guardrails.latency_ms`, etc.).
- `ConfigStore.get_agent_mode_config` now resolves the nested fields; runtime validates keys and falls back gracefully when entries missing.

## Telemetry & Observability
- Emit structured payloads:
  - `telemetry.tool_iteration` for every tool node attempt (`status=running/succeeded/failed`).
  - `telemetry.agent_handoff` when reflections request clarifications or lane reruns.
  - `telemetry.analysis_chunk` streaming final analysis text (mirrors existing behavior).
- Attach `agents_run_id`, `agent_role`, `retry_count` metadata for dashboards.
- Log plan snapshots and retry decisions at INFO for postmortem traceability.

## Testing Strategy
- **Unit tests** – `backend/tests/analytics/test_agent_orchestrator.py` covering:
  - Plan validation (duplicate node, cycle, retry exhaustion).
  - Runtime executing a synthetic DAG with stubbed tool adapters and ensuring retries obey policy.
  - Memory persistence round-trips for receipts and plan state.
- **Integration smoke** – async test harness that executes the runtime against a fake agent streaming target producing `tool_call_delta`, `analysis_streaming`, and verifying SSE payloads match expected schema.
- **Regression guardrails** – property-based tests (or parametrized) to ensure cached nodes skip execution and resume correctly after persisted plan reload.

## Rollout Considerations
- Feature flag `AGENT_ORCHESTRATOR_ENABLED` gates the new runtime in `analytics_memory_workflow`; fallback continues to call `SingleAgentController` when disabled.
- Maintain planner-based flow as `planner-executor` until telemetry parity achieved; include runbook updates and incident response steps in `docs/ops/analytics-agent-orchestrator.md`.
- Instrument config versioning so plan templates can be swapped without code deploys, leveraging TTL-aware cache invalidation.

