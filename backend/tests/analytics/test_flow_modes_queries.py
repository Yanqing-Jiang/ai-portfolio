import asyncio
import sys
from pathlib import Path
from typing import List

import pytest
import fakeredis.aioredis

ROOT = Path(__file__).resolve().parents[3]
BACKEND_ROOT = Path(__file__).resolve().parents[2]
for entry in (ROOT, BACKEND_ROOT):
    entry_str = str(entry)
    if entry_str not in sys.path:
        sys.path.insert(0, entry_str)

from analytics.core import config as analytics_config
from analytics.core import analysis
from analytics.flows import planner_executor
from analytics.core.memory_gate import MemoryGate
from analytics.core.session_state import SessionStateRepository
from analytics.flows import instrumentation
from analytics.flows.workflow import analytics_memory_workflow
from analytics.sql import executor

MARKET_QUERY = "Nvidia market share in the past 5 years?"
MARGIN_QUERY = "How's Nvidia margin growth compare to industry average?"

@pytest.fixture(autouse=True)
def _memory_gate_uses_fakeredis():
    fake = fakeredis.aioredis.FakeRedis()
    instrumentation._memory_gate = MemoryGate(
        repository=SessionStateRepository(redis_client=fake)
    )
    try:
        yield
    finally:
        instrumentation._memory_gate = None


class DummyUnifiedClient:
    def __init__(self) -> None:
        self.messages: List[List[dict]] = []
        self.return_invalid_sql = False

    async def simple_completion(self, messages, reasoning_effort="low", session_id=None, model=None):
        self.messages.append(messages)
        if self.return_invalid_sql:
            self.return_invalid_sql = False
            sql = """```sql\nSELECT ticker FROM comp_financials;\n```"""
            return sql, "stub-response-id"
        last_content = messages[-1].get("content", "").lower()
        if "margin" in last_content:
            sql = """```sql\nSELECT ticker, calendar_year, gross_margin FROM fake_margin;\n```"""
        else:
            sql = """```sql\nSELECT ticker, calendar_year, market_share_percent FROM fake_market_share;\n```"""
        return sql, "stub-response-id"


def _fake_execute_sql(sql: str):
    sql_lower = sql.lower()
    if "market_share" in sql_lower:
        return [{"calendar_year": 2020, "market_share_percent": 12.3, "ticker": "NVDA"}]
    if "gross_margin" in sql_lower or "margin" in sql_lower:
        return [{"calendar_year": 2020, "company_net_margin_change_pp": 1.2, "ticker": "NVDA"}]
    return [{"calendar_year": 2020, "value": 1.0, "ticker": "NVDA"}]


@pytest.fixture(autouse=True)
def _reload_configs(monkeypatch):
    analytics_config.CONFIGS.load()
    monkeypatch.setattr(planner_executor, "CONFIGS", analytics_config.CONFIGS)
    dummy_client = DummyUnifiedClient()
    monkeypatch.setattr(planner_executor, "get_unified_client", lambda: dummy_client)
    monkeypatch.setattr(planner_executor, "compute_required_clarifications", lambda intent, plan, template, configs=None: [])
    monkeypatch.setattr(planner_executor, "detect_missing_slots", lambda intent, plan, configs=None: [])

    async def _fake_execute(sql: str, timeout: float = 15.0):
        return _fake_execute_sql(sql)

    monkeypatch.setattr(executor, "execute_sql", _fake_execute)
    monkeypatch.setattr(planner_executor, "execute_sql", _fake_execute)
    monkeypatch.setattr(analysis, "get_openai_client", lambda: None)
    return dummy_client


async def _collect_events(query: str, flow: str):
    events = []
    async for event in analytics_memory_workflow(query, flow=flow):
        events.append(event)
    return events


@pytest.mark.asyncio
async def test_planner_executor_uses_market_share_template():
    events = await _collect_events(MARKET_QUERY, flow="planner-executor")
    template_event = next(e for e in events if e.get("event") == "template_selected")
    assert template_event["data"]["template_id"] == "market_share_single"
    assert template_event["data"]["has_template"] is True

    sql_event = next(e for e in events if e.get("event") == "sql_generated")
    assert 'comp_financials' in sql_event["data"].get("sql", '').lower()
    assert sql_event["data"].get("llm_used") is False
    assert sql_event["data"].get("fallback_reason") in {None, 'sql_validation_failed'}


@pytest.mark.asyncio
async def test_single_agent_tool_calls_include_template_details():
    events = await _collect_events(MARGIN_QUERY, flow="single-agent")
    template_event = next(e for e in events if e.get("event") == "template_selected")
    assert template_event["data"]["template_id"] == "margin_growth_vs_peers"

    sql_tool_end = next(
        event for event in events
        if event.get("event") == "tool_call"
        and event["data"].get("tool") == "sql_generator"
        and event["data"].get("status") == "end"
    )
    assert "Margin Growth" in sql_tool_end["data"]["details"]["template_used"]


@pytest.mark.asyncio
async def test_multi_agent_emits_agent_turns():
    events = await _collect_events(MARKET_QUERY, flow="multi-agent")
    template_event = next(e for e in events if e.get("event") == "template_selected")
    assert template_event["data"]["template_id"] == "market_share_single"

    agent_roles = {
        (event["data"].get("role"), event["data"].get("status"))
        for event in events
        if event.get("event") == "agent_turn"
    }
    assert ("sql_specialist", "start") in agent_roles
    assert ("sql_specialist", "complete") in agent_roles


@pytest.mark.asyncio
async def test_planner_executor_validation_fallback(_reload_configs):
    client = planner_executor.get_unified_client()
    client.return_invalid_sql = True
    events = await _collect_events(MARKET_QUERY, flow="planner-executor")

    compiled_events = [event for event in events if event.get("event") == "sql_compiled"]
    assert compiled_events[-1]["data"].get("template_fallback") is True

    validation_events = [event for event in events if event.get("event") == "sql_validated"]
    assert validation_events[-1]["data"].get("ok") is True
    assert validation_events[-1]["data"].get("attempt", 1) >= 2

    sql_event = next(event for event in events if event.get("event") == "sql_generated")
    assert "SELECT" in sql_event["data"].get("sql", "")
    assert sql_event["data"].get("fallback_reason") in {"sql_validation_failed", "sql_execution_error"}

