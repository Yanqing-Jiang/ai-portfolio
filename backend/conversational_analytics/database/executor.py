"""Database executor for Conversational Analytics."""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List, Optional

import asyncpg

from ..config import settings

logger = logging.getLogger(__name__)


async def execute_sql(sql: str, *, timeout: float = 15.0) -> List[Dict[str, Any]]:
    """Execute SQL query against the conv_analytics_data table.
    
    Args:
        sql: SQL query to execute
        timeout: Query timeout in seconds
        
    Returns:
        List of row dictionaries
        
    Raises:
        RuntimeError: On database connection or execution errors
    """
    database_url = settings.database_url
    if not database_url:
        raise ValueError("DATABASE_URL environment variable is required")

    logger.info("[CONV_ANALYTICS] Executing SQL (%s chars)", len(sql))
    conn: Optional[asyncpg.Connection] = None
    
    try:
        conn = await asyncpg.connect(
            database_url,
            statement_cache_size=0,
            timeout=timeout,
            command_timeout=timeout,
        )
        
        # Set statement timeout for safety
        try:
            await conn.execute("SET statement_timeout = '15s'")
        except Exception:
            pass  # Best effort only
            
        rows = await conn.fetch(sql, timeout=timeout)
        result = [dict(row) for row in rows]
        logger.info("[CONV_ANALYTICS] Query returned %d rows", len(result))
        return result
        
    except asyncio.TimeoutError as exc:
        logger.error("[CONV_ANALYTICS] SQL execution timeout")
        raise RuntimeError("Database execution timeout") from exc
    except Exception as exc:
        logger.error("[CONV_ANALYTICS] SQL execution failed: %s", exc)
        raise RuntimeError(f"Database execution error: {exc}") from exc
    finally:
        if conn:
            await conn.close()


async def check_table_exists() -> bool:
    """Check if conv_analytics_data table exists."""
    try:
        result = await execute_sql("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'conv_analytics_data'
            );
        """)
        return result[0].get("exists", False) if result else False
    except Exception:
        return False
