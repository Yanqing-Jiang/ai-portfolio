# --- Analytics Function/Class Map ---
# Function: invoke_analysis_lane
#   Role: Tool-callable interface for AnalysisLaneExecutor.
#   Called from: analytics.tools.canonical_registry, analytics.tools.definitions.run_tool_by_id
#   Invokes: analytics.flows.lane_executors.AnalysisLaneExecutor
#   Why: Enables analysis lane execution as a registered tool for Single/Multi-Agent flows.
# --- End Analytics Function/Class Map ---
"""Analysis lane tool wrapper for Canonical Registry integration."""
from __future__ import annotations

from typing import Any, AsyncGenerator, Dict, List, Optional

from analytics.flows.lane_executors import AnalysisLaneExecutor

# Tool schema for OpenAI/Claude function calling
ANALYSIS_LANE_TOOL_SCHEMA: Dict[str, Any] = {
    "name": "invoke_analysis_lane",
    "description": (
        "Generate narrative analysis from SQL data and chart context. "
        "Produces TL;DR summaries, key highlights, risk factors, and next steps "
        "with evidence attribution from web sources."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "session_id": {
                "type": "string",
                "description": "Session identifier for context and caching",
            },
            "analysis_mode": {
                "type": "string",
                "enum": ["full", "summary", "bullets"],
                "description": "Analysis output format",
                "default": "full",
            },
            "force_refresh": {
                "type": "boolean",
                "description": "Skip cache and force fresh analysis generation",
                "default": False,
            },
        },
        "required": ["session_id"],
    },
}


async def invoke_analysis_lane(
    *,
    pipeline: Any,
    ctx: Any,
    registry: Any,
    executed: Optional[List[str]] = None,
    tool_state: Optional[Dict[str, Any]] = None,
    mode_config: Any = None,
) -> AsyncGenerator[Dict[str, Any], None]:
    """
    Tool-callable interface for analysis lane execution.

    This wrapper exposes the AnalysisLaneExecutor as a tool that can be registered
    in the Canonical Registry and invoked by Single Agent and Multi-Agent flows.

    Args:
        pipeline: The planner pipeline instance
        ctx: The planner phase context
        registry: The tool registry for lane execution
        executed: Set of already-executed lane identifiers
        tool_state: Optional tool state for parallel execution
        mode_config: Mode configuration for analysis behavior

    Yields:
        SSE events from analysis lane execution including analysis_ready,
        narrative chunks, evidence payloads, etc.
    """
    executor = AnalysisLaneExecutor(
        pipeline=pipeline,
        ctx=ctx,
        registry=registry,
        executed=executed or [],
        tool_state=tool_state,
        mode_config=mode_config,
    )

    async for event in executor.run():
        yield event
