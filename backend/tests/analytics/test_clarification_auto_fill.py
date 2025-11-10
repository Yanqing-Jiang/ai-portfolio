from __future__ import annotations

import time

from analytics.core.events import TimedEventEmitter
from analytics.core.intent_impl.models import ClarifyRequestModel, IntentModel, SlotStatusModel, TimeframeModel
from analytics.core.state import QueryPlanModel
from analytics.flows.planner_executor import (
    PlannerPhaseContext,
    _apply_plan_timeframe_defaults,
    _auto_fill_missing_slots,
    _filter_answered_requests,
)


def _make_context() -> PlannerPhaseContext:
    emitter = TimedEventEmitter(session_id="s-auto", flow="single_agent")
    ctx = PlannerPhaseContext(
        query="How's Nvidia margin growth compare to peers?",
        session_id="s-auto",
        workflow_start=time.time(),
        timed_emitter=emitter,
    )
    ctx.intent = IntentModel(intent_key="margin_growth_vs_peers", confidence=0.7)
    return ctx


def test_filter_answered_requests_skips_resolved_slots() -> None:
    requests = [
        ClarifyRequestModel(
            slot="timeframe",
            question="Select timeframe",
            type="single",
            options=["last 5 years"],
            request_id="req-1",
            reason="Need timeframe",
        ),
        ClarifyRequestModel(
            slot="metric",
            question="Select metric",
            type="single",
            options=["Operating Margin"],
            request_id="req-2",
            reason="Need metric",
        ),
    ]
    filtered = _filter_answered_requests(requests, {"timeframe"})
    assert len(filtered) == 1
    assert filtered[0].slot == "metric"


def test_auto_fill_missing_slots_promotes_assumptions() -> None:
    ctx = _make_context()
    ctx.slot_statuses["timeframe"] = SlotStatusModel(
        status="missing",
        value=None,
        reason="Timeframe required",
        suggestions=["last 5 years"],
        allow_custom=True,
    )

    remaining, answers = _auto_fill_missing_slots(ctx, ["Using timeframe: last_5_years"])

    assert remaining == []
    assert answers and answers[0].slot == "timeframe"
    assert ctx.slot_statuses["timeframe"].status == "assumed"
    assert ctx.slot_statuses["timeframe"].value == "last_5_years"


def test_auto_fill_missing_slots_defaults_from_suggestions() -> None:
    ctx = _make_context()
    ctx.slot_statuses["metric"] = SlotStatusModel(
        status="missing",
        value=None,
        reason="Metric required",
        suggestions=["Operating Margin"],
        allow_custom=False,
    )

    remaining, answers = _auto_fill_missing_slots(ctx, [])

    assert remaining == []
    assert answers and answers[0].slot == "metric"
    assert ctx.slot_statuses["metric"].status == "defaulted"
    assert ctx.slot_statuses["metric"].value == "Operating Margin"


def test_plan_timeframe_defaults_seed_slot_and_answers() -> None:
    ctx = _make_context()
    ctx.provisional_plan = QueryPlanModel(timeframe=TimeframeModel(preset="last_5_years", years_back=5))
    ctx.slot_statuses["timeframe"] = SlotStatusModel(
        status="missing",
        value=None,
        reason="Timeframe required",
        suggestions=["last 5 years", "last 2 years"],
        allow_custom=True,
    )

    payload = _apply_plan_timeframe_defaults(ctx)

    assert payload is not None
    status = ctx.slot_statuses["timeframe"]
    assert status.status == "defaulted"
    assert status.value.get("preset") == "last_5_years"
    assert "timeframe" in ctx.clarification_answers
