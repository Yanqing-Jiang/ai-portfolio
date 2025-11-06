from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest

from analytics.core.session_state import SessionStateRepository, SessionStateSnapshot


@pytest.mark.asyncio
async def test_session_state_repository_falls_back_when_redis_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    repo = SessionStateRepository()

    async def _no_redis(self) -> None:  # type: ignore[return-value]
        return None

    monkeypatch.setattr(SessionStateRepository, "_ensure_redis", _no_redis, raising=False)

    snapshot = SessionStateSnapshot(session_id="fallback-session")
    snapshot.record_outputs(analysis="Baseline analysis narrative")

    await repo.save(snapshot)
    assert getattr(repo, "_fallback_store", {}), "Expected fallback store to capture the snapshot when Redis is unavailable"

    restored = await repo.load("fallback-session")
    assert restored is not None
    assert restored.session_id == "fallback-session"
    assert restored.last_analysis == "Baseline analysis narrative"

    await repo.delete("fallback-session")


@pytest.mark.asyncio
async def test_session_state_repository_expires_stale_snapshot(monkeypatch: pytest.MonkeyPatch) -> None:
    repo = SessionStateRepository()

    async def _no_redis(self) -> None:  # type: ignore[return-value]
        return None

    monkeypatch.setattr(SessionStateRepository, "_ensure_redis", _no_redis, raising=False)

    snapshot = SessionStateSnapshot(session_id="expire-session")
    await repo.save(snapshot)

    key = repo._key("expire-session")
    expires_at, payload = repo._fallback_store[key]
    data = json.loads(payload)
    data["updated_at"] = (datetime.now(timezone.utc) - timedelta(minutes=15)).isoformat()
    repo._fallback_store[key] = (expires_at, json.dumps(data, default=str))

    restored = await repo.load("expire-session")
    assert restored is None
    assert key not in repo._fallback_store

@pytest.mark.asyncio
async def test_agents_session_ttl_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv('AGENTS_SESSION_TTL_MINUTES', '1')
    repo = SessionStateRepository()
    assert repo._ttl_seconds == 60
    snapshot = SessionStateSnapshot(session_id='agents-ttl')
    await repo.save(snapshot)

    key = repo._key('agents-ttl')
    expires_at, payload = repo._fallback_store[key]
    repo._fallback_store[key] = (expires_at - 120, payload)

    restored = await repo.load('agents-ttl')
    assert restored is None
    assert key not in repo._fallback_store
