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

## Critical Issues Observed
- `backend/analytics_supervisor/config_store.py:44` logs import fallbacks with `logger.warning(...)` before `logger` is defined, so any ImportError raises `NameError` and stops module loading.
- `backend/analytics_supervisor/config_store.py:293-338` expects `self.yaml_configs['query_patterns']`, but `CONFIGS.__dict__` stores the value under `queries['query_patterns']`. YAML fallback for templates therefore never returns matches.
- `backend/analytics_supervisor/config_store.py:366-387` treats `metrics_config.get('base_metrics', [])` as a list even though YAML uses `metrics` (dict) + `derived_metrics` (dict). The concatenation throws, is swallowed, and metrics fallback always returns an empty list.
- `backend/analytics_supervisor/config_store.py:444-459` naïvely aggregates every list within `companies` and `selection_rules`, pulling raw ticker strings into `companies_list`; subsequent `.get(...)` calls fail, so companies fallback emits no results.
- `backend/analytics_supervisor/config_store.py:515-547` iterates `chart_types` as if it were a list. The YAML is keyed dict entries, so the fallback never produces chart configs.
- `backend/analytics_supervisor/config_store.py:121-132` defines `FallbackConfig` as a plain class without `__init__`, yet code/tests instantiate it with keyword overrides (see `backend/analytics_supervisor/test_config_store.py:330-346`). This currently raises `TypeError`, breaking configuration overrides and several tests.

## Recommended Fixes
- Initialize the module logger before dependency import fallbacks or log via `logging.getLogger(__name__)` inside the exception block.
- Align YAML access with `CONFIGS` structure: use `self.yaml_configs.get('queries', {}).get('query_patterns', {})`, iterate `metrics`/`derived_metrics` dictionaries correctly, and skip non-company lists when building fallback company collections.
- Update chart fallback to iterate `.items()` and include the chart `type` metadata so results mirror the current YAML schema.
- Convert `FallbackConfig` into a dataclass (or implement an explicit `__init__`) so keyword overrides, timeouts, and `enable_*` flags work as intended. Update tests to cover the real YAML shapes instead of mocked-out lists.
- After repairs, rerun the ConfigStore test suite with the actual `CONFIGS` data loaded to ensure fallback stages produce real matches and that cache timestamps are validated without referencing stale objects.

## Validation Notes
- Existing tests in `backend/analytics_supervisor/test_config_store.py` focus on mocked services, so the broken YAML lookups are not exercised. Add fixtures that load `backend/config/schemas/*.yaml` to catch schema drift.
- End-to-end verification should stream through `/api/analytics/memory/supervisor/stream` with RAG and Supabase disabled to confirm YAML fallback now yields results instead of silent empties.