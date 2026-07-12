"""Ming Engine fortune API routes.

POST /api/fortune/create      — create a fortune session
GET  /api/fortune/{id}        — replay completed snapshot (CF-cacheable)
GET  /api/fortune/{id}/stream — SSE stream of A2UI messages
POST /api/fortune/{id}/action — follow-up action (re-runs from subset agent)
"""

from __future__ import annotations

import asyncio
import json as _json
import logging
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from fastapi import APIRouter, Header, HTTPException, Request, Response
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

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
        FOUNDATION_VERSION,
        FortuneRunContext,
        GUARDRAIL_AGENT,
        GuardrailOutput,
        NARRATIVE_AGENTS,
        NARRATIVE_SCHEMA_VERSION,
        NarrativeOutput,
        _narrative_mode,
        _promote_narrative_to_enriched,
        repair_occasion_narrative,
        run_foundation,
        run_guardrail,
        run_narrative_streamed,
    )
    from .config import get_settings
    from .stream_bridge import FortuneStreamBridge
    from .store import get_repository, FortuneRepository
    from .triage import ALLOWED_ACTION_IDS, normalize_action_focus, run_triage
    from .session_store import get_ask_session
    from .chain_store import (
        get_response_chain,
        set_response_chain,
    )
    from .simulator import simulate_birth_time
    from .naming import canonical_function
    from ._thinking_heartbeat import HeartbeatTick, iter_with_heartbeats
    from .state import (
        CreateFortuneRequest as _StateCreateFortuneRequest,
        FortuneSession,
        PersonBirthInfo as _StatePersonBirthInfo,
        RuntimeStatus,
        get_run_state,
        is_v2_pipeline,
        pipeline_mode,
    )
    from . import events as fortune_events
    from . import pipeline as fortune_pipeline
except ImportError:
    from agents import (  # type: ignore[no-redef]
        DEFAULT_FOLLOW_UP_BUTTONS,
        EnrichedNarrativeOutput,
        FOUNDATION_VERSION,
        FortuneRunContext,
        GUARDRAIL_AGENT,
        GuardrailOutput,
        NARRATIVE_AGENTS,
        NARRATIVE_SCHEMA_VERSION,
        NarrativeOutput,
        _narrative_mode,
        _promote_narrative_to_enriched,
        repair_occasion_narrative,
        run_foundation,
        run_guardrail,
        run_narrative_streamed,
    )
    from config import get_settings  # type: ignore[no-redef]
    from stream_bridge import FortuneStreamBridge  # type: ignore[no-redef]
    from store import get_repository, FortuneRepository  # type: ignore[no-redef]
    from triage import ALLOWED_ACTION_IDS, normalize_action_focus, run_triage  # type: ignore[no-redef]
    from session_store import get_ask_session  # type: ignore[no-redef]
    from chain_store import (  # type: ignore[no-redef]
        get_response_chain,
        set_response_chain,
    )
    from simulator import simulate_birth_time  # type: ignore[no-redef]
    from naming import canonical_function  # type: ignore[no-redef]
    from _thinking_heartbeat import HeartbeatTick, iter_with_heartbeats  # type: ignore[no-redef]
    from state import (  # type: ignore[no-redef]
        CreateFortuneRequest as _StateCreateFortuneRequest,
        FortuneSession,
        PersonBirthInfo as _StatePersonBirthInfo,
        RuntimeStatus,
        get_run_state,
        is_v2_pipeline,
        pipeline_mode,
    )
    import events as fortune_events  # type: ignore[no-redef]
    import pipeline as fortune_pipeline  # type: ignore[no-redef]


router = APIRouter(prefix="/api/fortune", tags=["fortune"])


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


class AskRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=500)


class AskResponse(BaseModel):
    fortune_id: str
    run_id: str
    narrative: dict[str, Any]
    # Degraded is true when ask-session memory could not be used (e.g. Supabase
    # unreachable) — the answer is still valid but it has no conversation history.
    degraded_memory: bool = False
    chain_status: str = "disabled"


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
    }
    person_b = foundation.get("person_b")
    if person_b:
        analysis_b = person_b.get("analysis")
        payload["person_b"] = {
            "pillars": _to_jsonable(person_b.get("pillars")),
            "elements": _to_jsonable(person_b.get("elements")),
            "mechanics": {
                "hidden_stems": _to_jsonable(getattr(analysis_b, "hidden_stems", None)),
                "ten_gods": _to_jsonable(getattr(analysis_b, "ten_gods", None)),
            },
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
    if not all(mechanics.get(k) for k in required):
        return None
    try:
        from .bazi_engine import FullBaziAnalysis
    except ImportError:
        from bazi_engine import FullBaziAnalysis  # type: ignore[no-redef]

    analysis_payload = {
        "pillars": mechanics.get("pillars") or pillars.get("pillars") or {},
        "hidden_stems": mechanics["hidden_stems"],
        "ten_gods": mechanics["ten_gods"],
        "interactions": mechanics["interactions"],
        "seasonal_strength": mechanics["seasonal_strength"],
        "luck_pillars": mechanics.get("luck_pillars") or [],
        "annual_pillars": mechanics.get("annual_pillars") or [],
        "enhanced_element_counts": mechanics.get("enhanced_element_counts") or {},
        "element_by_source": mechanics.get("element_by_source") or {},
        "harmony_score": mechanics.get("harmony_score") or 0.0,
    }
    try:
        analysis = FullBaziAnalysis.model_validate(analysis_payload)
    except Exception as exc:
        logger.warning(
            "[FORTUNE] snapshot mechanics failed to rehydrate analysis: %s", exc,
        )
        return None

    return {
        "analysis": analysis,
        "pillars": pillars.get("pillars") or {},
        "elements": pillars.get("elements") or {},
        "references": references_block.get("items") or [],
        "retrodictions": [],
        "trace": None,
    }


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

    if is_v2_pipeline():
        try:
            await fortune_events.get_events_redis(required=True)
        except fortune_events.RedisUnavailable as exc:
            logger.error("[FORTUNE] Redis unavailable at create (v2): %s", exc)
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
            logger.error("[FORTUNE] state put failed at create (v2): %s", exc)
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
        # DEBT: run task dies with its owning worker; no runner service/lease.
        # Upgrade when workers > 1 or deploys must not kill active runs.
        asyncio.create_task(fortune_pipeline.run_and_publish_safe(session))
    else:
        await store.put(session)

    logger.info("[FORTUNE] create fortune=%s run=%s focus=%s degraded=%s pipeline=%s",
                fortune_id_str, run_id_str, normalized.focus, degraded_persistence, pipeline_mode())

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
    payload = {
        "fortune_id": fortune_id,
        "snapshot_version": snapshot_version,
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
):
    await smart_rate_limit(request, scope=RateLimitScope.FORTUNE_STREAM, weight=1)

    store = get_run_state()
    session = await store.get(fortune_id)

    # Resume cursor: Last-Event-ID header OR ?after=<redis-id>
    last_event_id = request.headers.get("last-event-id") or request.headers.get("Last-Event-ID")
    cursor = after or last_event_id or "0-0"

    if is_v2_pipeline():
        return await _stream_fortune_v2(fortune_id, request, session, store, cursor)

    if session is None:
        raise HTTPException(status_code=404, detail="Fortune session not found")

    # v1: single in-flight stream per fortune (process-local lock semantics)
    if await store.lock_is_held_async(fortune_id):
        raise HTTPException(
            status_code=409,
            detail="A stream is already in progress for this fortune.",
            headers={"Retry-After": "5"},
        )

    lock_token = await store.acquire_lock(fortune_id)
    if lock_token is None:
        raise HTTPException(
            status_code=409,
            detail="A stream is already in progress for this fortune.",
            headers={"Retry-After": "5"},
        )

    async def event_generator():
        try:
            async for frame in fortune_pipeline.iter_fortune_sse_frames(
                session, request=request, store=store,
            ):
                yield frame
        finally:
            # Session object is mutated in-place in the memory overlay; sync once.
            try:
                await store.put(session)
            except Exception:
                pass
            await store.release_lock(fortune_id, lock_token)

    return StreamingResponse(
        with_heartbeat(event_generator()),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


async def _stream_fortune_v2(
    fortune_id: str,
    request: Request,
    session,
    store,
    cursor: str,
):
    """Tail Redis Streams for a run. Independent cursors — no consumer groups."""
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
            async for entry_id, envelope in fortune_events.tail_envelopes(
                run_id, after=cursor or "0-0",
            ):
                if await request.is_disconnected():
                    return
                yield fortune_events.format_sse(envelope, event_id=entry_id)
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

    # Refuse to rotate run_id under an active stream — otherwise the in-flight
    # generator consumes `pending_action_id` set by the NEXT click and
    # dispatches it as if it belonged to the current run.
    if await store.lock_is_held_async(fortune_id):
        raise HTTPException(
            status_code=409,
            detail="A stream is active; wait for it to finish before choosing a new action.",
            headers={"Retry-After": "3"},
        )

    # Update focus based on action
    normalized_focus = normalize_action_focus(request_body.action_id)
    if normalized_focus in {"career", "relationship", "year"}:
        session.request = session.request.model_copy(update={"focus": normalized_focus})

    # Persist a new run row for this follow-up action. Always rotate to a
    # fresh run id — even on persistence failure — so action-stream
    # attribution stays distinct from the previous run.
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
        request_body.payload.get("question") if isinstance(request_body.payload, dict) else None
    )
    session.touch(RuntimeStatus.initialized)
    await store.put(session)

    if is_v2_pipeline():
        await fortune_events.set_run_record(
            new_run_id, fortune_id=fortune_id, status="queued",
        )
        # DEBT: run task dies with its owning worker; no runner service/lease.
        # Upgrade when workers > 1 or deploys must not kill active runs.
        asyncio.create_task(fortune_pipeline.run_and_publish_safe(session))

    return {
        "fortune_id": fortune_id,
        "run_id": new_run_id,
        "action_id": request_body.action_id,
        "focus": session.request.focus,
        "status": session.status.value,
        "stream_url": f"/api/fortune/{fortune_id}/stream",
    }


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
    fortune_session = await store.get(fortune_id)
    repo = await get_repository()

    # Preferred path: hot in-memory session with live foundation.
    foundation: dict[str, Any] | None = None
    latest_narrative: dict[str, Any] | None = None
    if fortune_session is not None and fortune_session.latest_foundation:
        foundation = fortune_session.latest_foundation
        latest_narrative = fortune_session.latest_narrative
    else:
        hydrated = await _hydrate_foundation_from_snapshot(repo, fortune_id)
        if hydrated is not None:
            foundation = hydrated
            if fortune_session is not None:
                fortune_session.latest_foundation = hydrated
            # Also rehydrate latest_narrative from the snapshot so the
            # specialist still has the human-facing context the user is
            # currently looking at, even after a restart / cross-worker route.
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

    # Build a ctx from whichever source we have — prefer live session for
    # birth/focus/tone (most accurate), fall back to sensible defaults.
    req_src = fortune_session.request if fortune_session is not None else None

    # Persist a new run row so Ask turns show up in the Activity Rail distinctly.
    new_run_id = str(uuid.uuid4())
    try:
        run_rec = await repo.create_run(
            fortune_id=uuid.UUID(fortune_id),
            run_kind="ask",
        )
        if run_rec:
            new_run_id = str(run_rec.id)
    except Exception as exc:
        logger.warning("[FORTUNE] ask run persistence failed: %s", exc)

    settings = get_settings()
    ctx = FortuneRunContext(
        fortune_id=fortune_id,
        surface_id=(fortune_session.surface_id if fortune_session else settings.default_surface_id),
        run_id=new_run_id,
        question=request_body.question,
        focus=(req_src.focus if req_src else None),
        tone=(req_src.tone if req_src else None),
        birth_iso=(req_src.birth_iso if req_src else ""),
        timezone=(req_src.timezone if (req_src and req_src.timezone) else settings.default_timezone),
        birth_time_unknown=(req_src.birth_time_unknown if req_src else False),
        gender=(req_src.gender if (req_src and req_src.gender) else "unknown"),
    )

    # Try to attach durable ask-session memory. If Supabase is unreachable the
    # answer is still useful (stateless triage) — mark degraded_memory so the
    # client can hint at the loss of continuity.
    degraded_memory = False
    ask_session = None
    try:
        ask_session = await get_ask_session(fortune_id)
        if ask_session is None:
            degraded_memory = True
    except Exception as exc:
        logger.warning("[FORTUNE] ask-session acquisition failed: %s", exc)
        degraded_memory = True

    previous_response_id = await get_response_chain(fortune_id)
    response_id_sink: list[str] = []

    try:
        narrative = await run_triage(
            ctx,
            foundation=foundation,
            question=request_body.question,
            session=ask_session,
            original_input=_build_ask_original_input(req_src),
            latest_narrative=latest_narrative,
            ask_mode=True,
            previous_response_id=previous_response_id,
            response_id_sink=response_id_sink,
        )
    except Exception as exc:
        logger.exception("[FORTUNE] /ask triage failed: %s", exc)
        try:
            await repo.update_run_status(
                uuid.UUID(new_run_id), "error", error_message=str(exc)[:500],
            )
        except Exception:
            pass
        raise HTTPException(status_code=500, detail="Ask run failed.")

    # Mark the run complete. No snapshot upsert — /ask turns layer on top of
    # the existing fortune_snapshot rather than replacing it.
    try:
        await repo.update_run_status(uuid.UUID(new_run_id), "done")
    except Exception as exc:
        logger.warning("[FORTUNE] ask run status update failed: %s", exc)

    chain_status = "disabled"
    if previous_response_id:
        chain_status = "active"
    if response_id_sink:
        wrote = await set_response_chain(fortune_id, response_id_sink[-1])
        if wrote and chain_status == "disabled":
            chain_status = "seeded"

    return AskResponse(
        fortune_id=fortune_id,
        run_id=new_run_id,
        narrative=narrative.model_dump(),
        degraded_memory=degraded_memory,
        chain_status=chain_status,
    )


@router.post("/{fortune_id}/cancel")
async def cancel_fortune(fortune_id: str, request: Request):
    """Pause/cancel an in-flight reading.

    Sets ``session.cancel_requested = True``. The SSE stream loop polls this
    flag between SDK events and calls ``stream_result.cancel()`` gracefully,
    then closes the stream. Idempotent: calling it on a completed session is
    a no-op.
    """
    store = get_run_state()
    session = await store.get(fortune_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Fortune session not found")
    await store.request_cancel(fortune_id)
    logger.info("[FORTUNE] %s cancel requested", fortune_id)
    return {"fortune_id": fortune_id, "cancelled": True}


@router.post("/{fortune_id}/simulate")
async def simulate_fortune(fortune_id: str, request: Request):
    """Birth-Time Uncertainty Simulator — enumerate all 12 Earthly Branch
    hour hypotheses and return a stability report plus per-branch chart data.

    Deterministic (no LLM) but ~12× the compute of a single foundation run,
    so it gets its own rate-limit bucket at weight 4 — lower than /create's
    full-pipeline cost but higher than /action's single-LLM triage.
    """
    await smart_rate_limit(request, scope=RateLimitScope.FORTUNE_SIMULATE, weight=4)

    store = get_run_state()
    session = await store.get(fortune_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Fortune session not found")

    try:
        payload = simulate_birth_time(
            session.request.birth_iso,
            session.request.timezone or get_settings().default_timezone,
        )
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
