import asyncio
import time
from types import MethodType, SimpleNamespace

import pytest

from analytics.artifacts.models import AnalysisArtifact
from analytics.flows.planner_executor import (
    PlannerExecutorFlow,
    PlannerPhaseContext,
    _TOOL_QUEUE_SENTINEL,
)
from analytics.routing import FollowUpRoute
from analytics.core.events import TimedEventEmitter
from analytics.core.session_state import SessionStateSnapshot


def _make_context() -> PlannerPhaseContext:
    emitter = TimedEventEmitter(session_id="test-session", flow="planner-executor")
    return PlannerPhaseContext(
        query="Test query",
        session_id="test-session",
        workflow_start=time.time(),
        timed_emitter=emitter,
    )


@pytest.mark.asyncio
async def test_refresh_accessory_lanes_streams_both_lanes(monkeypatch):
    flow = PlannerExecutorFlow()
    ctx = _make_context()

    monkeypatch.setattr(
        "analytics.flows.planner_executor.get_default_tool_adapters",
        lambda: (
            SimpleNamespace(name="web_retriever"),
            SimpleNamespace(name="market_question_a"),
            SimpleNamespace(name="market_question_b"),
            SimpleNamespace(name="stock_tracker"),
        ),
    )

    class _StubRuntime:
        def __init__(self) -> None:
            self.queue = asyncio.Queue()
            self.closed = False
            self.queue.put_nowait({"event": "tool_parallel_result", "data": {"lane": "web"}})
            self.queue.put_nowait({"event": "tool_parallel_result", "data": {"lane": "market"}})
            self.queue.put_nowait(_TOOL_QUEUE_SENTINEL)

        async def close(self) -> None:
            self.closed = True

    def _stub_runtime(self, *_args, **_kwargs):
        return _StubRuntime()

    flow._start_tool_parallelism = MethodType(_stub_runtime, flow)  # type: ignore[attr-defined]

    events = []
    async for event in flow.refresh_accessory_lanes(
        ctx,
        ("web", "market"),
        reason="test_accessories",
        source="pytest",
        lane_reason={"web": "web_only", "market": "market_only"},
    ):
        events.append(event)

    lane_events = [event for event in events if event.get("event") == "tool_parallel_result"]
    lane_set = {event["data"].get("lane") for event in lane_events}
    assert lane_set == {"web", "market"}
    reason_lookup = {event["data"].get("lane"): event["data"].get("reason") for event in lane_events}
    assert reason_lookup["web"] == "web_only"
    assert reason_lookup["market"] == "market_only"
    assert ctx.accessory_stage_ms.get("web") is not None
    assert ctx.accessory_stage_ms.get("market") is not None


@pytest.mark.asyncio
async def test_refresh_accessory_lanes_parallel_runtime_matches_max_latency(monkeypatch):
    flow = PlannerExecutorFlow()
    ctx = _make_context()

    monkeypatch.setattr(
        "analytics.flows.planner_executor.get_default_tool_adapters",
        lambda: (
            SimpleNamespace(name="web_retriever"),
            SimpleNamespace(name="market_question_a"),
            SimpleNamespace(name="market_question_b"),
            SimpleNamespace(name="stock_tracker"),
        ),
    )

    class _DelayedRuntime:
        def __init__(self, schedule):
            self.queue = asyncio.Queue()
            self._pump = asyncio.create_task(self._emit(schedule))

        async def _emit(self, schedule):
            async def _produce(lane, delay):
                await asyncio.sleep(delay)
                await self.queue.put({"event": "tool_parallel_result", "data": {"lane": lane}})

            await asyncio.gather(*(_produce(lane, delay) for lane, delay in schedule))
            await self.queue.put(_TOOL_QUEUE_SENTINEL)

        async def close(self):
            await self._pump

    schedule = (("web", 0.4), ("market", 0.1))

    def _runtime_factory(self, *_args, **_kwargs):
        return _DelayedRuntime(schedule)

    flow._start_tool_parallelism = MethodType(_runtime_factory, flow)  # type: ignore[attr-defined]

    start = time.perf_counter()
    async for _ in flow.refresh_accessory_lanes(ctx, ("web", "market")):
        pass
    elapsed = time.perf_counter() - start

    assert abs(elapsed - 0.4) < 0.12
    assert ctx.accessory_stage_ms["web"] >= ctx.accessory_stage_ms["market"]


@pytest.mark.asyncio
async def test_initialize_context_reuses_latest_artifacts_snapshot():
    flow = PlannerExecutorFlow()
    ctx = _make_context()
    ctx.artifacts.analysis = AnalysisArtifact(
        query="Test query",
        summary="Existing analysis",
    )

    flow._capture_artifacts(ctx)  # type: ignore[attr-defined]
    flow.follow_up_route = FollowUpRoute.REUSE_SQL

    new_ctx = await flow.initialize_context("Reuse query", session_id="reuse-session")

    assert new_ctx.artifacts.analysis is not None
    assert new_ctx.artifacts.analysis.summary == "Existing analysis"

    new_ctx.artifacts.analysis.summary = "Mutated"
    latest_snapshot = flow.latest_artifacts()
    assert latest_snapshot is not None
    assert latest_snapshot.analysis.summary == "Existing analysis"


@pytest.mark.asyncio
async def test_initialize_context_wipes_accessory_state_for_fresh_full_pipeline():
    flow = PlannerExecutorFlow()
    snapshot = SessionStateSnapshot(session_id="fresh-run")
    snapshot.touch_lane("web")
    snapshot.touch_lane("market")
    snapshot.record_tool_receipt("web_retriever", {"tool": "web_retriever", "lane": "web"})
    snapshot.record_tool_receipt("stock_tracker", {"tool": "stock_tracker", "lane": "market"})
    flow.prime_with_snapshot(snapshot)
    flow.set_follow_up_route(FollowUpRoute.FULL_PIPELINE)

    ctx = await flow.initialize_context("Fresh accessories", session_id="fresh-run")

    assert ctx.lane_refresh_required.get("web") is True
    assert ctx.lane_refresh_required.get("market") is True
    assert ctx.revision_context is not None
    overrides = ctx.revision_context.lane_refresh_overrides
    assert overrides.get("web") is True
    assert overrides.get("market") is True
    assert "web" not in snapshot.lane_timestamps
    receipts = snapshot.tool_cache.get("tool_receipts") or {}
    assert "web_retriever" not in receipts
