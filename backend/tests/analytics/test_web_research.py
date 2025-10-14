import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[2]))

from typing import Optional

import pytest

from analytics.flows.multi_agent import _web_research_agent
from analytics.flows.orchestrator import AgentRunContext
from analytics.services.response_search import (
    ResponseSearchResult,
    SearchSnippet,
    TopicSearchResult,
    _DEFAULT_MODEL,
)


@pytest.mark.asyncio
async def test_web_research_agent_records_latency_distribution(monkeypatch):
    assert _DEFAULT_MODEL == "gemini-2.5-flash-lite"

    shared_state = {"web": {}}
    context = AgentRunContext(
        query="What is NVDA's 2025 guidance outlook?",
        session_id="session-latency",
        shared=shared_state,
        dependencies={},
        inputs={},
    )

    response = ResponseSearchResult(
        query=context.query,
        summary="Guidance tightening alongside AI demand.",
        snippets=[SearchSnippet(title="NVIDIA CFO sees upside")],
        latency_ms=810,
        model=_DEFAULT_MODEL,
    )
    response.topics = [
        TopicSearchResult(
            label="Primary question",
            query="NVDA 2025 guidance",
            latency_ms=320,
        ),
        TopicSearchResult(
            label="Industry context",
            query="Semiconductor demand backdrop",
            latency_ms=490,
        ),
    ]

    async def fake_perform_response_search(query: str, session_id: Optional[str] = None):
        assert session_id == "session-latency"
        return response

    monkeypatch.setattr(
        "analytics.flows.multi_agent.perform_response_search",
        fake_perform_response_search,
    )

    result = await _web_research_agent(context)

    assert result.metrics["latency_ms"] == 810
    assert result.metrics["latency_p50_ms"] == 405
    assert result.metrics["latency_max_ms"] == 490
    assert result.metrics["latency_min_ms"] == 320
    assert result.metrics["latency_samples"] == 2

    attempts = shared_state["web"].get("attempts")
    assert attempts and attempts[0]["latency_ms"] == 810

    latency_stats = shared_state["web"].get("latency_stats")
    assert latency_stats is not None
    assert latency_stats["total_ms"] == 810
    assert latency_stats["p50_ms"] == 405
    assert latency_stats["max_ms"] == 490
    assert latency_stats["min_ms"] == 320
    assert latency_stats["per_topic_ms"] == [320, 490]

    assert shared_state["web"]["model"] == _DEFAULT_MODEL
