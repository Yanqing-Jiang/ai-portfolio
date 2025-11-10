# --- Analytics Function/Class Map ---
# Function: build_template_descriptor
#   Role: Build a deterministic clarification template descriptor consumable by the UI.
#   Called from: tests.analytics.test_clarification_template_descriptor
#   Invokes: analytics.flows.planner.intent_templates._normalize_slot, analytics.validators.sanitize_for_json, analytics.flows.planner.intent_templates._normalize_option
#   Why: The descriptor lists each slot as a "step" with prompt metadata, option labels, and pre-filled values so clients can render forms even when the clarifier agent skips.
# Function: _normalize_slot
#   Role: Handles normalize slot logic for analytics.flows.planner.intent_templates.
#   Called from: Internal to analytics.flows.planner.intent_templates
#   Invokes: Internal helpers only
#   Why: Keeps analytics.flows.planner.intent_templates from duplicating normalize slot behavior across flows.
# Function: _normalize_option
#   Role: Handles normalize option logic for analytics.flows.planner.intent_templates.
#   Called from: Internal to analytics.flows.planner.intent_templates
#   Invokes: Internal helpers only
#   Why: Keeps analytics.flows.planner.intent_templates from duplicating normalize option behavior across flows.
# --- End Analytics Function/Class Map ---
# Function Roles:
# - build_template_descriptor(intent_key, template, followups, slot_statuses) -> Converts resolver follow-ups + slot states into a structured descriptor that frontend forms can render deterministically.
# - _normalize_option(option) -> Normalizes suggestion entries into {label, value} dictionaries for descriptor consumers.

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from analytics.core.intent_impl.models import FollowUpModel, SlotStatusModel
from analytics.validators import sanitize_for_json

PLACEHOLDER_SLOTS = {"__any__", "__all__", ""}


def build_template_descriptor(
    intent_key: Optional[str],
    template: Optional[Mapping[str, Any]],
    followups: Sequence[FollowUpModel],
    slot_statuses: Mapping[str, SlotStatusModel],
) -> Optional[Dict[str, Any]]:
    """
    Build a deterministic clarification template descriptor consumable by the UI.

    The descriptor lists each slot as a "step" with prompt metadata, option labels, and
    pre-filled values so clients can render forms even when the clarifier agent skips.
    """
    if not followups:
        return None

    steps: List[Dict[str, Any]] = []
    for index, followup in enumerate(followups):
        original_slot = (followup.slot or "").strip()
        slot_name = _normalize_slot(original_slot)
        if slot_name is None:
            continue
        options = [_normalize_option(option) for option in followup.suggestions or []]
        options = [option for option in options if option is not None]
        if not options:
            options = []
        status_lookup_key = followup.slot or slot_name
        slot_status = slot_statuses.get(status_lookup_key) or slot_statuses.get(slot_name)
        control_type = "select" if options else "input"
        default_value = options[0]["value"] if options and not followup.allow_custom else None
        prefill_value = slot_status.value if slot_status and slot_status.value is not None else None
        steps.append(
            {
                "id": f"{slot_name}-step-{index}",
                "slot": original_slot or slot_name,
                "normalizedSlot": slot_name,
                "title": followup.prompt or slot_name.replace("_", " ").title(),
                "description": followup.reason,
                "control": control_type,
                "options": options,
                "allowCustom": followup.allow_custom if followup.allow_custom is not None else True,
                "defaultValue": default_value,
                "prefillValue": prefill_value,
                "order": index,
            }
        )

    if not steps:
        return None

    descriptor: Dict[str, Any] = {
        "intentKey": intent_key,
        "templateId": None,
        "templateName": None,
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "steps": steps,
    }
    if isinstance(template, Mapping):
        descriptor["templateId"] = template.get("id") or template.get("template_id")
        descriptor["templateName"] = template.get("name")
    try:
        return sanitize_for_json(descriptor)
    except Exception:
        return descriptor


def _normalize_slot(slot: Optional[str]) -> Optional[str]:
    if not slot:
        return None
    normalized = slot.strip().lower()
    if normalized in PLACEHOLDER_SLOTS:
        return None
    return normalized


def _normalize_option(option: Any) -> Optional[Dict[str, Any]]:
    if option is None:
        return None
    if isinstance(option, Mapping):
        value = option.get("value") or option.get("label")
        label = option.get("label") or option.get("value")
        if value is None and label is None:
            return None
        resolved_value = value if value is not None else label
        resolved_label = label if label is not None else resolved_value
        return {"label": str(resolved_label), "value": resolved_value}
    return {"label": str(option), "value": option}
