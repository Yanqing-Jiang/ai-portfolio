"""Canonical function names and their stable external representations."""

from __future__ import annotations

from typing import Literal, TypeAlias

CanonicalFunction: TypeAlias = Literal["wish", "cycle", "compatibility", "occasion"]

FUNCTION_TO_SLUG: dict[CanonicalFunction, str] = {
    "wish": "custom-wish",
    "cycle": "luck-draw",
    "compatibility": "compatibility",
    "occasion": "lucky-day",
}
SLUG_TO_FUNCTION: dict[str, CanonicalFunction] = {
    slug: function_id for function_id, slug in FUNCTION_TO_SLUG.items()
}
FUNCTION_TO_FOCUS_PREFIX: dict[CanonicalFunction, str] = {
    "wish": "custom_wish",
    "cycle": "luck_cycle",
    "compatibility": "compatibility",
    "occasion": "occasion",
}


def parse_focus(focus: str | None) -> CanonicalFunction | None:
    """Return the canonical function encoded by a wire-format focus string."""
    normalized = (focus or "").lower().strip()
    for function_id, prefix in FUNCTION_TO_FOCUS_PREFIX.items():
        if normalized == prefix or normalized.startswith(f"{prefix}:"):
            return function_id
    return None


def canonical_function(
    focus: str | None,
    question: str | None = None,
) -> CanonicalFunction | None:
    """Classify a reading, using a question as the wish fallback."""
    return parse_focus(focus) or ("wish" if question else None)
