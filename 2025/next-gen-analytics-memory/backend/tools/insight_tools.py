"""High-level tools for generating insights."""
from __future__ import annotations

from typing import Any


def generate_insight(df_key: str, context: str) -> str:
    """Return a simple insight placeholder."""
    return f"Insight for {df_key}: {context}"


def suggest_next_questions(context: str) -> list[str]:
    """Return follow-up question suggestions (placeholder)."""
    return ["What happened next?", "Can you compare with peers?"]


__all__ = ["generate_insight", "suggest_next_questions"]
