from __future__ import annotations

from datetime import datetime
import time
from typing import Any, AsyncGenerator, Dict, Optional

from analytics.core.telemetry import tool_iteration as log_tool_iteration
from analytics.core.session_state import SessionStateSnapshot, get_session_state_repository
from analytics.routing import FollowUpRoute
from .hooks import AnalyticsFlowHooks
from .planner_executor import PlannerExecutorFlow, run_planner_executor
from .pipeline_tools import get_planner_tool_registry
from .schedulers import FlowMode, apply_mode_metadata


def _build_tool_metadata(manifest: Any) -> Dict[str, Dict[str, Any]]:
    metadata: Dict[str, Dict[str, Any]] = {}
    try:
        iterable = list(manifest)
    except TypeError:
        return metadata
    for entry in iterable:
        if not isinstance(entry, dict):
            continue
        name = entry.get("name")
        if not isinstance(name, str):
            continue
        metadata[name] = {
            "latency_budget_ms": entry.get("latency_budget_ms"),
            "output_artifacts": entry.get("output_artifacts"),
            "concurrency_limit": entry.get("concurrency_limit"),
        }
    return metadata


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
        payload: Dict[str, Any] = {
            "tool": tool,
            "status": "start",
            "step": step,
            "ts": datetime.utcnow().isoformat(),
        }
        metadata = self._flow.get_tool_metadata_for_step(step)
        if not metadata:
            metadata = self._flow.get_tool_metadata_for_alias(tool)
        if metadata:
            payload["latency_budget_ms"] = metadata.get("latency_budget_ms")
            payload["output_artifacts"] = metadata.get("output_artifacts")
            payload["concurrency_limit"] = metadata.get("concurrency_limit")
        annotated = apply_mode_metadata({"event": "tool_call", "data": payload}, self._flow.flow_mode)
        annotated["data"]["follow_up_route"] = self._flow.follow_up_route.value
        yield annotated

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
        metadata = self._flow.get_tool_metadata_for_event(event_name)
        if not metadata:
            metadata = self._flow.get_tool_metadata_for_alias(tool)
        if metadata:
            payload["latency_budget_ms"] = metadata.get("latency_budget_ms")
            payload["output_artifacts"] = metadata.get("output_artifacts")
            payload["concurrency_limit"] = metadata.get("concurrency_limit")
        log_tool_iteration(
            tool=tool,
            status="end",
            step=event_name,
            session_id=self._session_id,
            flow=self._flow.flow_label,
            elapsed_ms=elapsed,
            details=payload.get("details") or payload,
        )
        annotated_end = apply_mode_metadata({"event": "tool_call", "data": payload}, self._flow.flow_mode)
        annotated_end["data"]["follow_up_route"] = self._flow.follow_up_route.value
        yield annotated_end

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
        "classification": "intent_classifier",
        "intent_detection": "intent_classifier",
        "clarification": "clarification_manager",
        "plan_generation": "planner",
        "sql_compilation": "sql_generator",
        "sql_validation": "sql_validator",
        "sql_execution": "sql_executor",
        "chart_generation": "chart_designer",
        "chart_revision": "chart_designer",
        "analysis_generation": "analysis_writer",
        "analysis_revision": "analysis_writer",
    }

    TOOL_END_EVENTS = {
        "classification_complete": "intent_classifier",
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

    TOOL_METADATA_STEP_MAP = {
        "classification": "classification",
        "intent_detection": "intent_detection",
        "clarification": "clarification",
        "plan_generation": "plan_generation",
        "sql_compilation": "sql_generation",
        "sql_validation": "sql_generation",
        "sql_execution": "sql_generation",
        "chart_generation": "chart_generation",
        "chart_revision": "chart_revision",
        "analysis_generation": "analysis_generation",
        "analysis_revision": "analysis_revision",
    }

    TOOL_METADATA_EVENT_MAP = {
        "classification_complete": "classification",
        "intent_detection_complete": "intent_detection",
        "clarification_resolved": "clarification",
        "clarification_skipped": "clarification",
        "clarification_timeout": "clarification",
        "sql_generated": "sql_generation",
        "sql_compiled": "sql_generation",
        "sql_validated": "sql_generation",
        "execution_stats": "sql_generation",
        "chart_generated": "chart_generation",
        "chart_patch": "chart_revision",
        "analysis_revision": "analysis_revision",
        "analysis_complete": "analysis_generation",
    }

    TOOL_METADATA_ALIAS_MAP = {
        "intent_classifier": "classification",
        "clarification_manager": "clarification",
        "planner": "plan_generation",
        "sql_generator": "sql_generation",
        "sql_validator": "sql_generation",
        "sql_executor": "sql_generation",
        "chart_designer": "chart_generation",
        "analysis_writer": "analysis_generation",
    }

    def __init__(self) -> None:
        self._planner = PlannerExecutorFlow(flow_mode=FlowMode.SINGLE_AGENT)
        self.follow_up_route = FollowUpRoute.FULL_PIPELINE
        self._planner.set_follow_up_route(self.follow_up_route)
        self.flow_mode = FlowMode.SINGLE_AGENT
        self.flow_label = "single-agent"
        registry = get_planner_tool_registry()
        self.planner_tool_manifest = registry.describe_tools()
        self._tool_metadata_by_registry = _build_tool_metadata(self.planner_tool_manifest)
        self.tool_metadata: Dict[str, Dict[str, Any]] = {}
        for alias, registry_name in self.TOOL_METADATA_ALIAS_MAP.items():
            metadata = self._tool_metadata_by_registry.get(registry_name)
            if metadata:
                self.tool_metadata[alias] = metadata

    def prime_with_snapshot(self, snapshot: Optional[SessionStateSnapshot]) -> None:
        self._planner.prime_with_snapshot(snapshot)

    def set_follow_up_route(self, route: FollowUpRoute) -> None:
        self.follow_up_route = route
        self._planner.set_follow_up_route(route)

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

    def get_tool_metadata_for_step(self, step: Optional[str]) -> Optional[Dict[str, Any]]:
        if not step:
            return None
        registry_name = self.TOOL_METADATA_STEP_MAP.get(step)
        if not registry_name:
            return None
        return self._tool_metadata_by_registry.get(registry_name)

    def get_tool_metadata_for_event(self, event_name: Optional[str]) -> Optional[Dict[str, Any]]:
        if not event_name:
            return None
        registry_name = self.TOOL_METADATA_EVENT_MAP.get(event_name)
        if not registry_name:
            return None
        return self._tool_metadata_by_registry.get(registry_name)

    def get_tool_metadata_for_alias(self, alias: Optional[str]) -> Optional[Dict[str, Any]]:
        if not alias:
            return None
        metadata = self.tool_metadata.get(alias)
        if metadata:
            return metadata
        registry_name = self.TOOL_METADATA_ALIAS_MAP.get(alias)
        if registry_name:
            return self._tool_metadata_by_registry.get(registry_name)
        return None




    def latest_artifacts(self):
        return self._planner.latest_artifacts()

