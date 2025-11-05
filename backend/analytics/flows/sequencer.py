from __future__ import annotations

import inspect
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import (
    Any,
    AsyncGenerator,
    Awaitable,
    Callable,
    Dict,
    Iterable,
    List,
    Optional,
    Sequence,
    Tuple,
    Union,
)

from .orchestrator_protocol import FlowOrchestrator

logger = logging.getLogger(__name__)

SequencerEvent = Dict[str, Any]
EventCallback = Callable[[SequencerEvent], None]


LANE_STATUS_PENDING = "pending"
LANE_STATUS_RUNNING = "running"
LANE_STATUS_COMPLETED = "completed"
LANE_STATUS_SKIPPED = "skipped"
LANE_STATUS_FAILED = "failed"


@dataclass
class LaneState:
    name: str
    required: bool = True
    status: str = LANE_STATUS_PENDING
    completed: bool = False
    success: bool = False
    error: Optional[str] = None


@dataclass
class SequencerConfig:
    lane_order: Sequence[str]
    optional_lanes: Sequence[str] = ("web", "market")

DEFAULT_OPTIONAL_LANES: Tuple[str, ...] = ("web", "market")
LANE_TOOL_MAP: Dict[str, Tuple[str, ...]] = {
    "market": ("market_question_a", "market_question_b", "stock_tracker"),
    "web": ("web_retriever",),
}
LANE_TOOL_LOOKUP: Dict[str, str] = {
    tool.lower(): lane for lane, tools in LANE_TOOL_MAP.items() for tool in tools
}


class PlannerEventBus:
    """Fan out sequencer lifecycle events to registered subscribers."""

    def __init__(self, emit: Optional[EventCallback] = None) -> None:
        self._subscribers: List[EventCallback] = []
        if emit is not None:
            self._subscribers.append(emit)

    def subscribe(self, callback: EventCallback) -> None:
        if callback in self._subscribers:
            return
        self._subscribers.append(callback)

    def publish(self, event: SequencerEvent) -> None:
        for callback in list(self._subscribers):
            try:
                callback(event)
            except Exception:  # pragma: no cover - defensive logging
                logger.exception("PlannerEventBus subscriber raised")

    def emit_lane_transition(
        self,
        *,
        lane: str,
        status: str,
        success: Optional[bool] = None,
        error: Optional[str] = None,
        reused: Optional[bool] = None,
        reason: Optional[str] = None,
    ) -> None:
        payload: SequencerEvent = {
            "event": "planner_lane_transition",
            "data": {
                "lane": lane,
                "status": status,
                "ts": datetime.now(timezone.utc).isoformat(),
            },
        }
        data = payload["data"]
        if success is not None:
            data["success"] = success
        if error:
            data["error"] = error
        if reused is not None:
            data["reused"] = reused
        if reason:
            data["reason"] = reason
        self.publish(payload)


class PlannerSequencer:
    """
    Enforces the canonical planner lane ordering while delegating execution to a
    FlowOrchestrator implementation.

    Stages:
      1. Intent + clarification (blocking)
      2. SQL generation / execution + chart synthesis
      3. Web research fan-out (async)
      4. Market/stock refresh fan-out (async)
      5. Analysis synthesis once upstream lanes report completion
    """

    def __init__(
        self,
        orchestrator: FlowOrchestrator,
        *,
        emit: Optional[EventCallback] = None,
        lane_order: Optional[Sequence[str]] = None,
        lane_refresh_required: Optional[Dict[str, bool]] = None,
    ) -> None:
        self._orchestrator = orchestrator
        self._emit_callback = emit or (lambda event: None)
        self._event_bus = PlannerEventBus(self._emit_callback)
        self._lane_order: List[str] = list(
            lane_order
            or (
                "intent",
                "sql",
                "web",
                "market",
                "analysis",
            )
        )
        self._lane_refresh_required: Dict[str, bool] = {
            lane: bool(flag)
            for lane, flag in (lane_refresh_required or {}).items()
        }
        optional = set(getattr(orchestrator, "optional_lanes", DEFAULT_OPTIONAL_LANES))
        self._optional_lanes = optional
        self._lane_states: Dict[str, LaneState] = {}
        for lane in self._lane_order:
            required = lane not in optional
            if lane in optional:
                required = bool(self._lane_refresh_required.get(lane, True))
            self._lane_states[lane] = LaneState(name=lane, required=required)
        self._lane_dependencies: Dict[str, Tuple[str, ...]] = {
            "sql": ("intent",),
            "web": ("sql",),
            "market": ("sql",),
            "analysis": ("sql", "web", "market"),
        }

    @property
    def event_bus(self) -> PlannerEventBus:
        return self._event_bus

    async def run(self) -> AsyncGenerator[SequencerEvent, None]:
        """
        Execute the sequencer, yielding events emitted by the orchestrator while
        preserving the canonical ordering and lane dependencies.
        """
        async for event in self._run_intent_stage():
            yield event

        async for event in self._run_sql_stage():
            yield event

        async for event in self._kickoff_parallel_lanes():
            yield event

        async for event in self._await_analysis_stage():
            yield event

    async def _run_intent_stage(self) -> AsyncGenerator[SequencerEvent, None]:
        lane = "intent"
        self._start_lane(lane)
        try:
            async for event in self._decorate_stream(self._orchestrator.run_intent_stage):
                yield event
        except Exception as exc:
            self._finish_lane(lane, success=False, error=str(exc))
            raise
        else:
            self._finish_lane(lane, success=True)

    async def _run_sql_stage(self) -> AsyncGenerator[SequencerEvent, None]:
        lane = "sql"
        self._start_lane(lane)
        try:
            async for event in self._decorate_stream(self._orchestrator.run_sql_stage):
                yield event
        except Exception as exc:
            self._finish_lane(lane, success=False, error=str(exc))
            raise
        else:
            self._finish_lane(lane, success=True)

    async def _kickoff_parallel_lanes(self) -> AsyncGenerator[SequencerEvent, None]:
        async for event in self._run_lane("web", self._orchestrator.run_web_stage):
            yield event
        async for event in self._run_lane("market", self._orchestrator.run_market_stage):
            yield event

    async def _await_analysis_stage(self) -> AsyncGenerator[SequencerEvent, None]:
        lane = "analysis"
        if not self._dependencies_met(lane):
            pending = tuple(self._pending_lanes())
            logger.debug("Delaying analysis lane until dependencies complete: pending=%s", pending)
        self._start_lane(lane)
        try:
            async for event in self._decorate_stream(self._orchestrator.run_analysis_stage):
                yield event
        except Exception as exc:
            self._finish_lane(lane, success=False, error=str(exc))
            raise
        else:
            self._finish_lane(lane, success=True)

    async def _run_lane(
        self,
        lane: str,
        runner: Callable[[], AsyncGenerator[SequencerEvent, None]],
    ) -> AsyncGenerator[SequencerEvent, None]:
        if lane not in self._lane_states:
            return
        state = self._lane_states[lane]
        if not state.required and lane in self._optional_lanes and not self._should_run_lane(lane):
            self._skip_lane(lane, reason="cached_reuse")
            return
        if not self._dependencies_met(lane):
            logger.debug(
                "Sequencer invoked lane '%s' before dependencies settled; pending=%s",
                lane,
                tuple(self._pending_lanes()),
            )
        self._start_lane(lane)
        try:
            async for event in self._decorate_stream(runner):
                yield event
        except Exception as exc:
            self._finish_lane(lane, success=False, error=str(exc))
            raise
        else:
            self._finish_lane(lane, success=True)

    async def _decorate_stream(
        self,
        runner: Callable[[], AsyncGenerator[SequencerEvent, None]],
    ) -> AsyncGenerator[SequencerEvent, None]:
        async for event in _iter_async_generator(runner()):
            decorated = self._decorate_event(event)
            self._emit_callback(decorated)
            yield decorated

    def _decorate_event(self, event: SequencerEvent) -> SequencerEvent:
        if not isinstance(event, dict):
            return event
        metadata = self._orchestrator.event_metadata() or {}
        data = event.setdefault("data", {})
        for key, value in metadata.items():
            data.setdefault(key, value)
        pending = list(self._pending_lanes())
        if pending:
            data.setdefault("pending_lanes", pending)
        return event

    def _pending_lanes(self) -> Iterable[str]:
        return (
            state.name
            for state in self._lane_states.values()
            if not state.completed and state.required
        )

    def _should_run_lane(self, lane: str) -> bool:
        state = self._lane_states.get(lane)
        if state is None:
            return False
        if lane not in self._optional_lanes:
            return True
        if lane in self._lane_refresh_required:
            return bool(self._lane_refresh_required[lane])
        try:
            pending_iterable = self._orchestrator.pending_lanes()
        except Exception:  # pragma: no cover - defensive logging
            logger.exception("Failed to query orchestrator pending lanes")
            pending_iterable = ()
        pending = {entry for entry in pending_iterable}
        return lane in pending or state.required

    def _dependencies_met(self, lane: str) -> bool:
        dependencies = self._lane_dependencies.get(lane, ())
        return all(self._lane_states.get(dep, LaneState(dep)).completed for dep in dependencies)

    def _start_lane(self, lane: str) -> None:
        state = self._lane_states.get(lane)
        if state is None or state.completed:
            return
        state.status = LANE_STATUS_RUNNING
        self._event_bus.emit_lane_transition(lane=lane, status=LANE_STATUS_RUNNING)

    def _finish_lane(
        self,
        lane: str,
        *,
        success: bool,
        error: Optional[str] = None,
        reused: Optional[bool] = None,
    ) -> None:
        state = self._lane_states.get(lane)
        if state is None:
            return
        state.completed = True
        state.success = success
        state.error = error
        state.status = LANE_STATUS_COMPLETED if success else LANE_STATUS_FAILED
        try:
            self._orchestrator.lane_complete(
                lane,
                success=success,
                reused=bool(reused),
                reason=error,
            )
        except Exception:  # pragma: no cover - defensive logging
            logger.exception("Failed to notify orchestrator of lane completion: lane=%s", lane)
        self._event_bus.emit_lane_transition(
            lane=lane,
            status=state.status,
            success=success,
            error=error,
            reused=reused,
        )

    def _skip_lane(self, lane: str, *, reason: str = "cached") -> None:
        state = self._lane_states.get(lane)
        if state is None:
            return
        state.required = False
        state.completed = True
        state.success = True
        state.error = None
        state.status = LANE_STATUS_SKIPPED
        try:
            self._orchestrator.lane_complete(
                lane,
                success=True,
                reused=True,
                reason=reason,
            )
        except Exception:  # pragma: no cover - defensive logging
            logger.exception("Failed to notify orchestrator of skipped lane completion: lane=%s", lane)
        self._event_bus.emit_lane_transition(
            lane=lane,
            status=LANE_STATUS_SKIPPED,
            success=True,
            reused=True,
            reason=reason,
        )


async def _iter_async_generator(
    obj: Union[AsyncGenerator[SequencerEvent, None], Awaitable[Any]],
) -> AsyncGenerator[SequencerEvent, None]:
    if inspect.isawaitable(obj) and not hasattr(obj, "__aiter__"):
        awaited = await obj  # type: ignore[func-returns-value]
        async for item in _iter_async_generator(awaited):
            yield item
        return
    if not hasattr(obj, "__aiter__"):
        raise TypeError("Expected async generator for sequencer runner")
    async for item in obj:  # type: ignore[attr-defined]
        yield item
