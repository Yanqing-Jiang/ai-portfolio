"""
AI Brief Agent for the /consult intake chat (Phase 2).

A guided, scope-locked interviewer that turns a prospect's answers into a
structured project brief, then routes into the existing booking flow. It reuses
the backend's existing Anthropic client/key config pattern (CLAUDE_API_KEY, the
same env var conversational_analytics uses; falls back to ANTHROPIC_API_KEY).

Design:
- Stateless per turn: the frontend holds the transcript and sends it each call.
- Structured output via a forced `submit_turn` tool — so every turn returns both
  the assistant's reply AND the updated brief. (Forced tool_choice is incompatible
  with extended thinking, so thinking is disabled — which also keeps latency low.)
- Fire-safe: any failure raises; the endpoint degrades to the guided form.

Called from: backend.main (POST /api/intake/message)
"""
from __future__ import annotations

import json
import logging
import os
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Latest Claude Sonnet — good default for a low-latency structured interviewer.
# Overridable per-deploy; the bare alias is complete (no date suffix).
INTAKE_MODEL = os.getenv("INTAKE_MODEL", "claude-sonnet-5")
INTAKE_MAX_TOKENS = int(os.getenv("INTAKE_MAX_TOKENS", "1024"))

# The key comes from the same mechanism the backend already uses. If neither is
# set, the endpoint flags it and the frontend falls back to the form.
def _api_key() -> str:
    return os.getenv("CLAUDE_API_KEY") or os.getenv("ANTHROPIC_API_KEY") or ""


_client = None


def _get_client():
    """Lazy-init a shared Anthropic client (sync). Returns None if unconfigured
    or the package is missing — callers must handle None."""
    global _client
    if _client is not None:
        return _client
    key = _api_key()
    if not key:
        logger.warning("[INTAKE] No CLAUDE_API_KEY/ANTHROPIC_API_KEY — intake agent disabled")
        return None
    try:
        import anthropic
        _client = anthropic.Anthropic(api_key=key)
        return _client
    except Exception as exc:  # pragma: no cover
        logger.error("[INTAKE] Failed to init Anthropic client: %s", exc)
        return None


def intake_available() -> bool:
    return bool(_api_key())


# ---------------------------------------------------------------------------
# Scope-locked system prompts
# ---------------------------------------------------------------------------

_SHARED_GUARDRAILS = """
You are the intake agent for yanqing.app — Yanqing Jiang's AI-agent-system practice.
Your ONLY job is to interview a prospect and produce a structured project brief, so
Yanqing walks into the first conversation already understanding the problem.

Hard rules (never break):
- Stay strictly on consult intake. If asked anything off-topic (general chit-chat,
  coding help, how-tos, opinions), briefly decline and steer back to the intake.
- Do NOT do free technical consulting. If the prospect asks you to design/solve/architect
  their system now, say that's exactly what the paid session / scoped build is for, and
  keep interviewing. You gather requirements; you don't deliver the solution.
- Pricing is fixed and non-negotiable: the enterprise fit call is FREE; working sessions
  are $50 (30 min) and $90 (60 min); builds get a fixed proposal after scoping. Never
  invent, discount, or negotiate prices.
- Never request confidential data, credentials, secrets, PII beyond a name/email, or
  internal system names you don't need. If the prospect volunteers a secret, tell them
  not to and don't store it.
- Keep it short and human: ONE focused question per turn, warm and concrete. Reference
  what they already told you. Aim to finish in about 6 questions.
- When you have enough for a useful brief, set complete=true, give a short wrap-up in
  `reply`, and set recommended_next_step.

Every turn you MUST call the `submit_turn` tool with: your next `reply` to the user, the
updated `brief` (fill only what you actually know; leave unknown fields empty), up to 3
short `quick_replies` (tappable suggestions; optional), `complete`, and
`recommended_next_step`.
"""

_BUSINESS_SCRIPT = """
This prospect chose a BUSINESS workflow. Interview toward these six beats (adapt, don't
robotically list them):
1. What process should become faster, cheaper, or less manual?
2. Who does it today, and roughly how much time / cost does it take?
3. What inputs and systems does it touch? (names only — no credentials)
4. What makes it a win — hours, cost, cycle time, errors, capacity?
5. What constraints must be designed in from day one? (security review, data residency,
   human approval, vendor stack, deadline)
6. Who agrees to the plan, and on what timing?
You may ask ONE optional budget question with quick replies like "A range is approved",
"I need help sizing it", "No budget yet", "Prefer to discuss" — never force a figure.
recommended_next_step for business is usually "fit" (the free enterprise fit call).
"""

_INDIVIDUAL_SCRIPT = """
This prospect chose a PERSONAL system. Interview toward these beats:
1. Which system — a personal agent, a zero-maintenance website, or both?
2. What should it remember about them / how they work?
3. What should it do unprompted (brief them, research, track commitments, draft, coordinate tools)?
4. What tools and information may it use? (names only — no credentials)
5. What would make it indispensable in six months?
6. Timing and any privacy constraints.
recommended_next_step for individuals is usually "30" (a paid working session) — or "60"
if the scope is clearly larger.
"""

_SUBMIT_TURN_TOOL = {
    "name": "submit_turn",
    "description": "Return the assistant's next reply and the updated structured brief for this turn.",
    "input_schema": {
        "type": "object",
        "properties": {
            "reply": {"type": "string", "description": "The next message to show the user (one focused question, or the completion wrap-up)."},
            "brief": {
                "type": "object",
                "description": "The structured project brief so far. Fill only known fields; leave others as empty strings.",
                "properties": {
                    "desired_outcome": {"type": "string"},
                    "current_workflow": {"type": "string"},
                    "people_and_frequency": {"type": "string"},
                    "systems_and_data": {"type": "string"},
                    "success_metric": {"type": "string"},
                    "constraints": {"type": "string"},
                    "timing_and_stakeholders": {"type": "string"},
                    "open_questions": {"type": "array", "items": {"type": "string"}},
                },
                "required": [
                    "desired_outcome", "current_workflow", "people_and_frequency",
                    "systems_and_data", "success_metric", "constraints",
                    "timing_and_stakeholders", "open_questions",
                ],
            },
            "quick_replies": {"type": "array", "items": {"type": "string"}, "description": "Up to 3 short tappable suggestions. Optional."},
            "complete": {"type": "boolean", "description": "True when the brief is ready and the prospect should move to booking."},
            "recommended_next_step": {"type": "string", "enum": ["fit", "30", "60", ""], "description": "Recommended booking: 'fit' free call, '30'/$50, '60'/$90, or '' if unsure."},
        },
        "required": ["reply", "brief", "complete", "recommended_next_step"],
    },
}


def _system_prompt(path: str) -> str:
    script = _BUSINESS_SCRIPT if path == "business" else _INDIVIDUAL_SCRIPT
    return _SHARED_GUARDRAILS + "\n" + script


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

MAX_USER_TURNS = 12


def run_intake_turn(path: str, messages: list[dict[str, str]]) -> dict[str, Any]:
    """Run one interview turn. `messages` is the transcript so far as
    [{role: 'user'|'assistant', content: str}] (first message must be 'user').

    Returns a dict: {reply, brief, quick_replies, complete, recommended_next_step}.
    Raises on any failure (the endpoint converts that into a graceful fallback).
    """
    client = _get_client()
    if client is None:
        raise RuntimeError("intake_agent_unconfigured")

    path = "business" if path == "business" else "individual"

    # Sanitize transcript to the two allowed roles + string content.
    convo: list[dict[str, str]] = []
    for m in messages[-40:]:
        role = m.get("role")
        content = (m.get("content") or "").strip()
        if role in ("user", "assistant") and content:
            convo.append({"role": role, "content": content[:4000]})
    if not convo or convo[0]["role"] != "user":
        convo.insert(0, {"role": "user", "content": "Let's start."})

    resp = client.messages.create(
        model=INTAKE_MODEL,
        max_tokens=INTAKE_MAX_TOKENS,
        system=_system_prompt(path),
        messages=convo,
        tools=[_SUBMIT_TURN_TOOL],
        tool_choice={"type": "tool", "name": "submit_turn"},
        # Forced tool_choice is incompatible with thinking; disabling it also
        # keeps the interview snappy. (Sonnet 5 enables adaptive thinking by
        # default, which would 400 alongside a forced tool.)
        thinking={"type": "disabled"},
    )

    payload = None
    for block in resp.content:
        if getattr(block, "type", None) == "tool_use" and getattr(block, "name", None) == "submit_turn":
            payload = block.input
            break
    if payload is None:
        raise RuntimeError("intake_no_tool_output")

    brief = payload.get("brief") or {}
    if not isinstance(brief, dict):
        brief = {}
    return {
        "reply": (payload.get("reply") or "").strip() or "Could you tell me a bit more?",
        "brief": brief,
        "quick_replies": [q for q in (payload.get("quick_replies") or []) if isinstance(q, str)][:3],
        "complete": bool(payload.get("complete")),
        "recommended_next_step": payload.get("recommended_next_step") or "",
    }


def brief_to_notes(path: str, brief: dict[str, Any]) -> str:
    """Render an approved brief into the plain-text `notes` that ride into the
    booking and the dual-admin alert email (D5)."""
    labels = [
        ("desired_outcome", "Desired outcome"),
        ("current_workflow", "Current workflow"),
        ("people_and_frequency", "People & frequency"),
        ("systems_and_data", "Systems & data"),
        ("success_metric", "Success metric"),
        ("constraints", "Constraints"),
        ("timing_and_stakeholders", "Timing & stakeholders"),
    ]
    lines = [f"Path: {'Business workflow' if path == 'business' else 'Personal system'}", "", "AI intake brief:"]
    for key, label in labels:
        val = (brief.get(key) or "").strip()
        if val:
            lines.append(f"- {label}: {val}")
    oq = brief.get("open_questions") or []
    if isinstance(oq, list) and oq:
        lines.append("- Open questions: " + "; ".join(str(q) for q in oq))
    return "\n".join(lines).strip()[:1990]
