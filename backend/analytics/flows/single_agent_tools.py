from __future__ import annotations

from datetime import datetime
import copy
import time
from typing import Any, AsyncGenerator, Dict, List, Optional

from analytics.artifacts.models import PipelineArtifacts
from analytics.core.telemetry import tool_iteration as log_tool_iteration
from analytics.core.session_state import SessionStateSnapshot, get_session_state_repository
from analytics.validators import sanitize_for_json
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



def _build_single_agent_cohesive_payload(
    analysis_payload: Dict[str, Any],
    artifacts: Optional[PipelineArtifacts],
    *,
    default_manifest: Optional[List[Dict[str, Any]]] = None,
) -> Optional[Dict[str, Any]]:
    if not isinstance(analysis_payload, dict):
        analysis_payload = {}

    payload: Dict[str, Any] = {}

    analysis_text = analysis_payload.get("analysis")
    if isinstance(analysis_text, str) and analysis_text.strip():
        payload["analysis"] = analysis_text

    length_value = analysis_payload.get("analysis_length")
    if isinstance(length_value, (int, float)):
        payload["analysis_length"] = int(length_value)

    passthrough_keys = {
        "tldr",
        "bullets",
        "key_numbers",
        "risk_watch",
        "next_steps",
        "latency_guardrail",
        "analysis_overview",
        "tool_manifest",
        "tool_results",
        "stock_widget",
        "web_context",
        "bundle",
        "banner",
    }
    for key in passthrough_keys:
        if key in analysis_payload and analysis_payload[key] is not None:
            payload[key] = copy.deepcopy(analysis_payload[key])

    if (not payload.get("tool_manifest")) and default_manifest:
        payload["tool_manifest"] = copy.deepcopy(default_manifest)

    if artifacts:
        chart_art = artifacts.chart
        if chart_art and chart_art.spec:
            payload.setdefault("chart_spec", copy.deepcopy(chart_art.spec))
            if chart_art.spec_id:
                payload.setdefault("chart_spec_id", chart_art.spec_id)

        sql_gen = artifacts.sql_generation
        if sql_gen and sql_gen.sql:
            payload.setdefault("sql", sql_gen.sql)

        sql_exec = artifacts.sql_execution
        if sql_exec:
            if sql_exec.row_count is not None:
                payload.setdefault("sql_row_count", sql_exec.row_count)
            if sql_exec.columns:
                payload.setdefault("columns", list(sql_exec.columns))
            sample = sql_exec.sample_rows or sql_exec.dataset_preview
            if sample:
                payload.setdefault("data_sample", copy.deepcopy(sample))

        analysis_art = artifacts.analysis
        if analysis_art:
            if ("analysis" not in payload or not payload.get("analysis")) and analysis_art.analysis_text:
                payload["analysis"] = analysis_art.analysis_text
                if analysis_art.length is not None and "analysis_length" not in payload:
                    payload["analysis_length"] = analysis_art.length
            if ("stock_widget" not in payload or not payload.get("stock_widget")) and analysis_art.stock_widget:
                payload["stock_widget"] = copy.deepcopy(analysis_art.stock_widget)
            if ("web_context" not in payload or not payload.get("web_context")) and analysis_art.web_context:
                payload["web_context"] = copy.deepcopy(analysis_art.web_context)
            if "analysis_overview" not in payload or not payload.get("analysis_overview"):
                overview: Dict[str, Any] = {}
                if analysis_art.summary:
                    overview["tldr"] = analysis_art.summary
                if analysis_art.highlights:
                    overview["highlights"] = list(analysis_art.highlights)
                if analysis_art.key_numbers:
                    overview["key_numbers"] = list(analysis_art.key_numbers)
                if analysis_art.risk_watch:
                    overview["risk_watch"] = list(analysis_art.risk_watch)
                if analysis_art.next_steps:
                    overview["next_steps"] = list(analysis_art.next_steps)
                if analysis_art.evidence:
                    overview["evidence"] = copy.deepcopy(analysis_art.evidence)
                if overview:
                    payload["analysis_overview"] = overview
            if analysis_art.tool_bundle:
                bundle = analysis_art.tool_bundle
                if bundle.get("tool_manifest") and not payload.get("tool_manifest"):
                    payload["tool_manifest"] = copy.deepcopy(bundle["tool_manifest"])
                if bundle.get("tool_results") and not payload.get("tool_results"):
                    payload["tool_results"] = copy.deepcopy(bundle["tool_results"])
                if bundle.get("stock_widget") and not payload.get("stock_widget"):
                    payload["stock_widget"] = copy.deepcopy(bundle["stock_widget"])
                if bundle.get("web_context") and not payload.get("web_context"):
                    payload["web_context"] = copy.deepcopy(bundle["web_context"])

        market_art = artifacts.market if artifacts else None
        if market_art and market_art.snapshot and not payload.get("stock_widget"):
            payload["stock_widget"] = copy.deepcopy(market_art.snapshot)

        web_art = artifacts.web if artifacts else None
        if web_art and not payload.get("web_context"):
            payload["web_context"] = web_art.to_dict()

    sanitized = sanitize_for_json(payload)
    if not sanitized:
        return None
    return sanitized


class _SingleAgentToolHooks(AnalyticsFlowHooks):
    def __init__(self, flow: "SingleAgentController", session_id: Optional[str] = None) -> None:
        self._flow = flow
        self._timers: Dict[str, float] = {}
        self._sql_compile_details: Dict[str, Any] = {}
        self._session_id: Optional[str] = session_id
        self._emitted_cohesive = False
        self._last_analysis_payload: Optional[Dict[str, Any]] = None

    async def on_flow_start(self, ctx: Dict[str, Any]) -> AsyncGenerator[Dict[str, Any], None]:
        self._emitted_cohesive = False
        self._last_analysis_payload = None
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

    def _maybe_emit_cohesive_result(self, analysis_payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if self._emitted_cohesive:
            return None
        cohesive_payload = _build_single_agent_cohesive_payload(
            analysis_payload=analysis_payload,
            artifacts=self._flow.latest_artifacts(),
            default_manifest=self._flow.planner_tool_manifest,
        )
        if not cohesive_payload:
            return None
        self._emitted_cohesive = True
        event = {"event": "cohesive_result", "data": cohesive_payload}
        annotated = apply_mode_metadata(event, self._flow.flow_mode)
        annotated["data"]["follow_up_route"] = self._flow.follow_up_route.value
        return annotated

    async def after_event(self, ctx: Dict[str, Any], event: Dict[str, Any]) -> AsyncGenerator[Dict[str, Any], None]:
        if False:
            yield {}
        event_name = event.get("event")
        if event_name == "sql_compiled":
            self._sql_compile_details = event.get("data", {}) or {}
            return

        tool = self._flow.TOOL_END_EVENTS.get(event_name)
        if tool:
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
            return

        if event_name == "analysis_complete":
            analysis_payload = copy.deepcopy(event.get("data") or {})
            if (not analysis_payload.get("tool_manifest")) and self._flow.planner_tool_manifest:
                analysis_payload["tool_manifest"] = copy.deepcopy(self._flow.planner_tool_manifest)
            self._last_analysis_payload = analysis_payload
            cohesive_event = self._maybe_emit_cohesive_result(analysis_payload)
            if cohesive_event:
                yield cohesive_event
            return

        if event_name == "workflow_complete":
            if self._last_analysis_payload:
                cohesive_event = self._maybe_emit_cohesive_result(copy.deepcopy(self._last_analysis_payload))
                if cohesive_event:
                    yield cohesive_event
            return

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


class SingleAgentController:
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

