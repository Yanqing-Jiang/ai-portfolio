from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Iterable, List, Mapping, Optional, Set, Tuple

from pydantic import BaseModel, Field

from ..core.intent import IntentModel
from ..core.state import QueryPlanModel
from ..sql.template_requirements import get_required_slots, requirements_satisfied
from ..core.config import CONFIGS
from ..core.intent_impl.models import SlotStatusModel

try:
    from unified_responses_client import get_unified_client  # type: ignore
except ImportError:  # pragma: no cover
    get_unified_client = None  # type: ignore

_DECISION_CACHE: Set[Tuple[str, str]] = set()

_DEFAULT_QUESTIONS: Dict[str, Dict[str, Any]] = {
    "company": {
        "question": "Which company should we analyze?",
        "reason": "This template requires a specific company (ticker).",
    },
    "timeframe.start_year": {
        "question": "Which fiscal year should we evaluate?",
        "reason": "A specific year is required to rank R&D spending.",
    },
}

SCHEMA_CLARIFIER_SYSTEM_PROMPT = (
    "You validate structured analytics inputs for the planner. Reply with JSON fields action, slot, question, reason, options.\n"
    "- action must be one of skip, clarify, assume, or decline.\n"
    "- Choose decline when cached receipts or user inputs cannot satisfy the request and upstream lanes must rerun; set reason to an actionable value such as \"insufficient_inputs\".\n"
    "- When cached receipts already satisfy a missing slot, choose skip so the session can reuse cached data.\n"
    "- Keep question under 25 words when clarifying and make it specific to the template.\n"
    "- Use slot identifiers provided in required_slots.\n"
    "- Provide options only when you can list safe defaults; otherwise return an empty list.\n"
)


@dataclass
class ClarifierDecision:
    action: str
    missing_slots: List[str] = field(default_factory=list)
    slot: Optional[str] = None
    question: Optional[str] = None
    reason: Optional[str] = None
    options: List[str] = field(default_factory=list)


class ClarifierAgentResponse(BaseModel):
    action: str = Field(..., description="Action to take: skip, clarify, assume, or decline")
    slot: Optional[str] = Field(default=None)
    question: Optional[str] = Field(default=None)
    reason: Optional[str] = Field(default=None)
    options: List[str] = Field(default_factory=list)


def decide_schema_clarification(
    intent: IntentModel,
    plan: QueryPlanModel,
    *,
    session_id: Optional[str] = None,
    template_id: Optional[str] = None,
    model: str = "gpt-5-mini-2025-08-07",
    reasoning_effort: str = "low",
    slot_statuses: Optional[Mapping[str, SlotStatusModel]] = None,
) -> ClarifierDecision:
    required_slots = get_required_slots(intent.intent_key)
    satisfied, missing = requirements_satisfied(
        intent,
        plan,
        required_slots,
        slot_statuses=slot_statuses,
    )
    if satisfied:
        return ClarifierDecision(action="skip", missing_slots=[])

    if session_id and template_id:
        cache_key = (session_id, template_id)
        if cache_key in _DECISION_CACHE:
            return _fallback_decision(missing)
        _DECISION_CACHE.add(cache_key)

    if not missing:
        return ClarifierDecision(action="skip", missing_slots=[])

    primary_spec = missing[0]

    agent_response = _run_agent(intent, plan, missing, model=model, reasoning_effort=reasoning_effort)
    if agent_response is None:
        return _fallback_decision(missing)

    action = agent_response.action.lower().strip()
    if action not in {"skip", "clarify", "assume", "decline"}:
        return _fallback_decision(missing)

    if action in {"skip", "assume"}:
        return ClarifierDecision(action="skip", missing_slots=missing)
    if action == "decline":
        return ClarifierDecision(
            action="decline",
            missing_slots=missing,
            slot=_map_slot_spec_to_request(agent_response.slot or primary_spec),
            reason=agent_response.reason or "insufficient_inputs",
            options=list(agent_response.options or []),
        )

    slot_spec = agent_response.slot or primary_spec
    request_slot = _map_slot_spec_to_request(slot_spec)
    question = agent_response.question or _default_question(slot_spec)
    reason = agent_response.reason or _default_reason(slot_spec)
    options = agent_response.options or _default_options(slot_spec)

    return ClarifierDecision(
        action="clarify",
        missing_slots=missing,
        slot=request_slot,
        question=question,
        reason=reason,
        options=options,
    )


def _run_agent(
    intent: IntentModel,
    plan: QueryPlanModel,
    missing: List[str],
    *,
    model: str,
    reasoning_effort: str,
) -> Optional[ClarifierAgentResponse]:
    if get_unified_client is None:
        return None
    try:
        client = get_unified_client()
    except Exception:
        return None

    payload = {
        "intent_key": intent.intent_key,
        "required_slots": missing,
        "provided_slots": intent.slots_detected,
        "plan": plan.model_dump(mode="json"),
    }

    system_prompt = SCHEMA_CLARIFIER_SYSTEM_PROMPT

    user_prompt = (
        "Intent data:\n"
        f"{json.dumps(payload, ensure_ascii=False, indent=2)}\n\n"
        "Decide whether clarification is required."
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    try:
        response, _ = client.create_structured(
            response_model=ClarifierAgentResponse,
            messages=messages,
            model=model,
            reasoning_effort=reasoning_effort,
        )
        return response
    except Exception:
        return None


def _fallback_decision(missing: List[str]) -> ClarifierDecision:
    slot_spec = missing[0] if missing else None
    return ClarifierDecision(
        action="fallback",
        missing_slots=missing,
        slot=_map_slot_spec_to_request(slot_spec) if slot_spec else None,
        question=_default_question(slot_spec) if slot_spec else None,
        reason=_default_reason(slot_spec) if slot_spec else None,
        options=_default_options(slot_spec) if slot_spec else [],
    )


def _default_question(slot_spec: Optional[str]) -> Optional[str]:
    if not slot_spec:
        return None
    meta = _DEFAULT_QUESTIONS.get(slot_spec)
    if meta and meta.get("question"):
        return meta["question"]
    return f"Provide a value for {slot_spec}."


def _default_reason(slot_spec: Optional[str]) -> Optional[str]:
    if not slot_spec:
        return None
    meta = _DEFAULT_QUESTIONS.get(slot_spec)
    if meta and meta.get("reason"):
        return meta["reason"]
    return "Required by the selected analytics template."


def _default_options(slot_spec: Optional[str]) -> List[str]:
    if slot_spec == "company":
        companies_cfg = CONFIGS.companies.get("selection_rules", {}).get("default_companies", {})
        options = companies_cfg.get("tickers", ["NVDA", "AMD", "INTC"])
        return list(options)
    if slot_spec == "timeframe.start_year":
        current_year = datetime.utcnow().year
        defaults = CONFIGS.metrics.get("semantic", {}).get("query_defaults", {})
        years_back = defaults.get("default_years_back", 5)
        years = [str(current_year - offset) for offset in range(0, years_back + 1)]
        return years[:6]
    return []


def _map_slot_spec_to_request(slot_spec: Optional[str]) -> Optional[str]:
    if slot_spec is None:
        return None
    if slot_spec.startswith("timeframe."):
        return "timeframe"
    return slot_spec
