import time

import pytest

from analytics.core.events import TimedEventEmitter
from analytics.core.session_state import SessionStateSnapshot
from analytics.flows import planner_executor


@pytest.mark.asyncio
async def test_initialize_context_skips_snapshot_for_fresh_runs():
    pipeline = planner_executor.PlannerPipeline()
    snapshot = SessionStateSnapshot(session_id="sess-123")
    snapshot.last_sql = "select 1"
    pipeline._prefetched_snapshot = snapshot

    ctx = await planner_executor._initialize_context(pipeline, "latest revenue", None)

    assert ctx.revision_snapshot is None
    assert ctx.revision_context is None


def _fresh_context() -> planner_executor.PlannerPhaseContext:
    return planner_executor.PlannerPhaseContext(
        query="test",
        session_id="sess-test",
        workflow_start=time.time(),
        timed_emitter=TimedEventEmitter(session_id="sess-test", flow="planner-executor"),
    )


def test_ingest_tool_event_emits_fresh_completion():
    pipeline = planner_executor.PlannerPipeline()
    ctx = _fresh_context()
    ctx.force_full_fresh_pipeline = True

    events = pipeline._ingest_tool_event(
        ctx,
        {
            "event": "tool_parallel_result",
            "data": {
                "tool": "web_retriever",
                "status": "completed",
                "payload": {"ready": True},
            },
        },
    )

    assert any(
        evt.get("event") == "progress"
        and evt.get("data", {}).get("lane") == "web"
        and evt.get("data", {}).get("status") == "completed"
        for evt in events
    )


def test_fresh_lane_event_emits_telemetry_once(monkeypatch):
    pipeline = planner_executor.PlannerPipeline()
    ctx = _fresh_context()
    ctx.force_full_fresh_pipeline = True

    recorded = []

    def _capture(**kwargs):
        recorded.append(kwargs)

    monkeypatch.setattr(planner_executor.telemetry, "fresh_pipeline_lane", _capture)

    first = pipeline._maybe_emit_fresh_lane_event(ctx, "sql", "started")
    duplicate = pipeline._maybe_emit_fresh_lane_event(ctx, "sql", "started")
    completed = pipeline._maybe_emit_fresh_lane_event(ctx, "sql", "completed")

    assert first is not None
    assert duplicate is None
    assert completed is not None
    assert completed["data"]["status"] == "completed"
    assert [entry["status"] for entry in recorded] == ["started", "completed"]
