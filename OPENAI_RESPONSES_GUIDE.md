# OpenAI Responses API Integration Guide

> **Scope:** How this repository uses OpenAI's **Responses API** (Python SDK v1.107.3+) across the analytics suite. Target reasoning model: **gpt-5-mini-2025-08-07** unless explicitly overridden.

---

## Project Integration Overview
- `backend/unified_responses_client.py` is the single gateway for Responses API access (session tracking, reasoning flags, embeddings, retries).
- `backend/analytics/core/openai_client.py` wraps the unified client for analytics flows, exposing sync + async helpers that preserve shared session state.
- `backend/analytics/flows/` (planner_executor, single_agent_tools, multi_agent) orchestrate Responses prompts and stream SSE telemetry via `workflow.run_flow()`.
- `backend/analytics/sql/` compiles YAML catalogues from `backend/config/schemas/*.yaml` to suggest, validate, and execute SQL with deterministic fallbacks when the LLM output fails checks.
- `backend/analytics_agent.py` still calls the unified client but remains a standalone workflow; only update it when a shared front-end pathway requires the change.
- REST endpoints in `backend/main.py` surface these flows to the React front-end. No direct Responses usage exists in the front-end; all calls go through FastAPI.

---

## Unified Client Architecture
- **Singleton access:** `get_unified_client()` returns a cached `UnifiedResponsesClient` backed by `AsyncOpenAI`.
- **Message normalization:** `_format_messages` converts legacy content arrays to the `input_text` shape required by Responses.
- **Session continuity:** `session_id` maps to `response_id` so follow-up questions maintain context.
- **Reasoning controls:** `SUPERVISOR_REASONING_EFFORT` (low/medium/high) drives supervisor calls; `OPENAI_REASONING_MODELS` restricts which models receive the `reasoning` payload.
- **Embeddings support:** `create_embeddings()` bridges vector search consumers (RAG service, analytics memory cache warmers).
- **Streaming wrapper:** `stream_response()` yields `ResponseDelta` objects (`content`, `reasoning`, `tool_calls`) consumed by SSE endpoints.
- **Structured outputs:** `create_structured()` and `create_structured_async()` return `(parsed_model, raw_response)` tuples for Pydantic schemas used throughout analytics flows.

### Typical usage
```python
from unified_responses_client import get_unified_client
from analytics.core.state import IntentModel

client = get_unified_client()

intent, raw = await client.create_structured(
    response_model=IntentModel,
    messages=[{"role": "user", "content": "Show me AWS revenue vs peers."}],
    reasoning_effort="medium",
    session_id="intent-aws-123"
)
```

## YAML-Guided SQL Planning
- `analytics/sql/templates.py` loads the YAML catalogue (`backend/config/schemas/*.yaml`) listing metrics, charts, and query skeletons.
- `analytics/flows/planner_executor.py` asks the Responses API for a candidate SQL statement via `UnifiedResponsesClient.simple_completion()` before validation.
- `analytics/sql/validator.py` enforces catalog-driven guardrails (allowed tables/columns, limit ceilings) and falls back to `analytics/sql/compiler.py` when the LLM output fails safety checks.
- `analytics/sql/executor.py` runs the final statement and streams `sql_generated` telemetry including whether a template fallback was required.
- `single_agent_tools` and `multi_agent` flows wrap these planner events with `tool_call`, `agent_turn`, and `agent_reasoning` telemetry but reuse the same SQL pipeline.

---

## Request Patterns (Python)
### Structured intents & clarifications
Used by `analytics.core.clarify` and `analytics.flows.planner_executor` during intent and clarification phases.
```python
from analytics.core.state import ClarifyRequestModel

parsed, response = await client.create_structured(
    response_model=ClarifyRequestModel,
    messages=message_chain,
    reasoning_effort="medium",
    session_id=session_key,
    model=os.getenv("OPENAI_INTENT_MODEL", "gpt-5-mini-2025-08-07")
)
```
* Returns the typed Pydantic model plus the raw SDK object for logging/analytics.

### Streaming analytics answers
Surfaced at `/api/analytics/memory/stream`; implemented by `analytics/flows/workflow.analytics_memory_workflow()` which wraps the planner, single-agent, and multi-agent flows.
- Select a flow with the `flow` query parameter (`planner-executor`, `single-agent`, `multi-agent`); the legacy `mode` alias remains for backwards compatibility.
```python
async for delta in client.stream_response(
    messages=conversation,
    session_id=session_id,
    reasoning_effort="low"
):
    if delta.content:
        yield delta.content  # forwarded to FastAPI StreamingResponse
```
* Downstream SSE handlers ignore empty deltas and forward structured events to `useanalyticsMemoryStream`, which decorates them with `tool_call`, `agent_turn`, and `agent_reasoning` telemetry for the demo flows.

### Tool calling inside analytics tool registries
```python
from analytics.tools.registry import SupervisorTools

registered_tools = SupervisorTools().get_tool_schemas()

response = await client.create_response(
    messages=tool_prompt,
    tools=registered_tools,
    reasoning_effort=SUPERVISOR_REASONING_EFFORT
)
for item in getattr(response, "output", []) or []:
    for content in getattr(item, "content", []) or []:
        if content.get("type") == "tool_call":
            await dispatch_tool_call(content)
```
* After running the tool, results are posted back with `client.client.responses.submit_tool_outputs(...)`.

---

## Request Patterns (TypeScript)
We do not call the Responses API directly from the Vite front-end today. These examples remain for reference when building new client-side tooling.
```ts
import OpenAI from "openai";
const client = new OpenAI({ apiKey: process.env.OPENAI_API_KEY });

const resp = await client.responses.create({
  model: "gpt-5-mini-2025-08-07",
  instructions: "You are a precise analytics assistant.",
  input: "Summarise cohort performance in one paragraph.",
});
console.log(resp.output_text);
```
Use `openai/helpers/zod` if you need structured parsing in Node services.

---

## Environment Configuration
- `OPENAI_API_KEY` **(required)** for all server-side flows; requests fail fast if missing.
- `OPENAI_MODEL` overrides the default model for generic responses.
- `OPENAI_INTENT_MODEL` overrides analytics intent detection (otherwise defaults to GPT-5 mini).
- `OPENAI_REASONING_MODELS` (comma-separated) opt-in list for sending `reasoning` payloads.
- `SUPERVISOR_REASONING_EFFORT` tunes supervisor depth (`low` default).
- `OPENAI_EMBEDDING_MODEL` (optional) for RAG utilities; falls back to the client default when unset.

Keep these values in `backend/.env`; never check secrets into version control.

---

## Error Handling & Observability
- Log the OpenAI `response.id`, chosen model, and session key for every request (already wired in unified client).
- Retries with jitter wrap transient failures; adjust at the unified client level if behaviour changes.
- Cap token usage (~20k) before dispatch; analytics flows chunk or summarise payloads when necessary.
- Structured parse failures should tighten schemas or input prompts rather than brute-force retrying.

---

## Async vs Sync Callers
- Async-first: `analytics/flows` modules call awaitable helpers directly (planner, single-agent, multi-agent).
- Sync contexts (e.g., `analytics/core/openai_client.py::create_structured`) spin up a thread + event loop to avoid `RuntimeError: asyncio.run()` within an active loop.
- Avoid creating ad-hoc clients; always call `get_unified_client()` so session state and rate limiting remain centralized.

---

## Agents SDK (Optional Reference)
We currently do not ship the Agents SDK in production, but the patterns below remain valid for experiments.
```python
from agents import Agent, Runner

support = Agent(
    name="SupportAgent",
    instructions="You are a concise support assistant.",
    model="gpt-5-mini-2025-08-07",
)

result = Runner.run_sync(support, "Where is order 123-ABC?")
print(result.final_output)
```
For tool integration use `agents.function_tool`; persist memory with `SQLiteSession` or `SQLAlchemySession`.

---

## Flow Test Coverage (2025-09-26)
- `backend/tests/analytics/test_flow_modes_queries.py` runs stubbed planner-executor, single-agent, and multi-agent flows.
  - "Nvidia market share in the past 5 years?" selects the `market_share_single` YAML template and streams SQL from the Responses API stub.
  - "How's Nvidia margin growth compare to industry average?" drives the single-agent tool flow, logging `tool_call` end events with template metadata.
  - Multi-agent mode emits `agent_turn` events (e.g., `sql_specialist`) while reusing the shared planner pipeline.
- `backend/tests/analytics/test_legacy_modules_removed.py` guards against reintroducing the retired `analytics_memory`, `analytics_shared`, and `analytics_supervisor` packages.

## Practical Tips
- Prefer the Responses API for new analytics work; legacy Chat Completions sticks around only for the research agent.
- Keep instructions short and explicit; pair them with structured outputs whenever the backend needs to consume results.
- Use `reasoning: { "effort": "minimal" }` and `text: { "verbosity": "low" }` for latency-sensitive paths.
- Before modifying `analytics_agent.py`, confirm the change is required by a shared front-end experience; otherwise leave it untouched.
- Update this guide whenever SDK versions, models, or module paths change. Touch the helper functions first, then refresh examples here.
