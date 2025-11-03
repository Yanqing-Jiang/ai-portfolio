from __future__ import annotations

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
