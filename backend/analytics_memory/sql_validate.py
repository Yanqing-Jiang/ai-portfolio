from __future__ import annotations
from typing import List, Tuple

import sqlglot
from sqlglot import exp


def validate_sql(sql: str, allowed_tables: List[str], max_limit: int, granularity: str) -> Tuple[bool, List[str]]:
    issues: List[str] = []
    try:
        expr = sqlglot.parse_one(sql, read='postgres')
    except Exception as e:
        return False, [f"SQL parse error: {e}"]

    # Handle WITH queries - get the root SELECT
    root_select = expr.this if isinstance(expr, exp.With) else expr
    
    # Only SELECT queries allowed
    if not isinstance(root_select, exp.Select):
        issues.append('Only SELECT queries are allowed')

    # Collect CTE names to exclude from table validation
    cte_names = {cte.alias_or_name for cte in expr.find_all(exp.CTE)}
    
    # Tables validation - only check actual database tables, not CTEs
    tables = [t.name for t in expr.find_all(exp.Table)]
    for t in tables:
        if t not in cte_names and t not in allowed_tables:
            issues.append(f"Disallowed table: {t}")

    # LIMIT validation - check all SELECT statements
    select_statements = list(expr.find_all(exp.Select))
    has_limit = False
    max_limit_violation = None
    
    for sel in select_statements:
        limit_exp = sel.args.get('limit')
        if limit_exp:
            has_limit = True
            try:
                # Handle different sqlglot LIMIT structures
                if hasattr(limit_exp, 'expression') and limit_exp.expression:
                    limit_val = int(limit_exp.expression.name)
                elif hasattr(limit_exp, 'args') and limit_exp.args.get('expression'):
                    limit_val = int(limit_exp.args.get('expression').name)
                else:
                    # Try direct conversion
                    limit_val = int(str(limit_exp))
                
                if limit_val > max_limit:
                    max_limit_violation = limit_val
            except (ValueError, AttributeError, TypeError):
                issues.append('LIMIT must be a numeric constant')
    
    if not has_limit:
        issues.append('Query must include LIMIT')
    elif max_limit_violation:
        issues.append(f"LIMIT too high: {max_limit_violation} > {max_limit}")

    # Calendar year filter validation - scan all WHERE clauses
    has_calendar_year = False
    for where_clause in expr.find_all(exp.Where):
        for column in where_clause.find_all(exp.Column):
            column_name = (column.name or '').lower()
            if column_name == 'calendar_year':
                has_calendar_year = True
                break
        if has_calendar_year:
            break
    
    if not has_calendar_year:
        issues.append('calendar_year filter is required')

    # Granularity rule for quarterly queries
    if granularity == 'quarterly' and 'calendar_quarter_num' not in sql.lower():
        issues.append('Quarterly queries must filter on calendar_quarter_num')

    ok = len(issues) == 0
    return ok, issues

