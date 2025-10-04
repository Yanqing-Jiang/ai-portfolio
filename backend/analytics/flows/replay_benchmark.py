from __future__ import annotations

import argparse
import asyncio
import json
import time
from pathlib import Path
from typing import Any, AsyncGenerator, Dict, Iterable, List, Optional, Sequence

from .workflow import FLOW_FACTORIES, run_flow


def _default_flows() -> List[str]:
    return ["planner-executor", "single-agent", "multi-agent"]


async def _collect_events(
    flow: str,
    prompt: str,
    *,
    session_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    events: List[Dict[str, Any]] = []
    async for event in run_flow(flow, prompt, session_id=session_id, instrument=True, flow_label=flow):
        events.append(event)
    return events


def _summarize_events(flow: str, prompt: str, session_id: str, events: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    event_count = len(events)
    tool_calls = sum(1 for event in events if event.get("event") == "tool_call" and (event.get("data") or {}).get("status") == "start")
    errors = [event.get("data") for event in events if event.get("event") == "error"]
    final_payload = next((event.get("data") for event in reversed(events) if event.get("event") == "agent_reply"), None)
    return {
        "flow": flow,
        "prompt": prompt,
        "session_id": session_id,
        "event_count": event_count,
        "tool_call_count": tool_calls,
        "errors": errors,
        "final_response": final_payload,
    }


async def benchmark_prompts(
    prompts: Iterable[str],
    flows: Iterable[str],
    *,
    include_events: bool = False,
    session_prefix: str = "replay",
) -> List[Dict[str, Any]]:
    summaries: List[Dict[str, Any]] = []
    for flow in flows:
        if flow not in FLOW_FACTORIES:
            raise ValueError(f"Unsupported flow '{flow}'. Available flows: {', '.join(FLOW_FACTORIES)}")
        for index, prompt in enumerate(prompts):
            session_id = f"{session_prefix}-{flow}-{index}"
            start = time.perf_counter()
            events = await _collect_events(flow, prompt, session_id=session_id)
            duration_ms = int((time.perf_counter() - start) * 1000)
            summary = _summarize_events(flow, prompt, session_id, events)
            summary["duration_ms"] = duration_ms
            if include_events:
                summary["events"] = events
            summaries.append(summary)
    return summaries


def _parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Replay prompts against analytics flows and capture telemetry summaries.")
    parser.add_argument(
        "--prompt",
        action="append",
        dest="prompts",
        help="Prompt to evaluate; provide multiple --prompt flags to benchmark several queries.",
    )
    parser.add_argument(
        "--prompt-file",
        type=Path,
        dest="prompt_file",
        help="Optional text file containing one prompt per line.",
    )
    parser.add_argument(
        "--flow",
        action="append",
        dest="flows",
        help="Flow identifier to benchmark (e.g., multi-agent). Defaults to planner-executor, single-agent, multi-agent.",
    )
    parser.add_argument(
        "--include-events",
        action="store_true",
        help="Include raw events in the JSON output.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Optional path to write the benchmark summary as JSON. Defaults to stdout.",
    )
    return parser.parse_args(argv)


def _load_prompts(args: argparse.Namespace) -> List[str]:
    prompts: List[str] = []
    if args.prompts:
        prompts.extend(args.prompts)
    if args.prompt_file and args.prompt_file.exists():
        prompts.extend(line.strip() for line in args.prompt_file.read_text(encoding="utf-8").splitlines() if line.strip())
    if not prompts:
        raise ValueError("At least one prompt must be provided via --prompt or --prompt-file")
    return prompts


async def _main_async(args: argparse.Namespace) -> List[Dict[str, Any]]:
    prompts = _load_prompts(args)
    flows = args.flows or _default_flows()
    return await benchmark_prompts(prompts, flows, include_events=args.include_events)


def main(argv: Optional[Sequence[str]] = None) -> None:
    args = _parse_args(argv)
    summaries = asyncio.run(_main_async(args))
    payload = json.dumps(summaries, indent=2)
    if args.output:
        args.output.write_text(payload, encoding="utf-8")
    else:
        print(payload)


if __name__ == "__main__":
    main()
