"""Birth-Time Uncertainty Simulator.

When a user does not know their birth time, the initial reading defaults to
noon. That is a *single* hypothesis — some readings are robust to that choice,
others flip entirely. This module enumerates the 12 canonical Earthly
Branches (each covering a 2-hour window) and re-runs the deterministic BaZi
foundation for every one. Callers then see:

- which patterns hold across all candidate hours (high-confidence claims),
- which flip by branch (predictions to treat as provisional),
- the specific hour(s) most likely to match lived-experience hooks the user
  can later corroborate (peak age, life theme, etc).

No LLM calls are made — the value of the simulator is stability analysis on
the *chart itself*, not a dozen narrative rewrites. The chart computation
path is imported from ``calendar_tool`` + ``bazi_engine`` and re-used.
"""

from __future__ import annotations

import logging
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)


# The 12 Earthly Branches and the representative hour used to produce a
# chart whose hour-pillar lands in that branch's 2-hour window.
#
# IMPORTANT: BaZi day boundary is at 23:00 (cnlunar semantics), so if we
# picked 23:00 for 子 it would roll onto the NEXT BaZi day and flip the
# day-pillar. That would make the simulator measure both "hour uncertainty"
# AND a silent day-pillar shift. We therefore use EARLY 子 (00:30) on the
# same civil date, which keeps all 12 hypotheses on the same BaZi day as
# noon — a pure hour-uncertainty comparison, as advertised.
#
# The user's real birth could theoretically be in LATE 子 (23:00-23:59) of
# the recorded date, producing the *next* BaZi day. We intentionally do not
# model that here; it's a separate "was it before or after midnight?"
# question the user already answered by writing down the civil date.
EARTHLY_BRANCHES: list[dict[str, str]] = [
    {"branch": "子", "rep_hour": "00:30", "window": "23:00–01:00 (early)"},
    {"branch": "丑", "rep_hour": "01:30", "window": "01:00–03:00"},
    {"branch": "寅", "rep_hour": "03:30", "window": "03:00–05:00"},
    {"branch": "卯", "rep_hour": "05:30", "window": "05:00–07:00"},
    {"branch": "辰", "rep_hour": "07:30", "window": "07:00–09:00"},
    {"branch": "巳", "rep_hour": "09:30", "window": "09:00–11:00"},
    {"branch": "午", "rep_hour": "11:30", "window": "11:00–13:00"},
    {"branch": "未", "rep_hour": "13:30", "window": "13:00–15:00"},
    {"branch": "申", "rep_hour": "15:30", "window": "15:00–17:00"},
    {"branch": "酉", "rep_hour": "17:30", "window": "17:00–19:00"},
    {"branch": "戌", "rep_hour": "19:30", "window": "19:00–21:00"},
    {"branch": "亥", "rep_hour": "21:30", "window": "21:00–23:00"},
]


@dataclass(slots=True)
class BranchResult:
    branch: str
    rep_hour: str
    window: str
    hour_pillar_stem: str | None
    hour_pillar_branch: str | None
    day_master: str  # e.g. "乙 (wood)" — same across 12 by construction, but surface for honesty
    dominant_element: str
    weakest_element: str
    enhanced_element_counts: dict[str, float]
    seasonal_strength: str
    seasonal_score: float
    harmony_score: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "branch": self.branch,
            "repHour": self.rep_hour,
            "window": self.window,
            "hourPillarStem": self.hour_pillar_stem,
            "hourPillarBranch": self.hour_pillar_branch,
            "dayMaster": self.day_master,
            "dominantElement": self.dominant_element,
            "weakestElement": self.weakest_element,
            "enhancedElementCounts": self.enhanced_element_counts,
            "seasonalStrength": self.seasonal_strength,
            "seasonalScore": self.seasonal_score,
            "harmonyScore": self.harmony_score,
        }


@dataclass(slots=True)
class StabilityReport:
    """Aggregate stability across the 12 simulated charts.

    Each field records (a) the modal value across branches, (b) how many of
    the 12 charts agreed, and (c) the full distribution so the UI can draw
    a stability bar. Claims that score 11/12 or 12/12 can be shown with
    confidence; anything <= 6/12 should be marked "uncertain — birth time
    would sharpen this".
    """

    day_master: dict[str, Any]
    dominant_element: dict[str, Any]
    seasonal_strength: dict[str, Any]
    hour_branch_diversity: int  # always 12 by construction; surfaced for UX copy

    def to_dict(self) -> dict[str, Any]:
        return {
            "dayMaster": self.day_master,
            "dominantElement": self.dominant_element,
            "seasonalStrength": self.seasonal_strength,
            "hourBranchDiversity": self.hour_branch_diversity,
        }


def _modal(values: list[str]) -> dict[str, Any]:
    counts = Counter(values)
    modal_value, modal_count = counts.most_common(1)[0]
    return {
        "value": modal_value,
        "count": modal_count,
        "total": len(values),
        "distribution": dict(counts),
    }


def _replace_time(birth_iso: str, new_hhmm: str) -> str:
    """Swap the time portion of an ISO-8601 birth string.

    If the caller provided something we cannot parse (no T, malformed), we
    fall back to concatenation which mirrors the upstream route's default.
    """
    try:
        if "T" in birth_iso:
            date_part = birth_iso.split("T", 1)[0]
        else:
            date_part = birth_iso[:10]
        return f"{date_part}T{new_hhmm}:00"
    except Exception:
        return f"{birth_iso}T{new_hhmm}:00"


def _simulate_one(
    birth_iso: str,
    timezone_name: str,
    branch_entry: dict[str, str],
) -> BranchResult | None:
    """Run the deterministic foundation for a single branch hypothesis.

    Returns None if the chart computation raises — we log and skip rather
    than aborting the whole simulation over one bad branch.
    """
    try:
        from .calendar_tool import compute_bazi_chart
        from .bazi_engine import (
            compute_all_hidden_stems,
            compute_enhanced_elements,
            compute_seasonal_strength,
            compute_interactions,
            compute_harmony_score,
        )
    except ImportError:  # pragma: no cover — module-relative vs top-level
        from calendar_tool import compute_bazi_chart  # type: ignore[no-redef]
        from bazi_engine import (  # type: ignore[no-redef]
            compute_all_hidden_stems,
            compute_enhanced_elements,
            compute_seasonal_strength,
            compute_interactions,
            compute_harmony_score,
        )

    try:
        iso = _replace_time(birth_iso, branch_entry["rep_hour"])
        chart = compute_bazi_chart(iso, timezone=timezone_name, birth_time_unknown=False)
        hidden = compute_all_hidden_stems(chart)
        enhanced_counts, _ = compute_enhanced_elements(chart, hidden)
        dominant = max(enhanced_counts, key=enhanced_counts.get)  # type: ignore[arg-type]
        weakest = min(enhanced_counts, key=enhanced_counts.get)  # type: ignore[arg-type]
        month_branch = (
            chart["month"]["branch"]
            if isinstance(chart["month"], dict)
            else chart["month"].branch
        )
        seasonal = compute_seasonal_strength(chart["day_master_element"], month_branch)
        interactions = compute_interactions(chart)
        harmony = compute_harmony_score(interactions)
        hour = chart.get("hour")
        return BranchResult(
            branch=branch_entry["branch"],
            rep_hour=branch_entry["rep_hour"],
            window=branch_entry["window"],
            hour_pillar_stem=(hour.get("stem") if isinstance(hour, dict) else None),
            hour_pillar_branch=(hour.get("branch") if isinstance(hour, dict) else None),
            day_master=f"{chart['day_master']} ({chart['day_master_element']})",
            dominant_element=dominant,
            weakest_element=weakest,
            enhanced_element_counts={k: round(v, 2) for k, v in enhanced_counts.items()},
            seasonal_strength=seasonal.strength,
            seasonal_score=round(float(seasonal.score), 2),
            harmony_score=round(float(harmony), 2),
        )
    except Exception as exc:
        logger.warning(
            "[FORTUNE] simulator skipped branch=%s: %s",
            branch_entry.get("branch"),
            exc,
        )
        return None


def simulate_birth_time(birth_iso: str, timezone_name: str) -> dict[str, Any]:
    """Run the foundation for all 12 Earthly Branch hour hypotheses.

    One pass over EARTHLY_BRANCHES. If a branch compute raises we record it
    in ``failedBranches`` but do NOT fall back to a second loop — aggregates
    use the same surviving set that the UI renders, so totals cannot drift.

    Returns:
    {
        "branches":          [ ...BranchResults ],         # one per success
        "stability":         StabilityReport | None,       # over survivors
        "expectedBranches":  12,
        "completedBranches": n,
        "failedBranches":    [...branch_names],
        "partial":           bool,
    }

    Hard-fails (raises) only when *every* branch failed, which means the
    input was unparseable and a partial answer would mislead the user.
    """
    results: list[BranchResult] = []
    failed: list[str] = []
    for entry in EARTHLY_BRANCHES:
        r = _simulate_one(birth_iso, timezone_name, entry)
        if r is None:
            failed.append(entry["branch"])
        else:
            results.append(r)

    if not results:
        return {
            "branches": [],
            "stability": None,
            "expectedBranches": len(EARTHLY_BRANCHES),
            "completedBranches": 0,
            "failedBranches": failed,
            "partial": True,
            "error": "All 12 branch simulations failed; see server logs.",
        }

    # Aggregate from the SAME result set the caller will render. No second
    # pass, no opportunity for denominator disagreement.
    stability = StabilityReport(
        day_master=_modal([r.day_master for r in results]),
        dominant_element=_modal([r.dominant_element for r in results]),
        seasonal_strength=_modal([r.seasonal_strength for r in results]),
        hour_branch_diversity=len({r.hour_pillar_branch for r in results if r.hour_pillar_branch}),
    )

    return {
        "branches": [r.to_dict() for r in results],
        "stability": stability.to_dict(),
        "expectedBranches": len(EARTHLY_BRANCHES),
        "completedBranches": len(results),
        "failedBranches": failed,
        "partial": len(results) < len(EARTHLY_BRANCHES),
    }
