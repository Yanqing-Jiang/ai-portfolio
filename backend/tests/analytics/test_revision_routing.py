import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[2]))

import pytest
from typing import Dict, List, Optional
from datetime import datetime, timezone

from analytics.flows.workflow import analytics_memory_workflow
from analytics.routing import FollowUpRoute
from analytics.routing.follow_up_classifier import FollowUpClassifier
from analytics.services.response_search import SearchTopicPlan
from analytics.services.polygon import DailyBar, MarketSnapshot
from analytics.core.session_state import SessionStateSnapshot, get_session_state_repository, close_session_state_repository


FORBIDDEN_PIPELINE_EVENTS = {
    "classification_started",
    "classification_complete",
    "intent_detection_complete",
    "intent_detection_started",
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
    monkeypatch.setattr(FollowUpClassifier, "classify", lambda self, q, snap: FollowUpRoute.REUSE_SQL)
    monkeypatch.setattr(FollowUpClassifier, "detect_revision_targets", lambda self, q, snap: {"analysis"})
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
    web_events = [evt for evt in events if evt.get("event") == "web_revision_ready"]
    assert web_events, "Expected web_revision_ready event before analysis refresh"
    web_data = web_events[0].get("data", {})
    assert web_data.get("source") == "fresh_revision"
    assert web_data.get("from_cache") is False
    analysis_events = [
        evt
        for evt in events
        if evt.get("event") in {"analysis_revision", "analysis_revision_ready", "analysis_ready", "analysis_complete"}
    ]
    assert analysis_events, "Expected analysis completion events during revision"
    web_index = events.index(web_events[0])
    analysis_index = events.index(analysis_events[0])
    assert web_index < analysis_index, "Web refresh should complete before analysis events"
    assert not any(evt.get("event") in {"market_refresh", "market_revision_ready"} for evt in events), "Market lane should stay unused"

    stored = await repo.load(session_id)
    analytics_cache = stored.tool_cache.get("analytics", {})
    revision_snapshot = analytics_cache.get("revision_snapshot") or {}
    assert "intent" in revision_snapshot and "plan" in revision_snapshot and "slot_statuses" in revision_snapshot
    assert stored.messages and stored.messages[-1].get("content") == query
    directive_meta = stored.last_revision_directive or {}
    lane_meta = directive_meta.get("lane_refresh_required") or {}
    assert lane_meta.get("analysis") is True
    assert lane_meta.get("web") is True
    assert lane_meta.get("market") is False
    assert directive_meta.get("revision_lanes") == ["analysis", "web"]
    topic_payload = directive_meta.get("search_topics") or []
    assert len(topic_payload) >= 2
    baseline_query = topic_payload[0].get("query")
    assert any(topic.get("query") != baseline_query for topic in topic_payload[1:]), topic_payload

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
    monkeypatch.setattr(FollowUpClassifier, "classify", lambda self, q, snap: FollowUpRoute.REUSE_SQL)
    monkeypatch.setattr(FollowUpClassifier, "detect_revision_targets", lambda self, q, snap: {"analysis"})
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
    monkeypatch.setattr(FollowUpClassifier, "classify", lambda self, q, snap: FollowUpRoute.STOCK_ONLY)
    monkeypatch.setattr(FollowUpClassifier, "detect_revision_targets", lambda self, q, snap: {"market"})
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
async def test_revision_rejected_when_artifacts_missing():
    session_id = "missing-artifacts"
    repo = get_session_state_repository()
    snapshot = SessionStateSnapshot(session_id=session_id)
    snapshot.record_outputs(chart_spec={"meta": {"chartDesign": {"chart_type": "area"}}})
    await repo.save(snapshot)

    query = "analysis: Rewrite the summary with new highlights"
    events = []
    async for event in analytics_memory_workflow(query=query, session_id=session_id, flow="single-agent"):
        events.append(event)

    follow_up_events = [evt for evt in events if evt.get("event") == "follow_up_route"]
    assert follow_up_events, "Expected follow_up_route event when revisions cannot run"
    route_payload = follow_up_events[0].get("data", {})
    assert route_payload.get("route") == "cannot_revise"
    banner = route_payload.get("banner") or {}
    assert banner.get("reason") == "missing_analysis"
    assert not _has_forbidden_events(events), "Revision rejection should not trigger pipeline lanes"

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

def _seed_revision_snapshot(snapshot: SessionStateSnapshot, *, include_market: bool = False) -> None:
    snapshot.record_query("How is AMD revenue trending?", "revenue_trend")
    snapshot.last_sql = "SELECT 1"
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






