"""Process-local LRU caches for deterministic foundation helpers.

PR3 of the latency refactor — these caches are meant to remove the
per-request cost of recomputing chart-derived data that depends ONLY on
inputs we already have at request time. They never cache anything that
contains mutable runtime state (e.g. the run-scoped trace view that
``run_foundation`` returns) — caching that would leak trace steps across
sessions.

What lives here:

- ``compute_day_chart_cached(date_iso, timezone)`` — wraps
  ``compute_bazi_chart`` for noon charts of arbitrary dates. Hot path is
  the occasion candidate-day generator at ``agents._build_occasion_window``,
  which calls it once per day in a 30-60 day window. With the cache, a
  user re-running the same window (or two users with the same window in
  the same timezone) shares the work.
- ``score_candidate_day(...)`` — deterministic chart-compatibility score
  used by the occasion deterministic prefilter. Pure-function so the LRU
  is safe.

Cache sizes are tuned for the foreground request cardinality:
- 60-day window × 4 timezones × 2 daily refreshes = ~500 unique day
  charts is the realistic ceiling. ``maxsize=512`` covers it without
  burning memory.
- Score cache rides on the same cardinality plus per-querent variation,
  so ``maxsize=2048`` is generous.

Cache hits are silent — if you need observability, add a counter via
``functools.lru_cache.cache_info`` on each function.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any

try:
    from .bazi_engine import (
        BRANCH_TO_ELEMENT,
        CONTROLLED_BY,
        CONTROLS,
        GENERATED_BY,
        GENERATES,
        SIX_CLASHES,
        SIX_COMBINATIONS,
        SIX_DESTRUCTIONS,
        SIX_HARMS,
        STEM_TO_ELEMENT,
        compute_bazi_chart,
    )
except ImportError:  # pragma: no cover - non-package import path
    from bazi_engine import (  # type: ignore[no-redef]
        BRANCH_TO_ELEMENT,
        CONTROLLED_BY,
        CONTROLS,
        GENERATED_BY,
        GENERATES,
        SIX_CLASHES,
        SIX_COMBINATIONS,
        SIX_DESTRUCTIONS,
        SIX_HARMS,
        STEM_TO_ELEMENT,
        compute_bazi_chart,
    )


@lru_cache(maxsize=512)
def _compute_noon_chart(date_iso: str, timezone: str) -> dict[str, Any]:
    """LRU-cached wrapper around ``compute_bazi_chart`` at noon for a date.

    Keyed on ``(date_iso, timezone)`` so two requests with the same window
    share work. Returns the **chart dict** unchanged from
    ``compute_bazi_chart``; callers are expected NOT to mutate it.
    """
    return compute_bazi_chart(
        f"{date_iso}T12:00:00",
        timezone=timezone,
        birth_time_unknown=True,
    )


def compute_day_chart_cached(date_iso: str, timezone: str) -> dict[str, Any]:
    """Public wrapper — see ``_compute_noon_chart``. Returns a fresh dict copy.

    Returning a fresh top-level copy guards against accidental mutation by
    callers that add transient fields. The hot inner objects (``year``,
    ``month``, ``day``, ``hour``) are still shared dict refs; the
    occasion prefilter only reads them.
    """
    return dict(_compute_noon_chart(date_iso, timezone))


# ---------------------------------------------------------------------------
# Occasion candidate-day scoring
# ---------------------------------------------------------------------------

# Element-on-day-master interaction → score delta. The day's stem element
# vs the querent's day master element. Same > generates > generated_by
# (resource) > controlled_by > controls (drains/dominates).
_DM_INTERACTION_BASE: dict[str, float] = {
    "same": 12.0,         # peer days — confidence boost
    "generates": 18.0,    # day's element FEEDS day master (output star)
    "generated_by": 15.0, # day's element is FED BY day master (resource)
    "controlled_by": 8.0, # day master CONTROLS the day (wealth)
    "controls": -6.0,     # day's element CONTROLS day master (officer/pressure)
}


def _dm_interaction_kind(day_master_element: str, day_element: str) -> str:
    if day_master_element == day_element:
        return "same"
    if GENERATES.get(day_element) == day_master_element:
        return "generates"
    if GENERATES.get(day_master_element) == day_element:
        return "generated_by"
    if CONTROLS.get(day_master_element) == day_element:
        return "controlled_by"
    if CONTROLS.get(day_element) == day_master_element:
        return "controls"
    return "neutral"


def _branch_pair_score(querent_branch: str, day_branch: str) -> float:
    """Score the interaction between the querent day-branch and a candidate.

    Each applicable interaction is **summed** rather than early-returned —
    real BaZi pairs can carry overlapping relationships. The canonical
    overlaps in the existing tables are:

    - 寅亥: 六合 (wood) AND 六破 → ``+18 + -8 = +10``
    - 巳申: 六合 (water) AND 六破 → ``+18 + -8 = +10``

    Treating them as purely +18 systematically over-ranked those days for
    寅 and 巳 day-branch querents (codex PR3 review §2). Same-branch
    self-presence is a mild +4 (familiarity / 比肩) standalone.
    """
    if querent_branch == day_branch:
        return 4.0

    pair = frozenset({querent_branch, day_branch})
    score = 0.0
    if pair in SIX_COMBINATIONS:
        score += 18.0
    if pair in SIX_CLASHES:
        score += -22.0
    if pair in SIX_HARMS:
        score += -10.0
    if pair in SIX_DESTRUCTIONS:
        score += -8.0
    return score


@lru_cache(maxsize=16384)
def score_candidate_day(
    day_stem: str,
    day_branch: str,
    querent_day_master_stem: str,
    querent_day_branch: str,
    favored_element: str | None,
    avoid_element: str | None,
) -> float:
    """Pure scoring function for the occasion deterministic prefilter.

    Inputs are all small primitive strings so the LRU cache stays cheap
    and shareable across querents who happen to need the same comparison.

    Score range is roughly **-40 … +50**. Higher is more auspicious for
    the occasion. Components:

    1. Day-master interaction (the day's stem element vs querent's day
       master): ``_DM_INTERACTION_BASE``.
    2. Branch pair interaction (querent's day branch vs candidate day
       branch): ``_branch_pair_score``.
    3. Favored-element bonus (+8): if ``favored_element`` is given and
       the day's stem OR branch element matches it (occasion-type-driven
       — e.g. weddings favour Fire/Earth, signing contracts favours
       Metal). The caller decides what counts as favored.
    4. Avoid-element penalty (-10) for the symmetric case.

    The scoring is deterministic and traceable — no randomness, no LLM —
    so the prefilter can run hundreds of comparisons cheaply and the LLM
    only sees a curated top-21 + coverage sample.
    """
    day_stem_element = STEM_TO_ELEMENT[day_stem]
    day_branch_element = BRANCH_TO_ELEMENT[day_branch]
    day_master_element = STEM_TO_ELEMENT[querent_day_master_stem]

    score: float = 0.0

    # 1. Day-master interaction.
    dm_kind = _dm_interaction_kind(day_master_element, day_stem_element)
    score += _DM_INTERACTION_BASE.get(dm_kind, 0.0)

    # 2. Branch pair interaction.
    score += _branch_pair_score(querent_day_branch, day_branch)

    # 3 + 4. Occasion-type favored / avoid element.
    if favored_element is not None:
        if day_stem_element == favored_element or day_branch_element == favored_element:
            score += 8.0
    if avoid_element is not None:
        if day_stem_element == avoid_element or day_branch_element == avoid_element:
            score -= 10.0

    return score


# Occasion-type → favored / avoid elements. Hand-tuned defaults — the LLM
# still has the final say, but these guide the prefilter so the curated
# top-21 includes plausible candidates rather than a random first-21.
_OCCASION_PREFERENCE: dict[str, tuple[str | None, str | None]] = {
    # Celebratory / relationship — fire warmth, earth grounding, metal sharp.
    "wedding": ("fire", "water"),
    "marriage": ("fire", "water"),
    "engagement": ("fire", "water"),
    "anniversary": ("earth", None),
    "birthday": ("earth", None),
    # Business / formal — metal cuts cleanly, earth roots a contract.
    "signing": ("metal", "wood"),
    "contract": ("metal", "wood"),
    "launch": ("fire", "water"),
    "groundbreaking": ("earth", "wood"),
    "moving": ("earth", "water"),
    "travel": ("water", "earth"),
    # Health / treatment — gentle wood, no harsh metal.
    "surgery": ("wood", "metal"),
    "treatment": ("wood", "metal"),
    # Default: no preference — pure interaction-based scoring.
    "general": (None, None),
    "default": (None, None),
}


def occasion_preferences(occasion_type: str | None) -> tuple[str | None, str | None]:
    """Look up favored/avoid elements for an occasion type. Lower-cased + fuzzy."""
    if not occasion_type:
        return (None, None)
    key = occasion_type.lower().strip()
    if key in _OCCASION_PREFERENCE:
        return _OCCASION_PREFERENCE[key]
    # Soft prefix match — "weddings" / "wedding_a" / "wedding ceremony" → wedding.
    for known, prefs in _OCCASION_PREFERENCE.items():
        if key.startswith(known) or known.startswith(key):
            return prefs
    return (None, None)


def cache_clear_all() -> None:
    """Drop every cache. Test-only escape hatch."""
    _compute_noon_chart.cache_clear()
    score_candidate_day.cache_clear()


def pillar_stem_branch(value: Any) -> tuple[str, str]:
    """Defensive parse: extract (stem, branch) from any of these shapes:

    - ``{"stem": "甲", "branch": "寅"}`` — the canonical run_foundation output
    - object with ``.stem`` and ``.branch`` attributes
    - ``{"raw": "甲寅"}`` — degraded shape used by some legacy fixtures
    - ``"甲寅"`` — bare CJK 2-char string (defensive fallback)

    Raises ``ValueError`` with a clear message on any other shape so the
    occasion prefilter logs explain a bad foundation rather than crashing
    the route handler with an opaque ``KeyError`` / ``AttributeError``.
    """
    if isinstance(value, dict):
        if "stem" in value and "branch" in value:
            return value["stem"], value["branch"]
        raw = value.get("raw")
        if isinstance(raw, str) and len(raw) >= 2:
            return raw[0], raw[1]
        raise ValueError(
            f"pillar dict missing 'stem'/'branch' or valid 'raw': {value!r}"
        )
    if isinstance(value, str):
        if len(value) >= 2:
            return value[0], value[1]
        raise ValueError(f"pillar string too short: {value!r}")
    stem = getattr(value, "stem", None)
    branch = getattr(value, "branch", None)
    if stem is not None and branch is not None:
        return stem, branch
    raise ValueError(
        f"pillar object missing .stem/.branch attributes: {type(value).__name__}"
    )
