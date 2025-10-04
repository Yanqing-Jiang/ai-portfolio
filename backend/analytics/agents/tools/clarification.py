"""Clarification tool wrapping existing planner clarification logic."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from analytics.core.clarify import compute_required_clarifications
from analytics.core.context import get_configs
from analytics.core.types import ClarifyRequestModel, IntentModel, QueryPlanModel

from ..tool_registry import AnalyticsTool, ToolSpec


def _ensure_model(model_cls, payload: Dict[str, Any]):
    """Helper to parse dictionaries into pydantic models."""

    if isinstance(payload, model_cls):
        return payload
    if hasattr(model_cls, "model_validate"):
        return model_cls.model_validate(payload)
    return model_cls(**payload)


class ClarificationTool(AnalyticsTool):
    """Computes required clarifications for the agent workflow."""

    def __init__(self, *, configs: Optional[Dict[str, Any]] = None) -> None:
        spec = ToolSpec(
            name="clarification.ask_missing_slots",
            description="Detect missing parameters for the analytics query and return clarification prompts.",
            input_schema={
                "type": "object",
                "properties": {
                    "intent": {"type": "object", "description": "IntentModel payload"},
                    "plan": {"type": "object", "description": "QueryPlanModel payload"},
                    "template": {"type": ["object", "null"]},
                },
                "required": ["intent", "plan"],
            },
            output_schema={
                "type": "object",
                "properties": {
                    "clarifications": {
                        "type": "array",
                        "items": {"type": "object"},
                    }
                },
            },
        )
        super().__init__(spec)
        self._configs = configs or get_configs()

    async def ainvoke(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        intent_payload = payload.get("intent")
        plan_payload = payload.get("plan")
        template_payload = payload.get("template")
        if intent_payload is None or plan_payload is None:
            raise ValueError("Clarification tool requires 'intent' and 'plan' keys")

        intent = _ensure_model(IntentModel, intent_payload)
        plan = _ensure_model(QueryPlanModel, plan_payload)
        template: Optional[Dict[str, Any]] = None
        if template_payload is not None:
            template = dict(template_payload)

        clarifications: List[ClarifyRequestModel] = compute_required_clarifications(
            intent=intent,
            provisional_plan=plan,
            template=template,
            configs=self._configs,
        )
        return {
            "clarifications": [c.model_dump() for c in clarifications],
            "count": len(clarifications),
        }
