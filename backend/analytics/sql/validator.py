from __future__ import annotations

from typing import Iterable, List, Optional, Tuple

import sqlglot
from sqlglot import exp

from ..core.context import get_configs

CONFIGS = get_configs()


def _default_allowed_tables() -> List[str]:
    tables = CONFIGS.database.get("tables") if CONFIGS.database else None
    if isinstance(tables, dict):
        return list(tables.keys())
    return ["comp_financials"]


def validate_sql(
    sql: str,
    allowed_tables: Optional[Iterable[str]] = None,
    max_limit: Optional[int] = None,
    granularity: str = "annual",
    require_limit: bool = True,
) -> Tuple[bool, List[str]]:
    issues: List[str] = []

    allowed_tables = list(allowed_tables or _default_allowed_tables())
    defaults = CONFIGS.database.get("query_defaults", {}) if CONFIGS.database else {}
    max_limit = max_limit or defaults.get("max_limit", 10000)

    try:
        expr = sqlglot.parse_one(sql, read="postgres")
    except Exception as exc:
        return False, [f"SQL parse error: {exc}"]

    root_select = expr.this if isinstance(expr, exp.With) else expr
    if not isinstance(root_select, exp.Select):
        issues.append("Only SELECT queries are permitted")

    cte_names = {cte.alias_or_name for cte in expr.find_all(exp.CTE)}
    for table in expr.find_all(exp.Table):
        table_name = table.name
        if table_name not in cte_names and table_name not in allowed_tables:
            issues.append(f"Disallowed table: {table_name}")

    selects = list(expr.find_all(exp.Select)) or ([expr] if isinstance(expr, exp.Select) else [])
    limit_found = False
    for select in selects:
        limit_exp = select.args.get("limit")
        if not limit_exp:
            continue
        limit_found = True
        try:
            expression = getattr(limit_exp, "expression", None) or limit_exp.args.get("expression")
            limit_value = int(expression.name if expression else str(limit_exp))
            if limit_value > max_limit:
                issues.append(f"LIMIT exceeds maximum allowed ({limit_value} > {max_limit})")
        except Exception:
            issues.append("LIMIT must be a constant integer")

    if require_limit and not limit_found:
        issues.append("Query must include a LIMIT clause")

    has_calendar_year_filter = False
    for where_clause in expr.find_all(exp.Where):
        for column in where_clause.find_all(exp.Column):
            if (column.name or "").lower() == "calendar_year":
                has_calendar_year_filter = True
                break
        if has_calendar_year_filter:
            break

    if not has_calendar_year_filter:
        issues.append("calendar_year filter is required")

    if granularity == "quarterly" and "calendar_quarter_num" not in sql.lower():
        issues.append("Quarterly queries must reference calendar_quarter_num")

    return len(issues) == 0, issues


def quick_validate_sql_syntax(sql: str) -> Tuple[bool, str]:
    try:
        sqlglot.parse_one(sql, read="postgres")
        return True, ""
    except Exception as exc:
        return False, f"SQL syntax error: {exc}"
