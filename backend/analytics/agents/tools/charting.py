"""Charting tool definitions for analytics agents."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from analytics.core.charting import build_chart_spec, plan_chart_rule_based
from analytics.core.config import CONFIGS

from ..tool_registry import AnalyticsTool, ToolSpec


class ChartPlanningTool(AnalyticsTool):
    """Generates chart plan/spec from tabular analytics data."""

    def __init__(self) -> None:
        spec = ToolSpec(
            name="chart.generate",
            description="Plan and render an analytics chart based on query results.",
            input_schema={
                "type": "object",
                "properties": {
                    "data": {
                        "type": "array",
                        "items": {"type": "object"},
                    },
                    "query": {"type": "string"},
                    "intent_key": {"type": ["string", "null"]},
                    "comparison": {"type": ["string", "null"]},
                },
                "required": ["data", "query"],
            },
            output_schema={
                "type": "object",
                "properties": {
                    "chart_plan": {"type": "object"},
                    "chart_spec": {"type": "object"},
                },
            },
        )
        super().__init__(spec)

    async def ainvoke(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        data: List[Dict[str, Any]] = payload.get("data") or []
        if not isinstance(data, list):
            raise ValueError("'data' must be a list of result rows")
        query = payload.get("query")
        if not query:
            raise ValueError("'query' is required for chart.generate")
        intent_key: Optional[str] = payload.get("intent_key")
        comparison: Optional[str] = payload.get("comparison")

        chart_plan = plan_chart_rule_based(data, query, intent_key)
        charts_cfg = CONFIGS.charts if hasattr(CONFIGS, "charts") else {}
        chart_spec = build_chart_spec(
            data,
            chart_plan,
            charts_cfg,
            intent_key=intent_key,
            comparison=comparison,
        )
        return {"chart_plan": chart_plan, "chart_spec": chart_spec}
