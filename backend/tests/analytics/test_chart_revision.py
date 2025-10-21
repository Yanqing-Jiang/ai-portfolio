import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[2]))

import pytest

from analytics.flows import planner_executor
from analytics.flows.single_agent_tools import SingleAgentController
from analytics.core.session_state import SessionStateSnapshot, get_session_state_repository
from analytics.routing import FollowUpRoute


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.anyio("asyncio")
async def test_emit_chart_patch_updates_snapshot():
    repo = get_session_state_repository()
    session_id = "chart-revision-test"
    snapshot = SessionStateSnapshot(session_id=session_id)
    snapshot.record_outputs(chart_spec={
        "series": [{"type": "line"}],
        "meta": {"chartDesign": {"chart_type": "line"}},
    })
    await repo.save(snapshot)

    flow = planner_executor.PlannerExecutorFlow()
    patch_payload = {"ops": [{"op": "set_chart_type", "value": "bar"}], "reason": "Switch"}

    events = []
    async for event in flow.emit_chart_patch(session_id=session_id, patch=patch_payload):
        events.append(event)

    assert any(evt.get("event") == "chart_patch" for evt in events)
    patch_event = next(evt for evt in events if evt.get("event") == "chart_patch")
    assert patch_event["data"]["ops"][0]["value"] == "bar"

    updated_snapshot = await repo.load(session_id)
    assert updated_snapshot is not None
    assert (updated_snapshot.last_chart_spec or {}).get("meta", {}).get("chartDesign", {}).get("chart_type") == "bar"

    await repo.delete(session_id)


@pytest.mark.anyio("asyncio")
async def test_chart_revision_missing_session_guidance():
    repo = get_session_state_repository()
    session_id = "chart-revision-missing-session-guidance"
    await repo.delete(session_id)

    controller = SingleAgentController()
    patch_payload = {"ops": [{"op": "set_chart_type", "value": "bar"}], "reason": "Switch"}

    events = []
    async for event in controller.chart_revision(
        session_id=session_id,
        patch=patch_payload,
        query="Switch chart to bar",
        reason="revision_request",
        source="test",
    ):
        events.append(event)

    error_event = next(evt for evt in events if evt.get("event") == "error")
    assert error_event["data"]["code"] == "CHART_REVISION_MISSING_SESSION"

    final_event = next(evt for evt in events if evt.get("event") == "final_answer")
    message = (final_event.get("data") or {}).get("message") or ""
    assert "couldn't apply the chart update" in message.lower()
    assert final_event["data"]["follow_up_route"] == FollowUpRoute.FULL_PIPELINE.value

