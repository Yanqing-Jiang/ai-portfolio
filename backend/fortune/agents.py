"""Ming Engine agent pipeline: 5 OpenAI Agents SDK agents with structured outputs."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from agents import Agent, Runner
from pydantic import BaseModel, Field

try:
    from .calendar_tool import compute_bazi_chart, compute_bazi_chart_tool
    from .classics import retrieve_classical_references, retrieve_classical_references_tool
    from .config import get_settings
except ImportError:
    from calendar_tool import compute_bazi_chart, compute_bazi_chart_tool  # type: ignore[no-redef]
    from classics import retrieve_classical_references, retrieve_classical_references_tool  # type: ignore[no-redef]
    from config import get_settings  # type: ignore[no-redef]


# ---------------------------------------------------------------------------
# Run context
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class FortuneRunContext:
    fortune_id: str
    surface_id: str
    question: str | None = None
    focus: str | None = None
    tone: str | None = None
    birth_iso: str = ""
    timezone: str = "UTC"
    birth_time_unknown: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


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


class NarrativeSection(BaseModel):
    id: str
    heading: str
    content: str
    type: str
    citations: list[str] = Field(default_factory=list)


class NarrativeOutput(BaseModel):
    sections: list[NarrativeSection]


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
You are the Ming Engine narrative interpreter. Compose a personalized BaZi \
reading based on the user's Four Pillars chart, element balance, and classical references.

- Use the user-requested tone if provided.
- Section types: overview, career, relationship, timing, advice, health, wealth, year.
- Cite only from the supplied classical references by their id.
- Be interpretive and reflective, not deterministic or absolute.
- Each section should have a clear heading and substantive content.
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


INTAKE_AGENT: Agent[FortuneRunContext] = Agent(
    name="fortune_intake",
    model=_model("intake_model"),
    instructions=(
        "Clarify the user intent for a BaZi reading. "
        "Summarize requested focus, tone, and any missing optional details."
    ),
)

CHART_AGENT: Agent[FortuneRunContext] = Agent(
    name="fortune_chart",
    model=_model("chart_model"),
    instructions=(
        "Use the chart tool to compute Four Pillars data. "
        "Explain what the raw element counts imply for downstream interpretation."
    ),
    tools=[compute_bazi_chart_tool],
)

CLASSICS_AGENT: Agent[FortuneRunContext] = Agent(
    name="fortune_classics",
    model=_model("classics_model"),
    instructions=(
        "Use the classics retrieval tool to find concise, relevant textual "
        "support for the current reading focus."
    ),
    tools=[retrieve_classical_references_tool],
)

NARRATIVE_AGENT: Agent[FortuneRunContext] = Agent(
    name="fortune_narrative",
    model=_model("narrative_model"),
    instructions=NARRATIVE_INSTRUCTIONS,
    output_type=NarrativeOutput,
)

GUARDRAIL_AGENT: Agent[FortuneRunContext] = Agent(
    name="fortune_guardrail",
    model=_model("guardrail_model"),
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
    """Deterministic foundation: chart + element enrichment + classical retrieval.

    No LLM calls — this is pure Python computation.
    """
    chart = compute_bazi_chart(
        ctx.birth_iso,
        timezone=ctx.timezone,
        birth_time_unknown=ctx.birth_time_unknown,
    )

    elements = enrich_element_balance(
        chart["raw_element_counts"],
        chart["day_master_element"],
    )

    query_parts = [
        ctx.question,
        ctx.focus,
        ctx.tone,
        chart["day_master_element"],
    ]
    retrieval_query = " ".join(p for p in query_parts if p) or "general bazi reading"
    references = [
        ClassicalReference(**item)
        for item in retrieve_classical_references(retrieval_query)
    ]

    return {
        "pillars": chart,
        "elements": elements,
        "references": references,
    }


async def run_narrative(
    ctx: FortuneRunContext,
    *,
    foundation: dict[str, Any],
) -> NarrativeOutput:
    """Run the narrative agent (non-streaming) and return structured output."""
    prompt = json.dumps(
        {
            "focus": ctx.focus,
            "tone": ctx.tone,
            "question": ctx.question,
            "pillars": foundation["pillars"],
            "elements": foundation["elements"].model_dump(),
            "references": [r.model_dump() for r in foundation["references"]],
        },
        ensure_ascii=False,
    )
    result = await Runner.run(
        NARRATIVE_AGENT,
        input=prompt,
        context=ctx,
    )
    if isinstance(result.final_output, NarrativeOutput):
        return result.final_output
    return NarrativeOutput.model_validate(result.final_output)


async def run_narrative_streamed(
    ctx: FortuneRunContext,
    *,
    foundation: dict[str, Any],
):
    """Run the narrative agent with streaming. Returns the streamed run result."""
    prompt = json.dumps(
        {
            "focus": ctx.focus,
            "tone": ctx.tone,
            "question": ctx.question,
            "pillars": foundation["pillars"],
            "elements": foundation["elements"].model_dump(),
            "references": [r.model_dump() for r in foundation["references"]],
        },
        ensure_ascii=False,
    )
    return Runner.run_streamed(
        NARRATIVE_AGENT,
        input=prompt,
        context=ctx,
    )


async def run_guardrail(
    ctx: FortuneRunContext,
    *,
    narrative: NarrativeOutput,
) -> GuardrailOutput:
    """Run the guardrail agent and return structured output."""
    prompt = json.dumps(
        {
            "focus": ctx.focus,
            "tone": ctx.tone,
            "sections": [s.model_dump() for s in narrative.sections],
            "default_buttons": [b.model_dump() for b in DEFAULT_FOLLOW_UP_BUTTONS],
        },
        ensure_ascii=False,
    )
    result = await Runner.run(
        GUARDRAIL_AGENT,
        input=prompt,
        context=ctx,
    )
    if isinstance(result.final_output, GuardrailOutput):
        return result.final_output
    return GuardrailOutput.model_validate(result.final_output)
