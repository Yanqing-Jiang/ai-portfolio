"""SQLAlchemySession factory for each fortune's agent conversation.

The initial narrative, action follow-ups, and free-form Ask turns share one
durable session. This lets a user ask "why did you say my metal is weak?" and
have the answer build on the reading and prior turns without response-id chains.

We use the Agents SDK's ``SQLAlchemySession`` pointed at Supabase so:

1. Memory survives process restarts (Mac Mini reboots, Docker redeploys).
2. Conversation history remains available across process restarts.
3. The SDK handles compaction via ``SessionSettings(limit=…)`` — oldest
   messages beyond the limit are dropped on read. Good enough for a 20-turn
   conversation per fortune.

The session id is ``fortune_{fortune_id}``, so each fortune owns its own
conversation. Sharing across fortunes would require separate session ids
(not needed now).

Why a separate asyncpg engine rather than reusing ``store.get_fortune_pool()``:
SQLAlchemy's async engine owns its own connection pool and can't borrow raw
asyncpg connections. The two pools stay small (max 4 each) so the combined
footprint is bounded. Both go through Supavisor's transaction-mode pooler so
we pass ``statement_cache_size=0`` on the underlying asyncpg driver.
"""

from __future__ import annotations

import asyncio
import copy
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
    """Return a configured ``SQLAlchemySession`` scoped to one fortune.

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


class BufferedAskSession:
    """Session adapter that keeps a model turn private until it is approved.

    The Agents SDK normally writes the user input and raw model output to its
    session before our output guardrail runs.  This adapter reads the durable
    history but buffers all new items in memory.  The route explicitly commits
    them only after the safe response has been durably claimed, preventing a
    rejected or half-completed answer from resurfacing via /conversation.
    """

    def __init__(self, durable_session: object) -> None:
        self._durable_session = durable_session
        self._pending: list[object] = []
        self.session_id = getattr(durable_session, "session_id", "fortune_buffered")
        self.session_settings = getattr(durable_session, "session_settings", None)

    async def get_items(self, limit: int | None = None):
        durable = await self._durable_session.get_items()
        items = [*durable, *self._pending]
        if limit is not None:
            items = items[-limit:]
        return copy.deepcopy(items)

    async def add_items(self, items) -> None:
        self._pending.extend(copy.deepcopy(list(items)))

    async def pop_item(self):
        # Never mutate approved history. Runner only needs to pop items it
        # added during this buffered turn.
        return self._pending.pop() if self._pending else None

    async def clear_session(self) -> None:
        self._pending.clear()

    async def commit(self) -> None:
        if not self._pending:
            return
        pending = copy.deepcopy(self._pending)
        await self._durable_session.add_items(pending)
        self._pending.clear()

    def pending_items(self) -> list[object]:
        return copy.deepcopy(self._pending)

    def discard(self) -> None:
        self._pending.clear()


async def serialize_session_items(
    durable_session: object,
    items: list[object],
) -> list[str]:
    """Serialize buffered items exactly as the Agents SDK persists them."""
    serializer = getattr(durable_session, "_serialize_item", None)
    if serializer is None:
        raise RuntimeError("Ask session serializer unavailable")
    return [await serializer(item) for item in items]


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


_SKIP_ITEM_TYPES = frozenset(
    {
        "function_call",
        "function_call_output",
        "reasoning",
        "tool_call",
        "tool_result",
        "hosted_tool_call",
        "computer_call",
        "computer_call_output",
        "file_search_call",
        "web_search_call",
        "code_interpreter_call",
        "image_generation_call",
        "mcp_call",
        "mcp_list_tools",
        "mcp_approval_request",
    }
)


def _extract_message_text(item: dict) -> str | None:
    """Return plain text for a user/assistant MESSAGE item, else None."""
    if not isinstance(item, dict):
        return None
    item_type = item.get("type")
    if isinstance(item_type, str) and item_type in _SKIP_ITEM_TYPES:
        return None
    role = item.get("role")
    if role not in ("user", "assistant"):
        return None
    # Explicit non-message typed items with a role should still be skipped.
    if isinstance(item_type, str) and item_type not in ("message",):
        return None

    content = item.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for part in content:
            if isinstance(part, str):
                parts.append(part)
                continue
            if not isinstance(part, dict):
                continue
            part_type = part.get("type")
            if part_type in ("input_text", "output_text", "text") and "text" in part:
                parts.append(str(part.get("text") or ""))
            elif "text" in part and part_type not in ("input_image", "refusal"):
                parts.append(str(part.get("text") or ""))
        text = "\n".join(p for p in parts if p)
        return text or None
    return None


def filter_conversation_turns(
    rows: list[tuple[object, object]],
) -> list[dict[str, str]]:
    """Filter deserialized session rows into MemoryPanel turns.

    ``rows`` is a list of ``(message_data, created_at)`` pairs. Only
    user/assistant MESSAGE items are kept; tool/reasoning items are skipped.
    Text is truncated to 2000 chars.
    """
    import json

    turns: list[dict[str, str]] = []
    for raw, created_at in rows:
        try:
            if isinstance(raw, str):
                item = json.loads(raw)
            elif isinstance(raw, dict):
                item = raw
            else:
                continue
        except Exception:
            continue
        text = _extract_message_text(item)
        if text is None:
            continue
        role = item.get("role")
        if role not in ("user", "assistant"):
            continue
        text = _display_turn_text(role, text)
        if text is None:
            continue
        at = ""
        if created_at is not None:
            try:
                at = created_at.isoformat()  # type: ignore[union-attr]
            except Exception:
                at = str(created_at)
        turns.append({"role": role, "text": text[:2000], "at": at})
    return turns


def conversation_turns_from_items(
    items: list[object], created_at: object | None = None, *,
    client_request_id: object | None = None,
    delivery_id: object | None = None,
) -> list[dict[str, str]]:
    """Project approved Ask outbox items when SDK memory is unavailable."""
    turns = filter_conversation_turns([(item, created_at) for item in items])
    for turn in turns:
        if client_request_id is not None:
            turn["client_request_id"] = str(client_request_id)
        if delivery_id is not None:
            turn["delivery_id"] = str(delivery_id)
    return turns


def _display_turn_text(role: str, text: str) -> str | None:
    """Reduce a session message to its human-readable surface.

    Session rows carry the raw run inputs/outputs: user turns can be the
    structured context payload (foundation JSON) and assistant turns the
    structured narrative. MemoryPanel must show conversational text only —
    never internal prompt payloads.
    """
    import json

    stripped = text.strip()
    if not stripped.startswith("{"):
        return stripped
    try:
        obj = json.loads(stripped)
    except ValueError:
        return stripped
    if not isinstance(obj, dict):
        return stripped
    if role == "user":
        intent = obj.get("intent")
        question = obj.get("question") or (
            intent.get("question") if isinstance(intent, dict) else None
        )
        if isinstance(question, str) and question.strip():
            return question.strip()
        return None
    tldr = obj.get("tldr")
    if isinstance(tldr, str) and tldr.strip():
        return tldr.strip()
    return None


async def list_conversation_turns(fortune_id: str) -> list[dict[str, str]]:
    """Return MemoryPanel turns from SQLAlchemySession for one fortune.

    Only user/assistant MESSAGE items are included; tool/reasoning items are
    skipped. Text is truncated to 2000 chars. Empty list when no session.
    """
    session = await get_ask_session(fortune_id)
    if session is None:
        return []

    try:
        from sqlalchemy import select
    except Exception as exc:  # pragma: no cover
        logger.warning("[FORTUNE] conversation list import failed: %s", exc)
        return []

    try:
        # Prefer a direct read so we can include created_at for ``at``.
        await session._ensure_tables()  # type: ignore[attr-defined]
        async with session._session_factory() as sess:  # type: ignore[attr-defined]
            messages = session._messages  # type: ignore[attr-defined]
            stmt = (
                select(messages.c.message_data, messages.c.created_at)
                .where(messages.c.session_id == session.session_id)
                .order_by(messages.c.created_at.asc(), messages.c.id.asc())
            )
            result = await sess.execute(stmt)
            rows = list(result.all())
    except Exception as exc:
        logger.warning("[FORTUNE] conversation list failed for %s: %s", fortune_id, exc)
        return []

    return filter_conversation_turns(rows)
