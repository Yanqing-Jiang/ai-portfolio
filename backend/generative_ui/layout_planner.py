# --- Layout Planner Function/Class Map ---
# Dataclass: LayoutOverride
#   Role: Constrained, catalog-safe override of default skill layout (variant, widget order, emphasis).
#   Called from: backend.generative_ui.runtime.A2UIRuntime, potential route hooks.
#   Invokes: n/a
#   Why: Allows the model to personalize layouts without breaking catalog/skill guardrails.
# Class: LayoutOverrideValidator
#   Role: Validate layout overrides against skill constraints.
#   Called from: LayoutPlanner.propose_override, backend.generative_ui.runtime (testing).
#   Invokes: skill metadata checks.
#   Why: Ensures layout overrides stay catalog-safe (no unknown widgets, valid variants).
# Class: LayoutPlanner
#   Role: Generate a LayoutOverride proposal for a given skill/plan.
#   Called from: backend.generative_ui.runtime.A2UIRuntime.
#   Invokes: _analyze_question_intent, optional model_proposer, LayoutOverrideValidator.validate.
#   Why: Centralizes layout-planning logic behind a safe interface.
# --- End Layout Planner Function/Class Map ---
"""
Constrained layout planner for A2UI.

The planner returns a small, validated override object instead of a free-form
component tree so that the renderer can stay deterministic and catalog-safe.
"""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass
from typing import List, Optional, Tuple

from .skills import A2UISkillMeta
from .config import get_settings

logger = logging.getLogger(__name__)

# Environment variable to enable LLM-based layout planning (default: False for cost/latency)
# Set GENUI_LAYOUT_USE_MODEL=true to enable Claude-driven layout proposals
LAYOUT_USE_MODEL_ENV = os.getenv("GENUI_LAYOUT_USE_MODEL", "false").lower() == "true"

# Allowed emphasis values
VALID_EMPHASIS = {"focus_chart", "focus_table", "focus_news", "balanced", None}


@dataclass(frozen=True)
class LayoutOverride:
    """
    Constrained, catalog-safe layout override.
    
    Dataclass: LayoutOverride — immutable override configuration.
    Called from: LayoutPlanner.propose_override, A2UIRuntime.stream_dashboard
    Invokes: n/a
    Purpose: Pass constrained layout variants to the emitter without breaking catalog.
    """

    layout_variant: Optional[str] = None
    widget_order: Optional[List[str]] = None
    emphasis: Optional[str] = None
    hidden_widgets: Optional[List[str]] = None


class LayoutOverrideValidator:
    """
    Validate layout overrides against skill constraints.
    
    Class: LayoutOverrideValidator — guards against invalid overrides.
    Called from: LayoutPlanner.propose_override
    Invokes: skill metadata validation
    Purpose: Keep layout planning catalog-safe by rejecting invalid requests.
    """

    @staticmethod
    def validate(override: LayoutOverride, skill: A2UISkillMeta) -> Tuple[bool, List[str]]:
        """
        Validate a layout override against skill constraints.
        
        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        errors = []

        # Check layout_variant
        if override.layout_variant:
            allowed_variants = skill.layout_variants or []
            if allowed_variants and override.layout_variant not in allowed_variants:
                errors.append(
                    f"layout_variant '{override.layout_variant}' not in allowed variants: {allowed_variants}"
                )

        # Check widget_order - all must be in skill's widgets
        if override.widget_order:
            allowed_widgets = set(skill.widgets or [])
            for widget in override.widget_order:
                if widget not in allowed_widgets:
                    errors.append(
                        f"widget '{widget}' in widget_order not in skill's widgets: {skill.widgets}"
                    )

        # Check hidden_widgets - all must be in skill's widgets
        if override.hidden_widgets:
            allowed_widgets = set(skill.widgets or [])
            for widget in override.hidden_widgets:
                if widget not in allowed_widgets:
                    errors.append(
                        f"widget '{widget}' in hidden_widgets not in skill's widgets: {skill.widgets}"
                    )

        # Check emphasis is a valid value
        if override.emphasis and override.emphasis not in VALID_EMPHASIS:
            errors.append(
                f"emphasis '{override.emphasis}' not valid. Allowed: {VALID_EMPHASIS}"
            )

        return (len(errors) == 0, errors)


def _analyze_question_intent(question: str) -> dict:
    """
    Analyze the user's question to determine layout preferences.
    
    Function: _analyze_question_intent — extracts layout hints from natural language.
    Called from: LayoutPlanner.propose_override
    Invokes: regex patterns
    Purpose: Heuristic question analysis to suggest appropriate layouts.
    
    Returns dict with detected intents:
        - focus_news: bool - user wants news/sentiment emphasized
        - focus_chart: bool - user wants visualization emphasized
        - focus_table: bool - user wants tabular data emphasized
        - wants_comparison: bool - multi-entity comparison context
        - time_sensitive: bool - question about trends/changes over time
    """
    lower = question.lower()
    
    intents = {
        "focus_news": False,
        "focus_chart": False,
        "focus_table": False,
        "wants_comparison": False,
        "time_sensitive": False,
    }
    
    # News-related patterns
    news_patterns = [
        r"\bnews\b", r"\bheadline", r"\bsentiment\b", r"\bannounce",
        r"\bpress release\b", r"\breach\b", r"\breport\b"
    ]
    if any(re.search(p, lower) for p in news_patterns):
        intents["focus_news"] = True
    
    # Chart/visualization patterns
    chart_patterns = [
        r"\bchart\b", r"\bgraph\b", r"\bvisuali", r"\btrend\b", r"\bplot\b",
        r"\bshow me\b", r"\bover time\b", r"\bhistor"
    ]
    if any(re.search(p, lower) for p in chart_patterns):
        intents["focus_chart"] = True
    
    # Table/data patterns
    table_patterns = [
        r"\btable\b", r"\blist\b", r"\bdata\b", r"\bnumber", r"\bmetric",
        r"\bbreak\s*down\b", r"\bdetail"
    ]
    if any(re.search(p, lower) for p in table_patterns):
        intents["focus_table"] = True
    
    # Comparison patterns
    compare_patterns = [
        r"\bvs\b", r"\bversus\b", r"\bcompare", r"\bbenchmark\b",
        r"\bagainst\b", r"\bstack up\b", r"\bhead to head\b"
    ]
    if any(re.search(p, lower) for p in compare_patterns):
        intents["wants_comparison"] = True
    
    # Time-sensitive patterns
    time_patterns = [
        r"\btrend\b", r"\bover\s+\w+\s+months?\b", r"\byear\s+over\s+year\b",
        r"\bquarter", r"\bchange\b", r"\bgrow", r"\bdecline"
    ]
    if any(re.search(p, lower) for p in time_patterns):
        intents["time_sensitive"] = True
    
    return intents


class LayoutPlanner:
    """
    Generate layout overrides for A2UI skills.
    
    Class: LayoutPlanner — heuristic layout proposal and validation.
    Called from: backend.generative_ui.runtime.A2UIRuntime.stream_dashboard
    Invokes: _analyze_question_intent, optional model proposer, LayoutOverrideValidator.validate
    Purpose: Propose context-aware layouts while maintaining catalog safety.
    """

    def __init__(self, *, use_model: Optional[bool] = None) -> None:
        """
        Initialize planner.
        
        Args:
            use_model: Whether to call Claude for overrides. If None, uses GENUI_LAYOUT_USE_MODEL env var.
                       Defaults to False (heuristics-only) for cost/latency optimization.
        """
        self.enabled = True
        # Use explicit parameter if provided, otherwise fall back to environment variable
        self.use_model = use_model if use_model is not None else LAYOUT_USE_MODEL_ENV
        self.validator = LayoutOverrideValidator()
        try:
            import anthropic  # type: ignore
            self._anthropic = anthropic
        except Exception:
            self._anthropic = None

    def propose_override(
        self, skill: A2UISkillMeta, question: str
    ) -> Optional[LayoutOverride]:
        """
        Propose a layout override constrained by the skill's widget/layout set.
        
        Uses heuristic question analysis to suggest appropriate emphasis and variants.
        All proposals are validated before returning to ensure catalog safety.
        
        Args:
            skill: The selected skill with its layout constraints
            question: The user's original question
            
        Returns:
            A validated LayoutOverride or None if default layout should be used
        """
        if not self.enabled:
            return None

        heuristic_override = self._build_heuristic_override(skill, question)

        # Optional model proposal
        if self.use_model:
            model_override = self._propose_override_with_model(skill, question)
            if model_override:
                is_valid, errors = self.validator.validate(model_override, skill)
                if is_valid:
                    return model_override
                logger.warning("Model override rejected for %s: %s", skill.skill_id, errors)

        if heuristic_override is None:
            return None

        is_valid, errors = self.validator.validate(heuristic_override, skill)
        if not is_valid:
            logger.warning(
                "Layout override rejected for skill %s: %s",
                skill.skill_id, errors
            )
            return LayoutOverride(
                layout_variant=skill.default_variant,
                widget_order=None,
                emphasis=None,
                hidden_widgets=None,
            )

        logger.debug(
            "Layout override proposed for skill %s: variant=%s, emphasis=%s",
            skill.skill_id, heuristic_override.layout_variant, heuristic_override.emphasis
        )
        return heuristic_override

    # ------------------------------------------------------------------
    # Model-backed planner helpers (Claude Agent SDK)
    # ------------------------------------------------------------------
    def _build_tool_schema(self, skill: A2UISkillMeta) -> dict:
        """Define the Claude tool schema for layout override proposals."""
        return {
            "name": "propose_layout_override",
            "description": (
                "Choose a layout variant and optional widget ordering for the given skill. "
                "Use only the allowed variants and widgets provided."
            ),
            "strict": True,
            "input_schema": {
                "type": "object",
                "properties": {
                    "layout_variant": {
                        "type": "string",
                        "enum": skill.layout_variants or ([skill.default_variant] if skill.default_variant else []),
                        "description": "Pick one allowed layout variant.",
                    },
                    "widget_order": {
                        "type": "array",
                        "items": {"type": "string", "enum": skill.widgets},
                        "description": "Optional widget ordering to emphasize intent.",
                    },
                    "hidden_widgets": {
                        "type": "array",
                        "items": {"type": "string", "enum": skill.widgets},
                        "description": "Widgets to hide when not relevant.",
                    },
                    "emphasis": {
                        "type": "string",
                        "enum": [v for v in VALID_EMPHASIS if v],
                        "description": "High-level emphasis for the layout.",
                    },
                },
                "required": ["layout_variant"],
            },
        }

    def _propose_override_with_model(
        self, skill: A2UISkillMeta, question: str
    ) -> Optional[LayoutOverride]:
        """Call Claude to propose an override; falls back silently on errors."""
        if self._anthropic is None:
            return None
        settings = get_settings()
        if not settings.claude_api_key:
            return None

        tool = self._build_tool_schema(skill)
        system_prompt = (
            "You are a layout planner for a catalog-safe A2UI dashboard. "
            "Use only allowed variants and widgets. Prefer balanced layouts unless "
            "the question clearly signals focus on news, charts, or tables. "
            "Respond only via the provided tool."
        )
        try:
            client = self._anthropic.Anthropic(api_key=settings.claude_api_key)
            response = client.messages.create(
                model=settings.claude_model or "claude-haiku-4-5-20251001",
                system=system_prompt,
                messages=[{"role": "user", "content": f"Question: {question}\nSkill: {skill.skill_id}"}],
                tools=[tool],
                tool_choice={"type": "tool", "name": tool["name"]},
                max_tokens=256,
            )
            for block in response.content or []:
                if getattr(block, "type", None) == "tool_use" and getattr(block, "name", "") == tool["name"]:
                    payload = getattr(block, "input", {}) or {}
                    return LayoutOverride(
                        layout_variant=payload.get("layout_variant"),
                        widget_order=payload.get("widget_order"),
                        emphasis=payload.get("emphasis"),
                        hidden_widgets=payload.get("hidden_widgets"),
                    )
            return None
        except Exception as exc:  # pragma: no cover - network/SDK errors
            logger.warning("Model planner failed: %s", exc)
            return None

    def _build_heuristic_override(self, skill: A2UISkillMeta, question: str) -> Optional[LayoutOverride]:
        """Heuristic (regex) planner used as default and fallback."""
        intents = _analyze_question_intent(question)

        emphasis = None
        if intents["focus_news"]:
            emphasis = "focus_news"
        elif intents["focus_chart"] or intents["time_sensitive"]:
            emphasis = "focus_chart"
        elif intents["focus_table"]:
            emphasis = "focus_table"
        elif intents["wants_comparison"]:
            emphasis = "balanced"

        variant = skill.default_variant
        if skill.layout_variants:
            if emphasis == "focus_chart" and "grid_focus_chart" in skill.layout_variants:
                variant = "grid_focus_chart"
            elif variant and variant not in skill.layout_variants:
                variant = skill.layout_variants[0]
            elif not variant:
                variant = skill.layout_variants[0]

        widget_order: Optional[List[str]] = None
        hidden_widgets: Optional[List[str]] = None

        suggested_order: List[str] = []
        if emphasis == "focus_news":
            suggested_order = ["NewsTimeline", "KpiCard", "PriceChart", "ExplainMovePanel", "DataTable"]
        elif emphasis == "focus_chart":
            suggested_order = ["PriceChart", "MetricChart", "CorrelationMatrix", "KpiCard", "DataTable", "ExplainMovePanel"]
        elif emphasis == "focus_table":
            suggested_order = ["DataTable", "KpiCard", "PriceChart", "ExplainMovePanel"]

        if suggested_order:
            widget_order = [w for w in suggested_order if w in (skill.widgets or [])]
            if not widget_order:
                widget_order = None

        if not any([variant != skill.default_variant, emphasis, widget_order, hidden_widgets]):
            return None

        return LayoutOverride(
            layout_variant=variant,
            widget_order=widget_order,
            emphasis=emphasis,
            hidden_widgets=hidden_widgets,
        )


__all__ = ["LayoutPlanner", "LayoutOverride", "LayoutOverrideValidator"]
