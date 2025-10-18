from backend.analytics.core.config import CONFIGS
from backend.analytics.core.intent_impl import detection
from backend.analytics.core.slot_catalog import get_slot_catalog


def _config_payload():
    return {
        "queries": CONFIGS.queries,
        "query_requirements": CONFIGS.query_requirements,
        "companies": CONFIGS.companies,
        "metrics": CONFIGS.metrics,
    }


def test_resolve_intent_slots_fallback_prompts_for_company(monkeypatch):
    get_slot_catalog(refresh=True)

    def _raise():
        raise ValueError("mock client unavailable")

    monkeypatch.setattr(detection, "get_unified_client", _raise)

    result = detection.resolve_intent_slots(
        "market share analysis",
        _config_payload(),
    )

    assert result.intent.key == "market_share_single"
    assert result.slots["company"].status == "missing"
    assert any(f.slot == "company" for f in result.followups)
    followup_slots = {followup.slot for followup in result.followups}
    assert "timeframe" in followup_slots
    assert "metric" not in followup_slots
    timeframe_status = result.slots.get("timeframe")
    assert timeframe_status is not None
    assert timeframe_status.status == "missing"
    metric_status = result.slots.get("metric")
    assert metric_status is not None
    assert metric_status.status == "defaulted"
    assert metric_status.value == "Revenue"


def test_resolve_intent_slots_fallback_detects_company(monkeypatch):
    get_slot_catalog(refresh=True)

    def _raise():
        raise ValueError("mock client unavailable")

    monkeypatch.setattr(detection, "get_unified_client", _raise)

    result = detection.resolve_intent_slots(
        "AMD market share analysis",
        _config_payload(),
    )

    assert result.intent.key == "market_share_single"
    assert result.slots["company"].status == "filled"
    assert result.slots["company"].value == "AMD"
    assert all(f.slot != "company" for f in result.followups)
    timeframe_status = result.slots.get("timeframe")
    assert timeframe_status is not None
    assert timeframe_status.status == "missing"
    followup_slots = {followup.slot for followup in result.followups}
    assert "timeframe" in followup_slots
    assert "metric" not in followup_slots
    metric_status = result.slots.get("metric")
    assert metric_status is not None
    assert metric_status.status == "defaulted"
    assert metric_status.value == "Revenue"


def test_resolve_intent_slots_fallback_rnd_metric(monkeypatch):
    get_slot_catalog(refresh=True)

    def _raise():
        raise ValueError("mock client unavailable")

    monkeypatch.setattr(detection, "get_unified_client", _raise)

    result = detection.resolve_intent_slots(
        "How is R&D expense compare to industry average?",
        _config_payload(),
    )

    assert result.intent.key == "rnd_expense_vs_peers"
    metric_status = result.slots.get("metric")
    assert metric_status is not None
    assert metric_status.status == "defaulted"
    assert metric_status.value == "R&D Expense"
