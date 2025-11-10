# --- Analytics Function/Class Map ---
# Function: _normalize_timestamp
#   Role: Normalize ISO-8601 timestamps (including trailing Z) into aware datetime objects.
#   Called from: analytics.accessory_receipts._compute_age_seconds
#   Invokes: datetime.fromisoformat
#   Why: Ensures accessory receipt helpers share consistent timestamp parsing.
# Function: _resolve_receipt
#   Role: Resolve the most relevant tool receipt for a given lane based on LANE_TOOL_MAP hints.
#   Called from: analytics.accessory_receipts.enrich_accessory_payload, analytics.accessory_receipts.build_lane_reuse_event
#   Invokes: analytics.accessory_receipts._candidate_tools
#   Why: Keeps lane metadata wiring centralized instead of duplicating lookup logic across flows.
# Function: enrich_accessory_payload
#   Role: Inject cached receipt metadata (age, guardrails, fast-path latency) into artifact payloads.
#   Called from: analytics.flows.multi_agent._queue_artifact_event
#   Invokes: analytics.accessory_receipts._resolve_receipt, analytics.accessory_receipts._compute_age_seconds
#   Why: Ensures reused-lane payloads surface determinant evidence for UI/telemetry consumers.
# Function: build_lane_reuse_event
#   Role: Build a canonical lane_reused event (with metadata) for accessory reuse.
#   Called from: analytics.flows.multi_agent._queue_artifact_event
#   Invokes: analytics.accessory_receipts.enrich_accessory_payload
#   Why: Guarantees lane reuse ordering and telemetry parity when PlannerSequencer is bypassed.
# --- End Analytics Function/Class Map ---
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Mapping, Optional, Sequence

from analytics.flows.sequencer import LANE_TOOL_MAP
from analytics.validators import sanitize_for_json


def _normalize_timestamp(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    text = str(value).strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def _candidate_tools(lane: str) -> Sequence[str]:
    lane_key = (lane or "").strip().lower()
    if not lane_key:
        return ()
    candidates = list(LANE_TOOL_MAP.get(lane_key, ()))
    if lane_key == "web":
        candidates.extend(["web_retriever_cached", "web_retriever_live", "web_search"])
    elif lane_key == "market":
        candidates.extend(["market_snapshot", "market_refresh"])
    return tuple(dict.fromkeys(candidates))


def _resolve_receipt(lane: str, receipts: Mapping[str, Any]) -> Optional[Mapping[str, Any]]:
    lane_key = (lane or "").strip().lower()
    if not lane_key or not receipts:
        return None
    for tool_name in _candidate_tools(lane_key):
        receipt = receipts.get(tool_name)
        if isinstance(receipt, Mapping):
            return receipt
        for candidate_key, candidate_value in receipts.items():
            if (
                isinstance(candidate_key, str)
                and candidate_key.lower().startswith(tool_name.lower())
                and isinstance(candidate_value, Mapping)
            ):
                return candidate_value
    return None


def _compute_age_seconds(receipt: Mapping[str, Any]) -> Optional[int]:
    timestamp = (
        receipt.get("timestamp")
        or receipt.get("recorded_at")
        or receipt.get("completed_at")
    )
    reuse_meta = receipt.get("reuse_metadata")
    if not timestamp and isinstance(reuse_meta, Mapping):
        timestamp = reuse_meta.get("ts")
    parsed = _normalize_timestamp(timestamp)
    if parsed is None:
        return None
    delta = datetime.now(timezone.utc) - parsed
    try:
        return max(int(delta.total_seconds()), 0)
    except OverflowError:
        return None


def _resolve_fast_path_latency(receipt: Mapping[str, Any]) -> Optional[int]:
    candidates = [
        receipt.get("fast_path_latency_ms"),
        receipt.get("latency_ms"),
        receipt.get("elapsed_ms"),
        receipt.get("reused_at_ms"),
    ]
    reuse_meta = receipt.get("reuse_metadata")
    if isinstance(reuse_meta, Mapping):
        candidates.extend(
            [
                reuse_meta.get("fast_path_latency_ms"),
                reuse_meta.get("latency_ms"),
                reuse_meta.get("elapsed_ms"),
                reuse_meta.get("reused_at_ms"),
            ]
        )
    for candidate in candidates:
        if isinstance(candidate, (int, float)):
            return int(candidate)
    return None


def _resolve_guardrail(receipt: Mapping[str, Any]) -> Optional[Mapping[str, Any]]:
    guardrail = receipt.get("latency_guardrail") or receipt.get("guardrail")
    if not guardrail:
        reuse_meta = receipt.get("reuse_metadata")
        if isinstance(reuse_meta, Mapping):
            guardrail = reuse_meta.get("guardrail")
    if guardrail is None:
        return None
    return sanitize_for_json(guardrail)


def enrich_accessory_payload(
    lane: str,
    payload: Dict[str, Any],
    *,
    receipts: Mapping[str, Any],
) -> Dict[str, Any]:
    """
    Mutate payload with metadata derived from cached receipts (age, guardrails, latency).
    Returns a shallow metadata dict for callers that also need the enriched values.
    """
    metadata: Dict[str, Any] = {}
    receipt = _resolve_receipt(lane, receipts)
    if not receipt:
        return metadata

    age_seconds = _compute_age_seconds(receipt)
    if age_seconds is not None and payload.get("age_seconds") is None:
        payload["age_seconds"] = age_seconds
    if age_seconds is not None:
        metadata["age_seconds"] = age_seconds

    fast_path_latency = _resolve_fast_path_latency(receipt)
    if fast_path_latency is not None and payload.get("fast_path_latency_ms") is None:
        payload["fast_path_latency_ms"] = fast_path_latency
    if fast_path_latency is not None:
        metadata["fast_path_latency_ms"] = fast_path_latency

    guardrail = _resolve_guardrail(receipt)
    if guardrail and not payload.get("latency_guardrail"):
        payload["latency_guardrail"] = guardrail
    if guardrail:
        metadata["guardrail"] = guardrail

    return metadata


def build_lane_reuse_event(
    lane: str,
    payload: Mapping[str, Any],
    *,
    receipts: Mapping[str, Any],
) -> Optional[Dict[str, Any]]:
    lane_key = (lane or "").strip().lower()
    if not lane_key:
        return None

    enriched_payload: Dict[str, Any] = dict(payload)
    metadata = enrich_accessory_payload(lane_key, enriched_payload, receipts=receipts)

    event: Dict[str, Any] = {
        "event": "lane_reused",
        "data": {
            "lane": lane_key,
            "status": "reused",
            "reused": True,
            "ts": enriched_payload.get("ts") or datetime.now(timezone.utc).isoformat(),
            "source": enriched_payload.get("source"),
            "reason": enriched_payload.get("reason") or "cached_artifact",
        },
    }

    age_value = enriched_payload.get("age_seconds")
    if age_value is None:
        age_value = metadata.get("age_seconds")
    if isinstance(age_value, (int, float)):
        event["data"]["age_seconds"] = int(age_value)

    fast_path_value = enriched_payload.get("fast_path_latency_ms")
    if fast_path_value is None:
        fast_path_value = metadata.get("fast_path_latency_ms")
    if isinstance(fast_path_value, (int, float)):
        event["data"]["fast_path_latency_ms"] = int(fast_path_value)

    guardrail_value = (
        enriched_payload.get("latency_guardrail")
        or metadata.get("guardrail")
    )
    if guardrail_value:
        event["data"]["guardrail"] = sanitize_for_json(guardrail_value)

    return event
