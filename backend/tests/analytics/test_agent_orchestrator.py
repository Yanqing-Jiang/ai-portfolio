from __future__ import annotations

import asyncio
from typing import Any, AsyncIterator, Mapping

import pytest

from analytics.agent_orchestrator import (
    AgentMemory,
    AgentRuntime,
    AgentRuntimeConfig,
    PlanTemplate,
)
from analytics.core.session_state import SessionStateSnapshot
from analytics.flows.schedulers import FlowMode


class _StubRunResult:
    """Minimal RunResultStreaming stub for orchestrator tests."""

    def __init__(self, final_output: Mapping[str, Any]) -> None:
        self.final_output = final_output
        self.run_id = "run-stub-001"
        self.trace_id = "trace-stub-001"

    async def stream_events(self) -> AsyncIterator[Any]:
        if False:
            yield None


@pytest.mark.asyncio
async def test_agent_runtime_publishes_plan_and_persists_state(monkeypatch: pytest.MonkeyPatch) -> None:
    queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
    snapshot = SessionStateSnapshot(session_id="session-test")
    memory = AgentMemory(snapshot)

    template = PlanTemplate.from_config(
        {
            "name": "test_single_node",
            "nodes": [
                {
                    "name": "analysis_lane",
                    "kind": "analysis",
                }
            ],
        }
    )

    captured_args: dict[str, Any] = {}

    def _fake_stream(agent: Any, *, input: str, session: Any = None, context: Any, run_config: Any, max_turns: int = 0) -> _StubRunResult:
        captured_args.update(
            {
                "agent": agent,
                "input": input,
                "session": session,
                "context": context,
                "run_config": run_config,
                "max_turns": max_turns,
            }
        )
        return _StubRunResult({"analysis": "Analysis goes here."})

    runner_module = __import__("analytics.agent_orchestrator.agent_runtime", fromlist=["Runner"])
    runner_cls = getattr(runner_module, "Runner")
    target_method = "stream" if hasattr(runner_cls, "stream") else "run_streamed"
    monkeypatch.setattr(runner_cls, target_method, _fake_stream)

    runtime = AgentRuntime(
        agent=object(),
        memory=memory,
        queue=queue,
        flow_mode=FlowMode.SINGLE_AGENT,
        config=AgentRuntimeConfig(
            model="gpt-4.1",
            plan_template=template,
            max_turns=4,
        ),
    )

    run_ctx = type("RunCtx", (), {"session_id": "session-test"})()
    result = await runtime.run("How did revenue trend?", session_id="session-test", run_context=run_ctx)

    events = []
    while not queue.empty():
        events.append(await queue.get())

    assert captured_args["input"] == "How did revenue trend?"
    assert captured_args["session"] is None
    assert getattr(captured_args["context"], "session_id", None) == "session-test"

    assert events, "Expected orchestrator to enqueue SSE events"
    event_names = [event["event"] for event in events]
    assert "agent_plan_updated" in event_names
    assert "analysis_bundle" in event_names
    assert event_names[-1] == "workflow_complete"

    plan_snapshot = memory.agent_cache.get("plan_state")
    assert isinstance(plan_snapshot, dict)
    node_payload = plan_snapshot["nodes"]["analysis_lane"]
    assert node_payload["status"] == "succeeded"
    assert node_payload["artifacts"]["final_output"]["analysis"] == "Analysis goes here."
    assert result.final_output["analysis"] == "Analysis goes here."


def test_agent_memory_records_receipts_and_clarifications() -> None:
    snapshot = SessionStateSnapshot(session_id="session-memory")
    memory = AgentMemory(snapshot)

    receipt_payload = {"status": "completed", "summary": "analysis refreshed"}
    memory.record_tool_receipt("analysis_lane", receipt_payload)
    recorded = memory.get_tool_receipt("analysis_lane")

    assert recorded is not None
    assert recorded["summary"] == "analysis refreshed"

    clarification_payload = {"question": "Need primary ticker confirmation"}
    memory.record_clarification(clarification_payload)

    clarifications = memory.agent_cache.get("clarifications")
    assert isinstance(clarifications, list)
    assert clarifications and clarifications[0]["question"] == "Need primary ticker confirmation"
