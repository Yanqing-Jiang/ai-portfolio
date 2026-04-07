"""Ming Engine fortune API routes.

POST /api/fortune/create   — create a fortune session
GET  /api/fortune/{id}/stream — SSE stream of A2UI messages
POST /api/fortune/{id}/action — follow-up action (re-runs from subset agent)
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

try:
    from rate_limiter import smart_rate_limit, RateLimitScope
except ImportError:
    from ..rate_limiter import smart_rate_limit, RateLimitScope  # type: ignore[no-redef]

try:
    from sse_utils import with_heartbeat
except ImportError:
    from ..sse_utils import with_heartbeat  # type: ignore[no-redef]

try:
    from generative_ui.clarification import (
        ClarificationField,
        ClarificationOption,
        ClarificationRequest,
        clarification_to_sse_event,
    )
except ImportError:
    from ..generative_ui.clarification import (  # type: ignore[no-redef]
        ClarificationField,
        ClarificationOption,
        ClarificationRequest,
        clarification_to_sse_event,
    )

try:
    from .agents import (
        DEFAULT_FOLLOW_UP_BUTTONS,
        EnrichedNarrativeOutput,
        FortuneRunContext,
        GuardrailOutput,
        NarrativeOutput,
        run_foundation,
        run_guardrail,
        run_narrative_streamed,
    )
    from .config import get_settings
    from .stream_bridge import FortuneStreamBridge
except ImportError:
    from agents import (  # type: ignore[no-redef]
        DEFAULT_FOLLOW_UP_BUTTONS,
        EnrichedNarrativeOutput,
        FortuneRunContext,
        GuardrailOutput,
        NarrativeOutput,
        run_foundation,
        run_guardrail,
        run_narrative_streamed,
    )
    from config import get_settings  # type: ignore[no-redef]
    from stream_bridge import FortuneStreamBridge  # type: ignore[no-redef]


router = APIRouter(prefix="/api/fortune", tags=["fortune"])


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class RuntimeStatus(str, Enum):
    initialized = "initialized"
    awaiting_clarification = "awaiting_clarification"
    streaming = "streaming"
    complete = "complete"
    error = "error"


class CreateFortuneRequest(BaseModel):
    birth_iso: str = Field(..., min_length=1)
    timezone: str | None = None
    focus: str | None = None
    question: str | None = None
    tone: str | None = None
    birth_time_unknown: bool = False
    gender: str | None = None


class CreateFortuneResponse(BaseModel):
    fortune_id: str
    surface_id: str


class ActionRequest(BaseModel):
    action_id: str
    payload: dict[str, Any] = Field(default_factory=dict)


class CorrectionRequest(BaseModel):
    year: int
    user_note: str = Field(..., min_length=1, max_length=500)


# ---------------------------------------------------------------------------
# Session state (in-memory)
# ---------------------------------------------------------------------------

class FortuneSession(BaseModel):
    fortune_id: str
    surface_id: str
    request: CreateFortuneRequest
    status: RuntimeStatus = RuntimeStatus.initialized
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    latest_foundation: dict[str, Any] = Field(default_factory=dict)
    latest_narrative: dict[str, Any] | None = None
    latest_guardrail: dict[str, Any] | None = None
    corrections: dict[int, dict[str, str]] = Field(default_factory=dict)

    def touch(self, new_status: RuntimeStatus | None = None) -> None:
        if new_status is not None:
            self.status = new_status


class FortuneStore:
    def __init__(self) -> None:
        self._items: dict[str, FortuneSession] = {}

    def create(self, request: CreateFortuneRequest, surface_id: str) -> FortuneSession:
        session = FortuneSession(
            fortune_id=str(uuid.uuid4()),
            surface_id=surface_id,
            request=request,
        )
        self._items[session.fortune_id] = session
        return session

    def get(self, fortune_id: str) -> FortuneSession | None:
        return self._items.get(fortune_id)


_store: FortuneStore | None = None


def get_fortune_store() -> FortuneStore:
    global _store
    if _store is None:
        _store = FortuneStore()
    return _store


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

ALLOWED_ACTIONS = {
    "deep_dive_element",
    "year_forecast",
    "relationship_focus",
    "career_focus",
    "show_sources",
    "expand_classics",
}


def _sse_data(payload: str) -> str:
    return f"data: {payload}\n\n"


def _build_clarification(fortune_id: str) -> ClarificationRequest:
    return ClarificationRequest(
        request_id=f"fortune_focus_{fortune_id}",
        title="Choose a reading focus",
        subtitle="Birth data received. Choose how the reading should be framed.",
        fields=[
            ClarificationField(
                field_id="focus",
                input_type="single_choice",
                label="Reading focus",
                options=[
                    ClarificationOption(id="career_focus", label="Career Deep Dive"),
                    ClarificationOption(id="relationship_focus", label="Compatibility Check"),
                    ClarificationOption(id="year_forecast", label="Explore This Year Luck"),
                ],
                required=True,
            )
        ],
        skip_allowed=True,
    )


def _normalize_focus(action_id: str) -> str | None:
    return {
        "year_forecast": "year",
        "career_focus": "career",
        "relationship_focus": "relationship",
        "deep_dive_element": "element_balance",
        "show_sources": "sources",
        "expand_classics": "classics",
    }.get(action_id)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.post("/create", response_model=CreateFortuneResponse)
async def create_fortune(request_body: CreateFortuneRequest, request: Request):
    await smart_rate_limit(request, scope=RateLimitScope.FORTUNE, weight=1)

    settings = get_settings()
    store = get_fortune_store()
    normalized = request_body.model_copy(
        update={"timezone": request_body.timezone or settings.default_timezone},
    )
    session = store.create(normalized, surface_id=settings.default_surface_id)
    return CreateFortuneResponse(
        fortune_id=session.fortune_id,
        surface_id=session.surface_id,
    )


@router.get("/{fortune_id}/stream")
async def stream_fortune(fortune_id: str, request: Request):
    await smart_rate_limit(request, scope=RateLimitScope.FORTUNE, weight=3)

    store = get_fortune_store()
    session = store.get(fortune_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Fortune session not found")

    async def event_generator():
        bridge = FortuneStreamBridge(surface_id=session.surface_id)
        ctx = FortuneRunContext(
            fortune_id=session.fortune_id,
            surface_id=session.surface_id,
            question=session.request.question,
            focus=session.request.focus,
            tone=session.request.tone,
            birth_iso=session.request.birth_iso,
            timezone=session.request.timezone or "UTC",
            birth_time_unknown=session.request.birth_time_unknown,
            gender=session.request.gender or "unknown",
        )

        try:
            session.touch(RuntimeStatus.streaming)

            # 1. Begin rendering
            for msg in bridge.begin_messages():
                yield _sse_data(msg)

            # 2. Foundation (deterministic: full BaZi analysis + classics)
            foundation = await run_foundation(ctx)
            analysis = foundation["analysis"]
            session.latest_foundation = {
                "pillars": foundation["pillars"],
                "elements": foundation["elements"].model_dump(),
                "references": [r.model_dump() for r in foundation["references"]],
            }

            # Emit base data (existing widgets)
            yield _sse_data(bridge.emit_pillars(session.latest_foundation["pillars"]))
            yield _sse_data(bridge.emit_elements(session.latest_foundation["elements"]))
            yield _sse_data(bridge.emit_references(session.latest_foundation["references"]))

            # Emit enriched computation data (new widgets)
            yield _sse_data(bridge.emit_hidden_stems(analysis.hidden_stems))
            yield _sse_data(bridge.emit_ten_gods(analysis.ten_gods))
            yield _sse_data(bridge.emit_interactions(analysis.interactions))
            yield _sse_data(bridge.emit_seasonal_strength(analysis.seasonal_strength))
            yield _sse_data(bridge.emit_element_by_source(analysis.element_by_source))
            if analysis.luck_pillars:
                yield _sse_data(bridge.emit_luck_pillars(analysis.luck_pillars))
            if analysis.annual_pillars:
                yield _sse_data(bridge.emit_annual_pillars(analysis.annual_pillars))
            yield _sse_data(bridge.emit_kpi(analysis))

            # Emit foundation trace steps (Glass Box sidebar)
            trace = foundation.get("trace")
            if trace:
                yield _sse_data(bridge.emit_trace_steps_batch(trace.steps))

            # 3. Default focus if somehow missing (input phase always provides it)
            if not session.request.focus:
                session.request = session.request.model_copy(update={"focus": "general"})
                ctx = FortuneRunContext(
                    fortune_id=ctx.fortune_id,
                    surface_id=ctx.surface_id,
                    question=ctx.question,
                    focus="general",
                    tone=ctx.tone,
                    birth_iso=ctx.birth_iso,
                    timezone=ctx.timezone,
                    birth_time_unknown=ctx.birth_time_unknown,
                    gender=ctx.gender,
                )

            # 4. Narrative (run to completion — no streaming deltas to prevent layout jitter)
            import time as _time

            # Trace: LLM narrative call
            if trace:
                trace.add_instant("llm_start", "narrative", label="Generating Narrative",
                                  input_summary=f"focus={ctx.focus}")
                yield _sse_data(bridge.emit_trace_steps_batch(trace.steps))

            _t_narrative = _time.monotonic()
            stream_result = await run_narrative_streamed(ctx, foundation=foundation)
            async for event in stream_result.stream_events():
                pass  # consume stream silently; frontend shows skeleton until complete

            # 5. Extract final output from the completed stream run
            narrative = stream_result.final_output
            if not isinstance(narrative, (NarrativeOutput, EnrichedNarrativeOutput)):
                narrative = EnrichedNarrativeOutput.model_validate(narrative)
            session.latest_narrative = narrative.model_dump()

            if trace:
                dur = round((_time.monotonic() - _t_narrative) * 1000, 1)
                n_insights = len(narrative.insights) if hasattr(narrative, 'insights') else 0
                trace.add_instant("llm_complete", "narrative", label="Narrative Complete",
                                  output_summary=f"{n_insights} insights, {dur:.0f}ms")
                trace.steps[-1].duration_ms = dur

            yield _sse_data(
                bridge.emit_narrative_complete(session.latest_narrative)
            )

            # 6. Guardrail
            if trace:
                trace.add_instant("llm_start", "guardrail", label="Running Safety Check")

            _t_guard = _time.monotonic()
            guardrail = await run_guardrail(ctx, narrative=narrative)
            if not guardrail.follow_up_buttons:
                guardrail = GuardrailOutput(
                    level=guardrail.level,
                    message=guardrail.message,
                    disclaimer=guardrail.disclaimer,
                    follow_up_buttons=DEFAULT_FOLLOW_UP_BUTTONS,
                )
            session.latest_guardrail = guardrail.model_dump()

            if trace:
                dur = round((_time.monotonic() - _t_guard) * 1000, 1)
                trace.add_instant("llm_complete", "guardrail", label="Safety Check Complete",
                                  output_summary=f"level={guardrail.level}, {dur:.0f}ms")
                trace.steps[-1].duration_ms = dur

            yield _sse_data(bridge.emit_guardrail(session.latest_guardrail))

            # Emit final trace (all steps including LLM)
            if trace:
                yield _sse_data(bridge.emit_trace_steps_batch(trace.steps))
                yield _sse_data(bridge.emit_trace_summary(trace.summary()))

            # 7. Complete
            session.touch(RuntimeStatus.complete)
            for msg in bridge.emit_complete():
                yield _sse_data(msg)

        except Exception as exc:
            session.touch(RuntimeStatus.error)
            for msg in bridge.emit_error(str(exc)):
                yield _sse_data(msg)

    return StreamingResponse(
        with_heartbeat(event_generator()),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/{fortune_id}/action")
async def handle_fortune_action(
    fortune_id: str,
    request_body: ActionRequest,
    request: Request,
):
    await smart_rate_limit(request, scope=RateLimitScope.FORTUNE, weight=1)

    if request_body.action_id not in ALLOWED_ACTIONS:
        raise HTTPException(status_code=400, detail="Unsupported action_id")

    store = get_fortune_store()
    session = store.get(fortune_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Fortune session not found")

    # Update focus based on action
    normalized_focus = _normalize_focus(request_body.action_id)
    if normalized_focus in {"career", "relationship", "year"}:
        session.request = session.request.model_copy(update={"focus": normalized_focus})

    session.touch(RuntimeStatus.initialized)

    return {
        "fortune_id": fortune_id,
        "action_id": request_body.action_id,
        "focus": session.request.focus,
        "status": session.status.value,
        "stream_url": f"/api/fortune/{fortune_id}/stream",
    }


@router.post("/{fortune_id}/correction")
async def submit_correction(
    fortune_id: str,
    request_body: CorrectionRequest,
    request: Request,
):
    """Store user correction for a specific year prediction."""
    await smart_rate_limit(request, scope=RateLimitScope.FORTUNE, weight=1)

    store = get_fortune_store()
    session = store.get(fortune_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Fortune session not found")

    session.corrections[request_body.year] = {
        "user_note": request_body.user_note,
        "corrected_at": datetime.now(timezone.utc).isoformat(),
    }

    return {
        "fortune_id": fortune_id,
        "year": request_body.year,
        "correction": session.corrections[request_body.year],
    }
