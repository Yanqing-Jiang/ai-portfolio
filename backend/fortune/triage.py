"""Single session-aware agent for Ask turns and follow-up actions."""

from __future__ import annotations

import json
from typing import Any

from agents import Agent, Runner

try:
    from .agent_logging import classify_function, stage as _stage
    from .agents import (
        EnrichedNarrativeOutput,
        FortuneRunContext,
        NARRATIVE_MAX_TURNS,
        _model,
        _model_settings,
        _run_config,
    )
    from .config import get_settings
    from .naming import canonical_function
except ImportError:  # pragma: no cover
    from agent_logging import classify_function, stage as _stage  # type: ignore[no-redef]
    from agents import (  # type: ignore[no-redef]
        EnrichedNarrativeOutput,
        FortuneRunContext,
        NARRATIVE_MAX_TURNS,
        _model,
        _model_settings,
        _run_config,
    )
    from config import get_settings  # type: ignore[no-redef]
    from naming import canonical_function  # type: ignore[no-redef]


ACTION_FOCUS: dict[str, str] = {
    "deep_dive_element": "element_balance",
    "year_forecast": "year",
    "relationship_focus": "relationship",
    "career_focus": "career",
    "show_sources": "sources",
    "expand_classics": "classics",
}
ALLOWED_ACTION_IDS = frozenset(ACTION_FOCUS)


def normalize_action_focus(action_id: str) -> str | None:
    return ACTION_FOCUS.get(action_id)


ASK_INSTRUCTIONS = """\
You are the single follow-up agent for a completed Ming Engine reading. Answer
the current intent as a continuation of the reading, using the supplied
foundation, original input, latest narrative, and conversation session.

The payload includes `function`, one of four canonical contexts:
- wish: answer the user's wish/question; explain chart evidence and practical
  timing without pretending certainty.
- cycle: explain luck pillars and annual timing. Populate year_predictions only
  when the question or action asks about time.
- compatibility: reason about both people, their day pillars, element balance,
  interactions, relationship context, and the existing compatibility verdict.
- occasion: compare only dates in the supplied occasion window/top picks and
  explain why a candidate fits. Never invent or move a date.

An optional action_id is just a prompt: deep_dive_element emphasizes computed
element balance; year_forecast emphasizes timing; relationship_focus emphasizes
partnership; career_focus emphasizes Officer/Wealth/Output signals; show_sources
lists only supplied references; expand_classics explains supplied references or,
if none exist, chart structure without fabricating a citation. Free-form Ask
questions need no routing—answer the question directly.

Output one EnrichedNarrativeOutput:
- tldr: one specific sentence, at most 20 words.
- insights: 1-3 dense sections with snake_case id, emoji icon, short heading,
  tagline, and 2-4 concise bullets. Cite supplied reference ids when used.
- year_predictions: empty unless timing is genuinely relevant.

Continuity is mandatory. Resolve words such as "this", "that date", "us", or
"my decade" from the latest narrative, original input, and prior session turns.
When `intent.selected_section` is present, treat that trusted server projection
as the primary referent for words such as "this section" while still using the
full reading for supporting evidence.
Refine or qualify earlier claims; do not silently contradict them. Ground every
answer in specific computed stems/elements/animals, ten gods, seasonal strength,
or branch interactions from the foundation.

Use the stored reading_brief and computed Zi Wei chart when present. Legacy
readings without Zi Wei data cannot support palace/star claims. Keep the two
systems' evidence distinct and preserve disagreement. No invented chart facts.
Main prose must describe life opportunities, possible turning points and actions,
not technical terms. Lead with supported years/ages when relevant, using only
stored age_at_birthday values (Person A; age turning during each calendar year).
Do not infer an exact event, new age, or unsupported timing from nominal Zi Wei ages.
Technical terms belong only in a requested explanation of the chart or sources.
Do not present a past prediction as an observed fact about the user's life.

Write English only, at an 8th-grade reading level. Never emit CJK characters.
Use English BaZi terms (Day Master, Direct Officer, Seven Killings, Direct or
Indirect Wealth/Resource, Eating God, Hurt Officer, Rob Wealth; Wood, Fire,
Earth, Metal, Water; animal names; clash, combination, harm, punishment).
Fortune guidance is reflective, not deterministic medical, legal, or financial
advice.
"""


ASK_AGENT: Agent[FortuneRunContext] = Agent(
    name="fortune_ask",
    model=_model("narrative_model"),
    model_settings=_model_settings("ask_reasoning", "ask_max_tokens"),
    instructions=ASK_INSTRUCTIONS,
    output_type=EnrichedNarrativeOutput,
)


def _jsonable(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if isinstance(value, dict):
        return {key: _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    return value


def _project_foundation(foundation: dict[str, Any]) -> dict[str, Any]:
    """Keep the same computed reading context while dropping live trace objects."""
    keep = {
        key: value
        for key, value in foundation.items()
        if key not in {"trace"}
    }
    return _jsonable(keep)


def _project_latest_narrative(latest: dict[str, Any] | None) -> dict[str, Any] | None:
    if not latest:
        return None
    projected = {
        "tldr": latest.get("tldr"),
        "insights": latest.get("insights"),
        "year_predictions": latest.get("year_predictions"),
    }
    for block_name in ("wish", "occasion", "luck_cycle", "compatibility"):
        if latest.get(block_name):
            projected[block_name] = latest[block_name]
    return {key: _jsonable(value) for key, value in projected.items() if value}


def _project_selected_section(
    locator: dict[str, Any] | None,
    latest: dict[str, Any] | None,
) -> dict[str, Any] | None:
    """Resolve an allowlisted client locator against trusted narrative data."""
    if not locator:
        return None
    section_id = locator.get("section_id")
    if not isinstance(section_id, str):
        return None

    projected = _project_latest_narrative(latest) or {}
    field_paths = {
        "verdict": ("wish", "verdict"),
        "anchor": ("wish", "anchors"),
        "now": ("luck_cycle", "current_window"),
        "timeline": (None, "year_predictions"),
        "overview": ("compatibility", "overview"),
        "pillars": ("compatibility", "pair_interactions"),
        "top_picks": ("occasion", "top_picks"),
        "calendar": ("occasion", "top_picks"),
    }
    selection_id = locator.get("selection_id")
    resolved_selection: str | None = None

    if section_id == "why":
        mechanisms = []
        for block_name in ("wish", "luck_cycle", "compatibility", "occasion"):
            block = projected.get(block_name)
            if isinstance(block, dict) and block.get("mechanisms"):
                value = block["mechanisms"]
                mechanisms.extend(value if isinstance(value, list) else [value])
        data = mechanisms or None
    else:
        path = field_paths.get(section_id)
        if path is None:
            data = None
        else:
            block_name, field_name = path
            parent = projected if block_name is None else projected.get(block_name)
            data = parent.get(field_name) if isinstance(parent, dict) else None

    # A selection locator is accepted only when it resolves against trusted
    # server output. The browser never supplies the selected content itself.
    if isinstance(selection_id, str) and isinstance(data, list):
        match = next((
            item for item in data
            if isinstance(item, dict) and any(
                str(item.get(key)) == selection_id
                for key in ("id", "date", "rank")
                if item.get(key) is not None
            )
        ), None)
        if match is not None:
            data = match
            resolved_selection = selection_id

    result: dict[str, Any] = {"section_id": section_id}
    if resolved_selection is not None:
        result["selection_id"] = resolved_selection
    if data:
        result["data"] = data
    return result


def _build_triage_prompt(
    ctx: FortuneRunContext,
    foundation: dict[str, Any],
    *,
    action_id: str | None,
    question: str | None,
    original_input: dict[str, Any] | None = None,
    latest_narrative: dict[str, Any] | None = None,
    selected_section: dict[str, Any] | None = None,
) -> str:
    """Serialize stable reading context first for prompt-cache reuse."""
    stored_function = (original_input or {}).get("function_id")
    function_id = (
        stored_function
        if stored_function in {"wish", "cycle", "compatibility", "occasion"}
        else canonical_function(ctx.focus, ctx.question or question) or "wish"
    )
    payload = {
        "foundation": _project_foundation(foundation),
        "original_input": _jsonable(original_input or {}),
        "latest_narrative": _project_latest_narrative(latest_narrative),
        "function": function_id,
        "intent": {
            "action_id": action_id,
            "question": question or ctx.question,
            "focus": ctx.focus,
            "tone": ctx.tone,
            "selected_section": _project_selected_section(
                selected_section, latest_narrative,
            ),
        },
    }
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
    selected_section: dict[str, Any] | None = None,
    ask_mode: bool = False,
) -> EnrichedNarrativeOutput:
    """Run the one Ask/action agent, with SQLAlchemySession as sole memory."""
    if action_id is not None and action_id not in ALLOWED_ACTION_IDS:
        raise ValueError(f"Unsupported action_id: {action_id}")
    prompt = _build_triage_prompt(
        ctx,
        foundation,
        action_id=action_id,
        question=question,
        original_input=original_input,
        latest_narrative=latest_narrative,
        selected_section=selected_section,
    )
    kwargs: dict[str, Any] = {
        "input": prompt,
        "context": ctx,
        "run_config": _run_config(ctx),
    }
    if session is not None:
        kwargs["session"] = session

    settings = get_settings()
    stored_function = (original_input or {}).get("function_id")
    fn = (
        stored_function
        if stored_function in {"wish", "cycle", "compatibility", "occasion"}
        else canonical_function(ctx.focus, ctx.question or question) or classify_function(
            ctx.focus, ctx.question or question,
        )
    )
    with _stage(
        function=fn,
        stage="ask" if ask_mode else "direct_dispatch",
        model=settings.narrative_model,
        reasoning=settings.ask_reasoning,
        fortune_id=ctx.fortune_id,
        run_id=ctx.run_id,
        agent=ASK_AGENT.name,
        extra={
            "action_id": action_id or "free_form",
            "function_context": fn,
            "has_session": str(session is not None).lower(),
        },
    ) as sh:
        result = await Runner.run(
            ASK_AGENT, max_turns=NARRATIVE_MAX_TURNS, **kwargs,
        )
        sh.attach_result(result)
    from .insight_harness import validate_narrative_years
    narrative = EnrichedNarrativeOutput.model_validate(result.final_output)
    return validate_narrative_years(ctx, foundation, narrative)
