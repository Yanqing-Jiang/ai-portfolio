#!/usr/bin/env python3
"""Backfill fortune_snapshot.data_model for schema_version=1 rows (Phase 3A).

Default is --dry-run (no writes). Pass --apply to persist.

Uses the shared normalizer in ``fortune.snapshot_model`` so backfilled
``data_model`` matches live dual-write semantics.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any

# Allow running as ``python scripts/backfill_fortune_snapshots_v2.py`` from repo root.
ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

BATCH_SIZE = 100


def _load_dotenv() -> None:
    env_path = BACKEND / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip("'").strip('"')
        os.environ.setdefault(key, value)


def _unpack(value: Any) -> Any:
    if value is None or isinstance(value, (dict, list)):
        return value
    if isinstance(value, (bytes, bytearray)):
        value = value.decode("utf-8")
    if isinstance(value, str):
        try:
            return json.loads(value)
        except (TypeError, ValueError):
            return None
    return value


async def _run(*, apply: bool) -> int:
    import asyncpg

    from fortune.snapshot_model import data_model_from_legacy_columns

    _load_dotenv()
    dsn = os.getenv("SUPABASE_DB_URL") or os.getenv("DATABASE_URL")
    if not dsn:
        print("ERROR: SUPABASE_DB_URL / DATABASE_URL not set", file=sys.stderr)
        return 2

    # pgbouncer / Supavisor transaction mode — disable prepared statements.
    conn = await asyncpg.connect(dsn, statement_cache_size=0)
    try:
        total = await conn.fetchval(
            """
            SELECT COUNT(*)::int FROM fortune_snapshot
            WHERE schema_version = 1 OR data_model IS NULL
            """
        )
        print(f"candidates={total} mode={'apply' if apply else 'dry-run'} batch={BATCH_SIZE}")

        offset = 0
        updated = 0
        skipped = 0
        errors = 0
        while True:
            rows = await conn.fetch(
                """
                SELECT s.fortune_id,
                       s.schema_version,
                       s.latest_overview,
                       s.latest_pillars,
                       s.latest_mechanics,
                       s.latest_narrative,
                       s.latest_trace,
                       s.latest_references,
                       s.latest_retrodictions,
                       s.data_model,
                       f.focus
                FROM fortune_snapshot s
                LEFT JOIN fortune f ON f.id = s.fortune_id
                WHERE s.schema_version = 1 OR s.data_model IS NULL
                ORDER BY s.fortune_id
                LIMIT $1 OFFSET $2
                """,
                BATCH_SIZE,
                offset,
            )
            if not rows:
                break

            for row in rows:
                fid = row["fortune_id"]
                try:
                    model = data_model_from_legacy_columns(
                        overview=_unpack(row["latest_overview"]),
                        pillars=_unpack(row["latest_pillars"]),
                        mechanics=_unpack(row["latest_mechanics"]),
                        narrative=_unpack(row["latest_narrative"]),
                        trace=_unpack(row["latest_trace"]),
                        references=_unpack(row["latest_references"]),
                        retrodictions=_unpack(row["latest_retrodictions"]),
                        focus=row["focus"],
                    )
                    keys = sorted(model.keys())
                    if apply:
                        await conn.execute(
                            """
                            UPDATE fortune_snapshot
                            SET data_model = $2::jsonb,
                                schema_version = 2
                            WHERE fortune_id = $1
                            """,
                            fid,
                            json.dumps(model),
                        )
                        print(f"APPLY {fid} keys={keys}")
                        updated += 1
                    else:
                        print(f"DRY   {fid} keys={keys} n_keys={len(keys)}")
                        skipped += 1
                except Exception as exc:
                    errors += 1
                    print(f"ERROR {fid}: {exc}", file=sys.stderr)

            offset += len(rows)
            if len(rows) < BATCH_SIZE:
                break

        print(
            f"summary candidates={total} "
            f"{'updated' if apply else 'would_update'}={updated if apply else skipped} "
            f"errors={errors}"
        )
        return 0 if errors == 0 else 1
    finally:
        await conn.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=True,
        help="Print planned updates without writing (default)",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Persist schema_version=2 + data_model for each candidate row",
    )
    args = parser.parse_args()
    apply = bool(args.apply)
    return asyncio.run(_run(apply=apply))


if __name__ == "__main__":
    raise SystemExit(main())
