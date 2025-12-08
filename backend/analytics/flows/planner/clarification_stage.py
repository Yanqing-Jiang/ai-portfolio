# --- Analytics Function/Class Map ---
# Function: run_clarification_stage
#   Role: Execute the clarification phase with blocking/non-blocking handling, answer validation, auto-fill, and artifact capture.
#   Called from: analytics.flows.planner_executor.PlannerPipeline._clarification_phase
#   Invokes: _filter_answered_requests, _refresh_followups, _upsert_slot_status, _auto_fill_missing_slots, compute_required_clarifications
#   Why: Centralizes clarification handling for reuse across flows and reduces planner_executor size.
# Function: _auto_fill_missing_slots
#   Role: Auto-fill slots using assumptions, suggestions, and plan-aware defaults when not blocking.
#   Called from: run_clarification_stage
#   Invokes: SlotStatusModel, normalize_timeframe, normalize_metrics
#   Why: Reduces user clarification prompts by applying sensible defaults.
# --- End Analytics Function/Class Map ---
from __future__ import annotations

import asyncio
import logging
import time
import uuid
from datetime import datetime
from typing import Any, AsyncGenerator, Dict, List, Mapping, Optional, Sequence, Set, Tuple

from analytics.artifacts import ClarificationArtifact
from analytics.core.clarify import (
    compute_required_clarifications,
    get_validation_error_message,
    merge_answers,
    validate_clarification_answer,
    wait_for_answer_blocking,
)
from analytics.core.context import get_configs
from analytics.core.events import EventEmitter
from analytics.core.types import ClarifyAnswerModel, ClarifyRequestModel
from analytics.sql.sql_planner import choose_template

# Import shared helpers from intent_stage
from .intent_stage import (
    _filter_answered_requests,
    _refresh_followups,
    _request_allows_custom,
    _upsert_slot_status,
)

logger = logging.getLogger(__name__)

CONFIGS = get_configs()


def _auto_fill_missing_slots(
    ctx: Any,
    assumptions: List[str],
) -> Tuple[List[str], List[ClarifyAnswerModel]]:
    """
    Auto-fill missing slots using existing assumptions, suggestions, and plan-aware defaults.

    Returns:
        Tuple of (remaining_missing_slot_names, auto_filled_answers)
    """
    from analytics.core.intent_impl.models import SlotStatusModel
    from analytics.core.intent_impl.normalization import normalize_metrics, normalize_timeframe

    assumption_lookup: Dict[str, str] = {}
    for assumption in assumptions:
        if not isinstance(assumption, str):
            continue
        parts = assumption.split(":", 1)
        if len(parts) != 2:
            continue
        key, value = parts
        assumption_lookup[key.strip().lower()] = value.strip()

    remaining_missing: List[str] = []
    auto_answers: List[ClarifyAnswerModel] = []

    provisional_plan = getattr(ctx, "provisional_plan", None) or getattr(ctx, "plan", None)
    intent = getattr(ctx, "intent", None)
    session_id = getattr(ctx, "session_id", None) or str(uuid.uuid4())

    for slot_name, status in (ctx.slot_statuses or {}).items():
        if not isinstance(status, SlotStatusModel):
            continue
        if status.status != "missing":
            continue

        slot_label = slot_name.replace("_", " ")
        assumption_key = f"using {slot_label}".lower()
        assumed_value = assumption_lookup.get(assumption_key)
        if assumed_value:
            status.status = "assumed"
            status.value = assumed_value
            if not status.reason:
                status.reason = "Auto-filled from existing assumptions."
            ctx.slot_statuses[slot_name] = status
            auto_answers.append(
                ClarifyAnswerModel(
                    value=assumed_value,
                    request_id=f"auto-{slot_name}",
                    slot=slot_name,
                    session_id=session_id,
                    ts=datetime.utcnow().isoformat(),
                )
            )
            continue

        auto_value: Optional[Any] = None
        auto_reason: Optional[str] = None

        # Single suggestion
        if status.suggestions and len(status.suggestions) == 1:
            auto_value = status.suggestions[0]
            auto_reason = "Single suggestion auto-selected"
        # Plan-derived timeframe
        elif slot_name == "timeframe" and provisional_plan:
            plan_tf = getattr(provisional_plan, "timeframe", None)
            if plan_tf:
                normalized = normalize_timeframe(plan_tf, ctx.query or "", CONFIGS.__dict__, origin="auto_fill")
                if normalized:
                    auto_value = normalized
                    auto_reason = "Timeframe inferred from plan"
        # Plan-derived metrics
        elif slot_name in {"metric", "metrics"} and provisional_plan:
            plan_metrics = list(getattr(provisional_plan, "metrics", []) or [])
            if plan_metrics:
                normalized_metrics = normalize_metrics(plan_metrics, CONFIGS.__dict__)
                if normalized_metrics:
                    auto_value = normalized_metrics[0] if slot_name == "metric" else normalized_metrics
                    auto_reason = "Metrics inferred from plan"
        # Comparison default when multiple tickers detected
        elif slot_name == "comparison":
            intent_tickers: List[str] = []
            if intent and isinstance(getattr(intent, "slots_detected", None), dict):
                intent_raw_tickers = intent.slots_detected.get("tickers")
                if isinstance(intent_raw_tickers, (list, tuple, set)):
                    for value in intent_raw_tickers:
                        symbol = str(value).strip().upper()
                        if symbol and symbol not in intent_tickers and symbol != "ALL":
                            intent_tickers.append(symbol)
            if intent_tickers and len(intent_tickers) >= 2:
                auto_value = "all"
                auto_reason = "Comparison inferred from multiple tickers"

        # Fallback defaults
        if auto_value is None:
            if slot_name == "timeframe":
                if status.suggestions:
                    auto_value = status.suggestions[0]
                    auto_reason = "Timeframe auto-selected from suggestions"
                else:
                    auto_value = "last_5_years"
                    auto_reason = "Timeframe defaulted to last_5_years"
            elif slot_name == "metric":
                if status.suggestions:
                    auto_value = status.suggestions[0]
                    auto_reason = "Metric auto-selected from suggestions"
            elif slot_name == "comparison" and status.suggestions:
                auto_value = status.suggestions[0]
                auto_reason = "Comparison auto-selected from suggestions"

        if auto_value is not None:
            resolved_status = "assumed" if auto_reason and "assumption" in auto_reason.lower() else "defaulted"
            _upsert_slot_status(
                ctx,
                slot_name,
                status=resolved_status,
                value=auto_value,
                reason=auto_reason,
                suggestions=list(status.suggestions or []),
                allow_custom=status.allow_custom,
            )
            if auto_reason:
                assumptions.append(f"Using {slot_label}: {auto_value}")
            if intent and isinstance(getattr(intent, "slots_detected", None), dict):
                intent.slots_detected[slot_name] = auto_value
            auto_answers.append(
                ClarifyAnswerModel(
                    value=auto_value,
                    request_id=f"auto-{slot_name}",
                    slot=slot_name,
                    session_id=session_id,
                    ts=datetime.utcnow().isoformat(),
                )
            )
            continue

        remaining_missing.append(slot_name)

    return remaining_missing, auto_answers


async def run_clarification_stage(
    pipeline: Any, ctx: Any
) -> AsyncGenerator[Dict[str, Any], None]:
    """
    Run the clarification stage with slot resolution, blocking/non-blocking handling,
    answer validation, auto-fill, and artifact capture.
    """
    from analytics.core.intent_impl.models import SlotStatusModel

    session_id = getattr(ctx, "session_id", None) or str(uuid.uuid4())
    if not getattr(ctx, "session_id", None):
        ctx.session_id = session_id

    timed_emitter = getattr(ctx, "timed_emitter", None)
    intent = getattr(ctx, "intent", None)
    provisional_plan = getattr(ctx, "provisional_plan", None) or getattr(ctx, "plan", None)
    template = getattr(ctx, "template", None)

    official_clarifications = list(getattr(ctx, "clarifications", []) or [])
    assumptions = list(getattr(ctx, "assumptions", []) or [])
    clar_answers: List[Dict[str, Any]] = list(getattr(ctx, "clarification_answers", []) or [])

    rounds = getattr(ctx, "clarification_rounds", 0) or 0
    blocking_mode = bool(getattr(ctx, "blocking_clarification", False))
    timeout_seconds = float(getattr(ctx, "clarification_timeout_seconds", 60.0) or 60.0)

    answered_slots: set[str] = set()
    for slot_name, status in (ctx.slot_statuses or {}).items():
        if isinstance(status, SlotStatusModel) and status.status != "missing":
            answered_slots.add(slot_name)
    for answer in clar_answers:
        if isinstance(answer, Mapping) and isinstance(answer.get("slot"), str):
            answered_slots.add(answer["slot"])
        elif isinstance(answer, str):
            answered_slots.add(answer)

    official_clarifications = _filter_answered_requests(official_clarifications, answered_slots)
    ctx.clarifications = list(official_clarifications)
    ctx.clarifications_needed = bool(official_clarifications)
    all_answered_slots: set[str] = set(answered_slots)
    history_entries: List[Dict[str, Any]] = []
    _refresh_followups(ctx, official_clarifications)

    if official_clarifications:
        if timed_emitter:
            timed_emitter.start_step("clarification")
        missing_slots = [req.slot for req in official_clarifications]
        yield {
            "event": "clarification_needed",
            "data": {
                "missing_fields": missing_slots,
                "ts": datetime.utcnow().isoformat(),
            },
        }
        clarification_progress = EventEmitter.progress(
            "clarification", "Clarifying requirements..."
        )
        clarification_progress["data"]["ts"] = datetime.utcnow().isoformat()
        yield clarification_progress
        yield {
            "event": "clarification_loop_start",
            "data": {
                "total_clarifications": len(official_clarifications),
                "missing_slots": missing_slots,
                "ts": datetime.utcnow().isoformat(),
            },
        }
        while official_clarifications and rounds < 3:
            slot_request = official_clarifications[0]
            request_payload = {
                "request_id": slot_request.request_id,
                "slot": slot_request.slot,
                "question": slot_request.question,
                "type": slot_request.type,
                "options": slot_request.options,
                "default": slot_request.default,
                "proposed": slot_request.proposed,
                "proposed_confidence": slot_request.proposed_confidence,
                "reason": slot_request.reason,
                "required": slot_request.required,
                "round": rounds + 1,
                "remaining": len(official_clarifications),
            }
            clarification_event = EventEmitter.clarification_request(
                session_id, request_payload
            )
            clarification_event["data"]["ts"] = datetime.utcnow().isoformat()
            yield clarification_event
            history_entry: Dict[str, Any] = {"request": dict(request_payload)}
            try:
                answer = await asyncio.wait_for(
                    wait_for_answer_blocking(session_id, slot_request.request_id),
                    timeout=timeout_seconds,
                )
            except asyncio.TimeoutError:
                if blocking_mode:
                    timeout_payload = {
                        "session_id": session_id,
                        "request_id": slot_request.request_id,
                        "slot": slot_request.slot,
                        "ts": datetime.utcnow().isoformat(),
                    }
                    follow_up_route = getattr(ctx, "follow_up_route", None)
                    if follow_up_route is not None:
                        timeout_payload["follow_up_route"] = getattr(follow_up_route, "value", None)
                    timeout_event = EventEmitter.error(
                        "workflow_error",
                        f"Timeout waiting for {slot_request.slot} clarification.",
                        details=timeout_payload,
                        code="clarification_timeout",
                    )
                    timeout_event["event"] = "workflow_error"
                    timeout_event.setdefault("data", {}).update(timeout_payload)
                    timeout_event["data"]["error_code"] = "clarification_timeout"
                    yield timeout_event
                    ctx.halted = True
                    ctx.halt_reason = "clarification_timeout"
                    ctx.clarifications_needed = True
                    return
                timeout_event = EventEmitter.progress(
                    "clarification_timeout",
                    f"Timeout waiting for {slot_request.slot} clarification. Using default value.",
                )
                timeout_event["data"]["ts"] = datetime.utcnow().isoformat()
                yield timeout_event
                if slot_request.default:
                    answer = ClarifyAnswerModel(
                        session_id=session_id,
                        request_id=slot_request.request_id,
                        slot=slot_request.slot,
                        value=slot_request.default,
                        ts=datetime.utcnow().isoformat(),
                    )
                else:
                    official_clarifications.pop(0)
                    history_entry["response"] = {
                        "status": "timeout_no_value",
                        "slot": slot_request.slot,
                    }
                    _upsert_slot_status(
                        ctx,
                        slot_request.slot,
                        status="missing",
                        value=None,
                        reason=slot_request.reason,
                        suggestions=slot_request.options,
                        allow_custom=_request_allows_custom(slot_request),
                    )
                    _refresh_followups(ctx, official_clarifications)
                    history_entries.append(history_entry)
                    continue
            if answer:
                is_valid = validate_clarification_answer(answer, slot_request)
                if is_valid:
                    ack_event = EventEmitter.clarification_ack(
                        session_id, slot_request.request_id, answer.value
                    )
                    ack_event["data"].update(
                        {
                            "slot": slot_request.slot,
                            "ts": datetime.utcnow().isoformat(),
                        }
                    )
                    slot_status = _upsert_slot_status(
                        ctx,
                        slot_request.slot,
                        status="filled",
                        value=answer.value,
                        reason=slot_request.reason,
                        suggestions=slot_request.options,
                        allow_custom=_request_allows_custom(slot_request),
                    )
                    ack_event["data"]["slot_status"] = slot_status.model_dump()
                    yield ack_event
                    intent, provisional_plan, merge_assumptions = await merge_answers(
                        intent, provisional_plan, [answer], CONFIGS.__dict__
                    )
                    assumptions.extend(merge_assumptions)
                    history_entry["response"] = {
                        "status": "accepted",
                        "slot": answer.slot,
                        "value": answer.value,
                    }
                    clar_answers.append(
                        {
                            "slot": answer.slot,
                            "value": answer.value,
                            "request_id": slot_request.request_id,
                            "ts": answer.ts or datetime.utcnow().isoformat(),
                        }
                    )
                    template = choose_template(
                        intent, provisional_plan, CONFIGS.__dict__
                    )
                    new_clarifications = compute_required_clarifications(
                        intent, provisional_plan, template, CONFIGS.__dict__
                    )
                    remaining_original = official_clarifications[1:]
                    all_answered_slots.add(answer.slot)
                    combined_requests: List[ClarifyRequestModel] = []
                    for new_req in new_clarifications:
                        if new_req.slot not in all_answered_slots and all(
                            new_req.slot != existing.slot for existing in combined_requests
                        ):
                            combined_requests.append(new_req)
                    for orig_req in remaining_original:
                        if (
                            orig_req.slot not in all_answered_slots
                            and all(orig_req.slot != existing.slot for existing in combined_requests)
                        ):
                            combined_requests.append(orig_req)
                    official_clarifications = combined_requests
                    _refresh_followups(ctx, official_clarifications)
                    rounds += 1
                else:
                    error_message = get_validation_error_message(answer, slot_request)
                    error_event = EventEmitter.progress(
                        "clarification_error",
                        error_message or f"Invalid value for {slot_request.slot}: {answer.value}",
                    )
                    error_event["data"]["ts"] = datetime.utcnow().isoformat()
                    yield error_event
                    official_clarifications = official_clarifications[1:]
                    _upsert_slot_status(
                        ctx,
                        slot_request.slot,
                        status="missing",
                        value=None,
                        reason=error_message or slot_request.reason,
                        suggestions=slot_request.options,
                        allow_custom=_request_allows_custom(slot_request),
                    )
                    _refresh_followups(ctx, official_clarifications)
                    history_entry["response"] = {
                        "status": "rejected",
                        "slot": answer.slot,
                        "value": answer.value,
                        "error": error_message,
                    }
            else:
                official_clarifications = official_clarifications[1:]
                history_entry["response"] = {
                    "status": "no_answer",
                    "slot": slot_request.slot,
                }
                _upsert_slot_status(
                    ctx,
                    slot_request.slot,
                    status="missing",
                    value=None,
                    reason=slot_request.reason,
                    suggestions=slot_request.options,
                    allow_custom=_request_allows_custom(slot_request),
                )
                _refresh_followups(ctx, official_clarifications)
            if history_entry not in history_entries:
                history_entries.append(history_entry)
        clarification_elapsed = timed_emitter.end_step("clarification") if timed_emitter else None
        resolved_event = EventEmitter.intent_resolved(
            key=intent.intent_key,
            confidence=intent.confidence,
            rounds=rounds,
        )
        resolved_event["data"].update(
            {
                "assumptions": assumptions,
                "ts": datetime.utcnow().isoformat(),
            }
        )
        if clarification_elapsed:
            resolved_event["data"]["elapsed_ms"] = clarification_elapsed
        yield resolved_event
        pending_slots = sorted(
            {req.slot for req in official_clarifications if getattr(req, "slot", None)}
        )
        yield {
            "event": "clarification_complete",
            "data": {
                "rounds": rounds,
                "missing_slots": pending_slots,
                "ts": datetime.utcnow().isoformat(),
            },
        }
    else:
        yield {
            "event": "clarification_skipped",
            "data": {
                "reason": "All required slots satisfied",
                "ts": datetime.utcnow().isoformat(),
            },
        }

    ctx.intent = intent
    ctx.provisional_plan = provisional_plan
    ctx.template = template
    ctx.assumptions = assumptions
    ctx.clarifications_needed = bool(official_clarifications)
    ctx.clarification_rounds = rounds
    ctx.clarifications = official_clarifications

    if blocking_mode:
        remaining_missing, auto_answers = [], []
    else:
        remaining_missing, auto_answers = _auto_fill_missing_slots(ctx, assumptions)
    if auto_answers:
        clar_answers.extend([answer.model_dump(exclude_none=True) for answer in auto_answers])
    ctx.clarification_answers = clar_answers
    if remaining_missing:
        regenerated_requests: List[ClarifyRequestModel] = []
        for slot_name in remaining_missing:
            status_model = ctx.slot_statuses.get(slot_name)
            suggestions = list(status_model.suggestions or []) if status_model else []
            allow_custom = True
            if status_model and status_model.allow_custom is not None:
                allow_custom = status_model.allow_custom
            elif suggestions:
                allow_custom = False
            input_type = "single" if suggestions and not allow_custom else "free"
            default_option = suggestions[0] if suggestions and not allow_custom else None
            question_text = (
                status_model.reason
                if status_model and status_model.reason and status_model.reason.endswith("?")
                else f"Which {slot_name.replace('_', ' ')} should we use?"
            )
            regenerated_requests.append(
                ClarifyRequestModel(
                    slot=slot_name,
                    question=question_text,
                    type=input_type,
                    options=suggestions,
                    default=default_option,
                    reason=(
                        status_model.reason
                        if status_model and status_model.reason
                        else "This slot is required to continue the analysis."
                    ),
                    required=True,
                    request_id=str(uuid.uuid4()),
                    proposed=(
                        status_model.value
                        if status_model
                        and status_model.value is not None
                        and status_model.status in {"assumed", "defaulted"}
                        else None
                    ),
                    proposed_confidence=None,
                    session_id=ctx.session_id,
                )
            )
        ctx.clarifications = regenerated_requests
        _refresh_followups(ctx, regenerated_requests)
        ctx.halted = True
        ctx.halt_reason = "clarification_missing_slots"
        halt_event = EventEmitter.error(
            "clarification",
            "Missing required information to continue.",
            details={"missing_slots": remaining_missing},
            code="SLOTS_MISSING",
        )
        halt_event["data"]["ts"] = datetime.utcnow().isoformat()
        yield halt_event
        workflow_summary = {
            "status": "clarification_missing_slots",
            "missing_slots": remaining_missing,
            "total_elapsed_ms": int((time.time() - ctx.workflow_start) * 1000),
        }
        workflow_complete = EventEmitter.result("workflow_complete", workflow_summary)
        workflow_complete["event"] = "workflow_complete"
        workflow_complete["data"]["ts"] = datetime.utcnow().isoformat()
        yield workflow_complete
        yield {
            "event": "clarification_failed",
            "data": {
                "rounds": rounds,
                "missing_slots": remaining_missing,
                "ts": datetime.utcnow().isoformat(),
            },
        }
        decision = getattr(ctx, "schema_clarifier_decision", None)
        clarifier_action = None
        clarifier_missing = []
        clarifier_slot = None
        if decision is not None:
            clarifier_action = getattr(decision, "action", None)
            clarifier_missing = list(getattr(decision, "missing_slots", []) or [])
            clarifier_slot = getattr(decision, "slot", None)
        else:
            clarifier_action = "request"
        ctx.artifacts.clarification = ClarificationArtifact(
            query=ctx.query,
            clarifier_action=clarifier_action,
            clarifier_missing_slots=clarifier_missing,
            clarifier_slot=clarifier_slot,
            pending=[req.model_dump() for req in regenerated_requests],
            assumptions=list(assumptions),
            resolved=False,
            rounds=rounds,
            answered_slots=sorted(all_answered_slots),
            history=history_entries,
        )
        capture = getattr(pipeline, "_capture_artifacts", None)
        if callable(capture):
            capture(ctx)
        return

    if not official_clarifications:
        _refresh_followups(ctx, [])
    decision = getattr(ctx, "schema_clarifier_decision", None)
    clarifier_action = None
    clarifier_missing = []
    clarifier_slot = None
    if decision is not None:
        clarifier_action = getattr(decision, "action", None)
        clarifier_missing = list(getattr(decision, "missing_slots", []) or [])
        clarifier_slot = getattr(decision, "slot", None)
    elif official_clarifications:
        clarifier_action = "request"
    else:
        clarifier_action = "not_required"
    ctx.artifacts.clarification = ClarificationArtifact(
        query=ctx.query,
        clarifier_action=clarifier_action,
        clarifier_missing_slots=clarifier_missing,
        clarifier_slot=clarifier_slot,
        pending=[req.model_dump() for req in official_clarifications],
        assumptions=list(assumptions),
        resolved=not official_clarifications,
        rounds=rounds,
        answered_slots=sorted(all_answered_slots),
        history=history_entries,
    )
    capture = getattr(pipeline, "_capture_artifacts", None)
    if callable(capture):
        capture(ctx)
