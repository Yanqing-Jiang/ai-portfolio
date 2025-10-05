import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parents[2]))
import asyncio
from types import SimpleNamespace

import pytest

from analytics.flows import planner_executor


class DummyUnifiedClient:
    async def simple_completion(self, *args, **kwargs):
        return (
            '`sql\\nSELECT 1 AS value\\nFROM financials\\nWHERE calendar_year = 2024\\nLIMIT 10;\\n`',
            'resp-123',
        )



async def _noop_async_generator(*args, **kwargs):
    if False:
        yield None


def _fake_chart_plan(*args, **kwargs):
    return SimpleNamespace(chart_type="line", series=[1, 2])


def _fake_chart_spec(*args, **kwargs):
    return {"meta": {"chartDesign": {"chart_type": "line"}}}


def _fake_execute_sql(sql: str):
    assert "SELECT" in sql
    return [{"value": 1}]


def _fake_collect_bundle(**kwargs):
    return {}


class FakeIntent(SimpleNamespace):
    confidence = 0.9
    intent_key = "test_intent"
    slots_detected = {"company": "NVDA"}


class FakePlan(SimpleNamespace):
    granularity = 'annual'
    comparison = 'vs_avg'
    metrics = ['revenue']
    group_by = ['calendar_year']
    timeframe = SimpleNamespace(years_back=3)
    limit = 10



async def fake_classification(self, ctx):
    ctx.is_financial_query = True
    yield {"event": "classification_complete", "data": {}}


async def fake_intent_phase(self, ctx):
    ctx.intent = FakeIntent()
    yield {"event": "intent_detected", "data": {"intent_key": "test_intent"}}


async def fake_clarification_phase(self, ctx):
    yield {"event": "clarification_complete", "data": {}}


async def fake_plan_phase(self, ctx):
    ctx.plan = FakePlan()
    ctx.provisional_plan = ctx.plan
    ctx.template = {"id": "template_123"}
    ctx.candidate_templates = [{"id": "template_123"}]
    ctx.selected_template_id = "template_123"
    yield {"event": "plan_ready", "data": {}}


def test_sql_compilation_emits_template(monkeypatch):
    flow = planner_executor.PlannerExecutorFlow()
    flow.unified_client = DummyUnifiedClient()

    monkeypatch.setattr(planner_executor, '_classification_phase', fake_classification)
    monkeypatch.setattr(planner_executor, '_intent_phase', fake_intent_phase)
    monkeypatch.setattr(planner_executor, '_clarification_phase', fake_clarification_phase)
    monkeypatch.setattr(planner_executor, '_plan_phase', fake_plan_phase)
    monkeypatch.setattr(planner_executor, 'run_tool_parallelism', lambda ctx: _noop_async_generator())
    monkeypatch.setattr(planner_executor, 'plan_chart_rule_based', _fake_chart_plan)
    monkeypatch.setattr(planner_executor, 'build_chart_spec', _fake_chart_spec)
    monkeypatch.setattr(planner_executor, 'execute_sql', _fake_execute_sql)
    monkeypatch.setattr(planner_executor, 'collect_tool_bundle', _fake_collect_bundle)
    monkeypatch.setattr(planner_executor, 'stream_insights_llm', _noop_async_generator)
    monkeypatch.setattr(planner_executor, '_validate_sql', lambda sql: (True, [], 0))

    async def _run_flow():
        events = []
        async for event in flow.events('NVDA revenue trend', session_id='session-test'):
            events.append(event)
            if event.get('event') == 'workflow_complete':
                break
        return events

    events = asyncio.run(_run_flow())

    sql_events = [evt for evt in events if evt.get('event') == 'sql_compiled']
    assert sql_events, 'Expected sql_compiled event'
    sql_data = sql_events[0]['data']
    assert sql_data['template_used'] == 'template_123'
    assert sql_data['sql_length'] > 0

    generated = [evt for evt in events if evt.get('event') == 'sql_generated']
    assert generated, 'Expected sql_generated event'

