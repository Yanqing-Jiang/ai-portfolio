# Analytics Architecture Optimization Roadmap

## Alignment with Simple-Agent Philosophy
- Claude Code advocates a "simple agent, strong tools" pattern where the planner remains lightweight and downstream tooling carries complexity; modular flow steps let us honour that advice while keeping reasoning layers shallow (Claude Code blog, Sept 2024).
- Anthropic's orchestration guidance stresses composing reusable actions through small interfaces rather than monolithic DAGs, reinforcing the need to untangle `PlannerExecutorFlow` (Anthropic orchestration notes, Oct 2024).
- Community practitioners echo that maintaining a single, transparent planner with swap-in tool adapters keeps debugging manageable, mirroring our goal of consistent behaviours across all three flow modes (Claude developer forum thread, Feb 2025).

## Structural Improvements
1. **Pipeline Steps over God Objects**  
   Break `PlannerExecutorFlow` (~1,100 lines) into discrete `FlowStep` classes to avoid the shared mutable `PlannerPhaseContext` hot-spot (`backend/analytics/flows/planner_executor.py:120`, `backend/analytics/flows/planner_executor.py:563`). Steps such as classification, clarification, SQL, charting, and analysis can each emit events while updating a typed context, enabling re-ordering for experiments and simplified testing.
2. **Composable Event Middleware**  
   Convert `instrument_events` and `SingleAgentToolsFlow` overlays into reusable `AsyncEventMiddleware` so sequencing, telemetry, and tool envelopes stack declaratively (`backend/analytics/flows/instrumentation.py:17`, `backend/analytics/flows/single_agent_tools.py:13`). A middleware chain lets the three modes share the same base stream while opting into extra annotations.
3. **Responses-Oriented SQL Retry Loop**  
   Replace the inline YAML fallback with a `ResponsesSqlStrategy` that exclusively uses the Responses API. Each attempt calls `client.responses.create(...)` with the current error context, inspects structured tool outputs, and retries up to three times when validation or execution returns actionable error codes (for example `SQL_VALIDATION_FAILED`, empty result sets, or connection timeouts). The strategy surface should record attempt metadata, reasoning summaries, and final status so downstream flows can halt cleanly once the retry budget is exhausted.
4. **LLM Clarification Manager & Preflight Gate**  
   Collapse keyword heuristics and manual slot polling into an LLM-driven manager that runs immediately after session bootstrap. Both the off-topic classifier and clarification drafting must use `gpt-5-nano-2025-08-07` with low reasoning effort to keep responses fast. The manager emits one short decline when the model labels a query as non-financial, then guides users back toward supported analytics prompts before any mode-specific execution begins.
5. **Unified Tool & Agent Plugin Registry**  
   Merge `ToolTaskGroup` adapters with supervisor tools to avoid duplicating metadata and execution logic when we fan out adapters or spawn agent tasks (`backend/analytics/flows/tooling.py:577`, `backend/analytics/tools/registry.py:32`, `backend/analytics/flows/multi_agent.py:78`). A shared registry can surface descriptors, telemetry schemas, and executors to every mode.
6. **Explicit Config Providers & Types**  
   Replace direct `CONFIGS.__dict__` access with injected providers so tests or alternate environments can supply scoped configs without touching globals (`backend/analytics/flows/planner_executor.py:168`, `backend/analytics/core/config_store.py:53`). Tighten exports in `core/types.py` to explicit imports for clearer boundaries.

## Clarification-First Dispatch & Off-Topic Handling
- **LLM gate:** Every request runs through a lightweight Responses call to `gpt-5-nano-2025-08-07`, returning an `OffTopicClassifierSchema` payload plus proposed clarifications. The model decides whether the prompt is financial analysis or an in-scope follow-up; no heuristic keyword checks remain.
- **Polite decline baseline:** When the classifier reports `is_financial_query=False`, emit a single short message (for example, "I am here for financial analytics insights. Try asking about revenue trends or market share.") via `final_answer` and close the session without invoking downstream steps.
- **Clarification fan-out:** Once the manager gathers required slots (company, timeframe, etc.), broadcast the normalized intent, slots, and assumptions to planner, single-agent, and multi-agent flows so they execute against identical context.

## SQL Generation Strategy Reference
- YAML templates are fetched through `fetch_templates_for_intent(...)` so the Responses prompts see relevant patterns (`backend/analytics/flows/planner_executor.py:619-631`).
- `PlannerExecutorFlow` now uses the Responses API exclusively, retrying up to three times with `build_sql_retry_messages(...)` when validation errors or empty bodies surface (`backend/analytics/flows/planner_executor.py:635-765`).
- Each attempt records telemetry in `ctx.sql_attempts` and emits `sql_compiled`/`sql_generated` events, allowing dashboards to inspect retry behaviour without touching YAML fallbacks.
- Validation still runs through `validate_sql(...)`, but a failed pass now short-circuits the workflow with `SQL_VALIDATION_FINAL` instead of rehydrating templates (`backend/analytics/flows/planner_executor.py:792-821`).

## Responses API Reliability Notes
- Continue using the Python client `responses.create(...)` interface so we can attach reasoning summaries, background mode, and encrypted reasoning items as needed for longer analytical queries.
- Capture retry context (error code, SQL text hash, attempt count) in the telemetry payload so we can diagnose when the Responses API halted due to three failed retries versus upstream tool errors.
- Align retry policies with the Responses API background mode so multi-minute warehouse queries can run asynchronously without freezing the event stream.

## Cross-Mode Reuse Opportunities
- **Event Stream Core:** The base planner step pipeline should produce a canonical `AsyncIterator[Event]` that all modes consume; single- and multi-agent wrappers then add middleware (tool telemetry, agent envelopes) instead of reimplementing logic.
- **Clarification & Session APIs:** A shared `ClarificationManager` plus `SessionStateRepository` facade can expose identical contracts for retrieving cached SQL, chart specs, or tool payloads, enabling each mode to reuse cache hints without bespoke plumbing (`backend/analytics/core/session_state.py:70`).
- **Tool Plugin Interface:** Define `PluginDescriptor` and `PluginExecutor` abstractions so parallel tooling, supervisor tool calls, and agent DAGs all pull from the same inventory; reuse metadata (display name, outputs, capability tags) across modes.
- **Telemetry Emitters:** Centralize SSE schemas (progress, result, `tool_call`, `agent_turn`) via middleware helpers to guarantee consistent payload shapes across planner, single-agent, and multi-agent experiences (`backend/analytics/core/events.py:40`).

## Additional Research Takeaways
- Latest Responses API updates add background mode, reasoning summaries, and encrypted reasoning items, all of which map cleanly onto the retry loop and telemetry work we are planning for analytics flows.
- A dedicated `gpt-5-nano-2025-08-07` classification pass keeps the preflight lightweight while still allowing us to reuse structured outputs for clarifications, removing the need for bespoke keyword logic.

## Next Steps
1. Extract the new Responses retry loop into a dedicated `ResponsesSqlStrategy` object so planner, single-agent, and multi-agent flows can share telemetry helpers.
2. Stand up a `ClarificationManager` that caches `ctx.classification`, orchestrates follow-up questions, and exposes a shared API for other flows.
3. Extend regression tests to cover off-topic short replies and retry telemetry (`backend/tests/analytics/test_planner_policy.py`) once the upstream TODOs unblock existing failures.
