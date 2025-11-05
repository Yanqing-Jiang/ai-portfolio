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

    controller = SingleAgentController()
    artifacts = SimpleNamespace(
        market=SimpleNamespace(snapshot={"widget": {"quote": 123}}),
        web=SimpleNamespace(summary="Benchmarked sentiment."),
    )
    ctx_for_reuse = SimpleNamespace(
        artifacts=artifacts,
        snapshot_age_seconds=None,
        tool_receipts={
            "market_question_a": receipt_a,
            "market_question_b": ToolInvocationReceipt.from_dict(receipts_payload["market_question_b"]),
            "web_retriever": receipt_web,
        },
        revision_snapshot=None,
    )

    assert controller._should_reuse_market(ctx_for_reuse)
    assert controller._should_reuse_web(ctx_for_reuse)


def test_market_receipts_expire_when_stale() -> None:
    controller = SingleAgentController()
    freshness_boundary = controller.LANE_CACHE_TTL_SECONDS + 5
    stale_a = ToolInvocationReceipt(tool="market_question_a", status="completed")
    stale_b = ToolInvocationReceipt(tool="market_question_b", status="completed")
    cutoff = datetime.utcnow() - timedelta(seconds=freshness_boundary)
    iso_cutoff = cutoff.isoformat()
    stale_a.timestamp = iso_cutoff
    stale_b.timestamp = iso_cutoff

    artifacts = SimpleNamespace(
        market=SimpleNamespace(snapshot={"widget": {"quote": 42}}),
        web=None,
    )
    ctx = SimpleNamespace(
        artifacts=artifacts,
        snapshot_age_seconds=None,
        tool_receipts={
            "market_question_a": stale_a,
            "market_question_b": stale_b,
        },
        revision_snapshot=None,
    )

    assert not controller._should_reuse_market(ctx)


def test_web_receipts_expire_when_stale() -> None:
    controller = SingleAgentController()
    freshness_boundary = controller.LANE_CACHE_TTL_SECONDS + 5
    stale_web = ToolInvocationReceipt(tool="web_retriever", status="completed")
    cutoff = datetime.utcnow() - timedelta(seconds=freshness_boundary)
    stale_web.timestamp = cutoff.isoformat()

    artifacts = SimpleNamespace(
        market=None,
        web=SimpleNamespace(summary="Cached insight bundle."),
        analysis=None,
    )
    ctx = SimpleNamespace(
        artifacts=artifacts,
        snapshot_age_seconds=None,
        tool_receipts={
            "web_retriever": stale_web,
        },
        revision_snapshot=None,
    )

    assert not controller._should_reuse_web(ctx)


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
        model="gpt-4.1",
        tool_attempts={"analysis_writer": 2},
        retry_counts={"analysis_writer": 1},
        receipts=receipts,
    )
    agent_cache = snapshot.tool_cache.get("agent") or {}
    assert agent_cache["last_run_id"] == "run-001"
    assert agent_cache["trace_id"] == "trace-xyz"
    assert agent_cache["model"] == "gpt-4.1"
    assert agent_cache["tool_attempts"]["analysis_writer"] == 2
    assert agent_cache["retry_counts"]["analysis_writer"] == 1
    recorded_receipt = agent_cache["receipts"]["analysis_writer"]
    assert recorded_receipt["status"] == "completed"
    assert "finished_at" in recorded_receipt
