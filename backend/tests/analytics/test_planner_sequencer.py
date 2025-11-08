from __future__ import annotations

import asyncio
import time
from typing import Any, AsyncGenerator, Dict, Iterable, List, Optional, Tuple

import pytest

from analytics.flows.sequencer import (
    LANE_STATUS_COMPLETED,
    LANE_STATUS_FAILED,
    LANE_STATUS_RUNNING,
    LANE_STATUS_SKIPPED,
    PlannerSequencer,
)
from analytics.flows.orchestrator_protocol import FlowOrchestrator


def _make_event(stage: str, idx: int) -> Dict[str, Any]:
    return {"event": f"{stage}_event_{idx}", "data": {"stage": stage, "idx": idx}}


def _make_stream(stage: str, count: int) -> AsyncGenerator[Dict[str, Any], None]:
    async def _generator() -> AsyncGenerator[Dict[str, Any], None]:
        for idx in range(count):
            yield _make_event(stage, idx)
            await asyncio.sleep(0)
    return _generator()


class FakeOrchestrator(FlowOrchestrator):
    lane_order: Tuple[str, ...] = ("intent", "sql", "web", "market", "analysis")

    def __init__(
        self,
        *,
        intent_events: int = 1,
        sql_events: int = 2,
        web_events: int = 1,
        market_events: int = 1,
        analysis_events: int = 1,
        optional_lanes: Tuple[str, ...] = ("web", "market"),
    ) -> None:
        self._event_counts = {
            "intent": intent_events,
            "sql": sql_events,
            "web": web_events,
            "market": market_events,
            "analysis": analysis_events,
        }
        self.optional_lanes = optional_lanes
        self.run_counts = {lane: 0 for lane in self.lane_order}
        self.completed: Dict[str, bool] = {lane: False for lane in self.lane_order}
        self.success_map: Dict[str, Optional[bool]] = {lane: None for lane in self.lane_order}
        self.reused_map: Dict[str, Optional[bool]] = {lane: None for lane in self.lane_order}
        self._metadata = {"run_id": "test-run"}
        self.raise_on: Optional[str] = None

    def _register_call(self, lane: str) -> None:
        self.run_counts[lane] += 1

    async def run_intent_stage(self) -> AsyncGenerator[Dict[str, Any], None]:
        self._register_call("intent")
        async for event in _make_stream("intent", self._event_counts["intent"]):
            yield event

    async def run_sql_stage(self) -> AsyncGenerator[Dict[str, Any], None]:
        self._register_call("sql")
        if self.raise_on == "sql":
            raise RuntimeError("sql boom")
        async for event in _make_stream("sql", self._event_counts["sql"]):
            yield event

    async def run_web_stage(self) -> AsyncGenerator[Dict[str, Any], None]:
        self._register_call("web")
        if self.raise_on == "web":
            raise RuntimeError("web boom")
        async for event in _make_stream("web", self._event_counts["web"]):
            yield event

    async def run_market_stage(self) -> AsyncGenerator[Dict[str, Any], None]:
        self._register_call("market")
        if self.raise_on == "market":
            raise RuntimeError("market boom")
        async for event in _make_stream("market", self._event_counts["market"]):
            yield event

    async def run_analysis_stage(self) -> AsyncGenerator[Dict[str, Any], None]:
        self._register_call("analysis")
        async for event in _make_stream("analysis", self._event_counts["analysis"]):
            yield event

    def pending_lanes(self) -> Iterable[str]:
        return tuple(lane for lane, done in self.completed.items() if not done)

    def lane_complete(
        self,
        lane: str,
        *,
        success: bool,
        reused: bool = False,
        reason: Optional[str] = None,
    ) -> None:
        self.completed[lane] = True
        self.success_map[lane] = success
        self.reused_map[lane] = reused

    def event_metadata(self) -> Dict[str, Any]:
        return dict(self._metadata)


@pytest.mark.asyncio
async def test_sequencer_preserves_stage_order_and_metadata() -> None:
    orchestrator = FakeOrchestrator()
    sequencer = PlannerSequencer(orchestrator)
    lane_transitions: List[Dict[str, Any]] = []
    sequencer.event_bus.subscribe(lane_transitions.append)

    events: List[Dict[str, Any]] = []
    async for event in sequencer.run():
        events.append(event)

    # Expect events in canonical order (intent -> sql -> web -> market -> analysis)
    observed_sequence = [event["data"]["stage"] for event in events]
    assert observed_sequence == [
        "intent",
        "sql",
        "sql",
        "web",
        "market",
        "analysis",
    ]

    # Metadata injected into each event
    assert all(event["data"]["run_id"] == "test-run" for event in events)

    # Lane transitions emitted with success state
    completed_lanes = {
        entry["data"]["lane"]: entry["data"]["status"] for entry in lane_transitions
    }
    assert completed_lanes == {
        "intent": LANE_STATUS_COMPLETED,
        "sql": LANE_STATUS_COMPLETED,
        "web": LANE_STATUS_COMPLETED,
        "market": LANE_STATUS_COMPLETED,
        "analysis": LANE_STATUS_COMPLETED,
    }
    assert all(orchestrator.success_map[lane] is True for lane in orchestrator.lane_order)
    assert all(orchestrator.reused_map[lane] is False for lane in orchestrator.lane_order)

    intent_completed_seen = False
    for transition in lane_transitions:
        lane = transition["data"]["lane"]
        status = transition["data"]["status"]
        if lane == "intent" and status == LANE_STATUS_COMPLETED:
            intent_completed_seen = True
            continue
        if status == LANE_STATUS_RUNNING and lane != "intent":
            assert intent_completed_seen, (
                "Lane %s started (%s) before intent completed" % (lane, status)
            )


@pytest.mark.asyncio
async def test_optional_lanes_skipped_when_not_required() -> None:
    orchestrator = FakeOrchestrator(web_events=0, market_events=0)
    sequencer = PlannerSequencer(
        orchestrator,
        lane_refresh_required={"web": False, "market": False},
    )
    lane_transitions: List[Dict[str, Any]] = []
    sequencer.event_bus.subscribe(lane_transitions.append)

    events: List[Dict[str, Any]] = []
    async for event in sequencer.run():
        events.append(event)

    # No web/market events emitted because lanes reused
    stages = {event["data"]["stage"] for event in events}
    assert stages == {"intent", "sql", "analysis"}

    # Web/market runners never invoked
    assert orchestrator.run_counts["web"] == 0
    assert orchestrator.run_counts["market"] == 0

    lane_states = sequencer.lane_presentations()
    assert lane_states.get("web") == "reused"
    assert lane_states.get("market") == "reused"
    assert orchestrator.reused_map["web"] is True
    assert orchestrator.reused_map["market"] is True


@pytest.mark.asyncio
async def test_lane_reuse_event_emitted_for_skipped_optional_lanes() -> None:
    orchestrator = FakeOrchestrator(web_events=0, market_events=0)
    recorded: List[Dict[str, Any]] = []
    sequencer = PlannerSequencer(
        orchestrator,
        lane_refresh_required={"web": False, "market": False},
        emit=recorded.append,
    )

    async for _ in sequencer.run():
        pass

    reuse_events = [event for event in recorded if event.get("event") == "lane_reused"]
    lanes_reported = {event.get("data", {}).get("lane") for event in reuse_events}
    assert {"web", "market"}.issubset(lanes_reported)
    assert all(event.get("data", {}).get("source") == "sequencer" for event in reuse_events)


@pytest.mark.asyncio
async def test_lane_failure_propagates_and_emits_error() -> None:
    orchestrator = FakeOrchestrator()
    orchestrator.raise_on = "market"
    sequencer = PlannerSequencer(orchestrator)
    transitions: List[Dict[str, Any]] = []
    sequencer.event_bus.subscribe(transitions.append)

    with pytest.raises(RuntimeError, match="market boom"):
        async for _ in sequencer.run():
            pass

    status_map = {
        entry["data"]["lane"]: entry["data"]["status"] for entry in transitions
    }
    assert status_map["market"] == LANE_STATUS_FAILED
    assert orchestrator.success_map["market"] is False
    # Analysis should not be marked complete after failure
    assert orchestrator.success_map["analysis"] is None


def test_retry_callbacks_invoked() -> None:
    orchestrator = FakeOrchestrator()
    sequencer = PlannerSequencer(orchestrator)
    recorded: List[Tuple[str, int, Optional[str], Optional[str], Optional[Dict[str, Any]]]] = []

    def _on_retry(
        lane: str,
        attempt: int,
        reason: Optional[str],
        error: Optional[str],
        metadata: Optional[Dict[str, Any]],
    ) -> None:
        recorded.append((lane, attempt, reason, error, dict(metadata or {})))

    sequencer.on_retry(_on_retry)
    sequencer.notify_retry(
        "sql",
        attempt=2,
        reason="tool_retry",
        error="SQL_TIMEOUT",
        metadata={"tool": "sql_generation"},
    )

    assert recorded == [
        ("sql", 2, "tool_retry", "SQL_TIMEOUT", {"tool": "sql_generation"})
    ]


def test_abort_pending_lanes_marks_states_skipped() -> None:
    orchestrator = FakeOrchestrator()
    sequencer = PlannerSequencer(orchestrator)
    sequencer.prefill_lane_states({"sql": "pending", "web": "pending"})
    cancelled = sequencer.abort_pending_lanes(reason="restart")
    assert {"sql", "web"}.issubset(set(cancelled))
    assert sequencer._lane_states["sql"].status == LANE_STATUS_SKIPPED  # type: ignore[attr-defined]
    assert sequencer._lane_states["web"].status == LANE_STATUS_SKIPPED  # type: ignore[attr-defined]


def test_restart_aborts_optional_lanes() -> None:
    orchestrator = FakeOrchestrator()
    sequencer = PlannerSequencer(orchestrator)
    # Simulate in-flight optional lanes.
    sequencer._start_lane("web")  # type: ignore[attr-defined]
    sequencer._start_lane("market")  # type: ignore[attr-defined]

    cancelled = sequencer.abort_pending_lanes(reason="restart")
    cancelled_set = set(cancelled)
    assert {"web", "market"}.issubset(cancelled_set)
    lane_states = sequencer.lane_presentations()
    assert lane_states["web"] == "reused"
    assert lane_states["market"] == "reused"
    assert orchestrator.reused_map["web"] is True
    assert orchestrator.reused_map["market"] is True


class _SqlReadyOrchestrator(FakeOrchestrator):
    async def run_sql_stage(self) -> AsyncGenerator[Dict[str, Any], None]:
        self._register_call("sql")
        yield {"event": "sql_ready", "data": {"lane": "sql", "reused": True}}
        # Simulate planner work that would normally follow sql_ready.
        await asyncio.sleep(1.5)
        yield {"event": "sql_after", "data": {"lane": "sql"}}


@pytest.mark.asyncio
async def test_parallel_lanes_fast_path_triggers_before_sql_stage_completes() -> None:
    orchestrator = _SqlReadyOrchestrator(web_events=1, market_events=0)
    sequencer = PlannerSequencer(orchestrator)
    events: List[Dict[str, Any]] = []
    timestamps: List[float] = []
    lane_reuse_times: List[float] = []

    def _capture_reuse(event: Dict[str, Any]) -> None:
        if event.get("event") == "lane_reused":
            lane_reuse_times.append(time.perf_counter())

    sequencer.event_bus.subscribe(_capture_reuse)

    async for event in sequencer.run():
        events.append(event)
        timestamps.append(time.perf_counter())
        if event.get("event") == "sql_ready":
            sequencer.mark_lane_complete("sql", result=event.get("data"), success=True, reused=True)

    sql_ready_idx = next(idx for idx, evt in enumerate(events) if evt.get("event") == "sql_ready")
    assert lane_reuse_times, "expected lane_reused telemetry to fire"
    assert (
        lane_reuse_times[0] - timestamps[sql_ready_idx] < 0.2
    ), "lane_reused should emit within 200ms of sql_ready"
