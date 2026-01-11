from __future__ import annotations

import asyncio
import os
import ssl
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

import asyncpg


@dataclass(slots=True)
class TokenBalance:
    balance: int
    updated_at: Optional[datetime]


class TokenStore:
    """Simple Supabase-backed prompt token store."""

    def __init__(self) -> None:
        self._database_url = os.getenv("SUPABASE_DB_URL")
        self._pool: Optional[asyncpg.Pool] = None
        self._lock = asyncio.Lock()
        self._ssl_context: Optional[ssl.SSLContext] = None

        if self._database_url and os.getenv("SUPABASE_DB_DISABLE_SSL", "false").lower() != "true":
            self._ssl_context = ssl.create_default_context()

    @property
    def is_configured(self) -> bool:
        return bool(self._database_url)

    @property
    def is_available(self) -> bool:
        return self._pool is not None

    async def initialize(self) -> bool:
        """Create the asyncpg connection pool if configuration is present."""
        if not self.is_configured:
            print("TokenStore disabled - SUPABASE_DB_URL not configured")
            return False

        if self._pool is not None:
            return True

        async with self._lock:
            if self._pool is not None:
                return True
            try:
                self._pool = await asyncpg.create_pool(
                    self._database_url,
                    min_size=1,
                    max_size=int(os.getenv("SUPABASE_DB_POOL_MAX", "5")),
                    ssl=self._ssl_context,
                    # Disable statement caching for pgbouncer compatibility (Supabase)
                    statement_cache_size=0,
                )
                print("TokenStore connected to Supabase Postgres")
                return True
            except Exception as exc:  # pragma: no cover - network/credentials issues
                print(f"TokenStore initialization failed: {exc}")
                self._pool = None
                return False

    async def shutdown(self) -> None:
        if self._pool is not None:
            await self._pool.close()
            self._pool = None
            print("TokenStore pool closed")

    async def _get_pool(self) -> Optional[asyncpg.Pool]:
        if self._pool is not None:
            return self._pool
        await self.initialize()
        return self._pool

    async def get_balance(self, user_id: str) -> Optional[TokenBalance]:
        """Retrieve current token balance for the Supabase user."""
        pool = await self._get_pool()
        if pool is None:
            return None

        try:
            user_uuid = uuid.UUID(user_id)
        except Exception:
            print(f"TokenStore get_balance: invalid user_id {user_id}")
            return None

        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                select balance, updated_at AT TIME ZONE 'utc' as updated_at
                from prompt_token_balances
                where user_id = $1
                """,
                user_uuid,
            )

        if row is None:
            return TokenBalance(balance=0, updated_at=None)

        updated_at = row["updated_at"]
        if isinstance(updated_at, datetime) and updated_at.tzinfo is None:
            updated_at = updated_at.replace(tzinfo=timezone.utc)

        return TokenBalance(balance=row["balance"], updated_at=updated_at)

    async def increment(
        self,
        user_id: str,
        delta: int,
        source: str,
        reference_id: Optional[str] = None,
    ) -> Optional[TokenBalance]:
        """Credit tokens to a user and write a ledger entry."""
        if delta <= 0:
            raise ValueError("TokenStore.increment requires a positive delta")

        pool = await self._get_pool()
        if pool is None:
            return None

        try:
            user_uuid = uuid.UUID(user_id)
        except Exception:
            print(f"TokenStore increment: invalid user_id {user_id}")
            return None

        async with pool.acquire() as conn:
            async with conn.transaction():
                if reference_id:
                    duplicate = await conn.fetchval(
                        """
                        select 1 from prompt_token_ledger
                        where reference_id = $1 and source = $2
                        limit 1
                        """,
                        reference_id,
                        source,
                    )
                    if duplicate:
                        existing = await conn.fetchrow(
                            """
                            select balance, updated_at AT TIME ZONE 'utc' as updated_at
                            from prompt_token_balances
                            where user_id = $1
                            """,
                            user_uuid,
                        )
                        if existing:
                            existing_updated = existing["updated_at"]
                            if isinstance(existing_updated, datetime) and existing_updated.tzinfo is None:
                                existing_updated = existing_updated.replace(tzinfo=timezone.utc)
                            return TokenBalance(balance=existing["balance"], updated_at=existing_updated)
                        return TokenBalance(balance=0, updated_at=None)

                balance_row = await conn.fetchrow(
                    """
                    insert into prompt_token_balances (user_id, balance)
                    values ($1, $2)
                    on conflict (user_id)
                    do update set balance = prompt_token_balances.balance + excluded.balance,
                                  updated_at = timezone('utc', now())
                    returning balance, updated_at AT TIME ZONE 'utc' as updated_at
                    """,
                    user_uuid,
                    delta,
                )
                await conn.execute(
                    """
                    insert into prompt_token_ledger (user_id, delta, source, reference_id)
                    values ($1, $2, $3, $4)
                    """,
                    user_uuid,
                    delta,
                    source,
                    reference_id,
                )

        updated_at = balance_row["updated_at"]
        if isinstance(updated_at, datetime) and updated_at.tzinfo is None:
            updated_at = updated_at.replace(tzinfo=timezone.utc)

        return TokenBalance(balance=balance_row["balance"], updated_at=updated_at)

    async def consume(self, user_id: str, amount: int) -> bool:
        """Spend tokens if the user has sufficient balance."""
        if amount <= 0:
            print(f"TokenStore consume: ignoring non-positive amount {amount}")
            return False

        pool = await self._get_pool()
        if pool is None:
            return False

        try:
            user_uuid = uuid.UUID(user_id)
        except Exception:
            print(f"TokenStore consume: invalid user_id {user_id}")
            return False

        async with pool.acquire() as conn:
            async with conn.transaction():
                current = await conn.fetchrow(
                    "select balance from prompt_token_balances where user_id = $1 for update",
                    user_uuid,
                )
                if current is None:
                    print(f"TokenStore consume: no balance row for {user_id}")
                    return False

                balance = current["balance"] or 0
                if balance < amount:
                    print(
                        f"TokenStore consume: insufficient balance {balance} for {user_id}, "
                        f"needed {amount}"
                    )
                    return False

                new_balance = balance - amount
                await conn.execute(
                    """
                    update prompt_token_balances
                    set balance = $2,
                        updated_at = timezone('utc', now())
                    where user_id = $1
                    """,
                    user_uuid,
                    new_balance,
                )
                await conn.execute(
                    """
                    insert into prompt_token_ledger (user_id, delta, source, reference_id)
                    values ($1, $2, $3, $4)
                    """,
                    user_uuid,
                    -amount,
                    "rate_limit_consume",
                    None,
                )

        return True


token_store = TokenStore()
