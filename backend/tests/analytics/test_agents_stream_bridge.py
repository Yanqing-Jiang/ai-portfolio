from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any, Dict

import pytest

from analytics.flows.agents_stream_bridge import AgentsStreamBridge
from analytics.flows.schedulers import FlowMode
from analytics.tools import DEFAULT_SCHEMA_VERSION
from agents.stream_events import AgentUpdatedStreamEvent, RawResponsesStreamEvent, RunItemStreamEvent

# --- Analytics Function/Class Map ---
# Function: test_bridge_emits_tool_call_events
#   Role: Verifies AgentsStreamBridge forwards tool start/delta/completion events with canonical metadata.
#   Called from: pytest
#   Invokes: analytics.flows.agents_stream_bridge.AgentsStreamBridge
#   Why: Ensures SINGLE_AGENT telemetry exposes lane/specialist/schema fields for frontend parity.
# Function: test_bridge_emits_analysis_events
#   Role: Confirms analysis streaming + completion payloads retain metadata across tool completions.
#   Called from: pytest
#   Invokes: analytics.flows.agents_stream_bridge.AgentsStreamBridge
#   Why: Guarantees narrative streaming cards show the analysis lane metadata.
# Function: test_bridge_emits_supervisor_events
#   Role: Validates supervisor start/summary envelopes so ProcessPanel can render manager runs.
#   Called from: pytest
#   Invokes: analytics.flows.agents_stream_bridge.AgentsStreamBridge
#   Why: Keeps MULTI_AGENT mode emitting consistent supervisor telemetry.
# Function: test_bridge_emits_lane_completions_for_supervisor_tools
#   Role: Checks multi-agent tool completions continue to emit agent_tool_complete events per tool.
#   Called from: pytest
#   Invokes: analytics.flows.agents_stream_bridge.AgentsStreamBridge
#   Why: Ensures fan-out tool completions surface even when definitions are unknown to the registry.
# --- End Analytics Function/Class Map ---


class _ToolCallRawItem:
    def __init__(self, tool_id: str, name: str) -> None:
        self.id = tool_id
        self.name = name
        self.call_id = None
        self.tool_call_id = None


class _ToolCallRunItem:
    def __init__(self, tool: Dict[str, Any]) -> None:
        self.raw_item = _ToolCallRawItem(tool["id"], tool["name"])


class _DeltaPayload:
    type = "response.function_call_arguments.delta"

    def __init__(self, entry: Dict[str, Any]) -> None:
        self.item_id = entry["item_id"]
        self.delta = entry["arguments_delta"]
        self.sequence_number = entry["sequence_number"]
        self.output_index = entry["output_index"]


class _DonePayload:
    type = "response.function_call_arguments.done"

    def __init__(self, entry: Dict[str, Any]) -> None:
        self.item_id = entry["item_id"]
        self.name = entry["name"]
        self.arguments = entry["arguments"]
        self.sequence_number = entry["sequence_number"]
        self.output_index = entry["output_index"]


class _ToolCompletionPayload:
    type = "response.output_item.done"

    def __init__(self, tool_id: str, name: str) -> None:
        self.item = SimpleNamespace(
            id=tool_id,
            name=name,
            status="completed",
            call_id=tool_id,
        )
        self.output_index = 0
        self.sequence_number = 1


@pytest.mark.asyncio
async def test_bridge_emits_tool_call_events() -> None:
    queue: "asyncio.Queue[Dict[str, Any]]" = asyncio.Queue()
    bridge = AgentsStreamBridge(flow_mode=FlowMode.SINGLE_AGENT, queue=queue)

    tool_entry = {
        "id": "fc_tool_1",
        "name": "classification",
    }
    run_item_event = RunItemStreamEvent(name="tool_called", item=_ToolCallRunItem(tool_entry))
    await bridge._handle_stream_event(run_item_event)

    turn_event = await queue.get()
    assert turn_event["event"] == "agent_turn_start"
    assert turn_event["data"]["role"] == "planner_agent"
    assert turn_event["data"]["lane"] == "classification"
    assert turn_event["data"]["schema_version"] == DEFAULT_SCHEMA_VERSION

    started_event = await queue.get()
    assert started_event["event"] == "agent_tool_call"
    started_tool = started_event["data"]["tool_call"]
    assert started_tool["name"] == "classification"
    assert started_tool["metadata"]["lane"] == "classification"
    assert started_tool["metadata"]["specialist_role"] == "planner_agent"
    assert started_tool["metadata"]["schema_version"] == DEFAULT_SCHEMA_VERSION
    assert started_tool["metadata"]["latency_budget_ms"] == 500
    assert started_tool["metadata"]["concurrency_limit"] == 1

    delta_entry = {
        "item_id": "fc_tool_1",
        "arguments_delta": {"query": "AMD revenue"},
        "sequence_number": 1,
        "output_index": 0,
    }
    await bridge._handle_stream_event(RawResponsesStreamEvent(data=_DeltaPayload(delta_entry)))

    done_entry = {
        "item_id": "fc_tool_1",
        "name": "classification",
        "arguments": {"query": "AMD revenue", "reason": "initial"},
        "sequence_number": 2,
        "output_index": 0,
    }
    await bridge._handle_stream_event(RawResponsesStreamEvent(data=_DonePayload(done_entry)))

    delta_event = await queue.get()
    assert delta_event["event"] == "tool_call_delta"
    assert delta_event["data"]["tool_call"]["arguments_delta"] == {"query": "AMD revenue"}
    assert delta_event["data"]["mode"] == "single_agent"
    assert delta_event["data"]["tool_call"]["metadata"]["lane"] == "classification"

    done_event = await queue.get()
    assert done_event["event"] == "tool_call_arguments"
    tool_call = done_event["data"]["tool_call"]
    assert tool_call["name"] == "classification"
    assert tool_call["metadata"]["schema_version"] == DEFAULT_SCHEMA_VERSION
    assert tool_call["metadata"]["latency_budget_ms"] == 500


@pytest.mark.asyncio
async def test_bridge_emits_analysis_events() -> None:
    queue: "asyncio.Queue[Dict[str, Any]]" = asyncio.Queue()
    bridge = AgentsStreamBridge(flow_mode=FlowMode.SINGLE_AGENT, queue=queue)

    delta_payload = SimpleNamespace(
        type="response.output_text.delta",
        item_id="msg_analysis",
        delta="Final",
        output_index=0,
        sequence_number=1,
    )
    done_payload = SimpleNamespace(
        type="response.output_text.done",
        item_id="msg_analysis",
        text="Final analysis text",
        output_index=0,
        sequence_number=2,
    )
    tool_done_payload = SimpleNamespace(
        type="response.output_item.done",
        item=SimpleNamespace(
            id="call-123",
            name="analysis_revision",
            status="completed",
            call_id="call-123",
        ),
        output_index=0,
        sequence_number=3,
    )

    await bridge._handle_raw_response_event(delta_payload)  # type: ignore[arg-type]
    streaming_event = await queue.get()
    assert streaming_event["event"] == "analysis_streaming"
    assert streaming_event["data"]["partial_analysis"] == "Final"
    assert streaming_event["data"]["schedule_stage"] == "analysis"

    await bridge._handle_raw_response_event(done_payload)  # type: ignore[arg-type]
    completion_event = await queue.get()
    assert completion_event["event"] == "analysis_complete"
    assert completion_event["data"]["analysis"] == "Final analysis text"
    assert completion_event["data"]["analysis_length"] == len("Final analysis text")
    assert completion_event["data"]["lane"] == "analysis"

    await bridge._handle_raw_response_event(tool_done_payload)  # type: ignore[arg-type]
    tool_event = await queue.get()
    assert tool_event["event"] == "agent_tool_complete"
    tool_call = tool_event["data"]["tool_call"]
    assert tool_call["name"] == "analysis_revision"
    assert tool_call["status"] == "completed"
    assert tool_call["metadata"]["lane"] == "analysis"
    assert tool_call["metadata"]["schema_version"] == DEFAULT_SCHEMA_VERSION

    turn_end = await queue.get()
    assert turn_end["event"] == "agent_turn_end"
    assert turn_end["data"]["role"] == "planner_agent"
    assert turn_end["data"]["status"] == "complete"


@pytest.mark.asyncio
async def test_bridge_emits_supervisor_events() -> None:
    queue: "asyncio.Queue[Dict[str, Any]]" = asyncio.Queue()
    bridge = AgentsStreamBridge(flow_mode=FlowMode.MULTI_AGENT, queue=queue)

    supervisor_agent = SimpleNamespace(name="analytics_supervisor", model="gpt-4o-mini")
    specialist_agent = SimpleNamespace(name="sql_specialist", model="gpt-4o-mini")

    await bridge._handle_stream_event(AgentUpdatedStreamEvent(new_agent=supervisor_agent))
    start_event = await queue.get()
    assert start_event["event"] == "agent_supervisor_started"
    assert start_event["data"]["agent"] == "analytics_supervisor"
    assert start_event["data"]["mode"] == "multi_agent"

    await bridge._handle_stream_event(AgentUpdatedStreamEvent(new_agent=specialist_agent))
    await bridge._emit_supervisor_summary()
    summary_event = await queue.get()
    assert summary_event["event"] == "agent_supervisor_summary"
    assert summary_event["data"]["specialists"] == ["sql_specialist"]


@pytest.mark.asyncio
async def test_bridge_emits_lane_completions_for_supervisor_tools() -> None:
    queue: "asyncio.Queue[Dict[str, Any]]" = asyncio.Queue()
    bridge = AgentsStreamBridge(flow_mode=FlowMode.MULTI_AGENT, queue=queue)

    lane_tools = ("sql_generator", "web_retriever", "analysis_writer")
    for index, tool in enumerate(lane_tools):
        tool_entry = {"id": f"{tool}_id_{index}", "name": tool}
        await bridge._handle_stream_event(RunItemStreamEvent(name="tool_called", item=_ToolCallRunItem(tool_entry)))
        completion_payload = _ToolCompletionPayload(tool_entry["id"], tool)
        await bridge._handle_raw_response_event(completion_payload)  # type: ignore[arg-type]
        turn_start = await queue.get()
        assert turn_start["event"] == "agent_turn_start"
        started_event = await queue.get()
        assert started_event["event"] == "agent_tool_call"
        completion_event = await queue.get()
        assert completion_event["event"] == "agent_tool_complete"
        tool_call = completion_event["data"]["tool_call"]
        assert tool_call["name"] == tool
        turn_end = await queue.get()
        assert turn_end["event"] == "agent_turn_end"
        assert turn_end["data"]["tool"] == tool


@pytest.mark.asyncio
async def test_bridge_emits_latency_guardrail_on_budget_violation(monkeypatch: pytest.MonkeyPatch) -> None:
    queue: "asyncio.Queue[Dict[str, Any]]" = asyncio.Queue()
    bridge = AgentsStreamBridge(flow_mode=FlowMode.SINGLE_AGENT, queue=queue)

    tick_values = iter([10.0, 12.5])

    def _fake_monotonic() -> float:
        try:
            return next(tick_values)
        except StopIteration:
            return 12.5

    monkeypatch.setattr("analytics.flows.agents_stream_bridge.time.monotonic", _fake_monotonic)

    tool_entry = {"id": "classification_tool_guardrail", "name": "classification"}
    await bridge._handle_stream_event(RunItemStreamEvent(name="tool_called", item=_ToolCallRunItem(tool_entry)))
    turn_start = await queue.get()
    assert turn_start["event"] == "agent_turn_start"
    await queue.get()  # Drain agent_tool_call

    completion_payload = _ToolCompletionPayload(tool_entry["id"], tool_entry["name"])
    await bridge._handle_raw_response_event(completion_payload)  # type: ignore[arg-type]
    completion_event = await queue.get()
    assert completion_event["event"] == "agent_tool_complete"
    guardrail = completion_event["data"].get("latency_guardrail") or {}
    assert guardrail.get("status") == "violation"
    assert guardrail.get("tool") == "classification"
    assert completion_event["data"]["elapsed_ms"] >= 2000
