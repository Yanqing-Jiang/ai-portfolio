# ConfigStore Refactor Review

## System Overview
- `backend/analytics_supervisor/config_store.py` exposes a unified async API (`get_templates`, `get_metrics`, `get_companies`, `get_charts`, `get_analytics_context`) that should query the RAG layer first and then fall back to Supabase template_store, YAML configs, and finally an empty result. It keeps a 5 minute in-memory cache by query hash and wraps responses in `ConfigResult` for timing/source metadata.
- `backend/analytics_supervisor/tools.py` is the supervisor-facing toolbelt. All RAG retrieval helpers now call into `ConfigStore`, annotating results with `_config_metadata` for telemetry before returning data to the agent runtime.
- `backend/analytics_supervisor/supervisor.py` implements the Claude Code style single-agent loop. It plans via the OpenAI Responses client, executes tools sequentially, streams events (`planning_proposed`, `tool_start`, `data_retrieved`, `analysis_stream`, etc.), and handles clarification requests by coordinating with the shared clarification endpoint.
- `backend/main.py` wires `/api/analytics/memory/supervisor/stream` to the supervisor workflow and uses `apiService.streamWithAuth` (frontend) to deliver Server-Sent Events back to the React UI.
- The React analytics experience (`components/analytics/memory/Page.tsx` + `components/analytics/hooks/useAnalyticsMemoryStream.ts`) consumes those SSE events, updates chat history, process step indicators, and displays chart/spec + analysis payloads regardless of whether the legacy memory flow or supervisor flow is selected.

## Agentic Flow Walkthrough
1. User enters a query in the "Next Gen Analytics (Memory)" UI. The hook opens a streaming request against `/api/analytics/memory/supervisor/stream` when Supervisor mode is chosen.
2. FastAPI generates a session id, applies rate limits, and yields SSE events from `SupervisorWorkflow.events`.
3. The supervisor plans (`get_tool_schemas`, `detect_intent`, etc.), then iteratively calls tools. Every tool that needs config data (`retrieve_templates_rag`, `search_metrics_rag`, `search_companies_rag`, `get_analytics_context_rag`) invokes the shared `ConfigStore` methods.
4. `ConfigStore` should try sources in priority order, respect async timeouts, cache successful payloads, and return a `ConfigResult` that records the path taken. The supervisor attaches `_config_metadata` for downstream debugging.
5. Completed data (templates/metrics/companies) and chart/analysis results are emitted as SSE events, which the frontend renders inside chat cards.
