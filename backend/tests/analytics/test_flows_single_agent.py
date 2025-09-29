import pytest

from analytics.flows import single_agent_tools


class DummyPlanner:
    def __init__(self, events):
        self._events = events

    async def events(self, query: str, session_id=None):
        for event in self._events:
            yield event


@pytest.mark.asyncio
async def test_single_agent_injects_tool_call_events(monkeypatch):
    planner_events = [
        {"event": "progress", "data": {"step": "intent_detection"}},
        {"event": "intent_detection_complete", "data": {"intent_key": "market_share_all", "confidence": 0.92}},
        {"event": "progress", "data": {"step": "sql_compilation"}},
        {"event": "sql_compiled", "data": {"template_used": "market_share_trend", "sql_length": 118}},
        {"event": "sql_generated", "data": {"sql": "SELECT * FROM metrics"}},
        {"event": "progress", "data": {"step": "sql_validation"}},
        {"event": "sql_validated", "data": {"ok": True, "issues_count": 0}},
        {"event": "progress", "data": {"step": "sql_execution"}},
        {"event": "execution_stats", "data": {"row_count": 123}},
        {"event": "progress", "data": {"step": "analysis_generation"}},
        {"event": "analysis_complete", "data": {"analysis": "done", "analysis_length": 256}},
    ]

    monkeypatch.setattr(single_agent_tools, "PlannerExecutorFlow", lambda: DummyPlanner(planner_events))

    flow = single_agent_tools.SingleAgentToolsFlow()
    emitted = [event async for event in flow.events("demo question")]

    tool_events = [event for event in emitted if event.get("event") == "tool_call"]
    starts = [event["data"]["tool"] for event in tool_events if event["data"]["status"] == "start"]
    assert starts == [
        "intent_classifier",
        "sql_generator",
        "sql_validator",
        "sql_executor",
        "analysis_writer",
    ]

    sql_summary = next(
        event
        for event in tool_events
        if event["data"]["tool"] == "sql_generator" and event["data"]["status"] == "end"
    )
    assert sql_summary["data"]["details"]["template_used"] == "market_share_trend"
    assert sql_summary["data"]["details"]["sql_length"] == 118

    executor_summary = next(
        event
        for event in tool_events
        if event["data"]["tool"] == "sql_executor" and event["data"]["status"] == "end"
    )
    assert executor_summary["data"]["details"]["row_count"] == 123

    analysis_summary = next(
        event
        for event in tool_events
        if event["data"]["tool"] == "analysis_writer" and event["data"]["status"] == "end"
    )
    assert analysis_summary["data"]["details"]["analysis_length"] == 256
