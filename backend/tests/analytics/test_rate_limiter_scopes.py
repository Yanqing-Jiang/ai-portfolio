from __future__ import annotations

from typing import Callable

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from backend import rate_limiter


def _make_request_factory() -> Callable[[], Request]:
    """Create a factory that returns fresh Starlette Request objects for testing."""

    async def _receive() -> dict[str, object]:
        return {"type": "http.request", "body": b"", "more_body": False}

    def _factory() -> Request:
        scope = {
            "type": "http",
            "http_version": "1.1",
            "method": "GET",
            "path": "/test",
            "headers": [],
            "query_string": b"",
            "client": ("127.0.0.1", 9000),
            "server": ("testserver", 80),
        }
        return Request(scope, _receive)

    return _factory


@pytest.mark.parametrize(
    "alias,expected",
    [
        ("global", rate_limiter.RateLimitScope.GLOBAL),
        ("next-gen-analytics-agent", rate_limiter.RateLimitScope.ANALYTICS_AGENT),
        ("analytics_agent", rate_limiter.RateLimitScope.ANALYTICS_AGENT),
        ("next-gen-analytics-sql", rate_limiter.RateLimitScope.ANALYTICS_SQL),
        ("analytics_sql", rate_limiter.RateLimitScope.ANALYTICS_SQL),
        ("unknown", rate_limiter.RateLimitScope.GLOBAL),
        (None, rate_limiter.RateLimitScope.GLOBAL),
    ],
)
def test_resolve_scope_aliases(alias: str | None, expected: rate_limiter.RateLimitScope) -> None:
    assert rate_limiter.resolve_scope(alias) is expected


@pytest.mark.asyncio
async def test_guest_scoped_limits_are_independent(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DISABLE_RATE_LIMIT", "false")
    rate_limiter.redis_pool = None
    rate_limiter.in_memory_usage.clear()

    request_factory = _make_request_factory()

    # Exhaust the SQL guest allowance.
    for _ in range(rate_limiter.GUEST_LIMIT):
        await rate_limiter.smart_rate_limit(
            request_factory(),
            scope=rate_limiter.RateLimitScope.ANALYTICS_SQL,
        )

    with pytest.raises(HTTPException) as exc_info:
        await rate_limiter.smart_rate_limit(
            request_factory(),
            scope=rate_limiter.RateLimitScope.ANALYTICS_SQL,
        )

    assert exc_info.value.status_code == 401
    assert "Sign-in required" in exc_info.value.detail

    # Other analytics scope remains unaffected.
    await rate_limiter.smart_rate_limit(
        request_factory(),
        scope=rate_limiter.RateLimitScope.ANALYTICS_AGENT,
    )

    identifier = await rate_limiter.who_am_i(request_factory())
    sql_usage, sql_limit = await rate_limiter.get_user_usage(
        identifier,
        scope=rate_limiter.RateLimitScope.ANALYTICS_SQL,
    )
    agent_usage, agent_limit = await rate_limiter.get_user_usage(
        identifier,
        scope=rate_limiter.RateLimitScope.ANALYTICS_AGENT,
    )

    assert sql_usage == rate_limiter.GUEST_LIMIT
    assert sql_limit == rate_limiter.GUEST_LIMIT
    assert agent_usage == 1
    assert agent_limit == rate_limiter.GUEST_LIMIT
