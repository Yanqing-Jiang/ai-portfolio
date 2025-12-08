# --- Analytics Function/Class Map ---
# Function: invoke_sql_lane
#   Role: Tool-callable interface for SqlLaneExecutor.
#   Called from: analytics.tools.canonical_registry, analytics.tools.definitions.run_tool_by_id
#   Invokes: analytics.flows.lane_executors.SqlLaneExecutor
#   Why: Enables SQL lane execution as a registered tool for Single/Multi-Agent flows.
# --- End Analytics Function/Class Map ---
"""SQL lane tool wrapper for Canonical Registry integration."""
from __future__ import annotations

from typing import Any, AsyncGenerator, Dict, List, Optional

from analytics.flows.lane_executors import SqlLaneExecutor

# Tool schema for OpenAI/Claude function calling
SQL_LANE_TOOL_SCHEMA: Dict[str, Any] = {
    "name": "invoke_sql_lane",
    "description": (
        "Execute SQL generation and query execution for financial data analysis. "
        "Takes a natural language query and returns structured SQL results with "
        "data rows, columns, and execution metadata."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Natural language query describing the data needed",
            },
            "session_id": {
                "type": "string",
                "description": "Session identifier for context and caching",
            },
            "force_refresh": {
                "type": "boolean",
                "description": "Skip cache and force fresh SQL execution",
                "default": False,
            },
        },
        "required": ["query", "session_id"],
    },
}


async def invoke_sql_lane(
    *,
    pipeline: Any,
    ctx: Any,
    registry: Any,
    executed: Optional[List[str]] = None,
    tool_state: Optional[Dict[str, Any]] = None,
    run_sql_lane: bool = True,
) -> AsyncGenerator[Dict[str, Any], None]:
    """
    Tool-callable interface for SQL lane execution.

    This wrapper exposes the SqlLaneExecutor as a tool that can be registered
    in the Canonical Registry and invoked by Single Agent and Multi-Agent flows.

    Args:
        pipeline: The planner pipeline instance
        ctx: The planner phase context
        registry: The tool registry for lane execution
        executed: Set of already-executed lane identifiers
        tool_state: Optional tool state for parallel execution
        run_sql_lane: Whether to actually run the SQL lane (vs dry-run)

    Yields:
        SSE events from SQL lane execution including sql_ready, data payloads, etc.
    """
    executor = SqlLaneExecutor(
        pipeline=pipeline,
        ctx=ctx,
        registry=registry,
        executed=executed or [],
        tool_state=tool_state,
        run_sql_lane=run_sql_lane,
    )

    async for event in executor.run():
        yield event
