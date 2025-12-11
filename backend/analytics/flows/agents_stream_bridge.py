# --- Analytics Function/Class Map ---
# Module: agents_stream_bridge (facade)
#   Role: Re-export AgentsStreamBridge, ForbiddenToolCallError, and adapter helpers after bridge split.
#   Called from: analytics.agent_orchestrator.agent_runtime, analytics.flows.multi_agent, tests.analytics.test_agents_stream_bridge
#   Invokes: analytics.flows.agents_stream_bridge.core, analytics.flows.agents_stream_bridge.adapters
#   Why: Preserve import stability while isolating bridge core/adapters.
# --- End Analytics Function/Class Map ---
from __future__ import annotations

from analytics.flows.agents_stream_bridge.core import AgentsStreamBridge, ForbiddenToolCallError
from analytics.flows.agents_stream_bridge.adapters import (
    LANE_EVENT_BY_TOOL,
    agent_role_for_tool,
    agent_turn_payload,
    build_latency_guardrail,
    merge_tool_metadata,
)

__all__ = [
    "AgentsStreamBridge",
    "ForbiddenToolCallError",
    "LANE_EVENT_BY_TOOL",
    "agent_role_for_tool",
    "agent_turn_payload",
    "merge_tool_metadata",
    "build_latency_guardrail",
]





