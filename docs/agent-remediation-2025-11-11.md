# Agent Remediation Log — 2025-11-11

## Completed Work
- **Single-agent runtime guardrails:** Added configuration/flag checks so `_agent_run_stage` only executes when the session is in a follow-up or agentic revision mode. Fresh runs now stay on the deterministic planner path, eliminating missing SQL/chart/analysis payloads.
- **Clarification loop fix:** When the planner already resolved required slots, the agent’s clarification tool is skipped with telemetry, removing redundant clarification prompts.
- **Agent fallback pipeline:** After every agent run we verify SQL, web, market, and analysis artifacts. Any gaps automatically trigger the legacy planner lanes to regenerate results, guaranteeing downstream charts and narratives.
- **Accessory timestamp hardening:** Normalized cached receipt timestamps to timezone-aware UTC and guarded age calculations against naive inputs, preventing the “offset-naive vs. offset-aware” crash that blocked multi-agent web research.
- **Regression coverage:** Added unit tests covering the new gating/fallback logic plus timestamp normalization to ensure these behaviors stay enforced.

## Validation
- `python -m pytest backend/tests/analytics/test_single_agent_controller_agents.py backend/tests/analytics/test_accessory_receipts.py`
