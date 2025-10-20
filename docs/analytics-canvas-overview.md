# Analytics Agent Thinking Canvases

This note documents the redesigned canvases that power the analytics thinking panel. It describes how the single-agent fan-out and multi-agent workflow views should evolve, how ledger fields (`sequence`, `parallelGroup`, `lane`) drive the layout, and the concrete steps required to ship the change.

## Redesign Objectives

- Explicitly gate the single-agent flow with intent discovery (`classification`, `intent_detection`, `clarification`) before tools fan out, matching how the ledger records those steps on 2025-10-18.
- Give SQL compilation/validation/execution its own lane that runs in parallel with the market research and charting spokes instead of being absorbed into the market lane.
- Rebuild the multi-agent canvas so it mirrors the supplied supervisor → specialist fan-out pattern: a single start node, a supervisor hub, and vertical specialist lanes that own their downstream tools.
- Make concurrency obvious by letting shared `parallelGroup` values stack vertically inside a lane while still surfacing the supervisor’s orchestration edges.

## Single-Agent Canvas Redesign

### Pre-Fan-Out Preparation

- Render a dedicated pre-processing cluster between `__start__` and the `Agent Hub`. The cluster must render the intent steps in ledger order: `classification` → `intent_detection` → `clarification` → `schema_validation` (when present). Each node should use the existing `ProcessNode` chrome, but the connector is a single straight path rather than a full fan-out spoke.
- These nodes continue to source their metrics from `singleAgentFanout.telemetry`, but they should suppress branch counters so the header’s concurrency module only starts counting once the hub is reached.

### Fan-Out and Lanes

- After the preparation cluster, resume the hub-and-spoke fan-out. Each spoke should align to a named lane so that concurrent work is visually separated:
  - **SQL Lane** – `sql_compilation` → `sql_validation` → `sql_execution`; keep them chained so users can see the hand-off but render them in a vertical column to emphasize they are running alongside, not within, the market lane.
  - **Market Lane** – `tool_execution` (market data pull) and `market_agent`, sharing `parallelGroup: specialist_fanout`.
  - **Chart Lane** – `chart_generation`, downstream from SQL results but still positioned as its own spoke so users can tell when charting lags behind SQL.
  - **Web Lane** – `web_research_agent` or any other auxiliary tool assigned that lane by `inferHubLane`.
- The aggregator on the far side still collapses into `analysis_generation` → `follow_up_route`, but it should draw from each lane so the closing edge demonstrates the merge.

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

- Reintroduce the single start node (`__start__`) so every multi-agent run visually begins the same way as the single-agent canvas. Connect it to a supervisor hub node (current `agent_coordination`) that mirrors the “Supervisor” box from the reference image.
- Use solid edges for active routes and dashed edges for speculative routes (cached, queued, or retries) to echo the solid/dashed arrows shown in the diagram.

### Specialist Lanes

- Dedicate a vertical lane per specialist: planner, market, web, SQL, chart, and any additional roles. Each lane opens with the agent node (`planner_agent`, `market_agent`, etc.) and continues straight down with any tools the specialist invoked.
- When a tool step includes `lane`, place it directly under its agent; when the ledger only logs `parallelGroup`, infer the lane by prefix (for example, `sql_` → SQL lane). Tools should indent slightly so operators can read the lane as a stack owned by that specialist.
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

The supervisor routes requests down to each lane and receives results back up the central column, matching the Supervisor → Agent structure from the provided PNG while using the telemetry-friendly lane metadata.

## Implementation Plan

1. **Single-agent pre-processing cluster**
   - Update `SingleAgentFanoutCanvas` to split `buildNodes()` into `buildPreFanoutNodes()` and `buildBranchNodes()`. Use `['classification','intent_detection','clarification','schema_validation']` as the ordered template and skip missing entries gracefully (example: if the ledger only emits `classification` and `intent_detection`, the builder renders those two nodes and links directly to the hub).
   - Adjust `buildEdges()` so these nodes connect linearly (`__start__` → pre-processing chain → `Agent Hub`) before the hub fans out to branches.
2. **SQL lane extraction**
   - Extend the single-agent lane metadata (`SINGLE_AGENT_LANES` in `components/analytics/visualization/constants.ts`) with an explicit `sql` lane definition (x-position, badge color). Ensure `sql_compilation`, `sql_validation`, and `sql_execution` map to that lane even though their `parallelGroup` is `specialist_core`.
   - Update branch tool rendering so SQL nodes stay in their column while still showing dependency on market data when present (use an adjacency edge with a subtle dotted style between `sql_execution` and `chart_generation`).
3. **Multi-agent start + hub alignment**
   - Inside `WorkflowCanvas`, always prepend a synthetic `__start__` node when `flowMode !== 'single-agent'`. Reuse the start glyph from `SingleAgentFanoutCanvas` to keep styling consistent.
   - Promote `agent_coordination` to a distinguished hub node: bump its size, and route all supervisor edges through it so the fan-out visually matches the reference image.
4. **Lane stacking rules**
   - Refine `LANE_ORDER` and `LANE_BASE_POSITIONS` so each specialist gets a fixed x-offset. Ensure SQL, market, web, planner, chart, and analysis lanes align with the ASCII sketches. For example, map `sql_*` ids and `parallelGroup: specialist_core` to the SQL lane, while `analysis_generation` and `follow_up_route` return to the analysis lane beneath the hub.
   - Update `inferLaneFromStep` to check `step.id.startsWith('sql_')` before falling back to `parallelGroup`, guaranteeing the new SQL column gets populated even if future telemetry omits the `lane` field.
5. **Edge semantics and concurrency cues**
   - Extend the edge builder to emit dashed edges for speculative routes (`status === 'queued'` or `cached === true`) so the canvas mirrors the dashed “route” arrows from the user-provided diagram.
   - When multiple steps share a `parallelGroup` and `allows_parallel === true`, place them on the same y-level within the lane and offset them horizontally just enough to avoid overlap; reuse the existing `spreadParallelChildren` helper where possible.
6. **Verification**
   - Replay `docs/agent-process-ledger (54).json` through a Storybook story or unit snapshot (`components/analytics/__tests__/WorkflowCanvas.test.tsx`) to confirm: (a) pre-processing nodes gate single-agent fan-out, (b) SQL appears as its own lane, and (c) the multi-agent hub/lane layout matches the new pattern.
   - Add a regression fixture for a single-agent run missing `schema_validation` to prove the pre-processing cluster degrades cleanly.

## Example Ledger Mapping (2025-10-18)

The ledger file `docs/agent-process-ledger (54).json` demonstrates the intended staging:

- **02:07:14.895Z** – `classification` (no lane), `intent_detection` (`parallelGroup: specialist_core`), and `clarification` complete before any fan-out branches start.
- **02:07:34.181Z** – `tool_execution` (market lane) begins while SQL steps (`sql_compilation`, `sql_validation`, `sql_execution`) execute concurrently in the SQL lane. The shared `parallelGroup: specialist_fanout` confirms they are part of the same orchestrated stage even though they occupy different lanes.
- **02:07:35.006Z** – `chart_generation` consumes the SQL output; it remains in the chart lane to emphasize downstream visualization work.
- **02:07:50.312Z** – `agent_coordination` fires, drawing results from planner, market, web, and SQL lanes before the analysis lane (`analysis_generation`, `follow_up_route`) emits the final response.

## Telemetry Field Reference

- **`sequence`** – Monotonically increasing counter that we sort on first. Higher ranges (for example, `planner_agent.sequence = 839`) indicate category-specific allocation blocks; sort descending to maintain the emitted order when timestamps tie.
- **`parallelGroup`** – Names the orchestrated stage. When that stage advertises `allows_parallel: true`, steps with the same `parallelGroup` constitute a concurrent run. The canvas stacks them vertically inside the lane so their simultaneity is obvious.
- **`lane`** – Visualization hint that overrides or complements `parallelGroup`. The redesign prefers explicit lanes (SQL, market, web, chart, planner, analysis). If a step lacks `lane`, the renderer infers one from the id (`sql_`, `planner_`, `market_`) or falls back to the `parallelGroup` mapping.

## Post-Redesign Differences

- **Single-agent clarity** – Intent discovery is visually isolated ahead of the hub so operators know the fan-out only contains tools. SQL work streams run beside, not inside, market analysis, revealing true concurrency.
- **Multi-agent parity** – Both canvases now share the start → hub → lanes grammar, making it easier to jump between modes while still reflecting the Supervisor → specialist routing pattern from the design reference.
- **Concurrency cues** – Lanes and dashed edges tie directly back to `parallelGroup` semantics, so “concurrent run” means “same `parallelGroup` in an `allows_parallel` stage” and is rendered as stacked nodes within a lane, not as overlapping branches.

## 2025-10-18 Implementation Notes

- Multi-agent workflow nodes now resolve to dedicated lanes (`planner`, `sql`, `market`, `web`, `chart`, `analysis`) underneath a single supervisor hub. The start node feeds `agent_coordination`, which in turn fans tasks into the vertical specialist stacks so the canvas mirrors the Untitled.png reference.
- The insight ledger now normalizes `analysis_sources` before rendering and surfaces a “Data Inputs” block per step, preventing expansion crashes like the 2025-10-18 direct workflow replay (`agent-process-ledger (62).json`) and exposing lane/row metadata inline.
- Memory mode mounts the `LiveArtifacts` panel directly under the chat transcript so SQL tables, chart previews, stock snapshots, and web cards stream in as soon as readiness events arrive (and persist after completion).
- Status updates pin to the latest user turn when awaiting clarifications, then migrate underneath the newest assistant/result bubble once tool cards start rendering; the loading indicator remains a single `result` message rather than spawning extra assistant replies.
- Metric and timeframe clarifications flow through normalized payloads: `normalize_timeframe` tracks the `source`, slot statuses remain `missing` until the user responds, and the SQL planner/templates honour the curated metric list through the `{primary_metric}` placeholder.
- Added `backend/tests/analytics/test_timeframe_normalization.py` to guard the new timeframe semantics.

## Updated Integration Plan (2025-10-18)

The redesign is live; the remaining work focuses on regression coverage and snapshot parity.

1. **Front-end regression snapshots**  
   Capture Vitest snapshots for single-agent and multi-agent canvases (with and without `schema_validation`) so future layout tweaks keep the lane grammar intact.  
   _Files_: `components/analytics/__tests__/WorkflowCanvas.test.tsx`
2. **Ledger-level SQL/chart verification**  
   Extend the multi-agent pytest fixture to assert that `{primary_metric}` substitutions still populate `rawData` for revenue-growth and peer-comparison charts.  
   _Files_: `backend/tests/analytics/test_multi_agent_flow.py`
3. **Live artifacts polish**  
   Add a Vitest story/render test that exercises the merged status bubble + streaming result rendering to prevent regressions in the chat transcript.  
   _Files_: `components/analytics/memory/__tests__/ChatHistory.test.tsx`
