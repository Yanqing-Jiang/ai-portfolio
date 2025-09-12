from __future__ import annotations
from typing import List, Dict, Any
import asyncio
import asyncpg
import os

DATABASE_URL = os.getenv("DATABASE_URL")

async def execute(sql: str) -> List[Dict[str, Any]]:
    """Execute SQL with sane connection and query timeouts.

    - Connection timeout: 10s
    - Command timeout: 15s (applied at connection level)
    - Server-side statement_timeout: 15s (best-effort)
    """
    if not DATABASE_URL:
        raise ValueError("Database not configured - DATABASE_URL environment variable is missing")

    conn = None
    try:
        conn = await asyncpg.connect(
            DATABASE_URL,
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
