import asyncio
from datetime import datetime

import pytest

from analytics.core import config as analytics_config
from analytics.core.clarify import _detect_timeframe_slot, merge_answers
from analytics.core.intent_impl.detection import heuristic_intent
from analytics.core.types import ClarifyAnswerModel
from analytics.core.state import IntentModel, QueryPlanModel
from analytics.sql.sql_planner import choose_template


@pytest.fixture(scope="module", autouse=True)
def _load_configs():
    analytics_config.CONFIGS.load()


def _get_configs_dict():
    return analytics_config.CONFIGS.__dict__


def test_top_spender_requests_year_selection():
    intent = IntentModel(intent_key='rnd_top_spender', confidence=0.7, slots_detected={'original_query': 'Which company has the highest R&D spending?'})
    plan = QueryPlanModel()
    request = _detect_timeframe_slot(intent, plan, _get_configs_dict())
    assert request is not None
    assert request.slot == 'timeframe'
    assert 'year' in request.question.lower()
    current_year = str(datetime.utcnow().year)
    assert current_year in request.options


@pytest.mark.asyncio
async def test_merge_answers_sets_specific_year():
    intent = IntentModel(intent_key='rnd_top_spender', confidence=0.7, slots_detected={})
    plan = QueryPlanModel()
    answer = ClarifyAnswerModel(
        session_id='session-1',
        request_id='req-1',
        slot='timeframe',
        value='2024',
        ts=datetime.utcnow().isoformat()
    )

    _, updated_plan, assumptions = await merge_answers(intent, plan, [answer], _get_configs_dict())

    assert updated_plan.timeframe.start_year == 2024
    assert updated_plan.timeframe.end_year == 2024
    assert updated_plan.timeframe.years_back == 1
    assert any('2024' in assumption for assumption in assumptions)



def test_heuristic_routes_to_top_spender_intent():
    configs = _get_configs_dict()
    intent = heuristic_intent("Which company has the highest R&D spending?", configs)
    assert intent.intent_key == 'rnd_top_spender'
    assert all(c.slot != 'company' for c in intent.clarifications_suggested)


def test_choose_template_single_year_variant():
    configs = _get_configs_dict()
    intent = IntentModel(intent_key='rnd_top_spender', confidence=0.8, slots_detected={})
    plan = QueryPlanModel()
    plan.timeframe.start_year = 2024
    plan.timeframe.end_year = 2024
    plan.timeframe.years_back = 1
    template = choose_template(intent, plan, configs)
    assert template is not None
    assert "calendar_year = {start_year}" in template['sql_template']
    assert template.get('description') == template.get('single_year_description')
