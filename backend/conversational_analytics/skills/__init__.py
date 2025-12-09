# Skill registry utilities for conversational analytics.
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

BASE_DIR = Path(__file__).parent


@dataclass
class SlotSpec:
    """Specification for a skill input slot (used for HITL slot resolution)."""
    name: str
    required: bool = False
    default: Any = None
    options: List[str] = field(default_factory=list)
    description: str = ""


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


# Slot specifications per skill (defines required/optional slots, defaults, and options for HITL)
SKILL_SLOTS: Dict[str, List[SlotSpec]] = {
    "market_share_single": [
        SlotSpec(name="target_ticker", required=True, description="Target company ticker"),
        SlotSpec(name="ticker_list", required=False, default=["NVDA", "AMD", "INTC", "AVGO", "QCOM", "MU", "TXN"], description="Peer tickers"),
        SlotSpec(name="years_back", required=False, default=5, options=["3", "5", "10"], description="Years of history"),
        SlotSpec(name="period_filter", required=False, default="year", options=["quarter", "year"], description="Period granularity"),
    ],
    "revenue_comparison": [
        SlotSpec(name="ticker_list", required=True, default=["NVDA", "AMD", "INTC"], description="Tickers to compare (2-6)"),
        SlotSpec(name="years_back", required=False, default=5, options=["3", "5", "10"], description="Years of history"),
        SlotSpec(name="period_filter", required=True, default=None, options=["quarter", "year"], description="Period granularity"),
    ],
    "revenue_growth": [
        SlotSpec(name="ticker_list", required=False, default=["NVDA", "AMD", "INTC"], description="Tickers to compare"),
        SlotSpec(name="years_back", required=False, default=5, options=["3", "5", "10"], description="Years of history"),
        SlotSpec(name="period_filter", required=True, default=None, options=["quarter", "year"], description="Period granularity"),
        SlotSpec(name="growth_basis", required=False, default="yoy", options=["yoy", "qoq"], description="Growth calculation basis"),
    ],
    "margins_vs_peers": [
        SlotSpec(name="target_ticker", required=True, description="Target company ticker"),
        SlotSpec(name="ticker_list", required=False, default=["NVDA", "AMD", "INTC", "AVGO", "QCOM", "MU", "TXN"], description="Peer tickers"),
        SlotSpec(name="metric", required=True, default=None, options=["gross_margin", "operating_margin", "net_margin"], description="Margin type"),
        SlotSpec(name="years_back", required=False, default=5, options=["3", "5", "10"], description="Years of history"),
        SlotSpec(name="period_filter", required=True, default=None, options=["quarter", "year"], description="Period granularity"),
    ],
    "margin_growth_peers": [
        SlotSpec(name="target_ticker", required=True, description="Target company ticker"),
        SlotSpec(name="ticker_list", required=False, default=["NVDA", "AMD", "INTC", "AVGO", "QCOM", "MU", "TXN"], description="Peer tickers"),
        SlotSpec(name="metric", required=True, default=None, options=["gross_margin", "operating_margin", "net_margin"], description="Margin type"),
        SlotSpec(name="years_back", required=False, default=5, options=["3", "5", "10"], description="Years of history"),
        SlotSpec(name="period_filter", required=True, default=None, options=["quarter", "year"], description="Period granularity"),
    ],
    "offscope_greeting": [],
}


def get_skill_slots(skill: SkillMeta) -> List[SlotSpec]:
    """Function: get_skill_slots — returns slot specifications for a skill (used for HITL resolution).
    Called from: agent slot resolver.
    Purpose: Enables the agent to determine which slots need user clarification."""
    return SKILL_SLOTS.get(skill.skill_id, [])


def extract_slots_from_text(text: str, slots: List[SlotSpec]) -> Dict[str, Any]:
    """Function: extract_slots_from_text — heuristically extracts slot values from user text.
    Called from: agent before deciding whether to HITL.
    Purpose: Pre-fill slots using keyword matching to reduce unnecessary HITL prompts."""
    normalized = _normalize(text)
    extracted: Dict[str, Any] = {}
    
    # Ticker extraction (uppercase 2-5 letter words)
    ticker_pattern = r'\b([A-Z]{2,5})\b'
    found_tickers = re.findall(ticker_pattern, text.upper())
    known_tickers = {"NVDA", "AMD", "INTC", "AVGO", "QCOM", "MU", "TXN"}
    valid_tickers = [t for t in found_tickers if t in known_tickers]
    
    for slot in slots:
        if slot.name in ("target_ticker", "ticker_list"):
            if valid_tickers:
                if slot.name == "target_ticker":
                    extracted["target_ticker"] = valid_tickers[0]
                else:
                    extracted["ticker_list"] = valid_tickers if len(valid_tickers) > 1 else slot.default
        
        elif slot.name == "period_filter":
            if any(kw in normalized for kw in ["quarter", "quarterly", "qoq", "q/"]):
                extracted["period_filter"] = "quarter"
            elif any(kw in normalized for kw in ["year", "yearly", "annual", "yoy"]):
                extracted["period_filter"] = "year"
        
        elif slot.name == "years_back":
            # Look for "last N years" or "N year" patterns
            year_match = re.search(r'(\d+)\s*(?:year|yr)', normalized)
            if year_match:
                years = int(year_match.group(1))
                if years in (3, 5, 10):
                    extracted["years_back"] = years
        
        elif slot.name == "metric":
            if any(kw in normalized for kw in ["gross", "gross margin"]):
                extracted["metric"] = "gross_margin"
            elif any(kw in normalized for kw in ["operating", "op margin", "ebit"]):
                extracted["metric"] = "operating_margin"
            elif any(kw in normalized for kw in ["net", "net margin", "bottom line"]):
                extracted["metric"] = "net_margin"
        
        elif slot.name == "growth_basis":
            if "qoq" in normalized or "quarter over" in normalized:
                extracted["growth_basis"] = "qoq"
            elif "yoy" in normalized or "year over" in normalized:
                extracted["growth_basis"] = "yoy"
    
    return extracted


def resolve_slots(skill: SkillMeta, user_text: str) -> tuple[Dict[str, Any], List[SlotSpec]]:
    """Function: resolve_slots — resolves slot values and identifies ambiguous required slots.
    Called from: agent.run_with_tools before tool execution.
    Returns: (resolved_slots, ambiguous_slots) where ambiguous_slots need HITL.
    Purpose: Centralized slot resolution for HITL flow."""
    slots = get_skill_slots(skill)
    extracted = extract_slots_from_text(user_text, slots)
    
    resolved: Dict[str, Any] = {}
    ambiguous: List[SlotSpec] = []
    
    for slot in slots:
        if slot.name in extracted:
            resolved[slot.name] = extracted[slot.name]
        elif slot.default is not None:
            resolved[slot.name] = slot.default
        elif slot.required:
            # Required slot missing and no default -> ambiguous
            ambiguous.append(slot)
    
    return resolved, ambiguous


__all__ = [
    "SkillMeta",
    "SlotSpec", 
    "SKILL_INDEX",
    "SKILL_SLOTS",
    "select_skill",
    "load_skill_content",
    "get_skill_slots",
    "extract_slots_from_text",
    "resolve_slots",
]

