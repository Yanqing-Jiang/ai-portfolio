# --- Analytics Function/Class Map ---
# Function: _coerce_event
#   Role: Normalize adhoc ledger rows or SSE payloads into an event dict.
#   Called from: Internal to analytics.scripts.schedule_replay
#   Invokes: Internal helpers only
#   Why: Supports downstream analytics workflows that rely on _coerce_event.
# Function: _load_json_events
#   Role: Handles load json events logic for analytics.scripts.schedule_replay.
#   Called from: Internal to analytics.scripts.schedule_replay
#   Invokes: json.loads, analytics.scripts.schedule_replay._coerce_event
#   Why: Keeps analytics.scripts.schedule_replay from duplicating load json events behavior across flows.
# Function: annotate_events
#   Role: Handles annotate events logic for analytics.scripts.schedule_replay.
#   Called from: Internal to analytics.scripts.schedule_replay
#   Invokes: analytics.flows.schedulers.apply_mode_metadata
#   Why: Keeps analytics.scripts.schedule_replay from duplicating annotate events behavior across flows.
# Function: summarize_events
#   Role: Handles summarize events logic for analytics.scripts.schedule_replay.
#   Called from: Internal to analytics.scripts.schedule_replay
#   Invokes: collections.Counter, collections.OrderedDict
#   Why: Keeps analytics.scripts.schedule_replay from duplicating summarize events behavior across flows.
# Function: render_summary
#   Role: Handles render summary logic for analytics.scripts.schedule_replay.
#   Called from: Internal to analytics.scripts.schedule_replay
#   Invokes: analytics.flows.schedulers.describe_mode_schedule
#   Why: Keeps analytics.scripts.schedule_replay from duplicating render summary behavior across flows.
# Function: main
#   Role: Handles main logic for analytics.scripts.schedule_replay.
#   Called from: Internal to analytics.scripts.schedule_replay
#   Invokes: argparse.ArgumentParser, analytics.flows.schedulers.FlowMode, analytics.scripts.schedule_replay.annotate_events, pathlib.Path, +2 more
#   Why: Keeps analytics.scripts.schedule_replay from duplicating main behavior across flows.
# --- End Analytics Function/Class Map ---
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, OrderedDict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence

from analytics.flows.schedulers import FlowMode, apply_mode_metadata, describe_mode_schedule


def _coerce_event(record: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize adhoc ledger rows or SSE payloads into an event dict."""
    event_name = record.get("event") or record.get("id") or record.get("name")
    data_obj = record.get("data")
    if not isinstance(data_obj, dict):
        # Fall back to treating the entire record (minus event/id fields) as data.
        data_obj = {k: v for k, v in record.items() if k not in {"event", "id", "name"}}
    normalized = {"event": str(event_name or "unknown"), "data": data_obj}
    if "timestamp" in record and "ts" not in normalized["data"]:
        normalized["data"]["ts"] = record["timestamp"]
    return normalized


def _load_json_events(path: Path) -> List[Dict[str, Any]]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(raw, dict):
        raw = raw.get("events") or raw.get("data") or raw
        if isinstance(raw, dict):
            raw = list(raw.values())
    if not isinstance(raw, Sequence):
        raise ValueError(f"Unsupported JSON payload in {path}")
    events: List[Dict[str, Any]] = []
    for item in raw:
        if isinstance(item, dict):
            events.append(_coerce_event(item))
    return events


def annotate_events(events: Iterable[Dict[str, Any]], mode: FlowMode) -> List[Dict[str, Any]]:
    annotated: List[Dict[str, Any]] = []
    for record in events:
        annotated.append(apply_mode_metadata(dict(record), mode))
    return annotated


def summarize_events(events: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    stage_counts = Counter()
    parallel_groups = Counter()
    first_occurrence: OrderedDict[str, Dict[str, Any]] = OrderedDict()
    for event in events:
        data = event.get("data") or {}
        stage = data.get("schedule_stage") or "unknown"
        stage_counts[stage] += 1
        group = data.get("parallel_group") or "unknown"
        parallel_groups[group] += 1
        if stage not in first_occurrence:
            first_occurrence[stage] = {
                "event": event.get("event"),
                "parallel_group": group,
                "ts": data.get("ts"),
            }
    return {
        "stages": stage_counts,
        "parallel_groups": parallel_groups,
        "first_stage_events": first_occurrence,
    }


def render_summary(summary: Dict[str, Any], mode: FlowMode) -> str:
    schedule = describe_mode_schedule(mode)
    lines = [
        f"Mode: {mode.value}",
        "Schedule stages observed:",
    ]
    for stage, count in summary["stages"].items():
        first = summary["first_stage_events"].get(stage)
        label = f"  - {stage}: {count} events"
        if first:
            label += f" (first event={first.get('event')}, ts={first.get('ts')})"
        lines.append(label)
    lines.append("Parallel groups:")
    for group, count in summary["parallel_groups"].items():
        lines.append(f"  - {group}: {count}")
    lines.append("Canonical schedule order:")
    for stage in schedule.get("stages", []):
        lines.append(
            f"  • {stage['key']} (parallel_group={stage['parallel_group']}, allows_parallel={stage['allows_parallel']})"
        )
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Annotate analytics events with scheduler metadata.")
    parser.add_argument("paths", nargs="+", help="JSON files containing event arrays or ledger exports.")
    parser.add_argument(
        "--mode",
        choices=[mode.value for mode in FlowMode],
        default=FlowMode.DIRECT.value,
        help="FlowMode to use when annotating events (default: direct).",
    )
    parser.add_argument(
        "--summary",
        action="store_true",
        help="Print a human-readable summary instead of emitting annotated JSON.",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Optional path to write annotated JSON or summary text.",
    )
    args = parser.parse_args(argv)
    mode = FlowMode(args.mode)
    collected: List[Dict[str, Any]] = []
    for raw_path in args.paths:
        path = Path(raw_path)
        if not path.exists():
            parser.error(f"file not found: {path}")
        collected.extend(_load_json_events(path))
    annotated = annotate_events(collected, mode)
    if args.summary:
        summary = summarize_events(annotated)
        output = render_summary(summary, mode)
    else:
        output = json.dumps(annotated, indent=2)
    if args.output:
        Path(args.output).write_text(output, encoding="utf-8")
    else:
        print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
