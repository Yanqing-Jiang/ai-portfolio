"""Structured agent-stage logging for the fortune pipeline.

Single-line key=value log records emitted at every Agent run boundary so the
4 user-facing functions (compatibility / occasion / luck_cycle / wish) plus
the general reading can be A/B-tested, perf-traced, and grepped without
parsing free-form messages.

Format::

    [FORTUNE-AGENT] fn=<function> stage=<stage> model=<model>
        reasoning=<effort> latency_ms=<int>
        tokens_in=<int> tokens_out=<int> reasoning_tokens=<int>
        run_id=<uuid> fortune_id=<uuid> agent=<name> ok=<true|false>

Designed for ``grep "[FORTUNE-AGENT]"`` followed by ``awk -F'[= ]' '{...}'``
or piped into a JSON-line scraper (the prefix lets the formatter ignore it).

If LangSmith / OTEL pickup is needed later we can dual-emit; for now the
durable trace lives in ``fortune_trace`` (Postgres, written by
``GlassBoxTraceProcessor``) and this is the dev/CI quick-look surface.
"""

from __future__ import annotations

import logging
import time
from collections import defaultdict
from contextlib import contextmanager
from dataclasses import dataclass
from threading import Lock
from typing import Any, Iterator

logger = logging.getLogger("fortune.agent")
_LATENCY_BUCKETS_MS = (250, 500, 1000, 2000, 5000, 10000, 30000, 60000)
_HISTOGRAM_LOCK = Lock()
_HISTOGRAMS: dict[tuple[str, str], list[int]] = defaultdict(
    lambda: [0] * (len(_LATENCY_BUCKETS_MS) + 1)
)


def _latency_bucket(latency_ms: float) -> str:
    for upper in _LATENCY_BUCKETS_MS:
        if latency_ms <= upper:
            return str(upper)
    return "inf"


def record_latency(function: str, stage: str, latency_ms: float) -> str:
    """Record one in-process latency sample and return its bucket label."""
    bucket = _latency_bucket(latency_ms)
    index = (
        len(_LATENCY_BUCKETS_MS)
        if bucket == "inf"
        else _LATENCY_BUCKETS_MS.index(int(bucket))
    )
    with _HISTOGRAM_LOCK:
        _HISTOGRAMS[(function, stage)][index] += 1
    return bucket


def latency_histogram_snapshot() -> dict[str, dict[str, int]]:
    """Return stage latency counts for tests/debug endpoints without log parsing."""
    labels = [str(v) for v in _LATENCY_BUCKETS_MS] + ["inf"]
    with _HISTOGRAM_LOCK:
        return {
            f"{function}.{stage}": dict(zip(labels, counts, strict=True))
            for (function, stage), counts in _HISTOGRAMS.items()
        }


# ---------------------------------------------------------------------------
# Function classification (the "4 functions" the user-facing UI exposes)
# ---------------------------------------------------------------------------

def classify_function(focus: str | None, question: str | None) -> str:
    """Classify an incoming reading into one of 5 buckets.

    The 4 customer-facing functions are: compatibility, occasion (lucky day),
    luck_cycle, wish. ``general`` covers the default Ming reading with no
    free-form question and no specialized focus prefix.
    """
    if focus and focus.startswith("compatibility"):
        return "compatibility"
    if focus and focus.startswith("occasion"):
        return "occasion"
    if focus and focus.startswith("luck_cycle"):
        return "luck_cycle"
    if question:
        return "wish"
    return "general"


# ---------------------------------------------------------------------------
# Usage extraction
# ---------------------------------------------------------------------------

@dataclass
class UsageSummary:
    input_tokens: int = 0
    output_tokens: int = 0
    reasoning_tokens: int = 0
    total_tokens: int = 0
    requests: int = 0


def extract_usage(result: Any) -> UsageSummary:
    """Pull token usage off a RunResult / RunResultStreaming.

    The Agents SDK exposes usage on ``result.context_wrapper.usage``. For
    streamed runs the final usage is only populated after the stream is
    fully consumed; callers should invoke this after the stream loop ends.
    Returns zeros when usage is unavailable rather than raising — these
    log lines are advisory.
    """
    try:
        ctx = getattr(result, "context_wrapper", None)
        usage = getattr(ctx, "usage", None)
        if usage is None:
            return UsageSummary()
        out_details = getattr(usage, "output_tokens_details", None)
        return UsageSummary(
            input_tokens=int(getattr(usage, "input_tokens", 0) or 0),
            output_tokens=int(getattr(usage, "output_tokens", 0) or 0),
            reasoning_tokens=int(
                getattr(out_details, "reasoning_tokens", 0) or 0
            ),
            total_tokens=int(getattr(usage, "total_tokens", 0) or 0),
            requests=int(getattr(usage, "requests", 0) or 0),
        )
    except Exception:  # pragma: no cover — log-side defensive
        return UsageSummary()


# ---------------------------------------------------------------------------
# Stage timer + emitter
# ---------------------------------------------------------------------------

@dataclass
class StageRecord:
    function: str
    stage: str
    model: str
    reasoning: str
    fortune_id: str
    run_id: str | None
    agent: str | None = None
    started_monotonic: float = 0.0
    extra: dict[str, Any] | None = None


def _format_kv(record: StageRecord, *, latency_ms: float, usage: UsageSummary, ok: bool, error: str | None) -> str:
    latency_bucket = record_latency(record.function, record.stage, latency_ms)
    parts = [
        f"fn={record.function}",
        f"stage={record.stage}",
        f"model={record.model}",
        f"reasoning={record.reasoning}",
        f"latency_ms={latency_ms:.0f}",
        f"latency_bucket_ms={latency_bucket}",
        f"tokens_in={usage.input_tokens}",
        f"tokens_out={usage.output_tokens}",
        f"reasoning_tokens={usage.reasoning_tokens}",
        f"requests={usage.requests}",
        f"run_id={record.run_id or '-'}",
        f"fortune_id={record.fortune_id or '-'}",
    ]
    if record.agent:
        parts.append(f"agent={record.agent}")
    parts.append(f"ok={'true' if ok else 'false'}")
    if error:
        # Truncate error to keep one-line grep useful.
        msg = error.replace("\n", " ").replace("=", "_")[:200]
        parts.append(f"error=\"{msg}\"")
    if record.extra:
        for k, v in record.extra.items():
            parts.append(f"{k}={v}")
    return "[FORTUNE-AGENT] " + " ".join(parts)


@contextmanager
def stage(
    *,
    function: str,
    stage: str,
    model: str,
    reasoning: str,
    fortune_id: str,
    run_id: str | None,
    agent: str | None = None,
    extra: dict[str, Any] | None = None,
) -> Iterator["StageHandle"]:
    """Context manager that times an agent stage and emits one structured log.

    Usage::

        with stage(function="wish", stage="narrative", model=..., ...) as sh:
            result = await Runner.run(...)
            sh.attach_result(result)

    On normal exit, emits an ``ok=true`` line with usage extracted from the
    attached result. On exception, emits ``ok=false error=<msg>`` and
    re-raises so callers see the failure.
    """
    record = StageRecord(
        function=function,
        stage=stage,
        model=model,
        reasoning=reasoning,
        fortune_id=fortune_id,
        run_id=run_id,
        agent=agent,
        started_monotonic=time.monotonic(),
        extra=extra,
    )
    handle = StageHandle(record)
    try:
        yield handle
    except Exception as exc:
        latency_ms = (time.monotonic() - record.started_monotonic) * 1000
        logger.warning(
            _format_kv(record, latency_ms=latency_ms, usage=UsageSummary(), ok=False, error=str(exc))
        )
        raise
    else:
        latency_ms = (time.monotonic() - record.started_monotonic) * 1000
        logger.info(
            _format_kv(
                record,
                latency_ms=latency_ms,
                usage=handle._usage,
                ok=True,
                error=None,
            )
        )


class StageHandle:
    """Receiver returned by ``stage()`` so callers can attach an SDK result."""

    def __init__(self, record: StageRecord) -> None:
        self._record = record
        self._usage = UsageSummary()

    def attach_result(self, result: Any) -> None:
        """Pull usage off the SDK result (RunResult / RunResultStreaming)."""
        self._usage = extract_usage(result)

    def attach_usage(self, usage: UsageSummary) -> None:
        """Set usage directly (e.g. when summing multiple sub-calls)."""
        self._usage = usage

    @property
    def function(self) -> str:
        return self._record.function

    @property
    def stage(self) -> str:
        return self._record.stage


# ---------------------------------------------------------------------------
# Top-of-stream summary line
# ---------------------------------------------------------------------------

def log_stream_start(
    *,
    fortune_id: str,
    run_id: str | None,
    function: str,
    focus: str | None,
    model: str,
    reasoning: str,
    has_person_b: bool = False,
    extra: dict[str, Any] | None = None,
) -> None:
    """Emit the per-stream banner so per-function counts are easy to grep."""
    parts = [
        f"event=stream_start",
        f"fn={function}",
        f"focus={focus or '-'}",
        f"model={model}",
        f"reasoning={reasoning}",
        f"person_b={'true' if has_person_b else 'false'}",
        f"run_id={run_id or '-'}",
        f"fortune_id={fortune_id or '-'}",
    ]
    if extra:
        for k, v in extra.items():
            parts.append(f"{k}={v}")
    logger.info("[FORTUNE-AGENT] " + " ".join(parts))


def log_stream_end(
    *,
    fortune_id: str,
    run_id: str | None,
    function: str,
    total_ms: float,
    ok: bool,
    error: str | None = None,
) -> None:
    parts = [
        f"event=stream_end",
        f"fn={function}",
        f"total_ms={total_ms:.0f}",
        f"ok={'true' if ok else 'false'}",
        f"run_id={run_id or '-'}",
        f"fortune_id={fortune_id or '-'}",
    ]
    if error:
        msg = error.replace("\n", " ")[:200]
        parts.append(f"error=\"{msg}\"")
    (logger.info if ok else logger.warning)("[FORTUNE-AGENT] " + " ".join(parts))
