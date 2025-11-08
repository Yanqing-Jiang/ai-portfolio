from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from typing import Any, Dict, Optional

import pytest

from analytics.artifacts.models import MarketArtifact, WebContextArtifact
from analytics.flows.planner_executor import (
    PlannerExecutorFlow,
    PlannerRevisionContext,
    ToolInvocationReceipt,
    _apply_revision_context_hints,
)
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
    assert receipt_a.source_lane == "market"
    assert receipt_web.source_lane == "web"
    assert receipt_web.latency_ms == 640
    assert receipt_a.latency_ms == 1200
    assert receipt_web.reused_at_ms is None


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


@pytest.mark.asyncio
async def test_agent_reasoning_persisted_to_snapshot(monkeypatch: pytest.MonkeyPatch) -> None:
    repo = _InMemorySessionStateRepository()
    monkeypatch.setattr("analytics.core.session_state.get_session_state_repository", lambda: repo)
    monkeypatch.setattr("analytics.flows.planner_executor.get_session_state_repository", lambda: repo)

    flow = PlannerExecutorFlow(flow_mode=FlowMode.SINGLE_AGENT)
    ctx = await flow.initialize_context("Agent reasoning cache", session_id="session-agent-reason")
    ctx.agentic_revision_mode = True
    ctx.revision_reasoning["web_retriever"] = {
        "summary": "Queued NVDA SERP refresh",
        "lane": "web",
        "metadata": {"parallel_group": "tool_fanout"},
    }

    await flow._persist_session_state(ctx, record_artifacts=False)
    snapshot = await repo.load(ctx.session_id)
    assert snapshot is not None
    reasoning_cache = snapshot.tool_cache.get("agent_reasoning") or {}
    assert reasoning_cache["web_retriever"]["summary"] == "Queued NVDA SERP refresh"
    assert reasoning_cache["web_retriever"]["lane"] == "web"


def test_revision_context_includes_reasoning_and_lane_metadata() -> None:
    snapshot = SessionStateSnapshot(session_id="revision-session")
    snapshot.tool_cache["tool_receipts"] = {
        "web_retriever": {
            "tool": "web_retriever",
            "status": "completed",
            "timestamp": datetime.utcnow().isoformat(),
        }
    }
    snapshot.record_agent_reasoning("web_retriever", "Cached SERP reused", lane="web")
    snapshot.touch_lane("web", at=datetime.now(timezone.utc) - timedelta(seconds=30))
    analytics_cache = snapshot.tool_cache.setdefault("analytics", {})
    analytics_cache["revision_snapshot"] = {
        "web_context": {"summary": "cached web"},
        "stock_widget": {"quote": 101.2},
    }

    revision_ctx = snapshot.revision_context()

    assert "web_retriever" in revision_ctx.tool_receipts
    assert revision_ctx.agent_reasoning["web_retriever"]["summary"] == "Cached SERP reused"
    age_seconds = revision_ctx.lane_age_seconds("web")
    assert age_seconds is not None and age_seconds < 90
    assert revision_ctx.revision_snapshot["web_context"]["summary"] == "cached web"


def test_record_tool_receipt_merges_lane_reuse_metadata() -> None:
    snapshot = SessionStateSnapshot(session_id="lane-reuse-meta")
    metadata = {
        "lane": "web",
        "reason": "cached_accessory",
        "age_seconds": 64.0,
        "fast_path_latency_ms": 480,
        "ts": datetime.now(timezone.utc).isoformat(),
    }
    snapshot.record_lane_reuse("web", metadata)
    snapshot.record_tool_receipt(
        "web_retriever",
        {
            "lane": "web",
            "status": "reused",
        },
    )
    receipts = snapshot.tool_cache.get("tool_receipts", {})
    assert "web_retriever" in receipts
    stored = receipts["web_retriever"]
    assert stored.get("reuse_metadata", {}).get("fast_path_latency_ms") == 480
    assert stored.get("source_lane") == "web"
    assert stored.get("reused_at_ms") == 480


def test_lane_fast_path_latency_helper_returns_delta() -> None:
    snapshot = SessionStateSnapshot(session_id="lane-fast-path")
    anchor = datetime(2025, 1, 1, tzinfo=timezone.utc)
    snapshot.record_lane_fast_path_marker("sql_ready_seen_at", at=anchor)
    latency = snapshot.lane_fast_path_latency_ms("sql_ready_seen_at", now=anchor + timedelta(seconds=1.25))
    assert latency == 1250


def test_planner_revision_context_should_refresh_respects_overrides() -> None:
    snapshot = SessionStateSnapshot(session_id="planner-revision")
    now = datetime.now(timezone.utc)
    snapshot.touch_lane("web", at=now - timedelta(seconds=10))
    snapshot.touch_lane("analysis", at=now - timedelta(seconds=400))
    snapshot.tool_cache["tool_receipts"] = {
        "web_retriever": {
            "tool": "web_retriever",
            "status": "completed",
            "timestamp": datetime.utcnow().isoformat(),
        }
    }

    planner_ctx = PlannerRevisionContext.from_snapshot(snapshot, lane_refresh_overrides={"web": False})
    assert planner_ctx is not None
    assert planner_ctx.should_refresh("web") is False
    assert planner_ctx.should_refresh("analysis") is True


@pytest.mark.asyncio
async def test_revision_context_sets_lane_refresh_flags() -> None:
    flow = PlannerExecutorFlow(flow_mode=FlowMode.SINGLE_AGENT)
    snapshot = SessionStateSnapshot(session_id="lane-age-session")
    now = datetime.now(timezone.utc)
    snapshot.touch_lane("web", at=now)
    snapshot.touch_lane("market", at=now - timedelta(seconds=500))
    flow.prime_with_snapshot(snapshot)

    ctx = await flow.initialize_context("Reuse cached accessories", session_id="lane-age-session")

    assert ctx.revision_context is not None
    assert ctx.lane_refresh_required.get("web") is False
    assert ctx.lane_refresh_required.get("market") is True


@pytest.mark.asyncio
async def test_revision_context_hints_override_existing_flags() -> None:
    flow = PlannerExecutorFlow(flow_mode=FlowMode.SINGLE_AGENT)
    snapshot = SessionStateSnapshot(session_id="lane-age-session-override")
    now = datetime.now(timezone.utc)
    snapshot.touch_lane("web", at=now)
    flow.prime_with_snapshot(snapshot)

    ctx = await flow.initialize_context("cached lane", session_id="lane-age-session-override")
    assert ctx.revision_context is not None
    ctx.lane_refresh_required["web"] = True

    _apply_revision_context_hints(ctx)

    assert ctx.lane_refresh_required["web"] is False
