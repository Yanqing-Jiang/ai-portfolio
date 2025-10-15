# Agentic Workflow Refactor Plan  
_Prepared: October 15, 2025_

## 1. Objectives
- Evolve both the Single-Agent and Multi-Agent analytics flows from scripted pipelines into policy-driven agents that choose which tools and specialists to activate.
- Introduce concurrency for the three critical workstreams (SQL, stock/market, web research) while preventing duplicate executions and preserving deterministic telemetry.
- Ensure the final Financial Analysis card and the supervisor’s cohesive result blend SQL output, online research, and stock context exactly once across all modes.
- Preserve revision workflows by allowing agents (single or supervisor) to decide what must be recomputed, with chart reruns always tied to the SQL chart artifact.

## 2. Research Inputs
- Claude Code Agent guidance emphasizes explicit tool declarations, delegation hooks, and clear success criteria to keep LLM agents aligned and debuggable.[^1]
- Anthropic’s multi-agent patterns recommend a supervisor that maintains shared state, assigns roles, and enforces dependency-aware execution DAGs.[^2]
- High-concurrency tool orchestration needs deterministic logging, cancellation controls, and idempotent tool adapters to avoid repeated side effects.[^3]

## 3. Current Architecture Snapshot
- **SingleAgentController** (legacy `SingleAgentToolsFlow`) directly streams `PlannerExecutorFlow.events()`, adding only telemetry hooks; all tool invocations happen sequentially inside the planner pipeline.
- **MultiAgentFlow** also rides the planner pipeline first, then executes a static `_base_plan` via `AgentExecutionOrchestrator`; specialist functions are mostly deterministic summarizers.
- `PlannerExecutorFlow` emits SQL/chart/accessory events sequentially; accessory fan-out happens late, blocking analysis and hampering concurrency.
- Financial Analysis cards are duplicated when both planner and supervisor emit narrative artifacts; deduplication relies on ad-hoc metadata.

## 4. Proposed Architecture

### 4.1 Agent Control Surface
- Introduce an `AgentDecisionContext` (new module) exposing:
  - Snapshot-derived artifacts (SQL text, chart spec, stock widget, web snippets).
  - Tool registry manifest with metadata (latency, idempotency).
  - Telemetry sink for structured decisions.
- Wrap tools in idempotent call adaptors (`ToolInvocation` objects) that record execution receipts (hash of inputs, tool version, emitted events).

### 4.2 Single-Agent Workflow
1. **Controller Layer**  
   - Replace direct `PlannerExecutorFlow.events()` calls with `SingleAgentController` that:
     - Runs the financial qualifier (existing GPT-5 nano classifier).
     - Constructs a decision loop: supply context to an `analysis_agent` prompt that can request tool invocations (`sql.generate`, `sql.run`, `market.snapshot`, `web.search`).
     - Accepts structured tool calls via JSON schema; rejects unknown tools.
2. **Concurrent Tool Execution**  
   - For each decision batch, fan out allowed tools using `asyncio.TaskGroup` (Python 3.13) while enforcing:
     - SQL lane (intent → plan → generate → validate → execute → chart) runs as one grouped workflow, but the controller can initiate it while market/web tasks run concurrently.
     - Market research’s “two questions” become two distinct prompts (e.g., `market.snapshot` and `market.comparison`) executed concurrently, each writing separate artifacts.
     - Stock chart generation can trigger once SQL execution finishes, but controller may prefetch symbol metadata concurrently for faster chart hydration.
3. **Financial Analysis Card**  
   - Consolidate planner/supervisor outputs into a single `analysis.final` artifact built by the agent after all required data is present.
   - Enforce a merge routine that requires references to SQL highlights (e.g., top metrics), web bullet list, and stock summary before emitting.
4. **Revision Flow**  
   - Persist per-tool receipts in `SessionStateSnapshot`. On follow-up:
     - Agent receives diff summary (query delta, snapshot ages).
     - Agent decides which tool receipts to invalidate and re-run; ensure chart reruns always queue the SQL chart tool via explicit gating (`requires_chart_refresh` flag attached to SQL decisions).
5. **Telemetry**  
   - Emit `agent_decision`, `tool_batch_start`, and `tool_batch_complete` events with concurrency metadata.
   - Continue sending `sql_ready`, `chart_ready`, `stock_ready`, `web_ready` once per artifact, annotated with `reused`/`fresh`.

### 4.3 Multi-Agent Workflow
1. **Dynamic Supervisor**  
   - Replace static `_base_plan` with `SupervisorAgent` (LLM prompt) that outputs a DAG of tasks referencing registered specialists. Example JSON schema:
     ```json
     {
       "tasks": [
         {"name": "sql_phase", "agent": "sql_chain", "depends_on": []},
         {"name": "market_q1", "agent": "market_agent", "depends_on": ["sql_phase"]},
         {"name": "market_q2", "agent": "market_agent", "depends_on": ["sql_phase"]},
         {"name": "web_scan", "agent": "web_research_agent", "depends_on": ["sql_phase"]},
         {"name": "viz", "agent": "viz_designer", "depends_on": ["sql_phase"]},
         {"name": "insights", "agent": "insight_reviewer", "depends_on": ["sql_phase", "market_q1", "web_scan", "viz"]}
       ]
     }
     ```
   - Supervisor enforces concurrency by emitting parallel tasks for the two market questions and allowing stock chart/viz + web research alongside SQL execution as soon as dependencies allow.
2. **Specialist Upgrades**
   - **Intent Liaison**: runs before supervisor planning to supply missing slots; writes to shared context.
   - **SQL Chain**: wraps existing planner pipeline but exposes intermediate checkpoints so supervisor can re-run subsections (e.g., `sql.generate` again) without repeating the whole chain.
   - **viz_designer**: becomes LLM-driven, with capability to request a fresh SQL sample if the spec demands new dimensions; however, reruns must go through supervisor to avoid duplicate SQL.
   - **market_agent/web_research_agent**: convert to idempotent tool callers with cached receipts; allow up to two concurrent prompts for market.
   - **insight_reviewer**: assembles final cohesive result by reading merged artifact state (SQL highlights + web snippets + stock summary) and emits exactly one narrative card.
3. **Duplicate Prevention**
   - Supervisor maintains `executed_tools` map; before issuing a task, it checks for matching tool receipt hash. If present and still valid (fresh snapshot), emit `reused` events instead of re-running.
   - For follow-ups, supervisor can mark individual tasks as `needs_rerun`: e.g., chart update only triggers `viz_designer` (with `requires_sql_refresh` gate to ensure SQL chart).
4. **Specialist Event Emission**
   - Each specialist emits its own chat card before supervisor finalizes:
     - `Generated SQL` (SQL chain).
     - `SQL Chart` (viz).
     - `Stock Chart` (market agent).
     - `Web Research` (web agent).
   - Metadata includes timestamps, `source: specialist`, `reused` flag, and tool latency.
5. **Cohesive Result Contract**
   - Supervisor aggregates final payload with explicit fields for SQL/stock/web contributions and ensures Financial Analysis card is emitted once with references to the three data sources.
   - Guarantee sanitized output (no Decimal serialization issues) before streaming to the frontend.

### 4.4 Shared Infrastructure Updates
- Extend `SessionStateSnapshot` to store tool receipts (`tool_id`, `input_hash`, `output_digest`, `timestamp`).
- Modify `collect_tool_bundle` to include new specialist cards and concurrency metadata.
- Update frontend analytics components to:
  - Render single Financial Analysis card based on consolidated artifacts.
  - Display specialist cards with `source` tag and handle `reused` badges.
  - Show concurrent progress lanes (ProcessPanel + WorkflowCanvas) with new events.

## 5. Implementation Phases
1. **Scaffolding**
   - Introduce new agent controller modules; refactor Planner pipeline to expose tool entrypoints individually.
   - Add tool receipt schema and persistence.
2. **Single-Agent Refactor**
   - Implement decision loop, concurrency framework, financial card consolidation, and revision policy.
   - Backfill unit tests with mocked tool registry to validate decision-making.
3. **Multi-Agent Refactor**
   - Implement supervisor prompt, dynamic DAG execution, upgraded specialists, and dedup logic.
   - Add concurrency tests ensuring SQL, market, and web tasks can run in parallel without duplication.
4. **Telemetry & Frontend**
   - Update events, ProcessPanel ledger, WorkflowCanvas visual cues.
   - Adjust `ChartCard`, `WorkflowCanvas`, and new tests to assert single analysis card rendering.
5. **Stabilization**
   - Regression tests (`pytest backend/tests/analytics/...`), new agent-specific suites, and Playwright flows covering concurrency indicators.
   - Load testing with synthetic workloads to verify tool idempotency and cancellation handling.

## 6. Testing Strategy
- **Unit Tests**
  - `test_single_agent_controller.py`: decision loop, tool receipt caching, revision routing.
  - `test_multi_agent_supervisor.py`: DAG parsing, duplicate prevention, concurrency guards.
  - `test_tool_receipts.py`: persistence and reuse logic.
- **Integration Tests**
  - Update existing planner SQL tests to assert concurrency events (`tool_batch_start`).
  - Multi-agent golden trace ensuring specialist cards precede cohesive result.
- **Frontend Tests**
  - Extend `ChartCard.test.tsx` to cover reused vs fresh renders.
  - Add snapshot tests for ProcessPanel concurrency UI.
- **Manual QA**
  - Scenario scripts for follow-up queries exercising selective reruns.
  - Monitor backend logs for decision summaries and ensure no duplicate tool invocations.

## 7. Rollout Considerations
- Feature-flag new agent controllers per flow (`ANALYTICS_AGENTIC_SINGLE`, `ANALYTICS_AGENTIC_MULTI`).
- Dual-run mode: capture telemetry from both old and new controller without exposing to users until stability is verified.
- Backwards compatibility: ensure API contracts for `/api/analytics/memory/stream` remain intact; add new fields as optional.
- Documentation updates: revise `ARCHITECTURE.md`, analytics TODO, and frontend storybook docs for new cards/concurrency.

## 8. Open Questions
- What guardrails are needed if an agent’s decision loop stalls or produces contradictory tool requests?
- Should market “two questions” prompts be templated or synthesized dynamically per query?
- How to surface agent reasoning to users without overwhelming the chat stream?

## 9. References
[^1]: Anthropic, “How to implement tool use,” _Claude Docs_, October 2025. <https://docs.anthropic.com/en/docs/agents-and-tools/tool-use/implement-tool-use>  
[^2]: Anthropic Engineering, “How we built our multi-agent research system,” June 13, 2025. <https://www.anthropic.com/engineering/built-multi-agent-research-system>  
[^3]: Anthropic Engineering, “Writing effective tools for agents — with agents,” September 11, 2025. <https://www.anthropic.com/engineering/writing-tools-for-agents>

## 10. Execution Plan & Progress _(Updated October 15, 2025 @ 13:40 PT)_

### 10.1 Active Burst (no legacy fallback)
1. **Tool Receipts & Planner Refactor** — land structured receipts inside `PlannerExecutorFlow` (️done).
2. **Single Agent Controller** — replace legacy pass-through with agentic controller: decision loop, concurrent tool batches, unified Financial Analysis card.
3. **Multi-Agent Supervisor Upgrade** — emit dynamic DAG, orchestrate specialists (intent liaison → SQL chain → viz designer → market/web pair → insight reviewer) with de-duplication guarantees.
4. **Telemetry & Frontend Contracts** — extend `tool_bundle`, session state, and SSE payloads; update ProcessPanel / WorkflowCanvas to visualize concurrency + agent reasoning.
5. **Revision & Snapshot Logic** — persist tool receipts, target reruns, enforce SQL-driven chart refreshes.
6. **Tests & Cleanup** — targeted pytest modules, teardown stale docs/helpers once new flows stabilize.

### 10.2 Progress Log
- **[Completed – Oct 15]** Planner receipts persisted; SQL/chart/analysis emit `ToolInvocationReceipt`s, with reuse events (`sql_ready`, `chart_ready`) validated via `pytest backend/tests/analytics/test_planner_executor_sql.py`.
- **[In Progress – Oct 15]** Single agent controller rewrite: audited `single_agent_tools.py`, captured concurrency + telemetry deltas, outlined decision batches (classifier → concurrent SQL/market/web lanes → chart trigger → analysis merge).
- **[Pending]** Multi-agent supervisor DAG + specialist upgrades.
- **[Pending]** Telemetry / frontend contract updates.
- **[Pending]** Revision routing w/ agent decisions.
- **[Pending]** Targeted tests + cleanup.

### 10.3 Near-Term Execution Notes
- Implement `SingleAgentController.events()` loop to orchestrate:
  - Initial GPT-5 nano financial qualifier.
  - Batch 1 (`asyncio.TaskGroup`): SQL chain (intent→plan→sql→validate→execute), concurrently issue `market.question_a` & `market.question_b`, initiate web search if cache stale.
  - Gate stock chart refresh until SQL execution marks data ready; reruns limited to SQL chart path.
  - Emit `agent_decision`, `tool_batch_start/complete`, and reasoning fragments for telemetry panels.
- Build controller-level aggregation helper to emit a single Financial Analysis card combining SQL metrics, web snippets, and stock snapshot (enforce presence of all three sources; surface failure metadata on missing pieces).
- Hydrate tool receipts from `SessionStateSnapshot` on follow-ups so controller can selectively rerun SQL/chart while skipping cached stock/web artifacts (respect 2-attempt guardrail; mark failures but continue flow).
