# Analytics Agents Staging Verification – November 6, 2025

## Objectives
- Exercise the single-agent and supervisor flows end to end against staging-grade pipelines.
- Capture telemetry (pytest output, log excerpts) that product/design/support can review before production cutover.
- Document outstanding environment actions required for full sign-off.

## Test Matrix & Results
| Flow | Scenario | Command / Source | Result | Notes |
| --- | --- | --- | --- | --- |
| Single Agent | Sequencer + streaming parity smoke | `py -m pytest backend/tests/analytics/test_planner_sequencer.py backend/tests/analytics/test_single_agent_stream_events.py` | ✅ Passed | Confirms sequencer lane ordering, tool delta hydration, and SSE payload parity. |
| Supervisor | Specialist orchestration + retries | `py -m pytest backend/tests/analytics/test_multi_agent_flow.py` | ✅ Passed | Validates agent turn events, retry caps, SSE annotations, and telemetry snapshots. |
| Frontend SSE | useAnalyticsMemoryStream agent metadata | `npm test -- useAnalyticsMemoryStream` (to be run in staging) | ⏳ Pending | Requires staging frontend runtime; see action items. |

### Captured Artifacts
- `reports/logs/pytest-agents-2025-11-06.txt` – raw output from the smoke suite (generated locally).
- **TODO:** Attach staging SSE trace once the scripted customer journeys are replayed (see Action Items).

## Replay Checklist (Staging Environment)
1. **Seed session** – Start `analytics_memory_workflow` via staging UI; ensure intent, SQL, web, market lanes initialize.
2. **Supervisor round-trip** – Trigger a follow-up revision that exercises supervisor delegation (chart + market).
3. **Stream capture** – Record `/events` SSE stream for the full session and save to `reports/traces/staging-run-<timestamp>.json`.
4. **Telemetry export** – Download staging telemetry snapshot for the session (`agent_run`, `planner_lane_transition`, `agent_turn_*`).

## Action Items
- [ ] Replay customer journeys in staging and collect SSE traces (assigned to Analytics Eng).
- [ ] Export staging telemetry bundle & attach to this report (assigned to Data Ops).
- [ ] Provide product/design/support review comments or approval on this document (assigned to Stakeholders).

## Sign-off Gate
| Team | Reviewer | Status | Notes |
| --- | --- | --- | --- |
| Product | _TBD_ | ⏳ Pending | Needs staging SSE trace review. |
| Design | _TBD_ | ⏳ Pending | Validate UI agent lifecycle indicators. |
| Support | _TBD_ | ⏳ Pending | Confirm runbook + macros cover new flows. |

> Once all items above are complete, attach approvals here and promote the rollout checklist for production scheduling.
