from __future__ import annotations

import hashlib
import hmac
import logging
import os
import secrets
import time
from dataclasses import dataclass
from datetime import datetime, timezone

try:
    import rate_limiter as shared_rate_limiter
except ImportError:  # pragma: no cover
    from .. import rate_limiter as shared_rate_limiter  # type: ignore


logger = logging.getLogger(__name__)

HOURLY_LIMIT = 10
WINDOW_SECONDS = 3600
_PROCESS_IP_SECRET = secrets.token_bytes(32)
_in_memory_usage: dict[str, tuple[int, int]] = {}


@dataclass(frozen=True)
class RateLimitResult:
    allowed: bool
    count: int
    remaining: int
    reset_epoch: int
    retry_after: int
    redis_available: bool


def _secret() -> bytes:
    configured = os.getenv("HOMER_PLAY_IP_SECRET")
    if configured:
        return configured.encode("utf-8")
    return _PROCESS_IP_SECRET


def _ip_token(request) -> str:
    # This endpoint is deliberately per-IP even when a visitor is signed in.
    # _guest_ip contains the repository's Cloudflare trust-anchor behavior.
    ip = shared_rate_limiter._guest_ip(request)
    return hmac.new(_secret(), ip.encode("utf-8"), hashlib.sha256).hexdigest()


def _window(now: int | None = None) -> tuple[int, int, int]:
    epoch = int(time.time()) if now is None else now
    window = epoch // WINDOW_SECONDS
    reset_epoch = (window + 1) * WINDOW_SECONDS
    return window, reset_epoch, epoch


def _key(ip_token: str, window: int) -> str:
    return f"homer-play:ip:v1:{ip_token}:{window}"


async def enforce_hourly_limit(request, *, now: int | None = None) -> RateLimitResult:
    window, reset_epoch, epoch = _window(now)
    retry_after = max(1, reset_epoch - epoch)
    if os.getenv("DISABLE_RATE_LIMIT", "false").lower() == "true":
        return RateLimitResult(True, 0, HOURLY_LIMIT, reset_epoch, retry_after, False)

    key = _key(_ip_token(request), window)
    redis_client = shared_rate_limiter.redis_pool
    if redis_client is not None:
        try:
            current = int(await redis_client.incr(key))
            ttl = await redis_client.ttl(key)
            if ttl is None or int(ttl) <= 0:
                await redis_client.expire(key, retry_after + 60)
            return RateLimitResult(
                allowed=current <= HOURLY_LIMIT,
                count=current,
                remaining=max(0, HOURLY_LIMIT - current),
                reset_epoch=reset_epoch,
                retry_after=retry_after,
                redis_available=True,
            )
        except Exception as exc:
            logger.warning("Homer play Redis rate limit unavailable; using process fallback: %s", type(exc).__name__)

    current, existing_reset = _in_memory_usage.get(key, (0, reset_epoch))
    if existing_reset <= epoch:
        current, existing_reset = 0, reset_epoch
    current += 1
    _in_memory_usage[key] = (current, existing_reset)
    return RateLimitResult(
        allowed=current <= HOURLY_LIMIT,
        count=current,
        remaining=max(0, HOURLY_LIMIT - current),
        reset_epoch=existing_reset,
        retry_after=max(1, existing_reset - epoch),
        redis_available=False,
    )


def reset_at_iso(reset_epoch: int) -> str:
    return datetime.fromtimestamp(reset_epoch, tz=timezone.utc).isoformat().replace("+00:00", "Z")
