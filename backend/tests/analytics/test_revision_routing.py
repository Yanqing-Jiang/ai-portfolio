import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[2]))

import pytest

from analytics.flows.workflow import analytics_memory_workflow
from analytics.core.session_state import SessionStateSnapshot, get_session_state_repository, close_session_state_repository


@pytest.mark.asyncio
async def test_chart_revision_routed_fast_path():
    session_id = "chart-revision-route"
    repo = get_session_state_repository()
    snapshot = SessionStateSnapshot(session_id=session_id)
    snapshot.record_outputs(
        chart_spec={
            "series": [{"type": "line", "name": "Revenue"}],
            "meta": {"chartDesign": {"chart_type": "line"}},
        }
    )
    await repo.save(snapshot)

    query = "Please revise the chart to a bar chart"
    events = []
    async for event in analytics_memory_workflow(query=query, session_id=session_id, flow="single-agent"):
        events.append(event)

    chart_events = [evt for evt in events if evt.get("event") == "chart_patch"]
    assert chart_events, "Expected a chart_patch event from revision fast-path"
    patch_event = chart_events[-1]
    ops = patch_event.get("data", {}).get("ops", [])
    assert ops and ops[0].get("op") == "set_chart_type" and ops[0].get("value") == "bar"

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
        }
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
async def test_analysis_revision_routed_fast_path():
    session_id = "analysis-revision-route"
    repo = get_session_state_repository()
    snapshot = SessionStateSnapshot(session_id=session_id)
    snapshot.record_outputs(analysis="Original summary")
    await repo.save(snapshot)

    query = "analysis: Updated summary focusing on YoY growth"
    events = []
    async for event in analytics_memory_workflow(query=query, session_id=session_id, flow="single-agent"):
        events.append(event)

    analysis_events = [evt for evt in events if evt.get("event") == "analysis_revision"]
    assert analysis_events, "Expected an analysis_revision event from revision fast-path"
    revision_event = analysis_events[-1]
    assert revision_event.get("data", {}).get("analysis") == "Updated summary focusing on YoY growth"

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
