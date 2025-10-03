import pytest
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
BACKEND_ROOT = ROOT / "backend"
for entry in (ROOT, BACKEND_ROOT):
    entry_str = str(entry)
    if entry_str not in sys.path:
        sys.path.insert(0, entry_str)

pytestmark = pytest.mark.anyio("asyncio")


@pytest.fixture
def anyio_backend():
    return "asyncio"


try:
    from analytics.flows import multi_agent
except ModuleNotFoundError as exc:
    pytest.skip(f"multi_agent dependencies missing: {exc}", allow_module_level=True)


class DummyPlanner:
    def __init__(self, events):
        self._events = events

    async def events(self, query: str, session_id=None):
        for event in self._events:
            yield event


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
            "data": {"llm_used": "planner", "template_fallback": False, "sql": "SELECT * FROM metrics"},
        },
        {"event": "progress", "data": {"step": "sql_validation"}},
        {"event": "sql_validated", "data": {"ok": True, "issues_count": 0}},
        {"event": "progress", "data": {"step": "sql_execution"}},
        {"event": "execution_stats", "data": {"row_count": 42}},
        {"event": "progress", "data": {"step": "chart_generation"}},
        {
            "event": "chart_generated",
            "data": {
                "chart_type": "line_multi",
                "chart_spec": {"type": "line", "datasets": [{"id": 1}]},
            },
        },
        {"event": "progress", "data": {"step": "analysis_generation"}},
        {"event": "analysis_streaming", "data": {"partial_analysis": "partial reasoning chunk"}},
        {"event": "analysis_complete", "data": {"analysis": "final text", "analysis_length": 128}},
    ]

    monkeypatch.setattr(multi_agent, "PlannerExecutorFlow", lambda: DummyPlanner(planner_events))
    async def _mock_market_agent(context):
        return multi_agent.AgentResult(name='market', output={'status': 'skip', 'tickers': []})
    monkeypatch.setattr(multi_agent, "_market_agent", _mock_market_agent)

    flow = multi_agent.MultiAgentFlow()
    emitted = [event async for event in flow.events("demo question about NVDA")]

    agent_turns = [event for event in emitted if event.get("event") == "agent_turn"]
    reasoning_events = [event for event in emitted if event.get("event") == "agent_reasoning"]

    # original planner phases still surface agent_turn telemetry
    sql_turn = next(
        event
        for event in agent_turns
        if event["data"]["role"] == "sql_specialist" and event["data"]["status"] == "complete"
    )
    assert sql_turn["data"]["summary"]["llm_used"] == "planner"

    viz_turn = next(
        event
        for event in agent_turns
        if event["data"]["role"] == "viz_designer" and event["data"]["status"] == "complete"
    )
    assert viz_turn["data"]["summary"]["chart_type"] == "line_multi"

    # orchestrator adds planner/analyst/chart/market roles
    orchestrated_roles = {"planner_agent", "analyst_agent", "chart_agent", "market_agent"}
    orchestrated = {
        event["data"]["role"]: event
        for event in agent_turns
        if event["data"].get("role") in orchestrated_roles and event["data"].get("status") == "complete"
    }
    assert orchestrated_roles.issubset(orchestrated.keys())

    planner_summary = orchestrated["planner_agent"]["data"].get("summary", {})
    assert planner_summary.get("bundle_id")
    assert planner_summary.get("tasks")

    chart_summary = orchestrated["chart_agent"]["data"].get("summary", {})
    assert chart_summary.get("chart", {}).get("spec_id")

    market_summary = orchestrated["market_agent"]["data"].get("summary", {})
    assert market_summary.get("tickers") == ["NVDA"]

    # reasoning now includes planner reflections as well as analyst output
    planner_thought = next(
        event
        for event in reasoning_events
        if event["data"].get("role") == "planner_agent"
    )
    assert "bundle" in planner_thought["data"]["thought"]

    insight_thought = next(
        event
        for event in reasoning_events
        if event["data"].get("role") == "insight_reviewer"
    )
    assert "partial" in insight_thought["data"]["thought"]
