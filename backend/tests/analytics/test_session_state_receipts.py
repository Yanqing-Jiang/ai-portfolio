from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import pytest

from analytics.agent_orchestrator.agent_plan import PlanState, PlanTemplate
from analytics.artifacts.models import (
    AnalysisArtifact,
    ChartArtifact,
    MarketArtifact,
    SQLExecutionArtifact,
    SQLGenerationArtifact,
    WebContextArtifact,
)
from analytics.flows.chart_revision import RevisionContext
from analytics.flows.planner_executor import (
    PlannerExecutorFlow,
    PlannerRevisionContext,
    ToolInvocationReceipt,
    _apply_revision_context_hints,
)
from analytics.flows.single_agent_tools import SingleAgentController, _SingleAgentRunContext
from analytics.flows.schedulers import FlowMode
from analytics.flows.workflow import _hydrate_inputs_manifest
from analytics.core.session_state import ANALYSIS_INPUT_BLOCKING, SessionStateSnapshot


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


def test_analysis_inputs_manifest_tracks_component_states() -> None:
    snapshot = SessionStateSnapshot(session_id="manifest-trace")
    snapshot.record_outputs(sql="SELECT 42")

    manifest = snapshot.analysis_inputs_manifest
    assert manifest["components"]["sql"]["state"] == "ready"
    assert manifest["components"]["dataset_preview"]["state"] in {"pending", "missing"}
    assert manifest["complete"] is False

    snapshot.record_tool_result(
        "planner_dataset_preview",
        {"rows": [{"label": "Q1"}], "row_count": 1},
    )
    manifest = snapshot.analysis_inputs_manifest
    assert manifest["components"]["dataset_preview"]["state"] == "ready"
    assert manifest["complete"] is True

    snapshot.record_tool_result("planner_stock_widget", {"snapshot": {"ACME": {"price": 100}}})
    manifest = snapshot.analysis_inputs_manifest
    assert manifest["components"]["market"]["state"] == "ready"

    snapshot.record_tool_result("web_search", {"summary": "Updated context", "snippets": [{"title": "result"}]})
    manifest = snapshot.analysis_inputs_manifest
    assert manifest["components"]["web"]["state"] == "ready"
    assert set(manifest["ready_components"]) >= {"sql", "dataset_preview", "market", "web"}


def test_lane_receipts_emit_manifest_metrics(monkeypatch: pytest.MonkeyPatch) -> None:
    sealed_metrics: List[Dict[str, Any]] = []
    missing_metrics: List[Dict[str, Any]] = []
    monkeypatch.setattr(
        "analytics.core.session_state.analysis_inputs_manifest_sealed",
        lambda **kwargs: sealed_metrics.append(kwargs),
    )
    monkeypatch.setattr(
        "analytics.core.session_state.analysis_inputs_missing",
        lambda **kwargs: missing_metrics.append(kwargs),
    )

    snapshot = SessionStateSnapshot(session_id="lane-manifest")
    snapshot.record_outputs(sql="SELECT 1")
    snapshot.record_tool_result("planner_dataset_preview", {"rows": [{"label": "Q1"}], "row_count": 1})
    snapshot.record_tool_result("planner_stock_widget", {"snapshot": {"ACME": {"price": 100}}})
    snapshot.record_tool_result("web_search", {"summary": "cached context", "snippets": [{"title": "news"}]})

    manifest = snapshot.analysis_inputs_manifest
    assert manifest.get("status") == "sealed"
    receipts = manifest.get("receipts") or {}
    for component in ("sql", "dataset_preview", "market", "web"):
        assert receipts.get(component), f"expected receipt for {component}"
    assert sealed_metrics, "sealed metric should emit once manifest completes"
    sealed_payload = sealed_metrics[0]
    assert set(sealed_payload.get("ready_components") or []).issuperset(ANALYSIS_INPUT_BLOCKING)
    sealed_receipts = sealed_payload.get("receipts") or {}
    assert sealed_receipts.get("sql"), "sealed metric should include sql receipt id"
    assert missing_metrics, "missing metrics should emit while manifest is incomplete"
    assert "dataset_preview" in missing_metrics[0]["missing_components"]


def test_manifest_marks_reused_components() -> None:
    snapshot = SessionStateSnapshot(session_id="manifest-reuse")
    snapshot.record_outputs(sql="SELECT 42")
    snapshot.record_tool_result(
        "planner_dataset_preview",
        {"rows": [{"label": "Q1"}], "row_count": 1},
    )
    reuse_metadata = {
        "lane": "sql",
        "reason": "chart_revision",
        "ts": datetime.now(timezone.utc).isoformat(),
    }
    snapshot.record_lane_reuse("sql", reuse_metadata)
    snapshot.refresh_analysis_inputs_manifest(persist=False)
    manifest = snapshot.analysis_inputs_manifest or {}
    sql_component = manifest.get("components", {}).get("sql", {})
    assert sql_component.get("state") == "ready"
    assert sql_component.get("reused") is True
    assert sql_component.get("reuse_metadata", {}).get("reason") == "chart_revision"


def test_lane_missing_artifact_metric_emitted_for_incomplete_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    missing_artifact_calls: List[Dict[str, Any]] = []
    missing_manifest_calls: List[Dict[str, Any]] = []
    monkeypatch.setattr(
        "analytics.core.session_state.analysis_lane_missing_artifact",
        lambda **kwargs: missing_artifact_calls.append(kwargs),
    )
    monkeypatch.setattr(
        "analytics.core.session_state.analysis_inputs_missing",
        lambda **kwargs: missing_manifest_calls.append(kwargs),
    )

    snapshot = SessionStateSnapshot(session_id="lane-missing")
    snapshot.record_tool_result("planner_dataset_preview", {"rows": []})

    assert missing_artifact_calls, "expected lane missing artifact metric to fire"
    event = missing_artifact_calls[0]
    assert event["component"] == "dataset_preview"
    assert event["lane"] == "sql"
    assert event["reason"] == "payload_incomplete"
    assert missing_manifest_calls, "manifest missing metric should emit after failure"
    assert "dataset_preview" in missing_manifest_calls[0]["missing_components"]


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


def test_record_tool_receipt_persists_digests_and_guardrail() -> None:
    snapshot = SessionStateSnapshot(session_id="sess-digests")
    snapshot.record_tool_receipt(
        "web_retriever",
        {
            "arguments": {"query": "NVDA earnings"},
            "payload": {"stock_widget": {"symbol": "NVDA"}},
            "latency_guardrail": {"status": "ok", "threshold_ms": 2500},
        },
    )
    receipt = snapshot.get_tool_receipt("web_retriever")
    assert receipt is not None
    assert receipt.get("arguments_digest", "").startswith('{"query"')
    assert receipt.get("output_digest")
    guardrail = receipt.get("latency_guardrail") or {}
    assert guardrail.get("status") == "ok"


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


def test_snapshot_revision_context_should_refresh_respects_ttl() -> None:
    now = datetime.now(timezone.utc)
    snapshot = SessionStateSnapshot(session_id="refresh-ctx")
    snapshot.touch_lane("web", at=now - timedelta(seconds=30))
    revision_ctx = snapshot.revision_context()
    revision_ctx.lane_ttls["web"] = 120

    assert revision_ctx.should_refresh("web", now=now) is False

    revision_ctx.lane_ttls["web"] = 10
    assert revision_ctx.should_refresh("web", now=now) is True
    assert revision_ctx.should_refresh("market", now=now) is True


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


@pytest.mark.asyncio
async def test_single_agent_seals_manifest_when_inputs_available(monkeypatch: pytest.MonkeyPatch) -> None:
    # Function: test_single_agent_seals_manifest_when_inputs_available -- validates planner-only single-agent runs persist SQL,
    # dataset, and web receipts once controller._planner._persist_session_state runs so RevisionContext.load sees a sealed manifest.
    # Invokes: SingleAgentController._planner._persist_session_state to mirror planner-mode sealing before agent runtime metadata writes.
    repo = _InMemorySessionStateRepository()
    monkeypatch.setattr("analytics.core.session_state.get_session_state_repository", lambda: repo)
    monkeypatch.setattr("analytics.flows.planner_executor.get_session_state_repository", lambda: repo)
    monkeypatch.setattr("analytics.flows.single_agent_tools.get_session_state_repository", lambda: repo)

    session_id = "single-agent-manifest"
    seed_snapshot = SessionStateSnapshot(session_id=session_id)
    seed_snapshot.record_outputs(sql="SELECT 1")
    await repo.save(seed_snapshot)

    controller = SingleAgentController()
    ctx = await controller._planner.initialize_context(
        "Highlight NVDA adoption signals",
        session_id=session_id,
    )

    ctx.artifacts.sql_execution = SQLExecutionArtifact(
        query=ctx.query,
        row_count=4,
        dataset_preview=[{"period": "Q1-2025", "value": 1.23}],
    )
    ctx.artifacts.web = WebContextArtifact(
        query=ctx.query,
        summary="Customers continue to scale orders.",
        snippets=[{"title": "Customer signal", "url": "https://example.com"}],
    )
    ctx.artifacts.market = MarketArtifact(
        query=ctx.query,
        tickers=["NVDA"],
        snapshot={"quote": {"NVDA": 123.45}},
    )
    ctx.artifacts.analysis = AnalysisArtifact(
        query=ctx.query,
        analysis_text="Multi-quarter adoption remains strong.",
    )
    ctx.artifacts.chart = ChartArtifact(
        query=ctx.query,
        spec={
            "mark": "line",
            "encoding": {
                "x": {"field": "period", "type": "ordinal"},
                "y": {"field": "value", "type": "quantitative"},
            },
        },
    )

    await controller._planner._persist_session_state(
        ctx,
        record_artifacts=True,
    )

    snapshot = await repo.load(ctx.session_id)
    assert snapshot is not None
    manifest = snapshot.analysis_inputs_manifest
    assert manifest.get("status") == "sealed"
    assert not manifest.get("missing_components")
    receipts = manifest.get("receipts") or {}
    for component in ("sql", "dataset_preview", "web"):
        assert receipts.get(component), f"Expected receipt for {component}"

    revision_ctx = await RevisionContext.load(session_id, repository=repo)
    assert revision_ctx.analysis_inputs_ready() is True
    assert revision_ctx.analysis_inputs_missing() == []


@pytest.mark.asyncio
async def test_planner_executor_dataset_preview_persists_without_sql_overwrite(monkeypatch: pytest.MonkeyPatch) -> None:
    repo = _InMemorySessionStateRepository()
    monkeypatch.setattr("analytics.core.session_state.get_session_state_repository", lambda: repo)
    monkeypatch.setattr("analytics.flows.planner_executor.get_session_state_repository", lambda: repo)

    session_id = "planner-dataset-preview"
    seed_snapshot = SessionStateSnapshot(session_id=session_id)
    seed_snapshot.record_outputs(sql="SELECT baseline_sql")
    await repo.save(seed_snapshot)

    flow = PlannerExecutorFlow(flow_mode=FlowMode.SINGLE_AGENT)
    ctx = await flow.initialize_context("Show AMD revenue trend", session_id=session_id)
    ctx.artifacts.sql_execution = SQLExecutionArtifact(
        query=ctx.query,
        row_count=2,
        dataset_preview=[{"period": "FY24", "value": 42.0}],
    )

    await flow._persist_session_state(ctx, record_dataset_preview=True)

    snapshot = await repo.load(session_id)
    assert snapshot is not None
    assert snapshot.last_sql == "SELECT baseline_sql"
    manifest = snapshot.analysis_inputs_manifest
    assert manifest.get("components", {}).get("dataset_preview", {}).get("state") == "ready"
    receipts = manifest.get("receipts") or {}
    assert receipts.get("dataset_preview"), "Expected dataset preview receipt id"
    cached_preview = snapshot.tool_cache.get("planner_dataset_preview") if isinstance(snapshot.tool_cache, dict) else None
    assert cached_preview and cached_preview.get("rows"), "Dataset preview payload should be cached"


@pytest.mark.asyncio
async def test_dataset_preview_receipt_written_for_string_row_count(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Function: test_dataset_preview_receipt_written_for_string_row_count - called from pytest runner, forwards
    assertions to ensure PlannerExecutorFlow persists dataset receipts when SQL execution only reports row_count
    as a string; verifies manifest sealing logic in analytics.memory revisions.
    """
    repo = _InMemorySessionStateRepository()
    monkeypatch.setattr("analytics.core.session_state.get_session_state_repository", lambda: repo)
    monkeypatch.setattr("analytics.flows.planner_executor.get_session_state_repository", lambda: repo)

    session_id = "planner-dataset-preview-string-row-count"
    flow = PlannerExecutorFlow(flow_mode=FlowMode.SINGLE_AGENT)
    ctx = await flow.initialize_context("Capture dataset receipt edge cases", session_id=session_id)
    ctx.artifacts.sql_generation = SQLGenerationArtifact(query=ctx.query, sql="SELECT new_metric FROM table")
    ctx.artifacts.sql_execution = SQLExecutionArtifact(
        query=ctx.query,
        row_count="12",  # planner SQL lane occasionally serializes this as a string
        dataset_preview=[],  # executor skipped preview rows due to payload size
    )

    await flow._persist_session_state(ctx, record_dataset_preview=True, record_sql=True)

    snapshot = await repo.load(session_id)
    assert snapshot is not None
    snapshot.ensure_analysis_inputs_manifest()
    manifest = snapshot.analysis_inputs_manifest or {}
    dataset_state = manifest.get("components", {}).get("dataset_preview", {}).get("state")
    assert dataset_state == "ready", "String row_count should still seal dataset preview"
    receipts = manifest.get("receipts") or {}
    assert receipts.get("dataset_preview"), "Expected dataset preview receipt id even without preview rows"
    cached_preview = snapshot.tool_cache.get("planner_dataset_preview") if isinstance(snapshot.tool_cache, dict) else None
    assert cached_preview is not None, "Dataset preview payload should be cached for manifest hydration"
    assert cached_preview.get("row_count") == 12, "Row count should be normalized to an int in the cached preview"


@pytest.mark.asyncio
async def test_persist_session_state_emits_lane_warning_when_dataset_receipt_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    repo = _InMemorySessionStateRepository()
    monkeypatch.setattr("analytics.core.session_state.get_session_state_repository", lambda: repo)
    monkeypatch.setattr("analytics.flows.planner_executor.get_session_state_repository", lambda: repo)

    telemetry_calls: List[Dict[str, Any]] = []
    monkeypatch.setattr(
        "analytics.core.telemetry.analysis_lane_missing_artifact",
        lambda **kwargs: telemetry_calls.append(kwargs),
    )

    flow = PlannerExecutorFlow(flow_mode=FlowMode.SINGLE_AGENT)
    ctx = await flow.initialize_context("Highlight manifest issues", session_id="planner-missing-preview")
    ctx.artifacts.sql_execution = SQLExecutionArtifact(
        query=ctx.query,
        row_count=5,
        dataset_preview=[{"period": "FY25", "value": 100}],
    )

    await flow._persist_session_state(ctx, record_dataset_preview=False, record_artifacts=False, record_sql=False)

    assert telemetry_calls, "Expected dataset receipt warning telemetry to fire"
    warning = telemetry_calls[0]
    assert warning["component"] == "dataset_preview"
    assert warning["lane"] == "sql"
    snapshot = await repo.load(ctx.session_id)
    assert snapshot is not None
    cached_preview = snapshot.tool_cache.get("planner_dataset_preview") if isinstance(snapshot.tool_cache, dict) else None
    assert cached_preview is None, "Dataset preview should not be cached when persistence is skipped"


@pytest.mark.asyncio
async def test_dataset_preview_warning_for_non_numeric_row_count(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Function: test_dataset_preview_warning_for_non_numeric_row_count - called from pytest runner, forwards
    assertions to ensure PlannerExecutorFlow emits lane warnings when SQL execution reports an unparseable
    row_count string so manifests remain in sync with telemetry.
    """
    repo = _InMemorySessionStateRepository()
    monkeypatch.setattr("analytics.core.session_state.get_session_state_repository", lambda: repo)
    monkeypatch.setattr("analytics.flows.planner_executor.get_session_state_repository", lambda: repo)

    telemetry_calls: List[Dict[str, Any]] = []
    monkeypatch.setattr(
        "analytics.core.telemetry.analysis_lane_missing_artifact",
        lambda **kwargs: telemetry_calls.append(kwargs),
    )

    session_id = "planner-dataset-preview-numeric-string-warning"
    flow = PlannerExecutorFlow(flow_mode=FlowMode.SINGLE_AGENT)
    ctx = await flow.initialize_context("Handle malformed row counts", session_id=session_id)
    ctx.artifacts.sql_execution = SQLExecutionArtifact(
        query=ctx.query,
        row_count="unknown",
        dataset_preview=[],
    )

    await flow._persist_session_state(ctx, record_dataset_preview=True)

    snapshot = await repo.load(session_id)
    assert snapshot is not None
    snapshot.ensure_analysis_inputs_manifest()
    manifest = snapshot.analysis_inputs_manifest or {}
    dataset_state = manifest.get("components", {}).get("dataset_preview", {}).get("state")
    assert dataset_state in {"pending", "missing"}, "Manifest should stay unsealed for invalid row counts"
    assert telemetry_calls, "Expected telemetry warning for missing dataset receipt"
    metadata = telemetry_calls[0].get("metadata") or {}
    assert metadata.get("row_count") is None
    assert metadata.get("raw_row_count") == "unknown"


@pytest.mark.asyncio
async def test_manifest_hydration_seals_pending_dataset_receipts(monkeypatch: pytest.MonkeyPatch) -> None:
    repo = _InMemorySessionStateRepository()
    monkeypatch.setattr("analytics.core.session_state.get_session_state_repository", lambda: repo)
    monkeypatch.setattr("analytics.flows.planner_executor.get_session_state_repository", lambda: repo)

    session_id = "manifest-hydration-pending"
    flow = PlannerExecutorFlow(flow_mode=FlowMode.SINGLE_AGENT)
    ctx = await flow.initialize_context("Seal manifest receipts", session_id=session_id)
    ctx.artifacts.sql_generation = SQLGenerationArtifact(query=ctx.query, sql="SELECT series FROM facts")
    ctx.artifacts.sql_execution = SQLExecutionArtifact(
        query=ctx.query,
        row_count=3,
        dataset_preview=[
            {"period": "FY24", "series": 1.0},
            {"period": "FY23", "series": 0.8},
        ],
    )
    await flow._persist_session_state(ctx, record_dataset_preview=True, record_artifacts=True, record_sql=True)

    snapshot = await repo.load(session_id)
    assert snapshot is not None
    manifest = snapshot.analysis_inputs_manifest or {}
    manifest["status"] = "pending"
    manifest["complete"] = False
    manifest["blocking_components"] = ["dataset_preview"]
    snapshot.analysis_inputs_manifest = manifest
    await repo.save(snapshot)

    hydrated = await _hydrate_inputs_manifest(session_id, repo, snapshot=snapshot)
    assert hydrated is not None
    reloaded = await repo.load(session_id)
    assert reloaded is not None
    manifest = reloaded.analysis_inputs_manifest or {}
    assert manifest.get("status") == "sealed"
    receipts = manifest.get("receipts") or {}
    assert receipts.get("dataset_preview"), "Dataset preview receipt should survive manifest hydration"


@pytest.mark.asyncio
async def test_manifest_hydration_backfills_dataset_preview_from_revision_snapshot(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = _InMemorySessionStateRepository()
    monkeypatch.setattr("analytics.core.session_state.get_session_state_repository", lambda: repo)
    monkeypatch.setattr("analytics.flows.planner_executor.get_session_state_repository", lambda: repo)

    session_id = "manifest-hydration-backfill"
    snapshot = SessionStateSnapshot(session_id=session_id)
    snapshot.record_outputs(sql="SELECT metric FROM facts")
    analytics_cache = snapshot.tool_cache.setdefault("analytics", {})
    analytics_cache["revision_snapshot"] = {
        "data_sample": [
            {"calendar_year": 2024, "revenue": 123.0},
            {"calendar_year": 2023, "revenue": 98.5},
        ],
        "sql_row_count": 2,
    }
    await repo.save(snapshot)

    hydrated = await _hydrate_inputs_manifest(session_id, repo, snapshot=snapshot)
    assert hydrated is not None
    reloaded = await repo.load(session_id)
    assert reloaded is not None
    preview_payload = (reloaded.tool_cache or {}).get("planner_dataset_preview")
    assert isinstance(preview_payload, dict) and preview_payload.get("rows"), "Dataset preview should be backfilled"
    manifest = reloaded.analysis_inputs_manifest or {}
    assert manifest.get("status") == "sealed"
    dataset_state = manifest.get("components", {}).get("dataset_preview", {}).get("state")
    assert dataset_state == "ready"


def test_dataset_preview_backfilled_from_artifacts() -> None:
    snapshot = SessionStateSnapshot(session_id="seed-artifacts")
    snapshot.tool_cache["analytics"] = {
        "artifacts": {
            "sql_execution": {
                "dataset_preview": [
                    {"period": "FY24", "value": 1.23},
                    {"period": "FY23", "value": 0.87},
                ],
                "row_count": 2,
            }
        }
    }
    changed = snapshot.ensure_dataset_preview_from_revision()
    assert changed
    cached_preview = snapshot.tool_cache.get("planner_dataset_preview")
    assert isinstance(cached_preview, dict) and len(cached_preview.get("rows") or []) == 2
    snapshot.refresh_analysis_inputs_manifest(persist=False)
    manifest = snapshot.analysis_inputs_manifest or {}
    assert manifest.get("components", {}).get("dataset_preview", {}).get("state") == "ready"


def test_market_receipt_backfilled_from_artifacts() -> None:
    snapshot = SessionStateSnapshot(session_id="seed-market")
    snapshot.tool_cache["analytics"] = {
        "artifacts": {
            "market": {
                "snapshot": {
                    "tickers": ["AMD", "NVDA"],
                    "prices": {"AMD": 120.0, "NVDA": 490.0},
                }
            }
        }
    }
    changed = snapshot.ensure_dataset_preview_from_revision()
    assert changed
    cached_market = snapshot.tool_cache.get("planner_stock_widget")
    assert isinstance(cached_market, dict)
    assert cached_market.get("tickers") == ["AMD", "NVDA"]
    snapshot.refresh_analysis_inputs_manifest(persist=False)
    manifest = snapshot.analysis_inputs_manifest or {}
    assert manifest.get("components", {}).get("market", {}).get("state") == "ready"
