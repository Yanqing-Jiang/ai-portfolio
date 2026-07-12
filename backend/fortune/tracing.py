"""Unified redacted Glass Box tracing for SDK and deterministic spans.

Every event is reduced to an allowlisted display projection before it is
scheduled for Redis or Postgres.  The per-run ``RunTrace`` view also preserves
the legacy A2UI trace-step/summary contract while the v2 stream receives
first-class ``payload.kind == \"trace\"`` envelopes.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import time
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Generator

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

_ISO_DATE_RE = re.compile(r"\b\d{4}-\d{2}-\d{2}(?:[T ][0-9:.+\-Z]+)?\b")
_MAX_SUMMARY = 240


class TraceStep(BaseModel):
    """Legacy display shape, now produced by the unified processor."""

    step_id: str
    step_type: str
    agent_name: str
    tool_name: str | None = None
    label: str = ""
    input_summary: str = ""
    output_summary: str = ""
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    duration_ms: float = 0.0
    status: str = "pending"


def _iso(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, tz=timezone.utc)
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    return None


def _safe_get(obj: Any, *names: str) -> Any:
    for name in names:
        if isinstance(obj, dict) and name in obj:
            return obj[name]
        if obj is not None and hasattr(obj, name):
            value = getattr(obj, name)
            if value is not None:
                return value
    return None


def _bounded_text(value: Any) -> str:
    if value is None:
        return ""
    if not isinstance(value, str):
        try:
            value = json.dumps(value, ensure_ascii=False, default=str)
        except Exception:
            value = str(value)
    return " ".join(value.split())[:_MAX_SUMMARY]


class RunTrace:
    """Run-scoped facade for deterministic spans and legacy trace frames."""

    def __init__(self, processor: "GlassBoxTraceProcessor", run_id: str, fortune_id: str) -> None:
        self.processor = processor
        self.run_id = run_id
        self.fortune_id = fortune_id
        self.steps: list[TraceStep] = []
        self._started = time.monotonic()
        self._counter = 0

    def _span_id(self, agent_name: str, tool_name: str | None, step_type: str) -> str:
        self._counter += 1
        seed = f"{self.run_id}:{self._counter}:{agent_name}:{tool_name or step_type}"
        return f"ts_{uuid.uuid5(uuid.NAMESPACE_URL, seed).hex[:8]}"

    @contextmanager
    def step(
        self,
        step_type: str,
        agent_name: str,
        *,
        tool_name: str | None = None,
        label: str = "",
        input_summary: str = "",
    ) -> Generator[TraceStep, None, None]:
        span_id = self._span_id(agent_name, tool_name, step_type)
        item = TraceStep(
            step_id=span_id,
            step_type=step_type,
            agent_name=agent_name,
            tool_name=tool_name,
            label=self.processor.redact(self.run_id, label),
            input_summary=self.processor.redact(self.run_id, input_summary),
            status="running",
        )
        self.steps.append(item)
        started = datetime.now(timezone.utc)
        t0 = time.monotonic()
        try:
            yield item
            item.status = "success"
        except Exception as exc:
            item.status = "error"
            item.output_summary = self.processor.redact(self.run_id, str(exc))
            raise
        finally:
            item.duration_ms = round((time.monotonic() - t0) * 1000, 1)
            item.output_summary = self.processor.redact(self.run_id, item.output_summary)
            self.processor.enqueue_manual(
                run_id=self.run_id,
                span_id=span_id,
                phase="complete",
                agent_name=agent_name,
                tool_name=tool_name,
                started_at=started,
                ended_at=datetime.now(timezone.utc),
                status=item.status,
                arg_summary=item.input_summary,
                result_summary=item.output_summary,
            )

    def add_instant(
        self,
        step_type: str,
        agent_name: str,
        *,
        tool_name: str | None = None,
        label: str = "",
        input_summary: str = "",
        output_summary: str = "",
    ) -> TraceStep:
        span_id = self._span_id(agent_name, tool_name, step_type)
        item = TraceStep(
            step_id=span_id,
            step_type=step_type,
            agent_name=agent_name,
            tool_name=tool_name,
            label=self.processor.redact(self.run_id, label),
            input_summary=self.processor.redact(self.run_id, input_summary),
            output_summary=self.processor.redact(self.run_id, output_summary),
            duration_ms=0.0,
            status="success",
        )
        self.steps.append(item)
        now = datetime.now(timezone.utc)
        self.processor.enqueue_manual(
            run_id=self.run_id,
            span_id=span_id,
            phase="complete",
            agent_name=agent_name,
            tool_name=tool_name,
            started_at=now,
            ended_at=now,
            status="success",
            arg_summary=item.input_summary,
            result_summary=item.output_summary,
        )
        return item

    def summary(self) -> dict[str, Any]:
        return {
            "totalDurationMs": round((time.monotonic() - self._started) * 1000, 1),
            "toolCallCount": sum(s.step_type == "tool_call" for s in self.steps),
            "llmCallCount": sum(s.step_type == "llm_start" for s in self.steps),
            "stepCount": len(self.steps),
        }


class GlassBoxTraceProcessor:
    """Single SDK/manual trace pathway with pre-enqueue redaction."""

    def __init__(self, run_id_resolver=None) -> None:
        self._resolver = run_id_resolver or self._default_resolver
        self._pending: dict[asyncio.Task, str] = {}
        self._runs: dict[str, RunTrace] = {}
        self._sensitive: dict[str, tuple[str, ...]] = {}

    @staticmethod
    def _default_resolver(trace_id: str | None) -> str | None:
        if not trace_id:
            return None
        raw = trace_id.removeprefix("trace_")
        try:
            return str(uuid.UUID(raw))
        except (ValueError, TypeError):
            return trace_id

    def begin_run(
        self,
        run_id: str | None,
        fortune_id: str,
        *,
        sensitive_values: list[str | None] | None = None,
    ) -> RunTrace:
        resolved = run_id or fortune_id
        values = tuple(v for v in (sensitive_values or []) if isinstance(v, str) and v)
        if values:
            self._sensitive[resolved] = values
        trace = self._runs.get(resolved)
        if trace is None:
            trace = RunTrace(self, resolved, fortune_id)
            self._runs[resolved] = trace
        return trace

    def redact(self, run_id: str, value: Any) -> str:
        text = _bounded_text(value)
        for secret in sorted(self._sensitive.get(run_id, ()), key=len, reverse=True):
            text = text.replace(secret, "[redacted]")
            if "T" in secret:
                text = text.replace(secret.split("T", 1)[0], "[redacted]")
        return _ISO_DATE_RE.sub("[redacted]", text)[:_MAX_SUMMARY]

    def _schedule(self, run_id: str, projection: dict[str, Any]) -> None:
        # ``projection`` is already allowlisted and redacted here. Raw SDK
        # span objects never cross the task boundary.
        try:
            task = asyncio.get_running_loop().create_task(self._deliver(projection))
        except RuntimeError:
            return
        self._pending[task] = run_id
        task.add_done_callback(self._pending.pop)

    def _projection(
        self,
        *,
        run_id: str,
        span_id: str,
        phase: str,
        span_type: str,
        agent_name: str | None,
        tool_name: str | None,
        started_at: datetime | None,
        ended_at: datetime | None,
        status: str,
        arg_summary: Any = "",
        result_summary: Any = "",
        parent_span_id: str | None = None,
        model: str | None = None,
    ) -> dict[str, Any]:
        duration = None
        if started_at is not None and ended_at is not None:
            duration = max(0, int((ended_at - started_at).total_seconds() * 1000))
        return {
            "eventId": f"{run_id}:{span_id}:{phase}",
            "runId": run_id,
            "spanId": span_id,
            "phase": phase,
            "parentSpanId": parent_span_id,
            "spanType": span_type,
            "agentName": self.redact(run_id, agent_name),
            "toolName": self.redact(run_id, tool_name),
            "model": self.redact(run_id, model),
            "durationMs": duration,
            "status": status,
            "argSummary": self.redact(run_id, arg_summary),
            "resultSummary": self.redact(run_id, result_summary),
            "startedAt": started_at.isoformat() if started_at else None,
            "endedAt": ended_at.isoformat() if ended_at else None,
        }

    def enqueue_manual(self, **fields: Any) -> None:
        projection = self._projection(span_type="deterministic", **fields)
        self._schedule(projection["runId"], projection)

    def on_trace_start(self, trace: Any) -> None:
        return None

    def on_trace_end(self, trace: Any) -> None:
        return None

    def _sdk_projection(self, span: Any, phase: str) -> dict[str, Any] | None:
        data = _safe_get(span, "span_data", "data")
        run_id = self._resolver(_safe_get(span, "trace_id"))
        span_id = _safe_get(span, "span_id", "id")
        if not run_id or not span_id:
            return None
        kind = type(data).__name__.lower().replace("spandata", "") or "unknown"
        error = _safe_get(span, "error")
        triggered = bool(_safe_get(data, "triggered"))
        status = "running" if phase == "start" else "error" if error else "rejected" if triggered else "success"
        # Only function spans expose bounded arg/result summaries. Generation
        # inputs/outputs contain the full birth profile and question and are
        # intentionally never projected.
        is_function = kind == "function"
        return self._projection(
            run_id=run_id,
            span_id=str(span_id),
            phase=phase,
            span_type=kind,
            agent_name=_safe_get(data, "agent_name") or (_safe_get(data, "name") if kind == "agent" else None),
            tool_name=_safe_get(data, "name") if is_function else None,
            parent_span_id=_safe_get(span, "parent_id", "parent_span_id"),
            model=_safe_get(data, "model", "model_name"),
            started_at=_iso(_safe_get(span, "started_at", "start_time", "timestamp")),
            ended_at=_iso(_safe_get(span, "ended_at", "end_time")),
            status=status,
            arg_summary=_safe_get(data, "input") if is_function else "",
            result_summary=_safe_get(data, "output") if is_function else "",
        )

    def on_span_start(self, span: Any) -> None:
        projection = self._sdk_projection(span, "start")
        if projection:
            self._schedule(projection["runId"], projection)

    def on_span_end(self, span: Any) -> None:
        projection = self._sdk_projection(span, "end")
        if projection:
            self._schedule(projection["runId"], projection)

    async def _deliver(self, projection: dict[str, Any]) -> None:
        await asyncio.gather(
            self._publish_live(projection),
            self._write_projection(projection),
            return_exceptions=True,
        )

    async def _publish_live(self, projection: dict[str, Any]) -> None:
        try:
            from . import events
            await events.publish_envelope(
                projection["runId"],
                {
                    "run_id": projection["runId"],
                    "payload": {"kind": "trace", "trace": projection},
                },
            )
        except Exception as exc:
            logger.warning("[FORTUNE] live trace publish failed: %s", exc)

    async def _write_projection(self, projection: dict[str, Any]) -> None:
        try:
            run_uuid = uuid.UUID(projection["runId"])
        except (ValueError, TypeError):
            return
        try:
            from .store import get_repository
            repo = await get_repository()
            if not repo.available:
                return
            await repo.pool.execute(
                """
                INSERT INTO fortune_trace (
                    run_id, span_id, phase, parent_span_id, span_type,
                    agent_name, tool_name, model, input_json, output_json,
                    error, started_at, ended_at, duration_ms
                ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9::jsonb,$10::jsonb,$11,$12,$13,$14)
                ON CONFLICT (run_id, span_id, phase) DO UPDATE SET
                    ended_at = COALESCE(EXCLUDED.ended_at, fortune_trace.ended_at),
                    duration_ms = COALESCE(EXCLUDED.duration_ms, fortune_trace.duration_ms),
                    error = COALESCE(EXCLUDED.error, fortune_trace.error),
                    input_json = EXCLUDED.input_json,
                    output_json = EXCLUDED.output_json
                """,
                run_uuid,
                projection["spanId"],
                projection["phase"],
                projection["parentSpanId"],
                projection["spanType"],
                projection["agentName"] or None,
                projection["toolName"] or None,
                projection["model"] or None,
                json.dumps({"summary": projection["argSummary"]}),
                json.dumps({"summary": projection["resultSummary"], "status": projection["status"]}),
                projection["resultSummary"] if projection["status"] == "error" else None,
                _iso(projection["startedAt"]),
                _iso(projection["endedAt"]),
                projection["durationMs"],
            )
        except Exception as exc:
            logger.warning(
                "[FORTUNE] trace projection persist failed run=%s span=%s: %s",
                projection["runId"], projection["spanId"], exc,
            )

    def shutdown(self) -> None:
        return None

    def force_flush(self) -> None:
        return None

    async def aflush(self, timeout: float = 3.0, run_id: str | None = None) -> None:
        pending = [task for task, owner in self._pending.items() if run_id is None or owner == run_id]
        if not pending:
            return
        try:
            await asyncio.wait_for(asyncio.gather(*pending, return_exceptions=True), timeout=timeout)
        except asyncio.TimeoutError:
            logger.warning("[FORTUNE] trace flush timed out with %d events pending", len(pending))


_registered = False
_processor: GlassBoxTraceProcessor | None = None


def get_trace_processor() -> GlassBoxTraceProcessor:
    global _processor
    if _processor is None:
        _processor = GlassBoxTraceProcessor()
    return _processor


def ensure_registered() -> None:
    global _registered
    if _registered:
        return
    try:
        from agents import add_trace_processor
        add_trace_processor(get_trace_processor())
        _registered = True
        logger.info("[FORTUNE] GlassBoxTraceProcessor registered")
    except Exception as exc:
        logger.error("[FORTUNE] trace processor registration failed: %s", exc)


async def flush_pending_spans(timeout: float = 3.0, run_id: str | None = None) -> None:
    await get_trace_processor().aflush(timeout=timeout, run_id=run_id)
