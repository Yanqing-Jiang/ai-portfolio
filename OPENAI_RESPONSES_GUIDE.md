# OpenAI Responses API Integration Guide

> **Scope:** How this repository uses OpenAI's **Responses API** (Python SDK v1.107.3+) across the analytics suite. Target reasoning model: **gpt-5-mini-2025-08-07** unless explicitly overridden.

---

## Project Integration Overview
- `backend/unified_responses_client.py` is the single gateway for Responses API access (session tracking, reasoning flags, embeddings, retries).
- `backend/analytics_memory/openai_client.py` adapts the unified client for intent/memory pipelines with sync + async helpers.
- `backend/analytics_shared/intent/` and `backend/analytics_supervisor/` import the unified client for structured outputs, streaming clarifications, and supervisor decisions.
- `backend/analytics_agent.py` calls the same unified client but remains a standalone workflow; avoid touching it unless a shared front-end pathway requires it.
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
from analytics_shared.intent.models import IntentModel

client = get_unified_client()

intent, raw = await client.create_structured(
    response_model=IntentModel,
    messages=[{"role": "user", "content": "Show me AWS revenue vs peers."}],
    reasoning_effort="medium",
    session_id="intent-aws-123"
)
```

---

## Request Patterns (Python)
### Structured intents & clarifications
Used by `analytics_shared.intent.detection` and `analytics_supervisor.supervisor`.
```python
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
Surfaced at `/api/analytics/memory/stream`.
```python
async for delta in client.stream_response(
    messages=conversation,
    session_id=session_id,
    reasoning_effort="low"
):
    if delta.content:
        yield delta.content  # forwarded to FastAPI StreamingResponse
```
* Downstream SSE handlers ignore empty deltas and only push text payloads to the browser.

### Tool calling inside supervisor flows
```python
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
- Async-first: `analytics_supervisor` and `analytics_shared` call awaitable helpers directly.
- Sync contexts (e.g., `analytics_memory/openai_client.py::create_structured`) spin up a thread + event loop to avoid `RuntimeError: asyncio.run()` within an active loop.
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

## Practical Tips
- Prefer the Responses API for new analytics work; legacy Chat Completions sticks around only for the research agent.
- Keep instructions short and explicit; pair them with structured outputs whenever the backend needs to consume results.
- Use `reasoning: { "effort": "minimal" }` and `text: { "verbosity": "low" }` for latency-sensitive paths.
- Before modifying `analytics_agent.py`, confirm the change is required by a shared front-end experience; otherwise leave it untouched.
- Update this guide whenever SDK versions, models, or module paths change. Touch the helper functions first, then refresh examples here.
