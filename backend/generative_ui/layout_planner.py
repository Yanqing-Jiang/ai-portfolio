# --- Layout Planner Function/Class Map ---
# Dataclass: LayoutOverride
#   Role: Constrained, catalog-safe override of default skill layout (variant, widget order, emphasis).
#   Called from: backend.generative_ui.runtime.A2UIRuntime (future), potential route hooks.
#   Invokes: n/a
#   Why: Allows the model to personalize layouts without breaking catalog/skill guardrails.
# Class: LayoutPlanner
#   Role: Generate a LayoutOverride proposal for a given skill/plan.
#   Called from: backend.generative_ui.runtime.A2UIRuntime (future).
#   Invokes: (future) Claude Agent SDK or Messages API; currently returns None to preserve defaults.
#   Why: Centralizes layout-planning logic behind a safe interface.
# --- End Layout Planner Function/Class Map ---
"""
Constrained layout planner for A2UI.

The planner returns a small, validated override object instead of a free-form
component tree so that the renderer can stay deterministic and catalog-safe.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from .skills import A2UISkillMeta


@dataclass(frozen=True)
class LayoutOverride:
    """Constrained, catalog-safe layout override."""

    layout_variant: Optional[str] = None
    widget_order: Optional[List[str]] = None
    emphasis: Optional[str] = None
    hidden_widgets: Optional[List[str]] = None


class LayoutPlanner:
    """Generate layout overrides for A2UI skills."""

    def __init__(self) -> None:
        """Initialize planner (placeholder for future model clients)."""
        # In the future: inject Claude Agent SDK client or OpenAI client
        # based on settings.
        self.enabled = True

    def propose_override(self, skill: A2UISkillMeta, question: str) -> Optional[LayoutOverride]:
        """
        Propose a layout override constrained by the skill's widget/layout set.

        Current behavior: return None to preserve deterministic templates while
        the runtime loop is being built. This function is intentionally a thin
        seam so we can later add model-backed proposals with server-side
        validation.
        """
        if not self.enabled:
            return None

        # Heuristic placeholder: keep template, but if the user asks about news,
        # suggest a "focus_news" emphasis when allowed by skill metadata.
        lower_q = question.lower()
        emphasis = None
        if "news" in lower_q or "headline" in lower_q:
            emphasis = "focus_news"

        # Respect allowed variants if provided
        variant = skill.default_variant if skill.default_variant else None
        if skill.layout_variants and variant not in skill.layout_variants:
            variant = skill.layout_variants[0]

        if not any([variant, emphasis]):
            return None

        return LayoutOverride(
            layout_variant=variant,
            widget_order=None,
            emphasis=emphasis,
            hidden_widgets=None,
        )


__all__ = ["LayoutPlanner", "LayoutOverride"]
