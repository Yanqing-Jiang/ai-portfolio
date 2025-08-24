"""Chart rendering node that never re-queries data."""
from __future__ import annotations

from typing import Dict, Any


def render_chart(state: Dict[str, Any]) -> Dict[str, Any]:
    """Generate chart spec from cached dataframe (placeholder)."""
    return {"chart_key": None}


__all__ = ["render_chart"]
