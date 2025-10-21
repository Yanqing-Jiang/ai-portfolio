# Analytics Agent Thinking Canvases

This note documents the redesigned canvases that power the analytics thinking panel. It describes how the single-agent fan-out and multi-agent workflow views should evolve, how ledger fields (`sequence`, `parallelGroup`, `lane`) drive the layout, and the concrete steps required to ship the change.

## Redesign Objectives

- Explicitly gate the single-agent flow with intent discovery (`classification`, `intent_detection`, `clarification`) before tools fan out, matching how the ledger records those steps on 2025-10-18.
- Give SQL compilation/validation/execution its own lane that runs in parallel with the market research and charting spokes instead of being absorbed into the market lane.
- Rebuild the multi-agent canvas so it mirrors the supplied supervisor -> specialist fan-out pattern: a single start node, a supervisor hub, and vertical specialist lanes that own their downstream tools.
- Make concurrency obvious by letting shared `parallelGroup` values stack vertically inside a lane while still surfacing the supervisor's orchestration edges.

## Single-Agent Canvas Redesign

### Pre-Fan-Out Preparation

- Render a dedicated pre-processing cluster between `__start__` and the `Agent Hub`. The cluster must render the intent steps in ledger order: `classification` -> `intent_detection` -> `clarification` -> `schema_validation` (when present). Each node should use the existing `ProcessNode` chrome, but the connector is a single straight path rather than a full fan-out spoke.
- These nodes continue to source their metrics from `singleAgentFanout.telemetry`, but they should suppress branch counters so the header's concurrency module only starts counting once the hub is reached.

### Fan-Out and Lanes

- After the preparation cluster, resume the hub-and-spoke fan-out. Each spoke should align to a named lane so that concurrent work is visually separated:
  - **SQL Lane** - `sql_compilation` -> `sql_validation` -> `sql_execution`; keep them chained so users can see the hand-off but render them in a vertical column to emphasize they are running alongside, not within, the market lane.
  - **Market Lane** - `tool_execution` (market data pull) and `market_agent`, sharing `parallelGroup: specialist_fanout`.
  - **Chart Lane** - `chart_generation`, downstream from SQL results but still positioned as its own spoke so users can tell when charting lags behind SQL.
  - **Web Lane** - `web_research_agent` or any other auxiliary tool assigned that lane by `inferHubLane`.
- The aggregator on the far side still collapses into `analysis_generation` -> `follow_up_route`, but it should draw from each lane so the closing edge demonstrates the merge.

### Flow Sketch

```
User Request
    |
Pre-Processing Cluster
    |- classification
    |- intent_detection
    '- clarification
    |
Agent Hub (fan-out)
    |- SQL Lane:
    |      sql_compilation -> sql_validation -> sql_execution
    |- Market Lane:
    |      tool_execution -> market_agent
    |- Chart Lane:
    |      chart_generation
    '- Web Lane:
           web_research_agent
            |
Downstream Merge
    analysis_generation -> follow_up_route
```

This sketch mirrors `docs/agent-process-ledger (54).json` at 2025-10-18 02:07 UTC, where the SQL and market tasks shared `parallelGroup: specialist_fanout` yet progressed independently.

## Multi-Agent Canvas Redesign

### Start + Hub Pattern

- Reintroduce the single start node (`__start__`) so every multi-agent run visually begins the same way as the single-agent canvas. Connect it to a supervisor hub node (current `agent_coordination`) that mirrors the "Supervisor" box from the reference image.
- Use solid edges for active routes and dashed edges for speculative routes (cached, queued, or retries) to echo the solid/dashed arrows shown in the diagram.

### Specialist Lanes

- Dedicate a vertical lane per specialist: planner, market, web, SQL, chart, and any additional roles. Each lane opens with the agent node (`planner_agent`, `market_agent`, etc.) and continues straight down with any tools the specialist invoked.
- When a tool step includes `lane`, place it directly under its agent; when the ledger only logs `parallelGroup`, infer the lane by prefix (for example, `sql_` -> SQL lane). Tools should indent slightly so operators can read the lane as a stack owned by that specialist.
- Allow simultaneous steps with identical `parallelGroup` values to occupy the same horizontal band inside the lane, making concurrent execution obvious without overlapping edges.

### Flow Sketch

```
User
  |
Supervisor Hub (agent_coordination)
  |
  +-- Planner Lane
  |     planner_agent
  |     plan_and_select_template
  |
  +-- Market Lane
  |     market_agent
  |     tool_execution
  |
  +-- Web Lane
  |     web_research_agent
  |
  +-- SQL Lane
  |     sql_compilation
  |     sql_validation
  |     sql_execution
  |
  \-- Chart Lane
        chart_generation

Final Response (analysis_generation -> follow_up_route)
```

The supervisor routes requests down to each lane and receives results back up the central column, matching the Supervisor -> Agent structure from the provided PNG while using the telemetry-friendly lane metadata.

### Multi-Agent Step Reference (2025-10-20 run)

The screenshot in `docs/multi-agent canvas.png` captures the ledger exported on 2025-10-20 20:56 UTC (`docs/agent-process-ledger (99).json`). The table below explains what happens behind each canvas node, pointing to the backend modules that produce the events.

| # | Step id (canvas label) | What happens behind the node |
| --- | --- | --- |
| 1 | `initializing` ("initializing") | `analytics_memory_workflow` emits a `status` payload with `step="initializing"` to tag the run with the selected flow, session id, and phase metadata before any flow-specific work starts (`backend/analytics/flows/workflow.py`). |
| 2 | `classification` ("classification") | `PlannerExecutorFlow._classification_phase` calls `classify_query_async` to label the query, record model/confidence, and persist the classification artifact before downstream specialists engage (`backend/analytics/flows/planner_executor.py`). |
| 3 | `schema_clarifier` ("schema_clarifier") | The same phase threads through `decide_schema_clarification`, deciding whether extra slots are required and logging the requested fields or missing data for later clarification (`backend/analytics/flows/planner_executor.py`). |
| 4 | `clarification` ("Requirements Clarification") | `_clarification_phase` polls `wait_for_answer_blocking`, issues `clarification_request` events, and merges the user's answers back into the slot ledger until requirements are satisfied or time out (`backend/analytics/flows/planner_executor.py`). |
| 5 | `schema_validation` ("Schema & Criteria Validation") | Once slots stabilize, `intent_to_sql_criteria` normalizes company, timeframe, granularity, tickers, and metrics into a deterministic `SqlCriteriaModel`, which emits the `criteria_ready` event the canvas shows for this node (`backend/analytics/core/intent_impl/models.py`). |
| 6 | `intent_detection` ("Intent Detection") | `_intent_phase` resolves the intent key, builds the provisional query plan, updates slot status metadata, and decides whether clarifications or schema checks are still needed (`backend/analytics/flows/planner_executor.py`). |
| 7 | `market_lane` ("Market Data") | Hedged accessory receipts (`market_question_*`, `stock_tracker`) flow through `_derive_accessory_events`, which synthesizes `stock_ready` data, stock widgets, and snapshot provenance for the market lane (`backend/analytics/flows/planner_executor.py`). |
| 8 | `tool_execution` ("Agent Tool Execution") | The stock tracker portion of that fan-out produces a `tool_parallel_result` with the rendered widget, so the canvas pins a dedicated node showing the accessory execution state (`backend/analytics/flows/planner_executor.py`). |
| 9 | `web_lane` ("Web Research") | `_derive_accessory_events` and `_web_research_agent` combine cached or freshly fetched Gemini results (summary, snippets, search ids) and mark the lane as ready once the web retriever finishes (`backend/analytics/flows/planner_executor.py`, `backend/analytics/flows/multi_agent.py`). |
| 10 | `sql_compilation` ("SQL Compilation") | The SQL stage iterates up to three Responses API attempts, logging generation progress, validation verdicts, template ids, and selected catalog entries before emitting `sql_compiled` / `sql_generated` (`backend/analytics/flows/planner_executor.py`). |
| 11 | `sql_validation` ("SQL Validation") | Each candidate query runs through `_validate_sql`, which enforces guardrails (disallowing risky constructs, ensuring LIMIT clauses) and records issue lists and elapsed timings for this node (`backend/analytics/flows/planner_executor.py`). |
| 12 | `sql_lane` ("SQL Lane") | Instrumentation folds compile, validation, and execution artifacts into a single lane record that carries the accepted SQL text, attempt counters, sample rows, and column summaries (`backend/analytics/flows/planner_executor.py`). |
| 13 | `sql_execution` ("Data Retrieval") | After `execute_sql` returns, `_set_sql_execution_artifact` snapshots the dataset, emits `execution_stats` and `data_retrieved`, and stamps the lane with row counts and preview data (`backend/analytics/flows/planner_executor.py`). |
| 14 | `chart_generation` ("Chart Generation") | The chart specialist looks at planner tasks and SQL artifacts, then `_chart_agent` reports the chart spec id, chart type, and series count once the visualization pipeline locks (`backend/analytics/flows/multi_agent.py`). |
| 15 | `planner_agent` ("Planner Agent Lane") | `_planner_agent` rebuilds the multi-agent task DAG, packages a planner bundle (tasks, manifest, tool results), and posts planner hand-off telemetry before downstream specialists run (`backend/analytics/flows/multi_agent.py`). |
| 16 | `market_agent` ("Market Insights") | `_market_agent` decides whether to reuse cached market snapshots, trigger fresh Polygon fetches, or skip retries based on planner confidence, then surfaces tickers, insights, and policy decisions in its output (`backend/analytics/flows/multi_agent.py`). |
| 17 | `web_research_agent` ("Web Insights") | `_web_research_agent` optionally reuses session cache, otherwise invokes the web retriever, collecting attempts, summaries, and snippet payloads while respecting hedge gating for accessories (`backend/analytics/flows/multi_agent.py`). |
| 18 | `agent_coordination` ("Agent Coordination") | `AgentExecutionOrchestrator.run` fans tasks to registered specialists; `MultiAgentFlow` converts `agent_turn` and `agent_reasoning` callbacks into supervisor status updates that the canvas groups under this hub (`backend/analytics/flows/multi_agent.py`, `backend/analytics/flows/orchestrator.py`). |
| 19 | `tool_fanout` ("Tool Fan-Out Telemetry") | The planner's accessory strategy launches hedged tools (two market prompts, stock tracker, web retriever) with a concurrency cap, logging start/completion, hedging metadata, and tool receipts for the fan-out node (`backend/analytics/flows/planner_executor.py`). |
| 20 | `analysis_generation` ("Final Analysis") | The analysis stage streams text from `stream_insights_llm`, accumulates TLDR bullets, key numbers, risk watch items, and bundles accessory evidence before emitting `analysis_complete` and the final analysis artifact (`backend/analytics/flows/planner_executor.py`). |
| 21 | `follow_up_route` ("Follow-Up Guidance") | `analytics_memory_workflow` classifies the follow-up route up front, and the analysis phase refreshes it with the banner config that tells the UI whether to reuse, retry, or run the full pipeline (`backend/analytics/flows/workflow.py`, `backend/analytics/flows/planner_executor.py`). |
| 22 | `plan_and_select_template` ("Query Planning & Template Selection") | After clarifications, the planner builds the structured query plan, emits `plan_built`, logs the chosen template (or fallback), and records candidate catalog entries for reuse (`backend/analytics/flows/planner_executor.py`). |



## Multi-Agent Canvas Update Plan (2025-10-20 Run)

1. **Adopt the shared start + hub spine**
   - In `components/analytics/visualization/WorkflowCanvas.tsx`, replace the synthetic `user_entry` / `final_response` nodes that are injected inside the `setNodes` effect with the same `ProcessStep` shape the single-agent canvas uses for `fanout_start` (label `__start__`). Feed that start node directly into `agent_coordination` so multi-agent runs begin with the same glyph.
   - Adjust the edge builder to route `fanout_start -> agent_coordination -> analysis_generation -> follow_up_route`, matching the supervisor spine in the grouped-steps doc and removing the extra loop back to the pseudo "User Question" node.
2. **Cluster planner and intent preparation steps**
   - While mapping `processedSteps`, bucket planner-intent steps (`initializing`, `classification`, `schema_clarifier`, `clarification`, `schema_validation`, `plan_and_select_template`) into a dedicated planner band that sits immediately beneath `planner_agent`. Swap the simple `laneCounts[resolvedLane]++` increment for a keyed structure such as `laneBands['planner:intent_prep']` so these steps line up on a shared Y origin instead of stair-stepping.
   - When replaying the 2025-10-20 ledger, `classification`, `intent_detection`, and `plan_and_select_template` should appear on the same horizontal band to reflect their shared `parallelGroup`.
3. **Normalize specialist lane concurrency**
   - Refine the lane stacking logic by indexing counts with both lane and `parallelGroup` (for example, `const bandKey = `${resolvedLane}:${step.parallelGroup ?? step.id}``). Cache the Y-offset per `bandKey` so hedged steps like `market_lane`, `tool_execution`, and `web_lane` align horizontally whenever they share `parallelGroup: specialist_fanout`.
   - Ensure the SQL chain (`sql_compilation`, `sql_validation`, `sql_lane`, `sql_execution`) reuses a single band when `parallelGroup === 'sql_pipeline'`, and draw a subtle dependency edge from the SQL lane's terminal node into `chart_generation` to mirror the grouped diagram.
4. **Surface fan-out telemetry and speculative edges**
   - Anchor `tool_fanout` in the dedicated `fanout` lane by giving it an explicit base position and connecting it to both the hub and each specialist lane. Reuse `buildReusedEdgeTooltip` for cache hits, and introduce an `isSpeculativeStep(step)` guard that returns `true` when `step.status === 'queued'` or `step.details?.hedged === true`; render those hub edges with a dashed stroke so speculative routes match the grouped-steps guidance.
   - Label the winning branch via the existing telemetry fields on `tool_fanout`, so operators can see which hedged branch delivered the final data without opening the ledger.
5. **Re-center the analysis return lane**
   - Treat `analysis_generation` and `follow_up_route` as first-class nodes inside the `analysis` lane instead of the pseudo `final_response`. After each specialist lane feeds back into `agent_coordination`, emit a solid edge from the hub into `analysis_generation`, then link into `follow_up_route` to show the final synthesis path that the grouped steps call out.
6. **Regression fixtures**
   - Capture the grouped-steps ledger (`docs/agent-process-ledger (99).json`) in a Storybook story or Jest snapshot so the refactored layout can be regression-tested. Add a second fixture that omits `schema_validation` to confirm the planner band degrades gracefully.