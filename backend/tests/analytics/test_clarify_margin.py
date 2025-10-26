import asyncio

from analytics.core.clarify import detect_missing_slots, merge_answers
from analytics.core.context import get_configs
from analytics.core.intent_impl.models import IntentModel, ClarifyAnswerModel
from analytics.core.state import QueryPlanModel
from analytics.sql.sql_planner import plan_sql_rule_based, choose_template


def _build_plan(intent: IntentModel) -> QueryPlanModel:
    plan_dict = plan_sql_rule_based(intent, get_configs().__dict__)
    return QueryPlanModel(**plan_dict)


def test_margin_clarification_prompts_when_type_ambiguous():
    intent = IntentModel(
        intent_key='margins_vs_peers',
        confidence=0.82,
        slots_detected={'company': 'NVDA', 'original_query': 'Show Nvidia margins vs peers'},
    )
    plan = _build_plan(intent)
    template = choose_template(intent, plan)
    configs = get_configs().__dict__

    requests = detect_missing_slots(intent, plan, template, configs)
    margin_requests = [req for req in requests if req.slot == 'metric']

    assert margin_requests, "Expected a metric clarification for unspecified margin type"
    request = margin_requests[0]
    assert request.options == ['Gross Margin', 'Operating Margin', 'Net Margin']
    assert request.default == 'Operating Margin'


def test_margin_clarification_infers_from_query_text():
    intent = IntentModel(
        intent_key='margins_vs_peers',
        confidence=0.88,
        slots_detected={'company': 'NVDA', 'original_query': 'Compare Nvidia gross margin vs peers'},
    )
    plan = _build_plan(intent)
    template = choose_template(intent, plan)
    configs = get_configs().__dict__

    requests = detect_missing_slots(intent, plan, template, configs)

    assert all(req.slot != 'metric' for req in requests)
    assert plan.metrics == ['Gross Margin']
    assert intent.slots_detected.get('metric') == 'Gross Margin'


def test_merge_answers_applies_margin_selection():
    intent = IntentModel(
        intent_key='margin_growth_vs_peers',
        confidence=0.9,
        slots_detected={'company': 'NVDA'},
    )
    plan = _build_plan(intent)
    configs = get_configs().__dict__

    answer = ClarifyAnswerModel(
        session_id='session-1',
        request_id='req-1',
        slot='metric',
        value='Net Margin',
        answered_at='2025-10-26T20:00:00Z',
    )

    intent_updated, plan_updated, assumptions = asyncio.run(merge_answers(intent, plan, [answer], configs))

    assert intent_updated.slots_detected.get('metric') == 'Net Margin'
    assert plan_updated.metrics == ['Net Margin']
    assert 'net margin' in " ".join(assumptions).lower()
