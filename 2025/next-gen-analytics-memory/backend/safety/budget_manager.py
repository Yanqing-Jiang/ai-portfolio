"""Resource budget tracking (placeholder)."""
from __future__ import annotations

from typing import Tuple


def check_budget(time_ms_left: int, tokens_left: int, bytes_left: int) -> Tuple[bool, str]:
    """Very small budget check that always passes."""
    return True, "ok"


__all__ = ["check_budget"]
