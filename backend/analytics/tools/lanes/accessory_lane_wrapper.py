# --- Analytics Function/Class Map ---
# Function: invoke_web_lane
#   Role: Tool-callable interface for web accessory lane.
#   Called from: analytics.tools.canonical_registry, analytics.tools.definitions.run_tool_by_id
#   Invokes: analytics.flows.lane_executors.AccessoryLaneExecutor
#   Why: Enables web research lane execution as a registered tool for Single/Multi-Agent flows.
# Function: invoke_market_lane
#   Role: Tool-callable interface for market accessory lane.
#   Called from: analytics.tools.canonical_registry, analytics.tools.definitions.run_tool_by_id
#   Invokes: analytics.flows.lane_executors.AccessoryLaneExecutor
#   Why: Enables market data lane execution as a registered tool for Single/Multi-Agent flows.
# --- End Analytics Function/Class Map ---
"""Accessory lane tool wrappers for Canonical Registry integration."""
from __future__ import annotations

from typing import Any, AsyncGenerator, Dict, Optional

from analytics.flows.lane_executors import AccessoryLaneExecutor

# Tool schema for web lane - OpenAI/Claude function calling
WEB_LANE_TOOL_SCHEMA: Dict[str, Any] = {
    "name": "invoke_web_lane",
    "description": (
        "Perform web research to gather context for financial analysis. "
        "Returns summaries, snippets, and source citations from trusted "
        "financial news and research sources."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "session_id": {
                "type": "string",
                "description": "Session identifier for context and caching",
            },
            "topic": {
                "type": "string",
                "description": "Optional search topic override",
            },
            "force_refresh": {
                "type": "boolean",
                "description": "Skip cache and force fresh web search",
                "default": False,
            },
        },
        "required": ["session_id"],
    },
}

# Tool schema for market lane - OpenAI/Claude function calling
MARKET_LANE_TOOL_SCHEMA: Dict[str, Any] = {
    "name": "invoke_market_lane",
    "description": (
        "Fetch real-time and historical market data for stock symbols. "
        "Returns price data, trading metrics, and market insights for "
        "specified tickers."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "session_id": {
                "type": "string",
                "description": "Session identifier for context and caching",
            },
            "tickers": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of stock ticker symbols",
            },
            "force_refresh": {
                "type": "boolean",
                "description": "Skip cache and force fresh market data fetch",
                "default": False,
            },
        },
        "required": ["session_id"],
    },
}


async def invoke_web_lane(
    *,
    pipeline: Any,
    ctx: Any,
    reason: Optional[str] = None,
    source: Optional[str] = None,
) -> AsyncGenerator[Dict[str, Any], None]:
    """
    Tool-callable interface for web research lane execution.

    This wrapper exposes the AccessoryLaneExecutor (web) as a tool that can be
    registered in the Canonical Registry and invoked by Single Agent and
    Multi-Agent flows.

    Args:
        pipeline: The planner pipeline instance
        ctx: The planner phase context
        reason: Reason for web lane invocation (for telemetry)
        source: Source of invocation (for telemetry)

    Yields:
        SSE events from web lane execution including web_ready, snippets, etc.
    """
    executor = AccessoryLaneExecutor(
        runner=None,
        lane="web",
        pipeline=pipeline,
        ctx=ctx,
        reason=reason or "tool_invocation",
        source=source or "canonical_registry",
    )

    async for event in executor.run():
        yield event


async def invoke_market_lane(
    *,
    pipeline: Any,
    ctx: Any,
    reason: Optional[str] = None,
    source: Optional[str] = None,
) -> AsyncGenerator[Dict[str, Any], None]:
    """
    Tool-callable interface for market data lane execution.

    This wrapper exposes the AccessoryLaneExecutor (market) as a tool that can be
    registered in the Canonical Registry and invoked by Single Agent and
    Multi-Agent flows.

    Args:
        pipeline: The planner pipeline instance
        ctx: The planner phase context
        reason: Reason for market lane invocation (for telemetry)
        source: Source of invocation (for telemetry)

    Yields:
        SSE events from market lane execution including stock_ready, widgets, etc.
    """
    executor = AccessoryLaneExecutor(
        runner=None,
        lane="market",
        pipeline=pipeline,
        ctx=ctx,
        reason=reason or "tool_invocation",
        source=source or "canonical_registry",
    )

    async for event in executor.run():
        yield event
