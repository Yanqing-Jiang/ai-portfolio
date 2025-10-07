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
