"""GlassBoxTraceProcessor — durable projection of OpenAI Agents SDK spans.

Registered once at app startup via ``agents.tracing.add_trace_processor``.
Every agent run (``Runner.run``, ``Runner.run_streamed``) emits spans for
agent starts/ends, LLM calls, tool calls, and handoffs. This processor:

1. Extracts portable metadata from each span.
2. Writes a row into ``fortune_trace`` keyed by ``run_id`` (which the caller
   sets as ``trace_id`` on ``RunConfig``) and ``span_id``.
3. Fire-and-forget — DB failures are logged but never block the agent loop.

The SSE "live" Glass Box continues to be driven by the existing
``trace_steps_batch`` emissions in ``routes.py`` for v1; this processor adds
durable capture so the replay endpoint's ``latest_trace`` snapshot can be
reconstructed from DB, and so the activity rail can query a complete trace
after the run completes.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)


def _iso(dt: Any) -> datetime | None:
    if dt is None:
        return None
    if isinstance(dt, datetime):
        return dt
    if isinstance(dt, (int, float)):
        return datetime.fromtimestamp(dt, tz=timezone.utc)
    if isinstance(dt, str):
        try:
            return datetime.fromisoformat(dt.replace("Z", "+00:00"))
        except ValueError:
            return None
    return None


def _safe_get(obj: Any, *names: str) -> Any:
    """Return the first attribute/item among ``names`` that exists on ``obj``."""
    for name in names:
        if obj is None:
            return None
        if isinstance(obj, dict) and name in obj:
            return obj[name]
        if hasattr(obj, name):
            val = getattr(obj, name)
            if val is not None:
                return val
    return None


def _extract_span_fields(span: Any) -> dict[str, Any]:
    """Best-effort extraction of span metadata across SDK versions.

    The Agents SDK exposes ``Span`` with a ``span_data`` payload whose shape
    varies by span type (AgentSpanData, FunctionSpanData, GenerationSpanData,
    HandoffSpanData, etc.). We pull the subset we care about and stash the
    raw payload as JSONB for later inspection.
    """
    span_data = _safe_get(span, "span_data", "data")
    span_type_cls = type(span_data).__name__ if span_data is not None else "unknown"

    # Normalize span_type to stable strings.
    span_type = span_type_cls.lower().replace("spandata", "") or "unknown"
    if not span_type:
        span_type = "unknown"

    agent_name = _safe_get(span_data, "agent_name", "name")
    tool_name = _safe_get(span_data, "tool_name", "function_name", "handoff_target")
    model = _safe_get(span_data, "model", "model_name")
    error = _safe_get(span, "error")
    error_str = None
    if error is not None:
        error_str = _safe_get(error, "message") or str(error)

    started_at = _iso(_safe_get(span, "started_at", "start_time", "timestamp"))
    ended_at = _iso(_safe_get(span, "ended_at", "end_time"))

    return {
        "trace_id": _safe_get(span, "trace_id"),
        "span_id": _safe_get(span, "span_id", "id"),
        "parent_span_id": _safe_get(span, "parent_id", "parent_span_id"),
        "span_type": span_type,
        "agent_name": agent_name,
        "tool_name": tool_name,
        "model": model,
        "started_at": started_at,
        "ended_at": ended_at,
        "error": error_str,
    }


def _span_duration_ms(fields: dict[str, Any]) -> int | None:
    s, e = fields.get("started_at"), fields.get("ended_at")
    if s is None or e is None:
        return None
    return max(0, int((e - s).total_seconds() * 1000))


class GlassBoxTraceProcessor:
    """Minimal TracingProcessor that projects SDK spans into ``fortune_trace``.

    Not a subclass because the SDK's abstract base class import path has
    shifted across versions (``agents.tracing.TracingProcessor``). Duck-typing
    against the expected method names keeps us compatible across minor
    versions in the 0.13–0.14 range.
    """

    def __init__(self, run_id_resolver=None) -> None:
        """``run_id_resolver`` (optional) maps ``trace_id`` → database run_id.

        We set ``trace_id=str(run_id)`` on ``RunConfig`` at the route layer,
        so the default resolver just parses it as a UUID. An override is only
        needed if we later route multiple concurrent traces through one run.
        """
        self._resolver = run_id_resolver or self._default_resolver
        # Track outstanding fire-and-forget writes so ``aflush`` can drain them
        # on shutdown. Plain set + discard callback avoids GC races on the
        # tasks (asyncio holds only weak references to bare create_task tasks).
        self._pending: set[asyncio.Task] = set()

    @staticmethod
    def _default_resolver(trace_id: str | None) -> str | None:
        """Parse ``trace_{hex32}`` back to a UUID string the ``fortune_run`` row can match.

        Agents SDK requires ``trace_id`` to start with ``trace_``, so we set
        it as ``trace_{uuid_without_dashes}`` at the route layer and invert
        that here. Falls through any other format as-is for forward-compat.
        """
        if not trace_id:
            return None
        raw = trace_id
        if raw.startswith("trace_"):
            raw = raw[len("trace_"):]
        # uuid.UUID accepts both hex-only and hyphenated forms.
        try:
            import uuid as _uuid
            return str(_uuid.UUID(raw))
        except (ValueError, TypeError):
            return trace_id

    # ------------------------------------------------------------------
    # TracingProcessor protocol
    # ------------------------------------------------------------------

    def on_trace_start(self, trace: Any) -> None:  # pragma: no cover - noop
        pass

    def on_trace_end(self, trace: Any) -> None:  # pragma: no cover - noop
        pass

    def _schedule(self, coro) -> None:
        """Fire-and-forget a write while keeping a strong reference so aflush
        can drain it. Swallows the 'no running loop' case (shutdown path)."""
        try:
            task = asyncio.get_running_loop().create_task(coro)
        except RuntimeError:
            coro.close()
            return
        self._pending.add(task)
        task.add_done_callback(self._pending.discard)

    def on_span_start(self, span: Any) -> None:
        """Write an initial row so partial traces survive a crash before span_end."""
        fields = _extract_span_fields(span)
        run_id = self._resolver(fields.get("trace_id"))
        if not run_id or not fields.get("span_id"):
            return
        self._schedule(self._write_span(run_id, fields, is_start=True))

    def on_span_end(self, span: Any) -> None:
        fields = _extract_span_fields(span)
        run_id = self._resolver(fields.get("trace_id"))
        if not run_id or not fields.get("span_id"):
            return
        self._schedule(self._write_span(run_id, fields, is_start=False))

    def shutdown(self) -> None:  # pragma: no cover - sync-side noop
        # SDK protocol requires a sync method. Real draining happens in
        # ``aflush`` which the FastAPI shutdown hook awaits directly.
        pass

    def force_flush(self) -> None:  # pragma: no cover - sync-side noop
        pass

    async def aflush(self, timeout: float = 3.0) -> None:
        """Await outstanding span writes up to ``timeout`` seconds.

        Called from the FastAPI shutdown hook so the tail of a trace makes it
        to Postgres before the worker exits. Timeout bounds the worst case so
        shutdown can't hang on a slow/unreachable database.
        """
        if not self._pending:
            return
        pending = list(self._pending)
        try:
            await asyncio.wait_for(
                asyncio.gather(*pending, return_exceptions=True),
                timeout=timeout,
            )
        except asyncio.TimeoutError:
            logger.warning(
                "[FORTUNE] trace flush timed out after %.1fs with %d writes pending",
                timeout, len(self._pending),
            )

    # ------------------------------------------------------------------
    # Durable write
    # ------------------------------------------------------------------

    async def _write_span(
        self, run_id: str, fields: dict[str, Any], is_start: bool
    ) -> None:
        try:
            from .store import get_repository
        except ImportError:
            from store import get_repository  # type: ignore[no-redef]
        try:
            repo = await get_repository()
            if not repo.available:
                return
            import uuid as _uuid
            try:
                run_uuid = _uuid.UUID(run_id)
            except (ValueError, TypeError):
                return
            duration_ms = _span_duration_ms(fields)
            # Upsert by (run_id, span_id). on_span_start inserts; on_span_end
            # updates ended_at + duration. Using ON CONFLICT for idempotency
            # in case both fire in unusual orders (e.g., retries).
            import json as _json
            await repo.pool.execute(
                """
                INSERT INTO fortune_trace (
                    run_id, span_id, parent_span_id, span_type,
                    agent_name, tool_name, model,
                    started_at, ended_at, duration_ms, error
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
                ON CONFLICT (run_id, span_id) DO UPDATE SET
                    ended_at    = COALESCE(EXCLUDED.ended_at, fortune_trace.ended_at),
                    duration_ms = COALESCE(EXCLUDED.duration_ms, fortune_trace.duration_ms),
                    error       = COALESCE(EXCLUDED.error, fortune_trace.error),
                    agent_name  = COALESCE(fortune_trace.agent_name, EXCLUDED.agent_name),
                    tool_name   = COALESCE(fortune_trace.tool_name, EXCLUDED.tool_name),
                    model       = COALESCE(fortune_trace.model, EXCLUDED.model)
                """,
                run_uuid,
                str(fields["span_id"]),
                fields.get("parent_span_id") and str(fields["parent_span_id"]),
                fields.get("span_type") or "unknown",
                fields.get("agent_name"),
                fields.get("tool_name"),
                fields.get("model"),
                fields.get("started_at"),
                fields.get("ended_at"),
                duration_ms,
                fields.get("error"),
            )
        except Exception as exc:  # pragma: no cover - best-effort persistence
            logger.warning(
                "[FORTUNE] trace span persist failed (run_id=%s span=%s): %s",
                run_id, fields.get("span_id"), exc,
            )


_registered = False
_processor: GlassBoxTraceProcessor | None = None


def ensure_registered() -> None:
    """Register the processor with the SDK (idempotent, called from startup)."""
    global _registered, _processor
    if _registered:
        return
    try:
        from agents import add_trace_processor
    except ImportError:  # pragma: no cover - SDK not installed in dev shell
        logger.warning("[FORTUNE] agents SDK not importable; trace processor disabled")
        return
    try:
        _processor = GlassBoxTraceProcessor()
        add_trace_processor(_processor)
        _registered = True
        logger.info("[FORTUNE] GlassBoxTraceProcessor registered")
    except Exception as exc:
        logger.error("[FORTUNE] trace processor registration failed: %s", exc)


async def flush_pending_spans(timeout: float = 3.0) -> None:
    """Module-level entry point for shutdown hooks — awaits span writes."""
    if _processor is None:
        return
    await _processor.aflush(timeout=timeout)
