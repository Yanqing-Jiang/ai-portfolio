# OpenAI Responses API Integration Guide

> **Scope:** How we use OpenAI's **Responses API** (SDK v1.107.3+) in this codebase. This guide documents the unified approach to OpenAI API integration across the analytics system. Target model: **gpt-5-mini-2025-08-07**.

---

## Where this lives in the repo

* `backend/unified_responses_client.py` — unified client for all OpenAI Responses API interactions
* `backend/analytics_memory/openai_client.py` — analytics memory specific client wrapper
* `backend/analytics_supervisor/responses_client.py` — supervisor specific client wrapper

Keep these helpers the *only* callers of the SDKs so we get uniform logging, retries, tracing, and model switches.

---

## SDK install & runtime

### Python

```bash
pip install --upgrade "openai>=1.107.3" pydantic>=2.7
```

**Note:** This guide is tested with OpenAI SDK v1.107.3. The Responses API is available and stable in this version.

```python
from openai import OpenAI, AsyncOpenAI
client = OpenAI()
async_client = AsyncOpenAI()
```

### TypeScript / Node

```bash
npm i openai@^5
# If you use Zod helpers for structured output, prefer zod@^3 for now
npm i zod@^3
```

```ts
import OpenAI from "openai";
export const client = new OpenAI({ apiKey: process.env.OPENAI_API_KEY });
```

---

## Migration-at-a-glance (Chat Completions → Responses)

* **system → instructions** (top‑level string)
* **messages\[] → input** (string or list of role/content items)
* **choices\[0].message.content → response.output\_text**
* **beta.chat.completions.parse → responses.parse** (keep Pydantic/Zod schemas)
* **streaming:** `stream=True` on `responses.create` and iterate SSE events

---

## Models to use

* **Default:** `gpt-5-mini-2025-08-07-mini-2025-08-07` (fastest/cheapest, great for most flows)
* **Heavy reasoning:** `gpt-5-mini-2025-08-07` (enable `reasoning: { effort: "minimal" | "medium" | "high" }`)
* Optional control: `text: { verbosity: "low" | "medium" | "high" }`

---

## Core Patterns (Python)

### 1) Standard response

```python
resp = client.responses.create(
    model="gpt-5-mini-2025-08-07",
    instructions="You are a precise analytics assistant.",
    input="Summarise cohort performance in one paragraph.",
    text={"verbosity": "low"},  # optional
)
print(resp.output_text)
```

### 2) Structured outputs via `responses.parse`

```python
from typing import Literal
from pydantic import BaseModel

class Insight(BaseModel):
    headline: str
    metric_delta: float
    confidence: Literal["low", "medium", "high"]

parsed = client.responses.parse(
    model="gpt-5-mini-2025-08-07",
    instructions="Extract a single KPI insight from the passage.",
    input=[{"role": "user", "content": "GMV +7.3% WoW; CAC −12%; NPS 58."}],
    text_format=Insight,  # returns .output_parsed as an Insight instance
    reasoning={"effort": "minimal"},  # optional on gpt-5-mini-2025-08-07; remove if your model rejects
)
print(parsed.output_parsed)
```

### 3) Streaming (server‑sent events)

```python
stream = client.responses.create(
    model="gpt-5-mini-2025-08-07",
    instructions="Be concise.",
    input="Explain cohort vs. rolling retention.",
    stream=True,
)
for event in stream:
    if event.type == "response.output_text.delta":
        print(event.delta, end="")
```

### 4) Tool calling (Responses API)

```python
tools = [
  {
    "type": "function",
    "name": "lookup_cohort",
    "description": "Get metrics for a named cohort",
    "parameters": {
      "type": "object",
      "properties": {"name": {"type": "string"}},
      "required": ["name"],
    },
  }
]
resp = client.responses.create(
    model="gpt-5-mini-2025-08-07",
    instructions="Use tools when needed; otherwise answer directly.",
    input="What’s the churn for the 2025-07 signup cohort?",
    tools=tools,
)
for item in resp.output:
    for content in getattr(item, "content", []) or []:
        if getattr(content, "type", None) == "tool_call":
            call = content  # resolve call.name + call.arguments in your runtime
```

---

## Core Patterns (TypeScript)

### 1) Standard response

```ts
const resp = await client.responses.create({
  model: "gpt-5-mini-2025-08-07-mini-2025-08-07",
  instructions: "You are a precise analytics assistant.",
  input: "Summarise cohort performance in one paragraph.",
  text: { verbosity: "low" },
});
console.log(resp.output_text);
```

### 2) Structured outputs

**Option A — SDK helper (Zod)**

```ts
import { z } from "zod";
import { zodTextFormat } from "openai/helpers/zod"; // requires zod v3 today

const Insight = z.object({
  headline: z.string(),
  metric_delta: z.number(),
  confidence: z.enum(["low", "medium", "high"]),
});

const parsed = await client.responses.parse({
  model: "gpt-5-mini-2025-08-07",
  instructions: "Extract one KPI insight.",
  input: "GMV +7.3% WoW; CAC −12%; NPS 58.",
  text: { format: zodTextFormat(Insight, "insight") },
  // text: { verbosity: "low" }, // optional
});
console.log(parsed.output_parsed); // typed by Zod
```

**Option B — Manual JSON schema** (works with any validator)

```ts
const parsed = await client.responses.parse({
  model: "gpt-5-mini-2025-08-07",
  instructions: "Extract one KPI insight.",
  input: "GMV +7.3% WoW; CAC −12%; NPS 58.",
  text: {
    format: {
      type: "json_schema",
      json_schema: {
        name: "insight",
        schema: {
          type: "object",
          additionalProperties: false,
          properties: {
            headline: { type: "string" },
            metric_delta: { type: "number" },
            confidence: { enum: ["low", "medium", "high"], type: "string" },
          },
          required: ["headline", "metric_delta", "confidence"],
        },
      },
    },
  },
});
```

### 3) Streaming

```ts
const stream = await client.responses.create({
  model: "gpt-5-mini-2025-08-07-mini-2025-08-07",
  input: "Explain cohort vs. rolling retention.",
  stream: true,
});
for await (const event of stream) {
  if (event.type === "response.output_text.delta") process.stdout.write(event.delta);
}
```

---

## Sessions & memory

Prefer **Agents SDK sessions** for multi‑turn memory; for raw Responses API flows, carry a stable `session_id` in your app and store prior turns server‑side.

* **Agents SDK:** `SQLiteSession` (dev) or `SQLAlchemySession` (prod) to persist conversation state; one line to reuse across runs.
* **OpenAI‑hosted:** `OpenAIConversationsSession` to offload storage.

---

## Agents SDK quickstart (Python)

```python
from agents import Agent, Runner

support = Agent(
    name="SupportAgent",
    instructions=(
        "You are a concise support assistant. Use tools if provided."
    ),
    model="gpt-5-mini-2025-08-07",  # optional; otherwise set provider defaults
)

result = Runner.run_sync(support, "Where is order 123-ABC?")
print(result.final_output)
```

### Tools

```python
from agents import function_tool

@function_tool
def lookup_order(order_id: str) -> dict:
    """Return status and ETA for an order."""
    ...

agent = Agent("Support", tools=[lookup_order], model="gpt-5-mini-2025-08-07")
```

### Sessions (memory)

```python
from agents import SQLiteSession
session = SQLiteSession("ticket-123")
Runner.run_sync(agent, "User reports missing package", session=session)
Runner.run_sync(agent, "Add a friendly apology", session=session)
```

### Handoffs & guardrails

* **Handoffs:** route between agents (e.g., Support → Billing) without spaghetti code.
* **Guardrails:** validate inputs/outputs (regex, Pydantic, or custom checks) and fail fast when contracts are broken.

---

## Error handling & observability

* Log: model, `_request_id`, response ID, and your `session_id`.
* Backoff on `RateLimitError` with jitter; centralize retries in the client layer.
* Cap payloads to \~20k tokens; summarize/segment large inputs first.
* If structured parse fails, prefer tightening the schema (enums, formats) over blind retries.

## Async/Sync Integration

**Important:** When integrating async Responses API calls in mixed async/sync contexts:

* **Never use `asyncio.run()`** in an existing event loop - causes `RuntimeError`
* **Use thread pools** for sync wrappers: `concurrent.futures.ThreadPoolExecutor`
* **Example sync wrapper:**

```python
import asyncio
import concurrent.futures

def sync_create_structured(async_client, **kwargs):
    async def _async_call():
        return await async_client.create_structured(**kwargs)

    with concurrent.futures.ThreadPoolExecutor() as executor:
        future = executor.submit(asyncio.run, _async_call())
        return future.result()
```

---

## Practical tips

* Prefer **Responses API** for new work; Chat Completions stays for backwards‑compat.
* Use `instructions` consistently as a short, explicit system persona.
* Use **structured outputs** for anything your code will consume; free‑form text for human‑readables.
* For speed‑sensitive tasks on `gpt-5-mini-2025-08-07`, set `reasoning: { effort: "minimal" }` and `text.verbosity: "low"`.
* For TypeScript structured outputs, the Zod helper works best with zod v3 today; otherwise pass your own JSON Schema.

---

## Appendix: Input shapes

* **String:** `input="hello"`
* **Role items:**

```json
[
  {"role": "user", "content": "hello"}
]
```

* **Multimodal:**

```json
[
  {
    "role": "user",
    "content": [
      {"type": "input_text", "text": "caption this"},
      {"type": "input_image", "image_url": "https://.../image.png"}
    ]
  }
]
```

---

## Appendix: Event types (streaming)

You’ll commonly handle:

* `response.output_text.delta`
* `response.refusal.delta`
* `response.completed`

---

**Maintainers:** keep this file current with SDK/model updates. If a breaking change lands, update the helpers first, then examples here.
