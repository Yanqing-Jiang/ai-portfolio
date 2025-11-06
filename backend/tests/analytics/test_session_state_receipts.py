from __future__ import annotations

from datetime import datetime, timedelta
from types import SimpleNamespace
from typing import Any, Dict, Optional

import pytest

from analytics.artifacts.models import MarketArtifact, WebContextArtifact
from analytics.flows.planner_executor import PlannerExecutorFlow, ToolInvocationReceipt
from analytics.flows.single_agent_tools import SingleAgentController
from analytics.flows.schedulers import FlowMode
from analytics.core.session_state import SessionStateSnapshot


class _InMemorySessionStateRepository:
    def __init__(self) -> None:
        self._store: Dict[str, Dict[str, Any]] = {}

    async def load(self, session_id: str) -> Optional[SessionStateSnapshot]:
        payload = self._store.get(session_id)
        if payload is None:
            return None
        return SessionStateSnapshot(**payload)

    async def save(self, snapshot: SessionStateSnapshot) -> None:
        self._store[snapshot.session_id] = snapshot.snapshot()


def _is_receipt_fresh(receipt: ToolInvocationReceipt, ttl_seconds: int) -> bool:
    try:
        timestamp = datetime.fromisoformat(receipt.timestamp)
    except ValueError:
        timestamp = datetime.fromisoformat(receipt.timestamp.rstrip("Z"))
    delta = datetime.utcnow() - timestamp
    return delta.total_seconds() <= ttl_seconds


@pytest.mark.asyncio
async def test_market_and_web_receipts_persist_in_snapshot(monkeypatch: pytest.MonkeyPatch) -> None:
    repo = _InMemorySessionStateRepository()
    monkeypatch.setattr("analytics.core.session_state.get_session_state_repository", lambda: repo)
    monkeypatch.setattr("analytics.flows.planner_executor.get_session_state_repository", lambda: repo)

    flow = PlannerExecutorFlow(flow_mode=FlowMode.SINGLE_AGENT)
    ctx = await flow.initialize_context("ACME margin outlook", session_id="session-receipts")
    ctx.artifacts.market = MarketArtifact(
        query=ctx.query,
        tickers=["ACME"],
        snapshot={"widget": {"quote": 123}},
    )
    ctx.artifacts.web = WebContextArtifact(
        query=ctx.query,
        summary="Benchmarked sentiment.",
        snippets=[{"title": "Key insight", "url": "https://example.com"}],
        search_id="search-1",
        from_cache=False,
    )

    event_market_a = {
        "event": "tool_parallel_result",
        "data": {
            "tool": "market_question_a",
            "status": "completed",
            "payload": {
                "stock_widget": {"quote": 123},
                "question_id": "market_question_a",
            },
            "metadata": {"question_id": "market_question_a"},
            "elapsed_ms": 1200,
            "parallel_group": "single_agent_market",
            "lane": "market",
        },
    }
    event_market_b = {
        "event": "tool_parallel_result",
        "data": {
            "tool": "market_question_b",
            "status": "completed",
            "payload": {
                "stock_widget": {"quote": 456},
                "question_id": "market_question_b",
            },
            "metadata": {"question_id": "market_question_b"},
            "elapsed_ms": 980,
            "parallel_group": "single_agent_market",
            "lane": "market",
        },
    }
    event_web = {
        "event": "tool_parallel_result",
        "data": {
            "tool": "web_retriever",
            "status": "completed",
            "payload": {
                "ready": True,
                "summary": "Benchmarked sentiment.",
                "snippets": [{"title": "Key insight", "url": "https://example.com"}],
            },
            "metadata": {"search_id": "search-1"},
            "elapsed_ms": 640,
            "parallel_group": "single_agent_web",
            "lane": "web",
        },
    }

    flow._ingest_tool_event(ctx, event_market_a)
    flow._ingest_tool_event(ctx, event_market_b)
    flow._ingest_tool_event(ctx, event_web)

    await flow._persist_session_state(ctx, record_artifacts=False)
    snapshot = await repo.load(ctx.session_id)
    assert snapshot is not None
    receipts_payload = snapshot.tool_cache.get("tool_receipts") or {}
    assert "market_question_a" in receipts_payload
    assert "market_question_b" in receipts_payload
    assert "web_retriever" in receipts_payload

    receipt_a = ToolInvocationReceipt.from_dict(receipts_payload["market_question_a"])
    receipt_web = ToolInvocationReceipt.from_dict(receipts_payload["web_retriever"])

    # Receipts should round-trip through the snapshot with metadata intact
    assert receipt_a.tool == "market_question_a"
    assert receipt_web.tool == "web_retriever"
    assert isinstance(receipt_a.timestamp, str)
    assert isinstance(receipt_web.timestamp, str)


def test_market_receipts_expire_when_stale() -> None:
    ttl_seconds = SingleAgentController.LANE_CACHE_TTL_SECONDS
    stale_a = ToolInvocationReceipt(tool="market_question_a", status="completed")
    stale_b = ToolInvocationReceipt(tool="market_question_b", status="completed")
    cutoff = datetime.utcnow() - timedelta(seconds=ttl_seconds + 5)
    iso_cutoff = cutoff.isoformat()
    stale_a.timestamp = iso_cutoff
    stale_b.timestamp = iso_cutoff

    assert not _is_receipt_fresh(stale_a, ttl_seconds)
    assert not _is_receipt_fresh(stale_b, ttl_seconds)


def test_web_receipts_expire_when_stale() -> None:
    ttl_seconds = SingleAgentController.LANE_CACHE_TTL_SECONDS
    stale_web = ToolInvocationReceipt(tool="web_retriever", status="completed")
    cutoff = datetime.utcnow() - timedelta(seconds=ttl_seconds + 5)
    stale_web.timestamp = cutoff.isoformat()

    assert not _is_receipt_fresh(stale_web, ttl_seconds)


def test_record_agent_run_persists_attempts_and_receipts() -> None:
    snapshot = SessionStateSnapshot(session_id="agent-session")
    receipts = {
        "analysis_writer": {
            "status": "completed",
            "finished_at": datetime.utcnow(),
        }
    }
    snapshot.record_agent_run(
        run_id="run-001",
        trace_id="trace-xyz",
        manager_trace_id="manager-123",
        model="gpt-5-mini-2025-08-07",
        tool_attempts={"analysis_writer": 2},
        retry_counts={"analysis_writer": 1},
        receipts=receipts,
    )
    agent_cache = snapshot.tool_cache.get("agent") or {}
    assert agent_cache["last_run_id"] == "run-001"
    assert agent_cache["trace_id"] == "trace-xyz"
    assert agent_cache["manager_trace_id"] == "manager-123"
    assert agent_cache["model"] == "gpt-5-mini-2025-08-07"
    assert agent_cache["tool_attempts"]["analysis_writer"] == 2
    assert agent_cache["retry_counts"]["analysis_writer"] == 1
    recorded_receipt = agent_cache["receipts"]["analysis_writer"]
    assert recorded_receipt["status"] == "completed"
    assert "finished_at" in recorded_receipt
    assert snapshot.agents_run_id == "run-001"
    assert snapshot.agents_trace_id == "trace-xyz"
    assert snapshot.agents_manager_trace_id == "manager-123"
    assert snapshot.agents_model == "gpt-5-mini-2025-08-07"
    assert snapshot.agents_tool_attempts["analysis_writer"] == 2
    assert snapshot.agents_retry_counts["analysis_writer"] == 1
    assert snapshot.agents_tool_receipts["analysis_writer"]["status"] == "completed"
