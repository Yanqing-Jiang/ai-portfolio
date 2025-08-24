"""Planning node for Next Gen Analytics (Memory)."""
from __future__ import annotations

from typing import Dict, Any


def plan(state: Dict[str, Any]) -> Dict[str, Any]:
    """Placeholder planning implementation.

    In the real system this would decompose the user query into concrete
    SQL tasks and handle clarification when needed.
    """
    return {"sql": None, "needs_clarification": False}


__all__ = ["plan"]
