"""Ming Engine fortune API routes.

POST /api/fortune/create               — create a fortune session
GET  /api/fortune/{id}                 — replay completed snapshot (CF-cacheable)
GET  /api/fortune/{id}/stream          — SSE stream of A2UI messages
GET  /api/fortune/{id}/trace           — redacted Glass Box projection (latest run)
GET  /api/fortune/{id}/conversation    — Ask session memory turns
POST /api/fortune/{id}/action          — follow-up action (re-runs from subset agent)
"""

from __future__ import annotations

import asyncio
import hashlib
import json as _json
import logging
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal

from fastapi import APIRouter, Header, HTTPException, Query, Request, Response
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field
from agents import OutputGuardrailTripwireTriggered

logger = logging.getLogger(__name__)

try:
    from rate_limiter import smart_rate_limit, RateLimitScope
except ImportError:
    from ..rate_limiter import smart_rate_limit, RateLimitScope  # type: ignore[no-redef]

try:
    from sse_utils import with_heartbeat
except ImportError:
    from ..sse_utils import with_heartbeat  # type: ignore[no-redef]

try:
    from .agents import (
        FOUNDATION_VERSION,
        FortuneRunContext,
        InsightBullet,
        InsightSection,
        EnrichedNarrativeOutput,
        NARRATIVE_SCHEMA_VERSION,
        NarrativeOutput,
        ensure_narrative_guardrail,
        run_foundation,
    )
    from .config import get_settings
    from .stream_bridge import READING_ERROR_MESSAGE
    from .store import ASK_LEASE_TTL_SECONDS, get_repository, FortuneRepository
    from .triage import ASK_AGENT, ALLOWED_ACTION_IDS, run_triage
    from .session_store import (
        BufferedAskSession,
        conversation_turns_from_items,
        get_ask_session,
        list_conversation_turns,
        serialize_session_items,
    )
    from .simulator import simulate_birth_time
    from .naming import canonical_function
    from .state import (
        CreateFortuneRequest as _StateCreateFortuneRequest,
        FortuneSession,
        PersonBirthInfo as _StatePersonBirthInfo,
        RuntimeStatus,
        get_run_state,
    )
    from . import events as fortune_events
    from . import pipeline as fortune_pipeline
except ImportError:
    from agents import (  # type: ignore[no-redef]
        FOUNDATION_VERSION,
        FortuneRunContext,
        InsightBullet,
        InsightSection,
        EnrichedNarrativeOutput,
        NARRATIVE_SCHEMA_VERSION,
        NarrativeOutput,
        ensure_narrative_guardrail,
        run_foundation,
    )
    from config import get_settings  # type: ignore[no-redef]
    from stream_bridge import READING_ERROR_MESSAGE  # type: ignore[no-redef]
    from store import ASK_LEASE_TTL_SECONDS, get_repository, FortuneRepository  # type: ignore[no-redef]
    from triage import ASK_AGENT, ALLOWED_ACTION_IDS, run_triage  # type: ignore[no-redef]
    from session_store import (  # type: ignore[no-redef]
        BufferedAskSession,
        conversation_turns_from_items,
        get_ask_session,
        list_conversation_turns,
        serialize_session_items,
    )
    from simulator import simulate_birth_time  # type: ignore[no-redef]
    from naming import canonical_function  # type: ignore[no-redef]
    from state import (  # type: ignore[no-redef]
        CreateFortuneRequest as _StateCreateFortuneRequest,
        FortuneSession,
        PersonBirthInfo as _StatePersonBirthInfo,
        RuntimeStatus,
        get_run_state,
    )
    import events as fortune_events  # type: ignore[no-redef]
    import pipeline as fortune_pipeline  # type: ignore[no-redef]


router = APIRouter(prefix="/api/fortune", tags=["fortune"])
ASK_REQUEST_TIMEOUT_SECONDS = 110


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

# RuntimeStatus imported from state.py

class PersonBirthInfo(BaseModel):
    birth_iso: str = Field(..., min_length=1)
    timezone: str | None = None
    gender: str | None = None
    birth_time_unknown: bool = False
    name: str | None = None


class CreateFortuneRequest(BaseModel):
    birth_iso: str = Field(..., min_length=1)
    timezone: str | None = None
    focus: str | None = None
    question: str | None = None
    tone: str | None = None
    birth_time_unknown: bool = False
    gender: str | None = None
    # Optional second person for compatibility flow. When present AND focus
    # starts with "compatibility:", the stream handler computes a second
    # foundation for this person and the narrative agent sees both charts.
    person_b: PersonBirthInfo | None = None


class CreateFortuneResponse(BaseModel):
    fortune_id: str
    run_id: str
    surface_id: str


class ActionRequest(BaseModel):
    action_id: str
    payload: dict[str, Any] = Field(default_factory=dict)


class AskContextRequest(BaseModel):
    """Untrusted locator only; section content is reconstructed server-side."""

    section_id: Literal[
        "verdict",
        "anchor",
        "why",
        "now",
        "timeline",
        "overview",
        "pillars",
        "top_picks",
        "calendar",
    ]
    selection_id: str | None = Field(default=None, max_length=80)


class AskRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=500)
    # Default keeps a backend-first rollout compatible with the previous web
    # client. New clients always send this value and reuse it on retry.
    client_request_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    context: AskContextRequest | None = None


class AskResponse(BaseModel):
    fortune_id: str
    run_id: str
    narrative: dict[str, Any]
    # Degraded is true when ask-session memory could not be used (e.g. Supabase
    # unreachable) — the answer is still valid but it has no conversation history.
    degraded_memory: bool = False
    chain_status: str = "disabled"


def _ask_payload_hash(request_body: AskRequest) -> str:
    payload = request_body.model_dump(mode="json", exclude={"client_request_id"})
    canonical = _json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


async def _mark_ask_request_failed(
    repo: "FortuneRepository",
    fortune_id: uuid.UUID,
    client_request_id: uuid.UUID,
    lease_token: uuid.UUID,
) -> None:
    """Release an idempotency key after a failed attempt without masking it."""
    try:
        await repo.fail_ask_request(
            fortune_id=fortune_id,
            client_request_id=client_request_id,
            lease_token=lease_token,
        )
    except Exception as exc:
        logger.warning("[FORTUNE] ask idempotency failure cleanup failed: %s", exc)


async def _complete_ask_request_or_503(
    repo: "FortuneRepository",
    fortune_id: uuid.UUID,
    client_request_id: uuid.UUID,
    lease_token: uuid.UUID,
    response: "AskResponse",
    *,
    run_id: uuid.UUID,
    run_status: str = "done",
    session_items: list[Any] | None = None,
    conversation_committed: bool = False,
) -> None:
    """Persist the replayable response before exposing/committing its turn."""
    try:
        await repo.complete_ask_request(
            fortune_id=fortune_id,
            client_request_id=client_request_id,
            lease_token=lease_token,
            response=response.model_dump(mode="json"),
            run_id=run_id,
            run_status=run_status,
            session_items=session_items,
            conversation_committed=conversation_committed,
        )
    except Exception as exc:
        logger.exception("[FORTUNE] Ask idempotency completion failed: %s", exc)
        await _mark_ask_request_failed(
            repo, fortune_id, client_request_id, lease_token,
        )
        raise HTTPException(
            status_code=503,
            detail="Ask retry protection unavailable; retry this saved question.",
        ) from exc


async def _completed_ask_replay(
    repo: "FortuneRepository",
    fortune_id: uuid.UUID,
    client_request_id: uuid.UUID,
    payload_hash: str,
) -> AskResponse | None:
    """Return already-completed work before mutable reading readiness gates."""
    existing = await repo.get_ask_request(
        fortune_id=fortune_id,
        client_request_id=client_request_id,
    )
    if existing is None:
        return None
    if existing.get("payload_hash") != payload_hash:
        raise HTTPException(
            status_code=409,
            detail="This Ask request ID was already used for different input.",
        )
    if existing.get("status") != "done" or not existing.get("response_json"):
        return None
    saved = _unpack_jsonb(existing["response_json"])
    if not isinstance(saved, dict):
        return None
    try:
        saved_run_id = uuid.UUID(str(saved.get("run_id")))
        await repo.reconcile_completed_ask_run(
            fortune_id=fortune_id,
            client_request_id=client_request_id,
            run_id=saved_run_id,
        )
    except (TypeError, ValueError):
        pass
    except Exception as exc:
        logger.warning("[FORTUNE] completed Ask run reconciliation failed: %s", exc)
    pending_items = _unpack_jsonb(existing.get("session_items"))
    if (
        not existing.get("conversation_committed")
        and isinstance(pending_items, list)
        and pending_items
    ):
        try:
            durable = await get_ask_session(str(fortune_id))
            if durable is not None:
                serialized_items = await serialize_session_items(durable, pending_items)
                await repo.commit_ask_conversation(
                    fortune_id=fortune_id,
                    client_request_id=client_request_id,
                    lease_token=existing["lease_token"],
                    delivery_id=existing["delivery_id"],
                    session_id=durable.session_id,
                    serialized_items=serialized_items,
                )
        except Exception as exc:
            logger.warning("[FORTUNE] Ask memory outbox repair failed: %s", exc)
            saved["degraded_memory"] = True
    return AskResponse.model_validate(saved)


class CorrectionRequest(BaseModel):
    year: int
    user_note: str = Field(..., min_length=1, max_length=500)


# ---------------------------------------------------------------------------
# Session state (in-memory)
# ---------------------------------------------------------------------------

# FortuneSession / FortuneStore deleted — see state.py (get_run_state).

def get_fortune_store():
    """Back-compat alias for tests/callers; returns the Redis/memory run state."""
    return get_run_state()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _sse_data(payload: str) -> str:
    return f"data: {payload}\n\n"


def _to_jsonable(obj: Any) -> Any:
    """Deep-convert Pydantic / dataclass / dict / list into JSON-safe structures."""
    if obj is None or isinstance(obj, (str, int, float, bool)):
        return obj
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    if isinstance(obj, dict):
        return {k: _to_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_to_jsonable(x) for x in obj]
    if hasattr(obj, "__dict__"):
        return {k: _to_jsonable(v) for k, v in vars(obj).items() if not k.startswith("_")}
    return str(obj)


def _snapshot_pillars(session: "FortuneSession", foundation: dict[str, Any]) -> dict[str, Any]:
    payload = {
        "pillars": _to_jsonable(foundation.get("pillars")),
        "elements": _to_jsonable(foundation.get("elements")),
        "ziwei": _to_jsonable(foundation.get("ziwei")),
        "birth_year": foundation.get("birth_year"),
        "reading_brief": _to_jsonable(foundation.get("reading_brief")),
    }
    person_b = foundation.get("person_b")
    if person_b:
        analysis_b = person_b.get("analysis")
        payload["person_b"] = {
            "pillars": _to_jsonable(person_b.get("pillars")),
            "elements": _to_jsonable(person_b.get("elements")),
            "ziwei": _to_jsonable(person_b.get("ziwei")),
            "birth_year": person_b.get("birth_year"),
            # Ask hydration needs the same computed chart for both people.
            # Persist the complete deterministic analysis, not just the two
            # fields needed by the compatibility result cards.
            "mechanics": _snapshot_mechanics(session, analysis_b),
        }
    if get_settings().snapshot_schema_versions_enabled:
        payload["foundation_version"] = FOUNDATION_VERSION
    return payload


def _snapshot_mechanics(session: "FortuneSession", analysis: Any) -> dict[str, Any]:
    """Serialize the FullBaziAnalysis fields we need to rebuild a foundation.

    This is the read source for /ask hydration: the Ask tab works even after
    the process restarts because we can re-construct the pydantic analysis
    from these JSON fields via ``FullBaziAnalysis.model_validate``.
    """
    if analysis is None:
        return {}
    payload = {
        "pillars": _to_jsonable(getattr(analysis, "pillars", None)),
        "hidden_stems": _to_jsonable(getattr(analysis, "hidden_stems", None)),
        "ten_gods": _to_jsonable(getattr(analysis, "ten_gods", None)),
        "interactions": _to_jsonable(getattr(analysis, "interactions", None)),
        "seasonal_strength": _to_jsonable(getattr(analysis, "seasonal_strength", None)),
        "element_by_source": _to_jsonable(getattr(analysis, "element_by_source", None)),
        "enhanced_element_counts": _to_jsonable(getattr(analysis, "enhanced_element_counts", None)),
        "luck_pillars": _to_jsonable(getattr(analysis, "luck_pillars", None)),
        "annual_pillars": _to_jsonable(getattr(analysis, "annual_pillars", None)),
        "harmony_score": getattr(analysis, "harmony_score", None),
    }
    if get_settings().snapshot_schema_versions_enabled:
        payload["foundation_version"] = FOUNDATION_VERSION
        payload["narrative_schema_version"] = NARRATIVE_SCHEMA_VERSION
    return payload


def _snapshot_references(foundation: dict[str, Any]) -> dict[str, Any]:
    return {"items": _to_jsonable(foundation.get("references", []))}


# Match pipeline rejected-branch copy (_pipeline_run._SAFE_REJECTION_*).
_ASK_SAFE_REJECTION_MESSAGE = "We can’t safely present this reading."
_ASK_SAFE_REJECTION_DISCLAIMER = (
    "Try again with a different question. This tool is for reflection and entertainment only."
)


def _ask_safe_rejection_narrative() -> dict[str, Any]:
    """Deterministic Ask narrative used when the output guardrail trips."""
    return EnrichedNarrativeOutput(
        tldr=_ASK_SAFE_REJECTION_MESSAGE,
        insights=[
            InsightSection(
                id="safety",
                icon="•",
                heading="Unavailable",
                tagline="This answer was withheld by the safety check.",
                bullets=[
                    InsightBullet(icon="•", text=_ASK_SAFE_REJECTION_MESSAGE),
                    InsightBullet(icon="•", text=_ASK_SAFE_REJECTION_DISCLAIMER),
                ],
            ),
            InsightSection(
                id="next_step",
                icon="•",
                heading="What to try",
                tagline="Ask a different follow-up.",
                bullets=[
                    InsightBullet(
                        icon="•",
                        text="Rephrase without sensitive or prohibited requests.",
                    ),
                    InsightBullet(
                        icon="•",
                        text="Stay with reflective, entertainment-only guidance.",
                    ),
                ],
            ),
        ],
    ).model_dump()


async def _latest_non_ask_run_status(
    repo: "FortuneRepository",
    fortune_id: uuid.UUID,
) -> str | None:
    """Return done once any initial/action reading completed successfully.

    A later optional action may fail without invalidating the approved reading
    that already exists. If no successful run exists, return the latest status
    so the caller can continue to distinguish pending from unavailable state.
    """
    if not repo.available or repo.pool is None:
        return None
    row = await repo.pool.fetchrow(
        """
        SELECT status
        FROM fortune_run
        WHERE fortune_id = $1
          AND run_kind IN ('initial', 'action')
        ORDER BY (status = 'done') DESC, created_at DESC
        LIMIT 1
        """,
        fortune_id,
    )
    return str(row["status"]) if row else None


def _build_ask_original_input(req: "CreateFortuneRequest | None") -> dict[str, Any] | None:
    """Snapshot the user's create-fortune inputs for follow-up Ask context.

    Pulled from ``FortuneSession.request`` (the live one) and forwarded to
    ``run_triage`` so the specialist sees the focus, original question,
    person_b, and other context the user already established. Returns ``None``
    when the request is missing — the hydrate-from-snapshot path falls back to
    ``ctx`` fields inside triage.
    """
    if req is None:
        return None
    out: dict[str, Any] = {
        "birth_iso": req.birth_iso,
        "timezone": req.timezone,
        "gender": req.gender,
        "birth_time_unknown": bool(req.birth_time_unknown),
        "focus": req.focus,
        "original_question": req.question,
        "tone": req.tone,
    }
    if req.person_b is not None:
        out["person_b"] = req.person_b.model_dump()
    return out


async def _hydrate_foundation_from_snapshot(
    repo: "FortuneRepository", fortune_id: str
) -> dict[str, Any] | None:
    """Rebuild a foundation dict from ``fortune_snapshot`` for /ask continuity.

    When a worker restarts (or the request routes to a worker that never saw
    the original /create), the in-memory ``FortuneSession.latest_foundation``
    is gone. Everything the triage prompt needs is durable though — this
    helper pulls the snapshot and re-hydrates the analysis as a
    ``FullBaziAnalysis`` pydantic instance so the live and hydrated paths go
    through ``_build_triage_prompt`` the same way.

    Returns None when the snapshot is missing or too incomplete to rebuild;
    caller should 409.
    """
    try:
        fid = uuid.UUID(fortune_id)
    except ValueError:
        return None
    row = await repo.get_snapshot(fid)
    if not row:
        return None
    mechanics = _unpack_jsonb(row.get("latest_mechanics")) or {}
    pillars = _unpack_jsonb(row.get("latest_pillars")) or {}
    references_block = _unpack_jsonb(row.get("latest_references")) or {}
    # Pull the minimum viable set. If any required field is missing the
    # snapshot pre-dates the mechanics expansion and we cannot trust the
    # reconstruction — return None and let the route 409 with a clear message.
    required = ("hidden_stems", "ten_gods", "interactions", "seasonal_strength")
    # ``interactions`` is a valid empty list for charts with no detected
    # combinations/clashes. Require the field and its expected container,
    # rather than treating emptiness as an incomplete snapshot.
    if not all(k in mechanics and mechanics[k] is not None for k in required):
        return None
    if not isinstance(mechanics.get("interactions"), list):
        return None
    try:
        from .bazi_engine import FullBaziAnalysis
    except ImportError:
        from bazi_engine import FullBaziAnalysis  # type: ignore[no-redef]

    def _rehydrate_analysis(
        stored_mechanics: dict[str, Any],
        stored_pillars: dict[str, Any],
        *,
        derive_missing: bool = False,
    ) -> Any:
        required_fields = (
            "hidden_stems", "ten_gods", "interactions", "seasonal_strength",
        )
        complete = all(
            key in stored_mechanics and stored_mechanics[key] is not None
            for key in required_fields
        ) and isinstance(stored_mechanics.get("interactions"), list)
        if not complete:
            if not derive_missing:
                raise ValueError("snapshot mechanics are incomplete")
            chart = stored_mechanics.get("pillars") or stored_pillars or {}
            if not isinstance(chart, dict) or not chart.get("day_master"):
                raise ValueError("legacy snapshot lacks a reconstructable chart")
            try:
                from .bazi_engine import (
                    compute_all_hidden_stems,
                    compute_enhanced_elements,
                    compute_harmony_score,
                    compute_interactions,
                    compute_seasonal_strength,
                    compute_ten_gods,
                )
            except ImportError:
                from bazi_engine import (  # type: ignore[no-redef]
                    compute_all_hidden_stems,
                    compute_enhanced_elements,
                    compute_harmony_score,
                    compute_interactions,
                    compute_seasonal_strength,
                    compute_ten_gods,
                )
            hidden = compute_all_hidden_stems(chart)
            interactions = compute_interactions(chart)
            enhanced, by_source = compute_enhanced_elements(chart, hidden)
            month = chart.get("month") or {}
            month_branch = month.get("branch") if isinstance(month, dict) else month.branch
            stored_mechanics = {
                **stored_mechanics,
                "pillars": chart,
                "hidden_stems": hidden,
                "ten_gods": compute_ten_gods(chart["day_master"], chart, hidden),
                "interactions": interactions,
                "seasonal_strength": compute_seasonal_strength(
                    chart.get("day_master_element"), month_branch,
                ),
                "enhanced_element_counts": enhanced,
                "element_by_source": by_source,
                "harmony_score": compute_harmony_score(interactions),
            }
        return FullBaziAnalysis.model_validate({
            "pillars": stored_mechanics.get("pillars") or stored_pillars or {},
            "hidden_stems": stored_mechanics["hidden_stems"],
            "ten_gods": stored_mechanics["ten_gods"],
            "interactions": stored_mechanics["interactions"],
            "seasonal_strength": stored_mechanics["seasonal_strength"],
            "luck_pillars": stored_mechanics.get("luck_pillars") or [],
            "annual_pillars": stored_mechanics.get("annual_pillars") or [],
            "enhanced_element_counts": stored_mechanics.get("enhanced_element_counts") or {},
            "element_by_source": stored_mechanics.get("element_by_source") or {},
            "harmony_score": stored_mechanics.get("harmony_score") or 0.0,
        })

    try:
        analysis = _rehydrate_analysis(mechanics, pillars.get("pillars") or {})
    except Exception as exc:
        logger.warning(
            "[FORTUNE] snapshot mechanics failed to rehydrate analysis: %s", exc,
        )
        return None

    request_context = _unpack_jsonb(row.get("request_context")) or {}
    foundation = {
        "analysis": analysis,
        "pillars": pillars.get("pillars") or {},
        "elements": pillars.get("elements") or {},
        "references": references_block.get("items") or [],
        "retrodictions": [],
        "trace": None,
        "request_context": request_context,
        "ziwei": pillars.get("ziwei"),
        "birth_year": pillars.get("birth_year"),
        "reading_brief": pillars.get("reading_brief"),
    }
    person_b = pillars.get("person_b")
    if isinstance(person_b, dict):
        person_b_mechanics = person_b.get("mechanics")
        if isinstance(person_b_mechanics, dict):
            try:
                analysis_b = _rehydrate_analysis(
                    person_b_mechanics,
                    person_b.get("pillars") or {},
                    derive_missing=True,
                )
                foundation["person_b"] = {
                    "analysis": analysis_b,
                    "pillars": person_b.get("pillars") or {},
                    "elements": person_b.get("elements") or {},
                    "ziwei": person_b.get("ziwei"),
                    "birth_year": person_b.get("birth_year"),
                }
            except Exception as exc:
                logger.warning(
                    "[FORTUNE] Person B snapshot mechanics failed to rehydrate: %s", exc,
                )
    elif isinstance(request_context.get("person_b"), dict):
        # Backfill snapshots written before complete Person B mechanics were
        # persisted. Foundation computation is deterministic, so legacy
        # compatibility readings can still answer grounded questions after a
        # worker restart without inventing the second chart.
        person_b_input = request_context["person_b"]
        birth_iso = person_b_input.get("birth_iso")
        if not isinstance(birth_iso, str) or not birth_iso:
            logger.warning("[FORTUNE] legacy compatibility snapshot lacks Person B birth input")
            return None
        try:
            foundation["person_b"] = await run_foundation(FortuneRunContext(
                fortune_id=fortune_id,
                surface_id="fortune_main",
                focus=request_context.get("focus"),
                birth_iso=birth_iso,
                timezone=(
                    person_b_input.get("timezone")
                    or request_context.get("timezone")
                    or get_settings().default_timezone
                ),
                birth_time_unknown=bool(person_b_input.get("birth_time_unknown")),
                gender=person_b_input.get("gender") or "unknown",
            ))
        except Exception as exc:
            logger.warning("[FORTUNE] legacy Person B foundation recompute failed: %s", exc)
            return None
    if isinstance(person_b, dict) and "person_b" not in foundation:
        # Some pre-007 rows have an incomplete Person B mechanics block but do
        # have the original input. Prefer deterministic recomputation to losing
        # compatibility grounding after a restart.
        person_b_input = request_context.get("person_b")
        if not isinstance(person_b_input, dict) or not person_b_input.get("birth_iso"):
            return None
        try:
            foundation["person_b"] = await run_foundation(FortuneRunContext(
                fortune_id=fortune_id,
                surface_id="fortune_main",
                focus=request_context.get("focus"),
                birth_iso=person_b_input["birth_iso"],
                timezone=(
                    person_b_input.get("timezone")
                    or request_context.get("timezone")
                    or get_settings().default_timezone
                ),
                birth_time_unknown=bool(person_b_input.get("birth_time_unknown")),
                gender=person_b_input.get("gender") or "unknown",
            ))
        except Exception as exc:
            logger.warning("[FORTUNE] Person B fallback recompute failed: %s", exc)
            return None
    return foundation


def _merge_ask_foundation(
    hydrated: dict[str, Any],
    hot_foundation: dict[str, Any] | None,
) -> dict[str, Any]:
    """Overlay live values without discarding durable nested mechanics."""
    if not hot_foundation:
        return hydrated
    merged = {**hydrated, **hot_foundation}
    hydrated_person_b = hydrated.get("person_b")
    hot_person_b = hot_foundation.get("person_b")
    if isinstance(hydrated_person_b, dict) and isinstance(hot_person_b, dict):
        merged["person_b"] = {**hydrated_person_b, **hot_person_b}
    return merged


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.post("/create", response_model=CreateFortuneResponse)
async def create_fortune(request_body: CreateFortuneRequest, request: Request):
    await smart_rate_limit(request, scope=RateLimitScope.FORTUNE_CREATE, weight=1)

    settings = get_settings()
    normalized = request_body.model_copy(
        update={"timezone": request_body.timezone or settings.default_timezone},
    )

    # Persist to Supabase (fortune + initial run).
    repo = await get_repository()
    client_ip = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")

    degraded_persistence = False
    fortune_rec = None
    run_rec = None
    try:
        fortune_rec = await repo.create_fortune(
            birth_iso=normalized.birth_iso,
            timezone_name=normalized.timezone or settings.default_timezone,
            focus=normalized.focus,
            question=normalized.question,
            tone=normalized.tone,
            birth_time_unknown=normalized.birth_time_unknown,
            gender=normalized.gender or "unknown",
            surface_id=settings.default_surface_id,
            client_ip=client_ip,
            user_agent=user_agent,
        )
        if fortune_rec is not None:
            run_rec = await repo.create_run(fortune_id=fortune_rec.id, run_kind="initial")
    except Exception as exc:
        degraded_persistence = True
        logger.warning("[FORTUNE] create persistence failed; falling back to in-memory: %s", exc)

    if fortune_rec is None:
        degraded_persistence = True
        fortune_id_str = str(uuid.uuid4())
        run_id_str = str(uuid.uuid4())
        logger.warning("[FORTUNE] DB unavailable; using in-memory IDs %s / %s",
                       fortune_id_str, run_id_str)
    else:
        fortune_id_str = str(fortune_rec.id)
        if run_rec is None:
            degraded_persistence = True
            run_id_str = str(uuid.uuid4())
            logger.warning("[FORTUNE] run persistence unavailable; using in-memory run ID %s",
                           run_id_str)
        else:
            run_id_str = str(run_rec.id)

    # Hot-path cache for active streaming (Redis registry via state.py).
    store = get_run_state()
    session = FortuneSession(
        fortune_id=fortune_id_str,
        run_id=run_id_str,
        surface_id=settings.default_surface_id,
        request=_StateCreateFortuneRequest.model_validate(normalized.model_dump()),
    )

    # Redis is correctness-critical: fail closed at create (no in-proc fallback).
    try:
        await fortune_events.get_events_redis(required=True)
    except fortune_events.RedisUnavailable as exc:
        logger.error("[FORTUNE] Redis unavailable at create: %s", exc)
        raise HTTPException(
            status_code=503,
            detail={
                "error": "redis_unavailable",
                "message": "Fortune service temporarily unavailable. Please retry shortly.",
            },
            headers={"Retry-After": "30"},
        ) from exc
    try:
        await store.put(session)
    except Exception as exc:
        logger.error("[FORTUNE] state put failed at create: %s", exc)
        raise HTTPException(
            status_code=503,
            detail={
                "error": "redis_unavailable",
                "message": "Fortune service temporarily unavailable. Please retry shortly.",
            },
            headers={"Retry-After": "30"},
        ) from exc
    await fortune_events.set_run_record(
        run_id_str, fortune_id=fortune_id_str, status="queued",
    )
    lock_token = await store.acquire_lock(fortune_id_str)
    if lock_token is None:  # pragma: no cover - new UUID cannot be contended
        raise HTTPException(
            status_code=409,
            detail="This fortune is busy; retry the reading.",
            headers={"Retry-After": "3"},
        )
    # DEBT: run task dies with its owning worker; no runner service/lease.
    # Upgrade when workers > 1 or deploys must not kill active runs.
    asyncio.create_task(
        fortune_pipeline.run_and_publish_safe(
            session, store=store, lock_token=lock_token,
        )
    )

    logger.info("[FORTUNE] create fortune=%s run=%s focus=%s degraded=%s",
                fortune_id_str, run_id_str, normalized.focus, degraded_persistence)

    response_payload = {
        "fortune_id": fortune_id_str,
        "run_id": run_id_str,
        "surface_id": settings.default_surface_id,
    }
    if degraded_persistence:
        return JSONResponse(
            content=response_payload,
            headers={"X-Fortune-Persistence": "degraded"},
        )
    return CreateFortuneResponse(**response_payload)


def _unpack_jsonb(value: Any) -> Any:
    """asyncpg returns JSONB as str by default; parse if so."""
    if value is None or isinstance(value, (dict, list)):
        return value
    if isinstance(value, (bytes, bytearray)):
        value = value.decode("utf-8")
    if isinstance(value, str):
        try:
            return _json.loads(value)
        except (ValueError, TypeError):
            logger.warning("[FORTUNE] invalid JSONB in replay payload: %r", value[:200])
            return None
    return value


def _replay_cache_control(snapshot_status: str) -> str:
    if snapshot_status == "error":
        return "no-store"
    if snapshot_status == "done":
        return "public, s-maxage=300, stale-while-revalidate=86400"
    # Partial snapshot — cache briefly for reload protection but don't let
    # CF serve it long enough to mask subsequent completion.
    return "public, s-maxage=10, stale-while-revalidate=30"


def _replay_headers(snapshot_status: str, etag: str) -> dict[str, str]:
    return {
        "Cache-Control": _replay_cache_control(snapshot_status),
        "ETag": etag,
        "Vary": "Accept-Encoding",
    }


def _if_none_match_matches(header_value: str | None, etag: str) -> bool:
    """RFC 7232 §3.2 compliant matcher: weak validators, lists, and '*'."""
    if not header_value:
        return False
    current = etag[2:] if etag.startswith("W/") else etag
    for candidate in header_value.split(","):
        token = candidate.strip()
        if not token:
            continue
        if token == "*":
            return True
        other = token[2:] if token.startswith("W/") else token
        if other == current:
            return True
    return False


def _replay_metadata(row: dict[str, Any]) -> dict[str, Any]:
    """Non-PII metadata only. birth_iso/question/gender never leave the backend."""
    return {
        "focus": row["focus"],
        "tone": row["tone"],
        "locale": row["locale"],
        "created_at": row["created_at"].isoformat() if row["created_at"] else None,
        # Boolean flag only — used by Reading Stability UI; not birth data.
        "birth_time_unknown": bool(row.get("birth_time_unknown")),
    }


@router.get("/{fortune_id}")
async def get_fortune_replay(
    fortune_id: str,
    request: Request,
    response: Response,
    if_none_match: str | None = Header(default=None, alias="If-None-Match"),
):
    """Return the completed fortune snapshot for replay/share.

    Serves as the cold-path read source for the shareable /fortune/:id route.
    Cloudflare edge caches the successful responses; FastAPI sets a
    snapshot-version ETag so cache invalidation happens naturally when a
    fortune is regenerated.
    """
    await smart_rate_limit(request, scope=RateLimitScope.FORTUNE_REPLAY, weight=1)

    try:
        fortune_uuid = uuid.UUID(fortune_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid fortune_id")

    repo = await get_repository()
    if not repo.available:
        store = get_run_state()
        if await store.get(fortune_id) is not None:
            return JSONResponse(
                status_code=202,
                content={"fortune_id": fortune_id, "status": "pending"},
                headers={"Cache-Control": "no-store"},
            )
        raise HTTPException(
            status_code=503,
            detail="Replay unavailable",
            headers={"Retry-After": "60"},
        )
    try:
        row = await repo.get_fortune_with_snapshot(fortune_uuid)
    except Exception as exc:
        logger.warning("[FORTUNE] replay lookup failed for %s: %s", fortune_id, exc)
        raise HTTPException(
            status_code=503,
            detail="Replay unavailable",
            headers={"Retry-After": "60"},
        ) from exc
    if row is None:
        raise HTTPException(status_code=404, detail="Fortune not found")

    snapshot_status = row.get("snapshot_status")
    snapshot_version = row.get("snapshot_version")
    # A failed initial run can leave a partial snapshot (or none). Its durable
    # run status must win over that stale progress state after a restart/expiry.
    # A later failed Ask/action never invalidates an already completed reading.
    reading_failed = snapshot_status != "done" and row.get("latest_reading_run_status") in {
        "error", "interrupted", "failed_guardrail",
    }
    if reading_failed:
        snapshot_status = "error"
        snapshot_version = snapshot_version or 0

    # No snapshot yet — run is probably still streaming (or crashed before first write).
    if snapshot_version is None:
        return JSONResponse(
            status_code=202,
            content={
                "fortune_id": fortune_id,
                "status": "pending",
            },
            headers={"Cache-Control": "no-store"},
        )

    etag = f'"fortune-{fortune_id}-v{snapshot_version}"'
    if reading_failed:
        etag = f'"fortune-{fortune_id}-v{snapshot_version}-error-{row.get("latest_reading_run_id")}"'
    if _if_none_match_matches(if_none_match, etag):
        return Response(
            status_code=304,
            headers=_replay_headers(snapshot_status, etag),
        )

    retrodictions_unpacked = _unpack_jsonb(row.get("latest_retrodictions"))
    # The LifeTimeline widget reads corrections from `/data/corrections`
    # (see stream_bridge `correctionsPath`) but storage keeps them nested
    # inside `latest_retrodictions.corrections` so /correction can update
    # them with a single jsonb_set. Hoist the sub-key into its own top-level
    # data slot on replay so reload/share renders the corrections overlay.
    corrections_block = (
        retrodictions_unpacked.get("corrections")
        if isinstance(retrodictions_unpacked, dict) else None
    )
    schema_version = row.get("schema_version")
    if schema_version is None:
        schema_version = 2 if reading_failed else 1
    data_model = _unpack_jsonb(row.get("data_model"))
    if reading_failed:
        data_model = dict(data_model or {})
        data_model["meta"] = {
            **(data_model.get("meta") or {}),
            "status": "error", "error_message": READING_ERROR_MESSAGE,
        }
        data_model["meta"].pop("progress", None)
        if row.get("latest_reading_run_status") == "failed_guardrail":
            data_model["guardrail"] = {
                "level": "critical", "message": "We can’t safely present this reading.",
            }
    payload = {
        "fortune_id": fortune_id,
        "snapshot_version": snapshot_version,
        "schema_version": int(schema_version),
        "status": snapshot_status,
        "metadata": _replay_metadata(row),
        "data": {
            "overview": _unpack_jsonb(row.get("latest_overview")),
            "pillars": _unpack_jsonb(row.get("latest_pillars")),
            "mechanics": _unpack_jsonb(row.get("latest_mechanics")),
            "narrative": _unpack_jsonb(row.get("latest_narrative")),
            "trace": _unpack_jsonb(row.get("latest_trace")),
            "references": _unpack_jsonb(row.get("latest_references")),
            "retrodictions": retrodictions_unpacked,
            "corrections": corrections_block,
        },
        # Additive v2 field; NULL/absent on schema_version=1 rows (dual-read).
        "data_model": data_model,
    }

    return JSONResponse(
        content=payload,
        headers=_replay_headers(snapshot_status, etag),
    )


@router.get("/{fortune_id}/stream")
async def stream_fortune(
    fortune_id: str,
    request: Request,
    after: str | None = None,
    expected_run_id: str | None = Query(default=None, alias="run_id"),
):
    """Tail Redis Streams for a run. Independent cursors — no consumer groups."""
    await smart_rate_limit(request, scope=RateLimitScope.FORTUNE_STREAM, weight=1)

    store = get_run_state()
    session = await store.get(fortune_id)

    # Resume cursor: Last-Event-ID header OR ?after=<redis-id>
    last_event_id = request.headers.get("last-event-id") or request.headers.get("Last-Event-ID")
    cursor = after or last_event_id or "0-0"
    run_id = session.run_id if session is not None else None

    # Resolve unknown run: Redis run hash via session, else snapshot store.
    if session is None:
        repo = await get_repository()
        try:
            fid = uuid.UUID(fortune_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid fortune_id")
        row = None
        if repo.available:
            try:
                row = await repo.get_fortune_with_snapshot(fid)
            except Exception:
                row = None
        if row is None and (not repo.available or await repo.get_fortune(fid) is None):
            raise HTTPException(status_code=404, detail="Fortune session not found")
        # Fortune exists in durable store but no live session / stream — resync.
        async def resync_only():
            yield fortune_events.format_typed_sse(
                "resync_required",
                {
                    "fortune_id": fortune_id,
                    "reason": "stream_unavailable",
                    "message": "Reconnect window expired; re-hydrate from snapshot.",
                },
            )
        return StreamingResponse(
            with_heartbeat(resync_only()),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache, no-transform",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    run_id = session.run_id or ""

    # Action runs reuse a fortune_id, so bind each stream URL to the run the
    # client intended to consume. A delayed reconnect must not attach to a
    # later run and apply its events under the old cursor/state.
    if expected_run_id and expected_run_id != run_id:
        async def run_changed_gen():
            yield fortune_events.format_typed_sse(
                "resync_required",
                {
                    "fortune_id": fortune_id,
                    "run_id": run_id,
                    "expected_run_id": expected_run_id,
                    "reason": "run_changed",
                    "message": "The reading advanced to a different run; re-hydrate its snapshot.",
                },
            )
        return StreamingResponse(
            with_heartbeat(run_changed_gen()),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache, no-transform",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    # Trim-gap / expired stream → typed resync_required (never hang).
    if cursor and cursor not in {"0", "0-0"}:
        try:
            if await fortune_events.needs_resync(run_id, cursor):
                async def resync_gen():
                    yield fortune_events.format_typed_sse(
                        "resync_required",
                        {
                            "fortune_id": fortune_id,
                            "run_id": run_id,
                            "reason": "cursor_out_of_window",
                            "after": cursor,
                            "message": "Event cursor predates retained window; re-hydrate from snapshot.",
                        },
                    )
                return StreamingResponse(
                    with_heartbeat(resync_gen()),
                    media_type="text/event-stream",
                    headers={
                        "Cache-Control": "no-cache, no-transform",
                        "Connection": "keep-alive",
                        "X-Accel-Buffering": "no",
                    },
                )
        except Exception as exc:
            logger.warning("[FORTUNE] resync check failed: %s", exc)

    async def event_generator():
        try:
            redis_cursor, _ = fortune_events.decode_cursor(run_id, cursor)
            async for entry_id, envelope in fortune_events.tail_envelopes(
                run_id, after=redis_cursor,
            ):
                if await request.is_disconnected():
                    return
                yield fortune_events.format_sse(
                    envelope,
                    event_id=fortune_events.encode_cursor(run_id, entry_id),
                )
        except Exception as exc:
            logger.exception("[FORTUNE] v2 stream tail error: %s", exc)
            # Clean terminal error — do not hang.
            yield fortune_events.format_sse(
                {
                    "run_id": run_id,
                    "fortune_id": fortune_id,
                    "seq": 0,
                    "payload": {"done": True, "error": True, "message": "stream_unavailable"},
                }
            )

    return StreamingResponse(
        with_heartbeat(event_generator()),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
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
    await smart_rate_limit(request, scope=RateLimitScope.FORTUNE_ACTION, weight=1)

    if request_body.action_id not in ALLOWED_ACTION_IDS:
        raise HTTPException(status_code=400, detail="Unsupported action_id")

    store = get_run_state()
    session = await store.get(fortune_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Fortune session not found")

    lock_token = await store.acquire_lock(fortune_id)
    if lock_token is None:
        raise HTTPException(
            status_code=409,
            detail="This fortune is busy; wait for the current run to finish.",
            headers={"Retry-After": "3"},
        )
    try:
        new_run_id = str(uuid.uuid4())
        try:
            repo = await get_repository()
            run_rec = await repo.create_run(
                fortune_id=uuid.UUID(fortune_id),
                run_kind="action",
                action_type=request_body.action_id,
            )
            if run_rec:
                new_run_id = str(run_rec.id)
        except Exception as exc:
            logger.warning("[FORTUNE] action run persistence failed: %s", exc)

        session.run_id = new_run_id
        session.pending_action_id = request_body.action_id
        session.pending_action_question = (
            request_body.payload.get("question")
            if isinstance(request_body.payload, dict) else None
        )
        session.touch(RuntimeStatus.initialized)
        await store.put(session)

        await fortune_events.set_run_record(
            new_run_id, fortune_id=fortune_id, status="queued",
        )
        asyncio.create_task(
            fortune_pipeline.run_and_publish_safe(
                session, store=store, lock_token=lock_token,
            )
        )
        lock_token = None  # background task now owns the writer lock

        return {
            "fortune_id": fortune_id,
            "run_id": new_run_id,
            "action_id": request_body.action_id,
            "focus": session.request.focus,
            "status": session.status.value,
            "stream_url": f"/api/fortune/{fortune_id}/stream?run_id={new_run_id}",
        }
    finally:
        await store.release_lock(fortune_id, lock_token)


@router.post("/{fortune_id}/ask", response_model=AskResponse)
async def ask_fortune(
    fortune_id: str,
    request_body: AskRequest,
    request: Request,
):
    """Free-form follow-up question with durable conversation memory.

    Unlike ``/action`` (button-driven, stateless re-triage), this endpoint
    threads a ``SQLAlchemySession`` keyed by ``fortune_{fortune_id}`` so
    repeated calls build on prior Q&A. Returns the structured narrative
    directly — the frontend renders it inline in the Ask tab.
    """
    await smart_rate_limit(request, scope=RateLimitScope.FORTUNE_ASK, weight=1)

    store = get_run_state()
    lock_token = await store.acquire_lock(fortune_id, ttl=ASK_LEASE_TTL_SECONDS)
    if lock_token is None:
        raise HTTPException(
            status_code=409,
            detail="This fortune is busy; wait for the current response to finish.",
            headers={"Retry-After": "3"},
        )
    try:
        try:
            return await asyncio.wait_for(
                _ask_fortune_locked(fortune_id, request_body, store=store),
                timeout=ASK_REQUEST_TIMEOUT_SECONDS,
            )
        except asyncio.TimeoutError as exc:
            raise HTTPException(
                status_code=504,
                detail="The answer took too long; retry this saved question.",
            ) from exc
    finally:
        await store.release_lock(fortune_id, lock_token)


async def _ask_fortune_locked(
    fortune_id: str,
    request_body: AskRequest,
    *,
    store,
) -> AskResponse:
    """Execute one serialized Ask turn."""
    fortune_session = await store.get(fortune_id)
    repo = await get_repository()

    try:
        fid_for_status = uuid.UUID(fortune_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid fortune_id")
    payload_hash = _ask_payload_hash(request_body)
    try:
        replay = await _completed_ask_replay(
            repo,
            fid_for_status,
            request_body.client_request_id,
            payload_hash,
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("[FORTUNE] Ask idempotency lookup failed: %s", exc)
        raise HTTPException(status_code=503, detail="Ask retry protection unavailable.")
    if replay is not None:
        return replay

    # Always attempt durable mechanics hydration. Redis intentionally strips
    # heavyweight ``analysis`` and Person B data; a truthy hot projection is
    # therefore not proof that Ask has the authoritative reading context.
    foundation: dict[str, Any] | None = None
    latest_narrative: dict[str, Any] | None = None
    hot_foundation = (
        fortune_session.latest_foundation
        if fortune_session is not None and fortune_session.latest_foundation
        else None
    )
    hydrated = await _hydrate_foundation_from_snapshot(repo, fortune_id)
    if hydrated is not None:
        # Live-only values (notably Person B before the first snapshot write)
        # may enrich the durable projection, while hydrated analysis fills the
        # fields intentionally removed by Redis serialization.
        foundation = _merge_ask_foundation(hydrated, hot_foundation)
        if "analysis" not in foundation:
            foundation = None
        elif fortune_session is not None:
            fortune_session.latest_foundation = foundation
    elif hot_foundation is not None and hot_foundation.get("analysis") is not None:
        foundation = hot_foundation

    if fortune_session is not None:
        latest_narrative = fortune_session.latest_narrative
    if latest_narrative is None and hydrated is not None:
        # Also rehydrate latest_narrative so the specialist sees the same
        # human-facing result the user is asking about after a restart.
        try:
            fid = uuid.UUID(fortune_id)
            row = await repo.get_snapshot(fid) if repo.available else None
            if row:
                latest_narrative = _unpack_jsonb(row.get("latest_narrative"))
                if fortune_session is not None and latest_narrative is not None:
                    fortune_session.latest_narrative = latest_narrative
        except Exception as exc:
            logger.debug("[FORTUNE] /ask narrative rehydrate skipped: %s", exc)

    if foundation is None:
        # If we have neither session nor snapshot, the fortune either does not
        # exist or the initial pipeline never persisted. Return 404 vs 409
        # accordingly so the client differentiates "gone" from "not ready".
        if fortune_session is None:
            # Last-chance check: does the fortune row exist at all?
            try:
                fid = uuid.UUID(fortune_id)
                row = await repo.get_fortune(fid) if repo.available else None
            except ValueError:
                row = None
            if row is None:
                raise HTTPException(status_code=404, detail="Fortune not found")
        raise HTTPException(
            status_code=409,
            detail="Initial reading not yet complete; cannot answer follow-ups.",
        )

    # Done-gate: foundation reconstructability is necessary but not sufficient.
    # Ask must wait for a successful (status=done) initial/action reading.
    reading_status = await _latest_non_ask_run_status(repo, fid_for_status)
    if reading_status is not None and reading_status != "done":
        raise HTTPException(
            status_code=409,
            detail=(
                "Reading not complete — ask is available after a successful reading."
            ),
        )

    # Claim/replay only after readiness checks. A retry carries the same UUID;
    # completed work is returned without another model call or session write.
    try:
        idempotency = await repo.claim_ask_request(
            fortune_id=fid_for_status,
            client_request_id=request_body.client_request_id,
            payload_hash=payload_hash,
        )
    except Exception as exc:
        logger.exception("[FORTUNE] Ask idempotency claim failed: %s", exc)
        raise HTTPException(status_code=503, detail="Ask retry protection unavailable.")
    if idempotency is None:
        raise HTTPException(
            status_code=503,
            detail="Ask retry protection unavailable.",
        )
    if idempotency.get("payload_hash") != payload_hash:
        raise HTTPException(
            status_code=409,
            detail="This Ask request ID was already used for different input.",
        )
    if not idempotency.get("claimed"):
        if idempotency.get("status") == "done" and idempotency.get("response_json"):
            saved = _unpack_jsonb(idempotency["response_json"])
            if isinstance(saved, dict):
                pending_items = _unpack_jsonb(idempotency.get("session_items"))
                if (
                    not idempotency.get("conversation_committed")
                    and isinstance(pending_items, list)
                    and pending_items
                ):
                    try:
                        durable = await get_ask_session(fortune_id)
                        if durable is not None:
                            serialized_items = await serialize_session_items(
                                durable, pending_items,
                            )
                            await repo.commit_ask_conversation(
                                fortune_id=fid_for_status,
                                client_request_id=request_body.client_request_id,
                                lease_token=idempotency["lease_token"],
                                delivery_id=idempotency["delivery_id"],
                                session_id=durable.session_id,
                                serialized_items=serialized_items,
                            )
                    except Exception as exc:
                        logger.warning("[FORTUNE] Ask memory outbox repair failed: %s", exc)
                        saved["degraded_memory"] = True
                return AskResponse.model_validate(saved)
        raise HTTPException(
            status_code=409,
            detail="This question is still being prepared; retry shortly.",
            headers={"Retry-After": "3"},
        )

    lease_token = idempotency.get("lease_token")
    if not isinstance(lease_token, uuid.UUID):
        try:
            lease_token = uuid.UUID(str(lease_token))
        except (TypeError, ValueError) as exc:
            raise HTTPException(
                status_code=503, detail="Ask retry protection unavailable.",
            ) from exc
    delivery_id = idempotency.get("delivery_id")
    if not isinstance(delivery_id, uuid.UUID):
        try:
            delivery_id = uuid.UUID(str(delivery_id))
        except (TypeError, ValueError) as exc:
            raise HTTPException(
                status_code=503, detail="Ask retry protection unavailable.",
            ) from exc

    # Build a ctx from whichever source we have — prefer live session for
    # birth/focus/tone (most accurate), fall back to sensible defaults.
    req_src = fortune_session.request if fortune_session is not None else None
    original_input = _build_ask_original_input(req_src)
    if original_input is None:
        candidate = foundation.get("request_context")
        original_input = candidate if isinstance(candidate, dict) and candidate else None
    if original_input is None:
        # Backward compatibility for snapshots created before request_context
        # existed. Person B cannot be reconstructed for those legacy rows, but
        # the durable fortune record still preserves focus and primary inputs,
        # preventing a career/cycle/occasion question from becoming "wish".
        try:
            record = await repo.get_fortune(fid_for_status)
            if record is not None:
                original_input = {
                    "birth_iso": record.birth_iso,
                    "timezone": record.timezone,
                    "gender": record.gender,
                    "birth_time_unknown": bool(record.birth_time_unknown),
                    "focus": record.focus,
                    "original_question": record.question,
                    "tone": record.tone,
                }
        except Exception as exc:
            logger.debug("[FORTUNE] legacy Ask request-context hydration skipped: %s", exc)

    # The idempotency row owns exactly one activity-rail run. Creation and
    # attachment happen in one transaction, so retries cannot orphan runs.
    try:
        ask_run_id = await repo.ensure_ask_run(
            fortune_id=fid_for_status,
            client_request_id=request_body.client_request_id,
            lease_token=lease_token,
        )
    except Exception as exc:
        logger.exception("[FORTUNE] ask run creation failed: %s", exc)
        await _mark_ask_request_failed(
            repo, fid_for_status, request_body.client_request_id, lease_token,
        )
        raise HTTPException(status_code=503, detail="Ask activity persistence unavailable.")
    new_run_id = str(ask_run_id)
    try:
        settings = get_settings()
        ctx = FortuneRunContext(
            fortune_id=fortune_id,
            surface_id=(fortune_session.surface_id if fortune_session else settings.default_surface_id),
            run_id=new_run_id,
            question=request_body.question,
            focus=(req_src.focus if req_src else (original_input or {}).get("focus")),
            tone=(req_src.tone if req_src else (original_input or {}).get("tone")),
            birth_iso=(req_src.birth_iso if req_src else (original_input or {}).get("birth_iso", "")),
            timezone=(req_src.timezone if (req_src and req_src.timezone) else (original_input or {}).get("timezone", settings.default_timezone)),
            birth_time_unknown=(req_src.birth_time_unknown if req_src else bool((original_input or {}).get("birth_time_unknown", False))),
            gender=(req_src.gender if (req_src and req_src.gender) else (original_input or {}).get("gender", "unknown")),
        )

        # Try to attach durable ask-session memory. If Supabase is unreachable the
        # answer is still useful (stateless triage) — mark degraded_memory so the
        # client can hint at the loss of continuity.
        degraded_memory = False
        ask_session: BufferedAskSession | None = None
        durable_ask_session = None
        try:
            durable_ask_session = await get_ask_session(fortune_id)
            if durable_ask_session is None:
                degraded_memory = True
            else:
                ask_session = BufferedAskSession(durable_ask_session)
        except Exception as exc:
            logger.warning("[FORTUNE] ask-session acquisition failed: %s", exc)
            degraded_memory = True

        try:
            narrative = await run_triage(
                ctx,
                foundation=foundation,
                question=request_body.question,
                session=ask_session,
                original_input=original_input,
                latest_narrative=latest_narrative,
                selected_section=(
                    request_body.context.model_dump(exclude_none=True)
                    if request_body.context is not None
                    else None
                ),
                ask_mode=True,
            )
        except Exception as exc:
            logger.exception("[FORTUNE] /ask triage failed: %s", exc)
            try:
                await repo.update_run_status(
                    uuid.UUID(new_run_id), "error", error_message=str(exc)[:500],
                )
            except Exception:
                pass
            await _mark_ask_request_failed(
                repo, fid_for_status, request_body.client_request_id, lease_token,
            )
            raise HTTPException(status_code=500, detail="Ask run failed.")

        # Same output guardrail as the initial narrative pipeline. Bound via the
        # existing ensure_narrative_guardrail surface (policy agent is one turn).
        try:
            await ensure_narrative_guardrail(ctx, narrative, agent=ASK_AGENT)
        except OutputGuardrailTripwireTriggered:
            # The raw rejected output only exists in the buffered session. Drop
            # it so it cannot reappear through hydration or influence a retry.
            if ask_session is not None:
                ask_session.discard()
            response = AskResponse(
                fortune_id=fortune_id,
                run_id=new_run_id,
                narrative=_ask_safe_rejection_narrative(),
                degraded_memory=degraded_memory,
                chain_status="disabled",
            )
            safe_items = [
                {"role": "user", "content": request_body.question},
                {"role": "assistant", "content": response.narrative["tldr"]},
            ]
            try:
                if durable_ask_session is not None:
                    serialized_items = await serialize_session_items(
                        durable_ask_session, safe_items,
                    )
                    await repo.complete_ask_with_conversation(
                        fortune_id=fid_for_status,
                        client_request_id=request_body.client_request_id,
                        lease_token=lease_token,
                        delivery_id=delivery_id,
                        response=response.model_dump(mode="json"),
                        session_items=safe_items,
                        session_id=durable_ask_session.session_id,
                        serialized_items=serialized_items,
                        run_id=ask_run_id,
                        run_status="failed_guardrail",
                    )
                else:
                    await _complete_ask_request_or_503(
                        repo, fid_for_status, request_body.client_request_id,
                        lease_token, response, run_id=ask_run_id,
                        run_status="failed_guardrail", session_items=safe_items,
                        conversation_committed=False,
                    )
            except HTTPException:
                raise
            except Exception as exc:
                logger.warning("[FORTUNE] safe rejection persistence failed: %s", exc)
                await _mark_ask_request_failed(
                    repo, fid_for_status, request_body.client_request_id, lease_token,
                )
                raise HTTPException(
                    status_code=503,
                    detail="Answer persistence is temporarily unavailable; retry safely.",
                ) from exc
            return response
        except Exception as exc:
            # Non-tripwire guardrail failure: never return the unvetted answer.
            logger.exception("[FORTUNE] /ask guardrail failed: %s", exc)
            if ask_session is not None:
                ask_session.discard()
            try:
                await repo.update_run_status(
                    uuid.UUID(new_run_id), "error", error_message=str(exc)[:500],
                )
            except Exception:
                pass
            await _mark_ask_request_failed(
                repo, fid_for_status, request_body.client_request_id, lease_token,
            )
            raise HTTPException(status_code=500, detail="Ask run failed.")

        response = AskResponse(
            fortune_id=fortune_id,
            run_id=new_run_id,
            narrative=narrative.model_dump(),
            degraded_memory=degraded_memory,
            chain_status="disabled",
        )
        # Store the replayable response before publishing the new session turn.
        # A completion failure therefore leaves no durable conversation side
        # effect, and retrying the same UUID is safe.
        session_items = (
            [_to_jsonable(item) for item in ask_session.pending_items()]
            if ask_session is not None
            else []
        )
        if not session_items:
            # Even when SDK-memory acquisition is degraded, the idempotency
            # row remains a durable outbox for the approved visible turn. The
            # conversation endpoint displays it immediately and repairs it
            # into agent_messages when the SDK session becomes available.
            session_items = [
                {"role": "user", "content": request_body.question},
                {"role": "assistant", "content": narrative.tldr},
            ]
        try:
            if ask_session is not None and session_items:
                serialized_items = await serialize_session_items(
                    durable_ask_session, session_items,
                )
                await repo.complete_ask_with_conversation(
                    fortune_id=fid_for_status,
                    client_request_id=request_body.client_request_id,
                    lease_token=lease_token,
                    delivery_id=delivery_id,
                    response=response.model_dump(mode="json"),
                    session_items=session_items,
                    session_id=durable_ask_session.session_id,
                    serialized_items=serialized_items,
                    run_id=ask_run_id,
                )
            else:
                await _complete_ask_request_or_503(
                    repo, fid_for_status, request_body.client_request_id,
                    lease_token, response, run_id=ask_run_id,
                    session_items=session_items,
                    conversation_committed=False,
                )
        except Exception as exc:
            # Do not report a run as done unless both the replay response and
            # approved conversation turn are durable.
            logger.warning("[FORTUNE] atomic Ask completion failed: %s", exc)
            await _mark_ask_request_failed(
                repo, fid_for_status, request_body.client_request_id, lease_token,
            )
            try:
                await repo.update_run_status(
                    uuid.UUID(new_run_id), "error", error_message=str(exc)[:500],
                )
            except Exception:
                pass
            if isinstance(exc, HTTPException):
                raise
            raise HTTPException(
                status_code=503,
                detail="Answer persistence is temporarily unavailable; retry safely.",
            ) from exc

        # No snapshot upsert — Ask turns layer on top of the existing snapshot.
        # Run completion was committed atomically with the response above.
        return response
    except asyncio.CancelledError:
        await _mark_ask_request_failed(
            repo, fid_for_status, request_body.client_request_id, lease_token,
        )
        try:
            await repo.update_run_status(
                uuid.UUID(new_run_id), "error", error_message="Ask request timed out",
            )
        except Exception:
            pass
        raise
    finally:
        # Evict after triage/status work; never raise from cleanup.
        try:
            from .tracing import get_trace_processor
            get_trace_processor().evict_run(new_run_id)
        except Exception:
            pass


@router.post("/{fortune_id}/cancel")
async def cancel_fortune(fortune_id: str, request: Request):
    """Pause/cancel an in-flight reading.

    Writes the Redis cancel flag (and session.cancel_requested) via
    ``store.request_cancel``. The worker-owned publisher task
    (``run_and_publish``) polls that flag between stages and exits the run
    as interrupted. Idempotent: calling it on a completed session is a no-op.
    """
    store = get_run_state()
    session = await store.get(fortune_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Fortune session not found")
    await store.request_cancel(fortune_id)
    logger.info("[FORTUNE] %s cancel requested", fortune_id)
    return {"fortune_id": fortune_id, "cancelled": True}


@router.get("/{fortune_id}/trace")
async def get_fortune_trace(fortune_id: str, request: Request):
    """Return redacted Glass Box projections for the fortune's latest run.

    Shape matches live SSE ``payload.trace`` so the frontend renders one list.
    DB rows are already redacted; columns are allowlisted explicitly.
    """
    await smart_rate_limit(request, scope=RateLimitScope.FORTUNE_REPLAY, weight=1)

    try:
        fid = uuid.UUID(fortune_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid fortune_id")

    repo = await get_repository()
    if not repo.available:
        raise HTTPException(status_code=503, detail="Fortune store unavailable")

    record = await repo.get_fortune(fid)
    if record is None:
        raise HTTPException(status_code=404, detail="Fortune not found")

    run_id, events = await repo.list_trace_projections(fid)
    return {
        "fortune_id": fortune_id,
        "run_id": str(run_id) if run_id else None,
        "events": events,
    }


@router.get("/{fortune_id}/conversation")
async def get_fortune_conversation(fortune_id: str, request: Request):
    """Return Ask conversation turns from SQLAlchemySession for MemoryPanel.

    Only user/assistant MESSAGE items; tool/reasoning items excluded.
    Text truncated to 2000 chars. Empty list when no session exists.
    """
    await smart_rate_limit(request, scope=RateLimitScope.FORTUNE_REPLAY, weight=1)

    try:
        uuid.UUID(fortune_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid fortune_id")

    fid = uuid.UUID(fortune_id)
    turns = await list_conversation_turns(fortune_id)
    pending: list[dict[str, Any]] = []
    try:
        repo = await get_repository()
        if repo.available:
            pending = await repo.list_pending_ask_conversations(fortune_id=fid)
    except Exception as exc:
        logger.warning("[FORTUNE] conversation outbox read failed for %s: %s", fortune_id, exc)

    if pending:
        durable = None
        try:
            durable = await get_ask_session(fortune_id)
        except Exception as exc:
            logger.warning("[FORTUNE] conversation repair session failed: %s", exc)
        if durable is not None:
            repaired_any = False
            unrepaired: list[dict[str, Any]] = []
            for row in pending:
                items = _unpack_jsonb(row.get("session_items"))
                if not isinstance(items, list) or not items:
                    continue
                try:
                    serialized = await serialize_session_items(durable, items)
                    await repo.commit_ask_conversation(
                        fortune_id=fid,
                        client_request_id=row["client_request_id"],
                        lease_token=row["lease_token"],
                        delivery_id=row["delivery_id"],
                        session_id=durable.session_id,
                        serialized_items=serialized,
                    )
                    repaired_any = True
                except Exception as exc:
                    logger.warning("[FORTUNE] conversation outbox repair failed: %s", exc)
                    unrepaired.append(row)
            if repaired_any:
                turns = await list_conversation_turns(fortune_id)
            pending = unrepaired

        # If memory is still degraded (or a repair failed), serve the approved
        # durable outbox so a successful Ask turn never disappears on reload.
        for row in pending:
            items = _unpack_jsonb(row.get("session_items"))
            if isinstance(items, list):
                turns.extend(
                    conversation_turns_from_items(
                        items, row.get("updated_at"),
                        client_request_id=row.get("client_request_id"),
                        delivery_id=row.get("delivery_id"),
                    )
                )

    # Stable request identities let the client reconcile an ambiguous success
    # with its optimistic/error pair, even when the question text is repeated.
    # The durable Ask outbox is authoritative for new turns; SDK-only turns
    # predating the outbox are retained as a legacy prefix.
    try:
        repo = await get_repository()
        records = (
            await repo.list_ask_conversations(fortune_id=fid)
            if repo.available else []
        )
        identified: list[dict[str, Any]] = []
        for row in records:
            items = _unpack_jsonb(row.get("session_items"))
            if isinstance(items, list):
                identified.extend(conversation_turns_from_items(
                    items, row.get("updated_at"),
                    client_request_id=row.get("client_request_id"),
                    delivery_id=row.get("delivery_id"),
                ))
        if identified:
            legacy_count = max(0, len(turns) - len(identified))
            turns = turns[:legacy_count] + identified
    except Exception as exc:
        logger.warning("[FORTUNE] conversation identity projection failed: %s", exc)
    return {
        "fortune_id": fortune_id,
        "turns": turns,
    }


@router.post("/{fortune_id}/simulate")
async def simulate_fortune(fortune_id: str, request: Request):
    """Birth-Time Uncertainty Simulator — enumerate all 12 Earthly Branch
    hour hypotheses and return a stability report plus per-branch chart data.

    Deterministic (no LLM) but ~12× the compute of a single foundation run,
    so it gets its own rate-limit bucket at weight 4 — lower than /create's
    full-pipeline cost but higher than /action's single-LLM triage.

    When the hot Redis session is gone, hydrate birth_iso/timezone from the
    durable fortune row instead of 404ing.
    """
    await smart_rate_limit(request, scope=RateLimitScope.FORTUNE_SIMULATE, weight=4)

    store = get_run_state()
    session = await store.get(fortune_id)

    birth_iso: str | None = None
    timezone_name: str | None = None
    if session is not None:
        birth_iso = session.request.birth_iso
        timezone_name = session.request.timezone or get_settings().default_timezone
    else:
        try:
            fid = uuid.UUID(fortune_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid fortune_id")
        repo = await get_repository()
        record = await repo.get_fortune(fid) if repo.available else None
        if record is None:
            raise HTTPException(status_code=404, detail="Fortune not found")
        birth_iso = record.birth_iso
        timezone_name = record.timezone or get_settings().default_timezone

    try:
        payload = simulate_birth_time(birth_iso, timezone_name)
    except Exception as exc:
        logger.exception("[FORTUNE] simulate failed: %s", exc)
        raise HTTPException(status_code=500, detail="Simulation failed.")

    payload["fortune_id"] = fortune_id
    return payload


@router.post("/{fortune_id}/correction")
async def submit_correction(
    fortune_id: str,
    request_body: CorrectionRequest,
    request: Request,
):
    """Store user correction for a specific year prediction.

    Writes through to ``fortune_snapshot.latest_retrodictions.corrections`` so
    the note survives a worker restart and a subsequent replay can render it.
    """
    await smart_rate_limit(request, scope=RateLimitScope.FORTUNE_CORRECTION, weight=1)

    try:
        fid = uuid.UUID(fortune_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid fortune_id")

    repo = await get_repository()
    store = get_run_state()
    session = await store.get(fortune_id)

    # The fortune must exist somewhere. Accept the correction as long as
    # EITHER the in-memory session OR the durable row resolves.
    if session is None:
        if not repo.available or await repo.get_fortune(fid) is None:
            raise HTTPException(status_code=404, detail="Fortune not found")

    corrected_at = datetime.now(timezone.utc)
    record = {
        "user_note": request_body.user_note,
        "corrected_at": corrected_at.isoformat(),
    }

    if repo.available:
        try:
            persisted = await repo.upsert_correction(
                fid,
                year=request_body.year,
                user_note=request_body.user_note,
                corrected_at=corrected_at,
            )
            if persisted is not None:
                record = persisted
        except Exception as exc:
            logger.warning("[FORTUNE] correction persistence failed: %s", exc)

    return {
        "fortune_id": fortune_id,
        "year": request_body.year,
        "correction": record,
    }
