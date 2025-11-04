from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import requests


def _now_tag() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")


def _write_events(events: List[Dict[str, Any]], suffix: str) -> str:
    timestamp = _now_tag()
    filename = f"docs/agent-process-ledger-debug-{timestamp}-{suffix}.json"
    with open(filename, "w", encoding="utf-8") as fh:
        json.dump(events, fh, indent=2, sort_keys=True)
    return filename


def _stream(
    base_url: str,
    query: str,
    *,
    session_id: Optional[str],
    flow: str,
) -> List[Dict[str, Any]]:
    params = {"query": query, "flow": flow}
    if session_id:
        params["session_id"] = session_id
    response = requests.get(
        f"{base_url}/api/analytics/memory/stream",
        params=params,
        headers={"Accept": "text/event-stream"},
        stream=True,
        timeout=(5, 300),
    )
    response.raise_for_status()
    events: List[Dict[str, Any]] = []
    try:
        for line in response.iter_lines(decode_unicode=True):
            if not line:
                continue
            if not line.startswith("data: "):
                continue
            payload = line[6:]
            try:
                event = json.loads(payload)
            except json.JSONDecodeError:
                continue
            events.append(event)
            if event.get("event") == "workflow_complete":
                break
    finally:
        response.close()
    return events


def main() -> None:
    parser = argparse.ArgumentParser(description="Reproduce baseline + analysis revision runs against the analytics workflow.")
    parser.add_argument("--base-url", default=os.getenv("BACKEND_URL", "http://localhost:8000"), help="Backend base URL.")
    parser.add_argument("--flow", default="single-agent", help="Workflow to exercise.")
    parser.add_argument("--baseline-query", required=True, help="Initial query to seed planner context.")
    parser.add_argument("--revision-query", required=True, help="Revision query to trigger analysis-only refresh.")
    args = parser.parse_args()

    baseline_events = _stream(args.base_url, args.baseline_query, session_id=None, flow=args.flow)
    baseline_file = _write_events(baseline_events, "baseline")
    print(f"Wrote baseline events to {baseline_file}")

    session_id = None
    for event in baseline_events:
        if event.get("event") == "session_started":
            data = event.get("data") or {}
            session_id = data.get("session_id")
            if session_id:
                break
    if not session_id:
        raise RuntimeError("Failed to capture session_id from baseline stream.")

    revision_events = _stream(args.base_url, args.revision_query, session_id=session_id, flow=args.flow)
    revision_file = _write_events(revision_events, "revision")
    print(f"Wrote revision events to {revision_file}")
    print(f"Session ID: {session_id}")


if __name__ == "__main__":
    main()
