"""Ming Engine agent pipeline: deterministic foundation plus live LLM stages."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any

from agents import Agent, ModelSettings, Runner, RunConfig
from openai.types.shared import Reasoning
from pydantic import BaseModel, Field

try:
    from .calendar_tool import compute_bazi_chart
    from .classics import retrieve_classical_references
    from .config import get_settings
    from .naming import canonical_function
    from .bazi_engine import (
        compute_full_analysis, FullBaziAnalysis,
        compute_all_hidden_stems, compute_ten_gods, compute_interactions,
        compute_seasonal_strength, compute_luck_pillars, compute_annual_pillars,
        compute_enhanced_elements, compute_harmony_score, compute_retrodictions,
    )
    from .trace_collector import TraceCollector
    from ._foundation_cache import (
        compute_day_chart_cached,
        occasion_preferences,
        pillar_stem_branch,
        score_candidate_day,
    )
except ImportError:
    from calendar_tool import compute_bazi_chart  # type: ignore[no-redef]
    from classics import retrieve_classical_references  # type: ignore[no-redef]
    from config import get_settings  # type: ignore[no-redef]
    from naming import canonical_function  # type: ignore[no-redef]
    from bazi_engine import (  # type: ignore[no-redef]
        compute_full_analysis, FullBaziAnalysis,
        compute_all_hidden_stems, compute_ten_gods, compute_interactions,
        compute_seasonal_strength, compute_luck_pillars, compute_annual_pillars,
        compute_enhanced_elements, compute_harmony_score, compute_retrodictions,
    )
    from trace_collector import TraceCollector  # type: ignore[no-redef]
    from _foundation_cache import (  # type: ignore[no-redef]
        compute_day_chart_cached,
        occasion_preferences,
        pillar_stem_branch,
        score_candidate_day,
    )


FOUNDATION_VERSION = 1
NARRATIVE_SCHEMA_VERSION = 1


# ---------------------------------------------------------------------------
# Run context
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class FortuneRunContext:
    fortune_id: str
    surface_id: str
    run_id: str | None = None
    question: str | None = None
    focus: str | None = None
    tone: str | None = None
    birth_iso: str = ""
    timezone: str = "UTC"
    birth_time_unknown: bool = False
    gender: str = "unknown"
    metadata: dict[str, Any] = field(default_factory=dict)


def _run_config(ctx: "FortuneRunContext") -> RunConfig:
    """Build RunConfig so TracingProcessor can route spans to the right row.

    OpenAI's hosted tracing exporter requires ``trace_id`` to start with
    ``trace_``; we prepend it here and strip it back to run_id in the
    GlassBoxTraceProcessor resolver. ``group_id`` must start with ``group_``
    for the same reason.
    """
    source_id = ctx.run_id or ctx.fortune_id
    return RunConfig(
        trace_id=f"trace_{source_id.replace('-', '')}" if source_id else None,
        group_id=f"group_{ctx.fortune_id.replace('-', '')}" if ctx.fortune_id else None,
        trace_metadata={
            # OpenAI hosted tracing requires all metadata values to be strings.
            "run_id": ctx.run_id or "",
            "fortune_id": ctx.fortune_id or "",
            "focus": ctx.focus or "",
            "tone": ctx.tone or "",
            "birth_time_unknown": "true" if ctx.birth_time_unknown else "false",
        },
    )


# ---------------------------------------------------------------------------
# Structured output models
# ---------------------------------------------------------------------------

class ElementScore(BaseModel):
    element: str
    score: int


class ElementBalanceOutput(BaseModel):
    scores: list[ElementScore]
    dominant: str
    weakest: str
    summary: str


class ClassicalReference(BaseModel):
    id: str
    passage: str
    translation: str
    source: str
    relevance: str


class InsightBullet(BaseModel):
    """Single bullet point inside an insight section."""
    icon: str = Field(description="Emoji icon for this bullet")
    text: str = Field(description="Concise insight, max ~80 chars")


class InsightSection(BaseModel):
    """One themed card in the accordion (e.g. Strengths, Watch Out)."""
    id: str
    icon: str = Field(description="Section emoji")
    heading: str = Field(description="Short heading, 2-4 words")
    tagline: str = Field(description="1-sentence sub-heading")
    bullets: list[InsightBullet] = Field(min_length=2, max_length=5)
    citations: list[str] = Field(default_factory=list)


class NarrativeOutput(BaseModel):
    """Structured narrative: a TL;DR + 3-4 insight cards."""
    tldr: str = Field(description="1-sentence summary, max 20 words")
    insights: list[InsightSection] = Field(min_length=2, max_length=5)


class YearPrediction(BaseModel):
    """Per-year prediction generated by the narrative agent."""
    year: int
    prediction: str = Field(description="Max 100 chars, key event/theme for this year")
    confidence: float = Field(ge=0.0, le=1.0, description="Confidence based on interaction strength")
    evidence_refs: list[str] = Field(default_factory=list, description="Classical ref IDs or interaction descriptions")


class CompatOverview(BaseModel):
    """Compatibility overview shown in the OverviewTab ring + hero copy."""
    score: int = Field(ge=0, le=100, description="0-100 overall harmony score")
    summary: str = Field(description="1-sentence italic hero verdict, max 20 words")
    relationship: str = Field(description="Relationship label: romance, marriage, business, friends, family")
    strengths: list[str] = Field(
        min_length=2, max_length=5,
        description="Short phrases describing what works well between the pair",
    )
    frictions: list[str] = Field(
        min_length=1, max_length=5,
        description="Short phrases describing tension points or watch-outs",
    )


class CompatPairInteraction(BaseModel):
    """One paired pillar interaction for the Pillars tab."""
    type: str = Field(description="combination | clash | harm | support | punishment")
    from_: str = Field(alias="from", description="Person A branch or stem")
    to: str = Field(description="Person B branch or stem")
    person_a: str = Field(description="Pillar label for person A, e.g. 'Day'")
    person_b: str = Field(description="Pillar label for person B, e.g. 'Day'")
    description: str | None = Field(default=None, description="1-2 sentence interpretation")
    effect: str | None = Field(default=None, description="Short practical effect")

    class Config:
        populate_by_name = True


class CompatMechanism(BaseModel):
    """Classical mechanism card for the Why tab."""
    id: str
    title: str = Field(description="Short serif title, e.g. 'Bing Fire warmed by Ji Earth'")
    type: str | None = Field(
        default=None,
        description="Mechanism category for filtering, e.g. combination | clash | harm | support",
    )
    icon: str = Field(description="Emoji or lucide icon name")
    bullets: list[str] = Field(min_length=1, max_length=4)
    citation_ids: list[str] = Field(default_factory=list, description="Classical reference ids")


class CompatibilityNarrativeFields(BaseModel):
    """Compat-specific output, only populated when focus is 'compatibility:*'."""
    overview: CompatOverview
    pair_interactions: list[CompatPairInteraction] = Field(
        default_factory=list, min_length=3, max_length=6
    )
    mechanisms: list[CompatMechanism] = Field(
        default_factory=list, min_length=4, max_length=6
    )


# --- Occasion (lucky-day) ---
class OccasionMechanism(BaseModel):
    id: str
    title: str
    type: str | None = Field(
        default=None,
        description="Mechanism category label for filtering, e.g. Timing | Element | Support | Caution",
    )
    icon: str
    bullets: list[str] = Field(min_length=1, max_length=4)
    citation_ids: list[str] = Field(default_factory=list)


class OccasionPick(BaseModel):
    rank: int = Field(ge=1, le=5)
    date: str  # ISO YYYY-MM-DD
    day_pillar_stem: str
    day_pillar_branch: str
    score: int = Field(ge=0, le=100)
    one_line_reason: str = Field(description="Max 100 chars")
    best_hours: list[str] = Field(default_factory=list, description="e.g. ['09:00-11:00']")
    mechanisms: list[OccasionMechanism] = Field(
        default_factory=list,
        max_length=4,
        description="Per-pick mechanism cards for inline expansion",
    )


class OccasionAnalysis(BaseModel):
    occasion_type: str
    key_elements: list[str]
    avoid_elements: list[str]
    description: str


class OccasionNarrativeFields(BaseModel):
    top_picks: list[OccasionPick] = Field(min_length=3, max_length=5)
    analysis: OccasionAnalysis
    mechanisms: list[OccasionMechanism] = Field(min_length=2, max_length=6)


# --- Luck Cycle (luck-draw) ---
class LuckCycleCurrentWindow(BaseModel):
    decade: str  # e.g. "2020-2030"
    score: int = Field(ge=0, le=100)
    summary: str
    element: str  # Wood|Fire|Earth|Metal|Water


class LuckCycleMechanism(BaseModel):
    id: str
    title: str
    icon: str
    bullets: list[str] = Field(min_length=1, max_length=4)
    citation_ids: list[str] = Field(default_factory=list)


class LuckCycleNarrativeFields(BaseModel):
    current_window: LuckCycleCurrentWindow
    mechanisms: list[LuckCycleMechanism] = Field(min_length=2, max_length=6)


# --- Wish (custom-wish) ---
class WishCondition(BaseModel):
    type: str = Field(description="check | warn | cross")
    text: str


class WishVerdict(BaseModel):
    title: str
    score: int = Field(ge=0, le=100)
    summary: str
    caution: str | None = None
    conditions: list[WishCondition] = Field(default_factory=list, max_length=6)


class WishAnchor(BaseModel):
    id: str
    label: str
    symbol: str  # single char / emoji / hanzi
    element: str | None = None
    relevance: float = Field(ge=0.0, le=1.0)
    bullets: list[str] = Field(min_length=1, max_length=4)


class WishMechanism(BaseModel):
    id: str
    title: str
    type: str | None = Field(
        default=None,
        description="Mechanism grouping, e.g. luck | interaction | chart",
    )
    icon: str
    bullets: list[str] = Field(min_length=1, max_length=4)
    citation_ids: list[str] = Field(default_factory=list)


class WishNarrativeFields(BaseModel):
    verdict: WishVerdict
    anchors: list[WishAnchor] = Field(min_length=2, max_length=5)
    mechanisms: list[WishMechanism] = Field(min_length=2, max_length=6)


class EnrichedNarrativeOutput(BaseModel):
    """Extended narrative with year predictions and evidence tracking.

    This is the **canonical merged type** consumed by the route handler and
    snapshot upserter. It still has all four sibling sub-blocks as Optional
    because downstream fan-out emitters at ``routes.py:1316-1411`` and the
    snapshot pipeline read a single merged shape regardless of mode.

    Per-mode narrow output types (``CompatibilityNarrativeOutput`` etc.)
    drive the OpenAI structured-output schema down from 11.4 KB → 3-5 KB,
    cutting reasoning tokens 30-40%. They are normalized back into this
    type via :func:`_promote_narrative_to_enriched` immediately after the
    agent returns, so the rest of the pipeline is unchanged.
    """
    tldr: str = Field(description="1-sentence summary, max 20 words")
    insights: list[InsightSection] = Field(min_length=2, max_length=5)
    year_predictions: list[YearPrediction] = Field(
        default_factory=list,
        description="Per-year predictions for years with notable interactions",
    )
    compatibility: CompatibilityNarrativeFields | None = Field(
        default=None,
        description="Populated only when the focus is 'compatibility:*' and Person B data is available",
    )
    occasion: OccasionNarrativeFields | None = None
    luck_cycle: LuckCycleNarrativeFields | None = None
    wish: WishNarrativeFields | None = None


# --- Per-mode narrow output schemas ----------------------------------------
# Each narrow output binds the matching mode block as REQUIRED (not Optional)
# and omits the other three siblings entirely. Compact JSON schema char count
# drops 54-72% vs ``EnrichedNarrativeOutput``, which is what cuts model
# reasoning tokens since the schema sits in the system context for every
# generation.


class CompatibilityNarrativeOutput(BaseModel):
    """Narrative output schema used when focus starts with ``compatibility:``."""
    tldr: str = Field(description="1-sentence summary, max 20 words")
    insights: list[InsightSection] = Field(min_length=2, max_length=5)
    year_predictions: list[YearPrediction] = Field(default_factory=list)
    compatibility: CompatibilityNarrativeFields


class OccasionNarrativeOutput(BaseModel):
    """Narrative output schema used when focus starts with ``occasion:``."""
    tldr: str = Field(description="1-sentence summary, max 20 words")
    insights: list[InsightSection] = Field(min_length=2, max_length=5)
    year_predictions: list[YearPrediction] = Field(default_factory=list)
    occasion: OccasionNarrativeFields


class LuckCycleNarrativeOutput(BaseModel):
    """Narrative output schema used when focus starts with ``luck_cycle:``."""
    tldr: str = Field(description="1-sentence summary, max 20 words")
    insights: list[InsightSection] = Field(min_length=2, max_length=5)
    year_predictions: list[YearPrediction] = Field(default_factory=list)
    luck_cycle: LuckCycleNarrativeFields


class WishNarrativeOutput(BaseModel):
    """Narrative output schema used for free-form custom-wish readings."""
    tldr: str = Field(description="1-sentence summary, max 20 words")
    insights: list[InsightSection] = Field(min_length=2, max_length=5)
    year_predictions: list[YearPrediction] = Field(default_factory=list)
    wish: WishNarrativeFields


# Map each narrow output class to the EnrichedNarrativeOutput attribute that
# carries its mode block. Used by ``_promote_narrative_to_enriched``.
_NARRATIVE_MODE_FIELD: dict[type, str] = {
    CompatibilityNarrativeOutput: "compatibility",
    OccasionNarrativeOutput: "occasion",
    LuckCycleNarrativeOutput: "luck_cycle",
    WishNarrativeOutput: "wish",
}


def _promote_narrative_to_enriched(
    narrow: Any,
) -> "EnrichedNarrativeOutput":
    """Convert any narrow per-mode output into the merged ``EnrichedNarrativeOutput``.

    Idempotent — if ``narrow`` is already ``EnrichedNarrativeOutput`` it is
    returned unchanged. Handles three input shapes:

    1. ``EnrichedNarrativeOutput`` instance → returned as-is (no validation).
    2. One of the four narrow per-mode classes → mode block is folded into
       a fresh ``EnrichedNarrativeOutput`` with siblings left ``None``.
    3. Legacy bare ``NarrativeOutput`` (no mode block, no year predictions)
       or any other Pydantic ``BaseModel`` / dict → validated through
       ``model_validate`` against its dump. Defensive against SDK drift.
    """
    if isinstance(narrow, EnrichedNarrativeOutput):
        return narrow
    field_name = _NARRATIVE_MODE_FIELD.get(type(narrow))
    if field_name is not None:
        return EnrichedNarrativeOutput(
            tldr=narrow.tldr,
            insights=narrow.insights,
            year_predictions=narrow.year_predictions,
            **{field_name: getattr(narrow, field_name)},
        )
    # Legacy NarrativeOutput or any other BaseModel: dump and validate.
    if isinstance(narrow, BaseModel):
        return EnrichedNarrativeOutput.model_validate(narrow.model_dump())
    # Plain dict / unknown shape: let pydantic's validator raise if invalid.
    return EnrichedNarrativeOutput.model_validate(narrow)


class FollowUpButton(BaseModel):
    id: str
    label: str


class GuardrailOutput(BaseModel):
    level: str
    message: str
    disclaimer: str
    follow_up_buttons: list[FollowUpButton] = Field(default_factory=list)


DEFAULT_FOLLOW_UP_BUTTONS = [
    FollowUpButton(id="year_forecast", label="Explore This Year Luck"),
    FollowUpButton(id="career_focus", label="Career Deep Dive"),
    FollowUpButton(id="relationship_focus", label="Compatibility Check"),
]


# ---------------------------------------------------------------------------
# Agent instructions
# ---------------------------------------------------------------------------

NARRATIVE_INSTRUCTIONS = """\
You are the Ming Engine narrative interpreter. You have access to a COMPLETE \
deterministic BaZi analysis — Four Pillars, hidden stems (藏干), ten gods (十神), \
branch interactions (冲合害), seasonal strength (旺相休囚死), luck pillars (大运), \
annual pillars (流年), and classical references. Your job is to INTERPRET this \
pre-computed data, not to guess or fabricate BaZi calculations.

Output format:
- tldr: 1 sentence, max 20 words, capturing the core insight.
- insights: 3-4 themed sections. Each section has:
  - id: snake_case identifier (e.g. "core_strength", "dynamics", "advice", "timing")
  - icon: a single emoji that represents the theme (🎯 ⚡ ✨ 🕐 ⚠️ 💡 🔥 🌊)
  - heading: 2-4 word title
  - tagline: 1 sentence explaining the theme for this chart
  - bullets: 2-4 items, each with an emoji icon and short text (max 80 chars, no paragraphs)
  - citations: list of classical reference ids used
- year_predictions: For each year in the annual_pillars that has notable interactions \
  (clashes, combinations, harms), produce a prediction:
  - year: the year number
  - prediction: max 100 chars, the key event or theme
  - confidence: 0.0-1.0 based on how strong the interaction signals are
  - evidence_refs: list of interaction descriptions or classical ref IDs

Guidelines:
- LANGUAGE — STRICT: output English ONLY. No Chinese characters (CJK Han)
  anywhere in tldr, insights, year_predictions, or any nested string. Use
  English-only names for all BaZi concepts:
    * Day Master, day pillar, month pillar, year pillar, hour pillar
    * Ten Gods: Direct Officer, Seven Killings, Direct Wealth,
      Indirect Wealth, Eating God, Hurt Officer, Direct Resource,
      Indirect Resource, Direct Companion, Rob Wealth
    * Elements: Wood, Fire, Earth, Metal, Water
    * Animals: Rat, Ox, Tiger, Rabbit, Dragon, Snake, Horse, Goat,
      Monkey, Rooster, Dog, Pig
    * Interactions: clash, combination, harm, punishment, destruction
- Reference SPECIFIC computed data using English names: "Your Metal Day
  Master scores 3.5" not the stem hanzi. "Indirect Resource in the month
  stem signals deep learning instinct." "Tiger-Monkey clash between year
  and month."
- Plain-language gloss: when a Ten-Gods term first appears in a bullet,
  add a brief parenthetical ("Hurt Officer (creative-output star)").
- Cite classical references by their id.
- Be concise — more insight per word, fewer words per insight.
- For year_predictions, focus on years with clashes or combinations. Skip
  uneventful years.
- Prefer actionable, practical bullets over abstract philosophy.
- Emit ONLY the one specialized block that matches the current reading
  mode: `compatibility`, `occasion`, `luck_cycle`, or `wish`. Leave the
  others null/omitted.

COMPATIBILITY MODE (only when `person_b` is present in the input JSON):
The focus string will start with "compatibility:" and you will receive Person A's \
chart as the top-level fields AND Person B's chart under `person_b`. Produce a \
`compatibility` object IN ADDITION TO the standard tldr/insights:

- compatibility.overview.score: 0-100 integer. Anchor to real signals:
  - +30 for element complementarity (A's dominant feeds B's weakest, or vice versa)
  - +25 for Day Master supporting relationship (same element, or producing/controlled)
  - +20 for branch combinations (六合, 三合) between the two charts
  - -25 for Day Pillar 冲 (direct clash) between A and B
  - -15 for Hour/Year clashes (刑, 破, 害)
  - Modulate by seasonal strength: weak Day Master benefiting from partner's dominant element is a strong positive
- compatibility.overview.summary: Italic single sentence hero verdict, max 20 words. \
  Reference both Day Masters by name (e.g. "Her Earth grounds your Fire.").
- compatibility.overview.relationship: extract from the focus string after the colon \
  (e.g. focus="compatibility:romance" → "romance"). Normalize to one of: romance, \
  marriage, business, friends, family.
- compatibility.overview.strengths: 2-4 phrases describing what works. Each must cite \
  a specific chart signal (e.g. "His Jia Wood feeds your weak Fire day master").
- compatibility.overview.frictions: 1-4 phrases describing tension. Cite a specific \
  clash / harm / 10-god collision.
- compatibility.pair_interactions: Scan paired pillars Year/Month/Day/Hour. For each \
  pair that has a meaningful interaction (combination, clash, harm, punishment), \
  emit one entry with:
  - type: "combination" | "clash" | "harm" | "support" | "punishment"
  - from: A's stem or branch code (e.g. "甲", "寅")
  - to: B's stem or branch code
  - person_a: "Year" | "Month" | "Day" | "Hour"
  - person_b: "Year" | "Month" | "Day" | "Hour"
  - description: 1-2 sentence interpretation
  - effect: short practical effect, e.g. "late-night decision fatigue"
  Skip neutral pairs. Return at least 3 pair interactions (max 6).
- compatibility.mechanisms: Return at least 4 classical mechanism cards (max 6). Each has:
  - id: snake_case slug
  - title: short serif-friendly title in PLAIN ENGLISH ONLY. Use phrasings
    like "Yang Fire warmed by Yin Earth", "Tiger meets Monkey clash",
    "Twin Yin Earth day masters". Do NOT emit pinyin-style proper nouns
    ("Ji卯", "Bing-Ren", "Geng-Wu"); do NOT emit any CJK glyphs in the
    title even partially. The mechanism title is shown verbatim in the
    UI — it must read like a normal English headline.
  - type: "combination" | "clash" | "harm" | "support" | "punishment"
  - icon: one of flame, sparkles, heart, zap, layers, mountain, trees
  - bullets: 1-3 reasoning points tied to computed data, English ONLY.
    Do not write things like "Both Day Masters are 己土" — write "Both
    Day Masters are Yin Earth" and gloss when first introduced.
  - citation_ids: classical reference ids consulted (from the `references` field)

When emitting in compatibility mode, the standard `insights` array should focus on \
the PAIR DYNAMICS (not Person A in isolation). Do not repeat single-person insights \
if they have no bearing on the pairing.

OCCASION MODE (only when `focus` starts with "occasion:"):
The focus string encodes `occasion:<type>:<windowStartISO>:<windowEndISO>`. Produce an \
`occasion` object IN ADDITION TO the standard tldr/insights:

- occasion.top_picks: 3-5 auspicious days chosen ONLY from `occasion_window.candidate_days`.
  - rank: 1-5
  - date: copy the exact ISO date from the selected candidate day
  - day_pillar_stem / day_pillar_branch: copy the exact selected candidate day's pillar
  - score: 0-100 integer based on how well the day supports the user's Day Master and the occasion type
  - one_line_reason: max 100 chars, specific and concrete
  - best_hours: list of favorable 2-hour windows such as "09:00-11:00"
  - mechanisms: 2-4 short mechanism cards specific to THIS date, each with id, title, \
    type, icon, bullets, and citation_ids
  Pick from the computed candidate days. Use pillar compatibility with the user's Day Master, \
  seasonal strength, and any meaningful branch interactions. Do not suggest dates outside the window.
- occasion.analysis:
  - occasion_type: normalized occasion label from the focus string
  - key_elements: favorable elements for this occasion in the user's chart context
  - avoid_elements: unfavorable or destabilizing elements for this occasion
  - description: 1-2 sentence explanation tied to the computed chart
- occasion.mechanisms: 2-6 classical mechanism cards. Each has:
  - id: snake_case slug
  - title: short serif-friendly title
  - type: short category label for filtering, e.g. Timing | Element | Support | Caution
  - icon: one of flame, sparkles, heart, zap, layers, mountain, trees
  - bullets: 1-4 reasoning points tied to computed data and the chosen dates
  - citation_ids: classical reference ids consulted

When emitting in occasion mode, the standard `insights` array should focus on WHY \
these dates are favorable, how the occasion type changes the recommendation, and what \
the user should watch for in timing.

LUCK CYCLE MODE (only when `focus` starts with "luck_cycle:"):
The focus string encodes `luck_cycle:<focus>:<horizon>`. Produce a `luck_cycle` object \
IN ADDITION TO the standard tldr/insights:

- luck_cycle.current_window: summarize the ACTIVE decade from `luck_pillars` by selecting \
  the pillar whose year range contains the current year.
  - decade: e.g. "2020-2030"
  - score: 0-100 integer for how supportive the current decade is
  - summary: 1-2 sentence interpretation anchored to the active pillar and chart
  - element: the dominant element of the active decade window
- luck_cycle.mechanisms: 2-6 classical mechanism cards. Each has:
  - id: snake_case slug
  - title: short serif-friendly title
  - icon: one of flame, sparkles, heart, zap, layers, mountain, trees
  - bullets: 1-4 reasoning points tied to the active luck pillar, nearby annual pillars, and chart interactions
  - citation_ids: classical reference ids consulted

When emitting in luck cycle mode, the standard `insights` array should focus on the \
current decade, what lever is strongest right now, and what timing shift the horizon suggests.

WISH MODE (only when a `question` is present and the focus does not start with \
"compatibility:", "occasion:", or "luck_cycle:"):
This is the custom wish / free-form intent bucket. Produce a `wish` object IN ADDITION \
TO the standard tldr/insights:

- wish.verdict:
  - title: short verdict headline
  - score: 0-100 integer
  - summary: concise answer to the wish
  - caution: optional short caveat
  - conditions: 0-6 items, each with `type` = check | warn | cross and `text`
- wish.anchors: 2-5 short interpretive cards tied to specific pillar features.
  Each has:
  - id: snake_case slug
  - label: short title
  - symbol: a single char / emoji / hanzi
  - element: optional supporting element
  - relevance: 0.0-1.0
  - bullets: 1-4 reasoning points tied to specific pillars, ten gods, or interactions
- wish.mechanisms: 2-6 classical mechanism cards. Each has:
  - id: snake_case slug
  - title: short serif-friendly title
  - type: "luck" | "interaction" | "chart"
  - icon: one of flame, sparkles, heart, zap, layers, mountain, trees
  - bullets: 1-4 reasoning points tied to computed data
  - citation_ids: classical reference ids consulted

When emitting in wish mode, the standard `insights` array should answer the actual \
question asked, stay specific to the user's chart, and avoid generic fortune-cookie language.
"""

GUARDRAIL_INSTRUCTIONS = """\
You are the Ming Engine guardrail layer. Review the narrative for safety and \
generate a user-facing disclaimer with follow-up options.

- Set level to "info" for standard readings, "warning" if the narrative \
touches sensitive topics, "critical" only if content should be suppressed.
- The message is the primary banner text; disclaimer is secondary.
- Canonical follow-up action ids: year_forecast, career_focus, \
relationship_focus, deep_dive_element, show_sources, expand_classics.
- Default button set should NOT include deep_dive_element.
"""


# ---------------------------------------------------------------------------
# Agent definitions
# ---------------------------------------------------------------------------

def _model(setting_name: str) -> str:
    return getattr(get_settings(), setting_name)


def _model_settings(
    reasoning_key: str,
    max_tokens_key: str | None = None,
    *,
    service_tier_key: str | None = None,
) -> ModelSettings:
    """Build per-stage ``ModelSettings`` from the FortuneSettings singleton.

    ``reasoning_key`` and the optional keys name attributes on
    ``FortuneSettings``.
    """
    settings = get_settings()
    effort = getattr(settings, reasoning_key, "low")
    kwargs: dict[str, Any] = {
        "reasoning": Reasoning(effort=effort, summary=None),
        "verbosity": "low",
        "store": False,
        # store=False means reasoning items are never persisted server-side;
        # session replay must carry them as encrypted content or follow-up
        # turns 404 on the dangling rs_* references.
        "response_include": ["reasoning.encrypted_content"],
    }
    if max_tokens_key is not None:
        cap = getattr(settings, max_tokens_key, None)
        if cap is not None:
            kwargs["max_tokens"] = int(cap)
    extra_args: dict[str, Any] = {}
    if service_tier_key is not None:
        tier = getattr(settings, service_tier_key, None)
        if tier:
            extra_args["service_tier"] = tier
    if extra_args:
        kwargs["extra_args"] = extra_args
    return ModelSettings(**kwargs)


def _current_year(ctx: FortuneRunContext) -> int:
    """Resolve the forecast anchor year, allowing tests to pin it via metadata."""
    raw = ctx.metadata.get("current_year")
    if isinstance(raw, int):
        return raw
    if isinstance(raw, str) and raw.isdigit():
        return int(raw)
    return date.today().year


def _read_field(item: Any, name: str, default: Any = None) -> Any:
    """Read a field from pydantic models, dicts, and lightweight test fixtures."""
    if isinstance(item, dict):
        return item.get(name, default)
    if hasattr(item, name):
        return getattr(item, name)
    data = getattr(item, "_data", None)
    if isinstance(data, dict):
        return data.get(name, default)
    return default


def _select_luck_pillars_for_prompt(
    luck_pillars: list[Any],
    *,
    current_year: int,
    limit: int = 4,
) -> list[Any]:
    """Pick the active luck pillar plus the next few pillars for narrative context."""
    if not luck_pillars:
        return []

    start_index = 0
    for idx, pillar in enumerate(luck_pillars):
        start_year = _read_field(pillar, "start_year")
        end_year = _read_field(pillar, "end_year")
        if isinstance(start_year, int) and isinstance(end_year, int):
            if start_year <= current_year <= end_year:
                start_index = idx
                break
            if start_year > current_year:
                start_index = idx
                break
    else:
        start_index = max(len(luck_pillars) - 1, 0)

    return luck_pillars[start_index:start_index + limit]


def _select_annual_pillars_for_prompt(
    annual_pillars: list[Any],
    *,
    current_year: int,
    horizon_years: int,
    limit: int = 20,
) -> list[Any]:
    """Pick notable annual pillars from the current forecast window only."""
    end_year = current_year + max(horizon_years, 0)
    window = [
        pillar for pillar in annual_pillars
        if current_year <= (_read_field(pillar, "year", -1) or -1) <= end_year
    ]
    notable = [
        pillar for pillar in window
        if _read_field(pillar, "interactions_with_chart", [])
    ]
    return notable[:limit]


def _build_narrative_agent(
    name: str,
    reasoning_setting_key: str,
    output_type: type[BaseModel],
    *,
    max_tokens_setting_key: str | None = None,
    service_tier_setting_key: str | None = None,
) -> Agent[FortuneRunContext]:
    """Construct a narrative agent bound to a per-mode output schema.

    All five mode agents share the same NARRATIVE_INSTRUCTIONS string so
    the OpenAI prompt-cache stable prefix stays identical across modes —
    only the bound schema and per-mode reasoning/max_tokens differ.

    """
    return Agent(
        name=name,
        model=_model("narrative_model"),
        model_settings=_model_settings(
            reasoning_setting_key,
            max_tokens_setting_key,
            service_tier_key=service_tier_setting_key,
        ),
        instructions=NARRATIVE_INSTRUCTIONS,
        output_type=output_type,
    )


# ``general`` retains ``narrative_reasoning`` (the legacy single key) so it
# acts as a backstop for any focus shape that doesn't match one of the
# four canonical modes — ``run_narrative`` / ``run_narrative_streamed``
# only fall through to ``general`` after route normalization.
#
# Compat starts at ``medium`` reasoning (gated by the fixture A/B in
# ``test_compat_reasoning_floor.py``); the other three modes default to
# ``low`` because their UI payloads are smaller and (for occasion) the
# deterministic prefilter does the heavy ranking before the model.
NARRATIVE_AGENTS: dict[str, Agent[FortuneRunContext]] = {
    "compatibility": _build_narrative_agent(
        "fortune_narrative_compatibility",
        "narrative_reasoning_compatibility",
        CompatibilityNarrativeOutput,
        max_tokens_setting_key="narrative_max_tokens_compatibility",
        service_tier_setting_key="narrative_service_tier_compatibility",
    ),
    "occasion": _build_narrative_agent(
        "fortune_narrative_occasion",
        "narrative_reasoning_occasion",
        OccasionNarrativeOutput,
        max_tokens_setting_key="narrative_max_tokens_occasion",
    ),
    "luck_cycle": _build_narrative_agent(
        "fortune_narrative_luck_cycle",
        "narrative_reasoning_luck_cycle",
        LuckCycleNarrativeOutput,
        max_tokens_setting_key="narrative_max_tokens_luck_cycle",
    ),
    "wish": _build_narrative_agent(
        "fortune_narrative_wish",
        "narrative_reasoning_wish",
        WishNarrativeOutput,
        max_tokens_setting_key="narrative_max_tokens_wish",
    ),
    "general": _build_narrative_agent(
        "fortune_narrative",
        "narrative_reasoning",
        EnrichedNarrativeOutput,
    ),
}

# Backwards-compatible alias. Test fixtures and a handful of admin/debug
# call sites still import ``NARRATIVE_AGENT`` directly. The general agent
# is the closest stand-in (same instructions, same output_type as before).
NARRATIVE_AGENT: Agent[FortuneRunContext] = NARRATIVE_AGENTS["general"]


def _narrative_mode(ctx: FortuneRunContext) -> str:
    """Pick the per-mode narrative agent key from the runtime context.

    Mirrors the deterministic fan-out at ``routes.py:1316-1411``: the same
    focus prefixes that drive ``emit_compat_*`` / ``emit_occasion_*`` /
    ``emit_luck_cycle_*`` / ``emit_wish_*`` should bind the agent that
    produces those blocks. Falls back to ``general`` (the legacy union
    schema) only when no mode matches — primarily useful in tests or
    internal debug runs.
    """
    function_id = canonical_function(ctx.focus, ctx.question)
    return "luck_cycle" if function_id == "cycle" else function_id or "general"


GUARDRAIL_AGENT: Agent[FortuneRunContext] = Agent(
    name="fortune_guardrail",
    model=_model("guardrail_model"),
    model_settings=_model_settings("guardrail_reasoning", "guardrail_max_tokens"),
    instructions=GUARDRAIL_INSTRUCTIONS,
    output_type=GuardrailOutput,
)


# ---------------------------------------------------------------------------
# Pipeline functions
# ---------------------------------------------------------------------------

def enrich_element_balance(
    raw_counts: dict[str, int],
    day_master_element: str,
) -> ElementBalanceOutput:
    scores = [ElementScore(element=k, score=v) for k, v in raw_counts.items()]
    by_score = sorted(scores, key=lambda s: (-s.score, s.element))
    dominant = by_score[0].element
    weakest = sorted(scores, key=lambda s: (s.score, s.element))[0].element
    return ElementBalanceOutput(
        scores=scores,
        dominant=dominant,
        weakest=weakest,
        summary=(
            f"{dominant.title()} is most prominent, {weakest} is comparatively weak, "
            f"and the day master expresses through {day_master_element}."
        ),
    )


async def run_foundation(ctx: FortuneRunContext) -> dict[str, Any]:
    """Deterministic foundation with traced individual steps.

    Each computation is wrapped in a TraceCollector step so the frontend
    can render a real-time "Glass Box" sidebar showing the THINK -> CALL ->
    RECEIVE -> INTERPRET rhythm.

    Returns foundation dict with an extra "trace" key containing the collector.
    """
    import time as _time_local

    try:
        from .agent_logging import classify_function as _cf, logger as _alogger
    except ImportError:
        from agent_logging import classify_function as _cf, logger as _alogger  # type: ignore[no-redef]
    _t_found_start = _time_local.monotonic()
    _foundation_fn = _cf(ctx.focus, ctx.question)

    from .bazi_engine import _normalize_dt
    from datetime import datetime as dt

    trace = TraceCollector()

    # 1. Four Pillars chart
    with trace.step("tool_call", "foundation", tool_name="compute_bazi_chart",
                     label="Calculating Four Pillars",
                     input_summary=f"{ctx.birth_iso} tz={ctx.timezone}") as ts:
        chart = compute_bazi_chart(
            ctx.birth_iso, timezone=ctx.timezone,
            birth_time_unknown=ctx.birth_time_unknown,
        )
        ts.output_summary = f"Day Master: {chart['day_master']} ({chart['day_master_element']})"

    # 2. Hidden stems
    with trace.step("tool_call", "foundation", tool_name="compute_hidden_stems",
                     label="Extracting Hidden Stems (\u85cf\u5e72)",
                     input_summary="4 branches") as ts:
        hidden = compute_all_hidden_stems(chart)
        total_hs = sum(len(v) for v in hidden.values())
        ts.output_summary = f"{total_hs} hidden stems across {len(hidden)} pillars"

    # 3. Ten Gods
    with trace.step("tool_call", "foundation", tool_name="compute_ten_gods",
                     label="Classifying Ten Gods (\u5341\u795e)",
                     input_summary=f"Day Master: {chart['day_master']}") as ts:
        ten_gods = compute_ten_gods(chart["day_master"], chart, hidden)
        ts.output_summary = f"{len(ten_gods)} positions classified"

    # 4. Interactions
    with trace.step("tool_call", "foundation", tool_name="compute_interactions",
                     label="Detecting Clashes & Combinations (\u51b2\u5408\u5bb3)",
                     input_summary="checking all branch pairs") as ts:
        interactions = compute_interactions(chart)
        ts.output_summary = f"{len(interactions)} interactions found"

    # 5. Seasonal strength
    month_branch = chart["month"]["branch"] if isinstance(chart["month"], dict) else chart["month"].branch
    with trace.step("tool_call", "foundation", tool_name="compute_seasonal_strength",
                     label="Evaluating Seasonal Strength (\u65fa\u76f8\u4f11\u56da\u6b7b)",
                     input_summary=f"{chart['day_master_element']} in {month_branch}") as ts:
        seasonal = compute_seasonal_strength(chart["day_master_element"], month_branch)
        ts.output_summary = f"{seasonal.strength} (score: {seasonal.score})"

    # 6. Enhanced element counts
    with trace.step("tool_call", "foundation", tool_name="compute_enhanced_elements",
                     label="Weighting Element Balance",
                     input_summary="stems + hidden stems") as ts:
        enhanced_counts, element_by_source = compute_enhanced_elements(chart, hidden)
        dominant = max(enhanced_counts, key=enhanced_counts.get)  # type: ignore[arg-type]
        ts.output_summary = f"Dominant: {dominant} ({enhanced_counts[dominant]:.1f})"

    # 7. Luck pillars
    luck_pillars = []
    if ctx.gender.lower() not in ("unknown", ""):
        with trace.step("tool_call", "foundation", tool_name="compute_luck_pillars",
                         label="Computing Luck Pillars (\u5927\u8fd0)",
                         input_summary=f"gender={ctx.gender}") as ts:
            luck_pillars = compute_luck_pillars(chart, ctx.birth_iso, ctx.timezone, ctx.gender)
            ts.output_summary = f"{len(luck_pillars)} decades computed"

    # 8. Annual pillars
    local_dt = _normalize_dt(ctx.birth_iso, ctx.timezone)
    birth_year = local_dt.year
    current_year = dt.now().year
    with trace.step("tool_call", "foundation", tool_name="compute_annual_pillars",
                     label="Computing Annual Pillars (\u6d41\u5e74)",
                     input_summary=f"{birth_year}-{current_year + 10}") as ts:
        annual_pillars = compute_annual_pillars(birth_year, current_year + 10, chart, luck_pillars)
        notable = sum(1 for ap in annual_pillars if ap.interactions_with_chart)
        ts.output_summary = f"{len(annual_pillars)} years, {notable} with interactions"

    # 9. Retrodictions (Spooky Accuracy)
    with trace.step("tool_call", "foundation", tool_name="compute_retrodictions",
                     label="Generating Retrodictions (Spooky Accuracy)",
                     input_summary=f"scanning past years for strong interactions") as ts:
        retrodictions = compute_retrodictions(annual_pillars, current_year=current_year)
        ts.output_summary = f"{len(retrodictions)} retrodictions generated"

    # 10. Harmony score
    harmony = compute_harmony_score(interactions)

    # Build FullBaziAnalysis for downstream compatibility
    analysis = FullBaziAnalysis(
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

    # 10. Element balance (legacy)
    elements = enrich_element_balance(
        chart["raw_element_counts"],
        chart["day_master_element"],
    )

    # 11. Classical retrieval
    with trace.step("tool_call", "foundation", tool_name="retrieve_classical_references",
                     label="Consulting Classical Texts",
                     input_summary=f"query: {ctx.focus or 'general'}") as ts:
        query_parts = [ctx.question, ctx.focus, ctx.tone, chart["day_master_element"]]
        retrieval_query = " ".join(p for p in query_parts if p) or "general bazi reading"
        references = [
            ClassicalReference(**item)
            for item in retrieve_classical_references(retrieval_query)
        ]
        ts.output_summary = f"{len(references)} passages matched"

    _foundation_ms = (_time_local.monotonic() - _t_found_start) * 1000
    _alogger.info(
        "[FORTUNE-AGENT] "
        f"fn={_foundation_fn} stage=foundation model=deterministic reasoning=- "
        f"latency_ms={_foundation_ms:.0f} "
        f"tokens_in=0 tokens_out=0 reasoning_tokens=0 requests=0 "
        f"run_id={ctx.run_id or '-'} fortune_id={ctx.fortune_id or '-'} "
        f"agent=fortune_foundation ok=true "
        f"interactions={len(interactions)} ten_gods={len(ten_gods)} "
        f"luck_pillars={len(luck_pillars)} annual_pillars={len(annual_pillars)}"
    )

    return {
        "pillars": chart,
        "elements": elements,
        "references": references,
        "analysis": analysis,
        "retrodictions": retrodictions,
        "trace": trace,
    }


def _build_narrative_prompt(ctx: FortuneRunContext, foundation: dict[str, Any]) -> str:
    """Build the JSON prompt for the narrative agent with full analysis data.

    Field ordering note: keys are inserted **stable-first → volatile-last** so
    the OpenAI Responses API automatic prompt cache (≥1024-token prefix
    match) hits on repeat queries by the same user. Concretely:

      1. Schema/foundation version markers (global, stable across deploys).
      2. Person A's birth-derived chart data (stable across that user's
         session — pillars, hidden stems, ten gods, interactions, seasonal
         strength, enhanced element counts, harmony score, luck pillars).
      3. Person B's chart (stable per-pair when present).
      4. ``occasion_window`` (changes when the user changes the window).
      5. ``current_year`` (changes daily/yearly).
      6. ``focus`` / ``tone`` / ``question`` / ``references`` (volatile per
         call — focus and question switch the agent's mode and references
         depend on focus, so they MUST come last).

    Re-ordering this dict will move where the cache prefix breaks. Audit
    against ``test_prompt_cache_prefix.py`` before touching.
    """
    analysis: FullBaziAnalysis = foundation["analysis"]
    settings = get_settings()
    current_year = _current_year(ctx)

    # 1. Stable global markers.
    prompt_data: dict[str, Any] = {
        "foundation_version": FOUNDATION_VERSION,
        "narrative_schema_version": NARRATIVE_SCHEMA_VERSION,
    }

    # 2. Stable per-user chart data (Person A).
    prompt_data.update({
        "pillars": foundation["pillars"],
        "elements": foundation["elements"].model_dump(),
        "hidden_stems": {k: [s.model_dump() for s in v] for k, v in analysis.hidden_stems.items()},
        "ten_gods": [tg.model_dump() for tg in analysis.ten_gods],
        "interactions": [ix.model_dump() for ix in analysis.interactions],
        "seasonal_strength": analysis.seasonal_strength.model_dump(),
        "enhanced_element_counts": analysis.enhanced_element_counts,
        "harmony_score": analysis.harmony_score,
    })

    # Include luck + annual pillars if available (for year predictions).
    if analysis.luck_pillars:
        luck_pillars = (
            _select_luck_pillars_for_prompt(
                analysis.luck_pillars,
                current_year=current_year,
            )
            if settings.active_luck_window_enabled
            else analysis.luck_pillars[:4]
        )
        prompt_data["luck_pillars"] = [lp.model_dump() for lp in luck_pillars]
    if analysis.annual_pillars:
        # Only include years with interactions (to keep prompt size reasonable).
        annual_pillars = (
            _select_annual_pillars_for_prompt(
                analysis.annual_pillars,
                current_year=current_year,
                horizon_years=settings.annual_prompt_horizon_years,
            )
            if settings.current_annual_window_enabled
            else [
                ap for ap in analysis.annual_pillars
                if ap.interactions_with_chart
            ][:20]
        )
        prompt_data["notable_annual_pillars"] = [
            ap.model_dump() for ap in annual_pillars
        ]

    # 3. Person B chart (stable per-pair, before any per-call volatile data).
    person_b_foundation = foundation.get("person_b")
    if person_b_foundation:
        analysis_b: FullBaziAnalysis = person_b_foundation["analysis"]
        prompt_data["person_a_label"] = "Person A"
        prompt_data["person_b"] = {
            "pillars": person_b_foundation["pillars"],
            "elements": person_b_foundation["elements"].model_dump()
                if hasattr(person_b_foundation["elements"], "model_dump")
                else person_b_foundation["elements"],
            "hidden_stems": {
                k: [s.model_dump() for s in v] for k, v in analysis_b.hidden_stems.items()
            },
            "ten_gods": [tg.model_dump() for tg in analysis_b.ten_gods],
            "interactions": [ix.model_dump() for ix in analysis_b.interactions],
            "seasonal_strength": analysis_b.seasonal_strength.model_dump(),
            "enhanced_element_counts": analysis_b.enhanced_element_counts,
            "harmony_score": analysis_b.harmony_score,
        }

    # 4. Occasion window (rarely-changing; depends on focus's window args).
    occasion_window = _build_occasion_window(ctx, foundation=foundation)
    if occasion_window:
        prompt_data["occasion_window"] = occasion_window

    # 5. Daily/yearly markers.
    prompt_data["current_year"] = current_year

    # 6. Per-call volatile fields (cache prefix breaks here on every call).
    prompt_data["focus"] = ctx.focus
    prompt_data["tone"] = ctx.tone
    prompt_data["question"] = ctx.question
    prompt_data["references"] = [r.model_dump() for r in foundation["references"]]

    return json.dumps(prompt_data, ensure_ascii=False)


def _parse_occasion_focus(focus: str | None) -> tuple[str, date, date] | None:
    if not focus or not focus.startswith("occasion:"):
        return None

    parts = focus.split(":", 3)
    if len(parts) != 4:
        return None

    occasion_type, start_raw, end_raw = parts[1], parts[2], parts[3]
    try:
        start = date.fromisoformat(start_raw[:10])
        end = date.fromisoformat(end_raw[:10])
    except ValueError:
        return None
    if end < start:
        return None
    return occasion_type, start, end


def _build_occasion_window(
    ctx: FortuneRunContext,
    *,
    foundation: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Build the occasion candidate-day window (with optional prefilter).

    Two call modes:

    1. **Prefilter** — when ``foundation`` is provided, the function
       generates ALL candidate days for the requested window, scores each
       against the querent's chart via
       :func:`_foundation_cache.score_candidate_day`, then returns only
       the top 21 plus a coverage sample (1 per 7-day bucket from the
       remainder, capped at 10). This narrows 60+ days down to ~30 picks
       and lets the narrative agent run at ``low`` reasoning effort.

    2. **Repair / no-prefilter** — when ``foundation`` is omitted (called
       by ``repair_occasion_narrative`` for date validation), all
       candidate days are returned in chronological order. The repair
       path needs the full date set so it can validate every pick the
       model emitted.

    Day-chart computation goes through ``compute_day_chart_cached``.
    """
    parsed = _parse_occasion_focus(ctx.focus)
    if parsed is None:
        return None

    occasion_type, start, end = parsed
    candidate_days: list[dict[str, Any]] = []
    cursor = start
    # A user-facing lucky-day window is normally one month. Cap defensively
    # so an accidental long range cannot dominate the model prompt. The
    # ``timedelta(days=61)`` produces exactly 62 inclusive calendar days.
    final_day = min(end, start + timedelta(days=61))
    while cursor <= final_day:
        chart = compute_day_chart_cached(cursor.isoformat(), ctx.timezone)
        day = chart["day"]
        candidate_days.append({
            "date": cursor.isoformat(),
            "day_pillar_stem": day["stem"],
            "day_pillar_branch": day["branch"],
            "stem_element": day["stem_element"],
            "branch_element": day["branch_element"],
        })
        cursor += timedelta(days=1)

    # Repair path: caller wants the full chronological list for date validation.
    if foundation is None:
        return {
            "occasion_type": occasion_type,
            "start": start.isoformat(),
            "end": end.isoformat(),
            "candidate_days": candidate_days,
        }

    # Prefilter path: rank by chart compatibility, take top-21 + sample.
    favored, avoid = occasion_preferences(occasion_type)
    # Defensive parse — log the route with a clear ValueError if a future
    # caller hands us a foundation with a non-canonical day-pillar shape
    # (e.g. CJK string fallback or {"raw": "甲寅"}).
    querent_dm_stem, querent_day_branch = pillar_stem_branch(
        foundation["pillars"]["day"],
    )

    scored: list[tuple[float, dict[str, Any]]] = []
    for cand in candidate_days:
        score = score_candidate_day(
            cand["day_pillar_stem"],
            cand["day_pillar_branch"],
            querent_dm_stem,
            querent_day_branch,
            favored,
            avoid,
        )
        scored.append((score, cand))

    # Top 21 by score (ties broken by chronological order so the model sees
    # earliest-good days first).
    scored_sorted_by_score = sorted(
        scored,
        key=lambda pair: (-pair[0], pair[1]["date"]),
    )
    top_picks = [cand for _score, cand in scored_sorted_by_score[:21]]

    # Coverage sample: from the REMAINDER, take one day per 7-day bucket so
    # the model still sees options spread across the window. Capped at 10.
    remaining = scored_sorted_by_score[21:]
    sample: list[dict[str, Any]] = []
    seen_buckets: set[int] = set()
    # Walk the remainder in date order so bucket selection is deterministic
    # (rather than score order, which would over-represent the start window).
    for cand in sorted([c for _s, c in remaining], key=lambda c: c["date"]):
        cand_date = date.fromisoformat(cand["date"])
        bucket = (cand_date - start).days // 7
        if bucket in seen_buckets:
            continue
        seen_buckets.add(bucket)
        sample.append(cand)
        if len(sample) >= 10:
            break

    # Combine top + sample, deduplicate by date, sort chronologically so
    # the model reads them naturally (the LLM still scores within this set).
    combined: dict[str, dict[str, Any]] = {c["date"]: c for c in top_picks}
    for cand in sample:
        combined.setdefault(cand["date"], cand)
    curated = sorted(combined.values(), key=lambda c: c["date"])

    return {
        "occasion_type": occasion_type,
        "start": start.isoformat(),
        "end": end.isoformat(),
        "candidate_days": curated,
        # Hint to the model about the prefilter — useful for prompt-side
        # tuning and surfaces in the trace_collector for debug.
        "prefilter": {
            "method": "deterministic",
            "total_candidates": len(candidate_days),
            "top_picks": len(top_picks),
            "coverage_sample": len(sample),
            "favored_element": favored,
            "avoid_element": avoid,
        },
    }


def repair_occasion_narrative(
    ctx: FortuneRunContext,
    narrative: dict[str, Any],
) -> dict[str, Any]:
    """Ensure lucky-day picks use real dates from the requested window.

    The LLM provides the interpretation, but date validity is deterministic.
    This keeps the UI from rendering placeholder strings such as "Invalid Date"
    and keeps every pick inside the user-selected window.
    """
    occasion = narrative.get("occasion")
    if not isinstance(occasion, dict):
        return narrative

    window = _build_occasion_window(ctx)
    if not window:
        return narrative

    candidates = window.get("candidate_days") or []
    by_date = {c["date"]: c for c in candidates}
    used: set[str] = set()
    repaired: list[dict[str, Any]] = []

    def _fallback_pick(rank: int, candidate: dict[str, Any]) -> dict[str, Any]:
        return {
            "rank": rank,
            "date": candidate["date"],
            "day_pillar_stem": candidate["day_pillar_stem"],
            "day_pillar_branch": candidate["day_pillar_branch"],
            "score": max(60, 86 - rank * 3),
            "one_line_reason": (
                f"Stable {candidate['stem_element']} and {candidate['branch_element']} timing "
                f"supports this {window['occasion_type']}."
            ),
            "best_hours": ["09:00-11:00", "11:00-13:00"],
            "mechanisms": occasion.get("mechanisms") or [],
        }

    raw_picks = occasion.get("top_picks") or []
    for raw in raw_picks:
        pick = raw.model_dump() if hasattr(raw, "model_dump") else dict(raw)
        candidate = by_date.get(str(pick.get("date", ""))[:10])
        if candidate is None or candidate["date"] in used:
            continue
        pick["date"] = candidate["date"]
        pick["day_pillar_stem"] = candidate["day_pillar_stem"]
        pick["day_pillar_branch"] = candidate["day_pillar_branch"]
        used.add(candidate["date"])
        repaired.append(pick)

    for candidate in candidates:
        if len(repaired) >= 3:
            break
        if candidate["date"] in used:
            continue
        used.add(candidate["date"])
        repaired.append(_fallback_pick(len(repaired) + 1, candidate))

    for idx, pick in enumerate(repaired[:5], start=1):
        pick["rank"] = idx

    occasion["top_picks"] = repaired[:5]
    occasion.setdefault("analysis", {
        "occasion_type": window["occasion_type"],
        "key_elements": [],
        "avoid_elements": [],
        "description": f"Dates are selected from {window['start']} to {window['end']}.",
    })
    narrative["occasion"] = occasion
    return narrative


try:
    from .agent_logging import classify_function, stage as _stage
except ImportError:
    from agent_logging import classify_function, stage as _stage  # type: ignore[no-redef]


async def run_narrative(
    ctx: FortuneRunContext,
    *,
    foundation: dict[str, Any],
    session: Any | None = None,
) -> EnrichedNarrativeOutput:
    """Run the narrative agent (non-streaming) and return structured output.

    Dispatches via ``NARRATIVE_AGENTS[_narrative_mode(ctx)]`` so the
    non-streamed path exercises the same per-mode narrow output schema as
    the streamed production path. The narrow output is promoted back to
    the merged ``EnrichedNarrativeOutput`` via
    :func:`_promote_narrative_to_enriched` so callers see one shape.
    """
    prompt = _build_narrative_prompt(ctx, foundation)
    agent = NARRATIVE_AGENTS[_narrative_mode(ctx)]
    settings = get_settings()
    fn = classify_function(ctx.focus, ctx.question)
    _agent_reasoning = agent.model_settings.reasoning.effort
    with _stage(
        function=fn,
        stage="narrative",
        model=settings.narrative_model,
        reasoning=_agent_reasoning,
        fortune_id=ctx.fortune_id,
        run_id=ctx.run_id,
        agent=agent.name,
        extra={"streamed": "false", "person_b": str("person_b" in foundation).lower()},
    ) as sh:
        kwargs: dict[str, Any] = {
            "input": prompt,
            "context": ctx,
            "run_config": _run_config(ctx),
        }
        if session is not None:
            kwargs["session"] = session
        result = await Runner.run(agent, **kwargs)
        sh.attach_result(result)
    return _promote_narrative_to_enriched(result.final_output)


async def run_narrative_streamed(
    ctx: FortuneRunContext,
    *,
    foundation: dict[str, Any],
    session: Any | None = None,
):
    """Run the narrative agent with streaming. Returns the streamed run result.

    Picks a per-mode agent from ``NARRATIVE_AGENTS`` based on the focus, so
    the bound ``output_type`` is the narrow schema for that mode. The
    ``RawResponsesStreamEvent`` events still flow through unchanged; the
    route handler (which owns the consumption loop) is responsible for
    emitting the structured ``narrative`` log entry on its side. This
    function only runs the SDK call — it does NOT emit a log of its own to
    avoid double-logging. See ``routes.py`` stream loop.

    Note: usage on the returned ``RunResultStreaming`` is stale until the
    stream is fully consumed; the route handler reads it after the loop.
    """
    prompt = _build_narrative_prompt(ctx, foundation)
    agent = NARRATIVE_AGENTS[_narrative_mode(ctx)]
    kwargs: dict[str, Any] = {
        "input": prompt,
        "context": ctx,
        "run_config": _run_config(ctx),
    }
    if session is not None:
        kwargs["session"] = session
    return Runner.run_streamed(agent, **kwargs)


async def run_guardrail(
    ctx: FortuneRunContext,
    *,
    narrative: NarrativeOutput | EnrichedNarrativeOutput,
) -> GuardrailOutput:
    """Run the guardrail agent and return structured output."""
    narrative_payload = (
        narrative.model_dump()
        if hasattr(narrative, "model_dump")
        else narrative
    )
    prompt = json.dumps(
        {
            "focus": ctx.focus,
            "tone": ctx.tone,
            "narrative": narrative_payload,
            "default_buttons": [b.model_dump() for b in DEFAULT_FOLLOW_UP_BUTTONS],
        },
        ensure_ascii=False,
    )
    settings = get_settings()
    fn = classify_function(ctx.focus, ctx.question)
    with _stage(
        function=fn,
        stage="guardrail",
        model=settings.guardrail_model,
        reasoning=settings.guardrail_reasoning,
        fortune_id=ctx.fortune_id,
        run_id=ctx.run_id,
        agent=GUARDRAIL_AGENT.name,
    ) as sh:
        result = await Runner.run(
            GUARDRAIL_AGENT,
            input=prompt,
            context=ctx,
            run_config=_run_config(ctx),
        )
        sh.attach_result(result)
    if isinstance(result.final_output, GuardrailOutput):
        return result.final_output
    return GuardrailOutput.model_validate(result.final_output)
