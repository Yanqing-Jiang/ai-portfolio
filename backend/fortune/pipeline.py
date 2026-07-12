"""Fortune run pipeline — frame producer shared by v1 SSE and v2 Redis Streams.

Extracted from ``routes.py`` Phase 1. Emits the same A2UI envelope JSON the
SSE layer has always sent. v1 yields frames directly; v2 publishes to
``events.py`` and lets ``/stream`` tail the Redis stream.
"""

from __future__ import annotations

import asyncio
import json as _json
import logging
import time as _time
import uuid
from typing import Any, AsyncIterator, Callable, Awaitable

logger = logging.getLogger(__name__)

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
        _narrative_mode,
        _promote_narrative_to_enriched,
        repair_occasion_narrative,
        run_foundation,
        run_guardrail,
        run_narrative_streamed,
    )
    from .config import get_settings
    from .stream_bridge import FortuneStreamBridge
    from .store import get_repository
    from .triage import run_triage
    from .naming import canonical_function
    from ._thinking_heartbeat import HeartbeatTick, iter_with_heartbeats
    from .state import FortuneSession, RuntimeStatus, get_run_state
    from . import events as fortune_events
except ImportError:  # pragma: no cover
    from agents import (  # type: ignore[no-redef]
        DEFAULT_FOLLOW_UP_BUTTONS,
        EnrichedNarrativeOutput,
        FOUNDATION_VERSION,
        FortuneRunContext,
        GUARDRAIL_AGENT,
        GuardrailOutput,
        NARRATIVE_AGENTS,
        NARRATIVE_SCHEMA_VERSION,
        _narrative_mode,
        _promote_narrative_to_enriched,
        repair_occasion_narrative,
        run_foundation,
        run_guardrail,
        run_narrative_streamed,
    )
    from config import get_settings  # type: ignore[no-redef]
    from stream_bridge import FortuneStreamBridge  # type: ignore[no-redef]
    from store import get_repository  # type: ignore[no-redef]
    from triage import run_triage  # type: ignore[no-redef]
    from naming import canonical_function  # type: ignore[no-redef]
    from _thinking_heartbeat import HeartbeatTick, iter_with_heartbeats  # type: ignore[no-redef]
    from state import FortuneSession, RuntimeStatus, get_run_state  # type: ignore[no-redef]
    import events as fortune_events  # type: ignore[no-redef]


def _to_jsonable(obj: Any) -> Any:
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


def _snapshot_pillars(session: FortuneSession, foundation: dict[str, Any]) -> dict[str, Any]:
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


def _snapshot_mechanics(session: FortuneSession, analysis: Any) -> dict[str, Any]:
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


def _build_ask_original_input(req: Any) -> dict[str, Any] | None:
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
    if getattr(req, "person_b", None) is not None:
        out["person_b"] = req.person_b.model_dump()
    return out


def _local_seq_allocator() -> Any:
    """Monotonic per-run seq for envelope compatibility with the frontend dedupe.

    Replaces the Postgres ``allocate_seq`` / ``allocate_seq_batch`` machinery.
    ``fortune_run.last_emitted_seq`` is no longer written from the hot path;
    resume cursors are Redis stream IDs (v2) or full replay (v1 reconnect).
    """
    counter = {"n": 0}

    async def alloc() -> int:
        counter["n"] += 1
        return counter["n"]

    return alloc




async def iter_fortune_sse_frames(session, *, request=None, store=None):
    """Yield SSE ``data:`` frames identical to the pre-Phase-1 generator."""
    if store is None:
        store = get_run_state()
    try:
        from ._pipeline_run import _event_generator_impl
    except ImportError:  # pragma: no cover
        from _pipeline_run import _event_generator_impl  # type: ignore[no-redef]
    async for frame in _event_generator_impl(session, request=request, store=store):
        yield frame


async def run_and_publish(session, *, store=None, lock_token: str | None = None) -> None:
    """v2 background runner: publish each frame envelope to Redis Streams."""
    if store is None:
        store = get_run_state()
    run_id = session.run_id or ""
    fortune_id = session.fortune_id
    owns_lock = lock_token is not None
    if lock_token is None:
        lock_token = await store.acquire_lock(fortune_id)
        owns_lock = lock_token is not None
    if lock_token is None:
        await fortune_events.set_run_record(
            run_id,
            fortune_id=fortune_id,
            status="failed",
            error_message="fortune_busy",
        )
        return
    try:
        await fortune_events.set_run_record(run_id, fortune_id=fortune_id, status="streaming")
        async for sse_chunk in iter_fortune_sse_frames(session, request=None, store=store):
            for line in sse_chunk.splitlines():
                if not line.startswith("data: "):
                    continue
                raw = line[6:]
                try:
                    envelope = _json.loads(raw)
                except (TypeError, ValueError):
                    envelope = {"raw": raw}
                entry_id = await fortune_events.publish_envelope(run_id, envelope)
                if entry_id is None:
                    logger.error("[FORTUNE-PIPELINE] publish failed run=%s", run_id)
                    await fortune_events.set_run_record(
                        run_id, fortune_id=fortune_id, status="failed",
                        error_message="redis_publish_failed",
                    )
                    return
        status_map = {
            RuntimeStatus.complete: "complete",
            RuntimeStatus.error: "error",
            RuntimeStatus.interrupted: "interrupted",
        }
        final = status_map.get(session.status, session.status.value)
        await fortune_events.set_run_record(run_id, fortune_id=fortune_id, status=final)
    except Exception as exc:
        logger.exception("[FORTUNE-PIPELINE] run_and_publish failed: %s", exc)
        await fortune_events.set_run_record(
            run_id, fortune_id=fortune_id, status="failed", error_message=str(exc)[:500],
        )
        raise
    finally:
        if owns_lock:
            await store.release_lock(fortune_id, lock_token)


async def run_and_publish_safe(session, *, store=None, lock_token: str | None = None) -> None:
    try:
        await run_and_publish(session, store=store, lock_token=lock_token)
    except Exception:
        pass
