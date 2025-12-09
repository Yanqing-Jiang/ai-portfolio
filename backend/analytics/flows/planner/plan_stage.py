# --- Analytics Function/Class Map ---
# Function: run_plan_stage
#   Role: Delegates to the pipeline's plan phase coroutine so lane executors can emit plan events.
#   Called from: analytics.flows.lane_executors.PlanLaneExecutor
#   Invokes: pipeline._plan_phase
#   Why: Restores an importable plan-stage runner after the plan_phase moved onto PlannerPipeline.
# --- End Analytics Function/Class Map ---
from __future__ import annotations

from typing import Any, AsyncGenerator, Mapping


async def run_plan_stage(pipeline: Any, *, ctx: Any) -> AsyncGenerator[Mapping[str, Any], None]:
    """
    Stream plan-phase events using the pipeline's internal _plan_phase coroutine.

    The wrapper keeps lane executors decoupled from PlannerPipeline internals while preserving
    the expected streaming interface for plan-stage execution.
    """
    if not hasattr(pipeline, "_plan_phase"):
        raise AttributeError("Pipeline missing _plan_phase")

    async for event in pipeline._plan_phase(ctx):
        yield event
