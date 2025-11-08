# Agents Supervisor Alert Scaffolding

Checklist for wiring analytics supervisor telemetry into alerting now that load coverage is in place. Use this as the baseline for SRE configuration.

## Alert Streams
- **Trace ingestion failures (`analytics.supervisor.trace_ingest`)**
  - Trigger when `backpressure_duration_ms` exceeds 5000 for two consecutive samples.
  - Source: `backend/logs/dev.log` (mirrored to CloudWatch). Use `Select-String` during dry runs to validate payloads.
- **Specialist lane stall (`analytics.supervisor.lane_stall`)**
  - Trigger when any lane stays in queued state longer than 90 seconds or exceeds retry budget.
  - Exposed via `core.telemetry.agent_run` events; Supervisors attach `parallel_group` and retry data.
- **Load-test regression (`analytics.supervisor.load_regression`)**
  - Trigger when `reports/load/*.json` artifacts show p95 latency above 4000 ms or failure rate above 2 percent.
  - Evaluated inside CI using `reports/load/agents-supervisor-iteration5.template.json`.
- **Agent tool completion delta (`analytics.agent_tool_gap`)**
  - Trigger when `outstanding_ratio` >= 0.10 for at least 5 minutes or `outstanding` >= 3 for a single lane.
  - Source: telemetry logger; each payload includes `lane`, `outstanding`, `total_calls`, and `threshold`. Wire into Grafana by charting the rolling sum of `outstanding` per lane and alerting on the ratio field.
  - CI guardrail: `.github/workflows/agentic-smoke.yml` replays the STOCK_ONLY / REUSE_SQL / redirect fixtures on every PR, uploads `agentic-smoke-fixtures` artifacts, and can optionally hit staging via `AGENTIC_SMOKE_BACKEND_URL` plus the `run_live` dispatch flag to generate `agentic-smoke-live` traces.
  - Response: inspect the latest `lane_reused` / `agent_tool_complete` events via `reports/agentic_smoke/*.json` or `scripts/dump_agents_stream.py`, then restart the stuck accessory worker or rerun the session with `python scripts/agentic_smoke_test.ps1 --scenario stock`.

## PowerShell Verification Snippets
```powershell
# Tail supervisor logs with alert annotations
Get-Content backend\logs\dev.log -Tail 50 | Select-String -Pattern "alert_key"

# Validate latest load artifact before publishing
Get-ChildItem reports\load\*.json | Sort-Object LastWriteTime -Descending | Select-Object -First 1 | Get-Content
```

## Next Steps
1. Map alert keys to PagerDuty routing once reliability council signs off.
2. Backfill unit tests around `_format_backpressure_event` to guarantee `alert_key` fields stay present.
3. Sync this checklist with `docs/analytics-agent-openai-sdk-roadmap.md` ahead of the beta go/no-go review.
