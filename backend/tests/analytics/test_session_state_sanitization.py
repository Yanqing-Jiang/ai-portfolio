from __future__ import annotations

from types import SimpleNamespace
import pathlib
import sys
import pytest

ROOT = pathlib.Path(__file__).resolve().parents[3]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from analytics.core.session_state import SessionStateSnapshot
from analytics.flows.multi_agent import MultiAgentFlow
from analytics.flows.planner_executor import PlannerPipeline


class _DummyRepository:
    def __init__(self) -> None:
        self.saved: SessionStateSnapshot | None = None
        self._snapshots: dict[str, SessionStateSnapshot] = {}

    async def load(self, session_id: str) -> SessionStateSnapshot | None:
        return self._snapshots.get(session_id)

    async def save(self, snapshot: SessionStateSnapshot) -> None:
        self.saved = snapshot
        self._snapshots[snapshot.session_id] = snapshot


@pytest.mark.asyncio
async def test_multi_agent_persist_bundle_sanitizes(monkeypatch) -> None:
    flow = MultiAgentFlow()
    repo = _DummyRepository()
    monkeypatch.setattr('analytics.flows.multi_agent.get_session_state_repository', lambda: repo)
    flow._session_snapshot = SessionStateSnapshot(session_id='session-demo')  # type: ignore[attr-defined]

    raw_bundle = {'sql': {'attempts': [{'window': slice(None, 1200, None)}]}}

    await flow._persist_bundle(raw_bundle)  # type: ignore[attr-defined]

    assert repo.saved is not None, "Snapshot should be persisted"
    stored = repo.saved.tool_cache['planner_bundle']
    encoded_window = stored['sql']['attempts'][0]['window']
    assert encoded_window == {'start': None, 'stop': 1200, 'step': None}


@pytest.mark.asyncio
async def test_planner_persist_session_state_sanitizes(monkeypatch) -> None:
    monkeypatch.setattr('analytics.flows.planner_executor.get_unified_client', lambda: None)
    pipeline = PlannerPipeline()
    repo = _DummyRepository()
    monkeypatch.setattr('analytics.flows.planner_executor.get_session_state_repository', lambda: repo)

    session_id = 'session-persist'
    repo._snapshots[session_id] = SessionStateSnapshot(session_id=session_id)

    ctx = SimpleNamespace(
        session_id=session_id,
        sql='',
        chart_spec=None,
        analysis='',
        artifacts=SimpleNamespace(to_dict=lambda: {}),
    )

    bundle = {'attempts': [{'window': slice(0, 4, None)}]}

    await pipeline._persist_session_state(ctx, tool_bundle=bundle, record_artifacts=False)

    assert repo.saved is not None, "Snapshot should be persisted"
    stored_bundle = repo.saved.tool_cache['planner_bundle']
    encoded_window = stored_bundle['attempts'][0]['window']
    assert encoded_window == {'start': 0, 'stop': 4, 'step': None}
