# --- Analytics Function/Class Map ---
# Constant: CLASSIFIER_TIMEOUT_SECONDS
#   Role: Timeout budget for classifier calls.
#   Called from: _run_classifier_with_timeout
#   Invokes: os.getenv
#   Why: Bounds classification latency for all flows.
# Constant: PRIMARY_CLASSIFIER_MODEL
#   Role: Default classifier model.
#   Called from: _classification_phase
#   Invokes: None
#   Why: Ensures deterministic classifier selection.
# Constant: SECONDARY_CLASSIFIER_MODEL
#   Role: Fallback classifier model.
#   Called from: _classification_phase
#   Invokes: None
#   Why: Provides resilience when the primary fails.
# Constant: SCHEMA_CLARIFIER_ENABLED
#   Role: Feature flag for schema clarifier.
#   Called from: _intent_phase
#   Invokes: None
#   Why: Centralizes clarifier enablement across flows.
# Constant: _FLOW_MODE_TO_RESOLVER_MODE
#   Role: Maps FlowMode to resolver mode.
#   Called from: _classification_phase, _intent_phase
#   Invokes: None
#   Why: Aligns intent slot resolver behavior with flow mode.
# Function: _build_classifier_fallback
#   Role: Emits a polite fallback classification result when models fail.
#   Called from: _run_classifier_with_fallback
#   Invokes: OffTopicClassifierSchema
#   Why: Keeps classification deterministic on failure.
# Function: _run_classifier_with_timeout
#   Role: Executes classifier with a timeout budget.
#   Called from: _run_classifier_with_fallback
#   Invokes: classify_query_async, asyncio.wait_for
#   Why: Prevents hanging classification calls.
# Function: _run_classifier_with_fallback
#   Role: Runs primary classifier and falls back to secondary on failure.
#   Called from: _classification_phase
#   Invokes: _run_classifier_with_timeout
#   Why: Improves classification reliability.
# Function: _compose_intent_from_resolution
#   Role: Merges structured resolver output with heuristic intent signals.
#   Called from: _intent_phase
#   Invokes: detect_intent, post_process_slots
#   Why: Produces the final IntentModel for downstream stages.
# Function: _apply_plan_metric_defaults
#   Role: Auto-fills metric slots when the plan contains metrics.
#   Called from: _intent_phase
#   Invokes: normalize_metrics, detect_margin_choice_from_metrics
#   Why: Avoids redundant clarifications when metrics are already known.
# Function: _apply_plan_timeframe_defaults
#   Role: Auto-fills timeframe slots from the plan.
#   Called from: _intent_phase
#   Invokes: normalize_timeframe
#   Why: Prevents unnecessary clarifications for timeframe.
# Function: _followup_to_clarify_request
#   Role: Converts follow-up prompts to clarification requests.
#   Called from: _intent_phase, _refresh_followups
#   Invokes: ClarifyRequestModel
#   Why: Keeps follow-ups consistent with clarifier schema.
# Function: _request_allows_custom
#   Role: Determines if a clarify request permits custom answers.
#   Called from: _clarify_request_to_followup
#   Invokes: None
#   Why: Aligns follow-up prompts with allowed inputs.
# Function: _clarify_request_to_followup
#   Role: Converts clarify requests back to follow-up models.
#   Called from: _refresh_followups
#   Invokes: FollowUpModel
#   Why: Keeps slot follow-ups synchronized.
# Function: _filter_answered_requests
#   Role: Drops clarify requests for slots already answered.
#   Called from: _intent_phase
#   Invokes: None
#   Why: Prevents duplicate clarification prompts.
# Function: _upsert_slot_status
#   Role: Updates slot statuses with normalization and suggestion merging.
#   Called from: _intent_phase, _clarification_phase
#   Invokes: normalize_metrics, normalize_timeframe
#   Why: Centralizes slot status mutation logic.
# Function: _refresh_followups
#   Role: Syncs follow-up prompts on ctx and intent resolution.
#   Called from: _intent_phase, _clarification_phase
#   Invokes: _clarify_request_to_followup
#   Why: Keeps follow-ups aligned after clarifier decisions.
# Function: _classification_phase
#   Role: Runs classification + slot resolution with reuse handling.
#   Called from: run_classification_stage
#   Invokes: _run_classifier_with_fallback, resolve_intent_slots_async
#   Why: Shared classification implementation for all modes.
# Function: _intent_phase
#   Role: Runs intent resolution, schema clarifier, and clarification prep.
#   Called from: run_intent_stage
#   Invokes: _apply_plan_metric_defaults, _apply_plan_timeframe_defaults, compute_required_clarifications
#   Why: Shared intent logic for all modes.
# Function: run_classification_stage
#   Role: Executes classification via shared implementation.
#   Called from: analytics.flows.planner_executor.PlannerPipeline.run_classification
#   Invokes: _classification_phase
#   Why: Exposes classification as a reusable stage.
# Function: run_intent_stage
#   Role: Executes intent via shared implementation.
#   Called from: analytics.flows.planner_executor.PlannerPipeline.run_intent
#   Invokes: _intent_phase
#   Why: Exposes intent as a reusable stage.
# --- End Analytics Function/Class Map ---
from __future__ import annotations

import asyncio
import contextlib
import logging
import os
import time
import uuid
from datetime import datetime
from typing import Any, AsyncGenerator, Dict, List, Mapping, Optional, Sequence, Set

from analytics.core.context import get_configs
from analytics.core.events import EventEmitter
from analytics.core.intent import (
    classify_query_async,
    detect_intent,
    OffTopicClassifierSchema,
    post_process_slots,
)
from analytics.core.clarify import compute_required_clarifications
from analytics.core.intent_impl.detection import resolve_intent_slots_async
from analytics.core.intent_impl.models import IntentResolutionModel, SlotStatusModel, FollowUpModel
from analytics.core.intent_impl.normalization import normalize_metrics, normalize_timeframe
from analytics.core.margins import detect_margin_choice_from_metrics
from analytics.core.telemetry import intent_resolution as log_intent_resolution
from analytics.core.types import (
    ClarifyRequestModel,
    IntentModel,
    QueryPlanModel,
)
from analytics.artifacts import (
    ClassificationArtifact as ClassificationArtifactModel,
    IntentArtifact as IntentArtifactModel,
)
from analytics.sql.sql_planner import build_query_plan, choose_template
from analytics.agents.schema_clarifier import ClarifierDecision, decide_schema_clarification
from ..schedulers import FlowMode
from .stage_helpers import build_slot_assumptions as _build_slot_assumptions, normalize_metric_slots as _normalize_metric_slots

logger = logging.getLogger(__name__)

CLASSIFIER_TIMEOUT_SECONDS = float(os.getenv("ANALYTICS_CLASSIFIER_TIMEOUT_SECONDS", "6.0"))

# Helper: classifier models (OpenAI-only to avoid Gemini schema mismatches)
PRIMARY_CLASSIFIER_MODEL = os.getenv("OPENAI_CLASSIFIER_MODEL", "gpt-5-nano-2025-08-07")
SECONDARY_CLASSIFIER_MODEL = os.getenv("OPENAI_SECONDARY_CLASSIFIER_MODEL", "gpt-5-mini-2025-08-07")

# Schema clarifier is now always enabled (legacy env flag removed)
SCHEMA_CLARIFIER_ENABLED = True

_FLOW_MODE_TO_RESOLVER_MODE: Dict[FlowMode, str] = {
    FlowMode.DIRECT: "single_agent",
    FlowMode.SINGLE_AGENT: "fanout",
    FlowMode.MULTI_AGENT: "fanout",
}

CONFIGS = get_configs()


def _build_classifier_fallback(reason: str) -> OffTopicClassifierSchema:
    logger.warning("Classifier fallback engaged: %s", reason)
    polite_message = (
        "I'm focused on financial analytics questions. Please include a company, ticker, or metric if you need help."
    )
    return OffTopicClassifierSchema(
        is_financial_query=True,
        confidence=0.55,
        topic_category="financial_analytics",
        polite_decline_message=None,
        suggested_rephrase=polite_message,
    )


async def _run_classifier_with_timeout(
    ctx: Any,
    model_name: str,
    provider: Optional[str],
) -> OffTopicClassifierSchema:
    try:
        return await asyncio.wait_for(
            classify_query_async(
                ctx.query,
                session_id=ctx.session_id,
                model=model_name,
                reasoning_effort="low",
                provider=provider,
            ),
            timeout=CLASSIFIER_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError:
        logger.warning(
            "[CLASSIFICATION] Model timeout after %.2fs (session=%s)",
            CLASSIFIER_TIMEOUT_SECONDS,
            ctx.session_id,
        )
        raise
    except Exception:
        logger.exception("[CLASSIFICATION] Model error; propagating")
        raise


async def _run_classifier_with_fallback(
    ctx: Any,
    primary_model: str = PRIMARY_CLASSIFIER_MODEL,
    secondary_model: str = SECONDARY_CLASSIFIER_MODEL,
) -> OffTopicClassifierSchema:
    """
    Run the primary classifier (provider inferred from model); on failure, fall back to the secondary model/provider.
    """
    primary_provider = "openai"
    secondary_provider = "openai"
    try:
        return await _run_classifier_with_timeout(ctx, primary_model, primary_provider)
    except Exception as exc:  # pragma: no cover - fallback path validated separately
        logger.warning(
            "[CLASSIFICATION] Primary classifier failed; falling back to secondary model %s (provider=%s): %s",
            secondary_model,
            secondary_provider,
            exc,
        )
        return await _run_classifier_with_timeout(ctx, secondary_model, secondary_provider)


def _compose_intent_from_resolution(
    query: str,
    configs: Mapping[str, Any],
    resolution: IntentResolutionModel,
    *,
    assumptions: Sequence[str] = (),
) -> IntentModel:
    """Merge structured slot resolution output with heuristic signals into a runtime IntentModel."""
    heuristic_model = detect_intent(query, configs)

    selection = getattr(resolution, "intent", None)
    intent_key = getattr(selection, "key", None)
    if not intent_key:
        intent_key = heuristic_model.intent_key
    confidence = getattr(selection, "confidence", None)
    if confidence is None:
        confidence = heuristic_model.confidence

    slots_detected: Dict[str, Any] = {}
    for slot_name, status in (resolution.slots or {}).items():
        if not isinstance(status, SlotStatusModel):
            continue
        if status.value is None:
            continue
        slots_detected[slot_name] = status.value

    slots_detected["original_query"] = query
    normalized_slots = post_process_slots(slots_detected, query, configs)

    reasoning = resolution.notes or heuristic_model.intent_reasoning or ""

    combined_assumptions = list(heuristic_model.assumptions or [])
    for assumption in assumptions:
        if assumption not in combined_assumptions:
            combined_assumptions.append(assumption)

    return IntentModel(
        intent_key=intent_key,
        confidence=confidence or 0.0,
        slots_detected=normalized_slots,
        assumptions=combined_assumptions,
        clarifications_suggested=list(heuristic_model.clarifications_suggested or []),
        possible_intents=list(heuristic_model.possible_intents or []),
        intent_reasoning=reasoning,
    )


def _apply_plan_metric_defaults(
    ctx: Any,
    plan: Optional[QueryPlanModel],
    *,
    configs: Mapping[str, Any],
) -> List[str]:
    """
    Ensure metric slots are populated when the query plan already specifies concrete metrics.

    Returns the normalized metric list that was applied, or an empty list if no updates occurred.
    """
    if plan is None:
        return []
    plan_metrics = list(getattr(plan, "metrics", []) or [])
    if not plan_metrics:
        return []

    normalized_metrics = normalize_metrics(plan_metrics, configs)
    if not normalized_metrics:
        return []

    intent_key = getattr(getattr(ctx, "intent", None), "intent_key", None)
    if intent_key in {"margins_vs_peers", "margin_growth_vs_peers"}:
        margin_choice = detect_margin_choice_from_metrics(normalized_metrics)
        if margin_choice is None:
            return []

    updated = False
    metric_status = ctx.slot_statuses.get("metric")
    metric_value_missing = True
    if isinstance(metric_status, SlotStatusModel):
        value = metric_status.value
        if isinstance(value, str) and value.strip():
            metric_value_missing = False
        elif isinstance(value, (list, tuple, set)) and any(v for v in value):
            metric_value_missing = False
        elif value is not None and not isinstance(value, (list, tuple, set, str)):
            metric_value_missing = False

    if metric_value_missing:
        suggestions = list(metric_status.suggestions or []) if isinstance(metric_status, SlotStatusModel) else []
        if not suggestions:
            suggestions = normalized_metrics
        reason = None
        allow_custom = True
        if isinstance(metric_status, SlotStatusModel):
            reason = metric_status.reason
            if metric_status.allow_custom is not None:
                allow_custom = metric_status.allow_custom
        ctx.slot_statuses["metric"] = SlotStatusModel(
            status="defaulted",
            value=normalized_metrics[0],
            reason=reason or "Metric auto-filled from plan defaults.",
            suggestions=suggestions,
            allow_custom=allow_custom,
        )
        ctx.intent_resolution.slots["metric"] = ctx.slot_statuses["metric"]
        updated = True

    metrics_status = ctx.slot_statuses.get("metrics")
    metrics_value_missing = True
    if isinstance(metrics_status, SlotStatusModel):
        value = metrics_status.value
        if isinstance(value, (list, tuple, set)) and any(value):
            metrics_value_missing = False
        elif isinstance(value, str) and value.strip():
            metrics_value_missing = False
        elif value not in (None, "", []):
            metrics_value_missing = False

    if metrics_value_missing:
        suggestions = list(metrics_status.suggestions or []) if isinstance(metrics_status, SlotStatusModel) else []
        if not suggestions:
            suggestions = normalized_metrics
        reason = None
        allow_custom = True
        if isinstance(metrics_status, SlotStatusModel):
            reason = metrics_status.reason
            if metrics_status.allow_custom is not None:
                allow_custom = metrics_status.allow_custom
        ctx.slot_statuses["metrics"] = SlotStatusModel(
            status="defaulted",
            value=normalized_metrics,
            reason=reason or "Metrics auto-filled from plan defaults.",
            suggestions=suggestions,
            allow_custom=allow_custom,
        )
        ctx.intent_resolution.slots["metrics"] = ctx.slot_statuses["metrics"]
        updated = True

    if updated:
        if ctx.intent_resolution.followups:
            ctx.intent_resolution.followups = [
                followup for followup in ctx.intent_resolution.followups if followup.slot not in {"metric", "metrics"}
            ]
        ctx.slot_followups = [followup for followup in ctx.slot_followups if followup.slot not in {"metric", "metrics"}]

    return normalized_metrics if updated else []


def _apply_plan_timeframe_defaults(
    ctx: Any,
    plan: Optional[QueryPlanModel] = None,
    *,
    configs: Optional[Mapping[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    """
    Populate the timeframe slot from an existing plan so we do not re-ask for a value the plan already encodes.
    """
    plan = plan or getattr(ctx, "provisional_plan", None) or getattr(ctx, "plan", None)
    if plan is None:
        return None
    configs_dict = dict(configs or getattr(CONFIGS, "__dict__", {}) or {})
    plan_tf = getattr(plan, "timeframe", None)
    if not plan_tf:
        return None
    if hasattr(plan_tf, "model_dump"):
        tf_payload = plan_tf.model_dump(exclude_none=True)
        if not tf_payload:
            return None
    elif isinstance(plan_tf, Mapping):
        non_null_fields = {k: v for k, v in plan_tf.items() if v not in (None, "", [], {})}
        if not non_null_fields:
            return None
    else:
        return None

    normalized_tf = normalize_timeframe(plan_tf, ctx.query or "", configs_dict, origin="plan_default")
    if not normalized_tf:
        return None

    existing_status = ctx.slot_statuses.get("timeframe")
    if isinstance(existing_status, SlotStatusModel):
        if existing_status.status in {"filled", "assumed", "defaulted"} and existing_status.value not in (None, "", [], {}):
            return normalized_tf
        suggestions = list(existing_status.suggestions or [])
        allow_custom = existing_status.allow_custom
        reason = existing_status.reason or "Timeframe auto-filled from plan defaults."
    else:
        suggestions = []
        allow_custom = True
        reason = "Timeframe auto-filled from plan defaults."

    preset_value = normalized_tf.get("preset") if isinstance(normalized_tf, Mapping) else None
    if preset_value and isinstance(preset_value, str) and preset_value not in suggestions:
        suggestions.append(preset_value)

    ctx.slot_statuses["timeframe"] = SlotStatusModel(
        status="defaulted",
        value=normalized_tf,
        reason=reason,
        suggestions=suggestions,
        allow_custom=allow_custom if allow_custom is not None else True,
    )

    if ctx.intent_resolution:
        ctx.intent_resolution.slots["timeframe"] = ctx.slot_statuses["timeframe"]
        if ctx.intent_resolution.followups:
            ctx.intent_resolution.followups = [followup for followup in ctx.intent_resolution.followups if followup.slot != "timeframe"]
    if ctx.slot_followups:
        ctx.slot_followups = [followup for followup in ctx.slot_followups if followup.slot != "timeframe"]

    already_recorded = False
    for answer in ctx.clarification_answers:
        if isinstance(answer, Mapping) and answer.get("slot") == "timeframe":
            already_recorded = True
            break
    if not already_recorded:
        ctx.clarification_answers.append(
            {
                "slot": "timeframe",
                "value": normalized_tf,
                "source": "plan_default",
                "ts": datetime.utcnow().isoformat(),
            }
        )

    return normalized_tf


def _build_schema_clarifier_request(decision: ClarifierDecision, session_id: str) -> Optional[ClarifyRequestModel]:
    if not decision.slot or not decision.question:
        return None
    options = decision.options or []
    default_option = options[0] if options else None
    input_type = "single" if options else "free"
    return ClarifyRequestModel(
        slot=decision.slot,
        question=decision.question,
        type=input_type,
        options=options,
        default=default_option,
        reason=decision.reason or "Required by the schema clarifier.",
        required=True,
        request_id=str(uuid.uuid4()),
        proposed=None,
        proposed_confidence=None,
        session_id=session_id,
    )


def _followup_to_clarify_request(followup: FollowUpModel, session_id: str) -> ClarifyRequestModel:
    options = list(followup.suggestions or [])
    allow_custom = followup.allow_custom if followup.allow_custom is not None else True
    if options:
        input_type = "single"
    else:
        input_type = "free"
    default_option = options[0] if options else None
    reason = followup.reason or "Additional information is required to continue."
    return ClarifyRequestModel(
        slot=followup.slot,
        question=followup.prompt,
        type=input_type,
        options=options,
        default=default_option if not allow_custom else None,
        reason=reason,
        required=True,
        request_id=str(uuid.uuid4()),
        proposed=default_option if allow_custom and default_option else None,
        proposed_confidence=None,
        session_id=session_id,
        allow_custom=allow_custom,
    )


def _request_allows_custom(request: ClarifyRequestModel) -> bool:
    allow_custom = getattr(request, "allow_custom", None)
    if allow_custom is not None:
        return bool(allow_custom)
    return not (request.type == "single" and request.options)


def _clarify_request_to_followup(request: ClarifyRequestModel) -> FollowUpModel:
    allow_custom = _request_allows_custom(request)
    return FollowUpModel(
        slot=request.slot,
        prompt=request.question,
        suggestions=list(request.options or []),
        allow_custom=allow_custom,
        reason=request.reason or None,
    )


def _filter_answered_requests(
    requests: Sequence[ClarifyRequestModel], answered_slots: Set[str]
) -> List[ClarifyRequestModel]:
    """
    Drop clarification requests whose slots have already been satisfied by defaults or prior answers.
    """
    normalized_answered = {
        slot.strip().lower() for slot in answered_slots if isinstance(slot, str) and slot.strip()
    }
    filtered: List[ClarifyRequestModel] = []
    for request in requests or []:
        slot = getattr(request, "slot", None)
        if not isinstance(slot, str):
            continue
        if slot.strip().lower() in normalized_answered:
            continue
        filtered.append(request)
    return filtered


def _upsert_slot_status(
    ctx: Any,
    slot: str,
    *,
    status: str,
    value: Any,
    reason: Optional[str] = None,
    suggestions: Optional[Sequence[str]] = None,
    allow_custom: Optional[bool] = None,
) -> SlotStatusModel:
    normalized_value = value
    if status == "filled":
        if slot == "timeframe":
            normalized_tf = normalize_timeframe(value, '', CONFIGS.__dict__, origin='clarification')
            if normalized_tf:
                normalized_value = normalized_tf
        elif slot in {"metric", "metrics"}:
            normalized_metrics = normalize_metrics(value, CONFIGS.__dict__)
            if slot == "metric":
                if normalized_metrics:
                    normalized_value = normalized_metrics[0]
            else:
                if normalized_metrics:
                    normalized_value = normalized_metrics

    existing = ctx.slot_statuses.get(slot)
    merged_suggestions: List[str] = []
    if existing and existing.suggestions:
        merged_suggestions.extend(existing.suggestions)
    if suggestions:
        for item in suggestions:
            if item not in merged_suggestions:
                merged_suggestions.append(item)
    resolved_reason = (
        reason
        if reason is not None
        else (existing.reason if existing else None)
    )
    resolved_allow_custom = (
        allow_custom
        if allow_custom is not None
        else (existing.allow_custom if existing is not None else None)
    )
    slot_model = SlotStatusModel(
        status=status,  # type: ignore[arg-type]
        value=normalized_value,
        reason=resolved_reason,
        suggestions=merged_suggestions,
        allow_custom=resolved_allow_custom,
    )
    ctx.slot_statuses[slot] = slot_model
    if ctx.intent_resolution is not None:
        ctx.intent_resolution.slots[slot] = slot_model
    return slot_model


def _refresh_followups(ctx: Any, requests: Sequence[ClarifyRequestModel]) -> None:
    followups = [_clarify_request_to_followup(request) for request in requests]
    ctx.slot_followups = list(followups)
    if ctx.intent_resolution is not None:
        ctx.intent_resolution.followups = list(followups)


async def _classification_phase(pipeline: Any, ctx: Any) -> AsyncGenerator[Dict[str, Any], None]:
    if ctx.classification is not None and ctx.intent_resolution is not None:
        yield {
            "event": "classification_reused",
            "data": {
                "message": "Reusing cached classification and slot resolution.",
                "category": getattr(ctx.classification, "topic_category", None),
                "confidence": getattr(ctx.classification, "confidence", None),
                "ts": datetime.utcnow().isoformat(),
            },
        }
        return

    timed_emitter = ctx.timed_emitter
    timed_emitter.start_step("classification")
    classification_started_ts = datetime.utcnow().isoformat()
    model_name = PRIMARY_CLASSIFIER_MODEL
    classifier_provider = "gemini" if "gemini" in model_name.lower() else "openai"
    yield {
        "event": "classification_started",
        "data": {
            "message": "Starting query classification...",
            "model": model_name,
            "provider": classifier_provider,
            "step": "classification",
            "ts": classification_started_ts,
        },
    }

    resolver_mode = _FLOW_MODE_TO_RESOLVER_MODE.get(ctx.flow_mode, "single_agent")
    prior_slot_values = {
        slot: status.value
        for slot, status in (ctx.slot_statuses or {}).items()
        if isinstance(status, SlotStatusModel) and status.value is not None
    }
    slot_task = asyncio.create_task(
        resolve_intent_slots_async(
            ctx.query,
            CONFIGS.__dict__,
            mode=resolver_mode,
            context_slots=prior_slot_values or None,
            session_id=ctx.session_id,
        ),
        name=f"intent-slots::{ctx.session_id}",
    )
    classifier_task = asyncio.create_task(
        _run_classifier_with_fallback(ctx, PRIMARY_CLASSIFIER_MODEL, SECONDARY_CLASSIFIER_MODEL),
        name=f"classifier::{ctx.session_id}",
    )
    try:
        classification, slot_resolution = await asyncio.gather(classifier_task, slot_task)
    except Exception:
        classifier_task.cancel()
        slot_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await classifier_task
            await slot_task
        raise

    ctx.intent_resolution = slot_resolution
    ctx.classification = classification
    ctx.is_financial_query = bool(getattr(classification, "is_financial_query", False))
    ctx.artifacts.classification = ClassificationArtifactModel(
        query=ctx.query,
        category=getattr(classification, "topic_category", None),
        confidence=getattr(classification, "confidence", None),
        is_financial=getattr(classification, "is_financial_query", None),
        model=model_name,
        raw=classification.model_dump(),
    )
    if hasattr(pipeline, "_capture_artifacts"):
        pipeline._capture_artifacts(ctx)
    reasoning_message = f"LLM classified topic '{classification.topic_category}'"
    yield {
        "event": "classification_reasoning",
        "data": {
            "thinking": reasoning_message,
            "confidence": classification.confidence,
            "category": classification.topic_category,
            "step": "classification",
            "ts": datetime.utcnow().isoformat(),
        },
    }
    classification_elapsed = timed_emitter.end_step("classification")
    classification_complete = {
        "event": "classification_complete",
        "data": {
            "is_financial": ctx.is_financial_query,
            "category": classification.topic_category,
            "confidence": classification.confidence,
            "ts": datetime.utcnow().isoformat(),
        },
    }
    if classification_elapsed:
        classification_complete["data"]["elapsed_ms"] = classification_elapsed
    yield classification_complete
    if not ctx.is_financial_query and not getattr(ctx, "is_revision_follow_up", False):
        polite_default = (
            "I'm focused on financial analytics questions. Please rephrase with a company, metric, or ticker so I can help."
        )
        decline_message = classification.polite_decline_message or polite_default
        if len(decline_message) > 200:
            decline_message = decline_message[:197] + "..."
        decline_notice = {
            "event": "classification_declined",
            "data": {
                "message": decline_message,
                "category": classification.topic_category,
                "confidence": classification.confidence,
                "ts": datetime.utcnow().isoformat(),
            },
        }
        yield decline_notice
        final_event = {
            "event": "final_answer",
            "data": {
                "message": decline_message,
                "confidence": classification.confidence,
                "category": classification.topic_category,
                "ts": datetime.utcnow().isoformat(),
            },
        }
        if getattr(classification, "suggested_rephrase", None):
            final_event["data"]["suggested_rephrase"] = classification.suggested_rephrase
        yield final_event
        result_builder = getattr(pipeline, "build_planner_result_payload", None)
        if callable(result_builder):
            planner_payload = result_builder(ctx)
            result_event = EventEmitter.result("planner_result", planner_payload)
            result_event["event"] = "planner_result"
            result_event["data"]["ts"] = datetime.utcnow().isoformat()
            yield result_event
        workflow_summary = {
            "status": "off_topic",
            "category": classification.topic_category,
            "total_elapsed_ms": int((time.time() - ctx.workflow_start) * 1000),
        }
        workflow_complete = EventEmitter.result("workflow_complete", workflow_summary)
        workflow_complete["event"] = "workflow_complete"
        workflow_complete["data"]["ts"] = datetime.utcnow().isoformat()
        yield workflow_complete


async def _intent_phase(pipeline: Any, ctx: Any) -> AsyncGenerator[Dict[str, Any], None]:
    timed_emitter = ctx.timed_emitter
    intent_progress = EventEmitter.progress("intent_detection", "Detecting intent...")
    intent_progress["data"]["ts"] = datetime.utcnow().isoformat()
    yield intent_progress
    timed_emitter.start_step("intent_detection")
    yield {
        "event": "intent_detection_started",
        "data": {
            "message": "Analyzing query intent...",
            "ts": datetime.utcnow().isoformat(),
        },
    }
    intent_start = time.time()
    slot_resolution = ctx.intent_resolution
    if slot_resolution is None:
        resolver_mode = _FLOW_MODE_TO_RESOLVER_MODE.get(ctx.flow_mode, "single_agent")
        prior_slot_values = {
            slot: status.value
            for slot, status in (ctx.slot_statuses or {}).items()
            if isinstance(status, SlotStatusModel) and status.value is not None
        }
        slot_resolution = await resolve_intent_slots_async(
            ctx.query,
            CONFIGS.__dict__,
            mode=resolver_mode,
            context_slots=prior_slot_values or None,
            session_id=ctx.session_id,
        )
    ctx.intent_resolution = slot_resolution
    _normalize_metric_slots(slot_resolution)
    ctx.intent_resolution = slot_resolution
    ctx.slot_statuses = slot_resolution.slots
    ctx.slot_followups = list(slot_resolution.followups or [])

    slot_assumptions = _build_slot_assumptions(ctx.slot_statuses)
    intent = _compose_intent_from_resolution(
        ctx.query,
        CONFIGS.__dict__,
        slot_resolution,
        assumptions=slot_assumptions,
    )
    ctx.intent = intent
    ctx.assumptions = list(intent.assumptions or [])

    intent_elapsed = timed_emitter.end_step("intent_detection")
    resolver_status = "structured"
    if isinstance(slot_resolution.notes, str) and "fell back" in slot_resolution.notes.lower():
        resolver_status = "fallback"

    ctx.provisional_plan = build_query_plan(intent, CONFIGS.__dict__)
    ctx.template = choose_template(intent, ctx.provisional_plan, CONFIGS.__dict__)

    plan_timeframe_defaults = _apply_plan_timeframe_defaults(
        ctx,
        ctx.provisional_plan,
        configs=CONFIGS.__dict__,
    )
    if plan_timeframe_defaults:
        slot_assumptions = _build_slot_assumptions(ctx.slot_statuses)
        intent = _compose_intent_from_resolution(
            ctx.query,
            CONFIGS.__dict__,
            ctx.intent_resolution,
            assumptions=slot_assumptions,
        )
        ctx.intent = intent
        ctx.assumptions = list(intent.assumptions or [])

    plan_metric_defaults = _apply_plan_metric_defaults(
        ctx,
        ctx.provisional_plan,
        configs=CONFIGS.__dict__,
    )
    if plan_metric_defaults:
        slot_assumptions = _build_slot_assumptions(ctx.slot_statuses)
        intent = _compose_intent_from_resolution(
            ctx.query,
            CONFIGS.__dict__,
            ctx.intent_resolution,
            assumptions=slot_assumptions,
        )
        ctx.intent = intent
        ctx.assumptions = list(intent.assumptions or [])

    slot_status_payload = {
        slot: {
            "status": status.status,
            "value": status.value,
            "reason": status.reason,
            "suggestions": list(status.suggestions or []),
            "allow_custom": status.allow_custom,
        }
        for slot, status in ctx.slot_statuses.items()
    }

    clarification_sources: Set[str] = set()
    if ctx.slot_followups:
        clarification_sources.add("structured_resolver")
    if resolver_status == "fallback":
        clarification_sources.add("heuristic_fallback")

    schema_decision: Optional[ClarifierDecision] = None
    if SCHEMA_CLARIFIER_ENABLED and ctx.template is not None:
        try:
            schema_decision = await asyncio.to_thread(
                decide_schema_clarification,
                intent,
                ctx.provisional_plan,
                session_id=ctx.session_id,
                template_id=intent.intent_key or (ctx.template.get("name") if isinstance(ctx.template, dict) else None),
                slot_statuses=ctx.slot_statuses,
            )
        except Exception as exc:
            logger.exception("[SCHEMA_CLARIFIER] decision failed: %s", exc)
            schema_decision = ClarifierDecision(action="fallback", missing_slots=[])
    elif SCHEMA_CLARIFIER_ENABLED:
        schema_decision = ClarifierDecision(action="fallback", missing_slots=[])

    ctx.clarifier_agent_invoked = bool(schema_decision)
    ctx.schema_clarifier_decision = schema_decision
    intent_raw = intent.model_dump()
    try:
        intent_raw["slot_resolution"] = slot_resolution.model_dump()
    except Exception:  # pragma: no cover - defensive
        intent_raw["slot_resolution"] = {}
    schema_requires_clarification = bool(schema_decision and getattr(schema_decision, "action", None) == "request")
    if SCHEMA_CLARIFIER_ENABLED:
        clarifier_event = EventEmitter.progress(
            "schema_clarifier",
            f"Schema clarifier decision: {(schema_decision.action if schema_decision else 'disabled')}",
        )
        clarifier_event["data"].update(
            {
                "action": schema_decision.action if schema_decision else "disabled",
                "missing_slots": schema_decision.missing_slots if schema_decision else [],
                "enabled": True,
                "ts": datetime.utcnow().isoformat(),
            }
        )
        if schema_decision and schema_decision.slot:
            clarifier_event["data"]["slot"] = schema_decision.slot
        yield clarifier_event
        completion_action = schema_decision.action if schema_decision else "disabled"
        if completion_action in {"skip", "fallback", "disabled"}:
            yield EventEmitter.complete(
                "schema_clarifier",
                f"Schema clarifier {completion_action}",
            )

    clarifier_request: Optional[ClarifyRequestModel] = None
    if schema_decision and schema_decision.action == "skip":
        official_clarifications: List[ClarifyRequestModel] = []
    else:
        official_clarifications = compute_required_clarifications(
            intent, ctx.provisional_plan, ctx.template, CONFIGS.__dict__
        )
        if official_clarifications:
            clarification_sources.add("structured_resolver")
        if schema_decision and schema_decision.action == "clarify" and not official_clarifications and not ctx.slot_followups:
            clarifier_request = _build_schema_clarifier_request(schema_decision, ctx.session_id)
            if clarifier_request:
                official_clarifications = [clarifier_request] + [
                    request for request in official_clarifications if request.slot != clarifier_request.slot
                ]
                clarification_sources.add("schema_clarifier")
    slot_followup_requests: List[ClarifyRequestModel] = [
        _followup_to_clarify_request(followup, ctx.session_id) for followup in ctx.slot_followups
    ]
    if slot_followup_requests:
        clarification_sources.add("structured_resolver")
    if slot_followup_requests:
        existing_slots = {request.slot for request in slot_followup_requests}
        remaining_requests = [
            request for request in official_clarifications if request.slot not in existing_slots
        ]
        official_clarifications = slot_followup_requests + remaining_requests
    deduped_requests: List[ClarifyRequestModel] = []
    seen_slots: set[str] = set()
    for request in official_clarifications:
        if request.slot in seen_slots:
            continue
        seen_slots.add(request.slot)
        deduped_requests.append(request)
    for request in deduped_requests:
        existing_status = ctx.slot_statuses.get(request.slot)
        allow_custom_flag = _request_allows_custom(request)
        status_name = existing_status.status if existing_status else "missing"
        value = existing_status.value if existing_status else None
        _upsert_slot_status(
            ctx,
            request.slot,
            status=status_name,
            value=value,
            reason=request.reason,
            suggestions=request.options,
            allow_custom=allow_custom_flag,
        )
    _refresh_followups(ctx, deduped_requests)
    slot_followup_payload = [
        {
            "slot": followup.slot,
            "prompt": followup.prompt,
            "suggestions": list(followup.suggestions or []),
            "allow_custom": followup.allow_custom,
            "reason": followup.reason,
        }
        for followup in ctx.slot_followups
    ]
    ctx.clarifications = deduped_requests
    ctx.assumptions = list(ctx.assumptions or [])
    ctx.clarification_sources = clarification_sources
    ctx.clarification_rounds = 0
    clarifications_required_flag = bool(deduped_requests) or schema_requires_clarification
    ctx.artifacts.intent = IntentArtifactModel(
        query=ctx.query,
        intent_key=getattr(intent, "intent_key", None),
        confidence=getattr(intent, "confidence", None),
        slots=dict(getattr(intent, "slots_detected", {}) or {}),
        clarifications_needed=clarifications_required_flag,
        low_confidence=getattr(intent, "low_confidence", None),
        raw=intent_raw,
    )
    if hasattr(pipeline, "_capture_artifacts"):
        pipeline._capture_artifacts(ctx)
    clarifications_needed = bool(deduped_requests)
    confidence_sufficient = (intent.confidence or 0.0) >= 0.75

    log_intent_resolution(
        intent_key=intent.intent_key,
        confidence=intent.confidence,
        slot_statuses=slot_status_payload,
        slot_followups=slot_followup_payload,
        elapsed_ms=intent_elapsed or int((time.time() - intent_start) * 1000),
        session_id=ctx.session_id,
        flow=ctx.flow_mode.value if isinstance(ctx.flow_mode, FlowMode) else str(ctx.flow_mode),
        resolver_status=resolver_status,
        clarification_sources=sorted(clarification_sources),
    )

    intent_complete = {
        "event": "intent_detection_complete",
        "data": {
            "intent_key": intent.intent_key,
            "confidence": intent.confidence,
            "slots_detected": intent.slots_detected,
            "slot_statuses": slot_status_payload,
            "slot_followups": slot_followup_payload,
            "clarification_sources": sorted(clarification_sources),
            "resolver_notes": slot_resolution.notes,
            "ts": datetime.utcnow().isoformat(),
            "elapsed_ms": int((time.time() - intent_start) * 1000),
        },
    }
    if intent_elapsed:
        intent_complete["data"]["elapsed_ms"] = intent_elapsed
    yield intent_complete

    if clarifications_needed:
        intent_status_event = EventEmitter.intent_draft(
            confidence=intent.confidence,
            clarifications_needed=True,
            clarifications_count=len(deduped_requests),
        )
    else:
        intent_status_event = EventEmitter.intent_decided(
            key=intent.intent_key,
            confidence=intent.confidence,
            clarifications_needed=False,
        )
        if not confidence_sufficient:
            intent_status_event["data"]["low_confidence"] = True
        if schema_decision:
            intent_status_event["data"]["schema_clarifier_action"] = schema_decision.action
            if schema_decision.missing_slots:
                intent_status_event["data"]["schema_clarifier_missing"] = schema_decision.missing_slots

    intent_status_event["data"]["slot_statuses"] = slot_status_payload
    intent_status_event["data"]["slot_followups"] = slot_followup_payload
    intent_status_event["data"]["clarification_sources"] = sorted(clarification_sources)
    intent_status_event["data"]["ts"] = datetime.utcnow().isoformat()
    if intent_elapsed:
        intent_status_event["data"]["elapsed_ms"] = intent_elapsed
    yield intent_status_event


async def run_classification_stage(pipeline: Any, ctx: Any) -> AsyncGenerator[Dict[str, Any], None]:
    async for event in _classification_phase(pipeline, ctx):
        yield event


async def run_intent_stage(pipeline: Any, ctx: Any) -> AsyncGenerator[Dict[str, Any], None]:
    async for event in _intent_phase(pipeline, ctx):
        yield event

