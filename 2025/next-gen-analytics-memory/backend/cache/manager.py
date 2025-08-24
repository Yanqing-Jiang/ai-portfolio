"""Cache manager and configuration."""
from __future__ import annotations

from typing import Any, Dict


CACHE_CONFIG = {
    "df_ttl_seconds": 86400,
    "chart_ttl_seconds": 604800,
    "sql_ttl_seconds": 3600,
    "max_cache_size_gb": 10,
    "eviction_policy": "LRU",
}


class CacheManager:
    """Very small in-memory cache placeholder."""

    def __init__(self) -> None:
        self.store: Dict[str, Any] = {}

    def get(self, key: str) -> Any:
        return self.store.get(key)

    def set(self, key: str, value: Any) -> None:
        self.store[key] = value

    def clear(self) -> None:
        self.store.clear()


__all__ = ["CACHE_CONFIG", "CacheManager"]
