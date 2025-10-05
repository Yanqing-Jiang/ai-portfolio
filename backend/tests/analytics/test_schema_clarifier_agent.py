import pytest

from analytics.agents import schema_clarifier
from analytics.core.intent import IntentModel
from analytics.agents.schema_clarifier import ClarifierAgentResponse, decide_schema_clarification
from analytics.core.state import QueryPlanModel


@pytest.fixture(autouse=True)
def _reset_decision_cache():
    schema_clarifier._DECISION_CACHE.clear()
    yield
    schema_clarifier._DECISION_CACHE.clear()


def _intent_with_company() -> IntentModel:
    return IntentModel(intent_key="market_share_single", confidence=0.9, slots_detected={"company": "NVDA"})


def _intent_without_company() -> IntentModel:
    return IntentModel(intent_key="market_share_single", confidence=0.9, slots_detected={})


def test_decide_skip_when_requirements_met():
    intent = _intent_with_company()
    plan = QueryPlanModel()
    decision = decide_schema_clarification(intent, plan, session_id="s1", template_id="market_share_single")
    assert decision.action == "skip"
    assert decision.missing_slots == []


def test_decide_clarify_when_company_missing(monkeypatch):
    intent = _intent_without_company()
    plan = QueryPlanModel()

    class DummyClient:
        def create_structured(self, response_model, messages, model, reasoning_effort):
            return (
                ClarifierAgentResponse(
                    action="clarify",
                    slot="company",
                    question="Which company should we analyze?",
                    reason="Need a specific ticker.",
                    options=["NVDA", "AMD"],
                ),
                None,
            )

    monkeypatch.setattr(schema_clarifier, "get_unified_client", lambda: DummyClient())

    decision = decide_schema_clarification(intent, plan, session_id="s2", template_id="market_share_single")
    assert decision.action == "clarify"
    assert decision.slot == "company"
    assert decision.options == ["NVDA", "AMD"]


def test_decide_fallback_when_client_unavailable(monkeypatch):
    intent = _intent_without_company()
    plan = QueryPlanModel()

    def _raise():
        raise RuntimeError("no client")

    monkeypatch.setattr(schema_clarifier, "get_unified_client", _raise)

    decision = decide_schema_clarification(intent, plan, session_id="s3", template_id="market_share_single")
    assert decision.action in {"fallback", "skip"}
    assert decision.slot is None or decision.slot == "company"
