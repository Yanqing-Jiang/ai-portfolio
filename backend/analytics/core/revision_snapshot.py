# --- Analytics Function/Class Map ---
# Function: build_intent_signature
#   Role: Handles build intent signature logic for analytics.core.revision_snapshot.
#   Called from: analytics.flows.planner_executor
#   Invokes: analytics.validators.sanitize_for_json, analytics.core.revision_snapshot._timeframe_to_dict
#   Why: Keeps analytics.core.revision_snapshot from duplicating build intent signature behavior across flows.
# Function: extract_revision_snapshot
#   Role: Handles extract revision snapshot logic for analytics.core.revision_snapshot.
#   Called from: analytics.flows.multi_agent, analytics.flows.planner_executor
#   Invokes: Internal helpers only
#   Why: Keeps analytics.core.revision_snapshot from duplicating extract revision snapshot behavior across flows.
# Function: signatures_equal
#   Role: Handles signatures equal logic for analytics.core.revision_snapshot.
#   Called from: analytics.flows.planner_executor
#   Invokes: analytics.core.revision_snapshot._canonicalize
#   Why: Keeps analytics.core.revision_snapshot from duplicating signatures equal behavior across flows.
# Function: _canonicalize
#   Role: Handles canonicalize logic for analytics.core.revision_snapshot.
#   Called from: Internal to analytics.core.revision_snapshot
#   Invokes: analytics.validators.sanitize_for_json, json.dumps
#   Why: Keeps analytics.core.revision_snapshot from duplicating canonicalize behavior across flows.
# Function: _timeframe_to_dict
#   Role: Handles timeframe to dict logic for analytics.core.revision_snapshot.
#   Called from: Internal to analytics.core.revision_snapshot
#   Invokes: Internal helpers only
#   Why: Keeps analytics.core.revision_snapshot from duplicating timeframe to dict behavior across flows.
# --- End Analytics Function/Class Map ---
from __future__ import annotations

import json
from typing import Any, Dict, Optional

from analytics.core.state import IntentModel, QueryPlanModel, TimeframeModel
from analytics.core.session_state import SessionStateSnapshot
from analytics.validators import sanitize_for_json

SIGNATURE_SLOT_KEYS = {
    "ticker",
    "tickers",
    "company",
    "companies",
    "peer_scope",
    "peer_group",
    "scope",
    "metric",
    "metrics",
    "comparison",
    "granularity",
    "statistic",
}


def build_intent_signature(
    intent: Optional[IntentModel],
    plan: Optional[QueryPlanModel],
) -> Optional[Dict[str, Any]]:
    if intent is None and plan is None:
        return None

    signature: Dict[str, Any] = {}
    if intent:
        if intent.intent_key:
            signature["intent_key"] = intent.intent_key
        slots_detected = {}
        raw_slots = intent.slots_detected or {}
        for key in SIGNATURE_SLOT_KEYS:
            value = raw_slots.get(key)
            if value is not None:
                slots_detected[key] = value
        if slots_detected:
            signature["slots"] = slots_detected

    if plan:
        plan_payload: Dict[str, Any] = {
            "granularity": getattr(plan, "granularity", None),
            "comparison": getattr(plan, "comparison", None),
            "metrics": list(getattr(plan, "metrics", []) or []),
            "derived_metrics": list(getattr(plan, "derived_metrics", []) or []),
            "group_by": list(getattr(plan, "group_by", []) or []),
        }
        timeframe = _timeframe_to_dict(plan.timeframe)
        if timeframe:
            plan_payload["timeframe"] = timeframe
        raw_filters = getattr(plan, "filters", None)
        filters = sanitize_for_json(raw_filters or {}) if raw_filters else {}
        if filters:
            plan_payload["filters"] = filters
        plan_payload = {key: value for key, value in plan_payload.items() if value not in (None, [], {}, "")}
        if plan_payload:
            signature["plan"] = plan_payload

    sanitized = sanitize_for_json(signature)
    return sanitized if sanitized else None


def extract_revision_snapshot(snapshot: Optional[SessionStateSnapshot]) -> Optional[Dict[str, Any]]:
    if snapshot is None or not hasattr(snapshot, "tool_cache"):
        return None
    analytics_cache = snapshot.tool_cache.get("analytics", {}) or {}
    payload = analytics_cache.get("revision_snapshot")
    if isinstance(payload, dict):
        return payload
    return None


def signatures_equal(first: Optional[Dict[str, Any]], second: Optional[Dict[str, Any]]) -> bool:
    return _canonicalize(first) == _canonicalize(second)


def _canonicalize(value: Optional[Dict[str, Any]]) -> Optional[str]:
    if value is None:
        return None
    sanitized = sanitize_for_json(value)
    try:
        return json.dumps(sanitized, sort_keys=True, separators=(",", ":"))
    except TypeError:
        return str(sanitized)


def _timeframe_to_dict(timeframe: Optional[TimeframeModel]) -> Dict[str, Any]:
    if timeframe is None:
        return {}
    payload: Dict[str, Any] = {}
    years_back = getattr(timeframe, "years_back", None)
    if years_back is not None:
        payload["years_back"] = years_back
    start_year = getattr(timeframe, "start_year", None)
    if start_year is not None:
        payload["start_year"] = start_year
    end_year = getattr(timeframe, "end_year", None)
    if end_year is not None:
        payload["end_year"] = end_year
    return payload
