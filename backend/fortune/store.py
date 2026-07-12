"""Fortune domain store: Supabase-backed repository for the Ming Engine.

Durable records live in Supabase Postgres via asyncpg; active-run session
state lives in Redis/memory via ``state.py``.

Connection model
----------------
`SUPABASE_DB_URL` points at the Supavisor transaction-mode pooler, which does
not support server-side prepared statements. All asyncpg calls use
``statement_cache_size=0`` to avoid DuplicatePreparedStatementError.

Public surface
--------------
- ``get_fortune_pool()``: lazy singleton asyncpg pool
- ``FortuneRepository``: CRUD for fortune, fortune_run, fortune_snapshot,
  fortune_message, fortune_trace
- ``last_emitted_seq`` column remains on ``fortune_run`` for a later drop
  migration (Phase 3+); hot path no longer writes it (Redis stream IDs are
  the resume cursor). ``allocate_seq`` / ``allocate_seq_batch`` deleted.
"""

from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import UUID

import asyncpg

logger = logging.getLogger(__name__)

_pool: Optional[asyncpg.Pool] = None
_pool_lock = asyncio.Lock()


def _db_url() -> str:
    """Read SUPABASE_DB_URL lazily so late env hydration (e.g. docker secrets)
    isn't frozen out by a cached empty import-time read."""
    return os.getenv("SUPABASE_DB_URL", "")


async def get_fortune_pool() -> Optional[asyncpg.Pool]:
    """Lazy singleton asyncpg pool for the fortune schema."""
    global _pool
    if _pool is not None:
        return _pool
    url = _db_url()
    if not url:
        logger.warning("[FORTUNE] SUPABASE_DB_URL not configured — persistence disabled")
        return None
    async with _pool_lock:
        if _pool is not None:
            return _pool
        try:
            # Let asyncpg handle SSL from the URL's sslmode param. The Supavisor
            # pooler presents a self-signed chain that strict contexts reject.
            _pool = await asyncpg.create_pool(
                url,
                min_size=1,
                max_size=8,
                statement_cache_size=0,
                command_timeout=10.0,
            )
            logger.info("[FORTUNE] Supabase connection pool initialized")
            return _pool
        except Exception as exc:
            logger.error("[FORTUNE] Pool creation failed: %s", exc)
            return None


async def close_fortune_pool() -> None:
    """Close the singleton asyncpg pool if it was initialized."""
    global _pool
    if _pool is None:
        return
    await _pool.close()
    _pool = None


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class FortuneRecord:
    id: UUID
    birth_iso: str
    timezone: str
    focus: str | None
    question: str | None
    tone: str | None
    birth_time_unknown: bool
    gender: str
    surface_id: str
    locale: str
    created_at: datetime


@dataclass(slots=True)
class FortuneRunRecord:
    id: UUID
    fortune_id: UUID
    run_kind: str
    action_type: str | None
    status: str
    last_emitted_seq: int
    created_at: datetime


# ---------------------------------------------------------------------------
# Repository
# ---------------------------------------------------------------------------


class FortuneRepository:
    """CRUD for fortune domain tables. All methods are no-ops if pool is None."""

    def __init__(self, pool: Optional[asyncpg.Pool]) -> None:
        self.pool = pool

    @property
    def available(self) -> bool:
        return self.pool is not None

    # -- fortune ------------------------------------------------------------

    async def create_fortune(
        self,
        *,
        birth_iso: str,
        timezone_name: str,
        focus: str | None,
        question: str | None,
        tone: str | None,
        birth_time_unknown: bool,
        gender: str,
        surface_id: str,
        locale: str = "en",
        client_ip: str | None = None,
        user_agent: str | None = None,
    ) -> FortuneRecord | None:
        if self.pool is None:
            return None
        row = await self.pool.fetchrow(
            """
            INSERT INTO fortune (
                birth_iso, timezone, focus, question, tone,
                birth_time_unknown, gender, surface_id, locale,
                client_ip, user_agent
            )
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11)
            RETURNING id, birth_iso, timezone, focus, question, tone,
                      birth_time_unknown, gender, surface_id, locale, created_at
            """,
            birth_iso, timezone_name, focus, question, tone,
            birth_time_unknown, gender, surface_id, locale,
            client_ip, user_agent,
        )
        return FortuneRecord(
            id=row["id"],
            birth_iso=row["birth_iso"],
            timezone=row["timezone"],
            focus=row["focus"],
            question=row["question"],
            tone=row["tone"],
            birth_time_unknown=row["birth_time_unknown"],
            gender=row["gender"],
            surface_id=row["surface_id"],
            locale=row["locale"],
            created_at=row["created_at"],
        )

    async def get_fortune(self, fortune_id: UUID) -> FortuneRecord | None:
        if self.pool is None:
            return None
        row = await self.pool.fetchrow(
            """
            SELECT id, birth_iso, timezone, focus, question, tone,
                   birth_time_unknown, gender, surface_id, locale, created_at
            FROM fortune WHERE id = $1
            """,
            fortune_id,
        )
        if row is None:
            return None
        return FortuneRecord(**dict(row))

    # -- fortune_run --------------------------------------------------------

    async def create_run(
        self,
        *,
        fortune_id: UUID,
        run_kind: str,  # 'initial' | 'action'
        action_type: str | None = None,
        model_used: str | None = None,
        reasoning_effort: str | None = None,
        request_id: str | None = None,
        trace_id: str | None = None,
        group_id: str | None = None,
    ) -> FortuneRunRecord | None:
        if self.pool is None:
            return None
        row = await self.pool.fetchrow(
            """
            INSERT INTO fortune_run (
                fortune_id, run_kind, action_type, status,
                model_used, reasoning_effort, request_id, trace_id, group_id
            )
            VALUES ($1,$2,$3,'queued',$4,$5,$6,$7,$8)
            RETURNING id, fortune_id, run_kind, action_type, status,
                      last_emitted_seq, created_at
            """,
            fortune_id, run_kind, action_type,
            model_used, reasoning_effort, request_id, trace_id, group_id,
        )
        return FortuneRunRecord(**dict(row))

    async def update_run_status(
        self,
        run_id: UUID,
        status: str,  # queued | streaming | done | failed_guardrail | error | interrupted
        *,
        error_message: str | None = None,
        prompt_tokens: int | None = None,
        completion_tokens: int | None = None,
        reasoning_tokens: int | None = None,
    ) -> None:
        if self.pool is None:
            return
        now = datetime.now(timezone.utc)
        started_at = now if status == "streaming" else None
        finished_at = now if status in (
            "done", "failed_guardrail", "error", "interrupted",
        ) else None
        await self.pool.execute(
            """
            UPDATE fortune_run
            SET status = $2,
                error_message = COALESCE($3, error_message),
                prompt_tokens = COALESCE($4, prompt_tokens),
                completion_tokens = COALESCE($5, completion_tokens),
                reasoning_tokens = COALESCE($6, reasoning_tokens),
                started_at = COALESCE(started_at, $7),
                finished_at = COALESCE(finished_at, $8)
            WHERE id = $1
            """,
            run_id, status, error_message,
            prompt_tokens, completion_tokens, reasoning_tokens,
            started_at, finished_at,
        )

    # -- fortune_snapshot ---------------------------------------------------

    async def upsert_snapshot(
        self,
        fortune_id: UUID,
        *,
        status: str,  # 'partial' | 'done'
        overview: dict[str, Any] | None = None,
        pillars: dict[str, Any] | None = None,
        mechanics: dict[str, Any] | None = None,
        narrative: dict[str, Any] | None = None,
        trace: dict[str, Any] | None = None,
        references: dict[str, Any] | None = None,
        retrodictions: dict[str, Any] | None = None,
        data_model: dict[str, Any] | None = None,
        schema_version: int | None = None,
    ) -> None:
        """Upsert snapshot. Dual-write: legacy ``latest_*`` + optional v2 ``data_model``.

        When ``data_model`` is provided, ``schema_version`` defaults to 2.
        Legacy-only callers leave both unset so schema_version/data_model stay.
        """
        if self.pool is None:
            return
        import json

        def _j(v: Any) -> Any:
            return json.dumps(v) if v is not None else None

        if data_model is not None and schema_version is None:
            schema_version = 2

        await self.pool.execute(
            """
            INSERT INTO fortune_snapshot (
                fortune_id, snapshot_version, status,
                latest_overview, latest_pillars, latest_mechanics,
                latest_narrative, latest_trace, latest_references,
                latest_retrodictions, schema_version, data_model
            )
            VALUES ($1, 1, $2, $3::jsonb, $4::jsonb, $5::jsonb,
                    $6::jsonb, $7::jsonb, $8::jsonb, $9::jsonb,
                    COALESCE($10, 1), $11::jsonb)
            ON CONFLICT (fortune_id) DO UPDATE SET
                snapshot_version = fortune_snapshot.snapshot_version + 1,
                status = EXCLUDED.status,
                latest_overview    = COALESCE(EXCLUDED.latest_overview,    fortune_snapshot.latest_overview),
                latest_pillars     = COALESCE(EXCLUDED.latest_pillars,     fortune_snapshot.latest_pillars),
                latest_mechanics   = COALESCE(EXCLUDED.latest_mechanics,   fortune_snapshot.latest_mechanics),
                latest_narrative   = COALESCE(EXCLUDED.latest_narrative,   fortune_snapshot.latest_narrative),
                latest_trace       = COALESCE(EXCLUDED.latest_trace,       fortune_snapshot.latest_trace),
                latest_references  = COALESCE(EXCLUDED.latest_references,  fortune_snapshot.latest_references),
                -- Merge retrodictions rather than replacing so user corrections
                -- stored under ``corrections`` survive later snapshot writes.
                -- ``||`` is a shallow rhs-wins merge — our payload only carries
                -- ``items``, so pre-existing ``corrections`` are preserved.
                latest_retrodictions = CASE
                    WHEN EXCLUDED.latest_retrodictions IS NULL
                        THEN fortune_snapshot.latest_retrodictions
                    ELSE COALESCE(fortune_snapshot.latest_retrodictions, '{}'::jsonb)
                         || EXCLUDED.latest_retrodictions
                END,
                schema_version = COALESCE($10, fortune_snapshot.schema_version),
                data_model = COALESCE(EXCLUDED.data_model, fortune_snapshot.data_model)
            """,
            fortune_id, status,
            _j(overview), _j(pillars), _j(mechanics),
            _j(narrative), _j(trace), _j(references),
            _j(retrodictions),
            schema_version,
            _j(data_model),
        )

    async def upsert_correction(
        self,
        fortune_id: UUID,
        *,
        year: int,
        user_note: str,
        corrected_at: datetime,
    ) -> dict[str, str] | None:
        """Persist a per-year user correction on ``fortune_snapshot.latest_retrodictions``.

        Stores under the ``corrections`` key keyed by year. Uses ``jsonb_set``
        so we do not clobber other retrodiction fields. Returns the stored
        record so the route can echo it unchanged.

        Falls back to creating an empty snapshot row when none exists — keeps
        /correction usable on fortunes whose stream failed before the first
        snapshot write.
        """
        if self.pool is None:
            return None
        import json
        record = {
            "user_note": user_note,
            "corrected_at": corrected_at.isoformat(),
        }
        payload = json.dumps(record)
        year_key = str(year)
        # Explicit ::text cast on $2 because asyncpg cannot otherwise infer
        # a type for it (jsonb_build_object is polymorphic).
        #
        # We set the WHOLE `corrections` key in one shot rather than using
        # ``jsonb_set(..., ARRAY['corrections', $2::text], ..., true)``
        # because Postgres' ``jsonb_set`` only auto-creates the LEAF when
        # ``create_missing=true``; if intermediate ``corrections`` does not
        # already exist, it returns the target unchanged. So we instead
        # write the merged ``corrections`` object directly.
        await self.pool.execute(
            """
            INSERT INTO fortune_snapshot (
                fortune_id, snapshot_version, status, latest_retrodictions
            )
            VALUES ($1, 1, 'partial',
                    jsonb_build_object('corrections',
                        jsonb_build_object($2::text, $3::jsonb)))
            ON CONFLICT (fortune_id) DO UPDATE SET
                latest_retrodictions = jsonb_set(
                    COALESCE(fortune_snapshot.latest_retrodictions, '{}'::jsonb),
                    ARRAY['corrections'],
                    COALESCE(
                        fortune_snapshot.latest_retrodictions -> 'corrections',
                        '{}'::jsonb
                    ) || jsonb_build_object($2::text, $3::jsonb),
                    true
                ),
                snapshot_version = fortune_snapshot.snapshot_version + 1
            """,
            fortune_id, year_key, payload,
        )
        return record

    async def sweep_stuck_runs(self, *, older_than_minutes: int = 10) -> int:
        """Mark runs stuck in 'queued'/'streaming' past the threshold as 'interrupted'.

        Idempotent: runs that have already transitioned won't match. Returns the
        count of runs updated so the caller can log. Called from startup and
        on a periodic timer — a crashed worker leaves rows stuck otherwise and
        the replay endpoint reports 'pending' forever.
        """
        if self.pool is None:
            return 0
        row = await self.pool.fetchrow(
            """
            WITH swept AS (
                UPDATE fortune_run
                SET status = 'interrupted',
                    error_message = COALESCE(error_message, 'worker exited mid-stream'),
                    finished_at = NOW()
                WHERE status IN ('queued', 'streaming')
                  AND COALESCE(started_at, created_at) < NOW() - ($1 || ' minutes')::interval
                RETURNING 1
            )
            SELECT COUNT(*)::int AS n FROM swept
            """,
            str(older_than_minutes),
        )
        return int(row["n"]) if row else 0

    async def get_snapshot(self, fortune_id: UUID) -> dict[str, Any] | None:
        if self.pool is None:
            return None
        row = await self.pool.fetchrow(
            """
            SELECT fortune_id, snapshot_version, schema_version, status,
                   latest_overview, latest_pillars, latest_mechanics,
                   latest_narrative, latest_trace, latest_references,
                   latest_retrodictions, data_model, updated_at
            FROM fortune_snapshot WHERE fortune_id = $1
            """,
            fortune_id,
        )
        return dict(row) if row else None

    async def get_fortune_with_snapshot(
        self, fortune_id: UUID
    ) -> dict[str, Any] | None:
        """Fetch fortune metadata + snapshot in one round-trip for replay.

        Returns None if the fortune row doesn't exist. If the fortune exists
        but has no snapshot yet, snapshot fields are None (client should treat
        as 'pending').
        """
        if self.pool is None:
            return None
        row = await self.pool.fetchrow(
            """
            SELECT
                f.id                AS fortune_id,
                f.birth_iso,
                f.timezone,
                f.focus,
                f.question,
                f.tone,
                f.birth_time_unknown,
                f.gender,
                f.locale,
                f.created_at,
                s.snapshot_version,
                s.schema_version,
                s.status            AS snapshot_status,
                s.latest_overview,
                s.latest_pillars,
                s.latest_mechanics,
                s.latest_narrative,
                s.latest_trace,
                s.latest_references,
                s.latest_retrodictions,
                s.data_model,
                s.updated_at        AS snapshot_updated_at
            FROM fortune f
            LEFT JOIN fortune_snapshot s ON s.fortune_id = f.id
            WHERE f.id = $1
            """,
            fortune_id,
        )
        return dict(row) if row else None

    # -- fortune_message ----------------------------------------------------

    async def create_message(
        self,
        *,
        fortune_id: UUID,
        run_id: UUID | None,
        role: str,  # 'user' | 'assistant' | 'system'
        content: str,
        action_type: str | None = None,
        citations: list[dict[str, Any]] | None = None,
        model_used: str | None = None,
        duration_ms: int | None = None,
    ) -> UUID | None:
        if self.pool is None:
            return None
        import json
        row = await self.pool.fetchrow(
            """
            INSERT INTO fortune_message (
                fortune_id, run_id, role, action_type, content,
                citations, model_used, duration_ms
            )
            VALUES ($1,$2,$3,$4,$5,$6::jsonb,$7,$8)
            RETURNING id
            """,
            fortune_id, run_id, role, action_type, content,
            json.dumps(citations or []), model_used, duration_ms,
        )
        return row["id"] if row else None

    # -- fortune_trace ------------------------------------------------------

    async def get_latest_run_id(self, fortune_id: UUID) -> UUID | None:
        """Return the most recent fortune_run id for a fortune, if any."""
        if self.pool is None:
            return None
        row = await self.pool.fetchrow(
            """
            SELECT id FROM fortune_run
            WHERE fortune_id = $1
            ORDER BY created_at DESC
            LIMIT 1
            """,
            fortune_id,
        )
        return row["id"] if row else None

    async def list_trace_projections(
        self,
        fortune_id: UUID,
        *,
        run_id: UUID | None = None,
    ) -> tuple[UUID | None, list[dict[str, Any]]]:
        """Return redacted Glass Box projections for ALL of the fortune's runs.

        Rows in ``fortune_trace`` are already allowlisted/redacted at write
        time. This read path re-shapes them into the live ``payload.trace``
        projection so the frontend renders one shape for live + replay.
        Fortune-scoped (pipeline run + every Ask turn, chronological) — a
        latest-run-only read would drop the pipeline trace after the first
        Ask. Pass ``run_id`` to scope to a single run.
        """
        if self.pool is None:
            return None, []

        latest_run_id = run_id or await self.get_latest_run_id(fortune_id)
        if latest_run_id is None:
            return None, []

        if run_id is not None:
            where = "t.run_id = $1"
            params: list[Any] = [run_id]
        else:
            where = "t.run_id IN (SELECT r.id FROM fortune_run r WHERE r.fortune_id = $1)"
            params = [fortune_id]

        rows = await self.pool.fetch(
            f"""
            SELECT
                t.run_id,
                t.span_id,
                t.phase,
                t.parent_span_id,
                t.span_type,
                t.agent_name,
                t.tool_name,
                t.model,
                t.input_json,
                t.output_json,
                t.error,
                t.started_at,
                t.ended_at,
                t.duration_ms
            FROM fortune_trace t
            WHERE {where}
            ORDER BY t.started_at ASC NULLS LAST, t.span_id ASC, t.phase ASC
            LIMIT 1000
            """,
            *params,
        )

        events: list[dict[str, Any]] = []
        for row in rows:
            events.append(_trace_row_to_projection(dict(row)))
        return latest_run_id, events


def _jsonb_summary(value: Any, key: str = "summary") -> str:
    if isinstance(value, str):
        try:
            value = _json_loads(value)
        except Exception:
            return value[:240]
    if isinstance(value, dict):
        raw = value.get(key, "")
        return "" if raw is None else str(raw)
    return ""


def _jsonb_status(value: Any, error: Any) -> str:
    if error:
        return "error"
    if isinstance(value, str):
        try:
            value = _json_loads(value)
        except Exception:
            return "success"
    if isinstance(value, dict):
        status = value.get("status")
        if isinstance(status, str) and status:
            return status
    return "success"


def _json_loads(raw: str) -> Any:
    import json
    return json.loads(raw)


def _trace_row_to_projection(row: dict[str, Any]) -> dict[str, Any]:
    """Map a durable fortune_trace row onto the live payload.trace shape."""
    run_id = str(row["run_id"])
    span_id = str(row["span_id"])
    phase = str(row.get("phase") or "complete")
    started = row.get("started_at")
    ended = row.get("ended_at")
    return {
        "eventId": f"{run_id}:{span_id}:{phase}",
        "runId": run_id,
        "spanId": span_id,
        "phase": phase,
        "parentSpanId": row.get("parent_span_id"),
        "spanType": row.get("span_type"),
        "agentName": row.get("agent_name"),
        "toolName": row.get("tool_name"),
        "model": row.get("model"),
        "durationMs": row.get("duration_ms"),
        "status": _jsonb_status(row.get("output_json"), row.get("error")),
        "argSummary": _jsonb_summary(row.get("input_json")),
        "resultSummary": _jsonb_summary(row.get("output_json")),
        "startedAt": started.isoformat() if started is not None else None,
        "endedAt": ended.isoformat() if ended is not None else None,
    }


# ---------------------------------------------------------------------------
# Module-level convenience
# ---------------------------------------------------------------------------

_repository: Optional[FortuneRepository] = None


async def get_repository() -> FortuneRepository:
    """Return a singleton repository bound to the lazy pool.

    Re-binds pool on every call so transient pool-init failures recover once
    Supabase is reachable again. Without this re-bind, a single failure at
    startup would poison the worker into non-durable mode until restart.
    """
    global _repository
    pool = await get_fortune_pool()
    if _repository is None:
        _repository = FortuneRepository(pool)
    else:
        _repository.pool = pool
    return _repository
