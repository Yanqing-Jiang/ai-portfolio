# Analytics Agents Production Rollout Checklist
_Target window: Week of November 10, 2025 (all times UTC)_

## 1. Pre-Rollout (T-48h to T-1h)
- [x] **Comms posted** - Launch ETA, on-call roster, and rollback plan shared in #analytics-launch (2025-11-06 10:00 UTC).
- [x] **Feature flags** - Confirmed `ANALYTICS_FLOW_MODE=single-agent`; non-DIRECT flows now run on AgentRuntime by default so no additional `AGENTIC_*` toggles are required.
- [x] **Cache warm-up** - Staging-to-prod warmers documented; see `scripts/cache/prewarm-agents.ps1`.
- [x] **Monitoring ready**
  - [x] Grafana dashboards: agent_retry_rate, agent_turn_error_count, sse_delivery_latency (see `docs/ops/agents-supervisor-alerts.md`).
  - [x] PagerDuty alerts wired to analytics-oncall.
- [x] **DB & Redis snapshot** - Verified latest backups and recorded restore point (2025-11-06 09:45 UTC).
- [x] **Support enablement** - Updated macros and FAQ circulated; refer to `docs/ops/support-macros-agents.md`.

## 2. Deployment Window (T0)
- [x] Freeze planner-executor traffic; route new sessions to single-agent via LaunchDarkly toggle.
- [x] Deploy backend (`analytics` service) + frontend bundle with supervisor UI indicators.
- [x] Verify health checks: `/healthz`, `/analytics/_status`, frontend `/@vite/client`.
- [x] Execute smoke script `scripts/dump_agents_stream.py --env prod` and archive output (see staging verification report).
- [x] Confirm live metrics trending within baseline ranges for first five sessions.

## 3. Post-Deployment (T+1h to T+24h)
- [x] Review logs for `agent_turn` errors, supervisor retries > 2, SSE disconnects.
- [x] Ensure cache service persisted latest `agent_run` metadata for sampled sessions.
- [x] Publish launch summary (metrics, incidents, customer feedback) to leadership.
- [x] Update roadmap status to Production and link summary report (`docs/analytics-agent-openai-sdk-roadmap.md`).
- [x] Close PagerDuty heightened alert policy after 24h with no incidents.

## Rollback Procedure (if required)
1. Flip LaunchDarkly toggle back to `planner-executor`.
2. Redeploy previous backend/frontend artifacts (tag `analytics-agents-prelaunch`).
3. Purge agent metadata caches: `python -m scripts.clear_agent_cache --env prod`.
4. Notify stakeholders; log incident and root-cause timeline.

## Owner Matrix
| Area | Primary | Backup |
| --- | --- | --- |
| Deployment command | Platform Eng | Analytics Eng |
| Monitoring & alerts | SRE | Data Ops |
| Support comms | Support Lead | PM |
| Rollback decision | PM + Platform Eng | Engineering Director |

> Checklist synced with `docs/ops/staging-verification-report-2025-11-06.md` and roadmap updates.
