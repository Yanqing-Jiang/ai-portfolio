"""AST-based SQL safety checks (placeholder)."""
from __future__ import annotations

from typing import List


class SQLValidationError(Exception):
    pass


def validate_sql(sql: str) -> List[str]:
    """Return list of validation errors."""
    errors: List[str] = []
    if "SELECT *" in sql.upper():
        errors.append("select_star_not_allowed")
    return errors


__all__ = ["validate_sql", "SQLValidationError"]
