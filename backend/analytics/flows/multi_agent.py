from __future__ import annotations

from datetime import datetime
import time
from typing import Any, AsyncGenerator, Dict, Optional

from analytics.core.telemetry import analysis_chunk as log_analysis_chunk
from .planner_executor import PlannerExecutorFlow


class MultiAgentFlow:
    """Coordinates specialist agents while reusing the planner-executor core."""

    AGENT_START_STEPS = {
        "intent_detection": "intent_analyst",
        "clarification": "user_liaison",
        "sql_compilation": "sql_specialist",
        "sql_validation": "risk_controller",
        "sql_execution": "data_engineer",
        "chart_generation": "viz_designer",
        "analysis_generation": "insight_reviewer",
    }

    AGENT_END_EVENTS = {
        "intent_detection_complete": "intent_analyst",
        "clarification_resolved": "user_liaison",
        "clarification_skipped": "user_liaison",
        "clarification_timeout": "user_liaison",
        "sql_generated": "sql_specialist",
        "sql_validated": "risk_controller",
        "execution_stats": "data_engineer",
        "chart_generated": "viz_designer",
        "analysis_complete": "insight_reviewer",
    }

    def __init__(self) -> None:
        self._planner = PlannerExecutorFlow()
        self.flow_label = "multi-agent"
        self._timers: Dict[str, float] = {}

    async def events(
        self, query: str, session_id: Optional[str] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        active_session = session_id
        async for event in self._planner.events(query, session_id=session_id):
            if event.get("event") == "session_started":
                active_session = (event.get("data") or {}).get("session_id", active_session)
            start_event = self._maybe_agent_turn_start(event)
            if start_event:
                yield start_event
            if event.get("event") == "analysis_streaming":
                reasoning = self._agent_reasoning(event, active_session)
                if reasoning:
                    yield reasoning
            yield event
            end_event = self._maybe_agent_turn_end(event)
            if end_event:
                yield end_event

    def _maybe_agent_turn_start(self, event: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if event.get("event") != "progress":
            return None
        step = (event.get("data") or {}).get("step")
        role = self.AGENT_START_STEPS.get(step)
        if not role:
            return None
        self._timers[role] = time.time()
        return {
            "event": "agent_turn",
            "data": {
                "role": role,
                "status": "start",
                "step": step,
                "ts": datetime.utcnow().isoformat(),
            },
        }

    def _maybe_agent_turn_end(self, event: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        role = self.AGENT_END_EVENTS.get(event.get("event"))
        if not role:
            return None
        start = self._timers.pop(role, None)
        elapsed = int((time.time() - start) * 1000) if start else None
        payload: Dict[str, Any] = {
            "role": role,
            "status": "complete",
            "ts": datetime.utcnow().isoformat(),
        }
        summary = self._agent_summary(role, event)
        if summary:
            payload["summary"] = summary
        if elapsed is not None:
            payload["elapsed_ms"] = elapsed
        return {"event": "agent_turn", "data": payload}

    def _agent_reasoning(self, event: Dict[str, Any], session_id: Optional[str]) -> Optional[Dict[str, Any]]:
        delta = (event.get("data") or {}).get("partial_analysis")
        if not delta:
            return None
        log_analysis_chunk(
            chunk=delta,
            step="analysis_generation",
            role="insight_reviewer",
            session_id=session_id,
            flow=getattr(self, "flow_label", None),
        )
        return {
            "event": "agent_reasoning",
            "data": {
                "role": "insight_reviewer",
                "thought": delta,
                "ts": datetime.utcnow().isoformat(),
            },
        }

    def _agent_summary(self, role: str, event: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        data = event.get("data") or {}
        if role == "intent_analyst":
            return {"intent_key": data.get("intent_key"), "confidence": data.get("confidence")}
        if role == "sql_specialist":
            return {"llm_used": data.get("llm_used"), "template_fallback": data.get("template_fallback")}
        if role == "risk_controller":
            return {"ok": data.get("ok"), "issues": data.get("issues_count")}
        if role == "data_engineer":
            return {"rows": data.get("row_count")}
        if role == "viz_designer":
            return {"chart_type": data.get("chart_type")}
        if role == "insight_reviewer":
            return {"analysis_length": data.get("analysis_length")}
        return None
