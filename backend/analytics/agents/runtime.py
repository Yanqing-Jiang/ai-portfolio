"""Runtime scaffolding for analytics single-agent flows."""
from __future__ import annotations

import inspect
import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Awaitable, Callable, Dict, List, Optional

from analytics.core.events import EventEmitter
from analytics.core.telemetry import tool_iteration

from .tool_registry import ToolRegistry
from .tools import register_default_tools

logger = logging.getLogger(__name__)


@dataclass
class AgentTurn:
    """Represents a single exchange in the agent conversation."""

    role: str
    content: str


@dataclass
class AgentSessionState:
    """Holds multi-turn context for an agent session."""

    session_id: str
    history: List[AgentTurn] = field(default_factory=list)
    tool_calls: int = 0
    llm_turn: int = 0
    last_response_id: Optional[str] = None

    def add_turn(self, role: str, content: str) -> None:
        self.history.append(AgentTurn(role=role, content=content))


EventCallback = Callable[[Dict[str, Any]], Awaitable[None] | None]


class SingleAgentRuntime:
    """Manages prompts, tool invocation, and guardrails for the simple agent."""

    def __init__(
        self,
        *,
        system_prompt: str,
        tool_registry: Optional[ToolRegistry] = None,
        max_tool_calls: int = 6,
        max_llm_turns: int = 8,
        auto_register_tools: bool = True,
        llm_adapter: Optional[Callable[[List[Dict[str, str]], Dict[str, Any]], Awaitable[Dict[str, Any]]]] = None,
        flow_label: str = "single-agent-runtime",
    ) -> None:
        self._system_prompt = system_prompt
        self._registry = tool_registry or ToolRegistry()
        if auto_register_tools:
            register_default_tools(self._registry)
            self._attach_logging_hooks()
        self._sessions: Dict[str, AgentSessionState] = {}
        self._sequence_by_session: Dict[str, int] = {}
        self._global_sequence: int = 0
        self._max_tool_calls = max_tool_calls
        self._max_llm_turns = max_llm_turns
        self._llm_adapter = llm_adapter
        self._flow_label = flow_label
        self._event_callback: Optional[EventCallback] = None

    @property
    def registry(self) -> ToolRegistry:
        return self._registry

    def set_event_callback(self, callback: Optional[EventCallback]) -> None:
        self._event_callback = callback

    def create_session(self, session_id: str) -> AgentSessionState:
        state = AgentSessionState(session_id=session_id)
        state.add_turn("system", self._system_prompt)
        self._sessions[session_id] = state
        self._sequence_by_session[session_id] = 0
        return state

    def get_session(self, session_id: str) -> AgentSessionState:
        if session_id not in self._sessions:
            return self.create_session(session_id)
        return self._sessions[session_id]

    async def handle_user_message(self, session_id: str, message: str) -> Dict[str, Any]:
        """Run the single-agent loop for a new user message."""

        state = self.get_session(session_id)
        state.add_turn("user", message)
        await self._emit_event(
            {
                "event": "agent_turn",
                "data": {
                    "role": "user",
                    "status": "received",
                    "turn": len(state.history),
                    "content": message,
                    "ts": datetime.utcnow().isoformat(),
                },
            },
            session_id=state.session_id,
        )
        reply = await self._run_agent_loop(state)
        return reply

    def set_llm_adapter(
        self,
        adapter: Callable[[List[Dict[str, str]], Dict[str, Any]], Awaitable[Dict[str, Any]]],
    ) -> None:
        """Configure the LLM adapter used to generate tool calls and replies."""

        self._llm_adapter = adapter

    async def _run_agent_loop(self, state: AgentSessionState) -> Dict[str, Any]:
        for turn_index in range(self._max_llm_turns):
            await self._emit_event(
                {
                    "event": "agent_turn",
                    "data": {
                        "role": "assistant",
                        "status": "thinking",
                        "turn": turn_index + 1,
                        "ts": datetime.utcnow().isoformat(),
                    },
                },
                session_id=state.session_id,
            )
            llm_output = await self._call_llm(state)
            if not isinstance(llm_output, dict):
                raise RuntimeError("LLM adapter must return a dict payload")
            decision = (llm_output.get("type") or "message").lower()
            if decision == "tool":
                tool_meta = llm_output.get("tool") or {}
                if not isinstance(tool_meta, dict):
                    raise RuntimeError("LLM tool payload must be an object")
                tool_name = tool_meta.get("name")
                if not tool_name:
                    raise RuntimeError("LLM requested tool call without a name")
                tool_payload = tool_meta.get("payload") or {}
                await self._emit_event(
                    {
                        "event": "agent_turn",
                        "data": {
                            "role": "assistant",
                            "status": "tool_call",
                            "tool": tool_name,
                            "turn": turn_index + 1,
                            "ts": datetime.utcnow().isoformat(),
                        },
                    },
                    session_id=state.session_id,
                )
                state.add_turn(
                    "assistant",
                    json.dumps(
                        {
                            "tool_call": tool_name,
                            "payload": tool_payload,
                        },
                        ensure_ascii=False,
                    ),
                )
                result = await self.invoke_tool(state.session_id, tool_name, tool_payload)
                state.add_turn(
                    "tool",
                    json.dumps(
                        {
                            "tool": tool_name,
                            "payload": tool_payload,
                            "result": result,
                        },
                        ensure_ascii=False,
                    ),
                )
                observation = llm_output.get("observation")
                if observation:
                    state.add_turn("system", f"[observation] {observation}")
                continue
            if decision == "message":
                content = llm_output.get("content")
                if not isinstance(content, str):
                    raise RuntimeError("LLM response missing 'content'")
                state.add_turn("assistant", content)
                await self._emit_event(
                    {
                        "event": "analysis_streaming",
                        "data": {
                            "step": "agent_reply",
                            "partial_analysis": content,
                            "chunk_length": len(content),
                            "ts": datetime.utcnow().isoformat(),
                            "response_id": state.last_response_id,
                        },
                    },
                    session_id=state.session_id,
                )
                result_payload = {
                    "role": "assistant",
                    "content": content,
                    "tool_calls": state.tool_calls,
                    "turns": turn_index + 1,
                    "response_id": state.last_response_id,
                }
                await self._emit_event(EventEmitter.result("agent_reply", result_payload), session_id=state.session_id)
                await self._emit_event(EventEmitter.complete("workflow", summary="Agent reply ready"), session_id=state.session_id)
                return result_payload
            if decision == "error":
                message = llm_output.get("message", "LLM reported an error")
                await self._emit_event(EventEmitter.error("agent_runtime", message), session_id=state.session_id)
                raise RuntimeError(message)
            raise RuntimeError(f"Unsupported LLM response type: {decision}")
        raise RuntimeError("Maximum LLM turns exceeded before reaching a final reply")

    async def _call_llm(self, state: AgentSessionState) -> Dict[str, Any]:
        if self._llm_adapter is None:
            raise RuntimeError("LLM adapter not configured for agent runtime")
        history_payload = [
            {"role": turn.role, "content": turn.content}
            for turn in state.history
        ]
        tool_specs = self._tool_spec_payload()
        response = await self._llm_adapter(history_payload, tool_specs)
        metadata = response.get("_metadata") if isinstance(response, dict) else None
        response_id = metadata.get("response_id") if isinstance(metadata, dict) else None
        state.llm_turn += 1
        state.last_response_id = response_id
        return response

    def _tool_spec_payload(self) -> Dict[str, Dict[str, Any]]:
        specs: Dict[str, Dict[str, Any]] = {}
        for name, spec in self._registry.list_specs().items():
            specs[name] = {
                "name": spec.name,
                "description": spec.description,
                "input_schema": spec.input_schema,
                "output_schema": spec.output_schema,
            }
        return specs

    def _attach_logging_hooks(self) -> None:
        for name in self._registry.list_specs():
            self._registry.register_hook(name, self._build_logging_hook(name))

    def _build_logging_hook(self, tool_name: str):
        async def _hook(payload: Dict[str, Any], result: Dict[str, Any]) -> None:
            try:
                payload_keys = list((payload or {}).keys())
                result_keys = list((result or {}).keys())
                logger.debug(
                    "Agent tool completed",
                    extra={
                        "tool": tool_name,
                        "payload_keys": payload_keys,
                        "result_keys": result_keys,
                    },
                )
            except Exception:  # pragma: no cover - logging safety
                logger.exception("Agent tool logging hook failed", extra={"tool": tool_name})
        return _hook

    async def invoke_tool(self, session_id: str, tool_name: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Invoke a registered tool while respecting guardrails."""

        self.record_tool_call(session_id)
        payload_keys = list((payload or {}).keys())
        start = time.perf_counter()
        await self._emit_event(
            {
                "event": "tool_call",
                "data": {
                    "tool": tool_name,
                    "status": "start",
                    "step": tool_name,
                    "payload_keys": payload_keys,
                    "ts": datetime.utcnow().isoformat(),
                },
            },
            session_id=session_id,
        )
        tool_iteration(
            tool=tool_name,
            status="start",
            step=tool_name,
            session_id=session_id,
            flow=self._flow_label,
            details={"payload_keys": payload_keys},
        )
        try:
            result = await self._registry.invoke(tool_name, payload)
            elapsed = int((time.perf_counter() - start) * 1000)
            result_keys = list((result or {}).keys())
            tool_iteration(
                tool=tool_name,
                status="end",
                step=tool_name,
                elapsed_ms=elapsed,
                session_id=session_id,
                flow=self._flow_label,
                details={"result_keys": result_keys},
            )
            await self._emit_event(
                {
                    "event": "tool_call",
                    "data": {
                        "tool": tool_name,
                        "status": "end",
                        "step": tool_name,
                        "result_keys": result_keys,
                        "elapsed_ms": elapsed,
                        "ts": datetime.utcnow().isoformat(),
                    },
                },
                session_id=session_id,
            )
            return result
        except Exception as exc:
            elapsed = int((time.perf_counter() - start) * 1000)
            tool_iteration(
                tool=tool_name,
                status="error",
                step=tool_name,
                elapsed_ms=elapsed,
                session_id=session_id,
                flow=self._flow_label,
                details={"error": str(exc)},
            )
            await self._emit_event(
                {
                    "event": "tool_call",
                    "data": {
                        "tool": tool_name,
                        "status": "error",
                        "step": tool_name,
                        "error": str(exc),
                        "elapsed_ms": elapsed,
                        "ts": datetime.utcnow().isoformat(),
                    },
                },
                session_id=session_id,
            )
            raise

    def record_tool_call(self, session_id: str) -> None:
        state = self.get_session(session_id)
        state.tool_calls += 1
        logger.debug(
            "Agent tool count incremented",
            extra={"session_id": session_id, "tool_calls": state.tool_calls},
        )
        if state.tool_calls > self._max_tool_calls:
            raise RuntimeError("Maximum tool calls exceeded for session")

    def _next_sequence(self, session_id: Optional[str]) -> int:
        if session_id:
            current = self._sequence_by_session.get(session_id, 0) + 1
            self._sequence_by_session[session_id] = current
            return current
        self._global_sequence += 1
        return self._global_sequence

    async def _emit_event(self, event: Optional[Dict[str, Any]], *, session_id: Optional[str] = None) -> None:
        if not event or self._event_callback is None:
            return
        data = event.get("data")
        if isinstance(data, dict):
            sequence = self._next_sequence(session_id)
            data.setdefault("sequence", sequence)
            if session_id:
                data.setdefault("session_id", session_id)
        try:
            result = self._event_callback(event)
            if inspect.isawaitable(result):
                await result  # type: ignore[func-returns-value]
        except Exception:
            logger.exception("Agent event callback failed", extra={"event": event.get("event")})





