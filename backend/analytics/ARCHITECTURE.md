# Analytics Architecture (Agentic Refactor) — October 2025

This document describes how we will evolve the existing analytics service to support autonomous single-agent and supervisor-led multi-agent workflows while reusing the current Python modules under `backend/analytics`. We focus on upgrading the orchestration logic, concurrency model, and telemetry contracts without introducing greenfield frameworks or speculative fallbacks.

## 1. Context & Constraints
- **Reuse before rebuild:** We extend `PlannerExecutorFlow`, `SingleAgentController`, `MultiAgentFlow`, and `AgentExecutionOrchestrator` rather than replacing them outright. Controllers wrap these modules to add policy-driven behavior.
- **No fallbacks:** Every flow must complete with the agentic path; we will not maintain the legacy sequential pipeline as a runtime fallback.
- **Legacy cleanup:** As controllers land, we delete obsolete wrappers (the former `SingleAgentToolsFlow`), redundant helper functions in `multi_agent.py` that only echoed planner state, and refactor the `flows/instrumentation.py` stubs so agent controllers own telemetry emission without duplicate decorators.
- **Shared artifacts:** SQL text, chart specs, stock widgets, and web snippets remain in `SessionStateSnapshot` to support revisions and cross-flow continuity.

## 2. Existing Components We Keep
| Component | Reuse Plan |
|-----------|------------|
| `planner_executor.PlannerExecutorFlow` | Becomes the “SQL chain” tool: intent → plan → generate → validate → execute → chart. Returns structured receipts for agent decisions. |
| `pipeline_tools.PlannerToolRegistry` | Houses callable tools. We promote each entry to an idempotent `ToolInvocation` that records hashes and outputs. |
| `multi_agent.AgentExecutionOrchestrator` | Continues to run DAGs, but accepts dynamic plans emitted by the supervisor agent. |
| `core.session_state.SessionStateSnapshot` | Stores tool receipts, agent summaries, and artifacts for reuse. |
| `tool_bundle.collect_tool_bundle` | Extended to tag specialist ownership, concurrency batches, and reasoning snippets. |

## 3. Refactor Themes
1. **Agent Controllers:** Replace passive wrappers with controllers that request tools, evaluate receipts, and emit telemetry.
2. **Deterministic Concurrency:** Run SQL, market research (two prompts), and stock chart generation concurrently where dependencies allow, using `asyncio.TaskGroup`.
3. **Single Analysis Card:** Synthesize SQL, web, and stock insights into one Financial Analysis message per session.
4. **Agent Reasoning Telemetry:** Stream reasoning and decision traces into an “Agent Thinking” panel for both flows.
5. **Autonomy with Guardrails:** Agents stop retrying a failing tool after two attempts, mark it as failed, continue the workflow, and surface the failure reason to the UI.

## 4. Single-Agent Controller

### 4.1 Responsibilities
- Wrap the legacy `SingleAgentToolsFlow` entrypoint with a new `SingleAgentController` that:
  - Runs the financial qualifier (`classify_query_async`) first.
  - Builds a decision loop prompt that understands the available tools and their receipts (inspired by Claude code agents’ explicit tool catalogs and success criteria).citeturn1search1
  - Issues structured tool batches over SSE.

### 4.2 Tool Catalogue
- **SQL Chain (`sql.chain`)** → delegates to `PlannerExecutorFlow`.
- **Market Research (`market.snapshot`, `market.followup`)** → two prompts generated dynamically from the user query (e.g., “What catalysts impact {ticker}?”, “What risk signals appear in the past quarter?”) so both can run concurrently per session.
- **Stock Chart (`stock.chart`)** → uses existing chart builder but is registered as a tool returning ECharts specs.
- **Web Research (`web.search`)** → reuses `perform_response_search` with caching receipts.

All tools populate `ToolInvocationReceipt` objects containing input hash, output digest, attempt count, latency, and `reused` flag.

### 4.3 Concurrency Model
- During each decision loop the controller:
  1. Launches the SQL chain task group.
  2. Launches `market.snapshot` and `market.followup` concurrently.
  3. Launches `stock.chart` once SQL execution emits `sql_ready` (dependency barrier).
  4. Allows `web.search` to start immediately; it will reuse cached snippets if the hash matches.
- Progress events (`tool_batch_start`, `tool_result`) include `batch_id`, `concurrency_level`, and the tool names for ProcessPanel.

### 4.4 Analysis Synthesis
- Introduce `analysis_builder.compose_financial_card(sql, web, stock)` that requires non-null contributions from all three artifacts before emitting the single Financial Analysis card. This card replaces the prior planner narrative events.
- The controller emits `analysis_ready` once, with references to artifact IDs and a `source: "single_agent_controller"` tag.

### 4.5 Revision Flow
- On follow-up queries the controller receives snapshot receipts:
  - If the agent detects schema-changing deltas, it invalidates the SQL chain receipt and re-runs the full tool.
  - If the request targets chart updates only, the controller reruns `stock.chart` and `sql.chain.chart_step` (a new partial entrypoint) while reusing SQL execution results.
  - Market/web tools rerun only when their input hash changes or receipts are stale (>10 minutes).

### 4.6 Failure Handling
- Each tool accrues `attempts`. After two failed attempts the agent logs `tool_failed` and continues with available data, mirroring resilience advice from multi-agent production systems.citeturn1search0turn1search3
- Failed tools contribute warnings inside the Financial Analysis card and appear in the telemetry stream.

### 4.7 Telemetry
- New events: `agent_decision`, `agent_reasoning_fragment`, `tool_batch_start`, `tool_batch_complete`, `tool_failed`.
- Reasoning fragments stream to the Agent Thinking panel with structured JSON containing `decision`, `rationale`, `evidence`, and `next_actions`.

## 5. Multi-Agent Supervisor Flow

### 5.1 Supervisor Agent
- Replace the fixed `_base_plan` with a supervisor LLM that emits a DAG of specialist tasks, following industry best practice of supervisors delegating explicit tools.citeturn1search2turn1search3
- Supervisor responsibilities:
  - Confirm `intent_liaison` has satisfied slot requirements.
  - Generate market follow-up prompts dynamically per query.
  - Schedule SQL, market, stock, and web specialists concurrently (sequence 1→4, with the three “1” specialists allowed to run in parallel).
  - Monitor receipts and mark tools as failed after two retries.
  - Decide which specialists to rerun during revisions, ensuring chart reruns go through the SQL chart path.

### 5.2 Specialist Lifecycle
1. **intent_liaison (LLM)** — clarifies slots; writes to shared context.
2. **SQL chain** — uses `PlannerExecutorFlow` entrypoints (`intent`, `plan`, `generate`, `validate`, `execute`, `chart`) and returns SQL text, columns, row samples, and chart spec.
3. **viz_designer (LLM)** — consumes SQL output and builds/patches charts; only fires after SQL chain finishes.
4. **market_agent (deterministic + optional commentary)** — issues two concurrent prompts, stores TradingView widgets, and marks them with `question_id`.
5. **web_research_agent (LLM)** — fetches snippets, deduplicates providers.
6. **insight_reviewer (LLM)** — composes the final consolidated Financial Analysis message pulled from SQL/web/stock artifacts.

Specialist outputs surface as individual cards before the supervisor summary:
- Generated SQL card (SQL chain).
- SQL Chart card (viz_designer).
- Stock Chart card (market_agent with chart context).
- Web Research card (web_research_agent).

### 5.3 Deduplication & Receipts
- Supervisor tracks `executed_tools` by `(tool_name, input_hash)`. If a duplicate is requested, it emits a `tool_reused` event instead of re-running.
- `market_agent` and `web_research_agent` share the receipt store with the single-agent flow to avoid duplicate HTTP calls.

### 5.4 Concurrency & Sequencing
- DAG constraints ensure:
  - `intent_liaison` runs first.
  - `sql_chain` starts immediately afterward.
  - `market_agent` (two tasks), `web_research_agent`, and `stock_chart` (viz + market) launch as soon as SQL emits `sql_ready`.
  - `insight_reviewer` waits on SQL, market, web, and viz results before composing the cohesive result.
- The orchestrator logs concurrency batches and latency metrics for each specialist.

### 5.5 Reasoning Telemetry
- Supervisor emits `agent_turn:start` / `agent_turn:complete` events with reasoning summaries.
- Reasoning snippets are streamed via `agent_reasoning_fragment` and surfaced in the Agent Thinking panel, aligning with modern observability practices for multi-agent systems.citeturn1search0turn1search2

### 5.6 Cohesive Result
- Supervisor emits one sanitized `cohesive_result` containing:
  - Final analysis (with SQL, web, stock citations).
  - SQL artifact references (text, row count, sample rows).
  - Stock widget configuration.
  - Web snippet summary.
- Financial Analysis card reuses this payload to stay in sync with single-agent mode.

## 6. Legacy Code Removal
- **Delete the legacy `SingleAgentToolsFlow`** once the controller is fully integrated; update imports in `analytics.flows.workflow` and tests.
- **Remove redundant artifact queue helpers** in `multi_agent.py` that simply mirror planner state, replacing them with receipt lookups.
- **Inline instrumentation logic** currently in `flows/instrumentation.py` into the new controllers, then remove the legacy decorators once parity tests pass.
- **Prune unused docs** replaced by this architecture file (`docs/analytics-*-plan-2025-10-14.md`), keeping history in git but not shipping stale content.

## 7. Testing & Observability
- **Unit Tests**
  - `test_single_agent_controller.py`: decision loop, concurrency fan-out, failure thresholds.
  - `test_multi_agent_supervisor.py`: DAG parsing, dedupe, revision routing, reasoning events.
  - `test_tool_receipts.py`: hashing, reuse, expiry logic.
- **Integration Tests**
  - Existing SQL planner tests updated to expect concurrent event ordering.
  - Multi-agent goldens extended to verify specialist cards arrive before cohesive result.
  - Revision routing tests assert targeted reruns and avoided duplicates.
- **Frontend Tests**
  - Update ProcessPanel and WorkflowCanvas tests to handle new telemetry.
  - Ensure Financial Analysis card renders once with combined data.
- **Monitoring**
  - Expand `analytics.core.telemetry` to log agent decisions, failed tools, and reasoning fragments.

## 8. Open Questions (Resolved)
1. **Autonomy & Failure Policy:** Agents stop attempting a tool after two failures, mark it failed, continue processing, and surface the error in both telemetry and the final analysis card. No workflow aborts the session.
2. **Market Prompts:** The supervisor/controller crafts two market prompts per query using templated question families (catalysts, risk signals) filled with context-specific details, and executes them concurrently to minimize latency.
3. **Reasoning Visibility:** Reasoning fragments from both the single agent and supervisor stream to the Agent Thinking panel via `agent_reasoning_fragment` events. Each fragment logs tool dependencies and evidence references for post-hoc debugging.

## 9. References
- Meta AI, “How we built our multi-agent research system,” June 13, 2025.citeturn1search0
- Anthropic Docs, “Agents and Tool Use — Best Practices,” October 2025.citeturn1search1
- Inspect.ai, “Inspect multi-agents: analyst, planner, router,” July 2025.citeturn1search3
- LangGraph, “Working with large tool catalogs in agent supervisors,” August 2025.citeturn1search2

---

## 10. Execution Plan & Progress
*(Updated October 15, 2025)*

### 10.1 Active Burst (No feature flags)
1. **Tool Receipts & Planner Refactor** — carve receipts into `PlannerExecutorFlow`, expose granular entrypoints, and ensure SQL + chart pipeline can be orchestrated externally.
2. **Single Agent Controller** — embed controller logic into `single_agent_tools.py`, retire `SingleAgentToolsFlow`, wire new telemetry, and preserve API compatibility for `analytics.flows.workflow`.
3. **Multi-Agent Supervisor Upgrade** — replace static `_base_plan` with LLM-driven DAG emission, upgrade specialists, and ensure concurrency requirements (SQL + market prompts + web + stock chart).
4. **Telemetry & Frontend Contracts** — update `tool_bundle`, event schemas (`agent_decision`, `agent_reasoning_fragment`), and confirm ProcessPanel/WorkflowCanvas fields align with existing `agent_turn`.
5. **Revision & Snapshot Logic** — persist and reuse tool receipts, enable targeted reruns, and guarantee chart reruns flow through SQL chart path.
6. **Cleanup & Tests** — delete deprecated docs/code, adjust test suites, and run targeted `pytest backend/tests/analytics` modules.

### 10.2 Progress Log
- **[Completed – Oct 15]** Tool receipts now persisted via `PlannerExecutorFlow`; SQL, chart, and analysis phases emit structured receipts and reused runs send `sql_ready`/`chart_ready` with reuse metadata.
- **[Pending]** Single agent controller embedded + telemetry ports.
- **[Pending]** Multi-agent supervisor DAG + specialist upgrades.
- **[Pending]** Telemetry / frontend contract updates.
- **[Pending]** Revision routing w/ agent decisions.
- **[Pending]** Targeted tests + cleanup.

*(Update this section as milestones complete.)*
