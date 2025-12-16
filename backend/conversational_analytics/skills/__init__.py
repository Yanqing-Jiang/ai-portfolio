# Skill registry utilities for conversational analytics.
# Claude-native skill routing: Claude decides which skill to use based on descriptions.
from __future__ import annotations

import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from ..config import settings
from ..sdk_assets import load_skill_override, should_use_sdk_assets

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
    """Function: SkillMeta — skill metadata used for routing and client surfacing.
    Called from: agent when Claude indicates a skill, skill catalog builder.
    Purpose: Lightweight metadata holder; actual routing is done by Claude using descriptions."""
    skill_id: str
    name: str
    filename: str
    description: str  # Brief description for the index (full description in YAML frontmatter)

    @property
    def path(self) -> Path:
        return BASE_DIR / self.filename


# Skill index - descriptions here are brief; full descriptions are in YAML frontmatter
SKILL_INDEX: List[SkillMeta] = [
    SkillMeta(
        skill_id="market_share_single",
        name="Market Share (Single Company)",
        filename="skill_market_share_single.md",
        description="Calculate a company's market share versus peers.",
    ),
    SkillMeta(
        skill_id="revenue_comparison",
        name="Revenue Comparison (Peers)",
        filename="skill_revenue_comparison.md",
        description="Compare revenue across peer tickers over time.",
    ),
    SkillMeta(
        skill_id="revenue_growth",
        name="Revenue Growth (YoY/QoQ)",
        filename="skill_revenue_growth.md",
        description="Compute revenue growth rates over time.",
    ),
    SkillMeta(
        skill_id="margins_vs_peers",
        name="Margins vs Peers",
        filename="skill_margins_vs_peers.md",
        description="Compare margins against peer averages.",
    ),
    SkillMeta(
        skill_id="margin_growth_peers",
        name="Margin Growth vs Peers",
        filename="skill_margin_growth_peers.md",
        description="Track margin growth vs peer averages.",
    ),
    SkillMeta(
        skill_id="project_showcase",
        name="Project Showcase / Architecture Demo",
        filename="skill_project_showcase.md",
        description="Educational walkthrough of the Next Gen Analytics Agent architecture.",
    ),
]


def _normalize(text: str) -> str:
    """Function: _normalize — normalizes text for slot extraction."""
    return re.sub(r"\s+", " ", text).lower().strip()


def _parse_yaml_frontmatter(content: str) -> Tuple[Dict[str, Any], str]:
    """Function: _parse_yaml_frontmatter — extracts YAML frontmatter from skill markdown.
    Called from: build_skill_catalog, load_skill_content_without_frontmatter.
    Returns: (frontmatter_dict, remaining_content)
    Purpose: Separates skill description metadata from skill instructions."""
    if not content.startswith("---"):
        return {}, content
    
    # Find the closing ---
    end_idx = content.find("---", 3)
    if end_idx == -1:
        return {}, content
    
    yaml_block = content[3:end_idx].strip()
    remaining = content[end_idx + 3:].strip()
    
    # Simple YAML parsing for name and description
    frontmatter: Dict[str, Any] = {}
    current_key = None
    current_value_lines: List[str] = []
    
    for line in yaml_block.split("\n"):
        # Check for new key
        if ":" in line and not line.startswith(" ") and not line.startswith("\t"):
            # Save previous key if exists
            if current_key and current_value_lines:
                value = "\n".join(current_value_lines).strip()
                # Remove leading | for multiline
                if value.startswith("|"):
                    value = value[1:].strip()
                frontmatter[current_key] = value
            
            key, _, value = line.partition(":")
            current_key = key.strip()
            value = value.strip()
            
            if value and value != "|":
                frontmatter[current_key] = value
                current_key = None
                current_value_lines = []
            else:
                current_value_lines = []
        elif current_key:
            # Continuation of multiline value
            current_value_lines.append(line.strip())
    
    # Save last key
    if current_key and current_value_lines:
        value = "\n".join(current_value_lines).strip()
        frontmatter[current_key] = value
    
    return frontmatter, remaining


def get_skill_by_id(skill_id: str) -> Optional[SkillMeta]:
    """Function: get_skill_by_id — retrieves a skill by its ID.
    Called from: agent when Claude indicates which skill to use.
    Purpose: Lookup skill metadata after Claude makes a routing decision."""
    for skill in SKILL_INDEX:
        if skill.skill_id == skill_id:
            return skill
    return None


def load_skill_content(skill: SkillMeta) -> str:
    """Function: load_skill_content — reads a skill markdown file for prompt injection.
    Called from: agent when building system prompt after Claude selects a skill.
    Invokes: optional `.claude/skills` mirror before falling back to in-repo skills.
    Purpose: Returns full skill content including frontmatter."""
    if should_use_sdk_assets(settings.use_sdk_assets):
        override = load_skill_override(skill.filename)
        if override:
            return override
    return skill.path.read_text(encoding="utf-8")


def load_skill_instructions(skill: SkillMeta) -> str:
    """Function: load_skill_instructions — reads skill content without YAML frontmatter.
    Called from: agent when injecting skill guidance after selection.
    Purpose: Returns only the instruction part, not the routing description."""
    content = load_skill_content(skill)
    _, instructions = _parse_yaml_frontmatter(content)
    return instructions


@lru_cache(maxsize=1)
def build_skill_catalog() -> str:
    """Function: build_skill_catalog — builds a catalog of all skills with descriptions.
    Called from: agent when constructing the system prompt.
    Purpose: Provides Claude with all skill descriptions so it can decide which to use.
    
    The catalog includes each skill's name, ID, and full description from YAML frontmatter.
    Claude uses this to autonomously decide which skill (if any) applies to the user's request."""
    
    catalog_lines = [
        "## Available Skills",
        "",
        "You have access to specialized skills for financial analysis. Review the descriptions below and decide which skill (if any) best matches the user's request.",
        "",
        "**IMPORTANT**: You are NOT required to use a skill. If the user's request doesn't match any skill, respond naturally without activating a skill. Skills are optional guidance, not mandatory routing.",
        "",
        "When you decide to use a skill, indicate it by including `[SKILL: skill_id]` at the start of your response (e.g., `[SKILL: market_share_single]`). The full skill instructions will then be loaded.",
        "",
    ]
    
    for skill in SKILL_INDEX:
        # Load and parse frontmatter for full description
        try:
            content = load_skill_content(skill)
            frontmatter, _ = _parse_yaml_frontmatter(content)
            description = frontmatter.get("description", skill.description)
        except Exception:
            description = skill.description
        
        catalog_lines.append(f"### {skill.name}")
        catalog_lines.append(f"**Skill ID**: `{skill.skill_id}`")
        catalog_lines.append(f"**Description**:")
        catalog_lines.append(description)
        catalog_lines.append("")
    
    return "\n".join(catalog_lines)


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
    "project_showcase": [],
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


def extract_skill_from_response(response_text: str) -> Optional[str]:
    """Function: extract_skill_from_response — extracts skill ID from Claude's response.
    Called from: agent after receiving Claude's first response.
    Purpose: Detects if Claude indicated a skill using [SKILL: skill_id] marker.
    
    Returns the skill_id if found, None otherwise."""
    # Look for [SKILL: skill_id] pattern
    match = re.search(r'\[SKILL:\s*(\w+)\]', response_text)
    if match:
        return match.group(1)
    return None


__all__ = [
    "SkillMeta",
    "SlotSpec", 
    "SKILL_INDEX",
    "SKILL_SLOTS",
    "get_skill_by_id",
    "load_skill_content",
    "load_skill_instructions",
    "build_skill_catalog",
    "extract_skill_from_response",
    "get_skill_slots",
    "extract_slots_from_text",
    "resolve_slots",
]
