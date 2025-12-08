# --- Analytics Function/Class Map ---
# Function: run_sql_stage
#   Role: Streams SQL lane via existing lane helpers.
#   Called from: analytics.flows.planner_executor._plan_phase
#   Invokes: analytics.flows.planner.sql_lane.stream_sql_lane
#   Why: Provides a reusable SQL lane entrypoint for single-/multi-agent flows.
# --- End Analytics Function/Class Map ---
from __future__ import annotations

from typing import Any, AsyncGenerator, Dict, Optional, Set

from .sql_lane import stream_sql_lane


async def run_sql_stage(
    pipeline: Any,
    *,
    ctx: Any,
    registry: Any,
    executed: Set[str],
    tool_state: Optional[Dict[str, Any]],
    run_sql_lane: bool,
) -> AsyncGenerator[Dict[str, Any], None]:
    """Run the SQL lane using the shared lane helper."""
    async for event in stream_sql_lane(
        pipeline,
        ctx=ctx,
        registry=registry,
        executed=executed,
        tool_state=tool_state,
        run_sql_lane=run_sql_lane,
    ):
        yield event

