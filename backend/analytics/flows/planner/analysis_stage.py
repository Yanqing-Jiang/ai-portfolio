# --- Analytics Function/Class Map ---
# Function: run_analysis_stage
#   Role: Prefetch accessories then stream analysis lane.
#   Called from: analytics.flows.planner_executor._plan_phase
#   Invokes: analytics.flows.planner.analysis_lane.ensure_analysis_dependencies, analytics.flows.planner.analysis_lane.stream_analysis_lane, pipeline._stream_with_tool_state
#   Why: Reuses analysis lane orchestration across single-/multi-agent flows.
# --- End Analytics Function/Class Map ---
from __future__ import annotations

from typing import Any, AsyncGenerator, Dict, Optional, Set

from .analysis_lane import ensure_analysis_dependencies, stream_analysis_lane


async def run_analysis_stage(
    pipeline: Any,
    *,
    ctx: Any,
    registry: Any,
    executed: Set[str],
    tool_state: Optional[Dict[str, Any]],
    mode_config: Any,
) -> AsyncGenerator[Dict[str, Any], None]:
    """Prefetch accessories (if needed) then stream the analysis lane."""
    async for event in pipeline._stream_with_tool_state(  # type: ignore[attr-defined]
        ensure_analysis_dependencies(pipeline, ctx, mode_config=mode_config),
        tool_state,
        ctx,
    ):
        yield event

    async for event in stream_analysis_lane(
        pipeline,
        ctx=ctx,
        registry=registry,
        executed=executed,
        tool_state=tool_state,
        mode_config=mode_config,
    ):
        yield event

