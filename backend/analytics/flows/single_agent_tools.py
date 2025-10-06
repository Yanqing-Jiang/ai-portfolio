from __future__ import annotations

from datetime import datetime
import time
from typing import Any, AsyncGenerator, Dict, Optional

from analytics.core.telemetry import tool_iteration as log_tool_iteration
from .hooks import AnalyticsFlowHooks
from .planner_executor import PlannerExecutorFlow, run_planner_executor


class _SingleAgentToolHooks(AnalyticsFlowHooks):
    def __init__(self, flow: "SingleAgentToolsFlow") -> None:
        self._flow = flow
        self._timers: Dict[str, float] = {}
        self._sql_compile_details: Dict[str, Any] = {}
        self._session_id: Optional[str] = None

    async def on_flow_start(self, ctx: Dict[str, Any]) -> AsyncGenerator[Dict[str, Any], None]:
        if False:
            yield {}

    async def before_event(self, ctx: Dict[str, Any], event: Dict[str, Any]) -> AsyncGenerator[Dict[str, Any], None]:
        if False:
            yield {}
        name = event.get("event")
        if name == "session_started":
            data = event.get("data") or {}
            self._session_id = data.get("session_id") or ctx.get("session_id")
            ctx["session_id"] = self._session_id
            return
        if name != "progress":
            return
        step = (event.get("data") or {}).get("step")
        tool = self._flow.TOOL_START_STEPS.get(step)
        if not tool:
            return
        self._timers[tool] = time.time()
        log_tool_iteration(
            tool=tool,
            status="start",
            step=step,
            session_id=self._session_id,
            flow=self._flow.flow_label,
        )
        yield {
            "event": "tool_call",
            "data": {
                "tool": tool,
                "status": "start",
                "step": step,
                "ts": datetime.utcnow().isoformat(),
            },
        }

    async def after_event(self, ctx: Dict[str, Any], event: Dict[str, Any]) -> AsyncGenerator[Dict[str, Any], None]:
        if False:
            yield {}
        event_name = event.get("event")
        if event_name == "sql_compiled":
            self._sql_compile_details = event.get("data", {}) or {}
            return
        tool = self._flow.TOOL_END_EVENTS.get(event_name)
        if not tool:
            return
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
            session_id=self._session_id,
            flow=self._flow.flow_label,
            elapsed_ms=elapsed,
            details=payload.get("details") or payload,
        )
        yield {"event": "tool_call", "data": payload}

    async def on_flow_end(
        self,
        ctx: Dict[str, Any],
        *,
        error: Optional[BaseException] = None,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        if False:
            yield {}

    def _extract_tool_details(self, tool: str, event: Dict[str, Any]) -> Dict[str, Any]:
        data = event.get("data") or {}
        if tool == "intent_classifier":
            return {
                "intent_key": data.get("intent_key"),
                "confidence": data.get("confidence"),
                "clarifications_needed": data.get("clarifications_needed"),
            }
        if tool == "sql_generator":
            details = {"llm_used": data.get("llm_used")}
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

    async def events(
        self,
        query: str,
        session_id: Optional[str] = None,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        planner_events = getattr(self._planner, "events", None)
        hooks = _SingleAgentToolHooks(self)
        if callable(planner_events):
            async for event in planner_events(query, session_id=session_id, hooks=hooks):
                yield event
        else:
            planner_stream = run_planner_executor(query, session_id=session_id)
            async for event in planner_stream:
                yield event


