"""Redis-backed OpenAI ``previous_response_id`` chain for Ask follow-ups.

PR-4 of the latency refactor — paired with PR-3 (compat reasoning flip
to ``low``). Why this exists:

- Compat narrative now ships ``store=True`` so subsequent Ask turns can
  pass ``previous_response_id=<last>`` to OpenAI for ~30-50% latency
  cut on follow-up reasoning. The chain map (fortune_id → last
  response_id) must survive across gunicorn workers (the demo runs 6),
  which rules out per-process in-memory state.
- ``portfolio-redis`` was already healthy on the docker network at PR-4
  time; reusing it instead of standing up a new dependency keeps the
  infra surface flat.
- Yanqing's explicit privacy posture: store=True is acceptable IFF the
  chain entries are deleted when the user's session ends. We implement
  "session end" as a Redis TTL (default 1h) plus a best-effort fire-
  and-forget OpenAI ``DELETE /v1/responses/{id}`` call once the key
  approaches expiry. Effective OpenAI-side retention: ~1h, vs.
  OpenAI's default ≥30 days for stored responses.

What this module does NOT do:
- Persist conversation history (that's ``SQLAlchemySession`` in
  ``session_store.py`` — Opus's option (ii)).
- Multi-tenant identity scoping (single fortune = single user per
  PR-4 scope; cross-tab isolation is a follow-up).

What it DOES do:
- ``get_response_chain(fortune_id)`` reads the last response_id.
- ``set_response_chain(fortune_id, response_id)`` writes + schedules
  a deferred cleanup task.
- ``clear_response_chain(fortune_id)`` evicts proactively (e.g., on
  explicit session-end signal from the frontend, future enhancement).
- Graceful degradation: if Redis is unreachable, every primitive
  returns ``None`` / no-op and the Ask handler reports
  ``chainStatus="disabled"`` so the UX is non-fatal.
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Any, Optional

logger = logging.getLogger(__name__)

# --- Function/Class Map ---
# Function: get_chain_redis — lazy singleton AsyncRedis pointed at REDIS_URL.
# Function: get_response_chain — read last_response_id for a fortune.
# Function: set_response_chain — write last_response_id + schedule expiry.
# Function: clear_response_chain — explicit early eviction.
# Function: _schedule_openai_delete — fire-and-forget OpenAI DELETE after TTL.
# Purpose: Ephemeral OpenAI response chain shared across gunicorn workers.


# Key shapes (kept in one place so future migrations are mechanical).
_CHAIN_KEY_PREFIX = "fortune:chain:"
_SESSION_RESPONSES_PREFIX = "fortune:session_responses:"


def _chain_key(fortune_id: str) -> str:
    return f"{_CHAIN_KEY_PREFIX}{fortune_id}"


def _session_responses_key(fortune_id: str) -> str:
    return f"{_SESSION_RESPONSES_PREFIX}{fortune_id}"


_redis_singleton: Any = None
_redis_lock: asyncio.Lock | None = None


def _ttl_seconds() -> int:
    """Read TTL from settings; falls back to env then 1h default."""
    try:
        from .config import get_settings
    except ImportError:  # pragma: no cover
        from config import get_settings  # type: ignore[no-redef]
    return int(getattr(get_settings(), "ask_chain_ttl_seconds", 3600) or 3600)


def _chaining_enabled() -> bool:
    try:
        from .config import get_settings
    except ImportError:  # pragma: no cover
        from config import get_settings  # type: ignore[no-redef]
    return bool(getattr(get_settings(), "ask_chaining_enabled", False))


async def get_chain_redis() -> Any:
    """Lazy AsyncRedis singleton. Returns ``None`` when Redis is unreachable
    OR when ``FORTUNE_ASK_CHAINING_ENABLED=false`` — callers degrade safely.

    We avoid importing the global ``rate_limiter.redis_pool`` because it
    is configured with ``decode_responses=True`` (string mode) which is
    what we want here too — but the rate limiter pool may be ``None`` in
    dev/test environments while we still want chain semantics, and we
    want a separate connection lifecycle so disposing one doesn't break
    the other.
    """
    global _redis_singleton, _redis_lock
    if not _chaining_enabled():
        return None
    if _redis_singleton is not None:
        return _redis_singleton
    if _redis_lock is None:
        _redis_lock = asyncio.Lock()
    async with _redis_lock:
        if _redis_singleton is not None:
            return _redis_singleton
        try:
            import redis.asyncio as redis_async  # type: ignore[import]
        except ImportError:  # pragma: no cover
            logger.warning("[CHAIN] redis package not installed — chain disabled")
            return None
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        try:
            client = redis_async.from_url(
                redis_url,
                encoding="utf-8",
                decode_responses=True,
            )
            # Verify reachability with a cheap ping before caching.
            await asyncio.wait_for(client.ping(), timeout=2.0)
            _redis_singleton = client
            logger.info("[CHAIN] chain Redis connected at %s", redis_url)
            return _redis_singleton
        except Exception as exc:
            logger.warning("[CHAIN] chain Redis unavailable (%s): %s", redis_url, exc)
            return None


async def get_response_chain(fortune_id: str) -> Optional[str]:
    """Return the last OpenAI response_id for ``fortune_id`` or ``None``.

    Cheap GET — no DB roundtrip. Safe to call on every Ask request.
    """
    client = await get_chain_redis()
    if client is None:
        return None
    try:
        return await client.get(_chain_key(fortune_id))
    except Exception as exc:
        logger.warning("[CHAIN] GET %s failed: %s", fortune_id, exc)
        return None


async def set_response_chain(
    fortune_id: str,
    response_id: str,
    *,
    schedule_cleanup: bool = True,
) -> bool:
    """Persist ``response_id`` as the new chain head for ``fortune_id``.

    Uses ``SETEX`` with the configured TTL so the key naturally expires
    after inactivity. Also appends to a per-fortune set tracked under
    ``session_responses:`` so a future explicit-cleanup endpoint can
    DELETE every response_id this user has accumulated.

    When ``schedule_cleanup`` is True (default), we kick off a fire-
    and-forget background task that sleeps for the TTL and then issues
    ``DELETE /v1/responses/{id}`` against OpenAI — implementing
    Yanqing's "deleted when user leaves the interface" promise even
    when the user just walks away without an explicit signal.

    Returns True on success, False if Redis was unreachable.
    """
    client = await get_chain_redis()
    if client is None:
        return False
    ttl = _ttl_seconds()
    try:
        await client.setex(_chain_key(fortune_id), ttl, response_id)
        await client.sadd(_session_responses_key(fortune_id), response_id)
        await client.expire(_session_responses_key(fortune_id), ttl)
    except Exception as exc:
        logger.warning("[CHAIN] SETEX %s failed: %s", fortune_id, exc)
        return False
    if schedule_cleanup:
        # Fire-and-forget; on backend restart these tasks vanish but the
        # Redis TTL still expires the key, so the worst case is OpenAI
        # retains the response on its own retention schedule. Trade-off
        # accepted; survives all "user closes the tab" paths.
        try:
            asyncio.create_task(_schedule_openai_delete(response_id, delay_s=ttl))
        except RuntimeError:
            # No running loop (test harness importing the module).
            pass
    return True


async def clear_response_chain(fortune_id: str) -> int:
    """Explicit early eviction — proactively DELETE every OpenAI
    response associated with the fortune and drop the chain pointer.

    Returns the count of response_ids successfully deleted on OpenAI's
    side (best-effort; 404s and network errors are swallowed).
    Intended for a future ``POST /api/fortune/{id}/session-end``
    endpoint or a frontend ``beforeunload`` signal.
    """
    client = await get_chain_redis()
    if client is None:
        return 0
    deleted = 0
    try:
        ids = await client.smembers(_session_responses_key(fortune_id))
        for rid in ids:
            ok = await _openai_delete_response(rid)
            if ok:
                deleted += 1
        await client.delete(
            _chain_key(fortune_id),
            _session_responses_key(fortune_id),
        )
    except Exception as exc:
        logger.warning("[CHAIN] CLEAR %s failed: %s", fortune_id, exc)
    return deleted


async def _schedule_openai_delete(response_id: str, *, delay_s: int) -> None:
    """Sleep then call OpenAI DELETE. Background fire-and-forget."""
    try:
        await asyncio.sleep(delay_s)
        await _openai_delete_response(response_id)
    except asyncio.CancelledError:  # pragma: no cover
        raise
    except Exception as exc:  # pragma: no cover
        logger.debug("[CHAIN] deferred cleanup failed for %s: %s", response_id, exc)


async def _openai_delete_response(response_id: str) -> bool:
    """Issue ``DELETE /v1/responses/{id}`` against OpenAI. Best-effort.

    Returns True if the response was either deleted or already gone (404).
    Errors are logged and swallowed — we never want chain cleanup to
    block a user-facing path.
    """
    try:
        try:
            from .config import get_settings
        except ImportError:  # pragma: no cover
            from config import get_settings  # type: ignore[no-redef]
        api_key = get_settings().openai_api_key
        if not api_key:
            return False
        # Use httpx instead of the openai SDK to avoid an event-loop
        # mismatch with the SDK's per-call client construction.
        import httpx
        async with httpx.AsyncClient(timeout=5.0) as http:
            resp = await http.delete(
                f"https://api.openai.com/v1/responses/{response_id}",
                headers={"Authorization": f"Bearer {api_key}"},
            )
        if resp.status_code in (200, 204, 404):
            return True
        logger.debug(
            "[CHAIN] DELETE %s returned %s: %s",
            response_id, resp.status_code, resp.text[:120],
        )
    except Exception as exc:
        logger.debug("[CHAIN] DELETE %s exception: %s", response_id, exc)
    return False


async def close_chain_redis() -> None:
    """Dispose of the chain Redis singleton on shutdown."""
    global _redis_singleton
    if _redis_singleton is None:
        return
    try:
        await _redis_singleton.aclose()
    except Exception:  # pragma: no cover
        pass
    finally:
        _redis_singleton = None
