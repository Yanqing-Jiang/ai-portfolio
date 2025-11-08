import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Iterable, List, Optional, Sequence

from analytics.core.session_state import SessionStateSnapshot, get_session_state_repository
from analytics.flows.sequencer import LANE_TOOL_LOOKUP


def _normalize_session_ids(values: Sequence[str]) -> List[str]:
    normalized: List[str] = []
    for value in values:
        candidate = str(value or "").strip()
        if candidate:
            normalized.append(candidate)
    return normalized


def _load_ids_from_file(path: str) -> List[str]:
    file_path = Path(path)
    if not file_path.exists():
        raise FileNotFoundError(f"Session list not found: {path}")
    text = file_path.read_text(encoding="utf-8").strip()
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return _normalize_session_ids(text.splitlines())
    if isinstance(payload, list):
        return _normalize_session_ids([str(item) for item in payload])
    raise ValueError(f"Unsupported session list format in {path!s}")


def _resolve_lane(tool_name: str, snapshot: SessionStateSnapshot) -> Optional[str]:
    lane = snapshot.tool_cache.get("tool_receipts", {}).get(tool_name, {}).get("lane")
    if isinstance(lane, str) and lane.strip():
        return lane.strip().lower()
    normalized = tool_name.strip().lower()
    return LANE_TOOL_LOOKUP.get(normalized)


def _merge_reuse_metadata(snapshot: SessionStateSnapshot, tool_name: str, lane: Optional[str]) -> bool:
    if not lane:
        return False
    receipts = snapshot.tool_cache.get("tool_receipts") or {}
    entry = receipts.get(tool_name)
    if not isinstance(entry, dict):
        return False
    reuse_metadata = entry.get("reuse_metadata")
    if reuse_metadata:
        return False
    lane_metadata = snapshot.get_lane_reuse_metadata(lane)
    if not lane_metadata:
        lane_metadata = {
            "lane": lane,
            "source": "backfill",
            "ts": snapshot.updated_at.isoformat(),
        }
    entry["reuse_metadata"] = lane_metadata
    snapshot.record_tool_receipt(tool_name, entry)
    return True


async def _process_session(session_id: str, *, dry_run: bool) -> bool:
    repo = get_session_state_repository()
    snapshot = await repo.load(session_id)
    if snapshot is None:
        print(f"[backfill] Session not found: {session_id}", file=sys.stderr)
        return False
    receipts = snapshot.tool_cache.get("tool_receipts") or {}
    updated = False
    for tool_name, payload in list(receipts.items()):
        if not isinstance(payload, dict):
            continue
        reused_flag = payload.get("reused")
        status = str(payload.get("status") or "").strip().lower()
        if not reused_flag and status != "reused":
            continue
        lane = payload.get("lane") or _resolve_lane(tool_name, snapshot)
        merged = _merge_reuse_metadata(snapshot, tool_name, lane)
        updated = updated or merged
    if updated and not dry_run:
        await repo.save(snapshot)
    return updated


async def _run_backfill(session_ids: Iterable[str], *, dry_run: bool) -> None:
    total = 0
    touched = 0
    for session_id in session_ids:
        total += 1
        updated = await _process_session(session_id, dry_run=dry_run)
        if updated:
            touched += 1
    print(f"[backfill] Processed {total} session(s); updated {touched}. Dry run={dry_run}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill accessory reuse receipts with metadata.")
    parser.add_argument(
        "--session",
        action="append",
        dest="sessions",
        default=[],
        help="Session ID to backfill (may be specified multiple times).",
    )
    parser.add_argument(
        "--session-list",
        dest="session_list",
        help="Path to a JSON or newline-delimited list of session IDs.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Compute changes without writing them back to Redis.",
    )
    args = parser.parse_args()
    session_ids: List[str] = _normalize_session_ids(args.sessions or [])
    if args.session_list:
        session_ids.extend(_load_ids_from_file(args.session_list))
    if not session_ids:
        parser.error("At least one --session or --session-list entry is required.")
    asyncio.run(_run_backfill(session_ids, dry_run=args.dry_run))


if __name__ == "__main__":
    main()
