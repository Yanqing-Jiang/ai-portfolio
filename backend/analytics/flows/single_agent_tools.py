from __future__ import annotations

from datetime import datetime
import time
from typing import Any, AsyncGenerator, Dict, Optional

from analytics.core.telemetry import tool_iteration as log_tool_iteration
from analytics.core.session_state import get_session_state_repository
from .hooks import AnalyticsFlowHooks
from .planner_executor import PlannerExecutorFlow, run_planner_executor
from .pipeline_tools import get_planner_tool_registry


class _SingleAgentToolHooks(AnalyticsFlowHooks):
    def __init__(self, flow: "SingleAgentToolsFlow", session_id: Optional[str] = None) -> None:
        self._flow = flow
        self._timers: Dict[str, float] = {}
        self._sql_compile_details: Dict[str, Any] = {}
        self._session_id: Optional[str] = session_id

    async def on_flow_start(self, ctx: Dict[str, Any]) -> AsyncGenerator[Dict[str, Any], None]:
        if ctx.get("session_id") and not self._session_id:
            session = ctx.get("session_id")
            if isinstance(session, str) and session:
                self._session_id = session
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
        "chart_revision": "chart_designer",
        "analysis_generation": "analysis_writer",
        "analysis_revision": "analysis_writer",
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
        "chart_patch": "chart_designer",
        "analysis_revision": "analysis_writer",
        "analysis_complete": "analysis_writer",
    }

    def __init__(self) -> None:
        self._planner = PlannerExecutorFlow()
        self.flow_label = "single-agent"
        self.planner_tool_manifest = get_planner_tool_registry().describe_tools()

    async def _forward_with_hooks(
        self,
        stream: AsyncGenerator[Dict[str, Any], None],
        hooks: _SingleAgentToolHooks,
        session_id: Optional[str],
    ) -> AsyncGenerator[Dict[str, Any], None]:
        hook_ctx: Dict[str, Any] = {"session_id": session_id}
        try:
            async for start_event in hooks.on_flow_start(hook_ctx):
                yield start_event
            async for event in stream:
                async for pre_event in hooks.before_event(hook_ctx, event):
                    yield pre_event
                yield event
                if event.get("event") == "session_started":
                    data = event.get("data") or {}
                    hook_ctx["session_id"] = data.get("session_id", hook_ctx.get("session_id"))
                async for post_event in hooks.after_event(hook_ctx, event):
                    yield post_event
        except BaseException as exc:
            async for end_event in hooks.on_flow_end(hook_ctx, error=exc):
                yield end_event
            raise
        else:
            async for end_event in hooks.on_flow_end(hook_ctx):
                yield end_event

    async def _resolve_session_query(self, session_id: str) -> str:
        repository = get_session_state_repository()
        snapshot = await repository.load(session_id)
        if snapshot and snapshot.last_query:
            return snapshot.last_query
        return ""

    async def _invoke_planner_tool(
        self,
        tool_name: str,
        *,
        session_id: str,
        query: Optional[str],
        hooks: _SingleAgentToolHooks,
        **kwargs: Any,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        resolved_query = query if query is not None else await self._resolve_session_query(session_id)
        ctx = await self._planner.initialize_context(resolved_query or "", session_id=session_id)
        registry = get_planner_tool_registry()
        tool_stream = registry.invoke(tool_name, self._planner._pipeline, ctx, **kwargs)
        async for event in self._forward_with_hooks(tool_stream, hooks, session_id):
            yield event

    async def events(
        self,
        query: str,
        session_id: Optional[str] = None,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        planner_events = getattr(self._planner, "events", None)
        hooks = _SingleAgentToolHooks(self, session_id=session_id)
        if callable(planner_events):
            try:
                async for event in planner_events(query, session_id=session_id, hooks=hooks):
                    yield event
                return
            except TypeError:
                planner_stream = planner_events(query, session_id=session_id)
        else:
            planner_stream = run_planner_executor(query, session_id=session_id)

        async for event in self._forward_with_hooks(planner_stream, hooks, session_id):
            yield event

    async def chart_revision(
        self,
        *,
        session_id: str,
        patch: Dict[str, Any],
        reason: Optional[str] = None,
        source: Optional[str] = None,
        query: Optional[str] = None,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        hooks = _SingleAgentToolHooks(self, session_id=session_id)
        async for event in self._invoke_planner_tool(
            "chart_revision",
            session_id=session_id,
            query=query,
            hooks=hooks,
            patch=patch,
            reason=reason,
            source=source,
        ):
            yield event

    async def analysis_revision(
        self,
        *,
        session_id: str,
        analysis: str,
        reason: Optional[str] = None,
        source: Optional[str] = None,
        query: Optional[str] = None,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        hooks = _SingleAgentToolHooks(self, session_id=session_id)
        async for event in self._invoke_planner_tool(
            "analysis_revision",
            session_id=session_id,
            query=query,
            hooks=hooks,
            analysis=analysis,
            reason=reason,
            source=source,
        ):
            yield event














