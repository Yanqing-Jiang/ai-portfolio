from __future__ import annotations

import asyncio
import sys
import types
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[2]))

google_stub = sys.modules.setdefault("google", types.ModuleType("google"))
genai_stub = types.ModuleType("google.genai")
genai_types_stub = types.ModuleType("google.genai.types")
setattr(genai_stub, "types", genai_types_stub)
setattr(google_stub, "genai", genai_stub)
sys.modules["google.genai"] = genai_stub
sys.modules["google.genai.types"] = genai_types_stub

from analytics.artifacts import AnalysisArtifact, PipelineArtifacts
from analytics.flows.single_agent_tools import SingleAgentController, _SingleAgentToolHooks
from analytics.routing import FollowUpRoute


def test_single_agent_fallback_final_answer_when_data_incomplete() -> None:
    controller = SingleAgentController()

    artifacts = PipelineArtifacts(
        analysis=AnalysisArtifact(
            query="Compare NVDA and AMD revenue in FY24",
            analysis_text="Preliminary narrative for comparison.",
        )
    )
    controller._planner._latest_artifacts = artifacts  # type: ignore[attr-defined]

    hooks = _SingleAgentToolHooks(controller)
    hooks._last_analysis_payload = {"analysis": "Preliminary narrative for comparison."}
    hooks._emitted_cohesive = False

    async def collect():
        results = []
        async for event in hooks.on_flow_end({"session_id": "sess-123"}):
            results.append(event)
        return results

    events = asyncio.run(collect())

    assert len(events) == 1
    event = events[0]
    assert event["event"] == "final_answer"
    data = event["data"]
    assert data["final_answer_only"] is True
    assert data["analysis_available"] is True
    assert data["flow_mode"] == "single_agent"
    assert set(data.get("missing_components", [])) == {"sql", "stock", "web"}
    assert data.get("follow_up_route") == controller.follow_up_route.value

    message = data["message"]
    assert message.startswith("Preliminary narrative for comparison.")
    assert "Pending lanes:" in message


def test_single_agent_chart_revision_final_answer_mentions_reuse() -> None:
    controller = SingleAgentController()
    controller.set_follow_up_route(FollowUpRoute.REUSE_SQL)

    hooks = _SingleAgentToolHooks(controller)
    hooks._last_analysis_payload = {
        "analysis": "Existing analysis retained.",
        "sql": "SELECT * FROM equities;",
        "stock_widget": {"symbols": [["NASDAQ:NVDA", "NVDA"]]},
        "web_context": {"summary": "Earnings preview already captured."},
    }

    payload = hooks._build_final_answer_payload()
    assert payload is not None
    assert payload["missing_components"] == []
    message = payload["message"]
    assert "Chart revision applied." in message
    assert "reused" in message.lower()
