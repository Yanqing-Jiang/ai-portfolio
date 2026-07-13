"""Apply one SQL migration using the backend's configured Supabase database.

This intentionally accepts exactly one checked-in file. The autodeploy gate
invokes it inside the existing backend image, with the newly pulled backend
tree mounted read-only, before replacing the live container.
"""

from __future__ import annotations

import asyncio
import hashlib
import os
from pathlib import Path
import re
import sys

import asyncpg


async def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: apply_migration.py /workspace/migrations/NNN_name.sql")
    path = Path(sys.argv[1]).resolve()
    allowed = {
        Path("/workspace/migrations").resolve(),  # autodeploy bind mount
        Path("/app/migrations").resolve(),       # container startup gate
    }
    if path.parent not in allowed or path.suffix != ".sql":
        raise SystemExit("migration must be a direct .sql child of an approved migration dir")
    database_url = os.environ.get("SUPABASE_DB_URL")
    if not database_url:
        raise SystemExit("SUPABASE_DB_URL is not configured")

    sql = path.read_text(encoding="utf-8")
    checksum = hashlib.sha256(sql.encode("utf-8")).hexdigest()
    transactional_sql = re.sub(
        r"(?m)^\s*(?:BEGIN|COMMIT);\s*$", "", sql,
    )
    version = path.name.split("_", 1)[0]
    if not version.isdigit():
        raise SystemExit("migration filename must begin with a numeric version")

    connection = await asyncpg.connect(database_url, statement_cache_size=0)
    try:
        # Supavisor's transaction-mode pooler does not preserve session locks
        # between statements. Keep the transaction-scoped advisory lock,
        # ledger bootstrap/check, migration, and ledger insert in one explicit
        # transaction so concurrent startup/autodeploy runners serialize on
        # the same server connection.
        async with connection.transaction():
            await connection.execute(
                "SELECT pg_advisory_xact_lock(hashtext('fortune_migrations'))"
            )
            await connection.execute(
                """
                CREATE TABLE IF NOT EXISTS public.fortune_schema_migration (
                    version TEXT PRIMARY KEY,
                    filename TEXT NOT NULL,
                    checksum TEXT NOT NULL,
                    applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )
            # Supabase may grant public-schema tables to its API roles via
            # default privileges. The ledger controls which migrations execute,
            # so it must never be writable (or readable) through PostgREST.
            await connection.execute(
                """
                ALTER TABLE public.fortune_schema_migration ENABLE ROW LEVEL SECURITY;
                REVOKE ALL ON public.fortune_schema_migration FROM PUBLIC, anon, authenticated;
                """
            )
            applied = await connection.fetchrow(
                "SELECT filename, checksum FROM public.fortune_schema_migration WHERE version = $1",
                version,
            )
            if applied is not None:
                if applied["filename"] != path.name or applied["checksum"] != checksum:
                    raise RuntimeError(
                        f"migration {version} is immutable but its filename/checksum changed"
                    )
                return
            await connection.execute(transactional_sql)
            await connection.execute(
                """
                INSERT INTO public.fortune_schema_migration (version, filename, checksum)
                VALUES ($1, $2, $3)
                """,
                version, path.name, checksum,
            )
    finally:
        await connection.close()


if __name__ == "__main__":
    asyncio.run(main())
