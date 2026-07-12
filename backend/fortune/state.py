"""Shared fortune run state (Phase 1) — Redis-backed registry.

Replaces process-local ``FortuneStore``. On ``FORTUNE_PIPELINE=v2`` Redis is
required (fail closed at create). On v1 / tests, falls back to an in-memory
backend so the golden path runs without a live Redis.

Keys:
  fortune:session:{fortune_id}  — JSON session blob (TTL 48h)
  fortune:lock:{fortune_id}     — SET NX token lock
  fortune:cancel:{fortune_id}   — cancel flag ("1")
  fortune:run:{run_id}          — owned by events.py (status outside stream)
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import os
import secrets
import time
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

SESSION_KEY_PREFIX = "fortune:session:"
LOCK_KEY_PREFIX = "fortune:lock:"
CANCEL_KEY_PREFIX = "fortune:cancel:"

SESSION_TTL_SECONDS = 48 * 60 * 60
LOCK_TTL_SECONDS = 600  # pipeline stages can be long; refreshed while held
CANCEL_TTL_SECONDS = 48 * 60 * 60


class RuntimeStatus(str, Enum):
    initialized = "initialized"
    awaiting_clarification = "awaiting_clarification"
    streaming = "streaming"
    interrupted = "interrupted"
    complete = "complete"
    error = "error"


class PersonBirthInfo(BaseModel):
    birth_iso: str = Field(..., min_length=1)
    timezone: str | None = None
    gender: str | None = None
    birth_time_unknown: bool = False
    name: str | None = None


class CreateFortuneRequest(BaseModel):
    birth_iso: str = Field(..., min_length=1)
    timezone: str | None = None
    focus: str | None = None
    question: str | None = None
    tone: str | None = None
    birth_time_unknown: bool = False
    gender: str | None = None
    person_b: PersonBirthInfo | None = None


class FortuneSession(BaseModel):
    """Live-run cache. Durable state lives in Supabase via store.py."""

    fortune_id: str
    run_id: str | None = None
    surface_id: str
    request: CreateFortuneRequest
    status: RuntimeStatus = RuntimeStatus.initialized
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    latest_foundation: dict[str, Any] = Field(default_factory=dict)
    latest_narrative: dict[str, Any] | None = None
    latest_guardrail: dict[str, Any] | None = None
    pending_action_id: str | None = None
    pending_action_question: str | None = None
    cancel_requested: bool = False

    def touch(self, new_status: RuntimeStatus | None = None) -> None:
        if new_status is not None:
            self.status = new_status


def pipeline_mode() -> str:
    """Return ``v1`` (default) or ``v2`` from ``FORTUNE_PIPELINE``."""
    try:
        from .config import get_settings
    except ImportError:  # pragma: no cover
        from config import get_settings  # type: ignore[no-redef]
    mode = (getattr(get_settings(), "pipeline", None) or os.getenv("FORTUNE_PIPELINE") or "v1")
    return str(mode).strip().lower() or "v1"


def is_v2_pipeline() -> bool:
    return pipeline_mode() == "v2"


class RedisUnavailable(RuntimeError):
    pass


# ---------------------------------------------------------------------------
# Redis client (separate from events so lifecycles stay clear)
# ---------------------------------------------------------------------------

_redis_singleton: Any = None
_redis_lock: asyncio.Lock | None = None


async def get_state_redis(*, required: bool = False) -> Any:
    global _redis_singleton, _redis_lock
    if _redis_singleton is not None:
        return _redis_singleton
    if _redis_lock is None:
        _redis_lock = asyncio.Lock()
    async with _redis_lock:
        if _redis_singleton is not None:
            return _redis_singleton
        try:
            import redis.asyncio as redis_async
        except ImportError as exc:  # pragma: no cover
            if required:
                raise RedisUnavailable("redis package not installed") from exc
            return None
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        try:
            client = redis_async.from_url(
                redis_url,
                encoding="utf-8",
                decode_responses=True,
            )
            await asyncio.wait_for(client.ping(), timeout=2.0)
            _redis_singleton = client
            logger.info("[FORTUNE-STATE] Redis connected at %s", redis_url)
            return _redis_singleton
        except Exception as exc:
            logger.warning("[FORTUNE-STATE] Redis unavailable (%s): %s", redis_url, exc)
            if required:
                raise RedisUnavailable(str(exc)) from exc
            return None


async def close_state_redis() -> None:
    global _redis_singleton
    if _redis_singleton is None:
        return
    try:
        await _redis_singleton.aclose()
    except Exception:
        pass
    _redis_singleton = None


# ---------------------------------------------------------------------------
# Serialization helpers — foundation analysis is a pydantic model mid-run
# ---------------------------------------------------------------------------

def _session_to_jsonable(session: FortuneSession) -> dict[str, Any]:
    """Dump session for Redis. Drops non-JSON foundation analysis object."""
    data = session.model_dump(mode="json")
    foundation = session.latest_foundation or {}
    # analysis / trace are live objects — keep only JSON-safe siblings in Redis;
    # the owning worker still holds the full in-proc overlay (see RunStateStore).
    safe_foundation = {
        k: v for k, v in foundation.items()
        if k not in {"analysis", "trace", "person_b"}
    }
    person_b = foundation.get("person_b")
    if isinstance(person_b, dict):
        safe_foundation["person_b"] = {
            k: v for k, v in person_b.items() if k not in {"analysis", "trace"}
        }
    data["latest_foundation"] = safe_foundation
    data["status"] = session.status.value
    return data


def _session_from_dict(data: dict[str, Any]) -> FortuneSession:
    return FortuneSession.model_validate(data)


# ---------------------------------------------------------------------------
# Store
# ---------------------------------------------------------------------------

class RunStateStore:
    """Session registry + cancel flags + per-fortune locks.

    Holds an in-process overlay for non-JSON foundation objects (analysis /
    trace) so the pipeline on the owning worker keeps working after Redis
    round-trips. Overlay is process-local by design — see DEBT on task spawn.
    """

    def __init__(self) -> None:
        self._memory: dict[str, FortuneSession] = {}
        self._memory_locks: dict[str, asyncio.Lock] = {}
        self._overlay: dict[str, dict[str, Any]] = {}  # fortune_id -> foundation live objs
        self._lock_tokens: dict[str, str] = {}

    async def _redis(self, *, required: bool = False) -> Any:
        # v2 always requires Redis for durable registry; v1 prefers Redis but
        # falls back to memory so tests/dev without Redis keep working.
        want_required = required or is_v2_pipeline()
        return await get_state_redis(required=want_required)

    def _apply_overlay(self, session: FortuneSession) -> FortuneSession:
        overlay = self._overlay.get(session.fortune_id)
        if not overlay:
            return session
        foundation = dict(session.latest_foundation or {})
        foundation.update(overlay)
        session.latest_foundation = foundation
        return session

    def _capture_overlay(self, session: FortuneSession) -> None:
        foundation = session.latest_foundation or {}
        live = {k: foundation[k] for k in ("analysis", "trace") if k in foundation}
        person_b = foundation.get("person_b")
        if isinstance(person_b, dict) and "analysis" in person_b:
            live["person_b"] = person_b
        if live:
            self._overlay[session.fortune_id] = live

    async def put(self, session: FortuneSession) -> FortuneSession:
        self._capture_overlay(session)
        self._memory[session.fortune_id] = session
        redis = await self._redis(required=False)
        if redis is not None:
            try:
                key = f"{SESSION_KEY_PREFIX}{session.fortune_id}"
                await redis.set(
                    key,
                    json.dumps(_session_to_jsonable(session), ensure_ascii=False),
                    ex=SESSION_TTL_SECONDS,
                )
                if session.cancel_requested:
                    await redis.set(
                        f"{CANCEL_KEY_PREFIX}{session.fortune_id}",
                        "1",
                        ex=CANCEL_TTL_SECONDS,
                    )
            except Exception as exc:
                if is_v2_pipeline():
                    raise RedisUnavailable(str(exc)) from exc
                logger.warning("[FORTUNE-STATE] put redis failed; memory only: %s", exc)
        return session

    async def get(self, fortune_id: str) -> FortuneSession | None:
        # Prefer live memory (has analysis overlay) on the owning worker.
        if fortune_id in self._memory:
            session = self._memory[fortune_id]
            # Refresh cancel flag from Redis so cross-request cancel works.
            if await self.is_cancelled(fortune_id):
                session.cancel_requested = True
            return self._apply_overlay(session)

        redis = await self._redis(required=False)
        if redis is None:
            return None
        try:
            raw = await redis.get(f"{SESSION_KEY_PREFIX}{fortune_id}")
            if not raw:
                return None
            session = _session_from_dict(json.loads(raw))
            if await self.is_cancelled(fortune_id):
                session.cancel_requested = True
            self._memory[fortune_id] = session
            return self._apply_overlay(session)
        except Exception as exc:
            logger.warning("[FORTUNE-STATE] get failed: %s", exc)
            return None

    async def delete(self, fortune_id: str) -> None:
        self._memory.pop(fortune_id, None)
        self._overlay.pop(fortune_id, None)
        redis = await self._redis(required=False)
        if redis is None:
            return
        try:
            await redis.delete(
                f"{SESSION_KEY_PREFIX}{fortune_id}",
                f"{CANCEL_KEY_PREFIX}{fortune_id}",
                f"{LOCK_KEY_PREFIX}{fortune_id}",
            )
        except Exception as exc:
            logger.debug("[FORTUNE-STATE] delete failed: %s", exc)

    async def request_cancel(self, fortune_id: str) -> bool:
        session = await self.get(fortune_id)
        if session is None:
            return False
        session.cancel_requested = True
        await self.put(session)
        redis = await self._redis(required=False)
        if redis is not None:
            try:
                await redis.set(
                    f"{CANCEL_KEY_PREFIX}{fortune_id}",
                    "1",
                    ex=CANCEL_TTL_SECONDS,
                )
            except Exception as exc:
                logger.warning("[FORTUNE-STATE] cancel flag write failed: %s", exc)
        return True

    async def is_cancelled(self, fortune_id: str) -> bool:
        mem = self._memory.get(fortune_id)
        if mem is not None and mem.cancel_requested:
            return True
        redis = await self._redis(required=False)
        if redis is None:
            return bool(mem and mem.cancel_requested)
        try:
            return (await redis.get(f"{CANCEL_KEY_PREFIX}{fortune_id}")) == "1"
        except Exception:
            return bool(mem and mem.cancel_requested)

    async def acquire_lock(self, fortune_id: str, *, ttl: int = LOCK_TTL_SECONDS) -> str | None:
        """SET NX lock with token. Returns token on success, None if held."""
        token = secrets.token_hex(16)
        redis = await self._redis(required=False)
        if redis is None:
            lock = self._memory_locks.setdefault(fortune_id, asyncio.Lock())
            if lock.locked():
                return None
            await lock.acquire()
            self._lock_tokens[fortune_id] = token
            return token
        try:
            ok = await redis.set(
                f"{LOCK_KEY_PREFIX}{fortune_id}",
                token,
                nx=True,
                ex=ttl,
            )
            if ok:
                self._lock_tokens[fortune_id] = token
                return token
            return None
        except Exception as exc:
            if is_v2_pipeline():
                raise RedisUnavailable(str(exc)) from exc
            lock = self._memory_locks.setdefault(fortune_id, asyncio.Lock())
            if lock.locked():
                return None
            await lock.acquire()
            self._lock_tokens[fortune_id] = token
            return token

    async def release_lock(self, fortune_id: str, token: str | None) -> None:
        if not token:
            return
        # Callers release from `finally` blocks that run while their request
        # task is being cancelled (client disconnect). Run the actual release
        # in a shielded task so cancellation can't leak the lock for its
        # full TTL.
        release = asyncio.ensure_future(self._release_lock_inner(fortune_id, token))
        try:
            await asyncio.shield(release)
        except asyncio.CancelledError:
            if not release.done():
                # Give the shielded release one more chance to finish before
                # propagating the caller's cancellation.
                with contextlib.suppress(Exception):
                    await asyncio.wait_for(asyncio.shield(release), timeout=2)
            raise

    async def _release_lock_inner(self, fortune_id: str, token: str) -> None:
        redis = await self._redis(required=False)
        if redis is None:
            if self._lock_tokens.get(fortune_id) == token:
                self._lock_tokens.pop(fortune_id, None)
                lock = self._memory_locks.get(fortune_id)
                if lock is not None and lock.locked():
                    lock.release()
            return
        key = f"{LOCK_KEY_PREFIX}{fortune_id}"
        try:
            current = await redis.get(key)
            if current == token:
                await redis.delete(key)
        except Exception as exc:
            logger.debug("[FORTUNE-STATE] release_lock failed: %s", exc)
        finally:
            self._lock_tokens.pop(fortune_id, None)

    async def refresh_lock(self, fortune_id: str, token: str, *, ttl: int = LOCK_TTL_SECONDS) -> bool:
        redis = await self._redis(required=False)
        if redis is None:
            return self._lock_tokens.get(fortune_id) == token
        key = f"{LOCK_KEY_PREFIX}{fortune_id}"
        try:
            current = await redis.get(key)
            if current != token:
                return False
            await redis.expire(key, ttl)
            return True
        except Exception:
            return False

    def lock_is_held(self, fortune_id: str) -> bool:
        """Best-effort sync probe for v1 409 checks (memory path)."""
        lock = self._memory_locks.get(fortune_id)
        if lock is not None and lock.locked():
            return True
        return fortune_id in self._lock_tokens

    async def lock_is_held_async(self, fortune_id: str) -> bool:
        if self.lock_is_held(fortune_id):
            return True
        redis = await self._redis(required=False)
        if redis is None:
            return False
        try:
            return bool(await redis.exists(f"{LOCK_KEY_PREFIX}{fortune_id}"))
        except Exception:
            return False


_store: RunStateStore | None = None


def get_run_state() -> RunStateStore:
    global _store
    if _store is None:
        _store = RunStateStore()
    return _store


def reset_run_state_for_tests() -> None:
    """Test helper — drop the singleton between cases."""
    global _store
    _store = RunStateStore()
