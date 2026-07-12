"""Redis Streams event backbone for fortune runs (Phase 1 / v2 pipeline).

Stream key: ``fortune:events:{run_id}``
Run status hash (outside the expiring stream): ``fortune:run:{run_id}``

Publisher stores the same JSON envelope the SSE layer sends today
(``{run_id, fortune_id, seq, payload}``). CJK scrubbing stays in
``stream_bridge`` emitters — frames arrive here already scrubbed.

Resume cursors are Redis stream entry IDs (strings), not numeric ordinals.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, AsyncIterator

logger = logging.getLogger(__name__)

STREAM_KEY_PREFIX = "fortune:events:"
RUN_HASH_PREFIX = "fortune:run:"
STREAM_MAXLEN = 2000
STREAM_TTL_SECONDS = 24 * 60 * 60
RUN_HASH_TTL_SECONDS = 48 * 60 * 60  # outlives the stream window

_redis_singleton: Any = None
_redis_lock = None


class RedisUnavailable(RuntimeError):
    """Raised when Redis cannot be reached and the v2 path requires it."""


def stream_key(run_id: str) -> str:
    return f"{STREAM_KEY_PREFIX}{run_id}"


def run_hash_key(run_id: str) -> str:
    return f"{RUN_HASH_PREFIX}{run_id}"


async def get_events_redis(*, required: bool = False) -> Any:
    """Lazy AsyncRedis singleton for the event backbone.

    When ``required`` is True, raises ``RedisUnavailable`` instead of returning
    None — used by v2 create (fail closed).
    """
    global _redis_singleton, _redis_lock
    import asyncio

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
            logger.warning("[FORTUNE-EVENTS] redis package not installed")
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
            logger.info("[FORTUNE-EVENTS] Redis connected at %s", redis_url)
            return _redis_singleton
        except Exception as exc:
            logger.warning("[FORTUNE-EVENTS] Redis unavailable (%s): %s", redis_url, exc)
            if required:
                raise RedisUnavailable(str(exc)) from exc
            return None


async def close_events_redis() -> None:
    global _redis_singleton
    if _redis_singleton is None:
        return
    try:
        await _redis_singleton.aclose()
    except Exception:
        pass
    _redis_singleton = None


def serialize_envelope(envelope: dict[str, Any]) -> str:
    """Serialize a frame envelope to the wire JSON the SSE layer sends today.

    Matches ``pipeline._emit`` / legacy routes ``json.dumps(env)`` defaults so
    v1 and v2 clients see identical ``data:`` payloads.
    """
    return json.dumps(envelope)


def format_sse(envelope: dict[str, Any], *, event_id: str | None = None) -> str:
    """Format an envelope as an SSE chunk, optionally with a Redis stream id."""
    data = serialize_envelope(envelope)
    if event_id:
        return f"id: {event_id}\ndata: {data}\n\n"
    return f"data: {data}\n\n"


def format_typed_sse(event_type: str, body: dict[str, Any], *, event_id: str | None = None) -> str:
    """Format a named SSE event (e.g. ``resync_required``)."""
    data = json.dumps(body)
    parts: list[str] = []
    if event_id:
        parts.append(f"id: {event_id}")
    parts.append(f"event: {event_type}")
    parts.append(f"data: {data}")
    parts.append("")
    parts.append("")
    return "\n".join(parts)


async def set_run_record(
    run_id: str,
    *,
    fortune_id: str,
    status: str,
    error_message: str | None = None,
    client: Any | None = None,
) -> None:
    """Persist terminal/non-terminal run status OUTSIDE the expiring stream."""
    redis = client or await get_events_redis()
    if redis is None:
        return
    key = run_hash_key(run_id)
    mapping = {
        "fortune_id": fortune_id,
        "status": status,
        "run_id": run_id,
    }
    if error_message is not None:
        mapping["error_message"] = error_message[:500]
    try:
        await redis.hset(key, mapping=mapping)
        await redis.expire(key, RUN_HASH_TTL_SECONDS)
    except Exception as exc:
        logger.warning("[FORTUNE-EVENTS] set_run_record failed: %s", exc)


async def get_run_record(run_id: str, *, client: Any | None = None) -> dict[str, str] | None:
    redis = client or await get_events_redis()
    if redis is None:
        return None
    try:
        data = await redis.hgetall(run_hash_key(run_id))
        return data or None
    except Exception as exc:
        logger.warning("[FORTUNE-EVENTS] get_run_record failed: %s", exc)
        return None


async def publish_envelope(
    run_id: str,
    envelope: dict[str, Any],
    *,
    client: Any | None = None,
) -> str | None:
    """XADD one frame. Returns the Redis stream entry id, or None on failure."""
    redis = client or await get_events_redis()
    if redis is None:
        logger.error("[FORTUNE-EVENTS] publish skipped — Redis unavailable run=%s", run_id)
        return None
    key = stream_key(run_id)
    payload = serialize_envelope(envelope)
    try:
        entry_id = await redis.xadd(
            key,
            {"envelope": payload},
            maxlen=STREAM_MAXLEN,
            approximate=True,
        )
        # Refresh TTL on every write so active runs don't expire mid-flight.
        await redis.expire(key, STREAM_TTL_SECONDS)
        return str(entry_id)
    except Exception as exc:
        logger.error("[FORTUNE-EVENTS] XADD failed run=%s: %s", run_id, exc)
        return None


async def stream_length(run_id: str, *, client: Any | None = None) -> int:
    redis = client or await get_events_redis()
    if redis is None:
        return 0
    try:
        return int(await redis.xlen(stream_key(run_id)))
    except Exception:
        return 0


async def stream_exists(run_id: str, *, client: Any | None = None) -> bool:
    redis = client or await get_events_redis()
    if redis is None:
        return False
    try:
        return bool(await redis.exists(stream_key(run_id)))
    except Exception:
        return False


async def first_stream_id(run_id: str, *, client: Any | None = None) -> str | None:
    """Return the earliest retained stream entry id, or None if empty/missing."""
    redis = client or await get_events_redis()
    if redis is None:
        return None
    try:
        rows = await redis.xrange(stream_key(run_id), min="-", max="+", count=1)
        if not rows:
            return None
        return str(rows[0][0])
    except Exception:
        return None


def _parse_stream_id(stream_id: str) -> tuple[int, int]:
    """Parse ``<ms>-<seq>`` into ints for correct ordering (not lexicographic)."""
    try:
        ms_s, seq_s = stream_id.split("-", 1)
        return int(ms_s), int(seq_s)
    except (TypeError, ValueError):
        return (-1, -1)


def cursor_predates_window(after: str, first_id: str | None) -> bool:
    """True when the client cursor is older than the first retained entry."""
    if not after or after in {"0", "0-0", "$"}:
        return False
    if first_id is None:
        return False
    return _parse_stream_id(after) < _parse_stream_id(first_id)


async def needs_resync(
    run_id: str,
    after: str | None,
    *,
    client: Any | None = None,
) -> bool:
    """Detect trim-gap / expired-stream cases that require snapshot rehydrate."""
    if not after or after in {"0", "0-0"}:
        return False
    redis = client or await get_events_redis()
    exists = await stream_exists(run_id, client=redis)
    if not exists:
        # Stream gone but caller may still know the run — resync.
        return True
    first = await first_stream_id(run_id, client=redis)
    if first is None:
        return True
    return cursor_predates_window(after, first)


async def tail_envelopes(
    run_id: str,
    *,
    after: str = "0-0",
    block_ms: int = 2000,
    client: Any | None = None,
) -> AsyncIterator[tuple[str, dict[str, Any]]]:
    """XREAD frames after ``after`` (exclusive). Independent cursors — no groups.

    Yields ``(entry_id, envelope_dict)``. Stops when a terminal envelope is
    observed (``payload.done`` / meta complete|error / typed cancel) OR when
    the run hash says the run is finished and the stream is drained.
    """
    redis = client or await get_events_redis()
    if redis is None:
        return
    key = stream_key(run_id)
    cursor = after if after else "0-0"
    idle_rounds = 0
    max_idle_after_terminal = 2

    while True:
        try:
            rows = await redis.xread({key: cursor}, block=block_ms, count=64)
        except Exception as exc:
            logger.error("[FORTUNE-EVENTS] XREAD failed run=%s: %s", run_id, exc)
            return

        if not rows:
            record = await get_run_record(run_id, client=redis)
            status = (record or {}).get("status", "")
            if status in {
                "complete", "done", "failed_guardrail", "error", "interrupted", "failed",
            }:
                idle_rounds += 1
                if idle_rounds >= max_idle_after_terminal:
                    return
            else:
                idle_rounds = 0
            # Stream key may have expired mid-wait.
            if not await stream_exists(run_id, client=redis):
                return
            continue

        idle_rounds = 0
        for _stream_name, messages in rows:
            for entry_id, fields in messages:
                cursor = str(entry_id)
                raw = fields.get("envelope") or fields.get(b"envelope")
                if isinstance(raw, bytes):
                    raw = raw.decode("utf-8")
                try:
                    envelope = json.loads(raw) if isinstance(raw, str) else {}
                except (TypeError, ValueError):
                    envelope = {"raw": raw}
                yield cursor, envelope
                if _envelope_is_terminal(envelope):
                    return


def _envelope_is_terminal(envelope: dict[str, Any]) -> bool:
    """Only the explicit ``done`` frame ends the tail immediately.

    The bridge emits terminal frames in the order meta-status → audit →
    ``{"done": true}``. Stopping on the meta-status frame (as this helper
    originally did) dropped audit/done from the first connection and forced
    clients into a reconnect to drain them. Runs that never publish a done
    frame are closed by the run-record idle check in ``tail_envelopes``.
    """
    if envelope.get("done") is True:
        return True
    payload = envelope.get("payload")
    if isinstance(payload, dict) and payload.get("done") is True:
        return True
    return False


