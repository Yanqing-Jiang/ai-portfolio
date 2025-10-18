import pytest

from analytics.core.intent import IntentModel, TimeframeModel
from analytics.core.state import QueryPlanModel
from analytics.sql.template_requirements import get_required_slots, requirements_satisfied
from analytics.core.intent_impl.models import SlotStatusModel


def test_market_share_single_requires_company():
    intent = IntentModel(intent_key="market_share_single", confidence=0.9, slots_detected={"company": "NVDA"})
    plan = QueryPlanModel()
    satisfied, missing = requirements_satisfied(intent, plan)
    assert satisfied
    assert missing == []


def test_market_share_single_defaults_trigger_clarification():
    # When only the broad default ticker list is present we should still ask for a specific company.
    intent = IntentModel(
        intent_key="market_share_single",
        confidence=0.6,
        slots_detected={
            "tickers": ["NVDA", "AMD", "INTC", "MU", "QCOM", "AVGO", "TXN"],
            "granularity": "annual",
        },
    )
    plan = QueryPlanModel()
    satisfied, missing = requirements_satisfied(intent, plan)
    assert not satisfied
    assert missing == ["company"]


def test_rnd_top_spender_requires_start_year():
    intent = IntentModel(intent_key="rnd_top_spender", confidence=0.9, slots_detected={})
    plan = QueryPlanModel(timeframe=TimeframeModel(years_back=5))
    satisfied, missing = requirements_satisfied(intent, plan)
    assert not satisfied
    assert "timeframe.start_year" in missing

    plan = QueryPlanModel(timeframe=TimeframeModel(start_year=2023))
    satisfied, missing = requirements_satisfied(intent, plan)
    assert satisfied


def test_get_required_slots_loaded_from_yaml():
    slots = get_required_slots("market_share_single")
    assert slots == ["company"]
    assert get_required_slots("unknown_intent") == []


def test_slot_status_missing_overrides_detected_company():
    intent = IntentModel(
        intent_key="market_share_single",
        confidence=0.8,
        slots_detected={"company": "AMD"},
    )
    plan = QueryPlanModel()
    slot_statuses = {"company": SlotStatusModel(status="missing", value=None)}

    satisfied, missing = requirements_satisfied(intent, plan, slot_statuses=slot_statuses)

    assert not satisfied
    assert missing == ["company"]


def test_slot_status_defaulted_counts_as_satisfied():
    intent = IntentModel(
        intent_key="market_share_single",
        confidence=0.8,
        slots_detected={},
    )
    plan = QueryPlanModel()
    slot_statuses = {
        "company": SlotStatusModel(status="defaulted", value=None, reason="using prior selection"),
    }

    satisfied, missing = requirements_satisfied(intent, plan, slot_statuses=slot_statuses)

    assert satisfied
    assert missing == []
