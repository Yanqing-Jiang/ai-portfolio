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
        FortuneRunContext,
        GuardrailOutput,
        NarrativeOutput,
        run_foundation,
        run_guardrail,
        run_narrative_streamed,
    )
    from .config import get_settings
    from .stream_bridge import FortuneStreamBridge
    from .store import get_repository, FortuneRepository
    from .triage import run_triage
    from .session_store import get_ask_session
    from .simulator import simulate_birth_time
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
    from store import get_repository, FortuneRepository  # type: ignore[no-redef]
    from triage import run_triage  # type: ignore[no-redef]
    from session_store import get_ask_session  # type: ignore[no-redef]
    from simulator import simulate_birth_time  # type: ignore[no-redef]


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


class CorrectionRequest(BaseModel):
    year: int
    user_note: str = Field(..., min_length=1, max_length=500)


# ---------------------------------------------------------------------------
# Session state (in-memory)
# ---------------------------------------------------------------------------

class FortuneSession(BaseModel):
    """In-memory live-run cache. Durable state lives in Supabase via store.py."""

    fortune_id: str
    run_id: str | None = None
    surface_id: str
    request: CreateFortuneRequest
    status: RuntimeStatus = RuntimeStatus.initialized
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    latest_foundation: dict[str, Any] = Field(default_factory=dict)
    latest_narrative: dict[str, Any] | None = None
    latest_guardrail: dict[str, Any] | None = None
    corrections: dict[int, dict[str, str]] = Field(default_factory=dict)
    # Set by POST /action; consumed by the next GET /stream so the triage
    # agent runs instead of the default narrative agent. Cleared after stream.
    pending_action_id: str | None = None
    pending_action_question: str | None = None

    def touch(self, new_status: RuntimeStatus | None = None) -> None:
        if new_status is not None:
            self.status = new_status


class FortuneStore:
    """Ephemeral per-process cache of active streaming sessions.

    Durable state (fortune, fortune_run, fortune_snapshot) lives in Supabase.
    This cache exists only to hold foundation/narrative/guardrail mid-stream
    so the hot path doesn't round-trip to the DB for every event.

    Also owns a per-fortune ``asyncio.Lock`` so concurrent
    ``/action`` + ``/stream`` + ``/ask`` on the same fortune cannot clobber
    ``run_id`` / ``pending_action_id`` / session state mid-flight.
    """

    def __init__(self) -> None:
        self._items: dict[str, FortuneSession] = {}
        self._locks: dict[str, asyncio.Lock] = {}

    def put(self, session: FortuneSession) -> FortuneSession:
        self._items[session.fortune_id] = session
        return session

    def get(self, fortune_id: str) -> FortuneSession | None:
        return self._items.get(fortune_id)

    def get_lock(self, fortune_id: str) -> asyncio.Lock:
        """Return a stable lock for this fortune. Created lazily on first touch."""
        lock = self._locks.get(fortune_id)
        if lock is None:
            lock = asyncio.Lock()
            self._locks[fortune_id] = lock
        return lock


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
    return {
        "pillars": _to_jsonable(foundation.get("pillars")),
        "elements": _to_jsonable(foundation.get("elements")),
    }


def _snapshot_mechanics(session: "FortuneSession", analysis: Any) -> dict[str, Any]:
    """Serialize the FullBaziAnalysis fields we need to rebuild a foundation.

    This is the read source for /ask hydration: the Ask tab works even after
    the process restarts because we can re-construct the pydantic analysis
    from these JSON fields via ``FullBaziAnalysis.model_validate``.
    """
    if analysis is None:
        return {}
    return {
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


def _normalize_focus(action_id: str) -> str | None:
    return {
        "year_forecast": "year",
        "career_focus": "career",
        "relationship_focus": "relationship",
        "deep_dive_element": "element_balance",
        "show_sources": "sources",
        "expand_classics": "classics",
    }.get(action_id)


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

    # Hot-path cache for active streaming.
    store = get_fortune_store()
    session = FortuneSession(
        fortune_id=fortune_id_str,
        run_id=run_id_str,
        surface_id=settings.default_surface_id,
        request=normalized,
    )
    store.put(session)

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


def _extract_stream_event_meta(event: Any) -> dict[str, Any] | None:
    """Translate an SDK stream event into a minimal dict for the UI.

    The Agents SDK's streamed run yields three classes of events:
      * ``RawResponsesStreamEvent`` — token-level text deltas (too noisy for
        JSON output agents; the partial JSON mid-stream is not useful to
        render, so we skip these).
      * ``RunItemStreamEvent`` — higher-level tool calls, tool outputs,
        message outputs. These are the semantic breadcrumbs worth surfacing.
      * ``AgentUpdatedStreamEvent`` — fires on each handoff / specialist switch.

    Returns a small dict describing the event in portable terms, or ``None``
    if the event should be skipped. Kept defensive against minor SDK shape
    drift: attribute lookups use ``getattr`` with fallbacks.
    """
    cls_name = type(event).__name__
    if cls_name == "AgentUpdatedStreamEvent":
        new_agent = getattr(event, "new_agent", None)
        return {
            "kind": "handoff",
            "agent": getattr(new_agent, "name", None) or "unknown",
        }
    if cls_name == "RunItemStreamEvent":
        item = getattr(event, "item", None)
        if item is None:
            return None
        raw_item = getattr(item, "raw_item", None)
        tool_name = (
            getattr(raw_item, "name", None)
            or getattr(raw_item, "tool_name", None)
            or (raw_item.get("name") if isinstance(raw_item, dict) else None)
            or (raw_item.get("tool_name") if isinstance(raw_item, dict) else None)
        )
        # Canonicalize the item kind: snake_case (``tool_call_item``) and
        # PascalCase (``ToolCallItem``) both collapse to the same token once
        # underscores are stripped and the string is lowered. Try both the
        # ``type`` field (SDK-provided, usually snake) and the class name
        # (always present) so shape drift between SDK minor versions doesn't
        # silently swallow events.
        type_field = getattr(item, "type", None) or ""
        class_token = type(item).__name__ or ""
        tokens = {
            s.replace("_", "").lower() for s in (type_field, class_token) if s
        }
        if not tokens:
            return None
        if "toolcalloutputitem" in tokens or "tooloutputitem" in tokens:
            return {"kind": "tool_output", "tool": tool_name or "tool"}
        if "toolcallitem" in tokens:
            return {"kind": "tool_call", "tool": tool_name or "tool"}
        if "handoffcallitem" in tokens or "handoffoutputitem" in tokens:
            target = (
                getattr(raw_item, "target", None)
                or getattr(raw_item, "handoff_target", None)
            )
            return {"kind": "handoff_call", "target": target}
        if "messageoutputitem" in tokens:
            return {"kind": "message", "tool": None}
        return None
    return None


@router.get("/{fortune_id}/stream")
async def stream_fortune(fortune_id: str, request: Request):
    await smart_rate_limit(request, scope=RateLimitScope.FORTUNE_STREAM, weight=1)

    store = get_fortune_store()
    session = store.get(fortune_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Fortune session not found")

    # Per-fortune lock prevents two browser tabs or a mid-stream reconnect from
    # racing on the same FortuneSession. We probe-acquire before even entering
    # the generator so the 409 comes back as a clean HTTP response, not a
    # mid-stream error envelope.
    lock = store.get_lock(fortune_id)
    if lock.locked():
        raise HTTPException(
            status_code=409,
            detail="A stream is already in progress for this fortune.",
            headers={"Retry-After": "5"},
        )

    async def event_generator():
        import time as _time
        import json as _json

        # Hold the lock for the full life of the generator. FastAPI's
        # StreamingResponse drives this generator in the same task as the
        # inbound request, so the lock is released even on client disconnect
        # (the finally block runs on GeneratorExit).
        async with lock:
            bridge = FortuneStreamBridge(surface_id=session.surface_id)
            ctx = FortuneRunContext(
                fortune_id=session.fortune_id,
                surface_id=session.surface_id,
                run_id=session.run_id,
                question=session.request.question,
                focus=session.request.focus,
                tone=session.request.tone,
                birth_iso=session.request.birth_iso,
                timezone=session.request.timezone or "UTC",
                birth_time_unknown=session.request.birth_time_unknown,
                gender=session.request.gender or "unknown",
            )

            # Per-stream envelope. Seq numbers come from the DB via
            # ``allocate_seq`` when persistence is available so they line up
            # with any durable event rows; we fall back to a local counter if
            # the DB is degraded.
            run_id = session.run_id
            fortune_id_str = session.fortune_id
            local_seq = {"n": 0}
            repo = await get_repository()
            run_uuid: uuid.UUID | None = None
            try:
                run_uuid = uuid.UUID(run_id) if run_id else None
            except (ValueError, TypeError):
                run_uuid = None

            async def _alloc_seq() -> int:
                if run_uuid is not None and repo.available:
                    try:
                        n = await repo.allocate_seq(run_uuid)
                        if n > 0:
                            return n
                    except Exception as exc:
                        logger.debug("[FORTUNE] allocate_seq fallback: %s", exc)
                local_seq["n"] += 1
                return local_seq["n"]

            # Key events we mirror into fortune_event for durable replay. Most
            # high-frequency data updates stay Redis-only; we keep only the
            # semantic milestones the client needs to render a coherent partial
            # state after reconnect.
            DURABLE_EVENTS = {
                "progress", "narrative_complete", "guardrail",
                "trace_summary", "complete", "error",
            }

            async def _emit(payload: str, *, event_name: str | None = None) -> str:
                seq = await _alloc_seq()
                try:
                    inner = _json.loads(payload)
                except (ValueError, TypeError):
                    inner = {"raw": payload}
                env = {
                    "run_id": run_id,
                    "fortune_id": fortune_id_str,
                    "seq": seq,
                    "payload": inner,
                }
                if event_name and event_name in DURABLE_EVENTS and run_uuid is not None and repo.available:
                    try:
                        await repo.append_event(
                            run_id=run_uuid,
                            fortune_id=uuid.UUID(fortune_id_str),
                            seq=seq,
                            event_name=event_name,
                            payload=inner,
                        )
                    except Exception as exc:
                        logger.debug(
                            "[FORTUNE] append_event(%s) skipped: %s", event_name, exc,
                        )
                return f"data: {_json.dumps(env)}\n\n"

            # Track whether we've actually started streaming. ``pending_action_id``
            # is only cleared after the run transitions to 'streaming' AND we've
            # emitted the first event — SHOULD-FIX #12 from the audit.
            pending_cleared = False
            pending_action = session.pending_action_id
            pending_question = session.pending_action_question

            async def _maybe_clear_pending() -> None:
                nonlocal pending_cleared
                if pending_cleared:
                    return
                pending_cleared = True
                session.pending_action_id = None
                session.pending_action_question = None

            if run_uuid is not None:
                try:
                    await repo.update_run_status(run_uuid, "streaming")
                except Exception as exc:
                    logger.warning("[FORTUNE] run status update failed: %s", exc)

            try:
                session.touch(RuntimeStatus.streaming)
                _t_start = _time.monotonic()
                logger.info("[FORTUNE] %s stream start — run=%s focus=%s birth=%s",
                            session.fortune_id, run_id, ctx.focus, ctx.birth_iso)

                # 1. Begin rendering
                for msg in bridge.begin_messages(fortune_id=session.fortune_id):
                    yield await _emit(msg)

                # After the first event is on the wire the run is durably
                # committed as streaming; safe to drop the pending-action
                # sentinel so a reconnect does not re-dispatch it.
                await _maybe_clear_pending()

                # 2. Foundation — reuse cached if available.
                cached = session.latest_foundation
                if cached and cached.get("analysis"):
                    logger.info("[FORTUNE] %s reusing cached foundation", session.fortune_id)
                    foundation = cached
                    analysis = foundation["analysis"]
                    trace = foundation.get("trace")
                else:
                    yield await _emit(
                        bridge.emit_progress("foundation", "Computing Four Pillars..."),
                        event_name="progress",
                    )
                    _t_found = _time.monotonic()
                    foundation = await run_foundation(ctx)
                    analysis = foundation["analysis"]
                    dur_f = round((_time.monotonic() - _t_found) * 1000, 1)
                    logger.info("[FORTUNE] %s foundation complete — %0.fms", session.fortune_id, dur_f)
                    session.latest_foundation = foundation
                    trace = foundation.get("trace")

                yield await _emit(bridge.emit_pillars(foundation["pillars"]))
                elements_data = (
                    foundation["elements"].model_dump()
                    if hasattr(foundation["elements"], "model_dump")
                    else foundation["elements"]
                )
                yield await _emit(bridge.emit_elements(elements_data))
                refs_data = [
                    r.model_dump() if hasattr(r, "model_dump") else r
                    for r in foundation["references"]
                ]
                yield await _emit(bridge.emit_references(refs_data))

                yield await _emit(bridge.emit_hidden_stems(analysis.hidden_stems))
                yield await _emit(bridge.emit_ten_gods(analysis.ten_gods))
                yield await _emit(bridge.emit_interactions(analysis.interactions))
                yield await _emit(bridge.emit_seasonal_strength(analysis.seasonal_strength))
                yield await _emit(bridge.emit_element_by_source(analysis.element_by_source))

                # Compatibility: compute Person B foundation and emit both
                # persons under /data/compatibility/{personA,personB} so the
                # compat UI (PillarsTab, OverviewTab) can render two charts.
                is_compat = bool(ctx.focus and ctx.focus.startswith("compatibility"))
                person_b_info = session.request.person_b
                foundation_b: dict[str, Any] | None = None
                if is_compat:
                    yield await _emit(bridge.emit_compat_person(
                        "personA",
                        name=None,
                        pillars=foundation["pillars"],
                        elements=elements_data,
                        ten_gods=analysis.ten_gods,
                        hidden_stems=analysis.hidden_stems,
                    ))
                    if person_b_info is not None:
                        yield await _emit(
                            bridge.emit_progress("foundation", "Computing Person B's Four Pillars..."),
                            event_name="progress",
                        )
                        ctx_b = FortuneRunContext(
                            fortune_id=session.fortune_id,
                            surface_id=session.surface_id,
                            run_id=session.run_id,
                            focus=ctx.focus,
                            birth_iso=person_b_info.birth_iso,
                            timezone=person_b_info.timezone or ctx.timezone,
                            birth_time_unknown=person_b_info.birth_time_unknown,
                            gender=person_b_info.gender or "unknown",
                        )
                        foundation_b = await run_foundation(ctx_b)
                        analysis_b = foundation_b["analysis"]
                        elements_b = (
                            foundation_b["elements"].model_dump()
                            if hasattr(foundation_b["elements"], "model_dump")
                            else foundation_b["elements"]
                        )
                        yield await _emit(bridge.emit_compat_person(
                            "personB",
                            name=person_b_info.name,
                            pillars=foundation_b["pillars"],
                            elements=elements_b,
                            ten_gods=analysis_b.ten_gods,
                            hidden_stems=analysis_b.hidden_stems,
                        ))
                        # Cache on session so _build_narrative_prompt can see it.
                        session.latest_foundation = {
                            **foundation,
                            "person_b": foundation_b,
                        }
                if analysis.luck_pillars:
                    yield await _emit(bridge.emit_luck_pillars(analysis.luck_pillars))
                if analysis.annual_pillars:
                    yield await _emit(bridge.emit_annual_pillars(analysis.annual_pillars))
                yield await _emit(bridge.emit_kpi(analysis))

                retrodictions = foundation.get("retrodictions", [])
                if retrodictions:
                    yield await _emit(bridge.emit_retrodictions(retrodictions))

                if trace:
                    yield await _emit(bridge.emit_trace_steps_batch(trace.steps))

                # Early partial snapshot BEFORE narrative generation starts.
                # Mid-run reconnects (page refresh, crashed tab) can now hit
                # GET /{fortune_id} and get a populated dashboard back — the
                # narrative section stays empty until the later partial write.
                # Without this write, replay returned 202 pending for the
                # entire narrative generation window.
                if run_uuid is not None:
                    try:
                        await repo.upsert_snapshot(
                            uuid.UUID(fortune_id_str),
                            status="partial",
                            mechanics=_snapshot_mechanics(session, analysis),
                            pillars=_snapshot_pillars(session, foundation),
                            references=_snapshot_references(foundation),
                            retrodictions=(
                                {"items": _to_jsonable(retrodictions)}
                                if retrodictions else None
                            ),
                        )
                    except Exception as exc:
                        logger.warning(
                            "[FORTUNE] foundation snapshot persistence failed: %s", exc,
                        )

                if not session.request.focus:
                    session.request = session.request.model_copy(update={"focus": "general"})
                    ctx = FortuneRunContext(
                        fortune_id=ctx.fortune_id,
                        surface_id=ctx.surface_id,
                        run_id=ctx.run_id,
                        question=ctx.question,
                        focus="general",
                        tone=ctx.tone,
                        birth_iso=ctx.birth_iso,
                        timezone=ctx.timezone,
                        birth_time_unknown=ctx.birth_time_unknown,
                        gender=ctx.gender,
                    )

                # 4. Narrative OR triage.
                if pending_action:
                    yield await _emit(
                        bridge.emit_progress(
                            "narrative", f"Routing follow-up via triage ({pending_action})...",
                        ),
                        event_name="progress",
                    )
                    if trace:
                        trace.add_instant(
                            "llm_start", "narrative", label="Triage + Specialist",
                            input_summary=f"action={pending_action}",
                        )
                        yield await _emit(bridge.emit_trace_steps_batch(trace.steps))
                    _t_narrative = _time.monotonic()
                    logger.info(
                        "[FORTUNE] %s triage start — action=%s",
                        session.fortune_id, pending_action,
                    )
                    narrative = await run_triage(
                        ctx,
                        foundation=foundation,
                        action_id=pending_action,
                        question=pending_question,
                    )
                else:
                    yield await _emit(
                        bridge.emit_progress("narrative", "Generating interpretation..."),
                        event_name="progress",
                    )
                    if trace:
                        trace.add_instant(
                            "llm_start", "narrative", label="Generating Narrative",
                            input_summary=f"focus={ctx.focus}",
                        )
                        yield await _emit(bridge.emit_trace_steps_batch(trace.steps))

                    _t_narrative = _time.monotonic()
                    logger.info("[FORTUNE] %s narrative start — model=%s", session.fortune_id, "gpt-5.4")

                    # BLOCKING #2 fix: translate SDK stream events into SSE
                    # envelopes. We surface semantic milestones (tool call,
                    # handoff, message completion) rather than raw text deltas —
                    # the narrative agent emits structured JSON so mid-stream
                    # partial text is not useful to render.
                    stream_result = await run_narrative_streamed(ctx, foundation=foundation)
                    seen_tools: set[str] = set()
                    async for event in stream_result.stream_events():
                        meta = _extract_stream_event_meta(event)
                        if meta is None:
                            continue
                        kind = meta.get("kind")
                        if kind == "handoff":
                            msg = f"Agent → {meta.get('agent')}"
                            yield await _emit(bridge.emit_progress("narrative", msg))
                            if trace:
                                trace.add_instant(
                                    "handoff", "narrative",
                                    label=msg,
                                    input_summary=meta.get("agent") or "",
                                )
                                yield await _emit(bridge.emit_trace_steps_batch(trace.steps))
                        elif kind == "tool_call":
                            tool = meta.get("tool") or "tool"
                            if tool in seen_tools:
                                continue
                            seen_tools.add(tool)
                            yield await _emit(
                                bridge.emit_progress("narrative", f"Calling tool: {tool}"),
                            )
                            if trace:
                                trace.add_instant(
                                    "tool_call", "narrative",
                                    tool_name=tool, label=f"Calling {tool}",
                                )
                                yield await _emit(bridge.emit_trace_steps_batch(trace.steps))
                        elif kind == "tool_output":
                            tool = meta.get("tool") or "tool"
                            yield await _emit(
                                bridge.emit_progress("narrative", f"Tool returned: {tool}"),
                            )
                            if trace:
                                trace.add_instant(
                                    "tool_result", "narrative",
                                    tool_name=tool, label=f"{tool} complete",
                                )
                                yield await _emit(bridge.emit_trace_steps_batch(trace.steps))
                        elif kind == "message":
                            yield await _emit(
                                bridge.emit_progress("narrative", "Model response received"),
                            )

                    narrative = stream_result.final_output
                    if not isinstance(narrative, (NarrativeOutput, EnrichedNarrativeOutput)):
                        narrative = EnrichedNarrativeOutput.model_validate(narrative)

                session.latest_narrative = narrative.model_dump()

                dur_n = round((_time.monotonic() - _t_narrative) * 1000, 1)
                n_insights = len(narrative.insights) if hasattr(narrative, "insights") else 0
                logger.info("[FORTUNE] %s narrative complete — %d insights, %.0fms",
                            session.fortune_id, n_insights, dur_n)

                if trace:
                    trace.add_instant(
                        "llm_complete", "narrative", label="Narrative Complete",
                        output_summary=f"{n_insights} insights, {dur_n:.0f}ms",
                    )
                    trace.steps[-1].duration_ms = dur_n

                yield await _emit(
                    bridge.emit_narrative_complete(session.latest_narrative),
                    event_name="narrative_complete",
                )

                if run_uuid is not None:
                    try:
                        await repo.upsert_snapshot(
                            uuid.UUID(fortune_id_str),
                            status="partial",
                            narrative=session.latest_narrative,
                            mechanics=_snapshot_mechanics(session, analysis),
                            pillars=_snapshot_pillars(session, foundation),
                            references=_snapshot_references(foundation),
                            retrodictions={"items": _to_jsonable(retrodictions)} if retrodictions else None,
                        )
                    except Exception as exc:
                        logger.warning("[FORTUNE] partial snapshot persistence failed: %s", exc)

                # 6. Guardrail
                yield await _emit(
                    bridge.emit_progress("guardrail", "Running safety check..."),
                    event_name="progress",
                )
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

                dur_g = round((_time.monotonic() - _t_guard) * 1000, 1)
                logger.info("[FORTUNE] %s guardrail complete — level=%s, %.0fms",
                            session.fortune_id, guardrail.level, dur_g)

                if trace:
                    trace.add_instant(
                        "llm_complete", "guardrail", label="Safety Check Complete",
                        output_summary=f"level={guardrail.level}, {dur_g:.0f}ms",
                    )
                    trace.steps[-1].duration_ms = dur_g

                yield await _emit(
                    bridge.emit_guardrail(session.latest_guardrail),
                    event_name="guardrail",
                )

                if trace:
                    yield await _emit(bridge.emit_trace_steps_batch(trace.steps))
                    yield await _emit(
                        bridge.emit_trace_summary(trace.summary()),
                        event_name="trace_summary",
                    )

                # 7. Complete — persist snapshot + update run status.
                total_ms = round((_time.monotonic() - _t_start) * 1000, 1)
                logger.info("[FORTUNE] %s stream complete — total %.0fms", session.fortune_id, total_ms)
                session.touch(RuntimeStatus.complete)

                if run_uuid is not None:
                    try:
                        await repo.upsert_snapshot(
                            uuid.UUID(fortune_id_str),
                            status="done",
                            narrative=session.latest_narrative,
                            mechanics=_snapshot_mechanics(session, analysis),
                            pillars=_snapshot_pillars(session, foundation),
                            references=_snapshot_references(foundation),
                            retrodictions={"items": _to_jsonable(retrodictions)} if retrodictions else None,
                        )
                        await repo.update_run_status(run_uuid, "done")
                    except Exception as exc:
                        logger.warning("[FORTUNE] snapshot/status persistence failed: %s", exc)

                for msg in bridge.emit_complete():
                    yield await _emit(msg, event_name="complete")

            except Exception as exc:
                logger.exception("[FORTUNE] %s stream error: %s", session.fortune_id, exc)
                session.touch(RuntimeStatus.error)
                if run_uuid is not None:
                    try:
                        await repo.update_run_status(
                            run_uuid, "error", error_message=str(exc)[:500],
                        )
                    except Exception as update_exc:
                        logger.warning("[FORTUNE] error-status update failed: %s", update_exc)
                # Pending-action was not cleared if we failed pre-first-event;
                # clear it now to avoid a poisoned re-dispatch on retry.
                await _maybe_clear_pending()
                for msg in bridge.emit_error(str(exc)):
                    yield await _emit(msg, event_name="error")

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
    await smart_rate_limit(request, scope=RateLimitScope.FORTUNE_ACTION, weight=1)

    if request_body.action_id not in ALLOWED_ACTIONS:
        raise HTTPException(status_code=400, detail="Unsupported action_id")

    store = get_fortune_store()
    session = store.get(fortune_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Fortune session not found")

    # Refuse to rotate run_id under an active stream — otherwise the in-flight
    # generator consumes `pending_action_id` set by the NEXT click and
    # dispatches it as if it belonged to the current run.
    lock = store.get_lock(fortune_id)
    if lock.locked():
        raise HTTPException(
            status_code=409,
            detail="A stream is active; wait for it to finish before choosing a new action.",
            headers={"Retry-After": "3"},
        )

    # Update focus based on action
    normalized_focus = _normalize_focus(request_body.action_id)
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

    store = get_fortune_store()
    fortune_session = store.get(fortune_id)
    repo = await get_repository()

    # Preferred path: hot in-memory session with live foundation.
    foundation: dict[str, Any] | None = None
    if fortune_session is not None and fortune_session.latest_foundation:
        foundation = fortune_session.latest_foundation
    else:
        # Fall back to the durable snapshot so /ask survives restarts and any
        # cross-worker route. This turns a previously confusing 409 into a
        # working answer whenever the snapshot is intact — SHOULD-FIX #5.
        hydrated = await _hydrate_foundation_from_snapshot(repo, fortune_id)
        if hydrated is not None:
            foundation = hydrated
            if fortune_session is not None:
                fortune_session.latest_foundation = hydrated

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

    try:
        narrative = await run_triage(
            ctx,
            foundation=foundation,
            question=request_body.question,
            session=ask_session,
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

    return AskResponse(
        fortune_id=fortune_id,
        run_id=new_run_id,
        narrative=narrative.model_dump(),
        degraded_memory=degraded_memory,
    )


@router.post("/{fortune_id}/simulate")
async def simulate_fortune(fortune_id: str, request: Request):
    """Birth-Time Uncertainty Simulator — enumerate all 12 Earthly Branch
    hour hypotheses and return a stability report plus per-branch chart data.

    Deterministic (no LLM) but ~12× the compute of a single foundation run,
    so it gets its own rate-limit bucket at weight 4 — lower than /create's
    full-pipeline cost but higher than /action's single-LLM triage.
    """
    await smart_rate_limit(request, scope=RateLimitScope.FORTUNE_SIMULATE, weight=4)

    store = get_fortune_store()
    session = store.get(fortune_id)
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
    In-memory ``session.corrections`` stays in sync for the live dashboard.
    """
    await smart_rate_limit(request, scope=RateLimitScope.FORTUNE_CORRECTION, weight=1)

    try:
        fid = uuid.UUID(fortune_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid fortune_id")

    repo = await get_repository()
    store = get_fortune_store()
    session = store.get(fortune_id)

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

    if session is not None:
        session.corrections[request_body.year] = record

    return {
        "fortune_id": fortune_id,
        "year": request_body.year,
        "correction": record,
    }
