from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Sequence, Tuple, TYPE_CHECKING, AsyncGenerator

from analytics.core.events import EventEmitter

if TYPE_CHECKING:  # pragma: no cover - import guard for typing only
    from .planner_executor import PlannerPhaseContext


@dataclass(frozen=True)
class ToolExecutionContext:
    """Context exposed to tool adapters during fan-out."""

    session_id: str
    query: str
    intent: Any
    plan: Any
    template: Optional[Any]
    configs: Dict[str, Any]


@dataclass
class ToolAdapterResult:
    """Normalized result emitted by a tool adapter."""

    name: str
    status: str
    payload: Dict[str, Any]
    error: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    elapsed_ms: Optional[int] = None
    fatal: bool = False


class BaseToolAdapter:
    """Minimal async interface each adapter must implement."""

    name: str = "tool"

    async def execute(self, context: ToolExecutionContext) -> ToolAdapterResult:  # pragma: no cover - interface
        raise NotImplementedError


class _FatalAdapterException(Exception):
    """Signal used to cancel sibling adapters when a fatal error occurs."""

    def __init__(self, result: ToolAdapterResult) -> None:
        super().__init__(result.error or "fatal tool adapter error")
        self.result = result


class ToolTaskGroup:
    """Coordinate tool adapters with bounded concurrency."""

    def __init__(self, adapters: Sequence[BaseToolAdapter], *, concurrency_limit: int = 5) -> None:
        self._adapters: Sequence[BaseToolAdapter] = adapters
        self._semaphore = asyncio.Semaphore(max(1, concurrency_limit))

    async def run(self, context: ToolExecutionContext) -> List[ToolAdapterResult]:
        results: Dict[int, ToolAdapterResult] = {}

        def _record(index: int, result: ToolAdapterResult) -> None:
            results.setdefault(index, result)

        async def _runner(index: int, adapter: BaseToolAdapter) -> None:
            started = datetime.utcnow()
            await self._semaphore.acquire()
            try:
                try:
                    result = await adapter.execute(context)
                except asyncio.CancelledError:
                    cancelled_at = datetime.utcnow()
                    cancel_result = ToolAdapterResult(
                        name=getattr(adapter, "name", f"adapter_{index}"),
                        status="cancelled",
                        payload={},
                        error="cancelled due to fatal sibling",
                        started_at=started.isoformat(),
                        completed_at=cancelled_at.isoformat(),
                        elapsed_ms=int((cancelled_at - started).total_seconds() * 1000),
                        fatal=False,
                    )
                    _record(index, cancel_result)
                    raise
                except Exception as exc:  # pragma: no cover - defensive fan-out guard
                    result = ToolAdapterResult(
                        name=getattr(adapter, "name", f"adapter_{index}"),
                        status="error",
                        payload={},
                        error=str(exc),
                        fatal=True,
                    )
                completed = datetime.utcnow()
                if result.started_at is None:
                    result.started_at = started.isoformat()
                if result.completed_at is None:
                    result.completed_at = completed.isoformat()
                if result.elapsed_ms is None:
                    result.elapsed_ms = int((completed - started).total_seconds() * 1000)
                _record(index, result)
                if result.status == "error" and result.fatal:
                    raise _FatalAdapterException(result)
            finally:
                self._semaphore.release()

        fatal_detected = False
        try:
            async with asyncio.TaskGroup() as tg:
                for idx, adapter in enumerate(self._adapters):
                    tg.create_task(_runner(idx, adapter))
        except _FatalAdapterException:
            fatal_detected = True
        except Exception:
            raise

        ordered = [results[idx] for idx in sorted(results.keys())]

        # Ensure adapters that never started (e.g., cancelled before acquiring semaphore) appear as cancelled
        if len(ordered) < len(self._adapters):
            for idx, adapter in enumerate(self._adapters):
                if idx not in results:
                    ordered.append(
                        ToolAdapterResult(
                            name=getattr(adapter, "name", f"adapter_{idx}"),
                            status="cancelled",
                            payload={},
                            error="cancelled before start",
                            fatal=False,
                        )
                    )
            ordered.sort(key=lambda res: self._adapters.index(next(a for a in self._adapters if getattr(a, "name", "") == res.name)))

        if fatal_detected:
            # flag results so downstream callers can surface cancellation reason
            for res in ordered:
                if res.status == "cancelled" and res.error == "cancelled due to fatal sibling":
                    res.payload.setdefault("cancelled", True)
        return ordered


# ----------------------------------------------------------------------------
# Default adapter implementations
# ----------------------------------------------------------------------------


class SQLPlannerAdapter(BaseToolAdapter):
    name = "sql_planner"

    async def execute(self, context: ToolExecutionContext) -> ToolAdapterResult:
        plan = context.plan
        metrics = getattr(plan, "metrics", []) or []
        comparison = getattr(plan, "comparison", None)
        granularity = getattr(plan, "granularity", None)
        payload = {
            "intent": getattr(context.intent, "intent_key", None),
            "metrics_count": len(metrics),
            "comparison": comparison,
            "granularity": granularity,
        }
        return ToolAdapterResult(name=self.name, status="planned", payload=payload)


class ChartBuilderAdapter(BaseToolAdapter):
    name = "chart_builder"

    async def execute(self, context: ToolExecutionContext) -> ToolAdapterResult:
        plan = context.plan
        fields = {
            "group_by": getattr(plan, "group_by", []),
            "timeframe": getattr(plan, "timeframe", None),
        }
        return ToolAdapterResult(name=self.name, status="awaiting_data", payload=fields)


class WebRetrieverAdapter(BaseToolAdapter):
    name = "web_retriever"

    async def execute(self, context: ToolExecutionContext) -> ToolAdapterResult:
        slots = getattr(context.intent, "slots_detected", {}) or {}
        payload = {
            "query_terms": slots.get("original_query") or context.query,
            "ready": False,
        }
        return ToolAdapterResult(name=self.name, status="queued", payload=payload)


class StockTrackerAdapter(BaseToolAdapter):
    name = "stock_tracker"

    async def execute(self, context: ToolExecutionContext) -> ToolAdapterResult:
        slots = getattr(context.intent, "slots_detected", {}) or {}
        company = slots.get("company")
        payload = {
            "tickers": ([company] if company else []),
            "ready": False,
        }
        return ToolAdapterResult(name=self.name, status="queued", payload=payload)


class NarrativeSynthesizerAdapter(BaseToolAdapter):
    name = "narrative_synthesizer"

    async def execute(self, context: ToolExecutionContext) -> ToolAdapterResult:
        plan = context.plan
        metrics = getattr(plan, "metrics", []) or []
        payload = {
            "preview": f"Preparing narrative for {', '.join(metrics[:3]) or 'selected metrics'}",
        }
        return ToolAdapterResult(name=self.name, status="drafting", payload=payload)


_DEFAULT_ADAPTERS: Tuple[BaseToolAdapter, ...] = (
    SQLPlannerAdapter(),
    ChartBuilderAdapter(),
    WebRetrieverAdapter(),
    StockTrackerAdapter(),
    NarrativeSynthesizerAdapter(),
)


def get_default_tool_adapters() -> Tuple[BaseToolAdapter, ...]:
    return _DEFAULT_ADAPTERS


async def run_tool_parallelism(ctx: "PlannerPhaseContext") -> AsyncGenerator[Dict[str, Any], None]:
    """Execute the registered tool adapters and yield telemetry events."""

    intent = getattr(ctx, "intent", None)
    plan = getattr(ctx, "plan", None) or getattr(ctx, "provisional_plan", None)
    if not intent or not plan:
        return

    adapters = get_default_tool_adapters()
    execution_context = ToolExecutionContext(
        session_id=ctx.session_id,
        query=ctx.query,
        intent=intent,
        plan=plan,
        template=getattr(ctx, "template", None),
        configs=getattr(ctx, "configs", {}),
    )

    yield {
        "event": "tool_parallel_start",
        "data": {
            "tool_group": "single_agent",
            "parallel_group": "tool_fanout",
            "tool_count": len(adapters),
            "ts": datetime.utcnow().isoformat(),
        },
    }

    task_group = ToolTaskGroup(adapters)
    results = await task_group.run(execution_context)

    fatal_detected = any(result.status == "error" and result.fatal for result in results)

    for result in results:
        yield {
            "event": "tool_parallel_result",
            "data": {
                "tool": result.name,
                "status": result.status,
                "payload": result.payload,
                "error": result.error,
                "elapsed_ms": result.elapsed_ms,
                "fatal": result.fatal,
                "parallel_group": "tool_fanout",
                "tool_group": "single_agent",
                "ts": datetime.utcnow().isoformat(),
            },
        }

    completion_status = "cancelled" if fatal_detected else "complete"
    yield {
        "event": "tool_parallel_complete",
        "data": {
            "tool_group": "single_agent",
            "parallel_group": "tool_fanout",
            "status": completion_status,
            "ts": datetime.utcnow().isoformat(),
        },
    }
