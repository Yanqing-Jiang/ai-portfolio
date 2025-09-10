from __future__ import annotations
from typing import List, Dict, Any
import asyncpg
import os

DATABASE_URL = os.getenv("DATABASE_URL")

async def execute(sql: str) -> List[Dict[str, Any]]:
    # Early validation for DATABASE_URL
    if not DATABASE_URL:
        raise ValueError("Database not configured - DATABASE_URL environment variable is missing")
    
    conn = None
    try:
        conn = await asyncpg.connect(DATABASE_URL, statement_cache_size=0)
        try:
            await conn.execute("SET statement_timeout = '15s'")
        except Exception:
            pass
        rows = await conn.fetch(sql)
        return [dict(r) for r in rows]
    except ValueError:
        # Re-raise our custom database configuration error
        raise
    except Exception as e:
        # Wrap other database errors with more context
        raise RuntimeError(f"Database execution error: {str(e)}") from e
    finally:
        if conn:
            await conn.close()
