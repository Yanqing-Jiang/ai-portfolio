import asyncio
from pathlib import Path

import pytest

from analytics.flows.planner_executor import PlannerExecutorFlow, PlannerPhaseContext
from analytics.core.events import TimedEventEmitter
from analytics.core.state import IntentModel, QueryPlanModel


@pytest.fixture
def anyio_backend():
    return 'asyncio'


class StubClient:
    def __init__(self) -> None:
        self.calls = 0

    async def simple_completion(self, *args, **kwargs):
        self.calls += 1
        if self.calls == 1:
            return "", None
        return "SELECT 1", None


@pytest.mark.anyio("asyncio")
async def test_sql_retry_policy_blocks_on_low_confidence(monkeypatch):
    flow = PlannerExecutorFlow()
    flow.unified_client = StubClient()

    intent = IntentModel(intent_key='financial_analysis', confidence=0.2, slots_detected={})
    plan = QueryPlanModel()
    plan.limit = 10000
    plan.granularity = 'quarterly'

    ctx = PlannerPhaseContext(
        query='What is the revenue trend for NVDA?',
        session_id='session-test',
        workflow_start=0.0,
        timed_emitter=TimedEventEmitter(session_id='session-test', flow='planner-executor'),
        intent=intent,
        plan=plan,
        candidate_templates=[],
        selected_template_id=None,
    )

    async def fake_classification(self, ctx_local):
        ctx_local.is_financial_query = True
        yield {'event': 'classification_complete', 'data': {'is_financial': True, 'category': 'financial_analytics'}}

    async def fake_intent(self, ctx_local):
        ctx_local.intent = intent
        ctx_local.provisional_plan = plan
        ctx_local.template = None
        ctx_local.candidate_templates = []
        ctx_local.selected_template_id = None
        ctx_local.clarifications = []
        yield {'event': 'intent_detection_complete', 'data': {'intent_key': intent.intent_key, 'confidence': intent.confidence}}

    async def skip_phase(*args, **kwargs):
        if False:
            yield  # pragma: no cover
        return

    async def fake_plan_phase(self, ctx_local):
        ctx_local.plan = plan
        ctx_local.candidate_templates = []
        ctx_local.selected_template_id = None
        yield

    monkeypatch.setattr('analytics.flows.planner_executor._initialize_context', lambda self, query, session_id: ctx)
    monkeypatch.setattr('analytics.flows.planner_executor._classification_phase', fake_classification, raising=False)
    monkeypatch.setattr('analytics.flows.planner_executor._intent_phase', fake_intent, raising=False)
    monkeypatch.setattr('analytics.flows.planner_executor._clarification_phase', skip_phase, raising=False)
    monkeypatch.setattr('analytics.flows.planner_executor._plan_phase', fake_plan_phase, raising=False)
    monkeypatch.setattr('analytics.sql.executor.execute_sql', lambda sql: asyncio.sleep(0, result=[]))

    events = []
    async for event in flow.events(ctx.query, session_id=ctx.session_id):
        events.append(event)
        if event.get('event') == 'workflow_complete':
            break

    assert flow.unified_client.calls == 2
    attempts = ctx.planner_result.sql_attempts
    assert attempts[0]['status'] in {'error', 'empty'}
    assert attempts[-1]['status'] == 'valid'
    assert ctx.planner_result.sql_text == 'SELECT 1'


    intent = IntentModel(intent_key='financial_analysis', confidence=0.2, slots_detected={})
    plan = QueryPlanModel()
    plan.limit = 10000
    plan.granularity = 'quarterly'

    ctx = PlannerPhaseContext(
        query='What is the revenue trend for NVDA?',
        session_id='session-test',
        workflow_start=0.0,
        timed_emitter=TimedEventEmitter(session_id='session-test', flow='planner-executor'),
        intent=intent,
        plan=plan,
        candidate_templates=[],
        selected_template_id=None,
    )

    events = []
    async for event in flow._sql_phase(
        ctx,
        query=ctx.query,
        intent=intent,
        plan=plan,
        session_id=ctx.session_id,
        candidate_templates=[],
        timed_emitter=ctx.timed_emitter,
    ):
        events.append(event)

    policy_events = [evt for evt in events if evt.get('event') == 'policy_decision']
    assert policy_events, 'Expected policy decision event when retries are blocked'
    assert policy_events[-1]['data']['action'] == 'skip_retry'
    assert flow.unified_client.calls == 1
    assert ctx.sql == ''
    assert ctx.sql_attempts[-1]['status'] == 'policy_blocked'
