# --- Analytics Function/Class Map ---
# Function: maybe_emit_fresh_lane_event
#   Role: Emits fresh-lane progress events for forced fresh pipelines.
#   Called from: analytics.flows.planner_executor (delegated)
#   Invokes: analytics.core.telemetry.fresh_pipeline_lane, analytics.core.events.EventEmitter.progress
#   Why: Centralizes fresh lane signaling for reuse.
# Function: collect_tool_deltas_now
#   Role: Drains non-blocking tool deltas from a tool_state queue.
#   Called from: analytics.flows.planner_executor (delegated)
#   Invokes: analytics.flows.planner.ToolParallelRuntime
#   Why: Keeps queue draining logic reusable across flows.
# Function: drain_tool_state_async
#   Role: Async drains tool_state queue until sentinel observed.
#   Called from: analytics.flows.planner_executor (delegated)
#   Invokes: collect_tool_deltas_now
#   Why: Shares async draining logic for planner and agents.
# --- End Analytics Function/Class Map ---
from __future__ import annotations

import asyncio
from asyncio import QueueEmpty
from datetime import datetime
from typing import Any, AsyncGenerator, Dict, List, Optional

from analytics.core import telemetry
from analytics.core.events import EventEmitter
from .fanout import ToolParallelRuntime, TOOL_QUEUE_SENTINEL

FRESH_RUN_REASONING_EFFORT = "low"


def maybe_emit_fresh_lane_event(
    pipeline: Any,
    ctx: Any,
    lane: str,
    status: str,
    *,
    reason: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Emit a fresh-lane event if forced full-fresh pipeline is active."""
    if getattr(pipeline, "_suppress_fresh_pipeline", False):
        return None
    if not getattr(ctx, "force_full_fresh_pipeline", False):
        return None
    status_map: Dict[str, str] = getattr(ctx, "_fresh_lane_status", {})
    if not hasattr(ctx, "_fresh_lane_status"):
        setattr(ctx, "_fresh_lane_status", status_map)
    previous = status_map.get(lane)
    if previous == status:
        return None
    if status == "started" and previous in {"started", "completed"}:
        return None
    if previous == "completed" and status == "failed":
        return None
    status_map[lane] = status
    message = f"{lane.title()} lane {status}"
    event = EventEmitter.progress(f"fresh_{lane}_{status}", message)
    data = event.setdefault("data", {})
    data["lane"] = lane
    data["status"] = status
    data["fresh_pipeline"] = True
    data["reasoning_effort"] = FRESH_RUN_REASONING_EFFORT
    data["ts"] = datetime.utcnow().isoformat()
    if reason:
        data["reason"] = reason
    telemetry.fresh_pipeline_lane(
        lane=lane,
        status=status,
        session_id=getattr(ctx, "session_id", None),
        flow=getattr(pipeline, "flow_label", None),
        reasoning_effort=FRESH_RUN_REASONING_EFFORT,
    )
    return event


def collect_tool_deltas_now(
    pipeline: Any,
    tool_state: Optional[Dict[str, Any]],
    ctx: Optional[Any] = None,
) -> List[Dict[str, Any]]:
    deltas: List[Dict[str, Any]] = []
    if not tool_state or not tool_state.get("active", False):
        return deltas
    queue: asyncio.Queue = tool_state["queue"]
    while True:
        try:
            event = queue.get_nowait()
        except QueueEmpty:
            break
        if event is TOOL_QUEUE_SENTINEL:
            tool_state["active"] = False
            runtime = tool_state.get("runtime")
            if isinstance(runtime, ToolParallelRuntime):
                runtime.active = False
            break
        deltas.append(pipeline._mark_delta_event(event, ctx))  # type: ignore[attr-defined]
    return deltas


async def drain_tool_state_async(
    pipeline: Any,
    tool_state: Optional[Dict[str, Any]],
    ctx: Optional[Any] = None,
) -> AsyncGenerator[Dict[str, Any], None]:
    if not tool_state or not tool_state.get("active", False):
        return
    queue: asyncio.Queue = tool_state["queue"]
    while tool_state.get("active", False):
        event = await queue.get()
        if event is TOOL_QUEUE_SENTINEL:
            tool_state["active"] = False
            runtime = tool_state.get("runtime")
            if isinstance(runtime, ToolParallelRuntime):
                runtime.active = False
            break
        yield pipeline._mark_delta_event(event, ctx)  # type: ignore[attr-defined]
    for pending in collect_tool_deltas_now(pipeline, tool_state, ctx):
        yield pending

