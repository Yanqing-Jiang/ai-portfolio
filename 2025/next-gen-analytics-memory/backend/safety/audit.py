"""Audit trail utilities."""
from __future__ import annotations

from typing import Any, Dict


def log_event(event: Dict[str, Any]) -> None:
    """Placeholder logging that simply prints the event."""
    print(event)


__all__ = ["log_event"]
