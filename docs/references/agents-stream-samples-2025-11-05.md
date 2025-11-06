# Agents Stream Samples — November 5, 2025

This reference captures how to collect and inspect raw OpenAI Agents streaming events for the analytics single-agent flow. The `scripts/dump_agents_stream.py` helper converts `Runner.run_streamed(...)` payloads into planner-style SSE events so we can snapshot the contract for tests.

## Prerequisites
- Valid `OPENAI_API_KEY` with access to the Agents SDK.
- `ANALYTICS_ENABLE_AGENTS=1` so the single-agent controller initializes the Agents runner.
- Repository dependencies installed (`pip install -r backend/requirements.txt`).

## Capture Workflow (PowerShell)
```powershell
Set-Location C:\Users\Y_J\Desktop\ai-portfolio-main
$env:ANALYTICS_ENABLE_AGENTS = "1"
$env:OPENAI_API_KEY = "<your-key>"
python scripts/dump_agents_stream.py "Build a KPI dashboard for Snowflake revenue" --output docs/references/agents-stream-fixture.json
```

The script writes a JSON fixture containing raw Agents SDK stream events alongside the translated SSE payloads:
```json
{
  "query": "Build a KPI dashboard for Snowflake revenue",
  "session_id": "sess_123",
  "trace_id": "trace_abc",
  "raw_events": [
    {"type": "RunItemStreamEvent", "name": "tool_called", "item": {"raw_item": {"name": "generate_sql"}}},
    {"type": "RawResponsesStreamEvent", "data": {"type": "response.function_call_arguments.delta", "delta": {"sql": "SELECT ..."}}}
  ],
  "sse_events": [
    {
      "event": "tool_call_delta",
      "data": {
        "tool_call": {
          "id": "call_01",
          "name": "generate_sql",
          "arguments_delta": {"sql": "SELECT ..."},
          "sequence_number": 0,
          "output_index": 0
        }
      },
      "flow_mode": "single_agent"
    }
  ]
}
```

## Next Steps
- Run the capture script against a real analytics session once the Agents runner is wired to production data sources.
- Refresh `docs/references/agents-stream-fixture.json` with the live transcript (current file contains a sanitized stub used by `backend/tests/analytics/test_agents_stream_bridge.py`).
- Point `backend/tests/analytics/test_planner_sequencer.py` fixtures at the captured SSE payload once finalized.
