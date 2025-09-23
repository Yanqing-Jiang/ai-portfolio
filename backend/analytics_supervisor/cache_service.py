#!/usr/bin/env python3
"""
Centralized Redis Cache Service for Analytics System

This module provides a unified Redis-based caching layer for the analytics
supervisor system, replacing scattered in-memory caches with a centralized,
scalable solution.

Features:
- Redis-based distributed caching
- TTL management with different expiration policies
- Automatic serialization/deserialization
- Circuit breaker pattern for Redis failures
- Cache invalidation patterns
- Performance monitoring and metrics

Usage:
    cache = get_cache_service()
    await cache.set("key", data, ttl=300)
    result = await cache.get("key")
"""

from __future__ import annotations
from typing import Any, Dict, List, Optional, Union
import json
import logging
import time
import asyncio
from datetime import datetime, timedelta
import hashlib
import os

try:
    import redis.asyncio as redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    redis = None

logger = logging.getLogger(__name__)

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")


class CacheService:
    """Centralized Redis cache service with fallback to in-memory cache"""

    def __init__(self, redis_url: str = REDIS_URL):
        self.redis_url = redis_url
        self.redis_client = None
        self.fallback_cache = {}  # In-memory fallback
        self.circuit_breaker_failures = 0
        self.circuit_breaker_threshold = 5
        self.circuit_breaker_timeout = 60  # seconds
        self.last_failure_time = 0
        self.default_ttl = {
            'config': 300,      # 5 minutes for config data
            'templates': 3600,  # 1 hour for SQL templates
            'metrics': 1800,    # 30 minutes for metrics
            'companies': 1800,  # 30 minutes for companies
            'context': 600      # 10 minutes for analytics context
        }

    async def _get_redis_client(self) -> Optional[redis.Redis]:
        """Get Redis client with circuit breaker pattern"""
        if not REDIS_AVAILABLE:
            logger.warning("Redis not available - using in-memory cache fallback")
            return None

        # Circuit breaker check
        if self.circuit_breaker_failures >= self.circuit_breaker_threshold:
            if time.time() - self.last_failure_time < self.circuit_breaker_timeout:
                return None
            else:
                # Reset circuit breaker after timeout
                self.circuit_breaker_failures = 0

        if not self.redis_client:
            try:
                self.redis_client = redis.from_url(
                    self.redis_url,
                    encoding="utf-8",
                    decode_responses=True,
                    socket_timeout=5.0,
                    socket_connect_timeout=5.0,
                    health_check_interval=30
                )
                # Test connection
                await self.redis_client.ping()
                logger.info("Redis connection established")
            except Exception as e:
                logger.warning(f"Failed to connect to Redis: {e}")
                self._record_failure()
                return None

        return self.redis_client

    def _record_failure(self):
        """Record Redis failure for circuit breaker"""
        self.circuit_breaker_failures += 1
        self.last_failure_time = time.time()
        self.redis_client = None

    def _generate_cache_key(self, prefix: str, query: str, **kwargs) -> str:
        """Generate consistent cache key with prefix and parameters"""
        # Create a hash of query + sorted parameters for consistent keys
        params_str = json.dumps(kwargs, sort_keys=True)
        hash_input = f"{query}:{params_str}"
        hash_value = hashlib.md5(hash_input.encode()).hexdigest()[:12]
        return f"analytics:{prefix}:{hash_value}"

    async def get(self, prefix: str, query: str, **kwargs) -> Optional[Any]:
        """Get cached data with Redis primary, in-memory fallback"""
        cache_key = self._generate_cache_key(prefix, query, **kwargs)

        # Try Redis first
        redis_client = await self._get_redis_client()
        if redis_client:
            try:
                cached_data = await redis_client.get(cache_key)
                if cached_data:
                    return json.loads(cached_data)
            except Exception as e:
                logger.warning(f"Redis get failed: {e}")
                self._record_failure()

        # Fallback to in-memory cache
        if cache_key in self.fallback_cache:
            cached_time, cached_data = self.fallback_cache[cache_key]
            # Check if still valid (5 minute TTL for fallback)
            if time.time() - cached_time < 300:
                return cached_data
            else:
                del self.fallback_cache[cache_key]

        return None

    async def set(
        self,
        prefix: str,
        query: str,
        data: Any,
        ttl: Optional[int] = None,
        **kwargs
    ) -> bool:
        """Set cached data with automatic TTL management"""
        cache_key = self._generate_cache_key(prefix, query, **kwargs)

        # Determine TTL
        if ttl is None:
            ttl = self.default_ttl.get(prefix, 300)

        # Try Redis first
        redis_client = await self._get_redis_client()
        if redis_client:
            try:
                serialized_data = json.dumps(data, default=str)
                await redis_client.setex(cache_key, ttl, serialized_data)
                return True
            except Exception as e:
                logger.warning(f"Redis set failed: {e}")
                self._record_failure()

        # Fallback to in-memory cache
        self.fallback_cache[cache_key] = (time.time(), data)
        return False  # Indicates fallback was used

    async def delete(self, prefix: str, query: str, **kwargs) -> bool:
        """Delete cached data"""
        cache_key = self._generate_cache_key(prefix, query, **kwargs)

        # Try Redis first
        redis_client = await self._get_redis_client()
        if redis_client:
            try:
                await redis_client.delete(cache_key)
            except Exception as e:
                logger.warning(f"Redis delete failed: {e}")
                self._record_failure()

        # Also remove from fallback cache
        if cache_key in self.fallback_cache:
            del self.fallback_cache[cache_key]

        return True

    async def delete_pattern(self, pattern: str) -> int:
        """Delete all keys matching a pattern (Redis only)"""
        redis_client = await self._get_redis_client()
        if not redis_client:
            return 0

        try:
            keys = await redis_client.keys(f"analytics:{pattern}:*")
            if keys:
                return await redis_client.delete(*keys)
            return 0
        except Exception as e:
            logger.warning(f"Redis pattern delete failed: {e}")
            self._record_failure()
            return 0

    async def clear_all(self) -> bool:
        """Clear all analytics cache data"""
        # Clear Redis
        deleted_count = await self.delete_pattern("*")

        # Clear fallback cache
        fallback_count = len(self.fallback_cache)
        self.fallback_cache.clear()

        logger.info(f"Cache cleared - Redis: {deleted_count}, Fallback: {fallback_count}")
        return True

    async def get_stats(self) -> Dict[str, Any]:
        """Get cache performance statistics"""
        stats = {
            'redis_available': REDIS_AVAILABLE,
            'circuit_breaker_failures': self.circuit_breaker_failures,
            'fallback_cache_size': len(self.fallback_cache),
            'last_failure_time': self.last_failure_time
        }

        # Try to get Redis info
        redis_client = await self._get_redis_client()
        if redis_client:
            try:
                info = await redis_client.info()
                stats['redis_info'] = {
                    'used_memory_human': info.get('used_memory_human'),
                    'connected_clients': info.get('connected_clients'),
                    'total_commands_processed': info.get('total_commands_processed'),
                    'keyspace_hits': info.get('keyspace_hits', 0),
                    'keyspace_misses': info.get('keyspace_misses', 0)
                }

                # Calculate hit ratio
                hits = info.get('keyspace_hits', 0)
                misses = info.get('keyspace_misses', 0)
                if hits + misses > 0:
                    stats['redis_hit_ratio'] = hits / (hits + misses)

            except Exception as e:
                logger.warning(f"Failed to get Redis stats: {e}")
                self._record_failure()

        return stats

    async def cleanup_expired(self) -> int:
        """Clean up expired entries from fallback cache"""
        current_time = time.time()
        expired_keys = []

        for key, (timestamp, _) in self.fallback_cache.items():
            if current_time - timestamp > 300:  # 5 minute TTL
                expired_keys.append(key)

        for key in expired_keys:
            del self.fallback_cache[key]

        return len(expired_keys)

    async def close(self) -> None:
        """Close Redis connection"""
        if self.redis_client:
            try:
                await self.redis_client.close()
            except Exception:
                pass
            self.redis_client = None


# Global cache service instance
_cache_service = None


def get_cache_service() -> CacheService:
    """Get global cache service instance"""
    global _cache_service
    if _cache_service is None:
        _cache_service = CacheService()
    return _cache_service


async def close_cache_service() -> None:
    """Close global cache service"""
    global _cache_service
    if _cache_service:
        await _cache_service.close()
        _cache_service = None


if __name__ == "__main__":
    async def test_cache_service():
        """Test the cache service functionality"""
        cache = get_cache_service()

        print("=== Testing Cache Service ===")

        # Test basic operations
        test_data = {"query": "revenue analysis", "results": ["template1", "template2"]}

        # Set cache
        print("Setting cache...")
        success = await cache.set("templates", "revenue analysis", test_data)
        print(f"Cache set success: {success}")

        # Get cache
        print("Getting cache...")
        cached_result = await cache.get("templates", "revenue analysis")
        print(f"Cache result: {cached_result}")

        # Test with TTL
        await cache.set("metrics", "test metric", {"value": 100}, ttl=60)

        # Get stats
        stats = await cache.get_stats()
        print(f"Cache stats: {json.dumps(stats, indent=2)}")

        # Cleanup
        await cache.clear_all()
        await close_cache_service()

    asyncio.run(test_cache_service())