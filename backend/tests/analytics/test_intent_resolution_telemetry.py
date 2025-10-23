import time

import pytest

from analytics.flows import planner_executor
from analytics.flows.schedulers import FlowMode
from analytics.core.events import TimedEventEmitter
from analytics.core.intent import IntentModel
from analytics.core.intent_impl.models import (
    IntentResolutionModel,
    IntentSelectionModel,
    SlotStatusModel,
    FollowUpModel,
)
from analytics.core.state import QueryPlanModel


@pytest.mark.asyncio
async def test_intent_resolution_telemetry(monkeypatch):
    captured = []

    async def fake_resolver(*args, **kwargs):
        return IntentResolutionModel(
            intent=IntentSelectionModel(key="market_share_single", confidence=0.8, mode="single_agent"),
            slots={
                "company": SlotStatusModel(status="filled", value="NVDA"),
                "timeframe": SlotStatusModel(
                    status="missing",
                    value=None,
                    reason="Timeframe required",
                    suggestions=["last_5_years"],
                    allow_custom=True,
                ),
            },
            followups=[
                FollowUpModel(
                    slot="timeframe",
                    prompt="Choose a timeframe to analyze",
                    suggestions=["last_5_years", "last_8_quarters"],
                    allow_custom=True,
                    reason="Timeframe missing",
                )
            ],
            notes="mock resolution",
        )

    def fake_detect_intent(query, configs, session_id=None):
        return IntentModel(intent_key="market_share_single", confidence=0.8, slots_detected={})

    def record_intent_resolution(**kwargs):
        captured.append(kwargs)

    monkeypatch.setattr(planner_executor, "resolve_intent_slots_async", fake_resolver)
    monkeypatch.setattr(planner_executor, "detect_intent", fake_detect_intent)
    monkeypatch.setattr(planner_executor, "log_intent_resolution", record_intent_resolution)
    monkeypatch.setattr(planner_executor, "build_query_plan", lambda intent, configs: QueryPlanModel())
    monkeypatch.setattr(planner_executor, "choose_template", lambda intent, plan, configs: {"id": "template"})

    flow = planner_executor.PlannerExecutorFlow()
    ctx = planner_executor.PlannerPhaseContext(
        query="AMD market share",
        session_id="sess-test",
        workflow_start=time.time(),
        timed_emitter=TimedEventEmitter(session_id="sess-test", flow=FlowMode.DIRECT.value),
        flow_mode=FlowMode.DIRECT,
        configs=planner_executor.CONFIGS.__dict__,
    )

    async for event in planner_executor._intent_phase(flow._pipeline, ctx):
        if event.get("event") == "intent_detection_complete":
            break

    assert captured, "intent_resolution telemetry was not emitted"
    payload = captured[0]
    assert payload["intent_key"] == "market_share_single"
    assert payload["slot_statuses"]["company"]["status"] == "filled"
    assert payload["slot_statuses"]["timeframe"]["status"] == "missing"
    assert payload["slot_followups"][0]["slot"] == "timeframe"
    assert payload["flow"] == FlowMode.DIRECT.value
    assert payload["clarification_sources"] == ["structured_resolver"]
