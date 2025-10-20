import pytest

from analytics.core.clarify import merge_answers
from analytics.core.intent_impl.models import IntentModel, ClarifyAnswerModel
from analytics.core.state import QueryPlanModel


@pytest.mark.asyncio
async def test_merge_answers_timeframe_forces_quarterly_granularity():
    intent = IntentModel(intent_key='market_share_single', confidence=0.82, slots_detected={})
    plan = QueryPlanModel()
    answer = ClarifyAnswerModel(
        value='last 4 quarters',
        request_id='req-1',
        slot='timeframe',
        session_id='session-1',
        ts=None,
    )

    updated_intent, updated_plan, assumptions = await merge_answers(intent, plan, [answer], configs={})

    assert updated_plan.granularity == 'quarterly'
    assert updated_intent.slots_detected.get('granularity') == 'quarterly'
    assert any('quarterly granularity' in note for note in assumptions)


@pytest.mark.asyncio
async def test_merge_answers_last_two_years_forces_quarterly_granularity():
    intent = IntentModel(intent_key='market_share_single', confidence=0.82, slots_detected={})
    plan = QueryPlanModel()
    answer = ClarifyAnswerModel(
        value='last 2 years',
        request_id='req-2',
        slot='timeframe',
        session_id='session-2',
        ts=None,
    )

    updated_intent, updated_plan, assumptions = await merge_answers(intent, plan, [answer], configs={})

    assert updated_plan.granularity == 'quarterly'
    assert updated_intent.slots_detected.get('granularity') == 'quarterly'
    assert any('quarterly granularity' in note for note in assumptions)


@pytest.mark.asyncio
async def test_merge_answers_last_five_years_keeps_annual_granularity():
    intent = IntentModel(intent_key='market_share_single', confidence=0.82, slots_detected={})
    plan = QueryPlanModel()
    answer = ClarifyAnswerModel(
        value='last 5 years',
        request_id='req-3',
        slot='timeframe',
        session_id='session-3',
        ts=None,
    )

    updated_intent, updated_plan, assumptions = await merge_answers(intent, plan, [answer], configs={})

    assert updated_plan.granularity == 'annual'
    assert updated_intent.slots_detected.get('granularity') != 'quarterly'
    assert all('quarterly granularity' not in note for note in assumptions)
