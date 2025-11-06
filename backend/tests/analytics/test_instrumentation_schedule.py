import pytest

from analytics.flows.instrumentation import instrument_events
from analytics.flows.schedulers import FlowMode
from analytics.core.session_state import SessionStateRepository, SessionStateSnapshot


class StubFlow:
    def __init__(self, mode: FlowMode, events):
        self.flow_mode = mode
        self.flow_label = mode.value
        self._events = events

    async def events(self, query: str, session_id: str = None):
        for event in self._events:
            yield event


@pytest.mark.asyncio
async def test_single_agent_parallel_group_from_schedule():
    events = [
        {"event": "classification_complete", "data": {"confidence": 0.99}},
        {
            "event": "tool_parallel_result",
            "data": {
                "tool": "web_retriever_cached",
                "payload": {"query_terms": "amd"},
            },
        },
    ]
    flow = StubFlow(FlowMode.SINGLE_AGENT, events)
    collected = []
    async for emitted in instrument_events(flow, "AMD revenue", session_id="sched-1", flow_label="single-agent"):
        collected.append(emitted)
    assert collected[0]["data"]["parallel_group"] == "core_sequential"
    assert collected[0]["data"]["schedule_stage"] == "classification"
    assert collected[1]["data"]["parallel_group"] == "tool_fanout"
    assert collected[1]["data"]["schedule_stage"] == "accessories_pre_analysis"


@pytest.mark.asyncio
async def test_multi_agent_supervisor_stage_metadata():
    events = [
        {"event": "agent_reasoning", "data": {"role": "supervisor"}},
        {"event": "analysis_complete", "data": {"analysis": "done"}},
    ]
    flow = StubFlow(FlowMode.MULTI_AGENT, events)
    emitted = []
    async for event in instrument_events(flow, "Compare AMD and NVDA", session_id="sched-2", flow_label="multi-agent"):
        emitted.append(event)
    assert emitted[0]["data"]["parallel_group"] == "supervisor"
    assert emitted[0]["data"]["schedule_stage"] == "supervisor"
    assert emitted[1]["data"]["parallel_group"] == "analysis_stream"
    assert emitted[1]["data"]["schedule_stage"] == "analysis"


@pytest.mark.asyncio
async def test_direct_schedule_chart_stage_alignment():
    events = [
        {"event": "chart_spec_ready", "data": {"chart_spec": {"id": "chart-1"}}},
        {"event": "workflow_complete", "data": {"status": "ok"}},
    ]
    flow = StubFlow(FlowMode.DIRECT, events)
    emitted = []
    async for event in instrument_events(flow, "Show dividend leaders", session_id="sched-3", flow_label="planner"):
        emitted.append(event)
    assert emitted[0]["data"]["parallel_group"] == "core_sequential"
    assert emitted[0]["data"]["schedule_stage"] == "chart"
    assert emitted[1]["data"]["parallel_group"] == "core_sequential"
    assert emitted[1]["data"]["schedule_stage"] == "analysis"


@pytest.mark.asyncio
async def test_analysis_complete_persists_analysis(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _noop(self):  # type: ignore[return-value]
        return None

    monkeypatch.setattr(SessionStateRepository, "_ensure_redis", _noop, raising=False)
    repository = SessionStateRepository()
    snapshot = SessionStateSnapshot(session_id="analysis-persist")
    await repository.save(snapshot)
    monkeypatch.setattr(
        "analytics.flows.instrumentation.get_session_state_repository",
        lambda: repository,
    )

    events = [
        {
            "event": "analysis_complete",
            "data": {
                "analysis": "Revenue growth outpaced peers.",
                "analysis_length": 34,
                "schedule_stage": "analysis",
            },
        }
    ]
    flow = StubFlow(FlowMode.SINGLE_AGENT, events)
    async for _ in instrument_events(
        flow,
        "Persist analysis",
        session_id="analysis-persist",
        flow_label="single-agent",
    ):
        pass

    stored = await repository.load("analysis-persist")
    assert stored is not None
    assert stored.last_analysis == "Revenue growth outpaced peers."
    analytics_cache = stored.tool_cache.get("analytics") if isinstance(stored.tool_cache, dict) else None
    assert analytics_cache and analytics_cache.get("last_analysis_length") == 34
    await repository.close()


@pytest.mark.asyncio
async def test_instrument_events_includes_agent_metadata(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _no_redis(self):  # type: ignore[return-value]
        return None

    monkeypatch.setattr(SessionStateRepository, "_ensure_redis", _no_redis, raising=False)
    repository = SessionStateRepository()
    snapshot = SessionStateSnapshot(session_id="agents-metadata")
    snapshot.record_agent_run(
        run_id="run-supervisor",
        trace_id="trace-supervisor",
        manager_trace_id="manager-trace",
        model="gpt-5-mini-2025-08-07",
        tool_attempts={"sql_executor": 1},
        retry_counts={"sql_executor": 0},
        receipts={"sql_executor": {"status": "completed"}},
    )
    await repository.save(snapshot)
    monkeypatch.setattr(
        "analytics.flows.instrumentation.get_session_state_repository",
        lambda: repository,
    )

    events = [{"event": "status", "data": {"step": "sql_executor"}}]
    flow = StubFlow(FlowMode.MULTI_AGENT, events)
    emitted = []
    async for event in instrument_events(
        flow,
        "Collect metadata",
        session_id="agents-metadata",
        flow_label="multi-agent",
    ):
        emitted.append(event)

    assert emitted, "expected instrumented events"
    metadata = emitted[0]["data"].get("agent_metadata")
    assert metadata is not None
    assert metadata["managerTraceId"] == "manager-trace"
    assert metadata["toolAttempts"]["sql_executor"] == 1
    assert metadata["retryCounts"]["sql_executor"] == 0
    await repository.close()
