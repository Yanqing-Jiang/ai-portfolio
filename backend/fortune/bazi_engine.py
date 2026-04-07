"""Deterministic BaZi (Four Pillars) advanced computation engine.

Extends calendar_tool.py with: hidden stems, 10 Gods, branch interactions,
seasonal strength, luck pillars (大运), annual pillars (流年), and enhanced
element counting. All computations are pure lookup tables — no LLM calls.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

import cnlunar
from pydantic import BaseModel, Field

try:
    from .calendar_tool import (
        BaziChart,
        Pillar,
        STEM_TO_ELEMENT,
        BRANCH_TO_ELEMENT,
        FIVE_ELEMENTS,
        compute_bazi_chart,
        _normalize_dt,
    )
except ImportError:
    from calendar_tool import (  # type: ignore[no-redef]
        BaziChart,
        Pillar,
        STEM_TO_ELEMENT,
        BRANCH_TO_ELEMENT,
        FIVE_ELEMENTS,
        compute_bazi_chart,
        _normalize_dt,
    )

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

HEAVENLY_STEMS = "甲乙丙丁戊己庚辛壬癸"
EARTHLY_BRANCHES = "子丑寅卯辰巳午未申酉戌亥"

YANG_STEMS = frozenset("甲丙戊庚壬")
YIN_STEMS = frozenset("乙丁己辛癸")

# Element generation cycle: Wood → Fire → Earth → Metal → Water → Wood
GENERATES: dict[str, str] = {
    "wood": "fire", "fire": "earth", "earth": "metal",
    "metal": "water", "water": "wood",
}

# Element control cycle: Wood → Earth → Water → Fire → Metal → Wood
CONTROLS: dict[str, str] = {
    "wood": "earth", "earth": "water", "water": "fire",
    "fire": "metal", "metal": "wood",
}

# Reverse lookups
GENERATED_BY = {v: k for k, v in GENERATES.items()}
CONTROLLED_BY = {v: k for k, v in CONTROLS.items()}

# ---------------------------------------------------------------------------
# Hidden Stems (藏干) — each branch contains 1-3 hidden stems
# ---------------------------------------------------------------------------

HIDDEN_STEMS_TABLE: dict[str, list[tuple[str, str]]] = {
    #  branch: [(stem, strength), ...]
    "子": [("癸", "main_qi")],
    "丑": [("己", "main_qi"), ("癸", "middle_qi"), ("辛", "residual_qi")],
    "寅": [("甲", "main_qi"), ("丙", "middle_qi"), ("戊", "residual_qi")],
    "卯": [("乙", "main_qi")],
    "辰": [("戊", "main_qi"), ("乙", "middle_qi"), ("癸", "residual_qi")],
    "巳": [("丙", "main_qi"), ("庚", "middle_qi"), ("戊", "residual_qi")],
    "午": [("丁", "main_qi"), ("己", "middle_qi")],
    "未": [("己", "main_qi"), ("丁", "middle_qi"), ("乙", "residual_qi")],
    "申": [("庚", "main_qi"), ("壬", "middle_qi"), ("戊", "residual_qi")],
    "酉": [("辛", "main_qi")],
    "戌": [("戊", "main_qi"), ("辛", "middle_qi"), ("丁", "residual_qi")],
    "亥": [("壬", "main_qi"), ("甲", "middle_qi")],
}

# Weight multipliers for hidden stems in element counting
HIDDEN_STEM_WEIGHTS: dict[str, float] = {
    "main_qi": 1.0,
    "middle_qi": 0.5,
    "residual_qi": 0.3,
}

# ---------------------------------------------------------------------------
# Branch Interactions (冲合害刑破)
# ---------------------------------------------------------------------------

# Six Clashes (六冲) — branch pairs that clash
SIX_CLASHES: frozenset[frozenset[str]] = frozenset({
    frozenset({"子", "午"}), frozenset({"丑", "未"}),
    frozenset({"寅", "申"}), frozenset({"卯", "酉"}),
    frozenset({"辰", "戌"}), frozenset({"巳", "亥"}),
})

# Six Combinations (六合) — branch pairs that combine into an element
SIX_COMBINATIONS: dict[frozenset[str], str] = {
    frozenset({"子", "丑"}): "earth",
    frozenset({"寅", "亥"}): "wood",
    frozenset({"卯", "戌"}): "fire",
    frozenset({"辰", "酉"}): "metal",
    frozenset({"巳", "申"}): "water",
    frozenset({"午", "未"}): "fire",
}

# Six Harms (六害) — branch pairs that harm
SIX_HARMS: frozenset[frozenset[str]] = frozenset({
    frozenset({"子", "未"}), frozenset({"丑", "午"}),
    frozenset({"寅", "巳"}), frozenset({"卯", "辰"}),
    frozenset({"申", "亥"}), frozenset({"酉", "戌"}),
})

# Punishments (刑) — grouped patterns
PUNISHMENT_GROUPS: list[tuple[str, ...]] = [
    ("寅", "巳", "申"),  # 无恩之刑
    ("丑", "未", "戌"),  # 持势之刑
    ("子", "卯"),         # 无礼之刑
]
SELF_PUNISHMENTS: frozenset[str] = frozenset({"辰", "午", "酉", "亥"})

# Six Destructions (六破)
SIX_DESTRUCTIONS: frozenset[frozenset[str]] = frozenset({
    frozenset({"子", "酉"}), frozenset({"丑", "辰"}),
    frozenset({"寅", "亥"}), frozenset({"卯", "午"}),
    frozenset({"巳", "申"}), frozenset({"未", "戌"}),
})

# ---------------------------------------------------------------------------
# Seasonal Strength (旺相休囚死)
# ---------------------------------------------------------------------------

# Map branch to its "season element" (the dominant element of that month)
BRANCH_TO_SEASON_ELEMENT: dict[str, str] = {
    "寅": "wood", "卯": "wood",
    "巳": "fire", "午": "fire",
    "申": "metal", "酉": "metal",
    "亥": "water", "子": "water",
    # Earth months (transitional)
    "辰": "earth", "未": "earth", "戌": "earth", "丑": "earth",
}

BRANCH_TO_SEASON_NAME: dict[str, str] = {
    "寅": "spring", "卯": "spring",
    "巳": "summer", "午": "summer",
    "申": "autumn", "酉": "autumn",
    "亥": "winter", "子": "winter",
    "辰": "late_spring", "未": "late_summer",
    "戌": "late_autumn", "丑": "late_winter",
}

# Strength order relative to the seasonal element:
# seasonal_el = prosperous, generated_by_seasonal = strong,
# generates_seasonal = resting, controlled_by_seasonal = imprisoned,
# controls_seasonal = dead
STRENGTH_LABELS = ("prosperous", "strong", "resting", "imprisoned", "dead")
STRENGTH_SCORES: dict[str, float] = {
    "prosperous": 1.0,
    "strong": 0.8,
    "resting": 0.5,
    "imprisoned": 0.3,
    "dead": 0.1,
}


# ---------------------------------------------------------------------------
# Solar terms for luck pillar calculation
# ---------------------------------------------------------------------------

# The 12 solar terms that mark month boundaries (节)
MONTH_BOUNDARY_TERMS = (
    "立春", "惊蛰", "清明", "立夏", "芒种", "小暑",
    "立秋", "白露", "寒露", "立冬", "大雪", "小寒",
)


# ---------------------------------------------------------------------------
# Pydantic Models
# ---------------------------------------------------------------------------

class HiddenStem(BaseModel):
    stem: str
    element: str
    strength: str  # "main_qi" | "middle_qi" | "residual_qi"


class TenGod(BaseModel):
    stem: str
    god: str        # Chinese name
    english: str    # English name
    pillar: str     # "year" | "month" | "day" | "hour"
    position: str   # "stem" | "hidden_main" | "hidden_middle" | "hidden_residual"


class Interaction(BaseModel):
    type: str                   # "clash" | "combination" | "harm" | "punishment" | "destruction"
    between: list[str]          # e.g. ["子", "午"]
    pillars: list[str]          # e.g. ["year", "day"]
    result_element: str | None = None  # for combinations
    description: str = ""


class SeasonalStrength(BaseModel):
    day_master_element: str
    month_branch: str
    season: str
    strength: str   # "prosperous" | "strong" | "resting" | "imprisoned" | "dead"
    score: float    # 0.0 - 1.0


class LuckPillar(BaseModel):
    index: int
    start_age: int
    end_age: int
    stem: str
    branch: str
    stem_element: str
    branch_element: str
    hidden_stems: list[HiddenStem]
    start_year: int
    end_year: int


class AnnualPillar(BaseModel):
    year: int
    stem: str
    branch: str
    stem_element: str
    branch_element: str
    interactions_with_chart: list[Interaction]
    luck_pillar_index: int  # which luck pillar is active


class FullBaziAnalysis(BaseModel):
    """Complete deterministic BaZi analysis."""
    pillars: dict[str, Any]
    hidden_stems: dict[str, list[HiddenStem]]
    ten_gods: list[TenGod]
    interactions: list[Interaction]
    seasonal_strength: SeasonalStrength
    luck_pillars: list[LuckPillar]
    annual_pillars: list[AnnualPillar]
    enhanced_element_counts: dict[str, float]
    element_by_source: dict[str, dict[str, float]]
    harmony_score: float = Field(description="0-100 score based on interaction balance")


# ---------------------------------------------------------------------------
# Computation functions
# ---------------------------------------------------------------------------

def compute_hidden_stems(branch: str) -> list[HiddenStem]:
    """Return hidden stems for an earthly branch."""
    entries = HIDDEN_STEMS_TABLE.get(branch, [])
    return [
        HiddenStem(stem=stem, element=STEM_TO_ELEMENT[stem], strength=strength)
        for stem, strength in entries
    ]


def compute_all_hidden_stems(chart: dict[str, Any]) -> dict[str, list[HiddenStem]]:
    """Return hidden stems for all pillars in the chart."""
    result: dict[str, list[HiddenStem]] = {}
    for pillar_name in ("year", "month", "day", "hour"):
        pillar_data = chart.get(pillar_name)
        if pillar_data is None:
            continue
        branch = pillar_data["branch"] if isinstance(pillar_data, dict) else pillar_data.branch
        result[pillar_name] = compute_hidden_stems(branch)
    return result


def _classify_ten_god(day_master_element: str, day_master_stem: str, target_stem: str) -> tuple[str, str]:
    """Classify a stem's relationship to the day master. Returns (chinese_name, english_name)."""
    target_element = STEM_TO_ELEMENT[target_stem]
    same_polarity = (day_master_stem in YANG_STEMS) == (target_stem in YANG_STEMS)

    if target_element == day_master_element:
        return ("比肩", "Companion") if same_polarity else ("劫财", "Rob Wealth")
    elif GENERATES.get(day_master_element) == target_element:
        # Day master generates target → output (food/injury)
        return ("食神", "Eating God") if same_polarity else ("伤官", "Hurting Officer")
    elif GENERATES.get(target_element) == day_master_element:
        # Target generates day master → resource (seal/owl)
        return ("偏印", "Indirect Seal") if same_polarity else ("正印", "Direct Seal")
    elif CONTROLS.get(day_master_element) == target_element:
        # Day master controls target → wealth
        return ("偏财", "Indirect Wealth") if same_polarity else ("正财", "Direct Wealth")
    elif CONTROLS.get(target_element) == day_master_element:
        # Target controls day master → power (officer/killer)
        return ("七杀", "Seven Killings") if same_polarity else ("正官", "Direct Officer")

    return ("未知", "Unknown")


def compute_ten_gods(
    day_master_stem: str,
    chart: dict[str, Any],
    hidden_stems: dict[str, list[HiddenStem]],
) -> list[TenGod]:
    """Classify every stem (surface + hidden) relative to day master."""
    day_master_element = STEM_TO_ELEMENT[day_master_stem]
    results: list[TenGod] = []

    for pillar_name in ("year", "month", "day", "hour"):
        pillar_data = chart.get(pillar_name)
        if pillar_data is None:
            continue
        stem = pillar_data["stem"] if isinstance(pillar_data, dict) else pillar_data.stem

        # Surface stem (skip day master itself — it's "self")
        if pillar_name != "day":
            god_cn, god_en = _classify_ten_god(day_master_element, day_master_stem, stem)
            results.append(TenGod(
                stem=stem, god=god_cn, english=god_en,
                pillar=pillar_name, position="stem",
            ))

        # Hidden stems in this pillar's branch
        position_map = {"main_qi": "hidden_main", "middle_qi": "hidden_middle", "residual_qi": "hidden_residual"}
        for hs in hidden_stems.get(pillar_name, []):
            god_cn, god_en = _classify_ten_god(day_master_element, day_master_stem, hs.stem)
            results.append(TenGod(
                stem=hs.stem, god=god_cn, english=god_en,
                pillar=pillar_name, position=position_map[hs.strength],
            ))

    return results


def _get_branch(chart: dict[str, Any], pillar_name: str) -> str | None:
    """Extract branch character from chart pillar."""
    p = chart.get(pillar_name)
    if p is None:
        return None
    return p["branch"] if isinstance(p, dict) else p.branch


def compute_interactions(chart: dict[str, Any]) -> list[Interaction]:
    """Check all branch pairs for clashes, combinations, harms, punishments, destructions."""
    pillar_names = ["year", "month", "day", "hour"]
    branches: list[tuple[str, str]] = []  # (pillar_name, branch)
    for name in pillar_names:
        b = _get_branch(chart, name)
        if b is not None:
            branches.append((name, b))

    interactions: list[Interaction] = []

    # Check all pairs
    for i in range(len(branches)):
        for j in range(i + 1, len(branches)):
            p1_name, b1 = branches[i]
            p2_name, b2 = branches[j]
            pair = frozenset({b1, b2})

            if pair in SIX_CLASHES:
                interactions.append(Interaction(
                    type="clash",
                    between=[b1, b2],
                    pillars=[p1_name, p2_name],
                    description=f"{b1}{b2}冲 — {BRANCH_TO_ELEMENT[b1]} vs {BRANCH_TO_ELEMENT[b2]}",
                ))

            if pair in SIX_COMBINATIONS:
                result_el = SIX_COMBINATIONS[pair]
                interactions.append(Interaction(
                    type="combination",
                    between=[b1, b2],
                    pillars=[p1_name, p2_name],
                    result_element=result_el,
                    description=f"{b1}{b2}合 → {result_el}",
                ))

            if pair in SIX_HARMS:
                interactions.append(Interaction(
                    type="harm",
                    between=[b1, b2],
                    pillars=[p1_name, p2_name],
                    description=f"{b1}{b2}害",
                ))

            if pair in SIX_DESTRUCTIONS:
                interactions.append(Interaction(
                    type="destruction",
                    between=[b1, b2],
                    pillars=[p1_name, p2_name],
                    description=f"{b1}{b2}破",
                ))

    # Check punishments (can involve 2 or 3 branches)
    branch_set = {b for _, b in branches}
    branch_to_pillar = {b: name for name, b in branches}

    for group in PUNISHMENT_GROUPS:
        present = [b for b in group if b in branch_set]
        if len(present) >= 2:
            interactions.append(Interaction(
                type="punishment",
                between=present,
                pillars=[branch_to_pillar[b] for b in present],
                description=f"{''.join(present)}刑",
            ))

    # Self-punishments
    from collections import Counter
    branch_counts = Counter(b for _, b in branches)
    for branch, count in branch_counts.items():
        if branch in SELF_PUNISHMENTS and count >= 2:
            pillars_with = [name for name, b in branches if b == branch]
            interactions.append(Interaction(
                type="punishment",
                between=[branch, branch],
                pillars=pillars_with,
                description=f"{branch}{branch}自刑",
            ))

    return interactions


def compute_seasonal_strength(
    day_master_element: str,
    month_branch: str,
) -> SeasonalStrength:
    """Determine how strong the day master is in the birth month (旺相休囚死)."""
    season_element = BRANCH_TO_SEASON_ELEMENT[month_branch]
    season_name = BRANCH_TO_SEASON_NAME[month_branch]

    # Build strength mapping for this season
    strength_map: dict[str, str] = {
        season_element: "prosperous",
        GENERATES[season_element]: "strong",
        GENERATED_BY[season_element]: "resting",
        CONTROLLED_BY[season_element]: "imprisoned",
        CONTROLS[season_element]: "dead",
    }

    strength = strength_map.get(day_master_element, "resting")
    score = STRENGTH_SCORES[strength]

    return SeasonalStrength(
        day_master_element=day_master_element,
        month_branch=month_branch,
        season=season_name,
        strength=strength,
        score=score,
    )


def _stem_index(stem: str) -> int:
    return HEAVENLY_STEMS.index(stem)


def _branch_index(branch: str) -> int:
    return EARTHLY_BRANCHES.index(branch)


def _stem_at(index: int) -> str:
    return HEAVENLY_STEMS[index % 10]


def _branch_at(index: int) -> str:
    return EARTHLY_BRANCHES[index % 12]


def compute_luck_pillars(
    chart: dict[str, Any],
    birth_iso: str,
    timezone: str,
    gender: str,
    num_pillars: int = 8,
) -> list[LuckPillar]:
    """Compute 大运 (luck pillars / 10-year cycles).

    Direction: male+yang or female+yin = forward; otherwise backward.
    Start age: days to nearest relevant solar term / 3.
    """
    year_stem = chart["year"]["stem"] if isinstance(chart["year"], dict) else chart["year"].stem
    month_stem = chart["month"]["stem"] if isinstance(chart["month"], dict) else chart["month"].stem
    month_branch = chart["month"]["branch"] if isinstance(chart["month"], dict) else chart["month"].branch

    is_yang_year = year_stem in YANG_STEMS
    is_male = gender.lower() in ("male", "m", "男")

    # Forward if (male+yang) or (female+yin)
    forward = (is_male and is_yang_year) or (not is_male and not is_yang_year)

    # Calculate start age using solar terms
    local_dt = _normalize_dt(birth_iso, timezone)
    birth_year = local_dt.year
    lunar = cnlunar.Lunar(local_dt, godType="8char")
    solar_terms = lunar.thisYearSolarTermsDic

    # Find the relevant solar term (the month boundary term)
    # Month boundary terms are the "节" (not "气")
    birth_day_of_year = local_dt.timetuple().tm_yday

    term_dates: list[tuple[str, int]] = []
    for term_name in MONTH_BOUNDARY_TERMS:
        if term_name in solar_terms:
            m, d = solar_terms[term_name]
            term_dt = datetime(birth_year, m, d)
            term_doy = term_dt.timetuple().tm_yday
            term_dates.append((term_name, term_doy))

    # Also check next year's 小寒 and 立春 for late-year births
    try:
        next_year_lunar = cnlunar.Lunar(datetime(birth_year + 1, 2, 1), godType="8char")
        next_terms = next_year_lunar.thisYearSolarTermsDic
        for term_name in ("小寒", "立春"):
            if term_name in next_terms:
                m, d = next_terms[term_name]
                term_dt = datetime(birth_year + 1, m, d)
                delta = (term_dt - datetime(birth_year, 1, 1)).days
                term_dates.append((term_name, delta))
    except Exception:
        pass

    term_dates.sort(key=lambda x: x[1])

    if forward:
        # Find next solar term after birth
        future_terms = [(n, d) for n, d in term_dates if d > birth_day_of_year]
        days_to_term = (future_terms[0][1] - birth_day_of_year) if future_terms else 30
    else:
        # Find previous solar term before birth
        past_terms = [(n, d) for n, d in term_dates if d <= birth_day_of_year]
        days_to_term = (birth_day_of_year - past_terms[-1][1]) if past_terms else 30

    # 3 days ≈ 1 year of life; start age = days / 3, rounded
    start_age = max(1, round(days_to_term / 3))

    # Build luck pillars by stepping through the sexagenary cycle
    m_stem_idx = _stem_index(month_stem)
    m_branch_idx = _branch_index(month_branch)
    direction = 1 if forward else -1

    pillars: list[LuckPillar] = []
    for i in range(num_pillars):
        offset = (i + 1) * direction
        stem = _stem_at(m_stem_idx + offset)
        branch = _branch_at(m_branch_idx + offset)
        age_start = start_age + i * 10
        age_end = age_start + 9
        year_start = birth_year + age_start
        year_end = birth_year + age_end

        pillars.append(LuckPillar(
            index=i,
            start_age=age_start,
            end_age=age_end,
            stem=stem,
            branch=branch,
            stem_element=STEM_TO_ELEMENT[stem],
            branch_element=BRANCH_TO_ELEMENT[branch],
            hidden_stems=compute_hidden_stems(branch),
            start_year=year_start,
            end_year=year_end,
        ))

    return pillars


def _year_stem_branch(year: int) -> tuple[str, str]:
    """Compute the stem and branch for any year using the sexagenary cycle."""
    stem = _stem_at(year - 4)
    branch = _branch_at(year - 4)
    return stem, branch


def _check_annual_interactions(
    annual_branch: str,
    chart: dict[str, Any],
) -> list[Interaction]:
    """Check interactions between an annual branch and all natal chart branches."""
    interactions: list[Interaction] = []
    for pillar_name in ("year", "month", "day", "hour"):
        natal_branch = _get_branch(chart, pillar_name)
        if natal_branch is None:
            continue
        pair = frozenset({annual_branch, natal_branch})

        if pair in SIX_CLASHES:
            interactions.append(Interaction(
                type="clash",
                between=[annual_branch, natal_branch],
                pillars=["annual", pillar_name],
                description=f"流年{annual_branch}冲{pillar_name}{natal_branch}",
            ))
        if pair in SIX_COMBINATIONS:
            interactions.append(Interaction(
                type="combination",
                between=[annual_branch, natal_branch],
                pillars=["annual", pillar_name],
                result_element=SIX_COMBINATIONS[pair],
                description=f"流年{annual_branch}合{pillar_name}{natal_branch} → {SIX_COMBINATIONS[pair]}",
            ))
        if pair in SIX_HARMS:
            interactions.append(Interaction(
                type="harm",
                between=[annual_branch, natal_branch],
                pillars=["annual", pillar_name],
                description=f"流年{annual_branch}害{pillar_name}{natal_branch}",
            ))

    return interactions


def compute_annual_pillars(
    start_year: int,
    end_year: int,
    chart: dict[str, Any],
    luck_pillars: list[LuckPillar],
) -> list[AnnualPillar]:
    """Compute 流年 (annual pillars) for a year range with natal chart interactions."""
    results: list[AnnualPillar] = []
    for year in range(start_year, end_year + 1):
        stem, branch = _year_stem_branch(year)
        interactions = _check_annual_interactions(branch, chart)

        # Find active luck pillar
        lp_index = -1
        for lp in luck_pillars:
            if lp.start_year <= year <= lp.end_year:
                lp_index = lp.index
                break

        results.append(AnnualPillar(
            year=year,
            stem=stem,
            branch=branch,
            stem_element=STEM_TO_ELEMENT[stem],
            branch_element=BRANCH_TO_ELEMENT[branch],
            interactions_with_chart=interactions,
            luck_pillar_index=lp_index,
        ))

    return results


def compute_enhanced_elements(
    chart: dict[str, Any],
    hidden_stems: dict[str, list[HiddenStem]],
) -> tuple[dict[str, float], dict[str, dict[str, float]]]:
    """Compute element counts including hidden stems with weights.

    Returns (total_counts, by_source) where by_source maps pillar -> element -> weight.
    """
    total: dict[str, float] = {e: 0.0 for e in FIVE_ELEMENTS}
    by_source: dict[str, dict[str, float]] = {}

    for pillar_name in ("year", "month", "day", "hour"):
        pillar_data = chart.get(pillar_name)
        if pillar_data is None:
            continue

        source: dict[str, float] = {e: 0.0 for e in FIVE_ELEMENTS}

        # Surface stem (weight 1.0)
        stem_el = pillar_data["stem_element"] if isinstance(pillar_data, dict) else pillar_data.stem_element
        source[stem_el] += 1.0
        total[stem_el] += 1.0

        # Hidden stems in the branch (weighted)
        for hs in hidden_stems.get(pillar_name, []):
            weight = HIDDEN_STEM_WEIGHTS[hs.strength]
            source[hs.element] += weight
            total[hs.element] += weight

        by_source[pillar_name] = source

    return total, by_source


def compute_harmony_score(interactions: list[Interaction]) -> float:
    """Compute a 0-100 harmony score based on interaction balance.

    Combinations add to harmony, clashes/harms/punishments subtract.
    """
    score = 70.0  # baseline
    for ix in interactions:
        if ix.type == "combination":
            score += 8.0
        elif ix.type == "clash":
            score -= 12.0
        elif ix.type == "harm":
            score -= 6.0
        elif ix.type == "punishment":
            score -= 8.0
        elif ix.type == "destruction":
            score -= 4.0
    return max(0.0, min(100.0, round(score, 1)))


# ---------------------------------------------------------------------------
# Master function
# ---------------------------------------------------------------------------

def compute_full_analysis(
    birth_iso: str,
    timezone: str = "UTC",
    gender: str = "unknown",
    birth_time_unknown: bool = False,
    year_range: tuple[int, int] | None = None,
) -> FullBaziAnalysis:
    """Run complete deterministic BaZi analysis. No LLM calls."""
    # 1. Base chart (existing)
    chart = compute_bazi_chart(birth_iso, timezone=timezone, birth_time_unknown=birth_time_unknown)

    # 2. Hidden stems
    hidden = compute_all_hidden_stems(chart)

    # 3. Ten Gods
    day_master_stem = chart["day_master"]
    ten_gods = compute_ten_gods(day_master_stem, chart, hidden)

    # 4. Branch interactions
    interactions = compute_interactions(chart)

    # 5. Seasonal strength
    month_branch = chart["month"]["branch"] if isinstance(chart["month"], dict) else chart["month"].branch
    seasonal = compute_seasonal_strength(chart["day_master_element"], month_branch)

    # 6. Enhanced element counts
    enhanced_counts, element_by_source = compute_enhanced_elements(chart, hidden)

    # 7. Luck pillars (need gender)
    if gender.lower() not in ("unknown", ""):
        luck_pillars = compute_luck_pillars(chart, birth_iso, timezone, gender)
    else:
        luck_pillars = []

    # 8. Annual pillars
    local_dt = _normalize_dt(birth_iso, timezone)
    birth_year = local_dt.year
    if year_range is None:
        # Default: from birth year to 30 years from now
        current_year = datetime.now().year
        year_range = (birth_year, current_year + 10)
    annual_pillars = compute_annual_pillars(year_range[0], year_range[1], chart, luck_pillars)

    # 9. Harmony score
    harmony = compute_harmony_score(interactions)

    return FullBaziAnalysis(
        pillars=chart,
        hidden_stems=hidden,
        ten_gods=ten_gods,
        interactions=interactions,
        seasonal_strength=seasonal,
        luck_pillars=luck_pillars,
        annual_pillars=annual_pillars,
        enhanced_element_counts=enhanced_counts,
        element_by_source=element_by_source,
        harmony_score=harmony,
    )
