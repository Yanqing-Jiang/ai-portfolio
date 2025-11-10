# --- Analytics Function/Class Map ---
# Class: AgentEventBus
#   Role: Thin abstraction over the shared SSE queue used by analytics workflows.
#   Called from: analytics.agent_orchestrator, analytics.agent_orchestrator.agent_runtime
#   Collaborators: logging.getLogger, analytics.validators.sanitize_for_json, analytics.flows.schedulers.apply_mode_metadata
#   Why: Ensures all orchestrator events are sanitized and annotated with flow metadata before they are consumed by the existing frontend subscribers.
# --- End Analytics Function/Class Map ---
from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, Optional

from analytics.validators import sanitize_for_json
from analytics.core.events import EventEmitter
from analytics.flows.schedulers import FlowMode, apply_mode_metadata


class AgentEventBus:
    """
    Thin abstraction over the shared SSE queue used by analytics workflows.

    Ensures all orchestrator events are sanitized and annotated with flow metadata
    before they are consumed by the existing frontend subscribers.
    """

    def __init__(
        self,
        queue: "asyncio.Queue[Optional[Dict[str, Any]]]",
        *,
        flow_mode: Optional[FlowMode] = None,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        self._queue = queue
        self._flow_mode = flow_mode
        self._logger = logger or logging.getLogger(__name__)

    async def publish(self, event_name: str, data: Optional[Dict[str, Any]] = None) -> None:
        """Publish an event to the SSE queue."""
        payload = {"event": event_name, "data": sanitize_for_json(data or {})}
        if self._flow_mode is not None:
            payload = apply_mode_metadata(payload, self._flow_mode)
        await self._queue.put(payload)

    def publish_nowait(self, event_name: str, data: Optional[Dict[str, Any]] = None) -> None:
        """Non-blocking variant of publish."""
        payload = {"event": event_name, "data": sanitize_for_json(data or {})}
        if self._flow_mode is not None:
            payload = apply_mode_metadata(payload, self._flow_mode)
        try:
            self._queue.put_nowait(payload)
        except asyncio.QueueFull:
            self._logger.warning("AgentEventBus queue full; dropping event=%s", event_name)

    async def emit_progress(self, step: str, message: Optional[str] = None) -> None:
        """Convenience wrapper for EventEmitter.progress."""
        await self._enqueue(EventEmitter.progress(step, message))

    async def emit_error(self, step: str, error: str, *, code: Optional[str] = None) -> None:
        await self._enqueue(EventEmitter.error(step, error, code=code))

    async def emit_complete(self, step: str, summary: Optional[str] = None) -> None:
        await self._enqueue(EventEmitter.complete(step, summary))

    async def _enqueue(self, payload: Dict[str, Any]) -> None:
        if self._flow_mode is not None:
            payload = apply_mode_metadata(payload, self._flow_mode)
        await self._queue.put(payload)
