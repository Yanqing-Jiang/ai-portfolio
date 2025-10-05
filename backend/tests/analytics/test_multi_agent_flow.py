import sys
from pathlib import Path
import asyncio

sys.path.append(str(Path(__file__).resolve().parents[2]))

from analytics.flows.multi_agent import MultiAgentFlow


class DummyPlannerFlow:
    async def events(self, query: str, session_id: str = None):
        yield {"event": "session_started", "data": {"session_id": session_id or "sess-123"}}
        yield {
            "event": "intent_detection_complete",
            "data": {
                "intent_key": "test_intent",
                "confidence": 0.92,
                "slots_detected": {"company": "NVDA"},
            },
        }
        yield {
            "event": "plan_built",
            "data": {"comparison": "vs_avg", "granularity": "annual"},
        }
        yield {
            "event": "web_search",
            "data": {
                "web_context": {
                    "summary": "NVIDIA guidance commentary",
                    "snippets": [{"title": "Headline"}],
                }
            },
        }
        yield {
            "event": "sql_compiled",
            "data": {
                "template_used": "template_123",
                "sql_length": 42,
                "template_fallback": False,
            },
        }
        yield {
            "event": "sql_generated",
            "data": {
                "sql": "SELECT 1",
                "llm_used": True,
                "template_fallback": False,
            },
        }
        yield {
            "event": "analysis_complete",
            "data": {"analysis": "Done", "analysis_length": 4},
        }
        yield {
            "event": "workflow_complete",
            "data": {"total_elapsed_ms": 100},
        }


def test_multi_agent_flow_handles_web_context(monkeypatch):
    flow = MultiAgentFlow()
    async def fake_orchestration(self, query, session_id):
        self._orchestrated = True
        if False:
            yield None
        return
    monkeypatch.setattr(MultiAgentFlow, "_run_agent_orchestration", fake_orchestration)
    flow._planner = DummyPlannerFlow()
    flow._orchestrated = True  # Skip orchestration for this unit test

    events = []

    async def _collect():
        async for evt in flow.events("NVDA outlook", session_id="session-xyz"):
            events.append(evt)
            if evt.get("event") == "workflow_complete":
                break

    asyncio.run(_collect())

    assert any(evt.get("event") == "web_search" for evt in events)
    assert events[-1]["event"] == "workflow_complete"
    web_context = flow._shared_context.get("web")
    assert web_context is not None
    assert web_context.get("summary") == "NVIDIA guidance commentary"
