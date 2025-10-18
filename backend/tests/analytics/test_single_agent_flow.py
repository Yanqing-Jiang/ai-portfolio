from __future__ import annotations

import time
from types import SimpleNamespace
from typing import List

import pytest

from analytics.artifacts.models import (
    AnalysisArtifact,
    MarketArtifact,
    PipelineArtifacts,
    SQLExecutionArtifact,
    WebContextArtifact,
)
from analytics.core.events import TimedEventEmitter
from analytics.flows.planner_executor import PlannerPhaseContext
from analytics.flows.single_agent_tools import SingleAgentController, _build_single_agent_cohesive_payload
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


def test_market_lane_uses_stock_tracker_and_concurrency_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    controller = SingleAgentController()
    captured: dict = {}

    def _fake_start(
        ctx: PlannerPhaseContext,
        *,
        adapters: List[object] | None = None,
        concurrency_override: int | None = None,
    ):
        captured["adapters"] = tuple(getattr(adapter, "name", repr(adapter)) for adapter in adapters or [])
        captured["concurrency"] = concurrency_override
        return None, None

    monkeypatch.setattr(controller._planner, "_start_tool_parallelism", _fake_start)
    dummy_ctx = SimpleNamespace()

    active = controller._start_fanout_lanes(dummy_ctx, ("market",))
    assert "market" in active
    assert captured["adapters"] == ("market_question_a", "market_question_b", "stock_tracker")
    assert captured["concurrency"] == 3


def test_iter_fresh_accessory_events_emit_once() -> None:
    controller = SingleAgentController()
    ctx = _build_context(controller)
    ctx.artifacts.market = MarketArtifact(
        query=ctx.query,
        snapshot={"symbols": [["NASDAQ:AAPL", "AAPL"]]},
    )
    ctx.artifacts.web = WebContextArtifact(
        query=ctx.query,
        summary="Apple expands services revenue.",
        snippets=[{"title": "Article", "url": "https://example.com/article"}],
    )

    lane_states = {"market": "fresh", "web": "fresh"}
    events = list(controller._iter_fresh_accessory_events(ctx, lane_states))
    assert [event["event"] for event in events] == ["stock_ready", "web_ready"]

    stock_event, web_event = events
    assert stock_event["data"]["reused"] is False
    assert stock_event["data"]["parallel_group"] == controller.LANE_PARALLEL_GROUPS["market"]
    assert stock_event["data"]["lane"] == "market"
    assert stock_event["data"]["flow_mode"] == controller.flow_mode.value
    assert stock_event["data"]["stock_widget"]["symbols"]

    assert web_event["data"]["reused"] is False
    assert web_event["data"]["parallel_group"] == controller.LANE_PARALLEL_GROUPS["web"]
    assert web_event["data"]["lane"] == "web"
    assert web_event["data"]["flow_mode"] == controller.flow_mode.value

    # Subsequent calls should not emit duplicates.
    assert list(controller._iter_fresh_accessory_events(ctx, lane_states)) == []


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
