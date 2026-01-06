"""
SQL Query Tool for shared data access.

Function: execute_sql_tool — runs validated SQL against comp_financials.
Called from: backend.generative_ui.agent_v2, backend.conversational_analytics.tools
Invokes: asyncpg connection pool to Supabase.
Purpose: Single implementation of read-only SQL execution for all projects.

Implements optimizations:
- #21: SQL parameterization for security
- #19: Connection pooling for performance
- #9: Tool use examples for better Claude invocation
"""
from __future__ import annotations

import asyncio
import logging
import re
from typing import Any, Dict, List, Optional, Tuple, Sequence

import asyncpg
from asyncpg import Pool

from .db_config import get_db_config

logger = logging.getLogger(__name__)


# ============================================================================
# Connection Pool Management (Optimization #19)
# ============================================================================

_pool: Optional[Pool] = None
_pool_lock = asyncio.Lock()


async def get_pool() -> Pool:
    """
    Get or create the connection pool singleton.
    
    Function: get_pool — manages asyncpg connection pool lifecycle.
    Called from: _execute_sql_raw, _execute_sql_parameterized
    Invokes: asyncpg.create_pool
    Why: Reuses connections for faster query execution and better resource utilization.
    """
    global _pool
    if _pool is None:
        async with _pool_lock:
            # Double-check after acquiring lock
            if _pool is None:
                config = get_db_config()
                if not config.database_url:
                    raise ValueError("DATABASE_URL environment variable is required")
                
                logger.info("[SHARED_TOOLS] Initializing connection pool")
                _pool = await asyncpg.create_pool(
                    config.database_url,
                    min_size=2,
                    max_size=10,
                    statement_cache_size=100,
                    command_timeout=30,
                    max_inactive_connection_lifetime=300,
                )
                logger.info("[SHARED_TOOLS] Connection pool initialized (min=2, max=10)")
    return _pool


async def close_pool() -> None:
    """
    Close the connection pool. Call during application shutdown.
    
    Function: close_pool — gracefully closes pool connections.
    Called from: application shutdown hooks
    Why: Ensures clean resource cleanup.
    """
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None
        logger.info("[SHARED_TOOLS] Connection pool closed")


# ============================================================================
# Tool Definition with Examples (Optimization #9)
# ============================================================================

# Tool definition for Claude (can be imported by either project)
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
    },
    # Tool use examples for better Claude invocation (Optimization #9)
    "examples": [
        {
            "input": {
                "sql": "SELECT ticker, calendar_year, SUM(value) as revenue FROM comp_financials WHERE metric = 'Revenue' GROUP BY ticker, calendar_year ORDER BY calendar_year DESC LIMIT 20",
                "reason": "Aggregate annual revenue by company to compare historical performance"
            },
            "output_summary": "Returns rows with ticker, year, and total revenue"
        },
        {
            "input": {
                "sql": "SELECT * FROM comp_financials WHERE ticker = 'NVDA' AND metric IN ('Gross Margin', 'Operating Margin') ORDER BY calendar_year DESC, calendar_quarter_num DESC LIMIT 16",
                "reason": "Fetch margin trends for NVIDIA over recent quarters"
            },
            "output_summary": "Returns quarterly margin values for charting"
        },
        {
            "input": {
                "sql": "SELECT ticker, calendar_year, calendar_quarter, metric, value FROM comp_financials WHERE ticker IN ('AMD', 'INTC', 'NVDA') AND metric = 'Revenue' ORDER BY ticker, calendar_year DESC, calendar_quarter_num DESC LIMIT 36",
                "reason": "Compare quarterly revenue across three semiconductor peers"
            },
            "output_summary": "Returns quarterly revenue data for peer comparison charts"
        }
    ]
}


# ============================================================================
# SQL Validation
# ============================================================================

# Allowed tickers for parameterized queries
ALLOWED_TICKERS = frozenset({"AMD", "AVGO", "INTC", "MU", "NVDA", "QCOM", "TXN"})

# Allowed metrics for parameterized queries
ALLOWED_METRICS = frozenset({
    "Revenue", "Net Income", "Gross Margin", "Operating Margin",
    "EPS", "Free Cash Flow", "Total Assets", "Total Liabilities",
    "Shareholders Equity", "R&D Expenses", "SG&A Expenses"
})


def _validate_sql(sql: str) -> Tuple[bool, str]:
    """
    Validate SQL query for safety.
    
    Function: _validate_sql — guards against dangerous SQL operations.
    Called from: execute_sql_tool
    Invokes: regex checks
    Purpose: Enforce SELECT-only queries on comp_financials.
    
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


def _sanitize_ticker(ticker: str) -> Optional[str]:
    """
    Sanitize and validate a ticker symbol.
    
    Function: _sanitize_ticker — validates ticker against allowed list.
    Called from: execute_parameterized_query, build_safe_ticker_filter
    Why: Prevents SQL injection through ticker values.
    
    Returns:
        Sanitized ticker if valid, None otherwise.
    """
    if not ticker:
        return None
    cleaned = ticker.upper().strip()
    return cleaned if cleaned in ALLOWED_TICKERS else None


def _sanitize_metric(metric: str) -> Optional[str]:
    """
    Sanitize and validate a metric name.
    
    Function: _sanitize_metric — validates metric against allowed list.
    Called from: execute_parameterized_query
    Why: Prevents SQL injection through metric values.
    
    Returns:
        Sanitized metric if valid, None otherwise.
    """
    if not metric:
        return None
    cleaned = metric.strip()
    return cleaned if cleaned in ALLOWED_METRICS else None


# ============================================================================
# Query Execution
# ============================================================================

async def _execute_sql_raw(sql: str, *, timeout: float = 15.0) -> List[Dict[str, Any]]:
    """
    Execute SQL query against the database using connection pool.
    
    Function: _execute_sql_raw — runs SQL via asyncpg pool.
    Called from: execute_sql_tool
    Invokes: get_pool, conn.fetch
    Purpose: Low-level DB execution with timeout handling and connection pooling.
    """
    pool = await get_pool()
    
    logger.info("[SHARED_TOOLS] Executing SQL (%s chars)", len(sql))
    
    try:
        async with pool.acquire() as conn:
            # Set statement timeout for safety
            try:
                await conn.execute("SET statement_timeout = '15s'")
            except Exception:
                pass  # Best effort only
            
            rows = await conn.fetch(sql, timeout=timeout)
            result = [dict(row) for row in rows]
            logger.info("[SHARED_TOOLS] Query returned %d rows", len(result))
            return result
        
    except asyncio.TimeoutError as exc:
        logger.error("[SHARED_TOOLS] SQL execution timeout")
        raise RuntimeError("Database execution timeout") from exc
    except Exception as exc:
        logger.error("[SHARED_TOOLS] SQL execution failed: %s", exc)
        raise RuntimeError(f"Database execution error: {exc}") from exc


async def _execute_sql_parameterized(
    sql: str,
    params: Sequence[Any],
    *,
    timeout: float = 15.0
) -> List[Dict[str, Any]]:
    """
    Execute parameterized SQL query against the database.
    
    Function: _execute_sql_parameterized — runs parameterized SQL via asyncpg pool.
    Called from: execute_parameterized_query
    Invokes: get_pool, conn.fetch with parameters
    Purpose: Secure query execution with SQL injection prevention (Optimization #21).
    
    Args:
        sql: SQL query with $1, $2, etc. placeholders
        params: Parameter values matching placeholders
        timeout: Query timeout in seconds
        
    Returns:
        List of row dictionaries
    """
    pool = await get_pool()
    
    logger.info("[SHARED_TOOLS] Executing parameterized SQL (%s chars, %d params)", len(sql), len(params))
    
    try:
        async with pool.acquire() as conn:
            # Set statement timeout for safety
            try:
                await conn.execute("SET statement_timeout = '15s'")
            except Exception:
                pass  # Best effort only
            
            rows = await conn.fetch(sql, *params, timeout=timeout)
            result = [dict(row) for row in rows]
            logger.info("[SHARED_TOOLS] Parameterized query returned %d rows", len(result))
            return result
        
    except asyncio.TimeoutError as exc:
        logger.error("[SHARED_TOOLS] Parameterized SQL execution timeout")
        raise RuntimeError("Database execution timeout") from exc
    except Exception as exc:
        logger.error("[SHARED_TOOLS] Parameterized SQL execution failed: %s", exc)
        raise RuntimeError(f"Database execution error: {exc}") from exc


def _serialize_rows(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Convert Decimal and other non-JSON types to serializable formats.
    
    Function: _serialize_rows — ensures JSON compatibility.
    Called from: execute_sql_tool, execute_parameterized_query
    Why: asyncpg returns Decimal for numeric columns; JSON needs float.
    """
    serializable_rows = []
    for row in rows:
        serializable_row = {}
        for k, v in row.items():
            if hasattr(v, '__float__'):
                serializable_row[k] = float(v)
            else:
                serializable_row[k] = v
        serializable_rows.append(serializable_row)
    return serializable_rows


async def execute_sql_tool(sql: str, reason: str = "") -> Dict[str, Any]:
    """
    Execute a SQL query and return results.
    
    Function: execute_sql_tool — validates and executes SQL queries.
    Called from: backend.generative_ui.agent_v2, backend.conversational_analytics.tools
    Invokes: _validate_sql, _execute_sql_raw
    Purpose: Safe, reusable SQL execution for financial data queries.
    
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
        rows = await _execute_sql_raw(sql)
        columns = list(rows[0].keys()) if rows else []
        serializable_rows = _serialize_rows(rows)
        
        return {
            "success": True,
            "sql": sql,
            "reason": reason,
            "rows": serializable_rows,
            "columns": columns,
            "row_count": len(rows)
        }
        
    except Exception as e:
        logger.error("[SHARED_TOOLS] Query failed: %s", e)
        return {
            "success": False,
            "error": str(e),
            "sql": sql,
            "rows": [],
            "columns": [],
            "row_count": 0
        }


async def execute_parameterized_query(
    tickers: Optional[List[str]] = None,
    metrics: Optional[List[str]] = None,
    limit: int = 100,
    order_by: str = "calendar_year DESC, calendar_quarter_num DESC",
    reason: str = ""
) -> Dict[str, Any]:
    """
    Execute a parameterized query with validated inputs.
    
    Function: execute_parameterized_query — builds and executes safe parameterized SQL.
    Called from: backend.generative_ui.agent_v2 (skill executors)
    Invokes: _sanitize_ticker, _sanitize_metric, _execute_sql_parameterized
    Purpose: SQL injection-safe queries for common dashboard patterns (Optimization #21).
    
    Args:
        tickers: List of ticker symbols to filter by
        metrics: List of metrics to filter by
        limit: Maximum number of rows to return
        order_by: ORDER BY clause (validated against safe patterns)
        reason: Explanation for the query
        
    Returns:
        Dictionary with sql, rows, columns, row_count, and success status
    """
    # Validate and sanitize inputs
    safe_tickers = []
    if tickers:
        for t in tickers:
            sanitized = _sanitize_ticker(t)
            if sanitized:
                safe_tickers.append(sanitized)
    
    safe_metrics = []
    if metrics:
        for m in metrics:
            sanitized = _sanitize_metric(m)
            if sanitized:
                safe_metrics.append(sanitized)
    
    # Validate limit
    limit = max(1, min(limit, 500))
    
    # Validate order_by against safe patterns
    safe_order_patterns = [
        "calendar_year DESC, calendar_quarter_num DESC",
        "calendar_year ASC, calendar_quarter_num ASC",
        "calendar_year DESC",
        "calendar_year ASC",
        "ticker, calendar_year DESC, calendar_quarter_num DESC",
        "ticker, calendar_year ASC, calendar_quarter_num ASC",
        "value DESC",
        "value ASC",
    ]
    if order_by not in safe_order_patterns:
        order_by = "calendar_year DESC, calendar_quarter_num DESC"
    
    # Build parameterized query
    conditions = []
    params: List[Any] = []
    param_idx = 1
    
    if safe_tickers:
        # Use ANY for multiple values
        conditions.append(f"ticker = ANY(${param_idx})")
        params.append(safe_tickers)
        param_idx += 1
    
    if safe_metrics:
        conditions.append(f"metric = ANY(${param_idx})")
        params.append(safe_metrics)
        param_idx += 1
    
    where_clause = " AND ".join(conditions) if conditions else "1=1"
    
    sql = f"""
        SELECT ticker, calendar_year, calendar_quarter_num, calendar_quarter, metric, value
        FROM comp_financials
        WHERE {where_clause}
        ORDER BY {order_by}
        LIMIT {limit}
    """
    
    try:
        rows = await _execute_sql_parameterized(sql.strip(), params)
        columns = list(rows[0].keys()) if rows else []
        serializable_rows = _serialize_rows(rows)
        
        return {
            "success": True,
            "sql": sql.strip(),
            "params": {
                "tickers": safe_tickers,
                "metrics": safe_metrics,
                "limit": limit,
            },
            "reason": reason,
            "rows": serializable_rows,
            "columns": columns,
            "row_count": len(rows)
        }
        
    except Exception as e:
        logger.error("[SHARED_TOOLS] Parameterized query failed: %s", e)
        return {
            "success": False,
            "error": str(e),
            "sql": sql.strip(),
            "rows": [],
            "columns": [],
            "row_count": 0
        }


__all__ = [
    "SQL_TOOL_DEFINITION",
    "execute_sql_tool",
    "execute_parameterized_query",
    "get_pool",
    "close_pool",
    "ALLOWED_TICKERS",
    "ALLOWED_METRICS",
]
