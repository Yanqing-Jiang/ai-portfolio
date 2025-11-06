# Analytics Canvas - Agent Lifecycle Indicators (November 2025)

## Purpose
Document the UI contract for streaming analytics runs now that OpenAI Agents power both the single-agent and supervisor flows. This supplements the existing architecture notes with concrete lane metadata, event sequencing, and support guidance.

## Stream Metadata
- **Core event types**
  - `agent_turn_start` / `agent_turn_end` - emitted for planner agent and each specialist; payload includes `role`, `lane`, `retry_count`, `parallel_group`, `tool`.
  - `planner_lane_transition` - sequencer-sourced lane status (`pending`, `running`, `fresh`, `reused`, `error`) across intent, sql, web, market, analysis.
  - `tool_call_delta` / `tool_call_arguments` / `agent_tool_complete` - single-agent tool invocation stream; payloads map to legacy planner tool IDs.
  - `analysis_streaming` / `analysis_complete` - chunked final-answer output with `lane=analysis`.
- **Session metadata**
  - `agent_metadata` block carries `run_id`, `trace_id`, `manager_trace_id`, `model`, retry maps, and `parallel_groups`.
  - UI should surface supervisor decisions using `delegation_decisions` when present.

## UI Guidelines
1. **Lane Pill States**
   - Use sequencer presentation states: `queued` (initial for chart/analysis), `running`, `fresh`, `reused`, `error`.
   - When supervisor retries a lane, increment badge using `retry_count`.
2. **Supervisor Timeline**
   - Display `agent_turn_start` / `agent_turn_end` entries in the modal timeline with specialist name, tool, and elapsed_ms.
   - Highlight retries by comparing consecutive `agent_turn_start` events with the same `lane`.
3. **Tool Cards**
   - For single-agent runs, continue rendering planner tool cards; populate `tool_call_arguments` fields (arguments, sequence_number).
   - For supervisor runs, annotate cards with `role` and `summary` from `AgentResult.to_events`.
4. **Final Answer Banner**
   - The analysis lane emits `analysis_complete` followed by `final_answer`. Display defer/resume state if `final_answer_only` is true.
5. **Error Handling**
   - If a lane transitions to `error`, surface the `error` field from the lane transition; optionally show `failure_markers` stored in cache.

## Support Playbook Highlights
- **Common Signals**
  - High `agent_retry_rate` (>25 percent) - investigate tool configuration; review `delegation_decisions`.
  - Repeated `agent_turn` errors on web lane - verify network credentials; fall back to cached receipts.
  - SSE disconnects - inspect `sse_delivery_latency` monitor and client network path.
- **Troubleshooting Steps**
  1. Retrieve session snapshot via `scripts/dump_agents_stream.py --session <id>`.
  2. Review `agent_run` telemetry for run_id and trace_id correlation.
  3. If supervisor stalled, reset lane states using `/admin/sessions/<id>/reset`.

## References
- `docs/analytics-agent-openai-sdk-roadmap.md`
- `docs/ops/analytics-agents-rollout-checklist.md`
- `docs/ops/agents-supervisor-alerts.md`
