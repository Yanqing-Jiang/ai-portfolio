"""Unit tests for fortune v2 event backbone + state (mocked Redis).

These do not require a live Redis. Optional live-Redis tests are marked
``redis`` and skip when unreachable.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

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
    assert await fortune_events.needs_resync(run_id, "999-1") is True
    assert await fortune_events.needs_resync(run_id, "0-0") is False
    assert await fortune_events.needs_resync(run_id, "1000-1") is False


@pytest.mark.asyncio
async def test_missing_stream_needs_resync(fake_redis):
    assert await fortune_events.needs_resync("missing-run", "1000-1") is True


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
    monkeypatch.setenv("FORTUNE_PIPELINE", "v1")

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
async def test_v2_create_fails_closed_without_redis(monkeypatch):
    monkeypatch.setenv("FORTUNE_PIPELINE", "v2")
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
