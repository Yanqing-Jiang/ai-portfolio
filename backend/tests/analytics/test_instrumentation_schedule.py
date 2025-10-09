import pytest

from analytics.flows.instrumentation import instrument_events
from analytics.flows.schedulers import FlowMode


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
