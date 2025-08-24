"""Cache invalidation rules."""
from __future__ import annotations

from typing import Iterable


def invalidate_keys(keys: Iterable[str]) -> None:
    """Placeholder for invalidation logic."""
    # Real implementation would drop keys from distributed cache
    pass


__all__ = ["invalidate_keys"]
