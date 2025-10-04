# Analytics Runtime Rollout Runbook

## Purpose
This runbook documents how to validate, enable, and (if required) roll back the runtime-based analytics agents. Use it when comparing planner-executor vs. runtime behaviour, preparing staged rollouts, or responding to incidents.

## Feature Flags
- `ANALYTICS_AGENT_RUNTIME` — selects the default flow (`planner-executor`, `single-agent`, `multi-agent`, `single-agent-legacy`, `multi-agent-legacy`).
- `ANALYTICS_TOOL_PARALLELISM` — enables TaskGroup fan-out in single/multi-agent runtimes.
- `ANALYTICS_ENABLE_WEB_SEARCH` — forces the web specialist even when the query lacks recency keywords.
- `ANALYTICS_MARKET_WIDGET` — enables market snapshot specialist execution when tickers are available.
- `ANALYTICS_MEMORY_INSTRUMENT` — toggles SSE instrumentation for benchmarking.

## Pre-Rollout Checklist
1. **Environment parity** — verify `.env` and `backend/.env` contain valid `OPENAI_API_KEY`, `DATABASE_URL`, and `POLYGON_API_KEY` values.
2. **Replay benchmarks** — run `python -m backend.analytics.flows.replay_benchmark --prompt "<sample query>" --flow planner-executor --flow multi-agent --flow single-agent` to capture latency + event diff between flows.
3. **Telemetry dashboards** — confirm ProcessPanel/WorkflowCanvas receive `sequence`, `responseId`, `market` snapshots, and multi-lane updates in staging.
4. **Fallback validation** — exercise planner, single, and multi runtimes with missing data and web-disabled scenarios to confirm guardrails surface clean errors.

## Rollout Steps
1. Enable `ANALYTICS_AGENT_RUNTIME=single` in staging, monitor error rate + latency for 30 minutes.
2. Switch staging to `ANALYTICS_AGENT_RUNTIME=multi` with `ANALYTICS_TOOL_PARALLELISM=1`; re-run replay benchmarks.
3. For production:
   - Start with `ANALYTICS_AGENT_RUNTIME=planner-executor` + dark-launch SSE instrumentation.
   - Gradually ramp to `single` (25% of traffic via routing layer) and monitor dashboards.
   - Once stable, set `ANALYTICS_AGENT_RUNTIME=multi` for 25%, then 50%, then 100%.
4. Enable `ANALYTICS_MARKET_WIDGET=1` after confirming Polygon access and market snapshot display.
5. Document rollout progress in the on-call log with benchmark links.

## Rollback Playbook
- Set `ANALYTICS_AGENT_RUNTIME=planner-executor` to restore the legacy flow.
- Disable `ANALYTICS_TOOL_PARALLELISM` and `ANALYTICS_MARKET_WIDGET` to bypass runtime-only features.
- Re-run `python -m backend.analytics.flows.replay_benchmark --prompt "<troublesome query>" --flow planner-executor --flow multi-agent` to confirm parity before reattempting rollout.

## Incident Response Tips
- Multi-agent failures emit `agent_turn` events with `status="failed"` and the captured errors list; surface the session in ProcessPanel for replay.
- Market snapshot issues usually stem from missing `POLYGON_API_KEY`; the runtime marks the specialist as `unavailable` and continues without failing the workflow.
- Use `backend/analytics/flows/replay_benchmark.py` with `--include-events` to export JSON for debugging SSE ordering issues.

## Post-Rollout Tasks
- Update telemetry thresholds in dashboards to reflect new sequence counts and response IDs.
- Expand the pytest suite with runtime-focused SSE order assertions once mocks are ready (see `backend/tests/analytics`).
- Archive replay benchmark JSON files in the analytics runbook folder for historical comparisons.
