# --- Analytics Function/Class Map ---
# Function: hash_payload
#   Role: Produces a stable SHA1 digest for payload deduping/telemetry.
#   Called from: analytics.flows.planner_executor, analytics.flows.single_agent_tools, analytics.flows.multi_agent
#   Invokes: analytics.validators.sanitize_for_json, json.dumps, hashlib.sha1
#   Why: Normalizes tool inputs/outputs for receipts and cache reuse.
# Function: normalize_metric_slots
#   Role: Normalizes metric slot statuses to clear missing/followups when values exist.
#   Called from: analytics.flows.planner_executor intent stage helpers
#   Invokes: slot_state.model_copy
#   Why: Keeps intent resolution consistent before planning and clarifications.
# Function: build_slot_assumptions
#   Role: Derives assumption strings for defaulted/assumed slots.
#   Called from: analytics.flows.planner_executor intent stage helpers
#   Invokes: None
#   Why: Annotates intent/plan context with slot defaults for downstream prompts.
# Function: ensure_tool_receipt
#   Role: Creates/updates a tool receipt with common status/reuse metadata.
#   Called from: analytics.flows.planner_executor
#   Invokes: None
#   Why: Centralizes receipt mutation to keep parity across flows.
# --- End Analytics Function/Class Map ---
from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, List, Mapping, Optional

from analytics.validators import sanitize_for_json


def hash_payload(payload: Any) -> str:
    """Return a deterministic hash for an arbitrary payload."""
    try:
        normalized = sanitize_for_json(payload)
    except Exception:
        normalized = payload
    try:
        encoded = json.dumps(
            normalized,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
    except TypeError:
        encoded = json.dumps(str(normalized), sort_keys=True).encode("utf-8")
    return hashlib.sha1(encoded).hexdigest()


def normalize_metric_slots(resolution: Any) -> None:
    """Mark metric slots as defaulted when values are present to clear followups."""
    if resolution is None or not hasattr(resolution, "slots"):
        return

    def _normalize(slot_name: str) -> None:
        slot_state = resolution.slots.get(slot_name)
        if slot_state is None:
            return
        value = getattr(slot_state, "value", None)
        has_value = False
        if isinstance(value, (list, tuple, set)):
            has_value = any(item is not None for item in value)
        elif value not in (None, "", []):
            has_value = True
        if getattr(slot_state, "status", None) == "missing" and has_value:
            if hasattr(slot_state, "model_copy"):
                resolution.slots[slot_name] = slot_state.model_copy(update={"status": "defaulted"})
        updated = resolution.slots.get(slot_name)
        if updated and getattr(updated, "status", None) != "missing":
            resolution.followups = [
                followup
                for followup in list(getattr(resolution, "followups", []) or [])
                if getattr(followup, "slot", None) != slot_name
            ]

    _normalize("metric")
    _normalize("metrics")


def build_slot_assumptions(slots: Mapping[str, Any]) -> List[str]:
    """Compose human-readable assumption statements for slots."""
    assumptions: List[str] = []
    for slot_name, status in (slots or {}).items():
        if not hasattr(status, "status"):
            continue
        slot_status = getattr(status, "status", None)
        value = getattr(status, "value", None)
        if slot_status == "defaulted" and value is not None:
            assumptions.append(f"{slot_name} defaulted to {value}")
        elif slot_status == "assumed":
            assumptions.append(f"{slot_name} assumed ({slot_status})")
    return assumptions


def ensure_tool_receipt(
    ctx: Any,
    tool: str,
    *,
    status: str,
    reused: bool = False,
    attempts: Optional[int] = None,
    input_hash: Optional[str] = None,
    output_hash: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Any:
    """
    Create or update a tool receipt with consistent fields.

    - status: receipt status (running/reused/completed/failed)
    - reused: flag for cache hits
    - attempts: override attempts counter (default increments by one)
    """
    receipts = getattr(ctx, "tool_receipts", None)
    if receipts is None:
        receipts = {}
        ctx.tool_receipts = receipts
    receipt = receipts.get(tool)
    if receipt is None:
        from analytics.flows.planner_executor import ToolInvocationReceipt  # local import to avoid cycles

        receipt = ToolInvocationReceipt(
            tool=tool,
            status=status,
            attempts=attempts if attempts is not None else 0,
            reused=reused,
            input_hash=input_hash,
            output_hash=output_hash,
            metadata=dict(metadata or {}),
        )
        receipts[tool] = receipt
        return receipt

    receipt.status = status
    receipt.reused = reused
    if attempts is not None:
        receipt.attempts = attempts
    elif status == "running":
        receipt.attempts = 0
    receipt.error = None
    receipt.output_hash = output_hash
    if input_hash and not receipt.input_hash:
        receipt.input_hash = input_hash
    if metadata:
        meta = dict(getattr(receipt, "metadata", {}) or {})
        meta.update(metadata)
        receipt.metadata = meta
    receipts[tool] = receipt
    return receipt

