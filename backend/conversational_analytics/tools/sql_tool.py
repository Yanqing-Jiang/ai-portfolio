"""SQL Query Tool for Conversational Analytics - Uses existing comp_financials table."""
from __future__ import annotations

import logging
import re
from typing import Any, Dict, List

from ..database.executor import execute_sql

logger = logging.getLogger(__name__)

# Tool definition for Claude
SQL_TOOL_DEFINITION = {
    "name": "query_database",
    "description": """Execute a SQL query against the comp_financials table to retrieve financial metrics for semiconductor companies.

The table has these columns:
- ticker: Stock symbol (AMD, AVGO, INTC, MU, NVDA, QCOM, TXN)
- calendar_year: Year (e.g., 2023, 2024)
- calendar_quarter_num: Quarter number (1, 2, 3, 4) - NULL for annual data
- calendar_quarter: Quarter label (Q1, Q2, Q3, Q4)
- metric: Name of the metric (e.g., 'Revenue', 'Net Income', 'Gross Margin')
- value: Numeric value

Common metrics available:
- Revenue, Net Income, Gross Margin, Operating Margin
- EPS (Earnings Per Share), Free Cash Flow
- Total Assets, Total Liabilities, Shareholders Equity
- R&D Expenses, SG&A Expenses

Example queries:
- SELECT ticker, calendar_year, SUM(value) as revenue FROM comp_financials WHERE metric = 'Revenue' GROUP BY ticker, calendar_year
- SELECT * FROM comp_financials WHERE ticker = 'NVDA' AND metric = 'Net Income' ORDER BY calendar_year DESC

Use this tool to answer analytics questions about semiconductor company financials.""",
    "input_schema": {
        "type": "object",
        "properties": {
            "sql": {
                "type": "string",
                "description": "PostgreSQL query to execute. Must be a SELECT query on comp_financials table."
            },
            "reason": {
                "type": "string",
                "description": "Brief explanation of why this query answers the user's question."
            }
        },
        "required": ["sql"]
    }
}


def _validate_sql(sql: str) -> tuple[bool, str]:
    """Validate SQL query for safety.
    
    Returns:
        Tuple of (is_valid, error_message)
    """
    sql_upper = sql.upper().strip()
    
    # Must be a SELECT query
    if not sql_upper.startswith("SELECT"):
        return False, "Only SELECT queries are allowed"
    
    # Disallow dangerous operations
    dangerous_keywords = ["DROP", "DELETE", "UPDATE", "INSERT", "TRUNCATE", "ALTER", "CREATE", "GRANT"]
    for keyword in dangerous_keywords:
        if re.search(rf'\b{keyword}\b', sql_upper):
            return False, f"Query contains disallowed keyword: {keyword}"
    
    # Must reference our table
    if "COMP_FINANCIALS" not in sql_upper:
        return False, "Query must reference comp_financials table"
    
    return True, ""


async def execute_sql_tool(sql: str, reason: str = "") -> Dict[str, Any]:
    """Execute a SQL query and return results.
    
    Args:
        sql: SQL query to execute
        reason: Explanation for the query
        
    Returns:
        Dictionary with sql, rows, columns, row_count, and success status
    """
    # Validate query
    is_valid, error_msg = _validate_sql(sql)
    if not is_valid:
        return {
            "success": False,
            "error": error_msg,
            "sql": sql,
            "rows": [],
            "columns": [],
            "row_count": 0
        }
    
    try:
        rows = await execute_sql(sql)
        columns = list(rows[0].keys()) if rows else []
        
        # Convert Decimal to float for JSON serialization
        serializable_rows = []
        for row in rows:
            serializable_row = {}
            for k, v in row.items():
                if hasattr(v, '__float__'):
                    serializable_row[k] = float(v)
                else:
                    serializable_row[k] = v
            serializable_rows.append(serializable_row)
        
        return {
            "success": True,
            "sql": sql,
            "reason": reason,
            "rows": serializable_rows,
            "columns": columns,
            "row_count": len(rows)
        }
        
    except Exception as e:
        logger.error("[SQL_TOOL] Query failed: %s", e)
        return {
            "success": False,
            "error": str(e),
            "sql": sql,
            "rows": [],
            "columns": [],
            "row_count": 0
        }
