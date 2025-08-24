"""SQL execution node with cache awareness."""
from __future__ import annotations

from typing import Dict, Any


def execute_sql(state: Dict[str, Any]) -> Dict[str, Any]:
    """Execute SQL or return cached dataframe.

    This placeholder simply records a cache miss and returns no data.
    """
    return {"df_key": None, "cache_hit": False}


__all__ = ["execute_sql"]
