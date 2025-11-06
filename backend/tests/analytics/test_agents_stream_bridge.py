from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any, Dict

import pytest

from analytics.flows.agents_stream_bridge import AgentsStreamBridge
from analytics.flows.schedulers import FlowMode
from agents.stream_events import RawResponsesStreamEvent, RunItemStreamEvent


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

    done_event = await queue.get()
    assert done_event["event"] == "tool_call_arguments"
    tool_call = done_event["data"]["tool_call"]
    assert tool_call["name"] == "classification"


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
