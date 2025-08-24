"""SQL related low-level helpers."""
from __future__ import annotations

from typing import Any, Dict


def run_query_sandboxed(sql: str, limit: int = 1000, timeout: int = 30) -> Dict[str, Any]:
    """Run the given SQL with guardrails (placeholder)."""
    return {"rows": []}


def explain_query(sql: str) -> str:
    """Return query plan (placeholder)."""
    return "EXPLAIN"


__all__ = ["run_query_sandboxed", "explain_query"]
