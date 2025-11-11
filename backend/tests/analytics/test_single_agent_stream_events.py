from __future__ import annotations

from types import SimpleNamespace
from typing import Any, Dict, List

import pytest

from analytics.core.session_state import SessionStateSnapshot
from analytics.flows.instrumentation import _maybe_update_session_state
from analytics.flows.schedulers import FlowMode
from analytics.flows.single_agent_tools import SingleAgentController, _SingleAgentToolHooks
from analytics.flows.orchestrator_adapter import PlannerOrchestratorAdapter
from analytics.flows.sequencer import PlannerSequencer
from analytics.routing import FollowUpRoute


def _make_controller() -> SingleAgentController:
    # Disable live agent wiring so tests avoid network setup while still exercising annotation logic.
    return SingleAgentController(enable_agents=False)


def test_agent_event_annotation_assigns_lane_and_tool() -> None:
    controller = _make_controller()
    ctx = SimpleNamespace()
    base_event = {
        "event": "tool_call_delta",
        "data": {
            "tool_call": {
                "id": "call-1",
                "name": "web_retriever",
                "arguments_delta": {"query": "AMD revenue"},
                "sequence_number": 1,
                "output_index": 0,
            }
        },
    }

    annotated = controller._annotate_runtime_event(base_event, ctx)

    assert annotated["data"]["lane"] == "web"
    assert annotated["data"]["tool"] == "web_retriever"
    assert annotated["data"]["parallel_group"] == "single_agent_fanout"


def test_instrumentation_records_agent_tool_receipts() -> None:
    snapshot = SessionStateSnapshot(session_id="session-tool-receipt")

    arguments_event = {
        "event": "tool_call_arguments",
        "data": {
            "tool_call": {
                "id": "call-1",
                "name": "web_retriever",
                "arguments": {"query": "AMD revenue"},
                "sequence_number": 2,
                "output_index": 0,
            }
        },
    }
    updated = _maybe_update_session_state(
        snapshot,
        arguments_event,
        query="AMD revenue guidance",
        flow_mode=FlowMode.SINGLE_AGENT,
    )
    assert updated
    receipts = snapshot.tool_cache.get("tool_receipts", {})
    assert "web_retriever" in receipts
    assert receipts["web_retriever"]["arguments"] == {"query": "AMD revenue"}

    completion_event = {
        "event": "agent_tool_complete",
        "data": {
            "tool_call": {
                "id": "call-1",
                "name": "web_retriever",
                "status": "completed",
                "sequence_number": 3,
                "output_index": 0,
            }
        },
    }
    updated_complete = _maybe_update_session_state(
        snapshot,
        completion_event,
        query="AMD revenue guidance",
        flow_mode=FlowMode.SINGLE_AGENT,
    )
    assert updated_complete
    receipts = snapshot.tool_cache.get("tool_receipts", {})
    assert receipts["web_retriever"]["status"] == "completed"


@pytest.mark.asyncio
async def test_prefetched_accessories_not_reran() -> None:
    call_flags = {"web": False, "market": False}

    async def _idle_stage():
        if False:  # pragma: no cover - generator placeholder
            yield {}

    async def _web_stage():
        call_flags["web"] = True
        if False:  # pragma: no cover
            yield {}

    async def _market_stage():
        call_flags["market"] = True
        if False:  # pragma: no cover
            yield {}

    orchestrator = PlannerOrchestratorAdapter(
        intent_runner=_idle_stage,
        sql_runner=_idle_stage,
        web_runner=_web_stage,
        market_runner=_market_stage,
        analysis_runner=_idle_stage,
    )
    sequencer = PlannerSequencer(orchestrator)
    sequencer.prefill_lane_states({"web": "pending", "market": "pending"})

    cached_payload = {"status": "cached", "reused": True, "schedule_stage": "hedged_accessories"}
    sequencer.mark_lane_complete("web", result=dict(cached_payload), reused=True, success=True)
    sequencer.mark_lane_complete("market", result=dict(cached_payload), reused=True, success=True)

    async for _ in sequencer.run():
        pass

    assert call_flags["web"] is False
    assert call_flags["market"] is False
    lane_states = sequencer.lane_presentations()
    assert lane_states.get("web") == "reused"
    assert lane_states.get("market") == "reused"

@pytest.mark.asyncio
async def test_forward_with_hooks_emits_session_started_without_flag() -> None:
    controller = _make_controller()
    hooks = _SingleAgentToolHooks(controller)

    async def _stream():
        yield {"event": "analysis_ready", "data": {"lane": "analysis"}}
        yield {"event": "workflow_complete", "data": {}}

    events = []
    async for event in controller._forward_with_hooks(_stream(), hooks, session_id="sess-auto"):
        events.append(event)

    assert events
    assert events[0]["event"] == "session_started"
    workflow = [evt for evt in events if evt.get("event") == "workflow_complete"]
    assert workflow and workflow[0]["data"]["session_id"] == "sess-auto"


def test_missing_lane_telemetry_warning_emitted() -> None:
    controller = _make_controller()
    lane_states = {"web": "pending", "market": "pending"}
    controller._update_lane_state_from_event(
        lane_states,
        {"event": "workflow_complete", "data": {}},
        revision_targets=set(),
    )
    warnings = list(controller._drain_lane_warning_events())
    assert warnings
    warning = warnings[0]
    assert warning["event"] == "status"
    assert sorted(warning["data"]["lanes"]) == ["market", "web"]


@pytest.mark.asyncio
async def test_stock_only_followups_emit_market_lane_reuse_event() -> None:
    controller = _make_controller()
    ctx = await controller._planner.initialize_context(
        "Only refresh NVDA stock widget",
        session_id="sess-lane-reuse",
    )
    ctx.follow_up_route = FollowUpRoute.STOCK_ONLY
    ctx.revision_context = SimpleNamespace(
        lane_age_seconds=lambda lane, now=None: 0.8 if lane == "market" else None,
    )
    lane_states = controller._initial_lane_states()
    event = controller._handle_lane_reuse(
        ctx,
        lane="market",
        lane_states=lane_states,
        reason="cached_market_artifacts",
    )
    assert event is not None
    assert event["event"] == "status"
    data = event.get("data") or {}
    assert data.get("step") == "lane_reused"
    assert data.get("lane") == "market"
    assert data.get("follow_up_route") == FollowUpRoute.STOCK_ONLY.value
    assert lane_states["market"] == "reused"


@pytest.mark.asyncio
async def test_forward_with_hooks_emits_prefetched_lane_reuse_events() -> None:
    controller = _make_controller()
    hooks = _SingleAgentToolHooks(controller, session_id="session-prefetch")
    controller._pending_lane_reuse_events.append(
        {"event": "lane_reused", "data": {"lane": "web", "reused": True}}
    )

    async def _stream():
        yield {"event": "workflow_complete", "data": {}}

    events: List[Dict[str, Any]] = []
    async for event in controller._forward_with_hooks(_stream(), hooks, session_id="session-prefetch"):
        events.append(event)

    assert any(evt.get("event") == "lane_reused" and evt.get("data", {}).get("lane") == "web" for evt in events)


@pytest.mark.asyncio
async def test_forward_with_hooks_raises_when_session_missing() -> None:
    controller = _make_controller()
    hooks = _SingleAgentToolHooks(controller)

    async def _stream():
        yield {"event": "workflow_complete", "data": {}}

    with pytest.raises(RuntimeError, match="session_started"):
        async for _ in controller._forward_with_hooks(_stream(), hooks, session_id=None):
            pass


@pytest.mark.asyncio
async def test_clarification_multi_phase_emits_single_completion() -> None:
    controller = _make_controller()
    hooks = _SingleAgentToolHooks(controller, session_id="clarification-multi-phase")

    async def _stream():
        yield {"event": "progress", "data": {"step": "clarification", "message": "Missing timeframe"}}
        yield {"event": "progress", "data": {"step": "clarification", "message": "Missing metric"}}
        yield {"event": "clarification_complete", "data": {"rounds": 2}}
        yield {"event": "workflow_complete", "data": {}}

    tool_events: List[Dict[str, Any]] = []
    async for event in controller._forward_with_hooks(_stream(), hooks, session_id="clarification-multi-phase"):
        if event.get("event") == "tool_call" and event.get("data", {}).get("tool") == "clarification_manager":
            tool_events.append(event)

    starts = [evt for evt in tool_events if evt["data"].get("status") == "start"]
    completes = [evt for evt in tool_events if evt["data"].get("status") == "end"]
    assert len(starts) == 1
    assert len(completes) == 1
