# --- Analytics Function/Class Map ---
# Class: ToolParallelRuntime
#   Role: Handles ToolParallelRuntime logic for analytics.flows.planner.fanout.
#   Called from: analytics.flows.multi_agent, analytics.flows.planner, analytics.flows.planner_executor, analytics.flows.single_agent_tools, +2 more
#   Collaborators: contextlib.suppress
#   Why: Keeps analytics.flows.planner.fanout from duplicating ToolParallelRuntime behavior across flows.
# Function: start_tool_parallelism
#   Role: Handles start tool parallelism logic for analytics.flows.planner.fanout.
#   Called from: analytics.flows.planner, analytics.flows.planner_executor, tests.analytics.test_planner_executor_sql
#   Invokes: asyncio.Queue, asyncio.create_task, analytics.flows.planner.fanout.ToolParallelRuntime, analytics.flows.tooling.run_tool_parallelism
#   Why: Keeps analytics.flows.planner.fanout from duplicating start tool parallelism behavior across flows.
# Function: derive_accessory_events
#   Role: Handles derive accessory events logic for analytics.flows.planner.fanout.
#   Called from: analytics.flows.planner, analytics.flows.planner_executor
#   Invokes: analytics.validators.sanitize_for_json
#   Why: Keeps analytics.flows.planner.fanout from duplicating derive accessory events behavior across flows.
# --- End Analytics Function/Class Map ---
from __future__ import annotations

import asyncio
import contextlib
from asyncio import Task
from dataclasses import dataclass
from datetime import datetime
from typing import (
    Any,
    Callable,
    Dict,
    Iterable,
    List,
    Mapping,
    Optional,
    Sequence,
)

from analytics.validators import sanitize_for_json

from ..tooling import run_tool_parallelism

try:  # pragma: no cover - typing only
    from typing import TYPE_CHECKING
except ImportError:  # pragma: no cover - fallback for minimal environments
    TYPE_CHECKING = False  # type: ignore[assignment]

if TYPE_CHECKING:  # pragma: no cover - typing only
    from analytics.flows.planner.context import PlannerPhaseContext


TOOL_QUEUE_SENTINEL: object = object()


@dataclass
class ToolParallelRuntime:
    runner: Optional[Task]
    dispatcher: Optional[Task]
    raw_queue: asyncio.Queue
    queue: asyncio.Queue
    active: bool = True

    async def close(self) -> None:
        """Cancel background tasks and mark the runtime inactive."""
        self.active = False
        for task in (self.dispatcher, self.runner):
            if task and not task.done():
                task.cancel()
                with contextlib.suppress(Exception):
                    await task


def start_tool_parallelism(
    ctx: "PlannerPhaseContext",
    *,
    ingest_tool_event: Callable[["PlannerPhaseContext", Dict[str, Any]], Iterable[Dict[str, Any]]],
    adapters: Optional[Sequence[Any]] = None,
    concurrency_override: Optional[int] = None,
) -> ToolParallelRuntime:
    raw_queue: asyncio.Queue = asyncio.Queue()
    dispatch_queue: asyncio.Queue = asyncio.Queue()

    async def runner() -> None:
        try:
            async for event in run_tool_parallelism(
                ctx,
                adapters=adapters,
                concurrency_override=concurrency_override,
            ):
                derived_events = ingest_tool_event(ctx, event) or []
                await raw_queue.put(event)
                for derived_event in derived_events:
                    await raw_queue.put(derived_event)
        finally:
            await raw_queue.put(TOOL_QUEUE_SENTINEL)

    async def dispatcher() -> None:
        sentinel_forwarded = False
        try:
            while True:
                item = await raw_queue.get()
                await dispatch_queue.put(item)
                if item is TOOL_QUEUE_SENTINEL:
                    sentinel_forwarded = True
                    break
        finally:
            if not sentinel_forwarded:
                await dispatch_queue.put(TOOL_QUEUE_SENTINEL)

    runner_task = asyncio.create_task(runner())
    dispatcher_task = asyncio.create_task(dispatcher())
    return ToolParallelRuntime(
        runner=runner_task,
        dispatcher=dispatcher_task,
        raw_queue=raw_queue,
        queue=dispatch_queue,
    )


def derive_accessory_events(
    ctx: "PlannerPhaseContext",
    *,
    tool_name: str,
    status: str,
    data: Mapping[str, Any],
    flow_mode_value: str,
    mark_delta_event: Callable[[Dict[str, Any], Optional["PlannerPhaseContext"]], Dict[str, Any]],
    compose_stock_ready_payload: Callable[["PlannerPhaseContext"], Optional[Dict[str, Any]]],
    compose_web_ready_payload: Callable[["PlannerPhaseContext"], Optional[Dict[str, Any]]],
) -> List[Dict[str, Any]]:
    derived: List[Dict[str, Any]] = []
    if status not in {"completed", "complete", "success"}:
        return derived

    payload = data.get("payload") or {}
    schedule_stage = str(data.get("schedule_stage") or "hedged_accessories")
    parallel_group = str(data.get("parallel_group") or "tool_fanout")
    completed_at = data.get("completed_at") or data.get("ts")

    def _base_event(name: str, raw_payload: Optional[Mapping[str, Any]], *, lane: str) -> Optional[Dict[str, Any]]:
        if not isinstance(raw_payload, Mapping):
            return None
        sanitized_payload = sanitize_for_json(dict(raw_payload)) or {}
        if not isinstance(sanitized_payload, dict):
            return None
        sanitized_payload.setdefault("schedule_stage", schedule_stage)
        sanitized_payload.setdefault("parallel_group", parallel_group)
        sanitized_payload.setdefault("lane", lane)
        sanitized_payload.setdefault("flow_mode", flow_mode_value)
        sanitized_payload.setdefault("ts", completed_at or datetime.utcnow().isoformat())
        return {"event": name, "data": sanitized_payload}

    if tool_name in {"stock_tracker"} or tool_name.startswith("market_question"):
        if getattr(ctx, "stock_widget_seeded", False) or (isinstance(payload, Mapping) and payload.get("stock_widget")):
            stock_payload = compose_stock_ready_payload(ctx)
            if not stock_payload and isinstance(payload, Mapping) and payload.get("stock_widget"):
                stock_payload = {
                    "stock_widget": sanitize_for_json(payload.get("stock_widget")),
                    "reused": bool(payload.get("from_cache") or data.get("reused")),
                }
            if stock_payload:
                stock_payload.setdefault("reused", bool(getattr(ctx, "reused_stock", False)))
                event = _base_event("stock_ready", stock_payload, lane="market")
                already_emitted = bool(getattr(ctx, "stock_ready_emitted", False))
                reuse_flag = bool(stock_payload.get("reused"))
                if event and (not already_emitted or reuse_flag):
                    derived.append(mark_delta_event(event, ctx))
                    ctx.stock_ready_emitted = True  # type: ignore[attr-defined]

    if tool_name.startswith("web_retriever"):
        if getattr(ctx, "web_search_seeded", False) or (isinstance(payload, Mapping) and payload.get("ready")):
            web_payload = compose_web_ready_payload(ctx)
            if not web_payload and isinstance(payload, Mapping):
                web_payload = dict(payload)
                web_payload["reused"] = bool(payload.get("from_cache") or data.get("reused"))
            if web_payload:
                web_payload.setdefault("reused", bool(getattr(ctx, "reused_web", False)))
                search_id = web_payload.get("search_id") or web_payload.get("searchId")
                if not search_id and isinstance(web_payload.get("web_context"), Mapping):
                    context_payload = web_payload.get("web_context") or {}
                    search_id = context_payload.get("search_id") or context_payload.get("searchId")
                normalized_search_id = str(search_id).strip() if search_id else ""
                seen_search_ids: set[str] = getattr(ctx, "_fanout_search_ids", set())
                if normalized_search_id:
                    if normalized_search_id in seen_search_ids:
                        return derived
                    seen_search_ids.add(normalized_search_id)
                    setattr(ctx, "_fanout_search_ids", seen_search_ids)
                event = _base_event("web_ready", web_payload, lane="web")
                if event and (not getattr(ctx, "web_ready_emitted", False) or web_payload.get("reused")):
                    derived.append(mark_delta_event(event, ctx))
                    ctx.web_ready_emitted = True  # type: ignore[attr-defined]

    return derived
