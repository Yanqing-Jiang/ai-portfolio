"""Incremental SQL node computing deltas against cached data."""
from __future__ import annotations

from typing import Dict, Any


def incremental_sql(state: Dict[str, Any]) -> Dict[str, Any]:
    """Placeholder incremental query implementation."""
    return {"df_key": None, "cache_hit": False}


__all__ = ["incremental_sql"]
