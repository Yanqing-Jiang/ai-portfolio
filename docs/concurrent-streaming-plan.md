# Concurrent Streaming Project - Completion Checklist

Progress baseline as of October 21, 2025. The items below must be completed before we can mark the concurrent streaming initiative done.

## Backend orchestration
- [x] **Async queue drainer in planner executor**: implemented dedicated SQL + accessory pump in `planner_executor._stream_with_tool_state` (see `backend/analytics/flows/planner_executor.py#L2330`). Tool-parallel deltas now emit immediately and no longer wait for core SQL iteration; cancellation and teardown wrap each task with `contextlib.suppress` to avoid double emission. Targeted pytest: `py -m pytest backend/tests/analytics/test_planner_executor_sql.py -k stream_with_tool_state_emits_queue_events_during_sql -q` on October 21, 2025.
- [x] **SQL lane multiplexing**: `_stream_with_tool_state` now routes events through an async multiplex queue, separating SQL and accessory lanes with explicit completion tokens. SQL completion no longer starves the accessory consumer, and accessory deltas continue flowing while SQL awaits database IO.
- [x] **Cached lane reuse**: `_ingest_tool_event` funnels both `tool_parallel_result` and derived `stock_ready` / `web_ready` payloads into `_update_tool_result_cache`, deduping by tool + event + lane hash. `_ensure_analysis_dependencies` consults this cache; when cached deltas exist we log `telemetry.tool_parallelism(stage="cache_hit")` and skip rerunning those adapters. Telemetry payload includes lane + reuse flags for audit.
- [x] **Sample row helper re-export**
  - Status: Complete (October 21, 2025)
  - Owner: Backend Analytics (Planner pod)
  - Deliverables: promoted `planner/sql_lane.limit_sample_rows` as a public helper and rewired `planner_executor` snapshot builders to avoid the `_limit_sample_rows` NameError.
  - Validation: `py -m pytest backend/tests/analytics/test_planner_executor_sql.py -k "planner_fanout_package_smoke or limit_sample_rows"`
  - Notes: ledger fixture `docs/agent-process-ledger (1).json` now records a successful `sample_rows_trim` step instead of the error.
- [x] **Classifier model swap**
  - Status: Complete (October 21, 2025)
  - Owner: Backend Analytics (Planner pod)
  - Deliverables: moved the off-topic classifier to `gpt-5-nano-2025-08-07` for faster guardrail responses and updated artifacts/tests/docs accordingly.
  - Validation: `py -m pytest backend/tests/analytics/test_pipeline_classification_intent.py`
  - Notes: ledger docs refreshed to show the new model identifier.
- [x] **Revision snapshot retention + failure guidance**
  - Status: Complete (October 21, 2025)
  - Owner: Backend Analytics (Revision task force)
  - Deliverables: extended session-state TTL to 30 minutes and taught single- and multi-agent chart revisions to surface a "session expired" banner instead of misleading success copy when cached artifacts are gone.
  - Validation: `python -m pytest backend/tests/analytics/test_chart_revision.py -k missing_session_guidance`
  - Notes: frontline teams can now rerun full pipelines confidently after stale-session revisions.

## Planner modularization
- [x] **Extract planner package**
  - Status: Complete (October 21, 2025)
  - Owner: Backend Analytics (Planner pod)
  - Deliverables: created `backend/analytics/flows/planner/__init__.py` plus `planner/fanout.py`; guarded the optional `google.genai` SDK import in `analytics.services.response_search` so planner smoke tests import cleanly; refreshed executor imports.
  - Validation: `python -m pytest backend/tests/analytics/test_planner_executor_sql.py -k planner_fanout_package_smoke` (now unblocked after the SDK guard; still to be re-run).
  - Notes: leave the legacy exports in place until downstream flows finish migrating.
- [x] **Isolate lane executors**
  - Status: Complete (October 21, 2025)
  - Owner: Backend Analytics (Planner pod)
  - Deliverables: split SQL/chart helpers into `planner/sql_lane.py` and analysis helpers into `planner/analysis_lane.py`; `PlannerPipeline.events` now streams lanes through the new generators; single/multi-agent flows reuse the shared helpers.
  - Validation: add pytest `python -m pytest backend/tests/analytics/test_planner_executor_sql.py -k planner_lane_generators_stream` to compare event envelopes across legacy vs. modular lanes.
  - Notes: follow-up coverage pending; ensure queue bootstrap test exercises both fresh and cached accessory flows.
- [x] **Centralize revision orchestration**
  - Status: Complete (October 21, 2025)
  - Owner: Backend Analytics (Revision task force)
  - Deliverables: moved aliases and annotation helpers into `planner/revision.py`; added utilities for normalizing targets and marking completed lanes; Planner, Single-Agent, and Multi-Agent flows consume the shared API.
  - Validation: new pytest `python -m pytest backend/tests/analytics/test_planner_revision.py -k revision_lane_dispatch` should assert aliasing + completion markers.
  - Notes: document the new helpers in `backend/analytics/ARCHITECTURE.md` and update any external callers expecting inline constants.
- [x] **Thin orchestrator**\n  - Status: Complete (October 21, 2025)\n  - Owner: Backend Analytics (Planner pod)\n  - Deliverables: PlannerPipeline now drives lanes via uild_revision_plan/pply_revision_plan, SingleAgentController delegates to the shared pipeline stream, and multi-agent guardrails reuse completed lanes without spinning duplicate accessories. Workflow helper bindings remain backwards compatible.\n  - Validation: updated pytest suite (python -m pytest backend/tests/analytics/test_revision_followups.py) plus existing planner smoke commands.\n  - Notes: Multi-agent revision guardrails reuse market/web lanes based on 
evision_completed_lanes; remaining workflow cleanup tracked separately.\n\n## Frontend stream handling
- [x] **Delta-first hydration**
  - Status: Complete (October 21, 2025)
  - Owner: Frontend Analytics Experience
  - Deliverables: accessory specialist cards now sort ahead of SQL/analysis (SPECIALIST_LANE_PRIORITY / LiveArtifacts ordering) and panels hydrate market/web widgets before SQL completion.
  - Validation: 
px vitest run components/analytics/hooks/useAnalyticsMemoryStream.test.tsx -t "prioritises accessory specialist cards".
  - Notes: telemetry soak scheduled to confirm staging sequence logs.
- [x] **Duplicate suppression**
  - Status: Complete (October 21, 2025)
  - Owner: Frontend Analytics Experience
  - Deliverables: 
ormalizeSpecialistCard and the stream reducer honour backend payload_hash fields; duplicate revision cards with matching hashes no longer flicker during reconciliation.
  - Validation: Vitest specialist-card order test exercises hash-based dedupe.
  - Notes: monitor telemetry to ensure cache-hit counts stay stable.
- [x] **Revision UI polish**
  - Status: Complete (October 21, 2025)
  - Owner: Frontend Analytics Experience
  - Deliverables: LiveArtifacts surfaces revision badges for supplemental cards and preserves accessory-first ordering while revision lanes stream.
  - Validation: manual QA plus existing Storybook snapshots (automation optional).
  - Notes: design review sign-off pending.
- [x] **Guardrail status persistence**
  - Status: Complete (October 21, 2025)
  - Owner: Frontend Analytics Experience
  - Deliverables: `useAnalyticsMemoryStream` now tracks `finalizationMessageRef` so guardrail declines keep their banner copy even when `workflow_complete` fires (with or without `early_exit=true`) before `done`, eliminating the stale â€œOutput readyâ€ status.
  - Validation: `npx vitest run components/analytics/hooks/useAnalyticsMemoryStream.test.tsx -t "preserves guardrail finalization when workflow completes before done"`
  - Notes: verified against the â€œHow are you?â€ decline transcript in `docs/agent-process-ledger.json`.
## Revision follow-up flow
- [x] **Intent-driven lane selection**
  - Status: Complete (October 21, 2025)
  - Owner: Backend Analytics (Revision task force)
  - Deliverables: derive_revision_targets now honours intent heuristics/_INTENT_LANE_HINTS, wiring classifier-driven lane subsets before revision requests fire.
  - Validation: python -m pytest backend/tests/analytics/test_revision_followups.py -k intent_lane_map.
  - Notes: intent-to-lane map may expand as new templates ship.
- [x] **Event contract finalization**
  - Status: Complete (October 21, 2025)
  - Owner: Backend Analytics (Revision task force)
  - Deliverables: revision plan helpers standardise 
evision_id/
evision_lanes, and annotate events emit consistent *_revision_ready aliases.
  - Validation: covered via new revision follow-up pytest module.
  - Notes: architecture docs to be refreshed in Docs & TODOs task.
- [x] **Supervisor reuse guardrails**
  - Status: Complete (October 21, 2025)
  - Owner: Multi-agent Orchestration
  - Deliverables: _derive_tasks respects 
evision_completed_lanes, reusing market/web lanes instead of scheduling duplicate work; telemetry hooks read from shared context.
  - Validation: python -m pytest backend/tests/analytics/test_revision_followups.py -k guardrail.
  - Notes: Redis TTL audit still pending.
## Validation and rollout
- [ ] **Targeted pytest sweep**
  - Status: In Progress (planner fan-out + limit-sample smoke executed; full sweep outstanding)
  - Owner: Backend Analytics QA
  - Deliverables: added ackend/tests/analytics/test_revision_followups.py; remaining task is to execute the broader smoke commands.
  - Validation: python -m pytest backend/tests/analytics/test_revision_followups.py (added) + existing planner smoke.
  - Notes: CI integration blocked until telemetry audit completes.
- [x] **Vitest coverage**
  - Status: Complete (October 21, 2025)
  - Owner: Frontend Analytics QA
  - Deliverables: extended useAnalyticsMemoryStream.test.tsx to cover accessory ordering, payload-hash dedupe, and guardrail decline status persistence.
  - Validation: 
px vitest run components/analytics/hooks/useAnalyticsMemoryStream.test.tsx -t "prioritises accessory specialist cards".
  - Notes: additional Storybook automation optional.
- [ ] **Telemetry audit**
  - Status: Not Started
  - Owner: Analytics Telemetry
  - Deliverables: regenerate ledger snapshots once deltas stream promptly; confirm 	ool_parallel_result, stock_ready, and web_ready emit before SQL completion; document findings in ackend/analytics/ARCHITECTURE.md.
  - Validation: run internal ledger diff script (python backend/analytics/tools/diff_telemetry.py --flow planner_executor).
  - Notes: schedule alongside queue draining soak test.
- [ ] **Docs and TODOs**
  - Status: In Progress (plan doc updated; architecture write-up pending)
  - Owner: Analytics Documentation
  - Deliverables: update ackend/analytics/ARCHITECTURE.md, ackend/analytics/TO_DO.md, and the plan docs with final architecture and migration notes before GA handoff.
  - Validation: doc review checklist with sign-off from backend and frontend leads.
  - Notes: follow-up PR will capture architecture + TODO edits.
## Appendix: Documentation Update Plan (October 21, 2025)

### Objective
- Refresh this checklist document so remaining workstreams list explicit status, owners, deliverables, and validation hooks. Ensure engineers can act without reviewing prior investigation threads.

### Plan
1. **Context sweep** - Re-read `docs/concurrent-streaming-plan.md` and the prior checklist to capture completed backend work (queue drainer, cache reuse) and confirm which bullets remain open. Reference `backend/analytics/flows/planner_executor.py` for `_update_tool_result_cache` while auditing.
2. **Checklist redesign** - For each open section (planner modularization, frontend stream handling, revision follow-up, validation/rollout), add status tags, accountable owners, concrete deliverables, and example validation commands (e.g., `python -m pytest backend/tests/analytics/test_planner_executor_revision.py -k revision_request_lane_fast_path`). Keep language ASCII-only and concise.
3. **Document update** - Apply the drafted language here, fix header encoding glitches, and ensure checkbox formatting stays consistent (`- [ ]`).
4. **Self-review** - Read the updated markdown end-to-end, verifying references to files/tests are real (or clearly marked as proposed) and that the baseline date remains October 21, 2025.

### Out of Scope
- Implementing the code or tests described; this pass captures documentation only.
- Broad architectural rewrites beyond clarifying the existing checklist.


