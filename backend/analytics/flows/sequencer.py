# --- Analytics Function/Class Map ---
# Class: LaneState
#   Role: Handles LaneState logic for analytics.flows.sequencer.
#   Called from: Internal to analytics.flows.sequencer
#   Collaborators: Internal helpers only
#   Why: Keeps analytics.flows.sequencer from duplicating LaneState behavior across flows.
# Class: SequencerConfig
#   Role: Handles SequencerConfig logic for analytics.flows.sequencer.
#   Called from: Internal to analytics.flows.sequencer
#   Collaborators: Internal helpers only
#   Why: Keeps analytics.flows.sequencer from duplicating SequencerConfig behavior across flows.
# Class: PlannerEventBus
#   Role: Fan out sequencer lifecycle events to registered subscribers.
#   Called from: analytics.flows.multi_agent, analytics.flows.workflow
#   Collaborators: Internal helpers only
#   Why: Supports downstream analytics workflows that rely on PlannerEventBus.
# Class: PlannerSequencer
#   Role: Enforces the canonical planner lane ordering while delegating execution to a FlowOrchestrator implementation.
#   Called from: analytics.flows.multi_agent, analytics.flows.single_agent_tools, analytics.flows.workflow, tests.analytics.test_multi_agent_flow, +3 more
#   Collaborators: analytics.flows.sequencer.PlannerEventBus, asyncio.Queue, analytics.flows.sequencer._iter_async_generator, analytics.flows.sequencer.LaneState, +2 more
#   Why: Stages: 1.
# Function: _iter_async_generator
#   Role: Handles iter async generator logic for analytics.flows.sequencer.
#   Called from: Internal to analytics.flows.sequencer
#   Invokes: inspect.isawaitable, analytics.flows.sequencer._iter_async_generator
#   Why: Keeps analytics.flows.sequencer from duplicating iter async generator behavior across flows.
# --- End Analytics Function/Class Map ---
from __future__ import annotations

import asyncio
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
    Set,
    Tuple,
    Union,
    Mapping,
)

from .orchestrator_protocol import FlowOrchestrator

logger = logging.getLogger(__name__)

SequencerEvent = Dict[str, Any]
EventCallback = Callable[[SequencerEvent], None]
RetryCallback = Callable[[str, int, Optional[str], Optional[str], Optional[Mapping[str, Any]]], None]


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
    reused: Optional[bool] = None


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
        # Supervisor adapters (single and multi-agent) register here to mirror cache and telemetry events.
        if callback in self._subscribers:
            return
        self._subscribers.append(callback)

    def unsubscribe(self, callback: EventCallback) -> None:
        if callback in self._subscribers:
            self._subscribers.remove(callback)

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

    def emit_lane_reused(
        self,
        *,
        lane: str,
        reason: Optional[str] = None,
        metadata: Optional[Mapping[str, Any]] = None,
    ) -> None:
        payload: SequencerEvent = {
            "event": "lane_reused",
            "data": {
                "lane": lane,
                "reused": True,
                "status": "reused",
                "ts": datetime.now(timezone.utc).isoformat(),
                "source": "sequencer",
            },
        }
        data = payload["data"]
        if reason:
            data["reason"] = reason
        if metadata:
            for key, value in metadata.items():
                if value is not None:
                    data[key] = value
        self.publish(payload)

    def emit_lane_retry(
        self,
        *,
        lane: str,
        attempt: int,
        reason: Optional[str] = None,
        error: Optional[str] = None,
        metadata: Optional[Mapping[str, Any]] = None,
    ) -> None:
        payload: SequencerEvent = {
            "event": "planner_lane_retry",
            "data": {
                "lane": lane,
                "attempt": attempt,
                "ts": datetime.now(timezone.utc).isoformat(),
            },
        }
        data = payload["data"]
        if reason:
            data["reason"] = reason
        if error:
            data["error"] = error
        if metadata:
            data["metadata"] = dict(metadata)
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
        # Multi-agent flows attach additional subscribers to the event bus to propagate supervisor telemetry.
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
            str(lane or "").strip().lower(): bool(flag)
            for lane, flag in (lane_refresh_required or {}).items()
        }
        optional = set(getattr(orchestrator, "optional_lanes", DEFAULT_OPTIONAL_LANES))
        self._optional_lanes = optional
        self._lane_states: Dict[str, LaneState] = {}
        self._lane_presentations: Dict[str, str] = {}
        self._revision_targets: Set[str] = set()
        for lane in self._lane_order:
            required = lane not in optional
            if lane in optional:
                required = bool(self._lane_refresh_required.get(lane, True))
            self._lane_states[lane] = LaneState(name=lane, required=required)
            self._lane_presentations[lane] = "pending"
            if lane in optional and not required:
                self._skip_lane(lane, reason="prefill_reuse")
        self._lane_dependencies: Dict[str, Tuple[str, ...]] = {
            "sql": ("intent",),
            "web": ("sql",),
            "market": ("sql",),
            "analysis": ("sql", "web", "market"),
        }
        self._retry_callbacks: List[RetryCallback] = []
        if self._lane_refresh_required:
            self.update_lane_requirements(self._lane_refresh_required, emit=False)
        self._parallel_lane_queue: Optional[asyncio.Queue[Optional[SequencerEvent]]] = None
        self._parallel_lane_task: Optional[asyncio.Task[None]] = None
        self._parallel_lane_started = False
        self._parallel_fanout_enabled = False

    @property
    def event_bus(self) -> PlannerEventBus:
        return self._event_bus

    def prefill_lane_states(self, lane_states: Mapping[str, str]) -> None:
        """
        Seed lane readiness before the sequencer run begins. Lanes marked for
        reuse/cached will emit skipped transitions immediately so downstream
        consumers observe parity with pre-existing planner behaviour.
        """
        for lane, raw_status in lane_states.items():
            state = self._lane_states.get(lane)
            if state is None:
                continue
            normalized = str(raw_status or "").strip().lower()
            if normalized in {"reused", "cached", "skip", "skipped"}:
                if not state.completed:
                    self._skip_lane(lane, reason="prefill_reuse")
                continue
            if normalized:
                self._lane_presentations[lane] = normalized
            state.required = True
            state.completed = False
            state.success = False
            state.error = None
            state.reused = None
            state.status = LANE_STATUS_PENDING
        self._recompute_presentations(preserve_queued=True)

    def update_lane_requirements(
        self,
        requirements: Mapping[str, Any],
        *,
        emit: bool = True,
    ) -> None:
        """
        Synchronize lane refresh requirements, ensuring optional lanes marked for
        reuse are reflected in sequencer state and downstream events.
        """
        for raw_lane, flag in requirements.items():
            lane = str(raw_lane or "").strip().lower()
            if not lane or lane not in self._lane_states:
                continue
            state = self._lane_states[lane]
            normalized = bool(flag)
            previous_required = state.required
            self._lane_refresh_required[lane] = normalized
            if lane not in self._optional_lanes:
                state.required = True
                if previous_required is False:
                    state.status = LANE_STATUS_PENDING
                    state.completed = False
                    state.success = False
                    state.reused = None
                    state.error = None
                continue
            state.required = normalized
            if not normalized:
                if state.status != LANE_STATUS_SKIPPED or not state.completed or not state.reused:
                    state.completed = True
                    state.success = True
                    state.error = None
                    state.status = LANE_STATUS_SKIPPED
                    state.reused = True
                    if emit:
                        self._event_bus.emit_lane_transition(
                            lane=lane,
                            status=LANE_STATUS_SKIPPED,
                            success=True,
                            reused=True,
                            reason="prefill_reuse",
                        )
                continue
            if previous_required is False or state.status == LANE_STATUS_SKIPPED:
                state.completed = False
                state.success = False
                state.error = None
                state.reused = None
                state.status = LANE_STATUS_PENDING
                if emit:
                    self._event_bus.emit_lane_transition(
                        lane=lane,
                        status=LANE_STATUS_PENDING,
                        reason="refresh_required",
                    )
            self._update_presentation(lane, preserve_queued=True)

    def mark_lane_complete(
        self,
        lane: str,
        *,
        result: Optional[Mapping[str, Any]] = None,
        success: Optional[bool] = None,
        reused: Optional[bool] = None,
        error: Optional[str] = None,
    ) -> None:
        """
        Update cached metadata for a lane based on downstream planner emissions.
        """
        normalized = str(lane or "").strip().lower()
        state = self._lane_states.get(normalized)
        if state is None:
            return
        payload: Dict[str, Any] = dict(result or {})
        if reused is None:
            reused_value = payload.get("reused")
            if reused_value is None:
                status_value = payload.get("status")
                if isinstance(status_value, str):
                    lowered = status_value.strip().lower()
                    if lowered in {"cached", "reused"}:
                        reused_value = True
            reused = bool(reused_value) if reused_value is not None else None
        if success is None and "success" in payload:
            success_field = payload.get("success")
            if success_field is not None:
                success = bool(success_field)
        if success is None and "status" in payload:
            status_field = payload.get("status")
            if isinstance(status_field, str):
                lowered = status_field.strip().lower()
                if lowered in {"failed", "error"}:
                    success = False
                elif lowered:
                    success = True
        if error is None:
            error_field = payload.get("error") or payload.get("reason")
            if isinstance(error_field, str):
                error = error_field
        if reused is not None:
            state.reused = bool(reused)
        if success is not None:
            state.success = bool(success)
        if error is not None:
            state.error = error
        lane_is_running = state.status == LANE_STATUS_RUNNING
        fast_path_ready = (
            lane_is_running
            and not state.completed
            and normalized == "sql"
            and reused is True
        )
        should_finalize = (
            not state.completed
            and (
                state.status in {LANE_STATUS_PENDING, LANE_STATUS_SKIPPED}
                or fast_path_ready
            )
            and (reused is True or success is not None or error is not None)
        )
        if should_finalize:
            resolved_success = True if success is None else bool(success)
            self._finish_lane(
                normalized,
                success=resolved_success,
                error=error,
                reused=reused if reused is not None else state.reused,
            )
            return
        self._update_presentation(normalized)

    def lane_snapshot(self) -> Dict[str, Dict[str, Any]]:
        """
        Return an immutable snapshot of current sequencer lane states so callers can
        derive presentation metadata without mutating internal bookkeeping.
        """
        snapshot: Dict[str, Dict[str, Any]] = {}
        for lane, state in self._lane_states.items():
            snapshot[lane] = {
                "status": state.status,
                "required": state.required,
                "completed": state.completed,
                "success": state.success,
                "error": state.error,
                "reused": state.reused,
            }
        return snapshot

    def lane_presentations(self) -> Dict[str, str]:
        """Return user-facing lane readiness states (fresh/reused/pending/etc.)."""
        return dict(self._lane_presentations)

    def set_revision_targets(self, targets: Iterable[str]) -> None:
        normalized: Set[str] = set()
        for target in targets or []:
            if target is None:
                continue
            value = str(target).strip().lower()
            if value:
                normalized.add(value)
        self._revision_targets = normalized
        self._recompute_presentations(preserve_queued=True)

    def on_retry(self, callback: RetryCallback) -> None:
        if callback in self._retry_callbacks:
            return
        self._retry_callbacks.append(callback)

    def remove_retry_callback(self, callback: RetryCallback) -> None:
        if callback in self._retry_callbacks:
            self._retry_callbacks.remove(callback)

    def notify_retry(
        self,
        lane: str,
        *,
        attempt: int,
        reason: Optional[str] = None,
        error: Optional[str] = None,
        metadata: Optional[Mapping[str, Any]] = None,
    ) -> None:
        state = self._lane_states.get(lane)
        if state is not None:
            state.status = LANE_STATUS_RUNNING
            if error:
                state.error = error
        for registered in list(self._retry_callbacks):
            try:
                registered(lane, attempt, reason, error, metadata)
            except Exception:  # pragma: no cover - defensive logging
                logger.exception("PlannerSequencer retry callback failed: lane=%s", lane)
        self._event_bus.emit_lane_retry(
            lane=lane,
            attempt=attempt,
            reason=reason,
            error=error,
            metadata=metadata,
        )
        self._update_presentation(lane)

    async def run(self) -> AsyncGenerator[SequencerEvent, None]:
        """
        Execute the sequencer, yielding events emitted by the orchestrator while
        preserving the canonical ordering and lane dependencies.
        """
        self._initialize_parallel_fanout_state()
        try:
            async for event in self._run_intent_stage():
                yield event

            # If SQL was reused during prefill, trigger accessory fan-out immediately.
            self._maybe_start_parallel_fanout("sql")

            async for event in self._stream_sql_stage_with_parallel():
                yield event

            async for queued in self._drain_parallel_lane_events(block=True):
                yield queued
            await self._wait_for_parallel_lane_task()

            async for event in self._await_analysis_stage():
                yield event
        finally:
            await self._cleanup_parallel_fanout()

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

    async def _stream_sql_stage_with_parallel(self) -> AsyncGenerator[SequencerEvent, None]:
        async for event in self._run_sql_stage():
            yield event
            await asyncio.sleep(0)
            async for queued in self._drain_parallel_lane_events(block=False):
                yield queued

    async def _kickoff_parallel_lanes(self) -> AsyncGenerator[SequencerEvent, None]:
        lanes: Tuple[Tuple[str, Callable[[], AsyncGenerator[SequencerEvent, None]]], ...] = (
            ("web", self._orchestrator.run_web_stage),
            ("market", self._orchestrator.run_market_stage),
        )

        queue: "asyncio.Queue[Optional[SequencerEvent]]" = asyncio.Queue()

        async def _drain_lane(lane_name: str, runner: Callable[[], AsyncGenerator[SequencerEvent, None]]) -> None:
            try:
                async for event in self._run_lane(lane_name, runner):
                    await queue.put(event)
            finally:
                await queue.put(None)

        tasks = [asyncio.create_task(_drain_lane(lane, runner)) for lane, runner in lanes]
        gather_results: List[Any] = []
        finished = 0
        try:
            while finished < len(tasks):
                item = await queue.get()
                if item is None:
                    finished += 1
                    continue
                yield item
        finally:
            for task in tasks:
                if not task.done():
                    task.cancel()
            gather_results = await asyncio.gather(*tasks, return_exceptions=True)
        for result in gather_results:
            if isinstance(result, BaseException):
                raise result

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
        if state.completed:
            logger.debug("Lane '%s' already settled (status=%s); skipping runner.", lane, state.status)
            return
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

    def _initialize_parallel_fanout_state(self) -> None:
        self._cancel_parallel_lane_task()
        self._parallel_fanout_enabled = True
        self._parallel_lane_started = False
        self._parallel_lane_queue = None
        self._parallel_lane_task = None

    def _maybe_start_parallel_fanout(self, lane: str) -> None:
        if lane != "sql":
            return
        if not self._parallel_fanout_enabled or self._parallel_lane_started:
            return
        state = self._lane_states.get("sql")
        if state is None or not state.completed:
            return
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            # Outside an event loop (e.g., during prefill); defer fan-out.
            return
        queue: asyncio.Queue[Optional[SequencerEvent]] = asyncio.Queue()
        self._parallel_lane_queue = queue

        async def _fanout() -> None:
            try:
                async for event in self._kickoff_parallel_lanes():
                    await queue.put(event)
            finally:
                if self._parallel_lane_queue is queue:
                    try:
                        await queue.put(None)
                    except asyncio.CancelledError:
                        pass

        self._parallel_lane_task = loop.create_task(_fanout())
        self._parallel_lane_started = True

    async def _drain_parallel_lane_events(
        self,
        *,
        block: bool,
    ) -> AsyncGenerator[SequencerEvent, None]:
        while True:
            event = await self._pop_parallel_lane_event(block=block)
            if event is None:
                if block and self._parallel_lane_queue is not None:
                    continue
                break
            yield event

    async def _pop_parallel_lane_event(self, *, block: bool) -> Optional[SequencerEvent]:
        queue = self._parallel_lane_queue
        if queue is None:
            return None
        if block:
            item = await queue.get()
        else:
            try:
                item = queue.get_nowait()
            except asyncio.QueueEmpty:
                return None
        if item is None:
            if self._parallel_lane_queue is queue:
                self._parallel_lane_queue = None
            return None
        return item

    async def _wait_for_parallel_lane_task(self) -> None:
        task = self._parallel_lane_task
        if task is None:
            return
        self._parallel_lane_task = None
        try:
            await task
        except asyncio.CancelledError:
            pass

    async def _cleanup_parallel_fanout(self) -> None:
        task = self._parallel_lane_task
        self._parallel_lane_task = None
        self._parallel_lane_queue = None
        self._parallel_lane_started = False
        self._parallel_fanout_enabled = False
        if task is None:
            return
        if not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        else:
            try:
                await task
            except asyncio.CancelledError:
                pass

    def _cancel_parallel_lane_task(self) -> None:
        task = self._parallel_lane_task
        if task and not task.done():
            task.cancel()
        self._parallel_lane_task = None
        self._parallel_lane_queue = None
        self._parallel_lane_started = False
        self._parallel_fanout_enabled = False
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
        state.reused = None
        self._event_bus.emit_lane_transition(lane=lane, status=LANE_STATUS_RUNNING)
        self._update_presentation(lane)

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
        if state.completed and state.status in {
            LANE_STATUS_COMPLETED,
            LANE_STATUS_FAILED,
            LANE_STATUS_SKIPPED,
        }:
            return
        state.completed = True
        state.success = success
        state.error = error
        state.status = LANE_STATUS_COMPLETED if success else LANE_STATUS_FAILED
        state.reused = reused if reused is not None else state.reused
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
        self._update_presentation(lane)
        presentation = self._lane_presentations.get(lane)
        if state.reused and success:
            self._event_bus.emit_lane_reused(
                lane=lane,
                reason=error or "cached_reuse",
                metadata={"presentation": presentation, "lane_status": state.status},
            )
        self._maybe_start_parallel_fanout(lane)

    def _skip_lane(self, lane: str, *, reason: str = "cached") -> None:
        state = self._lane_states.get(lane)
        if state is None:
            return
        state.required = False
        state.completed = True
        state.success = True
        state.error = None
        state.status = LANE_STATUS_SKIPPED
        state.reused = True
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
        self._update_presentation(lane)
        presentation = self._lane_presentations.get(lane)
        self._event_bus.emit_lane_reused(
            lane=lane,
            reason=reason,
            metadata={"presentation": presentation, "lane_status": state.status},
        )
        self._maybe_start_parallel_fanout(lane)

    def abort_pending_lanes(self, reason: str = "cancelled") -> List[str]:
        cancelled: List[str] = []
        for lane, state in self._lane_states.items():
            if state.status in {LANE_STATUS_COMPLETED, LANE_STATUS_FAILED, LANE_STATUS_SKIPPED}:
                continue
            cancelled.append(lane)
            self._skip_lane(lane, reason=reason)
        self._cancel_parallel_lane_task()
        return cancelled

    def _recompute_presentations(self, *, preserve_queued: bool = False) -> None:
        for lane in self._lane_order:
            self._update_presentation(lane, preserve_queued=preserve_queued)

    def _update_presentation(self, lane: str, *, preserve_queued: bool = False) -> None:
        state = self._lane_states.get(lane)
        if state is None:
            return
        previous = self._lane_presentations.get(lane, "pending")
        presentation = self._resolve_presentation(state, previous, preserve_queued=preserve_queued)
        self._lane_presentations[lane] = presentation

    def _resolve_presentation(
        self,
        state: LaneState,
        previous: str,
        *,
        preserve_queued: bool = False,
    ) -> str:
        status = state.status
        lane = state.name
        if status == LANE_STATUS_RUNNING:
            return "running"
        if status == LANE_STATUS_SKIPPED:
            return "reused"
        if status == LANE_STATUS_FAILED:
            return "error"
        if status == LANE_STATUS_COMPLETED:
            if not state.success:
                return "error"
            reused_flag = state.reused
            if reused_flag is None:
                reused_flag = lane != "sql" and lane not in self._revision_targets
            return "reused" if reused_flag else "fresh"
        if status == LANE_STATUS_PENDING:
            if preserve_queued and previous == "queued":
                return previous
            if previous == "queued":
                return previous
            return "pending"
        return previous or "pending"


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
