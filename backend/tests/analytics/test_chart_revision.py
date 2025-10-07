import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[2]))

import pytest

from analytics.flows import planner_executor
from analytics.core.session_state import SessionStateSnapshot, get_session_state_repository


@pytest.mark.asyncio
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

