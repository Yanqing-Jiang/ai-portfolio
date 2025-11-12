import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Iterable, List, Optional, Sequence

from analytics.core.session_state import SessionStateSnapshot, get_session_state_repository


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


async def _process_session(session_id: str, *, dry_run: bool) -> bool:
    repo = get_session_state_repository()
    snapshot: Optional[SessionStateSnapshot] = await repo.load(session_id)
    if snapshot is None:
        print(f"[manifest-backfill] Session not found: {session_id}", file=sys.stderr)
        return False

    before_manifest = snapshot.analysis_inputs_manifest if isinstance(snapshot.analysis_inputs_manifest, dict) else {}
    before_receipts = dict(snapshot.tool_cache.get("analysis_lane_receipts") or {})

    snapshot.ensure_analysis_lane_receipts()
    snapshot.refresh_analysis_inputs_manifest()

    after_manifest = snapshot.analysis_inputs_manifest if isinstance(snapshot.analysis_inputs_manifest, dict) else {}
    after_receipts = dict(snapshot.tool_cache.get("analysis_lane_receipts") or {})

    changed = (after_manifest != before_manifest) or (after_receipts != before_receipts)
    if changed and not dry_run:
        await repo.save(snapshot)
    return changed


async def _run_backfill(session_ids: Iterable[str], *, dry_run: bool) -> None:
    total = 0
    touched = 0
    for session_id in session_ids:
        total += 1
        updated = await _process_session(session_id, dry_run=dry_run)
        if updated:
            touched += 1
    print(f"[manifest-backfill] Processed {total} session(s); updated {touched}. Dry run={dry_run}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill analysis input manifests and lane receipts.")
    parser.add_argument(
        "--session",
        action="append",
        dest="sessions",
        default=[],
        help="Session ID to backfill (may be provided multiple times).",
    )
    parser.add_argument(
        "--session-list",
        dest="session_list",
        help="Path to a JSON or newline-delimited list of session IDs.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Compute changes without writing them back to storage.",
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
