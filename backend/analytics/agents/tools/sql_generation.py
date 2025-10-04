"""SQL-related tools for the simple agent runtime."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from analytics.core.types import IntentModel, QueryPlanModel
from analytics.sql.prompt_builder import build_sql_messages

from ..tool_registry import AnalyticsTool, ToolSpec
from .clarification import _ensure_model


class SqlMessageTool(AnalyticsTool):
    """Builds SQL drafting messages using existing prompt builder."""

    def __init__(self) -> None:
        spec = ToolSpec(
            name="sql.build_messages",
            description="Generate system/user prompts for SQL drafting based on the detected intent and plan.",
            input_schema={
                "type": "object",
                "properties": {
                    "original_query": {"type": "string"},
                    "intent": {"type": "object"},
                    "plan": {"type": "object"},
                    "templates": {"type": ["array", "null"]},
                    "top_k_templates": {"type": "integer"},
                },
                "required": ["original_query", "intent", "plan"],
            },
            output_schema={
                "type": "object",
                "properties": {
                    "messages": {
                        "type": "array",
                        "items": {"type": "object"},
                    }
                },
            },
        )
        super().__init__(spec)

    async def ainvoke(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        original_query = payload.get("original_query")
        if not original_query:
            raise ValueError("'original_query' is required for sql.build_messages")
        intent = _ensure_model(IntentModel, payload.get("intent"))
        plan = _ensure_model(QueryPlanModel, payload.get("plan"))
        templates: Optional[List[Dict[str, Any]]] = payload.get("templates")
        top_k = payload.get("top_k_templates", 2)

        messages = await build_sql_messages(
            original_query=original_query,
            intent=intent,
            plan=plan,
            templates=templates,
            top_k_templates=top_k,
        )
        return {"messages": messages, "count": len(messages)}
