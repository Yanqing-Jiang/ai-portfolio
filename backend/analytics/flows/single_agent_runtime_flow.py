from __future__ import annotations

import asyncio
import uuid
from typing import Any, AsyncGenerator, Dict, Optional

from analytics.agents.llm_adapter import build_responses_llm_adapter
from analytics.agents.runtime import SingleAgentRuntime
from analytics.core.events import EventEmitter

_SYSTEM_PROMPT = (
    "You are the analytics single agent. Follow the control flow: "
    "clarify missing slots when needed, build SQL, execute, enrich with web/analysis, "
    "and respond concisely with sources when available."
)


class SingleAgentRuntimeFlow:
    """Flow wrapper around the new single-agent runtime."""

    def __init__(self) -> None:
        self.flow_label = "single-agent-runtime"
        self._runtime = SingleAgentRuntime(
            system_prompt=_SYSTEM_PROMPT,
            flow_label=self.flow_label,
        )
        self._runtime.set_llm_adapter(build_responses_llm_adapter())

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

        agent_task = asyncio.create_task(
            self._runtime.handle_user_message(resolved_session, query)
        )

        try:
            while True:
                if agent_task.done() and event_queue.empty():
                    break
                try:
                    event = await asyncio.wait_for(event_queue.get(), timeout=0.1)
                    yield event
                except asyncio.TimeoutError:
                    if agent_task.done():
                        break
                    continue
        except Exception:
            agent_task.cancel()
            raise

        reply = await agent_task
        if reply.get("content"):
            yield EventEmitter.result("final_answer", {"content": reply["content"]})
        yield EventEmitter.complete("workflow", summary="Agent runtime finished")


__all__ = ["SingleAgentRuntimeFlow"]

