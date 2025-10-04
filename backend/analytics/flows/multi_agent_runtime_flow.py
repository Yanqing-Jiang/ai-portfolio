from __future__ import annotations

import asyncio
import contextlib
import uuid
from typing import Any, AsyncGenerator, Dict, Optional

from analytics.core.events import EventEmitter
from analytics.agents.multi_runtime import MultiAgentRuntime


class MultiAgentRuntimeFlow:
    """Flow wrapper around the Responses-powered multi-agent runtime."""

    def __init__(self) -> None:
        self.flow_label = "multi-agent-runtime"
        self._runtime = MultiAgentRuntime()

    async def events(
        self,
        query: str,
        session_id: Optional[str] = None,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        resolved_session = session_id or str(uuid.uuid4())
        event_queue: asyncio.Queue = asyncio.Queue()

        async def _event_sink(event: Dict[str, Any]) -> None:
            await event_queue.put(event)

        self._runtime.set_event_callback(_event_sink)

        yield EventEmitter.session_started(resolved_session)

        runtime_task = asyncio.create_task(
            self._runtime.run(query, session_id=resolved_session)
        )

        try:
            while True:
                if runtime_task.done() and event_queue.empty():
                    break
                try:
                    event = await asyncio.wait_for(event_queue.get(), timeout=0.1)
                    yield event
                except asyncio.TimeoutError:
                    if runtime_task.done():
                        break
                    continue
        finally:
            runtime_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await runtime_task

        yield EventEmitter.complete("workflow", summary="Multi-agent runtime finished")
