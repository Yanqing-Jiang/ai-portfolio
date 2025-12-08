# --- Analytics Function/Class Map ---
# Function: run_web_stage
#   Role: Stream the web accessory lane using PlannerPipeline refresh logic (TTL + receipts).
#   Called from: analytics.flows.lane_executors.create_accessory_executor, analytics.flows.pipeline_orchestrator.build_pipeline_lane_executors
#   Invokes: PlannerPipeline.refresh_web_lane
#   Why: Provides a self-contained web lane runner for executor factories and sequencer proxies.
# Function: run_market_stage
#   Role: Stream the market accessory lane using PlannerPipeline refresh logic (TTL + receipts).
#   Called from: analytics.flows.lane_executors.create_accessory_executor, analytics.flows.pipeline_orchestrator.build_pipeline_lane_executors
#   Invokes: PlannerPipeline.refresh_market_lane
#   Why: Centralizes market lane execution so accessory executors avoid orchestrator passthroughs.
# --- End Analytics Function/Class Map ---
from __future__ import annotations

from typing import Any, AsyncGenerator, Dict, Optional


async def run_web_stage(
    pipeline: Any,
    *,
    ctx: Any,
    reason: Optional[str] = None,
    source: Optional[str] = None,
) -> AsyncGenerator[Dict[str, Any], None]:
    """Refresh the web lane using planner accessory logic."""

    async for event in pipeline.refresh_web_lane(
        ctx,
        reason=reason,
        source=source,
    ):
        yield event


async def run_market_stage(
    pipeline: Any,
    *,
    ctx: Any,
    reason: Optional[str] = None,
    source: Optional[str] = None,
) -> AsyncGenerator[Dict[str, Any], None]:
    """Refresh the market lane using planner accessory logic."""

    async for event in pipeline.refresh_market_lane(
        ctx,
        reason=reason,
        source=source,
    ):
        yield event
