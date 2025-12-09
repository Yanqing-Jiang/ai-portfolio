# Skill registry utilities for conversational analytics.
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

BASE_DIR = Path(__file__).parent


@dataclass
class SkillMeta:
    """Skill metadata used for routing and client surfacing."""
    skill_id: str
    name: str
    filename: str
    keywords: List[str]
    description: str

    @property
    def path(self) -> Path:
        return BASE_DIR / self.filename


SKILL_INDEX: List[SkillMeta] = [
    SkillMeta(
        skill_id="market_share_single",
        name="Market Share (Single Company)",
        filename="skill_market_share_single.md",
        keywords=["market share", "share of market", "market position"],
        description="Calculate a company's market share versus peers.",
    ),
    SkillMeta(
        skill_id="revenue_comparison",
        name="Revenue Comparison (Peers)",
        filename="skill_revenue_comparison.md",
        keywords=["revenue comparison", "revenue vs", "compare revenue", "between"],
        description="Compare revenue across peer tickers over time.",
    ),
    SkillMeta(
        skill_id="revenue_growth",
        name="Revenue Growth (YoY/QoQ)",
        filename="skill_revenue_growth.md",
        keywords=["revenue growth", "growth rate", "yoy", "qoq", "growth"],
        description="Compute revenue growth rates over time.",
    ),
    SkillMeta(
        skill_id="margins_vs_peers",
        name="Margins vs Peers",
        filename="skill_margins_vs_peers.md",
        keywords=["margin", "profit margin", "vs peers", "industry average"],
        description="Compare margins against peer averages.",
    ),
    SkillMeta(
        skill_id="margin_growth_peers",
        name="Margin Growth vs Peers",
        filename="skill_margin_growth_peers.md",
        keywords=["margin growth", "margin expansion", "change in margin"],
        description="Track margin growth vs peer averages.",
    ),
    SkillMeta(
        skill_id="offscope_greeting",
        name="Off-Scope / Greeting",
        filename="skill_offscope_greeting.md",
        keywords=["hello", "hi", "hey", "thanks", "not finance", "non financial"],
        description="Politely decline or handle greetings without tools.",
    ),
]


def _normalize(text: str) -> str:
    """Function: _normalize — called by skill selection to lower/strip user text."""
    return re.sub(r"\s+", " ", text).lower().strip()


def select_skill(user_message: str) -> Optional[SkillMeta]:
    """Function: select_skill — called from agent to choose a skill based on keywords."""
    text = _normalize(user_message)
    for skill in SKILL_INDEX:
        if any(kw in text for kw in skill.keywords):
            return skill
    return None


def load_skill_content(skill: SkillMeta) -> str:
    """Function: load_skill_content — reads a skill markdown file for prompt injection."""
    return skill.path.read_text(encoding="utf-8")


__all__ = ["SkillMeta", "SKILL_INDEX", "select_skill", "load_skill_content"]

