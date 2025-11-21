# --- Analytics Function/Class Map ---
# Function: _agent_role_for_tool
#   Role: Determine the specialist role for a tool so agent_turn_* events can mirror planner telemetry.
#   Called from: analytics.flows.agents_stream_bridge.AgentsStreamBridge._record_turn_start
#   Invokes: Internal helpers only
#   Why: Keeps supervisor and single-agent agent_turn events aligned with tool metadata for UI badges.
# Function: _agent_turn_payload
#   Role: Build the agent_turn_start/end payloads with lane, schema_version, and tool identifiers.
#   Called from: analytics.flows.agents_stream_bridge.AgentsStreamBridge._record_turn_start/_record_turn_end
#   Invokes: datetime.utcnow, analytics.flows.agents_stream_bridge.AgentsStreamBridge._clean_dict
#   Why: Ensures SSE turn events expose canonical metadata for ProcessPanel/WorkflowCanvas.
# Class: AgentsStreamBridge
#   Role: Convert OpenAI Agents SDK streaming events into planner-style SSE payloads.
#   Called from: analytics.agent_orchestrator.agent_runtime, tests.analytics.test_agents_stream_bridge
#   Collaborators: analytics.flows.schedulers.apply_mode_metadata, logging.getLogger, analytics.validators.sanitize_for_json
#   Why: Supports downstream analytics workflows that rely on AgentsStreamBridge.
# Class: ForbiddenToolCallError
#   Role: Raised when an incoming Agent SDK tool invocation violates a guardrail allowlist so controllers can redirect to DIRECT.
#   Called from: analytics.agent_orchestrator.agent_runtime.AgentRuntime.run via AgentsStreamBridge._handle_tool_called_event
#   Invokes: Exception base class only
#   Why: Surfaces guardrail-enforced tool blocking as a hard failure to keep telemetry honest when agents ignore allowlists.
# --- End Analytics Function/Class Map ---
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
import time
from typing import Any, Dict, List, Optional, Mapping, Iterable

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

from analytics.flows.planner_executor import _evaluate_latency_guardrail
from analytics.flows.schedulers import FlowMode, apply_mode_metadata
from analytics.tools import TOOL_REGISTRY
from analytics.validators import sanitize_for_json


class ForbiddenToolCallError(Exception):
    """Raised when an Agent SDK tool call violates the configured allowlist."""

    def __init__(self, tool_name: str, guardrail: Optional[Mapping[str, Any]] = None) -> None:
        super().__init__(tool_name)
        self.tool_name = tool_name
        self.guardrail = guardrail or {}


class AgentsStreamBridge:
    """Convert OpenAI Agents SDK streaming events into planner-style SSE payloads."""

    def __init__(
        self,
        *,
        flow_mode: FlowMode,
        queue: "asyncio.Queue[Optional[Dict[str, Any]]]",
        logger: Optional[logging.Logger] = None,
        tool_allowlist: Optional[Iterable[str]] = None,
        guardrail_metadata: Optional[Mapping[str, Any]] = None,
    ) -> None:
        self._flow_mode = flow_mode
        self._queue = queue
        self._logger = logger or logging.getLogger(__name__)
        allowlist_set = {tool.strip() for tool in (tool_allowlist or []) if isinstance(tool, str) and tool.strip()}
        self._tool_allowlist = allowlist_set if allowlist_set else None
        self._guardrail_metadata = sanitize_for_json(dict(guardrail_metadata or {})) if guardrail_metadata else None
        self._tool_names: Dict[str, str] = {}
        self._output_buffers: Dict[str, str] = {}
        self._supervisor_seen = False
        self._supervisor_specialists: List[str] = []
        self._tool_start_times: Dict[str, float] = {}
        self._definition_metadata = {
            definition.name: self._clean_dict(
                {
                    "lane": definition.lane,
                    "specialist_role": definition.specialist_role,
                    "schema_version": definition.schema_version,
                    "latency_budget_ms": definition.latency_budget_ms,
                    "concurrency_limit": definition.concurrency_limit,
                    "output_artifacts": list(definition.output_artifacts or (definition.outputs or ())),
                }
            )
            for definition in TOOL_REGISTRY.values()
        }
        self._definitions_by_name = {definition.name: definition for definition in TOOL_REGISTRY.values()}
        self._tool_metadata: Dict[str, Dict[str, Any]] = {}
        self._turn_state: Dict[str, Dict[str, Any]] = {}

    async def forward(self, result: RunResultStreaming) -> RunResultStreaming:
        """Translate streaming events into SSE payloads."""
        try:
            async for event in result.stream_events():
                await self._handle_stream_event(event)
        finally:
            await self._emit_supervisor_summary()
        return result

    async def _handle_stream_event(self, event: StreamEvent) -> None:
        if isinstance(event, RunItemStreamEvent):
            await self._handle_tool_called_event(event)
            return
        if isinstance(event, RawResponsesStreamEvent):
            await self._handle_raw_response_event(event.data)
            return
        if isinstance(event, AgentUpdatedStreamEvent):
            await self._handle_agent_updated_event(event)
            return
        # Unknown event type - surface for diagnostics but do not fail the stream.
        self._logger.debug("Unhandled agent stream event: %s", type(event).__name__)

    async def _handle_agent_updated_event(self, event: AgentUpdatedStreamEvent) -> None:
        agent = event.new_agent
        agent_name = str(getattr(agent, "name", "") or getattr(agent, "id", "") or "").strip()
        agent_role = str(getattr(agent, "role", "") or "").strip().lower()
        if self._is_supervisor_agent(agent_name, agent_role):
            if not self._supervisor_seen:
                self._supervisor_seen = True
                payload = {
                    "agent": agent_name or "supervisor",
                    "model": getattr(getattr(agent, "model", None), "name", None) or getattr(agent, "model", None),
                    "ts": datetime.utcnow().isoformat(),
                    "mode": self._flow_mode.value,
                }
                await self._enqueue_event("agent_supervisor_started", payload)
        else:
            identifier = agent_name or agent_role or getattr(agent, "instructions", None)
            if identifier:
                if identifier not in self._supervisor_specialists:
                    self._supervisor_specialists.append(identifier)

    def _is_supervisor_agent(self, name: str, role: str) -> bool:
        lowered = (name or role or "").lower()
        return "supervisor" in lowered

    async def _emit_supervisor_summary(self) -> None:
        if not self._supervisor_seen:
            return
        payload = {
            "ts": datetime.utcnow().isoformat(),
            "specialists": list(self._supervisor_specialists),
            "mode": self._flow_mode.value,
        }
        await self._enqueue_event("agent_supervisor_summary", payload)
        self._supervisor_seen = False
        self._supervisor_specialists.clear()

    async def _handle_tool_called_event(self, event: RunItemStreamEvent) -> None:
        if event.name != "tool_called":
            return
        raw_item = getattr(event.item, "raw_item", None)
        if raw_item is None:
            return
        tool_id = self._extract_tool_identifier(raw_item)
        tool_name = getattr(raw_item, "name", None)
        if tool_id:
            self._tool_names[tool_id] = str(tool_name or tool_id)
            self._tool_start_times[tool_id] = time.monotonic()
        violation = self._tool_violation(tool_name)
        if violation is not None:
            await self._enqueue_event(
                "workflow_error",
                {
                    "error_code": "agent_tool_blocked",
                    "tool": tool_name,
                    "tool_call_id": tool_id,
                    "guardrail": violation,
                },
            )
            raise ForbiddenToolCallError(str(tool_name or ""), violation)
        metadata = self._merge_tool_metadata(
            tool_id=tool_id,
            tool_name=tool_name,
            runtime_metadata=getattr(raw_item, "metadata", None),
        )
        await self._record_turn_start(tool_id=tool_id, tool_name=tool_name, metadata=metadata)
        payload = {
            "tool_call": self._clean_dict(
                {
                    "id": tool_id,
                    "name": tool_name,
                    "status": "running",
                    "metadata": metadata or None,
                }
            )
        }
        await self._enqueue_event("agent_tool_call", payload)

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
        metadata = self._merge_tool_metadata(tool_id=tool_id, tool_name=tool_name, runtime_metadata=None)
        delta_payload = {
            "tool_call": self._clean_dict(
                {
                    "id": tool_id,
                    "name": tool_name,
                    "arguments_delta": payload.delta,
                    "sequence_number": payload.sequence_number,
                    "output_index": payload.output_index,
                    "metadata": metadata or None,
                }
            )
        }
        await self._enqueue_event("tool_call_delta", delta_payload)

    async def _emit_tool_call_summary(
        self, payload: ResponseFunctionCallArgumentsDoneEvent
    ) -> None:
        tool_id = str(payload.item_id)
        self._tool_names.setdefault(tool_id, payload.name)
        metadata = self._merge_tool_metadata(tool_id=tool_id, tool_name=payload.name, runtime_metadata=None)
        summary_payload = {
            "tool_call": self._clean_dict(
                {
                    "id": tool_id,
                    "name": payload.name,
                    "arguments": payload.arguments,
                    "sequence_number": payload.sequence_number,
                    "output_index": payload.output_index,
                    "metadata": metadata or None,
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
        tool_id = self._extract_tool_identifier(item)
        if tool_name:
            identifier_key = tool_id or str(getattr(item, "id", tool_name))
            self._tool_names[str(identifier_key)] = str(tool_name)
        metadata = self._merge_tool_metadata(
            tool_id=tool_id,
            tool_name=tool_name,
            runtime_metadata=getattr(item, "metadata", None),
        )
        elapsed_ms: Optional[int] = None
        if tool_id and tool_id in self._tool_start_times:
            try:
                elapsed_ms = int((time.monotonic() - self._tool_start_times.pop(tool_id)) * 1000)
            except Exception:
                elapsed_ms = None
        guardrail_payload = self._build_latency_guardrail(tool_name, elapsed_ms)
        completion_payload = {
            "tool_call": self._clean_dict(
                {
                    "id": tool_id or getattr(item, "id", None),
                    "name": tool_name,
                    "status": status,
                    "call_id": getattr(item, "call_id", None),
                    "output_index": getattr(payload, "output_index", None),
                    "sequence_number": getattr(payload, "sequence_number", None),
                    "metadata": metadata or None,
                }
            )
        }
        if elapsed_ms is not None:
            completion_payload["elapsed_ms"] = elapsed_ms
            completion_payload["tool_call"]["elapsed_ms"] = elapsed_ms
            metadata.setdefault("elapsed_ms", elapsed_ms)
        if guardrail_payload:
            completion_payload["latency_guardrail"] = guardrail_payload
            completion_payload["tool_call"]["metadata"] = metadata or {}
            completion_payload["tool_call"]["metadata"]["guardrail"] = guardrail_payload
        await self._enqueue_event("agent_tool_complete", completion_payload)
        if tool_id:
            self._tool_metadata.pop(tool_id, None)
            self._tool_start_times.pop(tool_id, None)
        await self._record_turn_end(tool_id=tool_id, tool_name=tool_name, metadata=metadata)

    async def _enqueue_event(self, name: str, data: Dict[str, Any]) -> None:
        event = {"event": name, "data": sanitize_for_json(data)}
        annotated = apply_mode_metadata(event, self._flow_mode)
        await self._queue.put(annotated)

    @staticmethod
    def _clean_dict(data: Dict[str, Any]) -> Dict[str, Any]:
        return {key: value for key, value in data.items() if value is not None}

    def _tool_violation(self, tool_name: Optional[str]) -> Optional[Dict[str, Any]]:
        """Return a guardrail payload when a tool is not allowlisted."""
        if not self._tool_allowlist or not tool_name:
            return None
        normalized = str(tool_name).strip()
        if not normalized:
            return None
        if normalized in self._tool_allowlist:
            return None
        payload: Dict[str, Any] = {
            "reason": "guardrail_allowlist_block",
            "tool": normalized,
        }
        if isinstance(self._guardrail_metadata, Mapping):
            payload["guardrail"] = dict(self._guardrail_metadata)
        return payload

    def _canonical_tool_metadata(self, tool_name: Optional[str]) -> Dict[str, Any]:
        if not tool_name:
            return {}
        canonical = self._definition_metadata.get(str(tool_name))
        return dict(canonical) if canonical else {}

    def _merge_tool_metadata(
        self,
        *,
        tool_id: Optional[str],
        tool_name: Optional[str],
        runtime_metadata: Optional[Any],
    ) -> Dict[str, Any]:
        merged: Dict[str, Any] = {}
        if tool_id and tool_id in self._tool_metadata:
            merged.update(self._tool_metadata[tool_id])
        if isinstance(runtime_metadata, dict):
            merged.update({key: value for key, value in runtime_metadata.items() if value is not None})
        for key, value in self._canonical_tool_metadata(tool_name).items():
            merged.setdefault(key, value)
        if self._guardrail_metadata:
            merged.setdefault("guardrail", self._guardrail_metadata)
        clean = {key: value for key, value in merged.items() if value is not None}
        if tool_id:
            if clean:
                self._tool_metadata[tool_id] = clean
            else:
                self._tool_metadata.pop(tool_id, None)
        return clean

    def _build_latency_guardrail(
        self,
        tool_name: Optional[str],
        elapsed_ms: Optional[int],
    ) -> Optional[Dict[str, Any]]:
        if not tool_name or elapsed_ms is None:
            return None
        definition = self._definitions_by_name.get(tool_name)
        if definition is None or definition.latency_budget_ms is None:
            return None
        stats = {"p50_ms": elapsed_ms, "p95_ms": elapsed_ms, "total_ms": elapsed_ms}
        guardrail = _evaluate_latency_guardrail(
            stats,
            p50_threshold=definition.latency_budget_ms,
            p95_threshold=definition.latency_budget_ms,
        )
        if not guardrail:
            return None
        guardrail["source"] = "agent_latency_budget"
        guardrail["tool"] = tool_name
        guardrail["threshold_ms"] = definition.latency_budget_ms
        return guardrail

    @staticmethod
    def _agent_role_for_tool(tool_name: Optional[str], metadata: Mapping[str, Any]) -> str:
        specialist_role = metadata.get("specialist_role")
        if isinstance(specialist_role, str) and specialist_role.strip():
            return specialist_role.strip()
        if isinstance(tool_name, str) and tool_name.strip():
            return tool_name.strip()
        return "planner_agent"

    def _agent_turn_payload(
        self,
        *,
        tool_id: Optional[str],
        tool_name: Optional[str],
        metadata: Mapping[str, Any],
        status: str,
        elapsed_ms: Optional[int] = None,
    ) -> Dict[str, Any]:
        role = self._agent_role_for_tool(tool_name, metadata)
        lane = metadata.get("lane") or metadata.get("telemetry_step")
        payload: Dict[str, Any] = {
            "role": role,
            "status": status,
            "tool": tool_name,
            "tool_call_id": tool_id,
            "lane": lane,
            "schema_version": metadata.get("schema_version"),
            "specialist_role": metadata.get("specialist_role"),
            "ts": datetime.utcnow().isoformat(),
        }
        if elapsed_ms is not None:
            payload["elapsed_ms"] = elapsed_ms
        for key in ("latency_budget_ms", "output_artifacts", "concurrency_limit"):
            if metadata.get(key) is not None:
                payload[key] = metadata.get(key)
        return self._clean_dict(payload)

    async def _record_turn_start(
        self, *, tool_id: Optional[str], tool_name: Optional[str], metadata: Mapping[str, Any]
    ) -> None:
        if not tool_id and not tool_name:
            return
        payload = self._agent_turn_payload(
            tool_id=tool_id,
            tool_name=tool_name,
            metadata=metadata,
            status="start",
        )
        if tool_id:
            self._turn_state[tool_id] = {
                "metadata": dict(metadata),
                "started_at": time.monotonic(),
                "tool_name": tool_name,
            }
        await self._enqueue_event("agent_turn_start", payload)

    async def _record_turn_end(
        self, *, tool_id: Optional[str], tool_name: Optional[str], metadata: Mapping[str, Any]
    ) -> None:
        turn_state = self._turn_state.pop(str(tool_id), None) if tool_id else None
        started_at = turn_state.get("started_at") if isinstance(turn_state, Mapping) else None
        elapsed_ms: Optional[int] = None
        if started_at is not None:
            try:
                elapsed_ms = int((time.monotonic() - float(started_at)) * 1000)
            except Exception:
                elapsed_ms = None
        elif metadata.get("elapsed_ms") is not None:
            try:
                elapsed_ms = int(metadata.get("elapsed_ms"))  # type: ignore[arg-type]
            except (TypeError, ValueError):
                elapsed_ms = None
        payload = self._agent_turn_payload(
            tool_id=tool_id,
            tool_name=tool_name or (turn_state or {}).get("tool_name"),
            metadata=(turn_state or {}).get("metadata") or metadata,
            status="complete",
            elapsed_ms=elapsed_ms,
        )
        if payload:
            await self._enqueue_event("agent_turn_end", payload)

    @staticmethod
    def _extract_tool_identifier(raw_item: Any) -> Optional[str]:
        for attr in ("id", "call_id", "tool_call_id"):
            value = getattr(raw_item, attr, None)
            if value:
                return str(value)
        return None
