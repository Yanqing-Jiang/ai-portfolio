"""Trace collector for Ming Engine agent pipeline.

Captures timing and metadata for every computation step, making the
agent harness transparent. Trace steps are emitted progressively via SSE
so the frontend can render a real-time "Glass Box" sidebar.
"""

from __future__ import annotations

import time
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Generator

from pydantic import BaseModel, Field


class TraceStep(BaseModel):
    """A single step in the agent pipeline trace."""
    step_id: str = Field(default_factory=lambda: f"ts_{uuid.uuid4().hex[:8]}")
    step_type: str       # "tool_call" | "tool_result" | "llm_start" | "llm_complete" | "data_emit"
    agent_name: str      # which agent or "foundation"
    tool_name: str | None = None
    label: str = ""      # human-friendly label
    input_summary: str = ""
    output_summary: str = ""
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    duration_ms: float = 0.0
    status: str = "pending"  # "pending" | "running" | "success" | "error"


class TraceCollector:
    """Collects trace steps during a pipeline run.

    Usage:
        collector = TraceCollector()
        with collector.step("tool_call", "foundation", tool_name="compute_bazi_chart",
                            label="Calculating Four Pillars",
                            input_summary="1990-05-15T14:00 Asia/Taipei") as ts:
            result = compute_bazi_chart(...)
            ts.output_summary = f"Day master: {result['day_master']}"

        # After all steps:
        summary = collector.summary()
    """

    def __init__(self) -> None:
        self.steps: list[TraceStep] = []
        self._start_time = time.monotonic()

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
        """Context manager that times a computation step."""
        ts = TraceStep(
            step_type=step_type,
            agent_name=agent_name,
            tool_name=tool_name,
            label=label,
            input_summary=input_summary,
            status="running",
        )
        self.steps.append(ts)
        t0 = time.monotonic()
        try:
            yield ts
            ts.duration_ms = round((time.monotonic() - t0) * 1000, 1)
            ts.status = "success"
        except Exception as exc:
            ts.duration_ms = round((time.monotonic() - t0) * 1000, 1)
            ts.status = "error"
            ts.output_summary = str(exc)[:200]
            raise

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
        """Add a zero-duration trace step (e.g., for data emissions)."""
        ts = TraceStep(
            step_type=step_type,
            agent_name=agent_name,
            tool_name=tool_name,
            label=label,
            input_summary=input_summary,
            output_summary=output_summary,
            duration_ms=0.0,
            status="success",
        )
        self.steps.append(ts)
        return ts

    def summary(self) -> dict[str, Any]:
        """Return aggregate trace summary."""
        total_ms = round((time.monotonic() - self._start_time) * 1000, 1)
        tool_calls = sum(1 for s in self.steps if s.step_type == "tool_call")
        llm_calls = sum(1 for s in self.steps if s.step_type in ("llm_start", "llm_complete"))
        return {
            "totalDurationMs": total_ms,
            "toolCallCount": tool_calls,
            "llmCallCount": llm_calls,
            "stepCount": len(self.steps),
        }
