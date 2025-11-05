from __future__ import annotations

import asyncio
import time
from types import SimpleNamespace
from typing import List

import pytest

from agents import Runner
from analytics.artifacts.models import (
    AnalysisArtifact,
    MarketArtifact,
    PipelineArtifacts,
    SQLExecutionArtifact,
    WebContextArtifact,
)
from analytics.core.events import TimedEventEmitter
from analytics.flows.planner_executor import PlannerPhaseContext, _TOOL_QUEUE_SENTINEL, ToolParallelRuntime
from analytics.flows.single_agent_tools import SingleAgentController, _SequencerRunState, _build_single_agent_cohesive_payload
from analytics.flows.sequencer import LANE_STATUS_FAILED, LANE_STATUS_RUNNING, LANE_STATUS_SKIPPED
from analytics.flows.schedulers import get_mode_config
from analytics.routing import FollowUpRoute


def _build_context(controller: SingleAgentController) -> PlannerPhaseContext:
    artifacts = PipelineArtifacts()
    emitter = TimedEventEmitter(session_id="sess-123", flow=controller.flow_label)
    ctx = PlannerPhaseContext(
        query="test query",
        session_id="sess-123",
        workflow_start=time.time(),
        timed_emitter=emitter,
        flow_mode=controller.flow_mode,
        artifacts=artifacts,
    )
    ctx.parallelism_enabled = True
    return ctx


def test_lane_transition_event_updates_states() -> None:
    controller = SingleAgentController()
    lane_states = controller._initial_lane_states()
    revision_targets: Set[str] = set()

    controller._apply_lane_transition_event(
        lane_states,
        {
            "event": "planner_lane_transition",
            "data": {"lane": "web", "status": LANE_STATUS_RUNNING},
        },
        revision_targets=revision_targets,
    )
    assert lane_states["web"] == "running"

    controller._apply_lane_transition_event(
        lane_states,
        {
            "event": "planner_lane_transition",
            "data": {"lane": "web", "status": LANE_STATUS_SKIPPED, "success": True, "reused": True},
        },
        revision_targets=revision_targets,
    )
    assert lane_states["web"] == "reused"

    controller._apply_lane_transition_event(
        lane_states,
        {
            "event": "planner_lane_transition",
            "data": {"lane": "market", "status": LANE_STATUS_FAILED, "success": False},
        },
        revision_targets=revision_targets,
    )
    assert lane_states["market"] == "error"


def test_initial_lane_states_respect_follow_up_route() -> None:
    controller = SingleAgentController()
    default_states = controller._initial_lane_states()
    assert default_states["sql"] == "pending"
    assert default_states["market"] == "skipped"

    controller.follow_up_route = FollowUpRoute.REUSE_SQL
    reuse_states = controller._initial_lane_states()
    assert reuse_states["sql"] == "reused"
    assert reuse_states["web"] == "skipped"


def test_handle_lane_complete_updates_reuse_flags() -> None:
    controller = SingleAgentController()
    dummy_ctx = SimpleNamespace(reused_web=False, reused_stock=False)
    controller._sequencer_state = SimpleNamespace(ctx=dummy_ctx)

    controller._handle_lane_complete("web", success=True, reused=True, reason=None)
    assert dummy_ctx.reused_web is True

    controller._handle_lane_complete("market", success=True, reused=False, reason=None)
    assert dummy_ctx.reused_stock is False

    controller._sequencer_state = None


def test_cohesive_payload_includes_analysis_sources() -> None:
    analysis_payload = {
        "analysis": "Quarterly performance remains resilient.",
        "analysis_length": 128,
        "sources": {"sql_executor": "fanout", "web_retriever": "cached", "stock_tracker": "fanout"},
        "stock_widget": {"symbols": ["AAPL"], "insights": {"latest_close": 176.23, "change_percent": 1.2}},
        "web_context": {
            "summary": "Apple expands services revenue.",
            "snippets": [
                {"title": "Apple Services Surge", "url": "https://example.com/apple-services", "snippet": "Services revenue grew double digits."}
            ],
        },
    }
    artifacts = PipelineArtifacts(
        sql_execution=SQLExecutionArtifact(query="test query", row_count=120, columns=["revenue", "net_income", "eps"]),
        web=WebContextArtifact(query="test query", summary="Apple expands services revenue.", snippets=[{"title": "Article", "url": "https://example.com"}]),
        market=MarketArtifact(query="test query", snapshot={"symbols": [["NASDAQ:AAPL", "AAPL"]]}),
        analysis=AnalysisArtifact(query="test query", analysis_text="Quarterly performance remains resilient."),
    )

    cohesive = _build_single_agent_cohesive_payload(analysis_payload, artifacts)
    assert cohesive is not None

    sources = cohesive.get("analysis_sources")
    assert isinstance(sources, dict)
    assert sources["sql"]["lane"] == "sql"
    assert sources["sql"]["reused"] is False
    assert sources["stock"]["lane"] == "stock"
    assert "AAPL" in sources["stock"]["symbols"]
    assert sources["web"]["reused"] is True
    assert sources["web"]["lane"] == "web"


def test_lane_summary_adds_rerun_scope_for_chart_revision() -> None:
    controller = SingleAgentController()
    controller.follow_up_route = FollowUpRoute.REUSE_SQL
    lane_states = {
        "sql": "reused",
        "chart": "fresh",
        "analysis": "fresh",
        "market": "reused",
        "web": "reused",
    }

    event = controller._emit_lane_summary(lane_states)
    data = event["data"]
    assert data["decision"] == "chart_revision"
    scope = data.get("rerun_scope")
    assert isinstance(scope, dict)
    rerun_set = set(scope.get("rerun", []))
    assert rerun_set == {"chart"}
    reuse_set = set(scope.get("reuse", []))
    assert reuse_set >= {"sql", "market", "web", "analysis"}
    assert scope.get("route") == FollowUpRoute.REUSE_SQL.value


@pytest.mark.asyncio
async def test_agent_run_stage_streams_queue(monkeypatch: pytest.MonkeyPatch) -> None:
    controller = SingleAgentController()
    controller._agents_enabled = True
    controller._agent = object()

    ctx = await controller._planner.initialize_context("agent queue test", session_id="agent-queue")
    state = _SequencerRunState(
        ctx=ctx,
        registry=controller._registry,
        executed=set(),
        mode_config=get_mode_config(controller.flow_mode),
        query="agent queue test",
        session_id="agent-queue",
    )
    state.lane_states = controller._initial_lane_states()
    controller._sequencer_state = state

    controller._planner._annotate_revision = lambda event, _: event  # type: ignore[attr-defined]
    controller._planner.latest_artifacts = lambda: PipelineArtifacts(
        analysis=AnalysisArtifact(query="agent queue test", analysis_text="Agent output", length=20),
    )

    async def fake_runner_run(agent, input, context, max_turns, run_config):
        annotated = controller._attach_retry_metadata(
            {"event": "tool_call", "data": {"tool": "analysis_writer"}},
            "analysis_generation",
            1,
        )
        await context.queue.put(annotated)
        return SimpleNamespace(final_output={"analysis": "Agent output", "analysis_length": 20})

    monkeypatch.setattr(Runner, "run", fake_runner_run)

    emitted = []
    async for event in controller._agent_run_stage():
        emitted.append(event)
        if event.get("event") == "workflow_complete":
            break

    controller._sequencer_state = None

    assert emitted, "Agent run stage should emit events"
    tool_event = emitted[0]
    assert tool_event["event"] == "tool_call"
    data = tool_event["data"]
    assert data["tool"] == "analysis_writer"
    assert data["attempt"] == 1
    assert data["retry"] is False
    event_names = [evt.get("event") for evt in emitted]
    assert "workflow_complete" in event_names, f"missing workflow_complete in events: {event_names}"


def test_flush_tool_events_marks_deltas_and_preserves_sentinel() -> None:
    controller = SingleAgentController()
    queue: asyncio.Queue = asyncio.Queue()
    ctx = _build_context(controller)
    payload = {
        "event": "tool_parallel_result",
        "data": {"tool": "stock_tracker", "payload": {"ready": True}},
    }
    queue.put_nowait(payload)
    queue.put_nowait(_TOOL_QUEUE_SENTINEL)

    flushed = controller._planner._pipeline._flush_tool_events(queue, ctx)
    assert len(flushed) == 1
    assert flushed[0]["data"]["delta"] is True
    assert flushed[0]["data"]["tool"] == "stock_tracker"
    assert queue.qsize() == 1
    assert queue.get_nowait() is _TOOL_QUEUE_SENTINEL
