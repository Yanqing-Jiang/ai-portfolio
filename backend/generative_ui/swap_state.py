# --- Function/Class Map ---
# Class: SwapStateRepository
#   Role: Redis-backed swap state storage with in-memory fallback.
#   Called from: Dashboard swap state endpoints in routes/dashboard.py
#   Invokes: redis.asyncio, SwapStateSnapshot, SwapStateBatch
#   Why: Persists component swap states across page refreshes with TTL expiry.
# Function: get_swap_state_repo
#   Role: Singleton accessor for the repository.
#   Called from: Dashboard routes
#   Invokes: SwapStateRepository
#   Why: Ensures single repository instance across requests.
# --- End Function/Class Map ---
"""
Swap State Repository

Redis-backed storage for A2UI component swap states with in-memory fallback.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from typing import Dict, Optional

from .models.swap_state import SwapStateSnapshot, SwapStateBatch

logger = logging.getLogger(__name__)

# Redis configuration
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
SWAP_STATE_TTL = int(os.getenv("SWAP_STATE_TTL", "3600"))  # 1 hour default


class SwapStateRepository:
    """
    Redis-backed swap state storage with in-memory fallback.

    Stores component swap states with automatic TTL expiry.
    Falls back to in-memory storage if Redis is unavailable.

    Key format: a2ui:swap:{dashboard_id}:{component_id}
    """

    KEY_PREFIX = "a2ui:swap"
    DEFAULT_TTL = SWAP_STATE_TTL

    def __init__(self):
        """Initialize repository with Redis connection attempt."""
        self._redis: Optional["redis.asyncio.Redis"] = None
        self._memory_store: Dict[str, Dict[str, SwapStateSnapshot]] = {}
        self._redis_available = False

    async def _get_redis(self):
        """
        Lazy-load Redis connection with graceful fallback.

        Returns None if Redis unavailable, triggering memory fallback.
        """
        if self._redis is not None:
            return self._redis if self._redis_available else None

        try:
            import redis.asyncio as redis_async

            self._redis = redis_async.from_url(
                REDIS_URL,
                encoding="utf-8",
                decode_responses=True,
                socket_connect_timeout=2.0,
                socket_timeout=2.0,
            )
            # Test connection
            await self._redis.ping()
            self._redis_available = True
            logger.info("[SwapState] Redis connected: %s", REDIS_URL)
            return self._redis

        except ImportError:
            logger.warning("[SwapState] redis package not installed, using memory fallback")
            self._redis_available = False
            return None

        except Exception as e:
            logger.warning("[SwapState] Redis unavailable (%s), using memory fallback", e)
            self._redis_available = False
            return None

    def _make_key(self, dashboard_id: str, component_id: str) -> str:
        """Build Redis key for a component's swap state."""
        return f"{self.KEY_PREFIX}:{dashboard_id}:{component_id}"

    def _make_dashboard_pattern(self, dashboard_id: str) -> str:
        """Build Redis pattern to match all components for a dashboard."""
        return f"{self.KEY_PREFIX}:{dashboard_id}:*"

    async def save(
        self,
        dashboard_id: str,
        component_id: str,
        state: SwapStateSnapshot,
        ttl: Optional[int] = None,
    ) -> bool:
        """
        Save a single component's swap state.

        Args:
            dashboard_id: Dashboard identifier
            component_id: Component identifier
            state: Swap state snapshot to save
            ttl: Optional TTL in seconds (defaults to DEFAULT_TTL)

        Returns:
            True if saved successfully
        """
        ttl = ttl or self.DEFAULT_TTL
        key = self._make_key(dashboard_id, component_id)
        data = state.model_dump_json()

        redis = await self._get_redis()
        if redis:
            try:
                await redis.setex(key, ttl, data)
                logger.debug("[SwapState] Saved to Redis: %s", key)
                return True
            except Exception as e:
                logger.warning("[SwapState] Redis save failed (%s), using memory", e)

        # Memory fallback
        if dashboard_id not in self._memory_store:
            self._memory_store[dashboard_id] = {}
        self._memory_store[dashboard_id][component_id] = state
        logger.debug("[SwapState] Saved to memory: %s/%s", dashboard_id, component_id)
        return True

    async def save_batch(
        self,
        dashboard_id: str,
        states: Dict[str, SwapStateSnapshot],
        ttl: Optional[int] = None,
    ) -> bool:
        """
        Save multiple component swap states in a batch.

        Args:
            dashboard_id: Dashboard identifier
            states: Map of component_id to swap state
            ttl: Optional TTL in seconds

        Returns:
            True if all saved successfully
        """
        ttl = ttl or self.DEFAULT_TTL
        redis = await self._get_redis()

        if redis:
            try:
                pipe = redis.pipeline()
                for component_id, state in states.items():
                    key = self._make_key(dashboard_id, component_id)
                    pipe.setex(key, ttl, state.model_dump_json())
                await pipe.execute()
                logger.info("[SwapState] Batch saved %d states to Redis", len(states))
                return True
            except Exception as e:
                logger.warning("[SwapState] Redis batch save failed (%s)", e)

        # Memory fallback
        if dashboard_id not in self._memory_store:
            self._memory_store[dashboard_id] = {}
        self._memory_store[dashboard_id].update(states)
        logger.info("[SwapState] Batch saved %d states to memory", len(states))
        return True

    async def load(self, dashboard_id: str, component_id: str) -> Optional[SwapStateSnapshot]:
        """
        Load a single component's swap state.

        Args:
            dashboard_id: Dashboard identifier
            component_id: Component identifier

        Returns:
            SwapStateSnapshot if found, None otherwise
        """
        key = self._make_key(dashboard_id, component_id)
        redis = await self._get_redis()

        if redis:
            try:
                data = await redis.get(key)
                if data:
                    return SwapStateSnapshot.model_validate_json(data)
            except Exception as e:
                logger.warning("[SwapState] Redis load failed (%s)", e)

        # Memory fallback
        dashboard_states = self._memory_store.get(dashboard_id, {})
        return dashboard_states.get(component_id)

    async def load_all(self, dashboard_id: str) -> Dict[str, SwapStateSnapshot]:
        """
        Load all swap states for a dashboard.

        Args:
            dashboard_id: Dashboard identifier

        Returns:
            Map of component_id to swap state
        """
        redis = await self._get_redis()
        states: Dict[str, SwapStateSnapshot] = {}

        if redis:
            try:
                pattern = self._make_dashboard_pattern(dashboard_id)
                keys = []
                async for key in redis.scan_iter(match=pattern):
                    keys.append(key)

                if keys:
                    values = await redis.mget(keys)
                    prefix_len = len(f"{self.KEY_PREFIX}:{dashboard_id}:")

                    for key, data in zip(keys, values):
                        if data:
                            component_id = key[prefix_len:]
                            states[component_id] = SwapStateSnapshot.model_validate_json(data)

                logger.info("[SwapState] Loaded %d states from Redis for %s", len(states), dashboard_id[:8])
                return states

            except Exception as e:
                logger.warning("[SwapState] Redis load_all failed (%s)", e)

        # Memory fallback
        states = dict(self._memory_store.get(dashboard_id, {}))
        logger.info("[SwapState] Loaded %d states from memory for %s", len(states), dashboard_id[:8])
        return states

    async def delete(self, dashboard_id: str, component_id: str) -> bool:
        """
        Delete a single component's swap state.

        Args:
            dashboard_id: Dashboard identifier
            component_id: Component identifier

        Returns:
            True if deleted (or didn't exist)
        """
        key = self._make_key(dashboard_id, component_id)
        redis = await self._get_redis()

        if redis:
            try:
                await redis.delete(key)
                logger.debug("[SwapState] Deleted from Redis: %s", key)
            except Exception as e:
                logger.warning("[SwapState] Redis delete failed (%s)", e)

        # Memory fallback (always clean up)
        if dashboard_id in self._memory_store:
            self._memory_store[dashboard_id].pop(component_id, None)

        return True

    async def clear(self, dashboard_id: str) -> int:
        """
        Clear all swap states for a dashboard.

        Args:
            dashboard_id: Dashboard identifier

        Returns:
            Number of states cleared
        """
        count = 0
        redis = await self._get_redis()

        if redis:
            try:
                pattern = self._make_dashboard_pattern(dashboard_id)
                keys = []
                async for key in redis.scan_iter(match=pattern):
                    keys.append(key)

                if keys:
                    count = await redis.delete(*keys)
                    logger.info("[SwapState] Cleared %d states from Redis for %s", count, dashboard_id[:8])

            except Exception as e:
                logger.warning("[SwapState] Redis clear failed (%s)", e)

        # Memory fallback
        mem_states = self._memory_store.pop(dashboard_id, {})
        if mem_states:
            count = max(count, len(mem_states))
            logger.info("[SwapState] Cleared %d states from memory for %s", len(mem_states), dashboard_id[:8])

        return count


# Singleton instance
_repo: Optional[SwapStateRepository] = None


def get_swap_state_repo() -> SwapStateRepository:
    """
    Get the singleton swap state repository.

    Returns:
        SwapStateRepository instance
    """
    global _repo
    if _repo is None:
        _repo = SwapStateRepository()
    return _repo
