import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[2]))

import pytest

from analytics.flows import planner_executor
from analytics.flows.planner_executor import (
    PlannerPipeline,
    PlannerPhaseContext,
    IntentModel,
    QueryPlanModel,
    IntentResolutionModel,
    SlotStatusModel,
    _build_revision_snapshot_payload,
    _derive_revision_topics,
)
from analytics.core.events import TimedEventEmitter
from analytics.core.session_state import SessionStateSnapshot, get_session_state_repository, close_session_state_repository
from analytics.artifacts import AnalysisArtifact, PlanArtifact, IntentArtifact as IntentArtifactModel


@pytest.mark.asyncio
async def test_emit_analysis_revision_updates_snapshot():
    repo = get_session_state_repository()
    session_id = "analysis-revision-test"
    snapshot = SessionStateSnapshot(session_id=session_id)
    snapshot.record_outputs(analysis="Original analysis")
    await repo.save(snapshot)

    flow = planner_executor.PlannerExecutorFlow()
    events = []
    async for event in flow.emit_analysis_revision(
        session_id=session_id,
        analysis="Updated analysis narrative",
        reason="user_revision",
    ):
        events.append(event)

    analysis_events = [evt for evt in events if evt.get("event") == "analysis_revision"]
    assert analysis_events, "Expected analysis_revision event to be emitted"
    final_event = analysis_events[-1]
    assert final_event.get("data", {}).get("analysis") == "Updated analysis narrative"

    updated_snapshot = await repo.load(session_id)
    assert updated_snapshot is not None
    assert updated_snapshot.last_analysis == "Updated analysis narrative"

    await repo.delete(session_id)
    await close_session_state_repository()


@pytest.mark.asyncio
async def test_build_revision_snapshot_payload_handles_legacy_strings():
    ctx = PlannerPhaseContext(
        query="Summarize AMD capital expenditure trends",
        session_id="legacy-snapshot-test",
        workflow_start=0.0,
        timed_emitter=TimedEventEmitter(session_id="legacy-snapshot-test", flow="planner-executor"),
    )

    ctx.artifacts.intent = IntentArtifactModel(
        query=ctx.query,
        intent_key="capex_trends",
        confidence=0.76,
        slots="@{tickers=@(AMD,NVDA); metric=Capital Expenditures; comparison=company; granularity=annual}",
        raw="@{intent_key=capex_trends; confidence=0.76; slots_detected=@{tickers=@(AMD,NVDA); metric=Capital Expenditures; comparison=company; granularity=annual}; assumptions=@('Using timeframe: last 4 years')}",
    )
    ctx.artifacts.plan = PlanArtifact(
        query=ctx.query,
        plan="@{metrics=@(Capital Expenditures,Revenue); derived_metrics=@(capex_intensity); timeframe=@{years_back=4; granularity=annual}; granularity=annual; comparison=company; statistic=; group_by=@(); filters=@{region='North America'}; limit=25}",
        criteria="@{plan=@{metrics=@(Capital Expenditures,Revenue); derived_metrics=@(capex_intensity); timeframe=@{years_back=4; granularity=annual}; granularity=annual; comparison=company; group_by=@()}; intent_key=capex_trends}",
    )
    ctx.artifacts.analysis = AnalysisArtifact(
        query=ctx.query,
        analysis_text="Baseline analysis narrative",
    )

    payload = _build_revision_snapshot_payload(ctx)

    assert payload is not None, "Expected revision snapshot payload to be generated"
    assert ctx.intent is not None, "Intent model should be reconstructed from legacy strings"
    assert ctx.intent.intent_key == "capex_trends"
    assert ctx.plan is not None, "Plan model should be reconstructed from legacy strings"
    assert ctx.plan.granularity == "annual"
    assert ctx.plan.comparison == "company"
    assert ctx.plan.metrics == ["Capital Expenditures", "Revenue"]
    assert payload.get("intent_signature"), "Intent signature should be included in the revision snapshot"


@pytest.mark.asyncio
async def test_rehydrate_revision_plan_regenerates_context():
    pipeline = PlannerPipeline()

    class StubRegistry:
        async def invoke(self, name, pipeline_obj, ctx, executed=None, **kwargs):
            if name == "intent_detection":
                intent_payload = {
                    "intent_key": "revenue_growth",
                    "confidence": 0.72,
                    "slots_detected": {"tickers": ["NVDA"]},
                    "assumptions": ["Using timeframe: last_4_quarters"],
                }
                ctx.intent = IntentModel.model_validate(intent_payload)
                slot_payload = {
                    "status": "filled",
                    "value": ["NVDA"],
                    "reason": "user_provided",
                    "suggestions": ["NVDA"],
                    "allow_custom": True,
                }
                ctx.slot_statuses = {"tickers": SlotStatusModel.model_validate(slot_payload)}
                resolution_payload = {
                    "intent": {"key": "revenue_growth", "confidence": 0.72, "mode": "single_agent"},
                    "slots": {"tickers": slot_payload},
                    "followups": [],
                }
                ctx.intent_resolution = IntentResolutionModel.model_validate(resolution_payload)
                yield {"event": "intent_detection_complete"}
            elif name == "plan_generation":
                plan_payload = {
                    "metrics": ["revenue"],
                    "granularity": "annual",
                    "comparison": "company",
                    "filters": {},
                }
                ctx.provisional_plan = QueryPlanModel.model_validate(plan_payload)
                ctx.plan = ctx.provisional_plan
                yield {"event": "plan_built"}
            else:
                yield {}

    pipeline._tool_registry = StubRegistry()  # type: ignore[attr-defined]

    ctx = PlannerPhaseContext(
        query="How is NVDA revenue trending?",
        session_id="rehydrate-session",
        workflow_start=0.0,
        timed_emitter=TimedEventEmitter(session_id="rehydrate-session", flow="planner-executor"),
    )

    success = await pipeline.rehydrate_revision_plan(ctx, executed={"classification"})

    assert success is True
    assert ctx.intent is not None
    assert ctx.plan is not None
    assert ctx.intent_signature is not None
    assert ctx.slot_statuses["tickers"].status == "filled"

    intent_receipt = ctx.tool_receipts.get("intent_detection")
    assert intent_receipt is not None
    assert intent_receipt.status == "completed"
    assert intent_receipt.reused is False

    plan_receipt = ctx.tool_receipts.get("plan_generation")
    assert plan_receipt is not None
    assert plan_receipt.status == "completed"
    assert plan_receipt.reused is False


@pytest.mark.asyncio
async def test_rehydrate_revision_plan_returns_false_when_plan_missing():
    pipeline = PlannerPipeline()

    class FailRegistry:
        async def invoke(self, name, pipeline_obj, ctx, executed=None, **kwargs):
            if name == "intent_detection":
                intent_payload = {
                    "intent_key": "cash_flow_trends",
                    "confidence": 0.6,
                    "slots_detected": {"tickers": ["AAPL"]},
                }
                ctx.intent = IntentModel.model_validate(intent_payload)
                yield {"event": "intent_detection_complete"}
            else:
                yield {}

    pipeline._tool_registry = FailRegistry()  # type: ignore[attr-defined]

    ctx = PlannerPhaseContext(
        query="Show Apple cash flow trends",
        session_id="rehydrate-failure",
        workflow_start=0.0,
        timed_emitter=TimedEventEmitter(session_id="rehydrate-failure", flow="planner-executor"),
    )

    success = await pipeline.rehydrate_revision_plan(ctx, executed={"classification"})

    assert success is False
    assert ctx.plan is None
    assert "plan_generation" not in ctx.tool_receipts


def test_derive_revision_topics_fallback_topics():
    fallback_basis = "highlight NVDA earnings momentum"
    topics = _derive_revision_topics(
        None,
        fallback_basis=fallback_basis,
        user_query="refresh NVDA outlook",
        analysis_text="Focus on quarterly earnings commentary.",
    )
    assert topics, "Expected fallback topics to be generated"
    assert len(topics) <= 5
    first_topic = topics[0]
    assert "query" in first_topic
    assert isinstance(first_topic["query"], str)

    directive = [{"query": "customer pipeline", "label": "Customer pipeline"}]
    preserved = _derive_revision_topics(
        directive,
        fallback_basis="ignore",
        user_query="unused",
        analysis_text=None,
    )
    assert preserved == directive


@pytest.mark.asyncio
async def test_persist_session_state_records_revision_snapshot_and_receipts():
    session_id = "snapshot-receipt-test"
    repo = get_session_state_repository()
    await repo.delete(session_id)

    pipeline = PlannerPipeline()
    ctx = PlannerPhaseContext(
        query="Summarize AMD capital expenditure trends",
        session_id=session_id,
        workflow_start=0.0,
        timed_emitter=TimedEventEmitter(session_id=session_id, flow="planner-executor"),
    )

    intent_payload = {
        "intent_key": "capex_trends",
        "confidence": 0.88,
        "slots_detected": {
            "tickers": ["AMD"],
            "metric": "Capital Expenditures",
            "comparison": "company",
        },
        "assumptions": ["metric defaulted to Capital Expenditures"],
    }
    ctx.intent = IntentModel.model_validate(intent_payload)
    plan_payload = {
        "metrics": ["Capital Expenditures"],
        "derived_metrics": [],
        "timeframe": {"years_back": 2, "granularity": "quarterly"},
        "granularity": "quarterly",
        "comparison": "company",
        "group_by": [],
        "filters": {},
        "limit": 50,
    }
    ctx.plan = QueryPlanModel.model_validate(plan_payload)
    ctx.provisional_plan = ctx.plan

    ctx.artifacts.intent = IntentArtifactModel(
        query=ctx.query,
        intent_key=ctx.intent.intent_key,
        confidence=ctx.intent.confidence,
        slots=ctx.intent.slots_detected,
        clarifications_needed=False,
        raw=intent_payload,
    )
    ctx.artifacts.plan = PlanArtifact(
        query=ctx.query,
        plan=ctx.plan.model_dump(),
        comparison=ctx.plan.comparison,
        granularity=ctx.plan.granularity,
        metrics_count=len(ctx.plan.metrics),
    )
    ctx.artifacts.analysis = AnalysisArtifact(
        query=ctx.query,
        analysis_text="Baseline analysis narrative",
    )

    await pipeline._persist_session_state(ctx, record_analysis=True, record_artifacts=True)

    snapshot = await repo.load(session_id)
    assert snapshot is not None
    analytics_cache = snapshot.tool_cache.get("analytics") or {}
    revision_snapshot = analytics_cache.get("revision_snapshot")
    assert revision_snapshot is not None, "Expected revision_snapshot to be persisted"
    assert revision_snapshot.get("intent_signature"), "Intent signature should be part of the revision snapshot"
    assert revision_snapshot.get("plan"), "Plan payload should be persisted in the revision snapshot"

    intent_receipt = snapshot.get_tool_receipt("intent_detection")
    assert intent_receipt is not None
    assert intent_receipt.get("status") == "completed"
    plan_receipt = snapshot.get_tool_receipt("plan_generation")
    assert plan_receipt is not None
    assert plan_receipt.get("status") == "completed"

    await repo.delete(session_id)
    await close_session_state_repository()
