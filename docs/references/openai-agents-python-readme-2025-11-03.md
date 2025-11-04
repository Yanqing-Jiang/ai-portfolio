# OpenAI Agents Python SDK Notes (README snapshot — November 3, 2025)

Source: https://github.com/openai/openai-agents-python/blob/main/README.md (retrieved 2025-11-03).

## Runner APIs
- `Runner.run(agent, input=..., session=...)` executes a single turn asynchronously; use `Runner.run_sync` for synchronous contexts.
- `Runner.stream(agent, input=..., session=...)` yields streaming deltas that contain `content` chunks alongside tool call events — aligns with our need to proxy outputs into SSE lanes.
- Sessions accept `None` (stateless default) or any implementation of the `Session` protocol; built-in helpers include `SQLiteSession` and optional Redis extensions.

## Tooling
- Decorate Python callables with `@function_tool` to expose them inside the Agents runtime; the decorator reads type hints to derive JSON schemas automatically, but explicit `json_schema` arguments can override defaults.
- Handoffs allow agents to transfer control by registering other agents in the `handoffs=[...]` list, mirroring our supervisor-to-specialist delegation plan.

## Tracing & Observability
- SDK ships tracing hooks that automatically capture tool calls, arguments, and latencies; integrate with our telemetry sink by propagating `result.trace_id`.

## Requirements
- Python 3.9+
- Install via `pip install openai-agents` (current release line 0.3.x includes streaming, tracing, and session APIs we need).

These notes back the code migration work to integrate the Agents SDK into the analytics agent flows.
