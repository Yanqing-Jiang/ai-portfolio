"""
Database Execution Shared Functions

Contains shared database execution logic used by both analytics_memory and analytics_supervisor systems.
Provides both basic and enhanced execution with safety features.
"""

import asyncio
import asyncpg
import os
import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)


async def execute(sql: str) -> List[Dict[str, Any]]:
    """
    Execute SQL with sane connection and query timeouts.

    Connection timeout: 10s
    Command timeout: 15s (applied at connection level)
    Server-side statement_timeout: 15s (best-effort)

    Args:
        sql: SQL query to execute

    Returns:
        List of result dictionaries

    Raises:
        ValueError: If database is not configured
        RuntimeError: If execution times out or other database errors occur
    """
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise ValueError("Database not configured - DATABASE_URL environment variable is missing")

    conn = None
    try:
        conn = await asyncpg.connect(
            database_url,
            statement_cache_size=0,
            timeout=10.0,
            command_timeout=15.0,
        )
        try:
            await conn.execute("SET statement_timeout = '15s'")
        except Exception:
            # Ignore if the server does not support this
            pass
        # Ensure the fetch itself honors a timeout
        rows = await conn.fetch(sql, timeout=15.0)
        return [dict(r) for r in rows]
    except asyncio.TimeoutError as te:
        raise RuntimeError("Database execution timeout") from te
    except ValueError:
        # Re-raise our custom database configuration error
        raise
    except Exception as e:
        # Wrap other database errors with more context
        raise RuntimeError(f"Database execution error: {str(e)}") from e
    finally:
        if conn:
            await conn.close()


async def execute_with_safety(sql: str, max_rows: int = 10000, timeout_seconds: int = 30) -> List[Dict[str, Any]]:
    """
    Execute SQL with enhanced safety features and configurable limits.

    Args:
        sql: SQL query to execute
        max_rows: Maximum number of rows to return (safety limit)
        timeout_seconds: Query timeout in seconds

    Returns:
        List of result dictionaries

    Raises:
        ValueError: If database is not configured or result set too large
        RuntimeError: If execution times out or other database errors occur
    """
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise ValueError("Database not configured - DATABASE_URL environment variable is missing")

    conn = None
    try:
        conn = await asyncpg.connect(
            database_url,
            statement_cache_size=0,
            timeout=10.0,
            command_timeout=float(timeout_seconds),
        )

        # Set server-side timeout
        try:
            await conn.execute(f"SET statement_timeout = '{timeout_seconds}s'")
        except Exception:
            # Ignore if the server does not support this
            pass

        # Execute query with timeout
        rows = await conn.fetch(sql, timeout=float(timeout_seconds))

        # Check row count safety limit
        if len(rows) > max_rows:
            logger.warning(f"Query returned {len(rows)} rows, truncating to {max_rows}")
            rows = rows[:max_rows]

        return [dict(r) for r in rows]
    except asyncio.TimeoutError as te:
        raise RuntimeError(f"Database execution timeout after {timeout_seconds}s") from te
    except ValueError:
        # Re-raise our custom database configuration error
        raise
    except Exception as e:
        # Wrap other database errors with more context
        error_msg = f"Database execution error: {str(e)}"
        logger.error(error_msg)
        raise RuntimeError(error_msg) from e
    finally:
        if conn:
            await conn.close()


async def test_connection() -> bool:
    """
    Test database connection health.

    Returns:
        True if connection successful, False otherwise
    """
    try:
        database_url = os.getenv("DATABASE_URL")
        if not database_url:
            return False

        conn = await asyncpg.connect(database_url, timeout=5.0)
        await conn.execute("SELECT 1", timeout=5.0)
        await conn.close()
        return True
    except Exception as e:
        logger.error(f"Database connection test failed: {e}")
        return False


async def get_table_info(table_name: str) -> Optional[List[Dict[str, Any]]]:
    """
    Get table schema information.

    Args:
        table_name: Name of the table to inspect

    Returns:
        List of column information dictionaries, or None if error
    """
    try:
        sql = """
        SELECT column_name, data_type, is_nullable
        FROM information_schema.columns
        WHERE table_name = $1
        ORDER BY ordinal_position
        """

        database_url = os.getenv("DATABASE_URL")
        if not database_url:
            return None

        conn = await asyncpg.connect(database_url, timeout=5.0)
        rows = await conn.fetch(sql, table_name, timeout=10.0)
        await conn.close()

        return [dict(r) for r in rows]
    except Exception as e:
        logger.error(f"Failed to get table info for {table_name}: {e}")
        return None


class DatabaseExecutor:
    """
    Database executor with connection pooling and retry logic.
    """

    def __init__(self, database_url: Optional[str] = None, pool_size: int = 5):
        self.database_url = database_url or os.getenv("DATABASE_URL")
        self.pool_size = pool_size
        self._pool = None

    async def initialize_pool(self):
        """Initialize connection pool."""
        if not self.database_url:
            raise ValueError("Database not configured - DATABASE_URL environment variable is missing")

        self._pool = await asyncpg.create_pool(
            self.database_url,
            min_size=1,
            max_size=self.pool_size,
            command_timeout=15.0
        )

    async def close_pool(self):
        """Close connection pool."""
        if self._pool:
            await self._pool.close()
            self._pool = None

    async def execute_query(self, sql: str, timeout: int = 15) -> List[Dict[str, Any]]:
        """
        Execute query using connection pool.

        Args:
            sql: SQL query to execute
            timeout: Query timeout in seconds

        Returns:
            List of result dictionaries
        """
        if not self._pool:
            await self.initialize_pool()

        async with self._pool.acquire() as conn:
            try:
                await conn.execute(f"SET statement_timeout = '{timeout}s'")
            except Exception:
                pass

            rows = await conn.fetch(sql, timeout=float(timeout))
            return [dict(r) for r in rows]


# For backward compatibility, export the simple execute function as default
__all__ = ['execute', 'execute_with_safety', 'test_connection', 'get_table_info', 'DatabaseExecutor']