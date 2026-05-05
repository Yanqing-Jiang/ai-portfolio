"""Triage pattern — route follow-up actions to specialist agents via ``Agent.as_tool()``.

The initial reading path (``NARRATIVE_AGENT``) is one-shot: a single LLM call
produces the full ``EnrichedNarrativeOutput``. Follow-up actions ("Career Deep
Dive", "Explore This Year Luck", …) take a different path: a ``TRIAGE_AGENT``
receives the user's intent plus the already-computed foundation, picks ONE
specialist, and delegates via a tool call.

Why this shape:

* Each specialist has a *narrow* system prompt. Focusing the model on one
  dimension (career / relationships / a specific year) produces denser
  interpretation than a generic "deep dive on X" re-prompt of the narrative
  agent.
* ``Agent.as_tool()`` runs the specialist inside the same parent trace, so
  ``GlassBoxTraceProcessor`` captures both the triage span AND the specialist
  span under the same ``trace_id``. That's what lights up the Activity Rail
  with "triage → deep_dive_element → classical lookup" breadcrumbs.
* The triage agent's output is shaped to the same ``EnrichedNarrativeOutput``
  contract as the initial narrative, so the frontend can render a follow-up
  answer with the same insight-card UI — no second renderer.
"""

from __future__ import annotations

import json
from typing import Any

from agents import Agent, Runner

try:
    from .agents import (
        EnrichedNarrativeOutput,
        FortuneRunContext,
        _model,
        _model_settings,
        _run_config,
    )
except ImportError:
    from agents import (  # type: ignore[no-redef]
        EnrichedNarrativeOutput,
        FortuneRunContext,
        _model,
        _model_settings,
        _run_config,
    )


# ---------------------------------------------------------------------------
# Code-side specialist router (Ask snappiness)
# ---------------------------------------------------------------------------
# The Ask tab originally went through the full triage→specialist chain (TWO
# sequential LLM calls). For a free-form follow-up that the user has
# already grounded in `latest_narrative`, the triage hop is pure overhead —
# its only job is to pick which specialist to call, and the focus prefix +
# a few keyword cues are usually enough to make that call deterministically
# in code. When the heuristic returns a confident match we skip triage
# entirely and dispatch the specialist directly (~half the round trips,
# ~50% latency improvement on simple follow-ups).

import re as _re


# Keyword groups. Phrases use substring matching; *words* (single short
# tokens like "fire", "us", "we", "source") use word-boundary matching to
# avoid false positives ("fired" → fire, "resource" → source).
_CAREER_PHRASES = (
    "career", "job", "promotion", "boss", "salary", "company",
    "office", "raise", "interview", "resign", "quit", "switch jobs",
    "fired", "laid off", "manager",
)
_CAREER_WORDS = ("work",)
_RELATIONSHIP_PHRASES = (
    "relationship", "partner", "marriage", "marry", "spouse", "wife",
    "husband", "girlfriend", "boyfriend", "harmony",
    "between us", "our compatibility", "together",
)
_RELATIONSHIP_WORDS = ("love", "us", "we")
_YEAR_PHRASES = (
    "next year", "decade", "luck", "cycle", "timing",
    "future", "forecast", "next month", "next week",
    "2025", "2026", "2027", "2028", "2029", "2030",
)
_YEAR_WORDS = ("year", "when")
# Order matters: classics specialist is for *expanding/explaining* the
# referenced texts, not for listing sources. So we check classics
# phrases first when both could match.
_CLASSICS_PHRASES = (
    "explain the classic", "classical text", "expand on", "more from",
    "deeper meaning", "philosophy", "tradition", "scripture",
)
_SOURCES_PHRASES = (
    "show me the source", "show the source", "show the references",
    "show me the references", "list the references", "where does this come from",
    "where did you get", "citation",
)
_SOURCES_WORDS = ("source", "sources", "reference", "references", "passage")
_ELEMENT_PHRASES = (
    "element", "five element", "balance", "imbalance",
    "lacking", "dominant",
)
_ELEMENT_WORDS = ("wood", "fire", "earth", "metal", "water")
# Occasion-specific intent: "fit", "best pick", "which day energetically
# fits" → element-balance specialist (per TRIAGE_INSTRUCTIONS). Without
# these, every occasion follow-up falls to year_forecast.
_OCCASION_FIT_PHRASES = (
    "best fit", "best pick", "right day", "energetically fits", "fits me",
    "support me", "good fit", "suit me", "the right one",
)
_OCCASION_FIT_WORDS = ("energy",)
_WHY_PHRASES = ("why", "explain", "interpret", "meaning")


def _has_phrase(q: str, phrases: tuple[str, ...]) -> bool:
    return any(p in q for p in phrases)


def _has_word(q: str, words: tuple[str, ...]) -> bool:
    """Word-boundary match for short tokens to avoid 'fired'→fire,
    'resource'→source false positives."""
    if not q:
        return False
    pattern = r"\b(" + "|".join(_re.escape(w) for w in words) + r")\b"
    return bool(_re.search(pattern, q))


def infer_specialist_action(
    *,
    question: str | None,
    focus: str | None,
    original_input: dict[str, Any] | None = None,
) -> str | None:
    """Pick a specialist action_id deterministically from question + focus.

    Returns ``None`` when no rule fires confidently — caller should fall
    back to the LLM triage agent. The rules mirror the heuristics in
    ``TRIAGE_INSTRUCTIONS`` so behavior stays consistent when the LLM is
    used (the LLM is now the fallback, not the primary path).
    """
    q = (question or "").lower().strip()
    # Allow the original_input.focus to fill in when ctx.focus is missing
    # (TRIAGE_INSTRUCTIONS routes on both signals).
    raw_focus = focus or (original_input or {}).get("focus")
    f = (raw_focus or "").lower().strip()

    # --- Strongest signal: keyword in the question itself ---
    if q:
        # Check classics expansion BEFORE generic sources — "explain the
        # classic" should land on expand_classics, not show_sources.
        if _has_phrase(q, _CLASSICS_PHRASES):
            return "expand_classics"
        if _has_phrase(q, _SOURCES_PHRASES) or _has_word(q, _SOURCES_WORDS):
            return "show_sources"

        # Occasion-specific energetic-fit intent only applies under an
        # occasion focus; otherwise these phrases are generic.
        if f.startswith("occasion:") and (
            _has_phrase(q, _OCCASION_FIT_PHRASES) or _has_word(q, _OCCASION_FIT_WORDS)
        ):
            return "deep_dive_element"

        if _has_phrase(q, _CAREER_PHRASES) or _has_word(q, _CAREER_WORDS):
            return "career_focus"
        if _has_phrase(q, _RELATIONSHIP_PHRASES) or _has_word(q, _RELATIONSHIP_WORDS):
            return "relationship_focus"
        if _has_phrase(q, _ELEMENT_PHRASES) or _has_word(q, _ELEMENT_WORDS):
            return "deep_dive_element"
        if _has_phrase(q, _YEAR_PHRASES) or _has_word(q, _YEAR_WORDS):
            return "year_forecast"

        # Wish / general "why … this … mean?" → expand classics. Per
        # TRIAGE_INSTRUCTIONS, "why" questions on wish or general focus
        # default to expand_classics rather than punting to the LLM.
        if (not f or f.startswith("wish")) and _has_phrase(q, _WHY_PHRASES):
            return "expand_classics"

    # --- Fall back to focus prefix → reasonable specialist default ---
    if f.startswith("compatibility:"):
        return "relationship_focus"
    if f.startswith("luck_cycle:"):
        return "year_forecast"
    if f.startswith("occasion:"):
        return "year_forecast"
    if f.startswith("wish") or f.startswith("compatibility") or f.startswith("luck") or f.startswith("occasion"):
        # tagged but no colon — still better than triage round trip.
        return "expand_classics"

    # No confident rule → caller should defer to LLM triage.
    return None


# ---------------------------------------------------------------------------
# Specialist instructions
# ---------------------------------------------------------------------------
# Each specialist receives the same serialized foundation + intent that the
# triage forwards as a tool-input string. The narrow instructions pull the
# LLM's attention to one dimension.

_BASE_OUTPUT_RULES = """
Output must be an EnrichedNarrativeOutput:
- tldr: 1 sentence, max 20 words, specific to this focus.
- insights: 1-3 sections (prefer 1 rich section over 3 shallow ones). Each
  section has id (snake_case), icon emoji, heading (2-4 words), tagline, and
  2-4 bullets (emoji + <=80 char text). Cite classical reference ids when used.
- year_predictions: only populate if the focus genuinely involves time (year
  forecast, career timing). Otherwise leave empty.

LANGUAGE — STRICT (mandatory, applies to EVERY field of the output):
- Output English ONLY. Do NOT include any Chinese characters (CJK Han) in
  tldr, insights, year_predictions, or any nested string. Zero Chinese.
- When a BaZi concept needs to be named, use ONLY its English form:
  Direct Officer, Seven Killings, Direct Wealth, Indirect Wealth,
  Eating God, Hurt Officer, Direct Resource, Indirect Resource,
  Direct Companion, Rob Wealth; Day Master; Wood / Fire / Earth /
  Metal / Water; Tiger / Rabbit / Dragon / Snake / Horse / Goat /
  Monkey / Rooster / Dog / Pig / Rat / Ox; clash, combination, harm,
  punishment. Never ten-god hanzi, stem hanzi, branch hanzi, or
  pinyin-with-tones in user-facing text.
- If a foundation field arrives with Chinese (e.g. analysis.ten_gods entries
  with `god_chinese`), translate to the English `god` field and drop the
  Chinese. Same for stems and branches: refer to "the Wood Day Master" or
  "the Tiger month branch", never the hanzi.
- Plain language: write at an 8th-grade reading level. Avoid jargon-only
  sentences. If a technical term is unavoidable, briefly gloss it
  parenthetically in plain English ("Hurt Officer (creative output star)").

Always reference SPECIFIC computed data from the foundation payload —
pillar stems (by element + animal, e.g. "the Wood Tiger month"), ten gods
by their English names, branch interactions (clash / combination / harm)
— not generic astrology language. Be concise; more insight per word.

CONTEXT CONTINUITY (mandatory): The prompt includes ``original_input`` (what
the user originally asked when starting this reading: focus, original
question, person_b, occasion window, relationship, horizon) and
``latest_narrative`` (the tldr + insights + verdict the user is currently
looking at on screen). Treat the follow-up as a continuation, not a fresh
reading:
- If the follow-up references "this", "that pick", "the harmony score", "my
  decade", anchor it to ``latest_narrative`` and ``original_input`` rather
  than asking for clarification.
- Do not contradict facts already shown in ``latest_narrative``; refine,
  expand, or qualify them. Cite a specific span (e.g. tldr / a section id /
  a year prediction) when you build on it.
- Echo the user's original constraint when relevant ("for your Oct 12
  wedding window", "between you and your partner born 1992-…").
"""

DEEP_DIVE_ELEMENT_INSTRUCTIONS = (
    "You are the element-balance specialist. Interpret the chart's five-element "
    "distribution in depth: which element dominates, which is deficient, how "
    "seasonal strength modulates the day master, and what practical lifestyle "
    "or environmental tilts would restore balance. Prefer interpretations "
    "grounded in enhanced_element_counts and element_by_source, not the raw "
    "stem count.\n" + _BASE_OUTPUT_RULES
)

YEAR_FORECAST_INSTRUCTIONS = (
    "You are the annual-luck specialist. From the notable_annual_pillars and "
    "luck_pillars, produce year_predictions for the next 3-5 years that have "
    "meaningful interactions with the natal chart (clashes 冲, combinations "
    "合, harms 害). For each year include a concrete theme, confidence based "
    "on interaction strength, and evidence refs. Keep insights tight — the "
    "year_predictions array is the main payload.\n" + _BASE_OUTPUT_RULES
)

RELATIONSHIP_FOCUS_INSTRUCTIONS = (
    "You are the relationships specialist. Read compatibility signals from "
    "the spouse palace (day branch), spouse-star presence (Direct Officer / "
    "Seven Killings for women, Direct Wealth / Indirect Wealth for men), "
    "and interactions touching the day pillar. Comment on timing windows "
    "for partnership via luck-pillar and annual-pillar activations of the "
    "day branch.\n" + _BASE_OUTPUT_RULES
)

CAREER_FOCUS_INSTRUCTIONS = (
    "You are the career specialist. Interpret career trajectory through "
    "the Officer stars (Direct Officer, Seven Killings), Wealth stars "
    "(Direct Wealth, Indirect Wealth), and Output stars (Eating God, "
    "Hurt Officer). Factor in day-master strength (seasonal_strength) to "
    "say whether the chart favors entrepreneurship vs. institutional "
    "roles. Cite luck-pillar transitions that mark career shifts.\n"
    + _BASE_OUTPUT_RULES
)

SHOW_SOURCES_INSTRUCTIONS = (
    "You are the sources specialist. Return a single insight section that "
    "lists the classical references already retrieved in the foundation "
    "payload, each with its passage, translation, source title, and a one-"
    "line relevance note tied to THIS chart. Do not invent passages. If the "
    "references list is empty, say so in the tagline.\n" + _BASE_OUTPUT_RULES
)

EXPAND_CLASSICS_INSTRUCTIONS = (
    "You are the classics-expansion specialist. Pick the 1-2 most relevant "
    "classical references from the foundation payload and expand each into a "
    "bullet-rich section: what the passage says, why it applies to THIS "
    "chart's stems/branches, and how the user might apply it. Always cite "
    "the reference id in the section's citations list.\n" + _BASE_OUTPUT_RULES
)


# ---------------------------------------------------------------------------
# Specialist agents
# ---------------------------------------------------------------------------

def _build_specialist(name: str, instructions: str) -> Agent[FortuneRunContext]:
    return Agent(
        name=name,
        model=_model("narrative_model"),
        model_settings=_model_settings("narrative_reasoning"),
        instructions=instructions,
        output_type=EnrichedNarrativeOutput,
    )


DEEP_DIVE_ELEMENT_AGENT = _build_specialist(
    "fortune_deep_dive_element", DEEP_DIVE_ELEMENT_INSTRUCTIONS,
)
YEAR_FORECAST_AGENT = _build_specialist(
    "fortune_year_forecast", YEAR_FORECAST_INSTRUCTIONS,
)
RELATIONSHIP_FOCUS_AGENT = _build_specialist(
    "fortune_relationship_focus", RELATIONSHIP_FOCUS_INSTRUCTIONS,
)
CAREER_FOCUS_AGENT = _build_specialist(
    "fortune_career_focus", CAREER_FOCUS_INSTRUCTIONS,
)
SHOW_SOURCES_AGENT = _build_specialist(
    "fortune_show_sources", SHOW_SOURCES_INSTRUCTIONS,
)
EXPAND_CLASSICS_AGENT = _build_specialist(
    "fortune_expand_classics", EXPAND_CLASSICS_INSTRUCTIONS,
)


SPECIALISTS: dict[str, Agent[FortuneRunContext]] = {
    "deep_dive_element": DEEP_DIVE_ELEMENT_AGENT,
    "year_forecast": YEAR_FORECAST_AGENT,
    "relationship_focus": RELATIONSHIP_FOCUS_AGENT,
    "career_focus": CAREER_FOCUS_AGENT,
    "show_sources": SHOW_SOURCES_AGENT,
    "expand_classics": EXPAND_CLASSICS_AGENT,
}


_SPECIALIST_INSTRUCTIONS: dict[str, str] = {
    "deep_dive_element": DEEP_DIVE_ELEMENT_INSTRUCTIONS,
    "year_forecast": YEAR_FORECAST_INSTRUCTIONS,
    "relationship_focus": RELATIONSHIP_FOCUS_INSTRUCTIONS,
    "career_focus": CAREER_FOCUS_INSTRUCTIONS,
    "show_sources": SHOW_SOURCES_INSTRUCTIONS,
    "expand_classics": EXPAND_CLASSICS_INSTRUCTIONS,
}


# Ask-tuned mirrors: same instructions but cheaper/faster reasoning effort.
# Used by /ask for follow-up turns where the latest_narrative + foundation
# already provide most of the grounding the LLM needs. The mirror dict is
# constructed lazily once (module import time after specialists exist) so
# we keep one Agent instance per action_id rather than rebuilding per call.
_ASK_SPECIALISTS: dict[str, Agent[FortuneRunContext]] = {
    action_id: Agent(
        name=f"fortune_{action_id}_ask",
        model=_model("narrative_model"),
        model_settings=_model_settings("ask_reasoning"),
        instructions=_SPECIALIST_INSTRUCTIONS[action_id],
        output_type=EnrichedNarrativeOutput,
    )
    for action_id in SPECIALISTS
}


def _resolve_specialist(action_id: str, *, ask_mode: bool) -> Agent[FortuneRunContext]:
    if ask_mode:
        return _ASK_SPECIALISTS.get(action_id) or SPECIALISTS[action_id]
    return SPECIALISTS[action_id]

ACTION_FOCUS: dict[str, str] = {
    "deep_dive_element": "element_balance",
    "year_forecast": "year",
    "relationship_focus": "relationship",
    "career_focus": "career",
    "show_sources": "sources",
    "expand_classics": "classics",
}

if set(ACTION_FOCUS) != set(SPECIALISTS):
    raise RuntimeError("fortune action registry drifted from specialist registry")

ALLOWED_ACTION_IDS = frozenset(SPECIALISTS)


def normalize_action_focus(action_id: str) -> str | None:
    return ACTION_FOCUS.get(action_id)


# ---------------------------------------------------------------------------
# Triage agent
# ---------------------------------------------------------------------------

TRIAGE_INSTRUCTIONS = """\
You are the Ming Engine triage router for follow-up questions. Given the
user's intent (``action_id`` and/or free-form ``question``), the original
inputs they provided when starting this reading (``original_input``), the
narrative they are currently looking at (``latest_narrative``), and the
already-computed BaZi foundation, pick EXACTLY ONE specialist tool and call
it, then return that specialist's output verbatim.

Routing rules:
- action_id is authoritative when present. Map it 1:1:
    deep_dive_element → deep_dive_element tool
    year_forecast → year_forecast tool
    relationship_focus → relationship_focus tool
    career_focus → career_focus tool
    show_sources → show_sources tool
    expand_classics → expand_classics tool
- If only a free-form question is provided, infer specialist from BOTH the
  follow-up question AND ``original_input.focus``. Heuristics:
    * focus starts with "compatibility:" → relationship_focus by default.
    * focus starts with "occasion:" → year_forecast (timing) or
      deep_dive_element (which day energetically fits) depending on intent.
    * focus starts with "luck_cycle:" → year_forecast.
    * wish/general — match the follow-up keywords (career/relationship/year)
      and fall back to expand_classics for "why" questions.
- Do NOT answer directly. Always delegate to a tool. The specialist's
  EnrichedNarrativeOutput is your final output — pass it through unchanged.

Pass the FULL JSON payload you received (foundation + original_input +
latest_narrative + intent) as the tool input so the specialist has access
to the same context — don't strip anything.
"""


def _build_triage_agent() -> Agent[FortuneRunContext]:
    tools = [
        agent.as_tool(
            tool_name=action_id,
            tool_description=(
                f"Specialist that produces a focused EnrichedNarrativeOutput for "
                f"the '{action_id}' intent. Input: JSON string with keys "
                f"{{intent, foundation}} — pass through the foundation unchanged."
            ),
        )
        for action_id, agent in SPECIALISTS.items()
    ]
    return Agent(
        name="fortune_triage",
        model=_model("narrative_model"),
        model_settings=_model_settings("narrative_reasoning"),
        instructions=TRIAGE_INSTRUCTIONS,
        tools=tools,
        output_type=EnrichedNarrativeOutput,
    )


TRIAGE_AGENT: Agent[FortuneRunContext] = _build_triage_agent()


# ---------------------------------------------------------------------------
# Pipeline function
# ---------------------------------------------------------------------------

def _build_original_input(ctx: FortuneRunContext, request_obj: Any | None) -> dict[str, Any]:
    """Project the original create-fortune input into a compact dict for the
    triage prompt. Parses ``focus`` into structured parts so the LLM doesn't
    have to re-tokenise it.

    ``request_obj`` is the live ``FortuneSession.request`` (CreateFortuneRequest)
    when present; falls back to ``ctx`` fields from the hydrated path.
    """
    focus = (ctx.focus or "")
    parts = focus.split(":")
    parsed: dict[str, Any] = {}
    if focus.startswith("compatibility:") and len(parts) >= 2:
        parsed = {"kind": "compatibility", "relationship": parts[1] or "unspecified"}
    elif focus.startswith("occasion:") and len(parts) >= 4:
        parsed = {
            "kind": "occasion",
            "occasion_type": parts[1],
            "window_start_iso": parts[2],
            "window_end_iso": parts[3],
        }
    elif focus.startswith("luck_cycle:") and len(parts) >= 3:
        parsed = {
            "kind": "luck_cycle",
            "luck_focus": parts[1],
            "horizon": parts[2],
        }
    elif focus:
        parsed = {"kind": "wish", "tag": focus}
    else:
        parsed = {"kind": "general"}

    out: dict[str, Any] = {
        "birth_iso": ctx.birth_iso or None,
        "timezone": ctx.timezone or None,
        "gender": ctx.gender or None,
        "birth_time_unknown": bool(getattr(ctx, "birth_time_unknown", False)),
        "focus_raw": ctx.focus,
        "focus_parsed": parsed,
        "original_question": ctx.question,
        "tone": ctx.tone,
    }
    if request_obj is not None and getattr(request_obj, "person_b", None):
        pb = request_obj.person_b
        out["person_b"] = {
            "birth_iso": getattr(pb, "birth_iso", None),
            "timezone": getattr(pb, "timezone", None),
            "gender": getattr(pb, "gender", None),
            "birth_time_unknown": bool(getattr(pb, "birth_time_unknown", False)),
            "name": getattr(pb, "name", None),
        }
    return out


def _project_latest_narrative(latest: dict[str, Any] | None) -> dict[str, Any] | None:
    """Trim a stored ``latest_narrative`` down to what the specialist needs to
    stay consistent with what the user is currently looking at. Drops large
    sub-blocks (compatibility.mechanisms, occasion.calendar) that are already
    represented in foundation; keeps the human-facing tldr, insights and
    function-specific verdict/headline.
    """
    if not latest:
        return None
    keep = {
        "tldr": latest.get("tldr"),
        "insights": latest.get("insights"),
        "year_predictions": latest.get("year_predictions"),
    }
    for fn_block in ("wish", "occasion", "luck_cycle", "compatibility"):
        block = latest.get(fn_block)
        if not block:
            continue
        slim: dict[str, Any] = {}
        # Common headline fields across function blocks.
        for k in ("verdict", "headline", "tldr", "score", "overview", "anchor"):
            if k in block:
                slim[k] = block[k]
        # Top picks for occasion — only top 3 to bound size.
        if fn_block == "occasion" and isinstance(block.get("top_picks"), list):
            slim["top_picks"] = block["top_picks"][:3]
        if fn_block == "compatibility" and isinstance(block.get("overview"), dict):
            slim["overview"] = block["overview"]
        if slim:
            keep[fn_block] = slim
    return {k: v for k, v in keep.items() if v}


def _build_triage_prompt(
    ctx: FortuneRunContext,
    foundation: dict[str, Any],
    *,
    action_id: str | None,
    question: str | None,
    original_input: dict[str, Any] | None = None,
    latest_narrative: dict[str, Any] | None = None,
) -> str:
    analysis = foundation.get("analysis")
    payload: dict[str, Any] = {
        "intent": {
            "action_id": action_id,
            "question": question,
            "focus": ctx.focus,
            "tone": ctx.tone,
        },
        "original_input": original_input or {},
        "latest_narrative": _project_latest_narrative(latest_narrative),
        "foundation": {
            "pillars": foundation.get("pillars"),
            "elements": foundation["elements"].model_dump()
                if hasattr(foundation.get("elements"), "model_dump")
                else foundation.get("elements"),
            "references": [
                r.model_dump() if hasattr(r, "model_dump") else r
                for r in foundation.get("references", [])
            ],
        },
    }
    if analysis is not None:
        payload["foundation"].update({
            "hidden_stems": {
                k: [s.model_dump() for s in v]
                for k, v in analysis.hidden_stems.items()
            },
            "ten_gods": [tg.model_dump() for tg in analysis.ten_gods],
            "interactions": [ix.model_dump() for ix in analysis.interactions],
            "seasonal_strength": analysis.seasonal_strength.model_dump(),
            "enhanced_element_counts": analysis.enhanced_element_counts,
            # deep_dive_element instructions cite element_by_source explicitly,
            # so we must expose it alongside enhanced_element_counts.
            "element_by_source": analysis.element_by_source,
            "harmony_score": analysis.harmony_score,
        })
        if analysis.luck_pillars:
            payload["foundation"]["luck_pillars"] = [
                lp.model_dump() for lp in analysis.luck_pillars[:4]
            ]
        if analysis.annual_pillars:
            payload["foundation"]["notable_annual_pillars"] = [
                ap.model_dump() for ap in analysis.annual_pillars
                if ap.interactions_with_chart
            ][:20]
    return json.dumps(payload, ensure_ascii=False)


async def run_triage(
    ctx: FortuneRunContext,
    *,
    foundation: dict[str, Any],
    action_id: str | None = None,
    question: str | None = None,
    session: Any | None = None,
    original_input: dict[str, Any] | None = None,
    latest_narrative: dict[str, Any] | None = None,
    ask_mode: bool = False,
) -> EnrichedNarrativeOutput:
    """Invoke the triage agent; returns the chosen specialist's output.

    Spans emitted by the SDK (triage agent start/end, tool call, specialist
    agent start/end, LLM generation) all land in ``fortune_trace`` via the
    GlassBoxTraceProcessor under a single ``trace_id`` — so the Activity Rail
    can render the full delegation chain.

    ``session`` (optional): when provided (typically a ``SQLAlchemySession``
    from ``fortune.session_store.get_ask_session``), the SDK persists turn
    history under ``session_id`` and replays it on subsequent calls — giving
    the Ask tab continuity without re-sending prior Q&A. Compaction is
    governed by the session's ``SessionSettings(limit=…)``.
    """
    prompt = _build_triage_prompt(
        ctx,
        foundation,
        action_id=action_id,
        question=question,
        original_input=original_input,
        latest_narrative=latest_narrative,
    )
    kwargs: dict[str, Any] = {
        "input": prompt,
        "context": ctx,
        "run_config": _run_config(ctx),
    }
    if session is not None:
        kwargs["session"] = session

    try:
        from .agent_logging import classify_function, stage as _stage
        from .config import get_settings
    except ImportError:
        from agent_logging import classify_function, stage as _stage  # type: ignore[no-redef]
        from config import get_settings  # type: ignore[no-redef]

    settings = get_settings()
    fn = classify_function(ctx.focus, ctx.question or question)

    # Fast path: if action_id is missing but the heuristic router can
    # confidently pick a specialist from the focus + free-form question,
    # promote it. This skips the triage LLM round trip entirely (~50%
    # latency cut on the Ask tab) while preserving the structured output
    # contract the FE expects.
    inferred = action_id
    routed_via = "explicit_action_id"
    if inferred is None and (question or ctx.question):
        candidate = infer_specialist_action(
            question=question or ctx.question,
            focus=ctx.focus,
            original_input=original_input,
        )
        if candidate is not None:
            inferred = candidate
            routed_via = "code_router"

    if inferred:
        if inferred not in SPECIALISTS:
            raise ValueError(f"Unsupported action_id: {inferred}")
        specialist = _resolve_specialist(inferred, ask_mode=ask_mode)
        # Effective reasoning effort for the trace label.
        effective_reasoning = (
            settings.ask_reasoning if ask_mode else settings.narrative_reasoning
        )
        with _stage(
            function=fn,
            stage="direct_dispatch",
            model=settings.narrative_model,
            reasoning=effective_reasoning,
            fortune_id=ctx.fortune_id,
            run_id=ctx.run_id,
            agent=specialist.name,
            extra={
                "action_id": inferred,
                "routed_via": routed_via,
                "ask_mode": "true" if ask_mode else "false",
                "has_question": "true" if (question or ctx.question) else "false",
                "has_session": "true" if session is not None else "false",
            },
        ) as sh:
            result = await Runner.run(specialist, **kwargs)
            sh.attach_result(result)
        if isinstance(result.final_output, EnrichedNarrativeOutput):
            return result.final_output
        return EnrichedNarrativeOutput.model_validate(result.final_output)

    with _stage(
        function=fn,
        stage="triage",
        model=settings.narrative_model,
        reasoning=settings.narrative_reasoning,
        fortune_id=ctx.fortune_id,
        run_id=ctx.run_id,
        agent=TRIAGE_AGENT.name,
        extra={
            "action_id": action_id or "-",
            "has_question": "true" if (question or ctx.question) else "false",
            "has_session": "true" if session is not None else "false",
        },
    ) as sh:
        result = await Runner.run(TRIAGE_AGENT, **kwargs)
        sh.attach_result(result)
    if isinstance(result.final_output, EnrichedNarrativeOutput):
        return result.final_output
    return EnrichedNarrativeOutput.model_validate(result.final_output)
