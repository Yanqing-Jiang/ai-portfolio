# --- Analytics Function/Class Map ---
# Function: invoke_chart_lane
#   Role: Tool-callable interface for ChartLaneExecutor.
#   Called from: analytics.tools.canonical_registry, analytics.tools.definitions.run_tool_by_id
#   Invokes: analytics.flows.lane_executors.ChartLaneExecutor
#   Why: Enables chart lane execution as a registered tool for Single/Multi-Agent flows.
# --- End Analytics Function/Class Map ---
"""Chart lane tool wrapper for Canonical Registry integration."""
from __future__ import annotations

from typing import Any, AsyncGenerator, Dict, List, Optional

from analytics.flows.lane_executors import ChartLaneExecutor

# Tool schema for OpenAI/Claude function calling
CHART_LANE_TOOL_SCHEMA: Dict[str, Any] = {
    "name": "invoke_chart_lane",
    "description": (
        "Generate ECharts visualization configuration from SQL data. "
        "Takes data rows and returns a complete chart specification with "
        "datasets, series configuration, and design metadata."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "session_id": {
                "type": "string",
                "description": "Session identifier for context and caching",
            },
            "chart_type": {
                "type": "string",
                "description": "Optional chart type override (line, bar, area, etc.)",
            },
            "force_refresh": {
                "type": "boolean",
                "description": "Skip cache and force fresh chart generation",
                "default": False,
            },
        },
        "required": ["session_id"],
    },
}


async def invoke_chart_lane(
    *,
    pipeline: Any,
    ctx: Any,
    registry: Any,
    executed: Optional[List[str]] = None,
    tool_state: Optional[Dict[str, Any]] = None,
    run_chart_lane: bool = True,
) -> AsyncGenerator[Dict[str, Any], None]:
    """
    Tool-callable interface for chart lane execution.

    This wrapper exposes the ChartLaneExecutor as a tool that can be registered
    in the Canonical Registry and invoked by Single Agent and Multi-Agent flows.

    Args:
        pipeline: The planner pipeline instance
        ctx: The planner phase context
        registry: The tool registry for lane execution
        executed: Set of already-executed lane identifiers
        tool_state: Optional tool state for parallel execution
        run_chart_lane: Whether to actually run the chart lane (vs dry-run)

    Yields:
        SSE events from chart lane execution including chart_ready, spec payloads, etc.
    """
    executor = ChartLaneExecutor(
        pipeline=pipeline,
        ctx=ctx,
        registry=registry,
        executed=executed or [],
        tool_state=tool_state,
        run_chart_lane=run_chart_lane,
    )

    async for event in executor.run():
        yield event
