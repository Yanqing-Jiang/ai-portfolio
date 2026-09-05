"""Unit tests for fortune v2 event backbone + state (mocked Redis).

These do not require a live Redis. Optional live-Redis tests are marked
``redis`` and skip when unreachable.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch
from unittest.mock import AsyncMock, MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fortune import events as fortune_events  # noqa: E402
from fortune.state import (  # noqa: E402
    CreateFortuneRequest,
    FortuneSession,
    get_run_state,
    reset_run_state_for_tests,
)


class _FakeRedis:
    """Minimal in-memory stand-in for redis.asyncio used by events/state."""

    def __init__(self) -> None:
        self.streams: dict[str, list[tuple[str, dict[str, str]]]] = {}
        self.hashes: dict[str, dict[str, str]] = {}
        self.kv: dict[str, str] = {}
        self.ttls: dict[str, int] = {}
        self._seq = 0

    async def ping(self) -> bool:
        return True

    async def xadd(self, key, fields, maxlen=None, approximate=True):
        self._seq += 1
        entry_id = f"1000-{self._seq}"
        self.streams.setdefault(key, []).append((entry_id, dict(fields)))
        if maxlen and len(self.streams[key]) > maxlen:
            self.streams[key] = self.streams[key][-maxlen:]
        return entry_id

    async def expire(self, key, ttl):
        self.ttls[key] = ttl
        return True

    async def xlen(self, key):
        return len(self.streams.get(key, []))

    async def exists(self, *keys):
        n = 0
        for k in keys:
            if k in self.streams or k in self.hashes or k in self.kv:
                n += 1
        return n

    async def xrange(self, key, min="-", max="+", count=None):
        rows = list(self.streams.get(key, []))
        if count:
            rows = rows[:count]
        return rows

    async def xread(self, streams, block=None, count=None):
        out = []
        for key, cursor in streams.items():
            rows = []
            for entry_id, fields in self.streams.get(key, []):
                if cursor in {"0", "0-0"} or entry_id > cursor:
                    rows.append((entry_id, fields))
            if count:
                rows = rows[:count]
            if rows:
                out.append((key, rows))
        return out

    async def hset(self, key, mapping=None, **kwargs):
        self.hashes.setdefault(key, {}).update(mapping or {})
        return True

    async def hgetall(self, key):
        return dict(self.hashes.get(key, {}))

    async def set(self, key, value, ex=None, nx=False):
        if nx and key in self.kv:
            return None
        self.kv[key] = value
        if ex:
            self.ttls[key] = ex
        return True

    async def get(self, key):
        return self.kv.get(key)

    async def delete(self, *keys):
        n = 0
        for k in keys:
            if self.kv.pop(k, None) is not None:
                n += 1
            if self.hashes.pop(k, None) is not None:
                n += 1
            if self.streams.pop(k, None) is not None:
                n += 1
        return n

    async def aclose(self):
        return None


@pytest.fixture
def fake_redis(monkeypatch):
    client = _FakeRedis()
    fortune_events._redis_singleton = client

    async def _get(*, required=False):
        return client

    monkeypatch.setattr(fortune_events, "get_events_redis", _get)
    yield client
    fortune_events._redis_singleton = None


@pytest.mark.asyncio
async def test_publish_and_tail_roundtrip(fake_redis):
    run_id = "run-1"
    env = {"run_id": run_id, "fortune_id": "f1", "seq": 1, "payload": {"hello": True}}
    entry_id = await fortune_events.publish_envelope(run_id, env)
    assert entry_id == "1000-1"
    assert fake_redis.ttls[fortune_events.stream_key(run_id)] == fortune_events.STREAM_TTL_SECONDS

    frames = []
    async for eid, got in fortune_events.tail_envelopes(run_id, after="0-0", block_ms=1):
        frames.append((eid, got))
        break
    assert frames[0][0] == "1000-1"
    assert frames[0][1]["payload"] == {"hello": True}


@pytest.mark.asyncio
async def test_cursor_predates_window_resync(fake_redis):
    run_id = "run-2"
    await fortune_events.publish_envelope(run_id, {"seq": 1, "payload": {"a": 1}})
    assert await fortune_events.needs_resync(
        run_id, fortune_events.encode_cursor(run_id, "999-1"),
    ) is True
    assert await fortune_events.needs_resync(run_id, "0-0") is False
    assert await fortune_events.needs_resync(
        run_id, fortune_events.encode_cursor(run_id, "1000-1"),
    ) is False


@pytest.mark.asyncio
async def test_cursor_from_another_run_always_resyncs(fake_redis):
    run_id = "run-target"
    await fortune_events.publish_envelope(run_id, {"seq": 1, "payload": {"a": 1}})
    newer_foreign_cursor = fortune_events.encode_cursor("run-newer", "9999-1")
    assert await fortune_events.needs_resync(run_id, newer_foreign_cursor) is True
    # Raw legacy IDs have no trustworthy run identity and fail closed.
    assert await fortune_events.needs_resync(run_id, "9999-1") is True


@pytest.mark.asyncio
async def test_missing_stream_needs_resync(fake_redis):
    cursor = fortune_events.encode_cursor("missing-run", "1000-1")
    assert await fortune_events.needs_resync("missing-run", cursor) is True


@pytest.mark.asyncio
async def test_run_record_outside_stream(fake_redis):
    await fortune_events.set_run_record("r1", fortune_id="f1", status="complete")
    rec = await fortune_events.get_run_record("r1")
    assert rec["status"] == "complete"
    assert rec["fortune_id"] == "f1"
    assert fortune_events.run_hash_key("r1") in fake_redis.ttls


@pytest.mark.asyncio
async def test_state_memory_fallback_without_redis(monkeypatch):
    reset_run_state_for_tests()

    async def _none(*, required=False):
        if required:
            raise fortune_events.RedisUnavailable("down")
        return None

    monkeypatch.setattr("fortune.state.get_state_redis", _none)
    store = get_run_state()
    session = FortuneSession(
        fortune_id="f-mem",
        run_id="r-mem",
        surface_id="fortune_main",
        request=CreateFortuneRequest(birth_iso="1990-01-01T00:00:00"),
    )
    await store.put(session)
    got = await store.get("f-mem")
    assert got is not None
    assert got.run_id == "r-mem"
    await store.request_cancel("f-mem")
    assert await store.is_cancelled("f-mem") is True


@pytest.mark.asyncio
async def test_create_fails_closed_without_redis(monkeypatch):
    fortune_events._redis_singleton = None

    async def _boom(*, required=False):
        if required:
            raise fortune_events.RedisUnavailable("down")
        return None

    with patch.object(fortune_events, "get_events_redis", _boom):
        with pytest.raises(fortune_events.RedisUnavailable):
            await fortune_events.get_events_redis(required=True)


@pytest.mark.redis
@pytest.mark.asyncio
async def test_live_redis_publish_if_available():
    fortune_events._redis_singleton = None
    client = await fortune_events.get_events_redis(required=False)
    if client is None:
        pytest.skip("redis://localhost:6379 not reachable")
    run_id = "live-test-run"
    entry = await fortune_events.publish_envelope(
        run_id, {"run_id": run_id, "fortune_id": "f", "seq": 1, "payload": {"ok": True}},
    )
    assert entry and "-" in entry
    await client.delete(fortune_events.stream_key(run_id))


@pytest.mark.asyncio
async def test_release_lock_survives_caller_cancellation(monkeypatch):
    """Client disconnect cancels the request task mid-``finally``; the lock
    release must still reach Redis or the fortune stays busy for the TTL."""
    import asyncio

    reset_run_state_for_tests()
    client = _FakeRedis()
    orig_get = client.get

    async def slow_get(key):
        await asyncio.sleep(0.05)
        return await orig_get(key)

    client.get = slow_get

    async def _redis(*, required=False):
        await asyncio.sleep(0)
        return client

    monkeypatch.setattr("fortune.state.get_state_redis", _redis)
    store = get_run_state()
    token = await store.acquire_lock("f-cancel")
    assert token
    assert client.kv

    task = asyncio.create_task(store.release_lock("f-cancel", token))
    await asyncio.sleep(0)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    for _ in range(100):
        if not client.kv:
            break
        await asyncio.sleep(0.01)
    assert not client.kv, "lock key leaked after caller cancellation"
    assert await store.acquire_lock("f-cancel")


@pytest.mark.asyncio
async def test_cancelled_background_run_terminalizes_sql_and_redis(monkeypatch):
    """A graceful worker restart cannot leave a reconnect stuck streaming."""
    import asyncio
    import uuid
    from fortune import pipeline
    from fortune.state import RuntimeStatus

    session = FortuneSession(
        fortune_id="11111111-1111-1111-1111-111111111111",
        run_id="22222222-2222-2222-2222-222222222222",
        surface_id="fortune_main",
        request=CreateFortuneRequest(birth_iso="1990-01-01T00:00:00"),
    )
    store = MagicMock()
    store.put = AsyncMock()
    store.release_lock = AsyncMock()
    store.evict_local = MagicMock()
    repo = MagicMock(available=True)
    repo.update_run_status = AsyncMock()

    async def _blocked_frames(*_args, **_kwargs):
        await asyncio.Event().wait()
        if False:
            yield ""

    monkeypatch.setattr(pipeline, "iter_fortune_sse_frames", _blocked_frames)
    monkeypatch.setattr(pipeline, "get_repository", AsyncMock(return_value=repo))
    monkeypatch.setattr(fortune_events, "set_run_record", AsyncMock())
    terminal = AsyncMock()
    monkeypatch.setattr(fortune_events, "publish_interrupted_terminal", terminal)

    task = asyncio.create_task(
        pipeline.run_and_publish(session, store=store, lock_token="owned"),
    )
    await asyncio.sleep(0)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    assert session.status is RuntimeStatus.interrupted
    repo.update_run_status.assert_awaited_once_with(
        uuid.UUID(session.run_id),
        "interrupted",
        error_message="Reading interrupted by a service restart. Please retry.",
    )
    terminal.assert_awaited_once()
    terminal_call = terminal.await_args.kwargs
    assert terminal_call["fortune_id"] == session.fortune_id
    final_status = fortune_events.set_run_record.await_args_list[-1].kwargs
    assert final_status["status"] == "interrupted"
    store.release_lock.assert_awaited_once_with(session.fortune_id, "owned")


@pytest.mark.asyncio
async def test_user_pause_publishes_terminal_frames(monkeypatch):
    from fortune import pipeline
    from fortune.state import RuntimeStatus

    session = FortuneSession(
        fortune_id="11111111-1111-1111-1111-111111111111",
        run_id="22222222-2222-2222-2222-222222222222",
        surface_id="fortune_main",
        request=CreateFortuneRequest(birth_iso="1990-01-01T00:00:00"),
    )
    store = MagicMock()
    store.release_lock = AsyncMock()

    async def paused_frames(*args, **kwargs):
        session.touch(RuntimeStatus.interrupted)
        if False:
            yield ""

    monkeypatch.setattr(pipeline, "iter_fortune_sse_frames", paused_frames)
    monkeypatch.setattr(fortune_events, "set_run_record", AsyncMock())
    terminal = AsyncMock(return_value=True)
    monkeypatch.setattr(fortune_events, "publish_interrupted_terminal", terminal)
    await pipeline.run_and_publish(session, store=store, lock_token="owned")
    terminal.assert_awaited_once_with(
        session.run_id, fortune_id=session.fortune_id,
        message="Reading paused by user",
    )
    assert fortune_events.set_run_record.await_args.kwargs["status"] == "interrupted"


def test_session_serialization_excludes_live_trace_before_dump():
    from fortune.state import _session_to_jsonable
    from pydantic import BaseModel

    class Balance(BaseModel):
        wood: float

    session = FortuneSession(
        fortune_id="test", surface_id="fortune_main",
        request=CreateFortuneRequest(birth_iso="1990-01-01T00:00:00"),
        latest_foundation={
            "trace": object(), "analysis": object(), "pillars": {"day": "甲子"},
            "elements": Balance(wood=1.5),
            "person_b": {"analysis": object(), "trace": object(), "pillars": {}},
        },
    )
    dumped = _session_to_jsonable(session)
    assert dumped["latest_foundation"] == {
        "pillars": {"day": "甲子"}, "elements": {"wood": 1.5}, "person_b": {"pillars": {}},
    }
    assert "trace" in session.latest_foundation


def test_migration_runner_uses_transaction_scoped_lock() -> None:
    source = (
        Path(__file__).resolve().parent.parent / "scripts" / "apply_migration.py"
    ).read_text(encoding="utf-8")
    assert "pg_advisory_xact_lock" in source
    assert "pg_advisory_lock(" not in source
    assert "pg_advisory_unlock" not in source
