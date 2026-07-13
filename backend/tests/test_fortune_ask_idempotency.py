"""Release-safety tests for durable Ask idempotency fencing."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from fortune.store import ASK_LEASE_TTL_SECONDS, FortuneRepository


@pytest.mark.asyncio
async def test_running_ask_recovery_uses_shared_lease_window() -> None:
    pool = AsyncMock()
    running = {
        "status": "running",
        "payload_hash": "same",
        "lease_token": uuid.uuid4(),
        "delivery_id": uuid.uuid4(),
        "response_json": None,
        "session_items": None,
        "conversation_committed": False,
        "updated_at": None,
    }
    pool.fetchrow.side_effect = [None, running, {**running, "lease_token": uuid.uuid4()}]
    repo = FortuneRepository(pool)

    result = await repo.claim_ask_request(
        fortune_id=uuid.uuid4(),
        client_request_id=uuid.uuid4(),
        payload_hash="same",
    )

    assert result is not None and result["claimed"] is True
    recovery_call = pool.fetchrow.await_args_list[2]
    assert "$4 * INTERVAL '1 second'" in recovery_call.args[0]
    assert recovery_call.args[4] == ASK_LEASE_TTL_SECONDS


@pytest.mark.asyncio
async def test_stale_lease_cannot_complete_reclaimed_ask() -> None:
    pool = MagicMock()
    conn = AsyncMock()
    conn.fetchval.return_value = None
    pool.acquire.return_value.__aenter__ = AsyncMock(return_value=conn)
    pool.acquire.return_value.__aexit__ = AsyncMock(return_value=None)
    conn.transaction = MagicMock()
    conn.transaction.return_value.__aenter__ = AsyncMock(return_value=None)
    conn.transaction.return_value.__aexit__ = AsyncMock(return_value=None)
    repo = FortuneRepository(pool)
    stale_lease = uuid.uuid4()
    run_id = uuid.uuid4()

    with pytest.raises(RuntimeError, match="lease was lost"):
        await repo.complete_ask_request(
            fortune_id=uuid.uuid4(),
            client_request_id=uuid.uuid4(),
            lease_token=stale_lease,
            response={"run_id": "stale"},
            run_id=run_id,
        )

    sql, *params = conn.fetchval.await_args.args
    assert "lease_token = $3" in sql
    assert params[2] == stale_lease


@pytest.mark.asyncio
async def test_stale_lease_cannot_ack_conversation_delivery() -> None:
    pool = AsyncMock()
    pool.fetchval.return_value = None
    repo = FortuneRepository(pool)

    with pytest.raises(RuntimeError, match="lease was lost"):
        await repo.mark_ask_conversation_committed(
            fortune_id=uuid.uuid4(),
            client_request_id=uuid.uuid4(),
            lease_token=uuid.uuid4(),
        )
