"""Analysis summarization tools."""
from __future__ import annotations

from typing import Any, Dict, List

from analytics.core.analysis import summarize

from ..tool_registry import AnalyticsTool, ToolSpec


class AnalysisSummaryTool(AnalyticsTool):
    """Produces a concise narrative summary from SQL results."""

    def __init__(self) -> None:
        spec = ToolSpec(
            name="analysis.summarize",
            description="Summarize tabular financial results into a human-readable narrative.",
            input_schema={
                "type": "object",
                "properties": {
                    "data": {
                        "type": "array",
                        "items": {"type": "object"},
                    },
                    "sql": {"type": "string"},
                    "query": {"type": "string"},
                },
                "required": ["data", "sql", "query"],
            },
            output_schema={
                "type": "object",
                "properties": {
                    "summary": {"type": "string"},
                },
            },
        )
        super().__init__(spec)

    async def ainvoke(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        data: List[Dict[str, Any]] = payload.get("data") or []
        sql = payload.get("sql")
        query = payload.get("query")
        if not sql or not query:
            raise ValueError("'sql' and 'query' are required for analysis.summarize")
        summary = summarize(data, sql, query)
        return {"summary": summary, "length": len(summary)}
