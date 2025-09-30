import pytest
import fakeredis.aioredis

from typing import Optional

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
BACKEND_ROOT = Path(__file__).resolve().parents[2]
for entry in (ROOT, BACKEND_ROOT):
    entry_str = str(entry)
    if entry_str not in sys.path:
        sys.path.insert(0, entry_str)

from analytics.core.memory_gate import MemoryGate
from analytics.core.session_state import SessionStateSnapshot, SessionStateRepository
from analytics.flows.instrumentation import instrument_events


@pytest.mark.asyncio
async def test_memory_gate_first_run_sets_cold_start(monkeypatch):
    redis_client = fakeredis.aioredis.FakeRedis()
    repository = SessionStateRepository(redis_client=redis_client)
    gate = MemoryGate(repository=repository)

    decision = await gate.evaluate(
        session_id="session-1",
        query="Show quarterly revenue growth",
        flow_label="planner-executor",
    )

    assert decision.policy == "cold_start"
    assert decision.reuse_sql is False
    assert decision.reuse_chart is False
    assert decision.reuse_analysis is False
    stored = await repository.load("session-1")
    assert stored is not None
    assert stored.routing.get("last_decision", {}).get("policy") == "cold_start"


@pytest.mark.asyncio
async def test_memory_gate_reuses_when_query_matches():
    redis_client = fakeredis.aioredis.FakeRedis()
    repository = SessionStateRepository(redis_client=redis_client)
    snapshot = SessionStateSnapshot(
        session_id="session-2",
        last_query="Compare revenue growth",
        last_sql="SELECT * FROM revenue",
        last_chart_spec={"type": "line"},
        last_analysis="Analysis text",
    )
    await repository.save(snapshot)

    gate = MemoryGate(repository=repository)
    decision = await gate.evaluate(
        session_id="session-2",
        query="Compare revenue growth",
        flow_label="planner-executor",
    )

    assert decision.policy == "reuse"
    assert decision.reuse_sql is True
    assert decision.tool_directives["sql_planner"].enabled is False
    assert decision.tool_directives["chart_builder"].enabled is False
    stored = await repository.load("session-2")
    assert stored is not None
    assert stored.routing.get("last_decision", {}).get("policy") == "reuse"


class _DummyFlow:
    flow_label = "planner-executor"

    async def events(self, query: str, session_id: Optional[str] = None):
        yield {"event": "session_started", "data": {"session_id": session_id}}
        yield {
            "event": "classification_complete",
            "data": {"ts": "2025-09-29T12:00:00Z", "is_financial": True, "category": "financial"},
        }
        yield {
            "event": "sql_generated",
            "data": {"sql": "SELECT 1", "ts": "2025-09-29T12:00:01Z"},
        }
        yield {
            "event": "analysis_complete",
            "data": {"analysis": "Done", "ts": "2025-09-29T12:00:02Z"},
        }



@pytest.mark.asyncio
async def test_instrument_events_injects_metadata():
    from analytics.flows import instrumentation

    redis_client = fakeredis.aioredis.FakeRedis()
    repository = SessionStateRepository(redis_client=redis_client)
    instrumentation._memory_gate = MemoryGate(repository=repository)

    flow = _DummyFlow()
    events = []
    async for event in instrument_events(flow, "Compare revenue growth", "session-3", flow.flow_label):
        events.append(event)

    assert events[0]["event"] == "session_started"
    assert events[0]["seq"] == 1

    gating_events = [evt for evt in events if evt["event"] == "memory_gate_decision"]
    assert len(gating_events) == 1
    gate_event = gating_events[0]
    assert gate_event["data"].get("parallel_group") == "memory"

    sql_event = next(evt for evt in events if evt["event"] == "sql_generated")
    assert sql_event["data"].get("parallel_group") == "sql"
    assert sql_event["seq"] > gate_event["seq"]

    # Sequence numbers should increase monotonically
    assert [evt["seq"] for evt in events] == sorted(evt["seq"] for evt in events)

    instrumentation._memory_gate = None
