# --- Analytics Function/Class Map ---
# Class: AgentsStreamBridge
#   Role: Convert OpenAI Agents SDK streaming events into planner-style SSE payloads.
#   Called from: analytics.agent_orchestrator.agent_runtime, tests.analytics.test_agents_stream_bridge
#   Collaborators: analytics.flows.schedulers.apply_mode_metadata, logging.getLogger, analytics.validators.sanitize_for_json
#   Why: Supports downstream analytics workflows that rely on AgentsStreamBridge.
# --- End Analytics Function/Class Map ---
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from agents.result import RunResultStreaming
from agents.stream_events import (
    AgentUpdatedStreamEvent,
    RawResponsesStreamEvent,
    RunItemStreamEvent,
    StreamEvent,
)
from openai.types.responses.response_function_call_arguments_delta_event import (
    ResponseFunctionCallArgumentsDeltaEvent,
)
from openai.types.responses.response_function_call_arguments_done_event import (
    ResponseFunctionCallArgumentsDoneEvent,
)
from openai.types.responses.response_output_item_done_event import (
    ResponseOutputItemDoneEvent,
)
from openai.types.responses.response_text_delta_event import (
    ResponseTextDeltaEvent,
)
from openai.types.responses.response_text_done_event import (
    ResponseTextDoneEvent,
)

from analytics.flows.schedulers import FlowMode, apply_mode_metadata
from analytics.validators import sanitize_for_json


class AgentsStreamBridge:
    """Convert OpenAI Agents SDK streaming events into planner-style SSE payloads."""

    def __init__(
        self,
        *,
        flow_mode: FlowMode,
        queue: "asyncio.Queue[Optional[Dict[str, Any]]]",
        logger: Optional[logging.Logger] = None,
    ) -> None:
        self._flow_mode = flow_mode
        self._queue = queue
        self._logger = logger or logging.getLogger(__name__)
        self._tool_names: Dict[str, str] = {}
        self._output_buffers: Dict[str, str] = {}

    async def forward(self, result: RunResultStreaming) -> RunResultStreaming:
        """Translate streaming events into SSE payloads."""
        async for event in result.stream_events():
            await self._handle_stream_event(event)
        return result

    async def _handle_stream_event(self, event: StreamEvent) -> None:
        if isinstance(event, RunItemStreamEvent):
            self._remember_tool_metadata(event)
            return
        if isinstance(event, RawResponsesStreamEvent):
            await self._handle_raw_response_event(event.data)
            return
        if isinstance(event, AgentUpdatedStreamEvent):
            # No UI payload yet for agent swaps; remember for future supervisor work.
            return
        # Unknown event type - surface for diagnostics but do not fail the stream.
        self._logger.debug("Unhandled agent stream event: %s", type(event).__name__)

    def _remember_tool_metadata(self, event: RunItemStreamEvent) -> None:
        if event.name != "tool_called":
            return
        raw_item = getattr(event.item, "raw_item", None)
        tool_name = getattr(raw_item, "name", None)
        if not tool_name:
            return
        identifier_candidates = (
            getattr(raw_item, "id", None),
            getattr(raw_item, "call_id", None),
            getattr(raw_item, "tool_call_id", None),
        )
        for candidate in identifier_candidates:
            if candidate:
                self._tool_names[str(candidate)] = str(tool_name)

    async def _handle_raw_response_event(self, payload: Any) -> None:
        event_type = getattr(payload, "type", None)
        if event_type == "response.function_call_arguments.delta":
            await self._emit_tool_call_delta(payload)
            return
        if event_type == "response.function_call_arguments.done":
            await self._emit_tool_call_summary(payload)
            return
        if event_type == "response.output_text.delta":
            await self._emit_analysis_chunk(payload)
            return
        if event_type == "response.output_text.done":
            await self._emit_analysis_complete(payload)
            return
        if event_type == "response.output_item.done":
            await self._emit_tool_completion(payload)
            return
        if event_type == "response.reasoning_text.delta":
            await self._emit_reasoning_delta(getattr(payload, "delta", None))
            return
        # Other response event types are currently ignored.

    async def _emit_tool_call_delta(
        self, payload: ResponseFunctionCallArgumentsDeltaEvent
    ) -> None:
        tool_id = str(payload.item_id)
        tool_name = self._tool_names.get(tool_id)
        delta_payload = {
            "tool_call": self._clean_dict(
                {
                    "id": tool_id,
                    "name": tool_name,
                    "arguments_delta": payload.delta,
                    "sequence_number": payload.sequence_number,
                    "output_index": payload.output_index,
                }
            )
        }
        await self._enqueue_event("tool_call_delta", delta_payload)

    async def _emit_tool_call_summary(
        self, payload: ResponseFunctionCallArgumentsDoneEvent
    ) -> None:
        tool_id = str(payload.item_id)
        self._tool_names.setdefault(tool_id, payload.name)
        summary_payload = {
            "tool_call": self._clean_dict(
                {
                    "id": tool_id,
                    "name": payload.name,
                    "arguments": payload.arguments,
                    "sequence_number": payload.sequence_number,
                    "output_index": payload.output_index,
                }
            )
        }
        await self._enqueue_event("tool_call_arguments", summary_payload)

    async def _emit_reasoning_delta(self, thought: Optional[str]) -> None:
        if not thought:
            return
        payload = {
            "role": "planner_agent",
            "thought": thought,
        }
        await self._enqueue_event("agent_reasoning", payload)

    async def _emit_analysis_chunk(
        self, payload: ResponseTextDeltaEvent
    ) -> None:
        fragment = getattr(payload, "delta", None)
        if not fragment:
            return
        item_id = str(payload.item_id)
        existing = self._output_buffers.get(item_id, "")
        self._output_buffers[item_id] = existing + fragment
        chunk_payload = {
            "step": "analysis_generation",
            "partial_analysis": fragment,
            "chunk_length": len(fragment),
            "sequence_number": getattr(payload, "sequence_number", None),
            "output_index": getattr(payload, "output_index", None),
            "lane": "analysis",
            "schedule_stage": "analysis",
            "ts": datetime.now(timezone.utc).isoformat(),
        }
        await self._enqueue_event("analysis_streaming", chunk_payload)

    async def _emit_analysis_complete(
        self, payload: ResponseTextDoneEvent
    ) -> None:
        item_id = str(payload.item_id)
        buffered = self._output_buffers.pop(item_id, "")
        final_text = getattr(payload, "text", None) or buffered
        if not final_text:
            return
        analysis_payload = {
            "analysis": final_text,
            "analysis_length": len(final_text),
            "schedule_stage": "analysis",
            "lane": "analysis",
            "reused": False,
            "ts": datetime.now(timezone.utc).isoformat(),
        }
        await self._enqueue_event("analysis_complete", analysis_payload)

    async def _emit_tool_completion(
        self, payload: ResponseOutputItemDoneEvent
    ) -> None:
        item = getattr(payload, "item", None)
        if not item:
            return
        tool_name = getattr(item, "name", None)
        status = getattr(item, "status", None)
        if tool_name:
            self._tool_names[str(getattr(item, "id", tool_name))] = str(tool_name)
        completion_payload = {
            "tool_call": self._clean_dict(
                {
                    "id": getattr(item, "id", None),
                    "name": tool_name,
                    "status": status,
                    "call_id": getattr(item, "call_id", None),
                    "output_index": getattr(payload, "output_index", None),
                    "sequence_number": getattr(payload, "sequence_number", None),
                }
            )
        }
        await self._enqueue_event("agent_tool_complete", completion_payload)

    async def _enqueue_event(self, name: str, data: Dict[str, Any]) -> None:
        event = {"event": name, "data": sanitize_for_json(data)}
        annotated = apply_mode_metadata(event, self._flow_mode)
        await self._queue.put(annotated)

    @staticmethod
    def _clean_dict(data: Dict[str, Any]) -> Dict[str, Any]:
        return {key: value for key, value in data.items() if value is not None}
