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

Always reference SPECIFIC computed data from the foundation payload — pillar
stems, ten gods names (e.g. "正官 Direct Officer"), branch interactions — not
generic astrology language. Be concise; more insight per word.
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
    "the spouse palace (day branch), spouse-star presence (正官/七杀 for female "
    "charts, 正财/偏财 for male charts), and interactions touching the day "
    "pillar. Comment on timing windows for partnership via luck/annual "
    "pillars that activate the day branch.\n" + _BASE_OUTPUT_RULES
)

CAREER_FOCUS_INSTRUCTIONS = (
    "You are the career specialist. Interpret career trajectory through the "
    "Officer stars (正官/七杀), Wealth stars (正财/偏财), and Output stars "
    "(食神/伤官). Factor in day-master strength (seasonal_strength) to say "
    "whether the chart favors entrepreneurship vs. institutional roles. Cite "
    "luck-pillar transitions that mark career shifts.\n" + _BASE_OUTPUT_RULES
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


# ---------------------------------------------------------------------------
# Triage agent
# ---------------------------------------------------------------------------

TRIAGE_INSTRUCTIONS = """\
You are the Ming Engine triage router for follow-up questions. Given the
user's intent (``action_id`` and/or free-form ``question``) and the already-
computed BaZi foundation, pick EXACTLY ONE specialist tool and call it, then
return that specialist's output verbatim.

Routing rules:
- action_id is authoritative when present. Map it 1:1:
    deep_dive_element → deep_dive_element tool
    year_forecast → year_forecast tool
    relationship_focus → relationship_focus tool
    career_focus → career_focus tool
    show_sources → show_sources tool
    expand_classics → expand_classics tool
- If only a free-form question is provided, pick the single best-matching
  specialist (prefer career/relationship/year when the question names those
  domains; show_sources when the user asks "where does this come from"; etc).
- Do NOT answer directly. Always delegate to a tool. The specialist's
  EnrichedNarrativeOutput is your final output — pass it through unchanged.

Pass the FULL ``foundation`` JSON you received as the tool input so the
specialist has access to the same data the initial narrative saw.
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

def _build_triage_prompt(
    ctx: FortuneRunContext,
    foundation: dict[str, Any],
    *,
    action_id: str | None,
    question: str | None,
) -> str:
    analysis = foundation.get("analysis")
    payload: dict[str, Any] = {
        "intent": {
            "action_id": action_id,
            "question": question,
            "focus": ctx.focus,
            "tone": ctx.tone,
        },
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
        ctx, foundation, action_id=action_id, question=question,
    )
    kwargs: dict[str, Any] = {
        "input": prompt,
        "context": ctx,
        "run_config": _run_config(ctx),
    }
    if session is not None:
        kwargs["session"] = session
    result = await Runner.run(TRIAGE_AGENT, **kwargs)
    if isinstance(result.final_output, EnrichedNarrativeOutput):
        return result.final_output
    return EnrichedNarrativeOutput.model_validate(result.final_output)
