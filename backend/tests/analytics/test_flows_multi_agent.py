import pytest

from analytics.flows import multi_agent


class DummyPlanner:
    def __init__(self, events):
        self._events = events

    async def events(self, query: str, session_id=None):
        for event in self._events:
            yield event


@pytest.mark.asyncio
async def test_multi_agent_emits_turns_and_reasoning(monkeypatch):
    planner_events = [
        {"event": "progress", "data": {"step": "intent_detection"}},
        {
            "event": "intent_detection_complete",
            "data": {"intent_key": "market_share_all", "confidence": 0.88, "slots_detected": {"company": "NVDA"}},
        },
        {"event": "progress", "data": {"step": "sql_compilation"}},
        {
            "event": "sql_generated",
            "data": {"llm_used": "planner", "template_fallback": False},
        },
        {"event": "progress", "data": {"step": "sql_validation"}},
        {"event": "sql_validated", "data": {"ok": True, "issues_count": 0}},
        {"event": "progress", "data": {"step": "sql_execution"}},
        {"event": "execution_stats", "data": {"row_count": 42}},
        {"event": "progress", "data": {"step": "chart_generation"}},
        {"event": "chart_generated", "data": {"chart_type": "line_multi"}},
        {"event": "progress", "data": {"step": "analysis_generation"}},
        {"event": "analysis_streaming", "data": {"partial_analysis": "partial reasoning chunk"}},
        {"event": "analysis_complete", "data": {"analysis": "final text", "analysis_length": 128}},
    ]

    monkeypatch.setattr(multi_agent, "PlannerExecutorFlow", lambda: DummyPlanner(planner_events))

    flow = multi_agent.MultiAgentFlow()
    emitted = [event async for event in flow.events("demo question")]

    agent_turns = [event for event in emitted if event.get("event") == "agent_turn"]
    reasoning_events = [event for event in emitted if event.get("event") == "agent_reasoning"]

    assert agent_turns[0]["data"]["role"] == "intent_analyst"
    assert agent_turns[0]["data"]["status"] == "start"
    assert agent_turns[1]["data"]["role"] == "intent_analyst"
    assert agent_turns[1]["data"]["status"] == "complete"

    sql_turn = next(
        event
        for event in agent_turns
        if event["data"]["role"] == "sql_specialist" and event["data"]["status"] == "complete"
    )
    assert sql_turn["data"]["summary"]["llm_used"] == "planner"

    insight_turn = next(
        event
        for event in agent_turns
        if event["data"]["role"] == "insight_reviewer" and event["data"]["status"] == "complete"
    )
    assert insight_turn["data"]["summary"]["analysis_length"] == 128

    data_engineer_turn = next(
        event
        for event in agent_turns
        if event["data"]["role"] == "data_engineer" and event["data"]["status"] == "complete"
    )
    assert data_engineer_turn["data"]["summary"]["rows"] == 42

    viz_turn = next(
        event
        for event in agent_turns
        if event["data"]["role"] == "viz_designer" and event["data"]["status"] == "complete"
    )
    assert viz_turn["data"]["summary"]["chart_type"] == "line_multi"

    assert reasoning_events
    assert reasoning_events[0]["data"]["role"] == "insight_reviewer"
    assert "partial" in reasoning_events[0]["data"]["thought"]
