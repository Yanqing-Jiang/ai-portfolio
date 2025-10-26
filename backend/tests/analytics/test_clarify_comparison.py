import pytest

from analytics.core.clarify import compute_required_clarifications
from analytics.core.config import CONFIGS
from analytics.core.intent_impl.detection import detect_intent_fast_async
from analytics.sql.sql_planner import build_query_plan


def _configs_dict() -> dict:
    return {
        "queries": CONFIGS.queries,
        "query_requirements": CONFIGS.query_requirements,
        "metrics": CONFIGS.metrics,
        "charts": CONFIGS.charts,
        "companies": CONFIGS.companies,
        "database": CONFIGS.database,
        "semantic": CONFIGS.semantic,
    }


@pytest.mark.asyncio
async def test_margin_average_prefills_vs_avg_and_skips_clarifier() -> None:
    configs = _configs_dict()
    query = "How's Nvidia margin growth compare to industry average?"

    intent = await detect_intent_fast_async(query, configs)
    plan = build_query_plan(intent, configs)
    clarifications = compute_required_clarifications(intent, plan, None, configs)

    assert intent.slots_detected.get("comparison") == "vs_avg"
    assert plan.comparison == "vs_avg"
    assert all(request.slot != "comparison" for request in clarifications)


@pytest.mark.asyncio
async def test_revenue_growth_average_prefills_vs_avg_and_skips_clarifier() -> None:
    configs = _configs_dict()
    query = "How fast is NVDA growing vs industry average?"

    intent = await detect_intent_fast_async(query, configs)
    plan = build_query_plan(intent, configs)
    clarifications = compute_required_clarifications(intent, plan, None, configs)

    assert intent.intent_key == "revenue_growth_vs_avg"
    assert intent.slots_detected.get("comparison") == "vs_avg"
    assert plan.comparison == "vs_avg"
    assert all(request.slot != "comparison" for request in clarifications)


@pytest.mark.asyncio
async def test_rnd_expense_average_prefills_vs_avg_and_skips_clarifier() -> None:
    configs = _configs_dict()
    query = "How does NVDA R&D expense compare to the industry average?"

    intent = await detect_intent_fast_async(query, configs)
    plan = build_query_plan(intent, configs)
    clarifications = compute_required_clarifications(intent, plan, None, configs)

    assert intent.intent_key == "rnd_expense_vs_peers"
    assert intent.slots_detected.get("comparison") == "vs_avg"
    assert plan.comparison == "vs_avg"
    assert all(request.slot != "comparison" for request in clarifications)


@pytest.mark.asyncio
async def test_margin_peers_prefills_vs_peers_and_skips_clarifier() -> None:
    configs = _configs_dict()
    query = "Compare Nvidia margin growth versus peers this year."

    intent = await detect_intent_fast_async(query, configs)
    plan = build_query_plan(intent, configs)
    clarifications = compute_required_clarifications(intent, plan, None, configs)

    assert intent.slots_detected.get("comparison") == "vs_peers"
    assert plan.comparison == "vs_peers"
    assert all(request.slot != "comparison" for request in clarifications)
