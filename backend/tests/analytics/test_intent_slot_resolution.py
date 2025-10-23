from backend.analytics.core.config import CONFIGS
from backend.analytics.core.intent_impl import detection
from backend.analytics.core.intent_impl.models import (
    IntentSelectionModel,
    LLMIntentResolutionModel,
    LLMSlotStatusModel,
    LLMFollowUpModel,
    TimeframeSlotValue,
)
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


def test_structured_resolver_honors_explicit_year_range(monkeypatch):
    get_slot_catalog(refresh=True)

    class _FakeClient:
        async def create_structured(self, *, response_model, messages, reasoning_effort, session_id=None, model=None):
            payload = LLMIntentResolutionModel(
                intent=IntentSelectionModel(key="revenue_comparison", confidence=0.92, mode="multi_agent"),
                slots={
                    "company": LLMSlotStatusModel(
                        status="filled",
                        value="AMD",
                        suggestions=["AMD", "NVDA"],
                        allow_custom=True,
                    ),
                    "metric": LLMSlotStatusModel(
                        status="filled",
                        value="Revenue",
                        suggestions=["Revenue"],
                        allow_custom=True,
                    ),
                    "timeframe": LLMSlotStatusModel(
                        status="filled",
                        value=TimeframeSlotValue(
                            granularity="annual",
                            years_back=4,
                            start_year=2021,
                            end_year=2024,
                            source="query",
                        ),
                        suggestions=["last 5 years"],
                        allow_custom=True,
                    ),
                },
                followups=[],
            )
            return payload, "fake-response-id"

    monkeypatch.setattr(detection, "get_unified_client", lambda: _FakeClient())

    result = detection.resolve_intent_slots(
        "AMD vs NVIDIA revenue comparison 2021-2024",
        _config_payload(),
    )

    assert result.intent.key == "revenue_comparison"
    assert not result.followups
    timeframe_status = result.slots.get("timeframe")
    assert timeframe_status is not None
    assert timeframe_status.status == "filled"
    assert timeframe_status.value["start_year"] == 2021
    assert timeframe_status.value["end_year"] == 2024
    assert timeframe_status.value["granularity"] == "annual"
    metric_status = result.slots.get("metric")
    assert metric_status is not None
    assert metric_status.status == "filled"
    assert metric_status.value == "Revenue"


def test_structured_resolver_drops_metric_followup_when_value_present(monkeypatch):
    get_slot_catalog(refresh=True)

    class _FakeClient:
        async def create_structured(self, *, response_model, messages, reasoning_effort, session_id=None, model=None):
            payload = LLMIntentResolutionModel(
                intent=IntentSelectionModel(key="revenue_comparison", confidence=0.9, mode="multi_agent"),
                slots={
                    "company": LLMSlotStatusModel(
                        status="filled",
                        value="AMD",
                        suggestions=["AMD", "NVDA"],
                        allow_custom=True,
                    ),
                    "metric": LLMSlotStatusModel(
                        status="missing",
                        value="Revenue",
                        suggestions=["Revenue"],
                        allow_custom=True,
                    ),
                    "metrics": LLMSlotStatusModel(
                        status="missing",
                        value=["Revenue", "Net Income"],
                        suggestions=["Revenue", "Net Income"],
                        allow_custom=True,
                    ),
                    "timeframe": LLMSlotStatusModel(
                        status="missing",
                        value=None,
                        suggestions=["last 5 years"],
                        allow_custom=True,
                    ),
                },
                followups=[
                    LLMFollowUpModel(
                        slot="metric",
                        prompt="Which metric should we compare?",
                        suggestions=["Revenue"],
                        allow_custom=True,
                        reason="Clarify the metric for comparison",
                    ),
                    LLMFollowUpModel(
                        slot="metrics",
                        prompt="Select metrics to compare",
                        suggestions=["Revenue", "Net Income"],
                        allow_custom=True,
                        reason="Clarify metrics",
                    )
                ],
            )
            return payload, "fake-response-id"

    monkeypatch.setattr(detection, "get_unified_client", lambda: _FakeClient())

    result = detection.resolve_intent_slots(
        "AMD vs NVIDIA revenue comparison",
        _config_payload(),
    )

    metric_status = result.slots.get("metric")
    assert metric_status is not None
    assert metric_status.status == "defaulted"
    assert metric_status.value == "Revenue"
    followup_slots = {followup.slot for followup in result.followups}
    assert "metric" not in followup_slots
    assert "metrics" not in followup_slots


def test_fallback_keeps_timeframe_when_years_present(monkeypatch):
    get_slot_catalog(refresh=True)

    def _raise():
        raise ValueError("mock client unavailable")

    monkeypatch.setattr(detection, "get_unified_client", _raise)

    result = detection.resolve_intent_slots(
        "AMD vs NVIDIA revenue comparison 2021-2024",
        _config_payload(),
    )

    timeframe_status = result.slots.get("timeframe")
    assert timeframe_status is not None
    assert timeframe_status.status in {"defaulted", "assumed"}
    assert timeframe_status.value["start_year"] == 2021
    assert timeframe_status.value["end_year"] == 2024
    assert all(f.slot != "timeframe" for f in result.followups)


def test_fallback_defaults_comparison_for_multi_company_query(monkeypatch):
    get_slot_catalog(refresh=True)

    def _raise():
        raise ValueError("mock client unavailable")

    monkeypatch.setattr(detection, "get_unified_client", _raise)

    result = detection.resolve_intent_slots(
        "Compare AMD and NVDA revenue 2021-2024",
        _config_payload(),
    )

    comparison_status = result.slots.get("comparison")
    assert comparison_status is not None
    assert comparison_status.status in {"filled", "defaulted"}
    assert comparison_status.value == "all"
    assert all(f.slot != "comparison" for f in result.followups)


def test_fallback_handles_missing_client_and_detects_revenue_comparison(monkeypatch):
    get_slot_catalog(refresh=True)
    monkeypatch.setattr(detection, "get_unified_client", lambda: None)

    result = detection.resolve_intent_slots(
        "AMD vs NVIDIA revenue comparison 2021-2024",
        _config_payload(),
    )

    assert result.intent.key == "revenue_comparison"
    metric_status = result.slots.get("metric")
    assert metric_status is not None
    assert metric_status.value == "Revenue"
    comparison_status = result.slots.get("comparison")
    assert comparison_status is not None
    assert comparison_status.value == "all"


def test_fallback_detects_operating_leverage_intent(monkeypatch):
    get_slot_catalog(refresh=True)

    def _raise():
        raise ValueError("mock client unavailable")

    monkeypatch.setattr(detection, "get_unified_client", _raise)

    result = detection.resolve_intent_slots(
        "What's AMD's operating leverage YoY vs the industry over the last five years?",
        _config_payload(),
    )

    assert result.intent.key == "operating_leverage_yoy_vs_peers"
    assert result.slots["comparison"].value in {"vs_avg", "all"}
    assert result.slots["company"].status == "filled"


def test_fallback_detects_eps_rank_intent(monkeypatch):
    get_slot_catalog(refresh=True)
    monkeypatch.setattr(detection, "get_unified_client", lambda: None)

    result = detection.resolve_intent_slots(
        "Who leads EPS YoY growth this quarter?",
        _config_payload(),
    )

    assert result.intent.key == "eps_yoy_rank_latest"
    assert result.slots.get("metric").value == "EPS Basic"
    assert result.slots.get("comparison").value == "all"


def test_fallback_detects_capex_intensity_rank(monkeypatch):
    get_slot_catalog(refresh=True)
    monkeypatch.setattr(detection, "get_unified_client", lambda: None)

    result = detection.resolve_intent_slots(
        "Rank CapEx intensity latest quarter. Who is most capital intensive?",
        _config_payload(),
    )

    assert result.intent.key == "capex_intensity_latest_rank"
    metric_status = result.slots.get("metric")
    assert metric_status is not None
    assert metric_status.value == "Capital Expenditures"
    assert result.slots.get("comparison").value == "all"
