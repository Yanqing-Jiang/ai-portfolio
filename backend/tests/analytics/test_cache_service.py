import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
BACKEND_ROOT = Path(__file__).resolve().parents[2]
for entry in (ROOT, BACKEND_ROOT):
    entry_str = str(entry)
    if entry_str not in sys.path:
        sys.path.insert(0, entry_str)

from backend.analytics.core.cache import CacheService


@pytest.mark.asyncio
async def test_cache_service_fallback_round_trip():
    service = CacheService()

    async def no_redis(*_args, **_kwargs):
        return None

    service._get_redis_client = no_redis.__get__(service, CacheService)  # type: ignore[attr-defined]

    payload = {"value": 42}
    stored = await service.set("metrics", "unit-test", payload, ttl=1)
    assert stored is False

    cached = await service.get("metrics", "unit-test")
    assert cached == payload

    await service.delete("metrics", "unit-test")
    assert await service.get("metrics", "unit-test") is None


@pytest.mark.asyncio
async def test_cache_service_cleanup_expired():
    service = CacheService()

    async def no_redis(*_args, **_kwargs):
        return None

    service._get_redis_client = no_redis.__get__(service, CacheService)  # type: ignore[attr-defined]

    await service.set("context", "temp", {"ok": True}, ttl=1)
    for key in list(service.fallback_cache.keys()):
        timestamp, data = service.fallback_cache[key]
        service.fallback_cache[key] = (timestamp - 400, data)

    removed = await service.cleanup_expired()
    assert removed >= 1
