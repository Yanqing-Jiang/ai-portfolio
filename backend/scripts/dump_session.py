from __future__ import annotations

import argparse
import asyncio
import json
from typing import Any, Dict

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from analytics.core.session_state import get_session_state_repository


def _serialize(obj: Any) -> Any:
    if isinstance(obj, (str, int, float, bool)) or obj is None:
        return obj
    if isinstance(obj, dict):
        return {str(key): _serialize(value) for key, value in obj.items()}
    if isinstance(obj, (list, tuple, set)):
        return [_serialize(item) for item in obj]
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    if hasattr(obj, "__dict__"):
        return _serialize(obj.__dict__)
    return str(obj)


async def _dump_session(session_id: str) -> Dict[str, Any]:
    repo = get_session_state_repository()
    snapshot = await repo.load(session_id)
    if snapshot is None:
        raise RuntimeError(f"No session snapshot found for '{session_id}'")
    payload: Dict[str, Any] = {
        "session_id": snapshot.session_id,
        "last_query": snapshot.last_query,
        "last_intent_key": snapshot.last_intent_key,
        "last_sql": snapshot.last_sql,
        "last_chart_spec": snapshot.last_chart_spec,
        "last_analysis": snapshot.last_analysis,
        "last_revision_directive": snapshot.last_revision_directive,
        "lane_timestamps": {lane: ts.isoformat() for lane, ts in snapshot.lane_timestamps.items()},
        "tool_cache_keys": list((snapshot.tool_cache or {}).keys()),
    }
    analytics_cache = (snapshot.tool_cache or {}).get("analytics") or {}
    payload["analytics"] = {
        "keys": list(analytics_cache.keys()),
        "revision_snapshot": analytics_cache.get("revision_snapshot"),
        "artifacts": analytics_cache.get("artifacts"),
        "artifact_version": analytics_cache.get("artifact_version"),
    }
    receipts = (snapshot.tool_cache or {}).get("tool_receipts") or {}
    payload["tool_receipts"] = receipts
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Dump stored analytics session state.")
    parser.add_argument("session_id", help="Session identifier to inspect.")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON output.")
    args = parser.parse_args()

    payload = asyncio.run(_dump_session(args.session_id))
    if args.pretty:
        print(json.dumps(_serialize(payload), indent=2, sort_keys=True))
    else:
        print(json.dumps(_serialize(payload)))


if __name__ == "__main__":
    main()
