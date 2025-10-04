"""Warehouse execution tool wrappers."""
from __future__ import annotations

from typing import Any, Dict

from analytics.sql.executor import execute_sql_with_limit

from ..tool_registry import AnalyticsTool, ToolSpec


class SqlExecutionTool(AnalyticsTool):
    """Executes SQL against the analytics warehouse with guardrails."""

    def __init__(self) -> None:
        spec = ToolSpec(
            name="sql.execute",
            description="Run warehouse SQL with a row-limit guard and return rows.",
            input_schema={
                "type": "object",
                "properties": {
                    "sql": {"type": "string"},
                    "max_rows": {"type": "integer"},
                    "timeout": {"type": "number"},
                },
                "required": ["sql"],
            },
            output_schema={
                "type": "object",
                "properties": {
                    "rows": {
                        "type": "array",
                        "items": {"type": "object"},
                    },
                    "row_count": {"type": "integer"},
                },
            },
        )
        super().__init__(spec)

    async def ainvoke(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        sql = payload.get("sql")
        if not sql:
            raise ValueError("'sql' is required for sql.execute")
        max_rows = int(payload.get("max_rows", 10000))
        timeout = float(payload.get("timeout", 20.0))
        rows = await execute_sql_with_limit(sql, max_rows=max_rows, timeout=timeout)
        return {"rows": rows, "row_count": len(rows)}
