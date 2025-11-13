import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[2]))

import pytest
from typing import Any, Dict, List, Optional, Set
from datetime import datetime, timezone

import analytics.flows.workflow as workflow_module
from analytics.flows.workflow import analytics_memory_workflow
from analytics.routing import FollowUpRoute
from analytics.routing.follow_up_classifier import FollowUpClassifier
from analytics.services.response_search import SearchTopicPlan
from analytics.services.polygon import DailyBar, MarketSnapshot
from analytics.core.session_state import SessionStateSnapshot, get_session_state_repository, close_session_state_repository


FORBIDDEN_PIPELINE_EVENTS = {
    "classification_started",
    "classification_complete",
    "classification_reasoning",
    "classification_declined",
    "intent_detection_complete",
    "intent_detection_started",
    "clarification_request",
    "clarification_progress",
    "clarification_resolved",
    "clarification_complete",
    "clarification_timeout",
    "sql_generated",
    "sql_ready",
    "sql_compiled",
    "sql_validated",
    "sql_execution",
    "sql_execution_started",
}


def _has_forbidden_events(events):
    return any(evt.get("event") in FORBIDDEN_PIPELINE_EVENTS for evt in events)


@pytest.mark.asyncio
async def test_chart_revision_routed_fast_path():
    session_id = "chart-revision-route"
    repo = get_session_state_repository()
    snapshot = SessionStateSnapshot(session_id=session_id)
    snapshot.record_outputs(
        chart_spec={
            "series": [{"type": "line", "name": "Revenue"}],
            "meta": {"chartDesign": {"chart_type": "line"}},
        },
        analysis="Baseline narrative",
    )
    await repo.save(snapshot)

    query = "Please revise the chart to a bar chart"
    events = []
    async for event in analytics_memory_workflow(query=query, session_id=session_id, flow="single-agent"):
        events.append(event)

    follow_up_events = [evt for evt in events if evt.get("event") == "follow_up_route"]
    assert follow_up_events, "Expected follow_up_route event for chart revision"
    assert follow_up_events[0].get("data", {}).get("route") == "chart_revision"

    chart_events = [evt for evt in events if evt.get("event") == "chart_patch"]
    assert chart_events, "Expected a chart_patch event from revision fast-path"
    patch_event = chart_events[-1]
    ops = patch_event.get("data", {}).get("ops", [])
    assert ops and ops[0].get("op") == "set_chart_type" and ops[0].get("value") == "bar"
    assert not _has_forbidden_events(events), "Chart revision should avoid full pipeline events"

    await repo.delete(session_id)
    await close_session_state_repository()


@pytest.mark.asyncio
async def test_chart_revision_allows_missing_analysis():
    session_id = "chart-lane-missing-analysis"
    repo = get_session_state_repository()
    snapshot = SessionStateSnapshot(session_id=session_id)
    snapshot.record_outputs(
        chart_spec={
            "series": [
                {
                    "type": "bar",
                    "name": "Revenue",
                    "data": [
                        {"label": "AMD", "value": 120},
                        {"label": "NVDA", "value": 150},
                    ],
                }
            ],
        }
    )
    _seed_revision_snapshot(snapshot)
    await repo.save(snapshot)

    events = []
    async for event in analytics_memory_workflow(
        query="Update the chart to a stacked bar view",
        session_id=session_id,
        flow="single-agent",
    ):
        events.append(event)

    follow_up_events = [evt for evt in events if evt.get("event") == "follow_up_route"]
    assert follow_up_events, "Expected follow_up_route event for chart-only snapshot"
    assert all(evt.get("data", {}).get("route") != "cannot_revise" for evt in follow_up_events)
    assert any(evt.get("event") == "revision_request" for evt in events), "Revision request should stream"

    await repo.delete(session_id)
    await close_session_state_repository()


@pytest.mark.asyncio
async def test_fresh_query_with_snapshot_stays_full_pipeline():
    session_id = "fresh-route"
    repo = get_session_state_repository()
    snapshot = SessionStateSnapshot(session_id=session_id)
    snapshot.record_outputs(
        chart_spec={
            "series": [{"type": "line", "name": "Revenue"}],
            "meta": {"chartDesign": {"chart_type": "line"}},
        },
        analysis="Baseline narrative",
    )
    await repo.save(snapshot)

    query = "Compare AMD and NVDA revenue from 2021 to 2024"
    events = []
    async for event in analytics_memory_workflow(query=query, session_id=session_id, flow="single-agent"):
        events.append(event)

    assert not any(evt.get("event") == "revision_request" for evt in events)
    follow_up_events = [evt for evt in events if evt.get("event") == "follow_up_route"]
    assert follow_up_events, "Expected follow_up_route event for fresh run"
    assert follow_up_events[0].get("data", {}).get("route") == "full_pipeline"
    banner_events = [
        evt.get("data", {}).get("banner")
        for evt in follow_up_events
        if evt.get("data", {}).get("banner")
    ]
    if banner_events:
        assert any(banner.get("title") == "Fresh Run Scheduled" for banner in banner_events)

    await repo.delete(session_id)
    await close_session_state_repository()


@pytest.mark.asyncio
async def test_analysis_revision_routed_fast_path(monkeypatch):
    session_id = "analysis-revision-route"
    repo = get_session_state_repository()
    snapshot = SessionStateSnapshot(session_id=session_id)
    snapshot.record_outputs(
        chart_spec={
            "series": [{"type": "line", "name": "Revenue"}],
            "meta": {"chartDesign": {"chart_type": "line"}},
        },
        analysis="Original summary",
    )
    _seed_revision_snapshot(snapshot)
    async def _fake_topics(query: str, *, session_id: Optional[str] = None, min_topics: int = 2):
        return [SearchTopicPlan(label="Risk", query="amd margin risks", reason="test")]
    monkeypatch.setattr(
        FollowUpClassifier,
        "classify",
        lambda self, q, snap, lane_readiness=None: FollowUpRoute.REUSE_SQL,
    )
    monkeypatch.setattr(
        FollowUpClassifier,
        "detect_revision_targets",
        lambda self, q, snap, lane_readiness=None: {"analysis"},
    )
    monkeypatch.setattr("analytics.services.response_search.generate_search_topics", _fake_topics)
    monkeypatch.setattr("analytics.services.response_search.has_search_api_key", lambda: True)
    await repo.save(snapshot)

    query = "analysis: Updated summary focusing on YoY growth"
    events = []
    async for event in analytics_memory_workflow(query=query, session_id=session_id, flow="single-agent"):
        events.append(event)

    follow_up_events = [evt for evt in events if evt.get("event") == "follow_up_route"]
    assert follow_up_events, "Expected follow_up_route event for analysis revision"
    assert follow_up_events[0].get("data", {}).get("route") in {"analysis_only", "mixed_revision"}
    lanes = follow_up_events[0].get("data", {}).get("lanes")
    assert lanes == ["analysis", "web"], f"Unexpected lanes payload: {lanes}"
    refresh_flags = follow_up_events[0].get("data", {}).get("lane_refresh_required") or {}
    assert refresh_flags.get("analysis") is True
    assert refresh_flags.get("web") is True
    assert refresh_flags.get("market") is False

    assert not _has_forbidden_events(events), "Analysis revision should avoid full pipeline events"
    revision_requests = [evt for evt in events if evt.get("event") == "revision_request"]
    assert revision_requests, "Revision directive event missing"
    topics_emitted = revision_requests[0].get("data", {}).get("search_topics") or []
    assert len(topics_emitted) >= 2, f"Expected at least two topics, got {topics_emitted}"


@pytest.mark.asyncio
@pytest.mark.parametrize("flow_name", ["single-agent", "multi-agent"])
async def test_baseline_pending_revision_emits_streaming_event(flow_name: str):
    session_id = f"baseline-pending-{flow_name}"
    repo = get_session_state_repository()
    snapshot = SessionStateSnapshot(session_id=session_id)
    snapshot.record_outputs(analysis="Initial summary still streaming.")
    await repo.save(snapshot)

    events: List[Dict[str, Any]] = []
    async for event in analytics_memory_workflow(
        query="analysis: highlight margin signals once ready",
        session_id=session_id,
        flow=flow_name,
    ):
        events.append(event)

    streaming_events = [evt for evt in events if evt.get("event") == "baseline_still_streaming"]
    assert streaming_events, f"Expected baseline_still_streaming event for flow {flow_name}"
    payload = streaming_events[0].get("data", {})
    assert payload.get("flow") == flow_name
    pending_components = payload.get("pending_components") or []
    assert "dataset_preview" in pending_components
    assert payload.get("session_id") == session_id
    assert not any(
        evt.get("event") == "follow_up_route" for evt in events if evt.get("event") != "baseline_still_streaming"
    ), "No follow_up_route expected when baseline is still streaming"

    await repo.delete(session_id)
    await close_session_state_repository()


@pytest.mark.asyncio
async def test_analysis_revision_runs_without_chart_lane():
    session_id = "analysis-lane-no-chart"
    repo = get_session_state_repository()
    snapshot = SessionStateSnapshot(session_id=session_id)
    snapshot.record_outputs(analysis="Original summary for comparison.")
    _seed_revision_snapshot(snapshot)
    await repo.save(snapshot)

    events = []
    async for event in analytics_memory_workflow(
        query="Revise the analysis to highlight cash flow strength",
        session_id=session_id,
        flow="single-agent",
    ):
        events.append(event)

    follow_up_events = [evt for evt in events if evt.get("event") == "follow_up_route"]
    assert follow_up_events, "Expected follow_up_route event for analysis-only revision"
    assert all(evt.get("data", {}).get("route") != "cannot_revise" for evt in follow_up_events)
    assert any(evt.get("event") == "revision_request" for evt in events), "Analysis revision should proceed"

    await repo.delete(session_id)
    await close_session_state_repository()


@pytest.mark.asyncio
async def test_agentic_revision_emits_follow_up_flag(monkeypatch):
    session_id = "agentic-revision-route"
    repo = get_session_state_repository()
    snapshot = SessionStateSnapshot(session_id=session_id)
    snapshot.record_outputs(
        chart_spec={
            "series": [{"type": "line", "name": "Revenue"}],
            "meta": {"chartDesign": {"chart_type": "line"}},
        },
        analysis="Baseline analysis text",
    )
    _seed_revision_snapshot(snapshot)
    await repo.save(snapshot)

    monkeypatch.setenv("AGENTIC_REVISIONS_ENABLED", "1")
    monkeypatch.setenv("AGENTIC_REVISION_SINGLE_AGENT", "1")
    monkeypatch.setenv("ANALYTICS_MEMORY_INSTRUMENT", "1")
    monkeypatch.setattr(
        FollowUpClassifier,
        "classify",
        lambda self, q, snap, lane_readiness=None: FollowUpRoute.FULL_PIPELINE,
    )
    monkeypatch.setattr(
        FollowUpClassifier,
        "detect_revision_targets",
        lambda self, q, snap, lane_readiness=None: set(),
    )
    monkeypatch.setattr("analytics.flows.chart_revision.is_analysis_revision_query", lambda q: False)

    class _FailingSequencer:
        def __init__(self, *args, **kwargs):
            raise AssertionError("PlannerSequencer should not initialize for agentic revisions")

    monkeypatch.setattr("analytics.flows.workflow.PlannerSequencer", _FailingSequencer)

    events = []
    async for event in analytics_memory_workflow(
        query="Refresh the insights with the latest context",
        session_id=session_id,
        flow="single-agent",
    ):
        events.append(event)

    follow_up_events = [evt for evt in events if evt.get("event") == "follow_up_route"]
    assert follow_up_events, "Expected follow_up_route event for agentic revision"
    assert any(evt.get("data", {}).get("agentic_revision") for evt in follow_up_events), follow_up_events

    await repo.delete(session_id)
    await close_session_state_repository()


@pytest.mark.asyncio
async def test_multi_agent_agentic_revision_skips_sequencer(monkeypatch):
    session_id = "multi-agent-agentic-route"
    repo = get_session_state_repository()
    snapshot = SessionStateSnapshot(session_id=session_id)
    snapshot.record_outputs(
        chart_spec={
            "series": [{"type": "line", "name": "Revenue"}],
            "meta": {"chartDesign": {"chart_type": "line"}},
        },
        analysis="Baseline analysis text",
    )
    _seed_revision_snapshot(snapshot, include_market=True)
    await repo.save(snapshot)

    monkeypatch.setenv("AGENTIC_REVISIONS_ENABLED", "1")
    monkeypatch.setenv("AGENTIC_REVISION_MULTI_AGENT", "1")
    monkeypatch.setenv("ANALYTICS_MEMORY_INSTRUMENT", "1")
    monkeypatch.setattr(
        FollowUpClassifier,
        "classify",
        lambda self, q, snap, lane_readiness=None: FollowUpRoute.FULL_PIPELINE,
    )
    monkeypatch.setattr(
        FollowUpClassifier,
        "detect_revision_targets",
        lambda self, q, snap, lane_readiness=None: set(),
    )

    class _FailingSequencer:
        def __init__(self, *args, **kwargs):
            raise AssertionError("PlannerSequencer should not initialize for multi-agent agentic revisions")

    monkeypatch.setattr("analytics.flows.workflow.PlannerSequencer", _FailingSequencer)

    captured: Dict[str, Any] = {}

    async def _fake_events(self, query: str, session_id: Optional[str] = None, *, sequencer=None, sequencer_state=None):
        captured["sequencer"] = sequencer
        captured["agentic_revision_mode"] = bool(getattr(self, "_agentic_revision_mode", False))
        yield {"event": "workflow_complete", "data": {"message": "agentic revision complete"}}

    monkeypatch.setattr("analytics.flows.multi_agent.MultiAgentFlow.events", _fake_events, raising=True)

    events: List[Dict[str, Any]] = []
    async for event in analytics_memory_workflow(
        query="Compare AMD vs NVDA revenue",
        session_id=session_id,
        flow="multi-agent",
    ):
        events.append(event)

    assert captured.get("sequencer") is None, "Agentic multi-agent revisions should skip the sequencer"
    assert captured.get("agentic_revision_mode") is True
    follow_up_events = [evt for evt in events if evt.get("event") == "follow_up_route"]
    assert follow_up_events, "Expected follow_up_route event for multi-agent revision"
    assert any(evt.get("data", {}).get("agentic_revision") for evt in follow_up_events)

    await repo.delete(session_id)
    await close_session_state_repository()


@pytest.mark.asyncio
async def test_market_revision_runs_without_chart_or_analysis():
    session_id = "market-lane-only"
    repo = get_session_state_repository()
    snapshot = SessionStateSnapshot(session_id=session_id)
    snapshot.record_outputs(sql="SELECT 1")
    snapshot.tool_cache.setdefault("analytics", {}).setdefault("artifacts", {})["market"] = {
        "snapshot": {"tickers": ["AMD"], "ready": True}
    }
    await repo.save(snapshot)

    events = []
    async for event in analytics_memory_workflow(
        query="How did AMD stock move versus peers?",
        session_id=session_id,
        flow="single-agent",
    ):
        events.append(event)

    follow_up_events = [evt for evt in events if evt.get("event") == "follow_up_route"]
    assert follow_up_events, "Expected follow_up_route for market-only revision"
    assert all(evt.get("data", {}).get("route") != "cannot_revise" for evt in follow_up_events)
    assert any(evt.get("event") == "revision_request" for evt in events), "Market revision should stream"

    await repo.delete(session_id)
    await close_session_state_repository()


@pytest.mark.asyncio
async def test_followup_generates_search_topics_without_explicit_patch(monkeypatch):
    session_id = "analysis-topic-route"
    repo = get_session_state_repository()
    snapshot = SessionStateSnapshot(session_id=session_id)
    snapshot.record_outputs(
        chart_spec={
            "series": [{"type": "line", "name": "Revenue"}],
            "meta": {"chartDesign": {"chart_type": "line"}},
        },
        analysis="Baseline summary about AMD revenue growth.",
    )
    _seed_revision_snapshot(snapshot)
    async def _fake_topics(query: str, *, session_id: Optional[str] = None, min_topics: int = 2):
        return [SearchTopicPlan(label="Focus", query="amd focus", reason="test")]
    monkeypatch.setattr(
        FollowUpClassifier,
        "classify",
        lambda self, q, snap, lane_readiness=None: FollowUpRoute.REUSE_SQL,
    )
    monkeypatch.setattr(
        FollowUpClassifier,
        "detect_revision_targets",
        lambda self, q, snap, lane_readiness=None: {"analysis"},
    )
    monkeypatch.setattr("analytics.services.response_search.generate_search_topics", _fake_topics)
    monkeypatch.setattr("analytics.services.response_search.has_search_api_key", lambda: True)
    await repo.save(snapshot)

    query = "Can you focus the analysis on AMD margin risks?"
    events: List[Dict[str, Any]] = []
    async for event in analytics_memory_workflow(query=query, session_id=session_id, flow="single-agent"):
        events.append(event)

    revision_requests = [evt for evt in events if evt.get("event") == "revision_request"]
    assert revision_requests, "Expected revision request for follow-up"
    emitted_topics = revision_requests[0].get("data", {}).get("search_topics") or []
    assert len(emitted_topics) >= 2, f"Expected dual topics, received {emitted_topics}"

    stored = await repo.load(session_id)
    directive_meta = stored.last_revision_directive or {}
    topic_payload = directive_meta.get("search_topics") or []
    assert len(topic_payload) >= 2, topic_payload
    first_query = topic_payload[0].get("query")
    assert any(topic.get("query") != first_query for topic in topic_payload[1:]), topic_payload

    await repo.delete(session_id)
    await close_session_state_repository()


@pytest.mark.asyncio
async def test_market_revision_uses_market_lane(monkeypatch):
    session_id = "market-revision-route"
    repo = get_session_state_repository()
    snapshot = SessionStateSnapshot(session_id=session_id)
    snapshot.record_outputs(
        chart_spec={
            "series": [{"type": "line", "name": "Revenue"}],
            "meta": {"chartDesign": {"chart_type": "line"}},
        },
        analysis="Original summary",
    )
    snapshot.record_query("How is AMD revenue trending?", "revenue_trend")
    snapshot.last_sql = "SELECT 1"
    analytics_cache = snapshot.tool_cache.setdefault("analytics", {})
    analytics_cache["artifacts"] = {"market": {"tickers": ["AMD"]}}
    _seed_revision_snapshot(snapshot, include_market=True)
    monkeypatch.setattr(
        FollowUpClassifier,
        "classify",
        lambda self, q, snap, lane_readiness=None: FollowUpRoute.STOCK_ONLY,
    )
    monkeypatch.setattr(
        FollowUpClassifier,
        "detect_revision_targets",
        lambda self, q, snap, lane_readiness=None: {"market"},
    )
    await repo.save(snapshot)

    query = "Refresh the market data for the tickers we discussed"
    events = []
    async for event in analytics_memory_workflow(query=query, session_id=session_id, flow="single-agent"):
        events.append(event)

    follow_up_events = [evt for evt in events if evt.get("event") == "follow_up_route"]
    assert follow_up_events, "Expected follow_up_route event for market revision"
    assert follow_up_events[0].get("data", {}).get("route") == "market_only"
    assert not _has_forbidden_events(events), "Market revision should avoid full pipeline events"

    stored = await repo.load(session_id)
    analytics_cache = stored.tool_cache.get("analytics", {})
    revision_snapshot = analytics_cache.get("revision_snapshot") or {}
    assert revision_snapshot.get("stock_widget")
    assert stored.messages and stored.messages[-1].get("content") == query

    await repo.delete(session_id)
    await close_session_state_repository()


@pytest.mark.asyncio
async def test_revision_rejected_when_artifacts_missing(monkeypatch: pytest.MonkeyPatch):
    session_id = "missing-artifacts"
    repo = get_session_state_repository()
    snapshot = SessionStateSnapshot(session_id=session_id)
    snapshot.record_outputs(chart_spec={"meta": {"chartDesign": {"chart_type": "area"}}})
    await repo.save(snapshot)

    telemetry_calls: List[Dict[str, Any]] = []
    monkeypatch.setattr(
        "analytics.flows.workflow.analysis_inputs_missing",
        lambda **kwargs: telemetry_calls.append(kwargs),
    )

    query = "analysis: Rewrite the summary with new highlights"
    events = []
    async for event in analytics_memory_workflow(query=query, session_id=session_id, flow="single-agent"):
        events.append(event)

    follow_up_events = [evt for evt in events if evt.get("event") == "follow_up_route"]
    assert follow_up_events, "Expected follow_up_route event when revisions cannot run"
    route_payload = follow_up_events[0].get("data", {})
    assert route_payload.get("route") == "cannot_revise"
    banner = route_payload.get("banner") or {}
    assert banner.get("reason") == "missing_analysis_inputs"
    assert set(banner.get("missing_components") or []) >= {"sql", "dataset_preview"}
    assert not _has_forbidden_events(events), "Revision rejection should not trigger pipeline lanes"
    assert telemetry_calls, "analysis_inputs_missing telemetry expected"
    assert set(telemetry_calls[0]["missing_components"]) >= {"sql", "dataset_preview"}

    stored = await repo.load(session_id)
    assert stored is not None
    assert stored.messages, "System message should record the revision skip"
    assert "Revision skipped" in stored.messages[-1].get("content", "")

    await repo.delete(session_id)
    await close_session_state_repository()


@pytest.mark.asyncio
async def test_revision_hint_ignored_without_snapshot():
    session_id = "revision-no-snapshot"
    query = "Can you revise the chart to a scatter plot?"
    events = []

    async for event in analytics_memory_workflow(query=query, session_id=session_id, flow="single-agent"):
        events.append(event)

    assert not any(evt.get("event") == "revision_request" for evt in events), "Fresh sessions should not raise revision lanes"
    follow_up_events = [evt for evt in events if evt.get("event") == "follow_up_route"]
    assert follow_up_events, "Expected follow_up_route event for fresh session"
    assert follow_up_events[0].get("data", {}).get("route") == "full_pipeline"

    repo = get_session_state_repository()
    await repo.delete(session_id)
    await close_session_state_repository()


@pytest.mark.asyncio
async def test_analysis_revision_runs_when_manifest_ready():
    session_id = "analysis-manifest-ready"
    repo = get_session_state_repository()
    snapshot = SessionStateSnapshot(session_id=session_id)
    snapshot.record_outputs(sql="SELECT 1")
    snapshot.record_tool_result("planner_dataset_preview", {"rows": [{"label": "Q1"}], "row_count": 1})
    snapshot.record_tool_result("planner_stock_widget", {"snapshot": {"ACME": {"price": 100}}})
    snapshot.record_tool_result("web_search", {"summary": "cached context", "snippets": [{"title": "news"}]})
    assert snapshot.last_analysis is None, "Baseline should not persist analysis text"
    await repo.save(snapshot)

    events = []
    async for event in analytics_memory_workflow(
        query="analysis: tighten the summary language",
        session_id=session_id,
        flow="single-agent",
    ):
        events.append(event)

    follow_up_events = [evt for evt in events if evt.get("event") == "follow_up_route"]
    assert follow_up_events, "Expected follow_up_route event for analysis revision"
    assert follow_up_events[0].get("data", {}).get("route") != "cannot_revise"
    assert any(evt.get("event") == "revision_request" for evt in events), "Revision directive should emit"
    assert any(evt.get("event") not in {"follow_up_route"} for evt in events if evt.get("event")), "Pipeline should execute"

    await repo.delete(session_id)
    await close_session_state_repository()


@pytest.mark.asyncio
async def test_planner_revision_reuses_manifest_without_analysis(monkeypatch):
    session_id = "planner-manifest-ready"
    repo = get_session_state_repository()
    snapshot = SessionStateSnapshot(session_id=session_id)
    snapshot.record_outputs(sql="SELECT 42")
    snapshot.record_tool_result("planner_dataset_preview", {"rows": [{"label": "Q1"}], "row_count": 1})
    snapshot.record_tool_result("planner_stock_widget", {"snapshot": {"ACME": {"price": 111}}})
    snapshot.record_tool_result("web_search", {"summary": "cached context", "snippets": [{"title": "delta"}]})
    await repo.save(snapshot)

    created = []

    class _PlannerStub:
        flow_label = "planner-stub"

        def __init__(self) -> None:
            self.session_follow_up = None
            self.lane_refresh_requirements: Dict[str, bool] = {}
            self.analysis_refresh_mode: Optional[str] = None
            self.revision_directive = None
            self.snapshot: Optional[SessionStateSnapshot] = None
            self.revision_targets: Set[str] = set()
            self.follow_up_route = None
            self.ran_analysis_refresh = False
            self.requested_focus: Optional[str] = None
            created.append(self)

        def set_session_follow_up(self, value: bool) -> None:
            self.session_follow_up = value

        def set_lane_refresh_requirements(self, requirements: Dict[str, bool]) -> None:
            self.lane_refresh_requirements = dict(requirements)

        def set_analysis_refresh_mode(self, mode: str) -> None:
            self.analysis_refresh_mode = mode

        def set_revision_directive(self, directive) -> None:
            self.revision_directive = directive

        def prime_with_snapshot(self, snapshot: SessionStateSnapshot) -> None:
            self.snapshot = snapshot

        def set_revision_targets(self, targets) -> None:
            self.revision_targets = set(targets)

        def set_follow_up_route(self, route) -> None:
            self.follow_up_route = route

        async def run_analysis_refresh(
            self,
            *,
            session_id: str,
            query: str,
            requested_focus: Optional[str],
            revision_directive,
            reason: Optional[str] = None,
            source: Optional[str] = None,
        ):
            self.ran_analysis_refresh = True
            self.requested_focus = requested_focus
            yield {
                "event": "analysis_revision",
                "data": {
                    "lane": "analysis",
                    "revision": True,
                    "session_id": session_id,
                    "source": source or "analytics_memory_workflow",
                    "requested_focus": requested_focus,
                },
            }

    def _factory():
        return _PlannerStub()

    monkeypatch.setitem(workflow_module.FLOW_FACTORIES, "planner-executor", _factory)
    monkeypatch.setattr(
        FollowUpClassifier,
        "classify",
        lambda self, q, snap, lane_readiness=None: FollowUpRoute.REUSE_SQL,
    )
    monkeypatch.setattr(
        FollowUpClassifier,
        "detect_revision_targets",
        lambda self, q, snap, lane_readiness=None: {"analysis"},
    )
    monkeypatch.setattr("analytics.services.response_search.generate_search_topics", lambda *args, **kwargs: [])
    monkeypatch.setattr("analytics.services.response_search.has_search_api_key", lambda: False)

    query = "analysis: re-run with updated macro commentary"
    events = []
    async for event in analytics_memory_workflow(
        query=query,
        session_id=session_id,
        flow="planner-executor",
    ):
        events.append(event)

    follow_up_events = [evt for evt in events if evt.get("event") == "follow_up_route"]
    assert follow_up_events, "Expected follow_up_route event for planner manifest revision"
    route_value = follow_up_events[0].get("data", {}).get("route")
    assert route_value in {"analysis_only", "mixed_revision"}
    assert any(evt.get("event") == "analysis_revision" for evt in events), "Analysis lane should execute"
    assert created, "Planner stub was not instantiated"
    stub = created[-1]
    assert stub.ran_analysis_refresh is True
    assert stub.requested_focus is not None
    assert stub.snapshot is not None and stub.snapshot.last_analysis is None
    assert stub.revision_targets == {"analysis", "web"}, f"Expected analysis/web targets, got {stub.revision_targets}"

    await repo.delete(session_id)
    await close_session_state_repository()

def _seed_revision_snapshot(snapshot: SessionStateSnapshot, *, include_market: bool = False) -> None:
    snapshot.record_query("How is AMD revenue trending?", "revenue_trend")
    snapshot.record_outputs(sql="SELECT 1")
    analytics_cache = snapshot.tool_cache.setdefault("analytics", {})
    chart_spec = snapshot.last_chart_spec or {
        "series": [{"type": "line", "name": "Revenue"}],
        "meta": {"chartDesign": {"chart_type": "line"}},
    }
    analysis_text = snapshot.last_analysis or ""
    payload = {
        "intent_signature": {"intent_key": "revenue_trend", "slots": {"metric": "revenue"}},
        "intent": {
            "intent_key": "revenue_trend",
            "confidence": 0.9,
            "slots_detected": {"metric": "revenue"},
            "assumptions": [],
            "clarifications_suggested": [],
            "possible_intents": [],
            "intent_reasoning": "test snapshot",
        },
        "plan": {
            "metrics": ["revenue"],
            "derived_metrics": [],
            "timeframe": {"years_back": 3},
            "granularity": "annual",
            "comparison": None,
            "statistic": None,
            "group_by": [],
            "filters": {},
        },
        "slot_statuses": {
            "metric": {
                "status": "filled",
                "value": "revenue",
                "reason": "snapshot seed",
                "suggestions": [],
                "allow_custom": True,
            }
        },
        "slot_followups": [],
        "clarifications": [],
        "clarification_rounds": 0,
        "sql": "SELECT 1",
        "sql_row_count": 10,
        "columns": ["period", "revenue"],
        "data_sample": [{"period": "2023", "revenue": 100}],
        "chart_spec": chart_spec,
        "analysis": analysis_text,
        "analysis_length": len(analysis_text),
        "web_context": {
            "ready": True,
            "summary": "Baseline context",
            "snippets": [],
            "search_topic": "baseline revenue trend",
            "latency_ms": 120,
        },
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    if include_market:
        payload["stock_widget"] = {
            "ready": True,
            "tickers": ["AMD"],
            "snapshot": {"AMD": {"price": 100.0}},
        }
    analytics_cache["revision_snapshot"] = payload
    snapshot.record_tool_result(
        "planner_dataset_preview",
        {"rows": [{"period": "2023", "revenue": 100}], "row_count": 1},
    )
    snapshot.record_tool_result(
        "web_search",
        {
            "ready": True,
            "summary": "Baseline context",
            "snippets": [{"title": "Revenue update", "url": "https://example.com/revenue"}],
        },
    )
    if include_market:
        snapshot.record_tool_result(
            "planner_stock_widget",
            {
                "snapshot": {
                    "AMD": {
                        "price": 100.0,
                        "change": 1.2,
                        "change_percent": 1.1,
                    }
                }
            },
        )
    snapshot.refresh_analysis_inputs_manifest(persist=False)






