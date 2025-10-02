import pytest

from analytics.flows.multi_agent import _derive_tasks, _query_agent
from analytics.flows.orchestrator import AgentRunContext, AgentResult


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.anyio("asyncio")
async def test_query_agent_summarizes_attempts():
    attempts = [
        {
            "attempt": 1,
            "source": "planner_llm",
            "status": "validation_failed",
            "error_code": "SQL_VALIDATION_FAILED",
            "error_detail": "bad filter",
        },
        {
            "attempt": 2,
            "source": "query_agent",
            "status": "success",
            "error_code": None,
            "error_detail": None,
        },
    ]
    shared = {
        "sql": {"attempts": attempts},
        "planner": {"tickers": ["NVDA"]},
        "analysis": {},
        "chart": {},
        "market": {},
        "_runtime": {},
    }
    planner_result = AgentResult(
        name="planner",
        output={
            "tasks": [
                {"name": "query", "status": "run"},
                {"name": "analyst", "status": "skip"},
            ]
        },
    )
    context = AgentRunContext(
        query="re-run sql",
        session_id="s",
        shared=shared,
        dependencies={"planner_phase": planner_result},
        inputs={},
    )

    result = await _query_agent(context)

    assert result.output["attempt_count"] == 2
    assert result.output["last_status"] == "success"
    assert result.output["summary"][0]["status"] == "validation_failed"


def test_derive_tasks_handles_chart_revision():
    planner_ctx = {"tickers": ["NVDA"]}
    sql_ctx = {"attempts": [{"status": "success"}], "row_count": 12}
    analysis_ctx = {"final": "analysis"}
    chart_ctx = {"spec_summary": {"chart_type": "line"}}
    market_ctx = {}

    tasks = _derive_tasks(planner_ctx, sql_ctx, analysis_ctx, chart_ctx, market_ctx, "revise chart for nvda")
    status_map = {task["name"]: task["status"] for task in tasks}

    assert status_map["query"] == "run"
    assert status_map["chart"] == "run"
    assert status_map["analyst"] == "skip"
    assert status_map["market"] == "skip"


def test_derive_tasks_standard_flow():
    planner_ctx = {"tickers": ["NVDA"]}
    sql_ctx = {"attempts": [{"status": "success"}], "row_count": 8}
    analysis_ctx = {"final": "analysis"}
    chart_ctx = {"spec_summary": {"chart_type": "bar"}}
    market_ctx = {}

    tasks = _derive_tasks(planner_ctx, sql_ctx, analysis_ctx, chart_ctx, market_ctx, "market share report")
    status_map = {task["name"]: task["status"] for task in tasks}

    assert status_map["query"] == "run"
    assert status_map["analyst"] == "run"
    assert status_map["chart"] == "run"
    assert status_map["market"] == "run"
