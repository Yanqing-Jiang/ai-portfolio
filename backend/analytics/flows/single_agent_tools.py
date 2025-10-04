from __future__ import annotations

from datetime import datetime
import time
from typing import Any, AsyncGenerator, Dict, Optional

from analytics.core.telemetry import tool_iteration as log_tool_iteration
from .planner_executor import PlannerExecutorFlow, run_planner_executor


class SingleAgentToolsFlow:
    """Augments the planner-executor flow with explicit tool-call telemetry."""

    TOOL_START_STEPS = {
        "intent_detection": "intent_classifier",
        "clarification": "clarification_manager",
        "sql_compilation": "sql_generator",
        "sql_validation": "sql_validator",
        "sql_execution": "sql_executor",
        "chart_generation": "chart_designer",
        "analysis_generation": "analysis_writer",
    }

    TOOL_END_EVENTS = {
        "intent_detection_complete": "intent_classifier",
        "clarification_resolved": "clarification_manager",
        "clarification_skipped": "clarification_manager",
        "clarification_timeout": "clarification_manager",
        "sql_generated": "sql_generator",
        "sql_validated": "sql_validator",
        "execution_stats": "sql_executor",
        "chart_generated": "chart_designer",
        "analysis_complete": "analysis_writer",
    }

    def __init__(self) -> None:
        self._planner = PlannerExecutorFlow()
        self.flow_label = "single-agent"
        self._timers: Dict[str, float] = {}
        self._sql_compile_details: Dict[str, Any] = {}
    async def events(
        self, query: str, session_id: Optional[str] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        active_session = session_id
        planner_events = getattr(self._planner, "events", None)
        if callable(planner_events):
            planner_stream = planner_events(query, session_id=session_id, skip_preflight=True)
        else:
            planner_stream = run_planner_executor(query, session_id=session_id, skip_preflight=True)

        async for event in planner_stream:
            if event.get("event") == "session_started":
                active_session = (event.get("data") or {}).get("session_id", active_session)
            start_event = self._maybe_tool_start(event, active_session)
            if start_event:
                yield start_event
            yield event
            end_event = self._maybe_tool_end(event, active_session)
            if end_event:
                yield end_event

    def _maybe_tool_start(self, event: Dict[str, Any], session_id: Optional[str]) -> Optional[Dict[str, Any]]:
        if event.get("event") != "progress":
            return None
        step = (event.get("data") or {}).get("step")
        tool = self.TOOL_START_STEPS.get(step)
        if not tool:
            return None
        self._timers[tool] = time.time()
        log_tool_iteration(
            tool=tool,
            status="start",
            step=step,
            session_id=session_id,
            flow=self.flow_label,
        )
        return {
            "event": "tool_call",
            "data": {
                "tool": tool,
                "status": "start",
                "step": step,
                "ts": datetime.utcnow().isoformat(),
            },
        }

    def _maybe_tool_end(self, event: Dict[str, Any], session_id: Optional[str]) -> Optional[Dict[str, Any]]:
        event_name = event.get("event")
        if event_name == "sql_compiled":
            self._sql_compile_details = event.get("data", {}) or {}
            return None
        tool = self.TOOL_END_EVENTS.get(event_name)
        if not tool:
            return None
        start = self._timers.pop(tool, None)
        elapsed = int((time.time() - start) * 1000) if start else None
        payload: Dict[str, Any] = {
            "tool": tool,
            "status": "end",
            "ts": datetime.utcnow().isoformat(),
            "details": self._extract_tool_details(tool, event),
        }
        if elapsed is not None:
            payload["elapsed_ms"] = elapsed
        log_tool_iteration(
            tool=tool,
            status="end",
            step=event_name,
            session_id=session_id,
            flow=self.flow_label,
            elapsed_ms=elapsed,
            details=payload.get("details") or payload,
        )
        return {"event": "tool_call", "data": payload}

    def _extract_tool_details(self, tool: str, event: Dict[str, Any]) -> Dict[str, Any]:
        data = event.get("data") or {}
        if tool == "intent_classifier":
            return {
                "intent_key": data.get("intent_key"),
                "confidence": data.get("confidence"),
                "clarifications_needed": data.get("clarifications_needed"),
            }
        if tool == "sql_generator":
            details = {
                "llm_used": data.get("llm_used"),
            }
            if self._sql_compile_details:
                details["template_used"] = self._sql_compile_details.get("template_used")
                details["sql_length"] = self._sql_compile_details.get("sql_length")
            self._sql_compile_details = {}
            return details
        if tool == "sql_validator":
            return {"ok": data.get("ok"), "issues": data.get("issues_count")}
        if tool == "sql_executor":
            return {"row_count": data.get("row_count")}
        if tool == "chart_designer":
            return {"chart_type": data.get("chart_type")}
        if tool == "analysis_writer":
            return {"analysis_length": data.get("analysis_length")}
        return data

