from __future__ import annotations

from types import SimpleNamespace

import pytest

from analytics.core.session_state import SessionStateSnapshot
from analytics.flows.instrumentation import _maybe_update_session_state
from analytics.flows.schedulers import FlowMode
from analytics.flows.single_agent_tools import SingleAgentController


def _make_controller() -> SingleAgentController:
    # Disable live agent wiring so tests avoid network setup while still exercising annotation logic.
    return SingleAgentController(enable_agents=False)


def test_agent_event_annotation_assigns_lane_and_tool() -> None:
    controller = _make_controller()
    ctx = SimpleNamespace()
    base_event = {
        "event": "tool_call_delta",
        "data": {
            "tool_call": {
                "id": "call-1",
                "name": "web_retriever",
                "arguments_delta": {"query": "AMD revenue"},
                "sequence_number": 1,
                "output_index": 0,
            }
        },
    }

    annotated = controller._annotate_runtime_event(base_event, ctx)

    assert annotated["data"]["lane"] == "web"
    assert annotated["data"]["tool"] == "web_retriever"
    assert annotated["data"]["parallel_group"] == "single_agent_fanout"


def test_instrumentation_records_agent_tool_receipts() -> None:
    snapshot = SessionStateSnapshot(session_id="session-tool-receipt")

    arguments_event = {
        "event": "tool_call_arguments",
        "data": {
            "tool_call": {
                "id": "call-1",
                "name": "web_retriever",
                "arguments": {"query": "AMD revenue"},
                "sequence_number": 2,
                "output_index": 0,
            }
        },
    }
    updated = _maybe_update_session_state(
        snapshot,
        arguments_event,
        query="AMD revenue guidance",
        flow_mode=FlowMode.SINGLE_AGENT,
    )
    assert updated
    receipts = snapshot.tool_cache.get("tool_receipts", {})
    assert "web_retriever" in receipts
    assert receipts["web_retriever"]["arguments"] == {"query": "AMD revenue"}

    completion_event = {
        "event": "agent_tool_complete",
        "data": {
            "tool_call": {
                "id": "call-1",
                "name": "web_retriever",
                "status": "completed",
                "sequence_number": 3,
                "output_index": 0,
            }
        },
    }
    updated_complete = _maybe_update_session_state(
        snapshot,
        completion_event,
        query="AMD revenue guidance",
        flow_mode=FlowMode.SINGLE_AGENT,
    )
    assert updated_complete
    receipts = snapshot.tool_cache.get("tool_receipts", {})
    assert receipts["web_retriever"]["status"] == "completed"
