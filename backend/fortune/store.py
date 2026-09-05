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
from uuid import UUID, uuid4

import asyncpg

logger = logging.getLogger(__name__)

_pool: Optional[asyncpg.Pool] = None
_pool_lock = asyncio.Lock()

# Ask requests use the same lease window for their Redis serialization lock and
# durable idempotency takeover. Keeping these aligned prevents a crashed worker
# from leaving retries blocked behind a longer, unrelated fortune-run lock.
ASK_LEASE_TTL_SECONDS = 180


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
        run_kind: str,  # 'initial' | 'action' | 'ask'
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

    async def claim_ask_request(
        self,
        *,
        fortune_id: UUID,
        client_request_id: UUID,
        payload_hash: str,
    ) -> dict[str, Any] | None:
        """Claim an Ask idempotency key or return its existing durable state."""
        if self.pool is None:
            return None
        lease_token = uuid4()
        delivery_id = uuid4()
        inserted = await self.pool.fetchrow(
            """
            INSERT INTO fortune_ask_request (
                fortune_id, client_request_id, payload_hash, lease_token,
                delivery_id, status
            ) VALUES ($1, $2, $3, $4, $5, 'running')
            ON CONFLICT (fortune_id, client_request_id) DO NOTHING
            RETURNING status, payload_hash, lease_token, delivery_id, run_id, response_json,
                      session_items, conversation_committed, updated_at
            """,
            fortune_id, client_request_id, payload_hash, lease_token, delivery_id,
        )
        if inserted is not None:
            return {**dict(inserted), "claimed": True}
        row = await self.pool.fetchrow(
            """
            SELECT status, payload_hash, lease_token, delivery_id, run_id, response_json,
                   session_items, conversation_committed, updated_at
            FROM fortune_ask_request
            WHERE fortune_id = $1 AND client_request_id = $2
            """,
            fortune_id, client_request_id,
        )
        if (
            row is not None
            and row["status"] == "error"
            and row["payload_hash"] == payload_hash
        ):
            retried = await self.pool.fetchrow(
                """
                UPDATE fortune_ask_request
                SET status = 'running', lease_token = $3, response_json = NULL,
                    session_items = NULL, conversation_committed = FALSE,
                    updated_at = NOW()
                WHERE fortune_id = $1 AND client_request_id = $2 AND status = 'error'
                RETURNING status, payload_hash, lease_token, delivery_id, run_id, response_json,
                          session_items, conversation_committed, updated_at
                """,
                fortune_id, client_request_id, lease_token,
            )
            if retried is not None:
                return {**dict(retried), "claimed": True}
        if (
            row is not None
            and row["status"] == "running"
            and row["payload_hash"] == payload_hash
        ):
            # Recover a key abandoned by a crashed/cancelled worker. This is the
            # same lease window used by the Ask serialization lock in routes.py.
            recovered = await self.pool.fetchrow(
                """
                UPDATE fortune_ask_request
                SET status = 'running', lease_token = $3, response_json = NULL,
                    session_items = NULL, conversation_committed = FALSE,
                    updated_at = NOW()
                WHERE fortune_id = $1 AND client_request_id = $2
                  AND status = 'running'
                  AND updated_at < NOW() - ($4 * INTERVAL '1 second')
                RETURNING status, payload_hash, lease_token, delivery_id, run_id, response_json,
                          session_items, conversation_committed, updated_at
                """,
                fortune_id, client_request_id, lease_token, ASK_LEASE_TTL_SECONDS,
            )
            if recovered is not None:
                return {**dict(recovered), "claimed": True}
        return ({**dict(row), "claimed": False} if row is not None else None)

    async def get_ask_request(
        self,
        *,
        fortune_id: UUID,
        client_request_id: UUID,
    ) -> dict[str, Any] | None:
        """Read an Ask idempotency record without claiming or renewing it."""
        if self.pool is None:
            return None
        row = await self.pool.fetchrow(
            """
            SELECT status, payload_hash, lease_token, delivery_id, run_id, response_json,
                   session_items, conversation_committed, updated_at
            FROM fortune_ask_request
            WHERE fortune_id = $1 AND client_request_id = $2
            """,
            fortune_id, client_request_id,
        )
        return dict(row) if row is not None else None

    async def list_pending_ask_conversations(
        self, *, fortune_id: UUID,
    ) -> list[dict[str, Any]]:
        """Return completed Ask outbox turns not yet copied to SDK memory."""
        if self.pool is None:
            return []
        rows = await self.pool.fetch(
            """
            SELECT client_request_id, lease_token, delivery_id, session_items,
                   updated_at
            FROM fortune_ask_request
            WHERE fortune_id = $1 AND status = 'done'
              AND conversation_committed = FALSE
              AND session_items IS NOT NULL
            ORDER BY created_at ASC, client_request_id ASC
            """,
            fortune_id,
        )
        return [dict(row) for row in rows]

    async def list_ask_conversations(
        self, *, fortune_id: UUID,
    ) -> list[dict[str, Any]]:
        """Return every completed Ask turn with stable delivery identities."""
        if self.pool is None:
            return []
        rows = await self.pool.fetch(
            """
            SELECT client_request_id, lease_token, delivery_id, session_items,
                   conversation_committed, updated_at
            FROM fortune_ask_request
            WHERE fortune_id = $1 AND status = 'done'
              AND session_items IS NOT NULL
            ORDER BY created_at ASC, client_request_id ASC
            """,
            fortune_id,
        )
        return [dict(row) for row in rows]

    async def ensure_ask_run(
        self, *, fortune_id: UUID, client_request_id: UUID, lease_token: UUID,
    ) -> UUID:
        """Create or recover the single activity-rail run owned by an Ask key."""
        if self.pool is None:
            raise RuntimeError("Ask persistence unavailable")
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                row = await conn.fetchrow(
                    """
                    SELECT run_id FROM fortune_ask_request
                    WHERE fortune_id = $1 AND client_request_id = $2
                      AND lease_token = $3 AND status = 'running'
                    FOR UPDATE
                    """,
                    fortune_id, client_request_id, lease_token,
                )
                if row is None:
                    raise RuntimeError("Ask idempotency lease was lost before run creation")
                run_id = row["run_id"]
                if run_id is None:
                    run_id = await conn.fetchval(
                        """
                        INSERT INTO fortune_run (fortune_id, run_kind, status)
                        VALUES ($1, 'ask', 'queued') RETURNING id
                        """,
                        fortune_id,
                    )
                    await conn.execute(
                        """
                        UPDATE fortune_ask_request SET run_id = $4, updated_at = NOW()
                        WHERE fortune_id = $1 AND client_request_id = $2
                          AND lease_token = $3
                        """,
                        fortune_id, client_request_id, lease_token, run_id,
                    )
                else:
                    await conn.execute(
                        """
                        UPDATE fortune_run SET status = 'queued', error_message = NULL,
                            finished_at = NULL
                        WHERE id = $1 AND fortune_id = $2
                        """,
                        run_id, fortune_id,
                    )
                return run_id

    async def complete_ask_request(
        self,
        *,
        fortune_id: UUID,
        client_request_id: UUID,
        lease_token: UUID,
        response: dict[str, Any],
        run_id: UUID,
        run_status: str = "done",
        session_items: list[Any] | None = None,
        conversation_committed: bool = False,
    ) -> None:
        if self.pool is None:
            return
        import json
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                updated = await conn.fetchval(
                    """
                    UPDATE fortune_ask_request
                    SET status = 'done', response_json = $4::jsonb,
                        session_items = $5::jsonb, conversation_committed = $6,
                        updated_at = NOW()
                    WHERE fortune_id = $1 AND client_request_id = $2
                      AND lease_token = $3 AND run_id = $7
                    RETURNING 1
                    """,
                    fortune_id, client_request_id, lease_token, json.dumps(response),
                    json.dumps(session_items) if session_items is not None else None,
                    conversation_committed, run_id,
                )
                if updated is None:
                    raise RuntimeError("Ask idempotency lease was lost before completion")
                result = await conn.execute(
                    """
                    UPDATE fortune_run SET status = $2, finished_at = NOW()
                    WHERE id = $1 AND fortune_id = $3
                    """,
                    run_id, run_status, fortune_id,
                )
                if result != "UPDATE 1":
                    raise RuntimeError("Ask run completion failed")

    async def mark_ask_conversation_committed(
        self, *, fortune_id: UUID, client_request_id: UUID, lease_token: UUID,
    ) -> None:
        if self.pool is None:
            return
        updated = await self.pool.fetchval(
            """
            UPDATE fortune_ask_request
            SET conversation_committed = TRUE, updated_at = NOW()
            WHERE fortune_id = $1 AND client_request_id = $2
              AND lease_token = $3 AND status = 'done'
            RETURNING 1
            """,
            fortune_id, client_request_id, lease_token,
        )
        if updated is None:
            raise RuntimeError("Ask idempotency lease was lost before memory acknowledgement")

    async def commit_ask_conversation(
        self,
        *,
        fortune_id: UUID,
        client_request_id: UUID,
        lease_token: UUID,
        delivery_id: UUID,
        session_id: str,
        serialized_items: list[str],
    ) -> None:
        """Publish an Ask turn and acknowledge its outbox in one transaction.

        The per-message delivery key is protected by a partial unique index.
        A retry after an ambiguous database result can therefore safely repeat
        the inserts without relying on message equality or a history window.
        """
        if self.pool is None:
            raise RuntimeError("Ask persistence unavailable")
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                owned = await conn.fetchval(
                    """
                    SELECT 1 FROM fortune_ask_request
                    WHERE fortune_id = $1 AND client_request_id = $2
                      AND lease_token = $3 AND delivery_id = $4
                      AND status = 'done' AND conversation_committed = FALSE
                    FOR UPDATE
                    """,
                    fortune_id, client_request_id, lease_token, delivery_id,
                )
                if owned is None:
                    # A previous transaction may already have committed. Treat
                    # that exact durable state as success; reject every other
                    # lease/delivery mismatch.
                    committed = await conn.fetchval(
                        """
                        SELECT 1 FROM fortune_ask_request
                        WHERE fortune_id = $1 AND client_request_id = $2
                          AND lease_token = $3 AND delivery_id = $4
                          AND status = 'done' AND conversation_committed = TRUE
                        """,
                        fortune_id, client_request_id, lease_token, delivery_id,
                    )
                    if committed is not None:
                        return
                    raise RuntimeError("Ask idempotency lease was lost before memory commit")

                await conn.execute(
                    """
                    INSERT INTO agent_sessions (session_id)
                    VALUES ($1) ON CONFLICT (session_id) DO NOTHING
                    """,
                    session_id,
                )
                for index, message_data in enumerate(serialized_items):
                    await conn.execute(
                        """
                        INSERT INTO agent_messages (
                            session_id, message_data,
                            ask_delivery_id, ask_delivery_index
                        ) VALUES ($1, $2, $3, $4)
                        ON CONFLICT DO NOTHING
                        """,
                        session_id, message_data, delivery_id, index,
                    )
                await conn.execute(
                    """
                    UPDATE agent_sessions SET updated_at = CURRENT_TIMESTAMP
                    WHERE session_id = $1
                    """,
                    session_id,
                )
                result = await conn.execute(
                    """
                    UPDATE fortune_ask_request
                    SET conversation_committed = TRUE, updated_at = NOW()
                    WHERE fortune_id = $1 AND client_request_id = $2
                      AND lease_token = $3 AND delivery_id = $4
                      AND status = 'done' AND conversation_committed = FALSE
                    """,
                    fortune_id, client_request_id, lease_token, delivery_id,
                )
                if result != "UPDATE 1":
                    raise RuntimeError("Ask memory acknowledgement failed")

    async def complete_ask_with_conversation(
        self,
        *,
        fortune_id: UUID,
        client_request_id: UUID,
        lease_token: UUID,
        delivery_id: UUID,
        response: dict[str, Any],
        session_items: list[Any],
        session_id: str,
        serialized_items: list[str],
        run_id: UUID,
        run_status: str = "done",
    ) -> None:
        """Atomically publish an approved turn and its replayable response.

        A client must never receive HTTP 200 while its turn only exists in an
        unserviced outbox. Combining the SDK message inserts with the
        idempotency completion makes either both durable or neither durable.
        The delivery key still makes an ambiguous transaction retry safe.
        """
        if self.pool is None:
            raise RuntimeError("Ask persistence unavailable")
        import json
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                owned = await conn.fetchval(
                    """
                    SELECT 1 FROM fortune_ask_request
                    WHERE fortune_id = $1 AND client_request_id = $2
                      AND lease_token = $3 AND delivery_id = $4
                      AND run_id = $5 AND status = 'running'
                    FOR UPDATE
                    """,
                    fortune_id, client_request_id, lease_token, delivery_id, run_id,
                )
                if owned is None:
                    committed = await conn.fetchval(
                        """
                        SELECT 1 FROM fortune_ask_request
                        WHERE fortune_id = $1 AND client_request_id = $2
                          AND lease_token = $3 AND delivery_id = $4
                          AND run_id = $5
                          AND status = 'done' AND conversation_committed = TRUE
                        """,
                        fortune_id, client_request_id, lease_token, delivery_id, run_id,
                    )
                    if committed is not None:
                        return
                    raise RuntimeError("Ask idempotency lease was lost before completion")

                await conn.execute(
                    """
                    INSERT INTO agent_sessions (session_id)
                    VALUES ($1) ON CONFLICT (session_id) DO NOTHING
                    """,
                    session_id,
                )
                for index, message_data in enumerate(serialized_items):
                    await conn.execute(
                        """
                        INSERT INTO agent_messages (
                            session_id, message_data,
                            ask_delivery_id, ask_delivery_index
                        ) VALUES ($1, $2, $3, $4)
                        ON CONFLICT DO NOTHING
                        """,
                        session_id, message_data, delivery_id, index,
                    )
                await conn.execute(
                    """
                    UPDATE agent_sessions SET updated_at = CURRENT_TIMESTAMP
                    WHERE session_id = $1
                    """,
                    session_id,
                )
                result = await conn.execute(
                    """
                    UPDATE fortune_ask_request
                    SET status = 'done', response_json = $5::jsonb,
                        session_items = $6::jsonb,
                        conversation_committed = TRUE, updated_at = NOW()
                    WHERE fortune_id = $1 AND client_request_id = $2
                      AND lease_token = $3 AND delivery_id = $4
                      AND run_id = $7 AND status = 'running'
                    """,
                    fortune_id, client_request_id, lease_token, delivery_id,
                    json.dumps(response), json.dumps(session_items), run_id,
                )
                if result != "UPDATE 1":
                    raise RuntimeError("Ask atomic conversation completion failed")
                run_result = await conn.execute(
                    """
                    UPDATE fortune_run SET status = $2, finished_at = NOW()
                    WHERE id = $1 AND fortune_id = $3
                    """,
                    run_id, run_status, fortune_id,
                )
                if run_result != "UPDATE 1":
                    raise RuntimeError("Ask run completion failed")

    async def reconcile_completed_ask_run(
        self, *, fortune_id: UUID, client_request_id: UUID, run_id: UUID,
    ) -> None:
        """Repair pre-atomic completed responses whose run stayed queued."""
        if self.pool is None:
            return
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                owned = await conn.fetchval(
                    """
                    UPDATE fortune_ask_request SET run_id = COALESCE(run_id, $3)
                    WHERE fortune_id = $1 AND client_request_id = $2
                      AND status = 'done' AND (run_id IS NULL OR run_id = $3)
                    RETURNING 1
                    """,
                    fortune_id, client_request_id, run_id,
                )
                if owned is None:
                    return
                await conn.execute(
                    """
                    UPDATE fortune_run SET status = 'done', finished_at = COALESCE(finished_at, NOW())
                    WHERE id = $1 AND fortune_id = $2 AND status NOT IN ('done', 'failed_guardrail')
                    """,
                    run_id, fortune_id,
                )

    async def fail_ask_request(
        self,
        *,
        fortune_id: UUID,
        client_request_id: UUID,
        lease_token: UUID,
    ) -> None:
        if self.pool is None:
            return
        await self.pool.execute(
            """
            UPDATE fortune_ask_request
            SET status = 'error', updated_at = NOW()
            WHERE fortune_id = $1 AND client_request_id = $2 AND lease_token = $3
            """,
            fortune_id, client_request_id, lease_token,
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
        request_context: dict[str, Any] | None = None,
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
                , request_context
            )
            VALUES ($1, 1, $2, $3::jsonb, $4::jsonb, $5::jsonb,
                    $6::jsonb, $7::jsonb, $8::jsonb, $9::jsonb,
                    COALESCE($10, 1), $11::jsonb, $12::jsonb)
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
                data_model = COALESCE(EXCLUDED.data_model, fortune_snapshot.data_model),
                request_context = COALESCE(EXCLUDED.request_context, fortune_snapshot.request_context)
            """,
            fortune_id, status,
            _j(overview), _j(pillars), _j(mechanics),
            _j(narrative), _j(trace), _j(references),
            _j(retrodictions),
            schema_version,
            _j(data_model),
            _j(request_context),
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

    async def sweep_stuck_run_records(
        self, *, older_than_minutes: int = 10,
    ) -> list[dict[str, str]]:
        """Interrupt stale runs and return identities for Redis reconciliation.

        Idempotent: runs that have already transitioned won't match. The caller
        uses the returned run/fortune ids to terminalize the Redis projection,
        which otherwise remains ``streaming`` after a hard worker exit.
        """
        if self.pool is None:
            return []
        rows = await self.pool.fetch(
            """
            WITH interrupted AS (
                UPDATE fortune_run
                SET status = 'interrupted',
                    error_message = COALESCE(error_message, 'worker exited mid-stream'),
                    finished_at = NOW()
                WHERE status IN ('queued', 'streaming')
                  AND COALESCE(started_at, created_at) < NOW() - ($1 || ' minutes')::interval
                RETURNING id
            )
            SELECT id, fortune_id
            FROM fortune_run
            WHERE status = 'interrupted' AND recovery_published_at IS NULL
            ORDER BY finished_at ASC NULLS FIRST, created_at ASC
            """,
            str(older_than_minutes),
        )
        return [
            {"run_id": str(row["id"]), "fortune_id": str(row["fortune_id"])}
            for row in rows
        ]

    async def mark_run_recovery_published(self, run_id: UUID) -> None:
        """Acknowledge that both Redis terminal projections were repaired."""
        if self.pool is None:
            return
        await self.pool.execute(
            """
            UPDATE fortune_run SET recovery_published_at = NOW()
            WHERE id = $1 AND status = 'interrupted'
              AND recovery_published_at IS NULL
            """,
            run_id,
        )

    async def sweep_stuck_runs(self, *, older_than_minutes: int = 10) -> int:
        """Backward-compatible count-only wrapper for maintenance callers."""
        return len(
            await self.sweep_stuck_run_records(
                older_than_minutes=older_than_minutes,
            )
        )

    async def get_snapshot(self, fortune_id: UUID) -> dict[str, Any] | None:
        if self.pool is None:
            return None
        row = await self.pool.fetchrow(
            """
            SELECT fortune_id, snapshot_version, schema_version, status,
                   latest_overview, latest_pillars, latest_mechanics,
                   latest_narrative, latest_trace, latest_references,
                   latest_retrodictions, data_model, request_context, updated_at
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
                s.updated_at        AS snapshot_updated_at,
                reading_run.id      AS latest_reading_run_id,
                reading_run.status  AS latest_reading_run_status
            FROM fortune f
            LEFT JOIN fortune_snapshot s ON s.fortune_id = f.id
            LEFT JOIN LATERAL (
                SELECT id, status
                FROM fortune_run
                WHERE fortune_id = f.id AND run_kind IN ('initial', 'action')
                ORDER BY created_at DESC
                LIMIT 1
            ) reading_run ON true
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
