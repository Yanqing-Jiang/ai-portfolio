# --- Analytics Function/Class Map ---
# Function: _ensure_env_loaded
#   Role: Handles ensure env loaded logic for analytics.sql.executor.
#   Called from: Internal to analytics.sql.executor
#   Invokes: os.getenv, dotenv.load_dotenv, pathlib.Path
#   Why: Keeps analytics.sql.executor from duplicating ensure env loaded behavior across flows.
# Function: _coerce_round_numeric
#   Role: Ensure ROUND() receives a NUMERIC argument for PostgreSQL compatibility.
#   Called from: Internal to analytics.sql.executor
#   Invokes: Internal helpers only
#   Why: Supports downstream analytics workflows that rely on _coerce_round_numeric.
# Function: execute_sql
#   Role: Handles execute sql logic for analytics.sql.executor.
#   Called from: analytics.flows.planner_executor, analytics.tools.registry
#   Invokes: analytics.sql.executor._coerce_round_numeric, os.getenv, asyncpg.connect
#   Why: Keeps analytics.sql.executor from duplicating execute sql behavior across flows.
# --- End Analytics Function/Class Map ---
from __future__ import annotations

import asyncio
import logging
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

import asyncpg
from dotenv import load_dotenv

logger = logging.getLogger(__name__)


def _ensure_env_loaded() -> None:
    if os.getenv("DATABASE_URL"):
        return
    backend_dir = Path(__file__).resolve().parents[2]
    env_path = backend_dir / ".env"
    if env_path.exists():
        load_dotenv(dotenv_path=env_path, override=False)
        logger.info("[DATABASE] Loaded environment variables from %s", env_path)


_ensure_env_loaded()


_ROUND_PATTERN = re.compile(
    r"ROUND\s*\(\s*([^,]+?)\s*,\s*(\d+)\s*\)",
    re.IGNORECASE | re.DOTALL,
)


def _coerce_round_numeric(sql: str) -> str:
    """Ensure ROUND() receives a NUMERIC argument for PostgreSQL compatibility."""

    def _repl(match: re.Match[str]) -> str:
        expression = match.group(1).strip()
        digits = match.group(2)
        upper_expr = expression.upper()
        if "::NUMERIC" in upper_expr or "CAST(" in upper_expr:
            return match.group(0)
        return f"ROUND(({expression})::numeric, {digits})"

    return _ROUND_PATTERN.sub(_repl, sql)


async def execute_sql(sql: str, *, timeout: float = 15.0) -> List[Dict[str, Any]]:
    sql = _coerce_round_numeric(sql)
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise ValueError("DATABASE_URL environment variable is required for analytics SQL execution")

    logger.info("[DATABASE] Executing SQL (%s chars)", len(sql))
    conn: Optional[asyncpg.Connection] = None
    try:
        conn = await asyncpg.connect(
            database_url,
            statement_cache_size=0,
            timeout=timeout,
            command_timeout=timeout,
        )
        try:
            await conn.execute("SET statement_timeout = '15s'")
        except Exception:  # pragma: no cover - best effort only
            pass
        rows = await conn.fetch(sql, timeout=timeout)
        return [dict(row) for row in rows]
    except asyncio.TimeoutError as exc:
        logger.error("[DATABASE] SQL execution timeout")
        raise RuntimeError("Database execution timeout") from exc
    except Exception as exc:
        logger.error("[DATABASE] SQL execution failed: %s", exc)
        raise RuntimeError(f"Database execution error: {exc}") from exc
    finally:
        if conn:
            await conn.close()
