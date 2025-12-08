# --- Analytics Function/Class Map ---
# Function: run_chart_stage
#   Role: Streams chart lane via shared lane helper.
#   Called from: analytics.flows.planner_executor._plan_phase
#   Invokes: analytics.flows.planner.sql_lane.stream_chart_lane
#   Why: Provides a reusable chart lane entrypoint for single-/multi-agent flows.
# --- End Analytics Function/Class Map ---
from __future__ import annotations

from typing import Any, AsyncGenerator, Dict, Optional, Set

from .sql_lane import stream_chart_lane


async def run_chart_stage(
    pipeline: Any,
    *,
    ctx: Any,
    registry: Any,
    executed: Set[str],
    tool_state: Optional[Dict[str, Any]],
    run_chart_lane: bool,
) -> AsyncGenerator[Dict[str, Any], None]:
    """Run the chart lane using the shared lane helper."""
    async for event in stream_chart_lane(
        pipeline,
        ctx=ctx,
        registry=registry,
        executed=executed,
        tool_state=tool_state,
        run_chart_lane=run_chart_lane,
    ):
        yield event

