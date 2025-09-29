"""Centralized cache utilities for analytics flows and supervisors."""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import time
from typing import Any, Dict, Optional

try:
    import redis.asyncio as redis  # type: ignore

    REDIS_AVAILABLE = True
except ImportError:  # pragma: no cover - redis optional
    redis = None
    REDIS_AVAILABLE = False

logger = logging.getLogger(__name__)

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")


class CacheService:
    """Redis backed cache service with resilient in-memory fallback."""

    def __init__(self, redis_url: str = REDIS_URL) -> None:
        self.redis_url = redis_url
        self.redis_client: Optional["redis.Redis"] = None
        self.fallback_cache: Dict[str, Any] = {}
        self.circuit_breaker_failures = 0
        self.circuit_breaker_threshold = 5
        self.circuit_breaker_timeout = 60
        self.last_failure_time = 0.0
        self.default_ttl: Dict[str, int] = {
            "config": 300,
            "templates": 3600,
            "metrics": 1800,
            "companies": 1800,
            "context": 600,
        }

    async def _get_redis_client(self) -> Optional["redis.Redis"]:
        """Return Redis client if available and circuit breaker allows."""

        if not REDIS_AVAILABLE:
            return None

        if self.circuit_breaker_failures >= self.circuit_breaker_threshold:
            if time.time() - self.last_failure_time < self.circuit_breaker_timeout:
                return None
            self.circuit_breaker_failures = 0

        if not self.redis_client:
            try:
                client = redis.from_url(  # type: ignore[call-arg]
                    self.redis_url,
                    encoding="utf-8",
                    decode_responses=True,
                    socket_timeout=5.0,
                    socket_connect_timeout=5.0,
                    health_check_interval=30,
                )
                await client.ping()
                self.redis_client = client
                logger.info("Redis connection established for analytics cache")
            except Exception as exc:  # pragma: no cover - network failure
                logger.warning("Failed to connect to Redis: %s", exc)
                self._record_failure()
                return None

        return self.redis_client

    def _record_failure(self) -> None:
        self.circuit_breaker_failures += 1
        self.last_failure_time = time.time()
        self.redis_client = None

    def _generate_cache_key(self, prefix: str, query: str, **kwargs: Any) -> str:
        params_str = json.dumps(kwargs, sort_keys=True)
        digest = hashlib.md5(f"{query}:{params_str}".encode()).hexdigest()[:12]
        return f"analytics:{prefix}:{digest}"

    async def get(self, prefix: str, query: str, **kwargs: Any) -> Optional[Any]:
        cache_key = self._generate_cache_key(prefix, query, **kwargs)

        redis_client = await self._get_redis_client()
        if redis_client:
            try:
                payload = await redis_client.get(cache_key)
                if payload:
                    return json.loads(payload)
            except Exception as exc:  # pragma: no cover - network failure
                logger.warning("Redis get failed: %s", exc)
                self._record_failure()

        fallback_entry = self.fallback_cache.get(cache_key)
        if fallback_entry:
            cached_time, data = fallback_entry
            if time.time() - cached_time < 300:
                return data
            del self.fallback_cache[cache_key]
        return None

    async def set(self, prefix: str, query: str, data: Any, ttl: Optional[int] = None, **kwargs: Any) -> bool:
        cache_key = self._generate_cache_key(prefix, query, **kwargs)
        ttl = ttl if ttl is not None else self.default_ttl.get(prefix, 300)

        redis_client = await self._get_redis_client()
        if redis_client:
            try:
                await redis_client.setex(cache_key, ttl, json.dumps(data, default=str))
                return True
            except Exception as exc:  # pragma: no cover - network failure
                logger.warning("Redis set failed: %s", exc)
                self._record_failure()

        self.fallback_cache[cache_key] = (time.time(), data)
        return False

    async def delete(self, prefix: str, query: str, **kwargs: Any) -> bool:
        cache_key = self._generate_cache_key(prefix, query, **kwargs)
        redis_client = await self._get_redis_client()
        if redis_client:
            try:
                await redis_client.delete(cache_key)
            except Exception as exc:  # pragma: no cover - network failure
                logger.warning("Redis delete failed: %s", exc)
                self._record_failure()
        self.fallback_cache.pop(cache_key, None)
        return True

    async def delete_pattern(self, pattern: str) -> int:
        redis_client = await self._get_redis_client()
        if not redis_client:
            return 0
        try:
            keys = await redis_client.keys(f"analytics:{pattern}:*")
            return await redis_client.delete(*keys) if keys else 0
        except Exception as exc:  # pragma: no cover
            logger.warning("Redis pattern delete failed: %s", exc)
            self._record_failure()
            return 0

    async def clear_all(self) -> bool:
        await self.delete_pattern("*")
        fallback_count = len(self.fallback_cache)
        self.fallback_cache.clear()
        logger.info("Cleared analytics cache; fallback entries: %s", fallback_count)
        return True

    async def get_stats(self) -> Dict[str, Any]:
        stats: Dict[str, Any] = {
            "redis_available": REDIS_AVAILABLE,
            "circuit_breaker_failures": self.circuit_breaker_failures,
            "fallback_cache_size": len(self.fallback_cache),
            "last_failure_time": self.last_failure_time,
        }
        redis_client = await self._get_redis_client()
        if redis_client:
            try:
                info = await redis_client.info()
                stats["redis_info"] = {
                    "used_memory_human": info.get("used_memory_human"),
                    "connected_clients": info.get("connected_clients"),
                    "total_commands_processed": info.get("total_commands_processed"),
                    "keyspace_hits": info.get("keyspace_hits", 0),
                    "keyspace_misses": info.get("keyspace_misses", 0),
                }
                hits = info.get("keyspace_hits", 0)
                misses = info.get("keyspace_misses", 0)
                if hits + misses:
                    stats["redis_hit_ratio"] = hits / (hits + misses)
            except Exception as exc:  # pragma: no cover
                logger.warning("Failed to fetch Redis stats: %s", exc)
                self._record_failure()
        return stats

    async def cleanup_expired(self) -> int:
        now = time.time()
        expired = [key for key, (ts, _) in self.fallback_cache.items() if now - ts > 300]
        for key in expired:
            self.fallback_cache.pop(key, None)
        return len(expired)

    async def close(self) -> None:
        if self.redis_client:
            try:
                await self.redis_client.close()
            except Exception:  # pragma: no cover
                pass
            self.redis_client = None


_cache_service: Optional[CacheService] = None


def get_cache_service() -> CacheService:
    global _cache_service
    if _cache_service is None:
        _cache_service = CacheService()
    return _cache_service


async def close_cache_service() -> None:
    global _cache_service
    if _cache_service:
        await _cache_service.close()
        _cache_service = None


__all__ = [
    "CacheService",
    "get_cache_service",
    "close_cache_service",
    "REDIS_AVAILABLE",
]
