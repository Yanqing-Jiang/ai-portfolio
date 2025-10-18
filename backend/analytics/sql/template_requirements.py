from __future__ import annotations

from typing import Any, Dict, Iterable, List, Mapping, Optional, Tuple

from ..core.intent import IntentModel
from ..core.state import QueryPlanModel, TimeframeModel
from ..core.config import CONFIGS
from ..core.intent_impl.models import SlotStatusModel

_REQUIREMENTS_CACHE: Dict[str, List[str]] = {}


def get_required_slots(intent_key: Optional[str]) -> List[str]:
    """Return the list of required slots for a given intent."""
    if not intent_key:
        return []
    if intent_key in _REQUIREMENTS_CACHE:
        return _REQUIREMENTS_CACHE[intent_key]

    raw = CONFIGS.query_requirements.get("required_slots", {}) if isinstance(CONFIGS.query_requirements, dict) else {}
    slots: Iterable[Any] = raw.get(intent_key, []) if isinstance(raw, dict) else []
    normalised = [str(slot).strip() for slot in slots if slot]
    _REQUIREMENTS_CACHE[intent_key] = normalised
    return normalised


def requirements_satisfied(
    intent: IntentModel,
    plan: Optional[QueryPlanModel],
    required_slots: Optional[Iterable[str]] = None,
    slot_statuses: Optional[Mapping[str, SlotStatusModel]] = None,
) -> Tuple[bool, List[str]]:
    """Check whether the required slots are satisfied for the given intent/plan."""
    required = list(required_slots) if required_slots is not None else get_required_slots(intent.intent_key)
    if not required:
        return True, []

    slots = intent.slots_detected or {}
    plan = plan or QueryPlanModel()
    missing: List[str] = []

    for slot_key in required:
        if _is_slot_filled(slot_key, slots, plan, slot_statuses):
            continue
        missing.append(slot_key)

    return len(missing) == 0, missing


def _is_slot_filled(
    slot_key: str,
    slots: Dict[str, Any],
    plan: QueryPlanModel,
    slot_statuses: Optional[Mapping[str, SlotStatusModel]],
) -> bool:
    """Return True if the slot identified by ``slot_key`` is satisfied."""
    status_model = _get_slot_status(slot_key, slot_statuses)
    if status_model is not None:
        if status_model.status == "missing":
            return False
        if status_model.status in {"filled", "defaulted", "assumed"}:
            if status_model.value not in (None, "", [], {}):
                return True
            # Defaulted/assumed slots may omit a concrete value; treat them as satisfied unless explicitly missing.
            if status_model.status in {"defaulted", "assumed"}:
                return True
            # Fall through for filled-but-empty values so legacy heuristics can double-check.
    if slot_key == "company":
        return _has_company(slots, slot_statuses)
    if slot_key == "comparison":
        comparison = slots.get("comparison") or getattr(plan, "comparison", None)
        return isinstance(comparison, str) and comparison.strip() != ""
    if slot_key.startswith("timeframe."):
        _, field = slot_key.split(".", 1)
        value = _get_timeframe_field(slots.get("timeframe"), field)
        if value is None:
            value = _get_timeframe_field(getattr(plan, "timeframe", None), field)
        return value is not None
    if slot_key == "timeframe":
        timeframe = slots.get("timeframe")
        value = _get_timeframe_field(timeframe, "years_back") or _get_timeframe_field(timeframe, "start_year")
        if value is None and getattr(plan, "timeframe", None) is not None:
            plan_tf = getattr(plan, "timeframe")
            value = _get_timeframe_field(plan_tf, "years_back") or _get_timeframe_field(plan_tf, "start_year")
        return value is not None

    value = slots.get(slot_key)
    if value in (None, "", [], {}):
        plan_attr = getattr(plan, slot_key, None)
        value = plan_attr if value in (None, "", [], {}) else value
    return value not in (None, "", [], {})


def _has_company(slots: Dict[str, Any], slot_statuses: Optional[Mapping[str, SlotStatusModel]]) -> bool:
    """Return True when we have a single, concrete company selection."""
    status_model = _get_slot_status("company", slot_statuses)
    if status_model is not None:
        if status_model.status == "missing":
            return False
        if status_model.status in {"filled", "defaulted", "assumed"}:
            if status_model.value not in (None, "", [], {}):
                return True
            if status_model.status in {"defaulted", "assumed"}:
                return True
    return _company_from_slots(slots) is not None


def _company_from_slots(slots: Dict[str, Any]) -> Optional[str]:
    company = slots.get("company")
    if isinstance(company, str) and company.strip():
        return company.strip()

    def _clean(symbols: Any) -> List[str]:
        if not isinstance(symbols, list):
            return []
        cleaned: List[str] = []
        for symbol in symbols:
            if isinstance(symbol, str):
                normalized = symbol.strip().upper()
                if normalized:
                    cleaned.append(normalized)
        return cleaned

    tickers = _clean(slots.get("tickers"))
    if len(tickers) == 1:
        return tickers[0]

    candidates = _clean(slots.get("company_candidates"))
    if len(candidates) == 1:
        return candidates[0]

    return None


def _get_slot_status(
    slot_key: str, slot_statuses: Optional[Mapping[str, SlotStatusModel]]
) -> Optional[SlotStatusModel]:
    if not slot_statuses:
        return None
    status = slot_statuses.get(slot_key)
    if status is None and slot_key.startswith("timeframe."):
        status = slot_statuses.get("timeframe")
    return status if isinstance(status, SlotStatusModel) else None


def _get_timeframe_field(timeframe: Any, field: str) -> Optional[Any]:
    if timeframe is None:
        return None
    if isinstance(timeframe, TimeframeModel):
        return getattr(timeframe, field, None)
    if isinstance(timeframe, dict):
        return timeframe.get(field)
    if hasattr(timeframe, field):
        return getattr(timeframe, field)
    return None
