# Integrating the OpenAI Agent SDK into Next-Gen Analytics

This guide outlines how to introduce the OpenAI Agent SDK into the analytics stack, replacing bespoke orchestration with SDK-managed agents, tooling, and guardrails. It assumes the repository layout as of October 22, 2025 and highlights the files/processes that benefit most from the migration.

---

## 1. Why adopt the Agent SDK here?

| Current Component | Location | Pain Point | Agent SDK Benefit |
|-------------------|----------|------------|-------------------|
| Planner / supervisor loop | `backend/analytics/flows/planner_executor.py:320-4380` | Custom event bus, manual tool scheduling, difficult tracing | Model flows as first-class agents with `AgentRunner`, built-in handoffs, and centralized telemetry |
| Schema clarifier | `backend/analytics/agents/schema_clarifier.py` | Manual intent validation, no guardrails | Convert to a focused agent using guardrail presets + structured outputs |
| Research / web agent | `backend/research_agent.py` | LangChain-specific wiring; lacks Responses-native safety | Replace with Agent SDK tooling (web search, HTTP tool adapters) |
| OpenAI client wrappers | `backend/unified_responses_client.py`, `backend/analytics/core/openai_client.py` | Hand-rolled Responses calls, compatibility shims | Use SDK’s native invocation + MCP tool registry |
| Multi-agent coordination & events | `backend/analytics/flows/multi_agent.py`, `components/analytics/hooks/useAnalyticsMemoryStream.ts` | Custom event schema and state machine | Consume SDK tracing stream directly, reducing bespoke protocol |

---

## 2. Prerequisites

1. **Upgrade dependencies**
   ```powershell
   # backend virtualenv
   pip install "openai-agent>=0.6.0" "openai>=1.110.0"
   ```
   Update `backend/requirements.txt` accordingly.

2. **Set environment variables**
   - `OPENAI_API_KEY` (existing)
   - `AGENT_SDK_MODEL` (default `gpt-5-mini-2025-08-07` for schema compliance)
   - Optional: `OPENAI_AGENT_LOG_LEVEL`, `OPENAI_AGENT_TRACING` (for SDK diagnostics)

3. **Audit tool dependencies** – Identify internal tool call sites (SQL executor, web retriever, Supabase adapters) so they can be registered as SDK tools.

---

## 3. Migration checklist

### Step 1 – Introduce an Agent SDK entry point

Create `backend/analytics/agents/runner.py` that instantiates the SDK `AgentRunner` with guardrails and a shared tool registry.

Suggested scaffolding:
```python
from openai import AgentsClient
from openai_agent import AgentRunner, GuardrailConfig
from analytics.agents.tools import analytics_tools_registry

def build_runner():
    client = AgentsClient()
    runner = AgentRunner(
        client=client,
        tools=analytics_tools_registry(),
        guardrails=GuardrailConfig(strict=True, default_model="gpt-4o-mini-2024-07-18"),
    )
    return runner
```

### Step 2 – Register tools

Convert existing Python callables into SDK tool adapters:

| Tool | Current implementation | New adapter |
|------|------------------------|-------------|
| SQL execution | `backend/analytics/sql/executor.py:1-320` | Wrap in `@tool` decorated function (e.g. `sql_query_tool`) |
| Chart design | `backend/analytics/core/charting.py:1-240` | Expose highlight or spec generator as tool |
| Web retrieval | `backend/research_agent.py` | Replace with SDK’s `web-search` tool or register custom HTTP fetcher |
| Market data | any Supabase or price fetcher functions | Register as data tools |

Add a module `backend/analytics/agents/tools.py` collecting these wrappers. Consider using MCP if these tools require network/file isolation.

### Step 3 – Translate planner phases into agents

Break `planner_executor` responsibilities into dedicated agents:

1. **Classifier agent** – Handles topic detection and off-topic responses.
   - Source: `_intent_phase` initialization inside `planner_executor.py:3730-3860`.
2. **Intent resolver agent** – Combines slot detection + schema clarifier.
   - Source: `analytics.core.intent_impl.detection.resolve_intent_slots_async` and `analytics.agents.schema_clarifier`.
3. **SQL specialist agent** – Plans and validates SQL (from `planner_executor.run_sql_phase`).
4. **Chart specialist agent** – Builds chart specs (`planner_executor.run_chart_phase` + `charting.py`).
5. **Narrative agent** – Streams analysis (`analytics/core/analysis.py`).

Define each agent via the SDK:
```python
from openai_agent import Agent

intent_agent = Agent(
    name="IntentResolver",
    instructions="Resolve company, timeframe, and metric slots. Use clarification tool when needed.",
    tools=[sql_metadata_tool, clarification_tool],
    model="gpt-4o-mini-2024-07-18",
)
```

Then orchestrate them with `runner.handoff(intent_agent, sql_agent, context=...)` to mirror the existing lane ordering.

### Step 4 – Replace manual event loop

Where `planner_executor` currently yields JSON events to the frontend, switch to streaming traces from the SDK:

```python
async for event in runner.stream(task, trace=True):
    socket.emit("agent_event", event.to_dict())
```

Remove redundant telemetry plumbing once the SDK trace events are wired into `useAnalyticsMemoryStream.ts`.

### Step 5 – Integrate guardrails and structured outputs

*Harness guardrails* – Standardize sensitive-data policies by loading guardrail YAML:
```python
from openai_agent import GuardrailConfig
guardrails = GuardrailConfig.from_file("config/agent_guardrails.yaml")
```

*Structured responses* – Replace custom JSON schema validation with SDK-enforced outputs for clarification questions, analysis summaries, etc.

### Step 6 – Adapt frontend stream handling

Update `components/analytics/hooks/useAnalyticsMemoryStream.ts:3300-3760` to consume SDK trace schemas (`agent_turn`, `handoff`, `tool_call`, `deliberation`). The hook already recognizes similar events—map new field names to existing UI states.

### Step 7 – Incremental rollout

1. **Phase 0:** Wrap schema clarifier only. Keep planner executor intact; use Agent SDK for slot validation. Verify ledger logs show `resolver_status=structured` without fallback.
2. **Phase 1:** Migrate research agent + SQL tool to SDK tools. Drive them through `AgentRunner` from the existing planner and compare outputs.
3. **Phase 2:** Replace entire planner executor loop with Agent SDK orchestration. Decommission `planner_executor.py` once parity tests pass.
4. **Phase 3:** Enable guardrails + external MCP tools; instrument telemetry around SDK traces.

---

## 4. Files to update / create

| Action | File(s) |
|--------|---------|
| Add Agent SDK runner scaffolding | `backend/analytics/agents/runner.py` (new) |
| Register tools | `backend/analytics/agents/tools.py` (new), update individual tool modules |
| Convert schema clarifier | `backend/analytics/agents/schema_clarifier.py` |
| Retrofit planner orchestration | `backend/analytics/flows/planner_executor.py`, `backend/analytics/flows/multi_agent.py` |
| Update OpenAI client wrappers | `backend/unified_responses_client.py`, `backend/analytics/core/openai_client.py` |
| Stream traces to frontend | `components/analytics/hooks/useAnalyticsMemoryStream.ts`, server push endpoints |
| Configuration | `backend/config/agent_guardrails.yaml` (new), update `requirements.txt`, environment docs |
| Tests | Add SDK integration tests under `backend/tests/agents/` |

---

## 5. Additional considerations

- **Telemetry:** The SDK emits structured logs; integrate them with `backend/analytics/core/telemetry.py` or migrate telemetry entirely to the SDK pipeline.
- **Rollbacks:** Keep the existing planner executor behind a feature flag (`ANALYTICS_AGENT_SDK_ENABLED`) so you can revert quickly.
- **Latency:** First-time schema enforcement may add startup latency; warm the runner during application boot.
- **Security:** Guardrails replace some manual filtering, but continue to sanitize SQL inputs and web content before executing tools.

---

By introducing the Agent SDK progressively—starting with the schema clarifier and moving toward full planner orchestration—you can reduce custom orchestration code, gain official guardrails, and align with OpenAI’s agent tooling roadmap ahead of the Assistants API sunset.
