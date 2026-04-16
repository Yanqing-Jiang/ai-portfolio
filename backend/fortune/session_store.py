"""SQLAlchemySession factory for Ask-tab follow-up memory.

The action-button follow-ups (Career Deep Dive, etc.) are stateless — each
click triages afresh on the already-computed foundation. The free-form **Ask
tab** is different: users type "why did you say my metal is weak?" and expect
the answer to build on prior turns. That needs durable conversation memory.

We use the Agents SDK's ``SQLAlchemySession`` pointed at Supabase so:

1. Memory survives process restarts (Mac Mini reboots, Docker redeploys).
2. All workers share the same history (no Redis fanout needed yet).
3. The SDK handles compaction via ``SessionSettings(limit=…)`` — oldest
   messages beyond the limit are dropped on read. Good enough for a 20-turn
   thread per fortune.

The session id is ``fortune_{fortune_id}``, so each fortune owns its own
ask-thread. Sharing across fortunes would require separate session ids
(not needed now).

Why a separate asyncpg engine rather than reusing ``store.get_fortune_pool()``:
SQLAlchemy's async engine owns its own connection pool and can't borrow raw
asyncpg connections. The two pools stay small (max 4 each) so the combined
footprint is bounded. Both go through Supavisor's transaction-mode pooler so
we pass ``statement_cache_size=0`` on the underlying asyncpg driver.
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)


def _db_url() -> str:
    """Read SUPABASE_DB_URL lazily — see store._db_url for rationale."""
    return os.getenv("SUPABASE_DB_URL", "")


def _ask_session_limit() -> int:
    return int(os.getenv("FORTUNE_ASK_SESSION_LIMIT", "20"))


_engine: object | None = None
_engine_lock = asyncio.Lock()
_tables_ready = False
_session_settings: object | None = None


def _sqlalchemy_url(raw: str) -> str:
    """Convert the asyncpg-style URL to SQLAlchemy's ``postgresql+asyncpg`` scheme."""
    if raw.startswith("postgresql+asyncpg://"):
        return raw
    if raw.startswith("postgresql://"):
        return "postgresql+asyncpg://" + raw[len("postgresql://"):]
    if raw.startswith("postgres://"):
        return "postgresql+asyncpg://" + raw[len("postgres://"):]
    return raw


async def get_ask_engine():
    """Lazy singleton AsyncEngine used for ``agent_sessions`` / ``agent_messages``.

    The first caller creates the engine AND auto-creates the SDK's session
    tables via ``create_tables=True`` on the first ``SQLAlchemySession``.
    Subsequent callers reuse the same engine.
    """
    global _engine
    if _engine is not None:
        return _engine
    raw = _db_url()
    if not raw:
        logger.warning("[FORTUNE] SUPABASE_DB_URL not configured — ask-session memory disabled")
        return None
    async with _engine_lock:
        if _engine is not None:
            return _engine
        try:
            from sqlalchemy.ext.asyncio import create_async_engine
            _engine = create_async_engine(
                _sqlalchemy_url(raw),
                # Small pool — ask-tab is lower-volume than the main fortune pool.
                pool_size=2,
                max_overflow=2,
                pool_pre_ping=True,
                # Supavisor transaction-mode pooler rejects server-side prepared
                # statements. Pass through to the asyncpg driver.
                connect_args={"statement_cache_size": 0},
            )
            logger.info("[FORTUNE] ask-session engine initialized")
        except Exception as exc:
            logger.warning("[FORTUNE] ask-session engine init failed: %s", exc)
            _engine = None
    return _engine


def _get_session_settings():
    """Lazy singleton ``SessionSettings(limit=...)`` — controls compaction."""
    global _session_settings
    if _session_settings is not None:
        return _session_settings
    try:
        from agents.memory.session_settings import SessionSettings
        _session_settings = SessionSettings(limit=_ask_session_limit())
    except Exception as exc:  # pragma: no cover
        logger.warning("[FORTUNE] SessionSettings unavailable: %s", exc)
        _session_settings = None
    return _session_settings


_tables_ready_lock = asyncio.Lock()


async def _ensure_tables_ready(engine) -> bool:
    """Create ``agent_sessions``/``agent_messages`` once per process.

    The SDK's ``SQLAlchemySession(create_tables=True)`` defers DDL to the first
    DB operation; it does NOT run ``create_all`` in ``__init__``. Setting a
    "ready" flag at construction time would mean a downstream failure leaves
    the process believing tables exist when they do not. To avoid that, we run
    ``Base.metadata.create_all`` here explicitly, gated by a lock so only one
    caller performs the DDL round-trip per process boot.
    """
    global _tables_ready
    if _tables_ready:
        return True
    async with _tables_ready_lock:
        if _tables_ready:
            return True
        try:
            from agents.extensions.memory.sqlalchemy_session import SQLAlchemySession
            # Build a throwaway session purely to trigger the SDK's internal
            # metadata build, then run create_all via the engine. The session
            # object knows the MetaData bound to these tables.
            bootstrap = SQLAlchemySession(
                session_id="__bootstrap__",
                engine=engine,
                create_tables=False,
                session_settings=_get_session_settings(),
            )
            async with engine.begin() as conn:
                await conn.run_sync(bootstrap._metadata.create_all)
            _tables_ready = True
            logger.info("[FORTUNE] ask-session tables ensured")
            return True
        except Exception as exc:
            logger.warning("[FORTUNE] ask-session table create failed: %s", exc)
            return False


async def get_ask_session(fortune_id: str):
    """Return a configured ``SQLAlchemySession`` scoped to one fortune's ask thread.

    Returns ``None`` when persistence is disabled so callers can fall back to
    stateless triage without crashing.
    """
    engine = await get_ask_engine()
    if engine is None:
        return None
    try:
        from agents.extensions.memory.sqlalchemy_session import SQLAlchemySession
    except ImportError:  # pragma: no cover
        logger.warning("[FORTUNE] SQLAlchemySession not importable; ask memory disabled")
        return None

    if not await _ensure_tables_ready(engine):
        return None

    try:
        return SQLAlchemySession(
            session_id=f"fortune_{fortune_id}",
            engine=engine,
            create_tables=False,  # tables already ensured by _ensure_tables_ready
            session_settings=_get_session_settings(),
        )
    except Exception as exc:
        logger.warning("[FORTUNE] SQLAlchemySession build failed: %s", exc)
        return None


async def close_ask_engine() -> None:
    """Dispose of the async engine on shutdown (called from FastAPI lifespan)."""
    global _engine, _tables_ready
    if _engine is None:
        return
    try:
        await _engine.dispose()
        logger.info("[FORTUNE] ask-session engine disposed")
    except Exception as exc:  # pragma: no cover
        logger.warning("[FORTUNE] ask-session engine dispose failed: %s", exc)
    finally:
        _engine = None
        # Reset so a subsequent get_ask_engine() in the same process (test
        # harnesses, reload) re-ensures tables against the new engine.
        _tables_ready = False
