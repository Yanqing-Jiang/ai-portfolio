from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from analytics.artifacts.models import (
    AnalysisArtifact,
    ChartArtifact,
    MarketArtifact,
    PipelineArtifacts,
    SQLGenerationArtifact,
    WebContextArtifact,
)
from analytics.flows.single_agent_tools import LANE_TTL_DEFAULTS, SingleAgentController, _SingleAgentRunContext


@pytest.mark.asyncio
async def test_emit_tool_event_enqueues_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    controller = SingleAgentController(enable_agents=False)
    queue: "asyncio.Queue[dict[str, any]]" = asyncio.Queue()
    run_context = _SingleAgentRunContext(
        controller=controller,
        session_id="session-test",
        query="latest revenue",
        queue=queue,
        revision_directive=None,
    )

    await controller._emit_tool_event(
        run_context,
        event_name="tool_attempt",
        tool="sql_generator",
        lane="sql",
        status="running",
        session_id="session-test",
        attempt=1,
        retry_count=0,
    )

    event = await queue.get()
    assert event["event"] == "tool_attempt"
    data = event["data"]
    assert data["tool"] == "sql_generator"
    assert data["lane"] == "sql"
    assert data["status"] == "running"
    assert data["attempt"] == 1


def test_cached_receipt_reusable_within_ttl() -> None:
    controller = SingleAgentController(enable_agents=False)
    recent = datetime.now(timezone.utc).isoformat()
    reusable = controller._is_cached_receipt_reusable(
        "analysis",
        {
            "status": "completed",
            "recorded_at": recent,
        },
    )
    assert reusable is True


def test_cached_receipt_stale_after_ttl() -> None:
    controller = SingleAgentController(enable_agents=False)
    ttl_seconds = LANE_TTL_DEFAULTS.get("analysis", 600)
    old = (datetime.now(timezone.utc) - timedelta(seconds=ttl_seconds + 10)).isoformat()
    reusable = controller._is_cached_receipt_reusable(
        "analysis",
        {
            "status": "completed",
            "recorded_at": old,
        },
    )
    assert reusable is False


class _DummyAgent:
    def __init__(self, *_, **__) -> None:
        pass


@pytest.fixture(autouse=True)
def _patch_agent(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("analytics.flows.single_agent_tools.Agent", _DummyAgent)


def test_single_agent_controller_enables_agents_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    controller = SingleAgentController()

    assert controller._agents_enabled is True
    assert isinstance(controller._agent, _DummyAgent)


def test_single_agent_controller_respects_disable_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    controller = SingleAgentController(enable_agents=False)

    assert controller._agents_enabled is False
    assert controller._agent is None


def test_agent_runtime_gated_by_follow_up(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    controller = SingleAgentController(enable_agents=True)
    controller._agent_runtime_allowed = True
    controller._session_follow_up = False
    controller._agentic_revision_mode = False
    assert controller._should_use_agent_runtime() is False
    controller._session_follow_up = True
    assert controller._should_use_agent_runtime() is True


def test_agent_runtime_needs_fallback_when_artifacts_missing() -> None:
    controller = SingleAgentController(enable_agents=False)
    dummy_ctx = SimpleNamespace(artifacts=None)
    assert controller._agent_runtime_needs_fallback(dummy_ctx) is True


def test_agent_runtime_no_fallback_when_artifacts_present() -> None:
    controller = SingleAgentController(enable_agents=False)
    artifacts = PipelineArtifacts(
        sql_generation=SQLGenerationArtifact(query="q", sql="select 1"),
        chart=ChartArtifact(query="q", spec={"series": []}),
        analysis=AnalysisArtifact(query="q", analysis_text="done"),
        web=WebContextArtifact(query="q", summary="ok"),
        market=MarketArtifact(query="q", snapshot={"price": 1}),
    )
    ctx = SimpleNamespace(artifacts=artifacts, reused_sql=False, reused_web=False, reused_market=False, reused_analysis=False)
    assert controller._agent_runtime_needs_fallback(ctx) is False
