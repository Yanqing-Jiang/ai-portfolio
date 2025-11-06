from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from agents import Runner
from agents.run import RunConfig
from agents.stream_events import (
    AgentUpdatedStreamEvent,
    RawResponsesStreamEvent,
    RunItemStreamEvent,
    StreamEvent,
)

from analytics.flows.agents_stream_bridge import AgentsStreamBridge
from analytics.flows.single_agent_tools import (
    SingleAgentController,
    _SingleAgentRunContext,
)
from analytics.validators import sanitize_for_json


LOGGER = logging.getLogger("analytics.dump_agents_stream")


def _default_output_path() -> Path:
    return Path("docs/references/agents-stream-fixture.json")


def _coerce(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (str, int, float, bool)):
        return value
    if hasattr(value, "model_dump"):
        try:
            return _coerce(value.model_dump())
        except Exception:
            return str(value)
    if isinstance(value, dict):
        return {str(key): _coerce(val) for key, val in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_coerce(entry) for entry in value]
    if hasattr(value, "__dict__"):
        return _coerce(vars(value))
    return str(value)


def _summarize_stream_event(event: StreamEvent) -> Dict[str, Any]:
    summary: Dict[str, Any] = {"type": event.__class__.__name__}
    if isinstance(event, RunItemStreamEvent):
        summary["name"] = event.name
        summary["item"] = _coerce(getattr(event, "item", None))
    elif isinstance(event, RawResponsesStreamEvent):
        summary["data"] = _coerce(getattr(event, "data", None))
    elif isinstance(event, AgentUpdatedStreamEvent):
        summary["agent"] = _coerce(getattr(event, "agent", None))
    return sanitize_for_json(summary)


class RecordingAgentsStreamBridge(AgentsStreamBridge):
    def __init__(
        self,
        *,
        raw_event_log: List[Dict[str, Any]],
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self._raw_event_log = raw_event_log

    async def _handle_stream_event(self, event: StreamEvent) -> None:
        self._raw_event_log.append(_summarize_stream_event(event))
        await super()._handle_stream_event(event)


async def _dump_stream(
    *,
    query: str,
    output_path: Path,
    session_id: Optional[str],
    max_turns: Optional[int],
) -> None:
    os.environ.setdefault("ANALYTICS_ENABLE_AGENTS", "1")

    controller = SingleAgentController()
    if not getattr(controller, "_agents_enabled", False) or controller._agent is None:
        raise RuntimeError(
            "Agents mode is disabled. Set OPENAI_API_KEY and ANALYTICS_ENABLE_AGENTS=1 before running."
        )

    run_session = session_id or str(uuid.uuid4())
    state = await controller._prepare_sequencer_state(query, session_id=run_session)  # pylint: disable=protected-access

    queue: "asyncio.Queue[Optional[Dict[str, Any]]]" = asyncio.Queue()
    run_context = _SingleAgentRunContext(
        controller=controller,
        session_id=state.ctx.session_id or run_session,
        query=query,
        queue=queue,
        revision_directive=None,
    )

    turns = max_turns or controller._max_turns  # pylint: disable=protected-access
    run_config = RunConfig(model=controller._agent_model, trace_id=str(uuid.uuid4()))  # pylint: disable=protected-access
    run_context.trace_id = run_config.trace_id

    run_streaming = Runner.run_streamed(
        controller._agent,  # pylint: disable=protected-access
        input=query,
        context=run_context,
        max_turns=turns,
        run_config=run_config,
    )

    raw_events: List[Dict[str, Any]] = []
    bridge = RecordingAgentsStreamBridge(
        flow_mode=controller.flow_mode,
        queue=queue,
        raw_event_log=raw_events,
        logger=LOGGER,
    )
    bridge_task = asyncio.create_task(bridge.forward(run_streaming))

    sse_events: List[Dict[str, Any]] = []
    try:
        while True:
            if bridge_task.done() and queue.empty():
                break
            try:
                event = await asyncio.wait_for(queue.get(), timeout=0.25)
            except asyncio.TimeoutError:
                continue
            if event is None:
                continue
            sse_events.append(sanitize_for_json(event))

        run_result = await bridge_task
        try:
            await controller._persist_agent_run_metadata(  # pylint: disable=protected-access
                run_context=run_context,
                run_config=run_config,
                run_result=run_result,
                ctx=state.ctx,
            )
        except Exception:  # pragma: no cover - best effort persistence
            LOGGER.exception("Failed to persist agent run metadata")
    finally:
        controller._sequencer_state = None  # pylint: disable=protected-access

    output_payload = {
        "query": query,
        "session_id": run_context.session_id,
        "trace_id": run_context.trace_id,
        "raw_events": raw_events,
        "sse_events": sse_events,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(output_payload, indent=2), encoding="utf-8")
    LOGGER.info("Wrote %d raw events and %d SSE events to %s", len(raw_events), len(sse_events), output_path)


def _parse_args(argv: List[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Capture OpenAI Agents streaming events for the analytics single-agent flow "
            "and persist them as fixture data."
        )
    )
    parser.add_argument("query", help="Planner prompt to send to the single-agent runner.")
    parser.add_argument(
        "--output",
        type=Path,
        default=_default_output_path(),
        help="Destination path for the JSON fixture (default: %(default)s).",
    )
    parser.add_argument(
        "--session-id",
        dest="session_id",
        help="Optional session identifier to reuse when capturing the stream.",
    )
    parser.add_argument(
        "--max-turns",
        dest="max_turns",
        type=int,
        help="Optional override for the agent max_turns limit.",
    )
    return parser.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> None:
    args = _parse_args(argv or sys.argv[1:])
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    try:
        asyncio.run(
            _dump_stream(
                query=args.query,
                output_path=args.output,
                session_id=args.session_id,
                max_turns=args.max_turns,
            )
        )
    except KeyboardInterrupt:  # pragma: no cover - CLI convenience
        LOGGER.warning("Interrupted, exiting without writing fixture.")
    except Exception as exc:  # pragma: no cover - user feedback
        LOGGER.error("Failed to capture agent stream: %s", exc)
        sys.exit(1)


if __name__ == "__main__":
    main()
