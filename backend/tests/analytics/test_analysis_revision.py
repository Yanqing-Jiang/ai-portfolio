import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[2]))

import pytest

from analytics.flows import planner_executor
from analytics.core.session_state import SessionStateSnapshot, get_session_state_repository, close_session_state_repository


@pytest.mark.asyncio
async def test_emit_analysis_revision_updates_snapshot():
    repo = get_session_state_repository()
    session_id = "analysis-revision-test"
    snapshot = SessionStateSnapshot(session_id=session_id)
    snapshot.record_outputs(analysis="Original analysis")
    await repo.save(snapshot)

    flow = planner_executor.PlannerExecutorFlow()
    events = []
    async for event in flow.emit_analysis_revision(
        session_id=session_id,
        analysis="Updated analysis narrative",
        reason="user_revision",
    ):
        events.append(event)

    analysis_events = [evt for evt in events if evt.get("event") == "analysis_revision"]
    assert analysis_events, "Expected analysis_revision event to be emitted"
    final_event = analysis_events[-1]
    assert final_event.get("data", {}).get("analysis") == "Updated analysis narrative"

    updated_snapshot = await repo.load(session_id)
    assert updated_snapshot is not None
    assert updated_snapshot.last_analysis == "Updated analysis narrative"

    await repo.delete(session_id)
    await close_session_state_repository()
