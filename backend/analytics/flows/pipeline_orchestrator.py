# --- Analytics Function/Class Map ---
# Dataclass: PipelineLaneExecutors
#   Role: Bundles configured lane executors for planner pipelines.
#   Called from: analytics.flows.planner_executor.PlannerPipeline.events
#   Collaborators: analytics.flows.lane_executors.SqlLaneExecutor, ChartLaneExecutor, AnalysisLaneExecutor
#   Why: Centralizes lane executor wiring so planner lanes reuse shared runners.
# Function: build_pipeline_lane_executors
#   Role: Configure lane executors with pipeline-aware runners for SQL, chart, and analysis lanes.
#   Called from: analytics.flows.planner_executor.PlannerPipeline.events
#   Invokes: analytics.flows.planner.sql_stage.run_sql_stage, analytics.flows.planner.chart_stage.run_chart_stage, analytics.flows.planner.analysis_stage.run_analysis_stage
#   Why: Keeps lane setup out of planner_executor.py while preserving SSE parity.
# --- End Analytics Function/Class Map ---
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, Set

from .lane_executors import AnalysisLaneExecutor, ChartLaneExecutor, SqlLaneExecutor, AccessoryLaneExecutor
from .planner.analysis_stage import run_analysis_stage
from .planner.chart_stage import run_chart_stage
from .planner.sql_stage import run_sql_stage
from .planner.accessory_stage import run_web_stage, run_market_stage


@dataclass
class PipelineLaneExecutors:
    sql: SqlLaneExecutor
    chart: ChartLaneExecutor
    analysis: AnalysisLaneExecutor
    web: Optional[AccessoryLaneExecutor] = None
    market: Optional[AccessoryLaneExecutor] = None


def build_pipeline_lane_executors(
    pipeline: Any,
    *,
    ctx: Any,
    registry: Any,
    executed: Set[str],
    tool_state: Optional[Dict[str, Any]],
    mode_config: Any,
    run_sql_lane: bool,
    run_chart_lane: bool,
) -> PipelineLaneExecutors:
    async def _sql_runner():
        async for event in run_sql_stage(
            pipeline,
            ctx=ctx,
            registry=registry,
            executed=executed,
            tool_state=tool_state,
            run_sql_lane=run_sql_lane,
        ):
            yield event

    async def _chart_runner():
        async for event in run_chart_stage(
            pipeline,
            ctx=ctx,
            registry=registry,
            executed=executed,
            tool_state=tool_state,
            run_chart_lane=run_chart_lane,
        ):
            yield event

    async def _analysis_runner():
        async for event in run_analysis_stage(
            pipeline,
            ctx=ctx,
            registry=registry,
            executed=executed,
            tool_state=tool_state,
            mode_config=mode_config,
        ):
            yield event

    async def _web_runner():
        async for event in run_web_stage(
            pipeline,
            ctx=ctx,
            reason="pipeline_orchestrator",
            source="planner_pipeline",
        ):
            yield event

    async def _market_runner():
        async for event in run_market_stage(
            pipeline,
            ctx=ctx,
            reason="pipeline_orchestrator",
            source="planner_pipeline",
        ):
            yield event

    return PipelineLaneExecutors(
        sql=SqlLaneExecutor(runner=_sql_runner),
        chart=ChartLaneExecutor(runner=_chart_runner),
        analysis=AnalysisLaneExecutor(runner=_analysis_runner),
        web=AccessoryLaneExecutor(runner=_web_runner, lane="web"),
        market=AccessoryLaneExecutor(runner=_market_runner, lane="market"),
    )
