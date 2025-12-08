# --- Analytics Function/Class Map ---
# Class: PlannerToolDefinition
#   Role: Handles PlannerToolDefinition logic for analytics.flows.pipeline_tools.
#   Called from: analytics.flows.single_agent_tools
#   Collaborators: dataclasses.field
#   Why: Keeps analytics.flows.pipeline_tools from duplicating PlannerToolDefinition behavior across flows.
# Class: PlannerToolRegistry
#   Role: Handles PlannerToolRegistry logic for analytics.flows.pipeline_tools.
#   Called from: analytics.flows.multi_agent, analytics.flows.planner.analysis_lane, analytics.flows.planner.sql_lane, analytics.flows.single_agent_tools
#   Collaborators: Internal helpers only
#   Why: Keeps analytics.flows.pipeline_tools from duplicating PlannerToolRegistry behavior across flows.
# Function: get_planner_tool_registry
#   Role: Handles get planner tool registry logic for analytics.flows.pipeline_tools.
#   Called from: analytics.flows.multi_agent, analytics.flows.planner_executor, analytics.flows.single_agent_tools, tests.analytics.test_pipeline_tools
#   Invokes: analytics.flows.pipeline_tools.PlannerToolRegistry, analytics.flows.pipeline_tools._bootstrap_registry
#   Why: Keeps analytics.flows.pipeline_tools from duplicating get planner tool registry behavior across flows.
# Function: _bootstrap_registry
#   Role: Handles bootstrap registry logic for analytics.flows.pipeline_tools.
#   Called from: Internal to analytics.flows.pipeline_tools
#   Invokes: analytics.flows.pipeline_tools.PlannerToolDefinition
#   Why: Keeps analytics.flows.pipeline_tools from duplicating bootstrap registry behavior across flows.
# Function: executor_factory_map
#   Role: Maps tool ids to lane executor factories for planner, single-agent, and multi-agent parity.
#   Called from: analytics.flows.pipeline_tools._bootstrap_registry
#   Invokes: analytics.flows.lane_executors factory helpers
#   Why: Binds canonical tool schemas to the shared lane executors.
# --- End Analytics Function/Class Map ---
from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Any, AsyncGenerator, Awaitable, Callable, Dict, Iterable, Optional, Sequence, Set, Mapping, List
import logging

from .planner_executor import PlannerPipeline, PlannerPhaseContext
from analytics.routing import FollowUpRoute
from analytics.validators import sanitize_for_json
from analytics.tools.search_tools import search_tools

from analytics.tools.definitions import TOOL_REGISTRY, ToolDefinition, ToolId
from analytics.tools.canonical_registry import get_canonical_registry
from .schedulers import get_mode_config, FlowMode
from .lane_executors import (
    create_analysis_executor,
    create_chart_executor,
    create_sql_executor,
    create_accessory_executor,
)


logger = logging.getLogger(__name__)

__all__ = [
    "PlannerToolDefinition",
    "PlannerToolRegistry",
    "get_planner_tool_registry",
]

PlannerToolHandler = Callable[[PlannerPipeline, PlannerPhaseContext, Dict[str, Any]], AsyncGenerator[Dict[str, Any], None]]


@dataclass
class PlannerToolDefinition:
    name: str
    description: str
    handler: PlannerToolHandler
    executor_factory: Optional[Callable[..., Any]] = None
    prerequisites: Sequence[str] = field(default_factory=tuple)
    telemetry_step: Optional[str] = None
    inputs: Sequence[str] = field(default_factory=tuple)
    outputs: Sequence[str] = field(default_factory=tuple)
    output_artifacts: Sequence[str] = field(default_factory=tuple)
    latency_budget_ms: Optional[int] = None
    concurrency_limit: Optional[int] = None
    parameters_schema: Optional[Dict[str, Any]] = None
    response_schema: Optional[Dict[str, Any]] = None
    retryable_errors: Sequence[str] = field(default_factory=tuple)
    error_severity: str = "transient"
    schema_version: str = "analytics_tool_schema/unspecified"


class PlannerToolRegistry:
    def __init__(self) -> None:
        self._tools: Dict[str, PlannerToolDefinition] = {}

    def register(self, definition: PlannerToolDefinition) -> None:
        key = definition.name
        if key in self._tools:
            raise ValueError(f"Planner tool '{key}' already registered")
        self._tools[key] = definition

    def get(self, name: str) -> PlannerToolDefinition:
        try:
            return self._tools[name]
        except KeyError as exc:
            raise KeyError(f"Planner tool '{name}' is not registered") from exc

    async def invoke(
        self,
        name: str,
        pipeline: PlannerPipeline,
        ctx: PlannerPhaseContext,
        *,
        executed: Optional[Set[str]] = None,
        use_executor: bool = True,
        **kwargs: Any,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        if executed is None:
            executed = set()
        if name in executed:
            return

        definition = self.get(name)
        for prerequisite in definition.prerequisites:
            async for event in self.invoke(
                prerequisite,
                pipeline,
                ctx,
                executed=executed,
                use_executor=use_executor,
                **kwargs,
            ):
                yield event
        executed.add(name)
        executor_factory = definition.executor_factory if use_executor else None
        if executor_factory is not None:
            mode_config = kwargs.get("mode_config")
            if mode_config is None:
                try:
                    flow_mode = getattr(ctx, "flow_mode", getattr(pipeline, "flow_mode", FlowMode.DIRECT))
                    mode_config = get_mode_config(flow_mode)
                except Exception:
                    mode_config = None
            factory_kwargs = {
                "registry": kwargs.get("registry") or self,
                "executed": executed,
                "tool_state": kwargs.get("tool_state") or getattr(ctx, "tool_state", None),
                "mode_config": mode_config,
                "run_sql_lane": kwargs.get("run_sql_lane", True),
                "run_chart_lane": kwargs.get("run_chart_lane", True),
                "reason": kwargs.get("reason"),
                "source": kwargs.get("source"),
            }
            executor = executor_factory(pipeline, ctx, **factory_kwargs)
            async for event in executor.run():
                yield event
            return

        async for event in definition.handler(pipeline, ctx, dict(kwargs)):
            yield event

    def list_tools(self) -> Sequence[PlannerToolDefinition]:
        return tuple(self._tools.values())

    def describe_tools(self) -> Sequence[Dict[str, Any]]:
        filtered: List[PlannerToolDefinition] = []
        for definition in self.list_tools():
            if definition.telemetry_step in {"web_refresh", "market_refresh"}:
                continue
            filtered.append(definition)
        return tuple(
            {
                "name": definition.name,
                "description": definition.description,
                "prerequisites": list(definition.prerequisites),
                "telemetry_step": definition.telemetry_step,
                "inputs": list(definition.inputs),
                "outputs": list(definition.outputs),
                "output_artifacts": list(definition.output_artifacts or definition.outputs),
                "latency_budget_ms": definition.latency_budget_ms,
                "concurrency_limit": definition.concurrency_limit,
                "parameters_schema": dict(definition.parameters_schema or {}),
                "response_schema": dict(definition.response_schema or {}),
                "retryable_errors": list(definition.retryable_errors or ()),
                "error_severity": definition.error_severity,
                "schema_version": definition.schema_version,
            }
            for definition in filtered
        )


_registry: Optional[PlannerToolRegistry] = None


def get_planner_tool_registry() -> PlannerToolRegistry:
    global _registry
    if _registry is None:
        _registry = PlannerToolRegistry()
        _bootstrap_registry(_registry)
    return _registry


def _bootstrap_registry(registry: PlannerToolRegistry) -> None:
    async def _run_classification(pipeline: PlannerPipeline, ctx: PlannerPhaseContext, _: Dict[str, Any]) -> AsyncGenerator[Dict[str, Any], None]:
        async for event in pipeline.run_classification(ctx):
            yield event

    async def _run_intent(pipeline: PlannerPipeline, ctx: PlannerPhaseContext, _: Dict[str, Any]) -> AsyncGenerator[Dict[str, Any], None]:
        async for event in pipeline.run_intent(ctx):
            yield event

    async def _run_clarification(pipeline: PlannerPipeline, ctx: PlannerPhaseContext, _: Dict[str, Any]) -> AsyncGenerator[Dict[str, Any], None]:
        async for event in pipeline.run_clarification(ctx):
            yield event

    async def _run_plan(pipeline: PlannerPipeline, ctx: PlannerPhaseContext, _: Dict[str, Any]) -> AsyncGenerator[Dict[str, Any], None]:
        async for event in pipeline.run_plan(ctx):
            yield event

    async def _run_sql(pipeline: PlannerPipeline, ctx: PlannerPhaseContext, _: Dict[str, Any]) -> AsyncGenerator[Dict[str, Any], None]:
        intent = ctx.intent
        plan = ctx.plan or ctx.provisional_plan
        if not intent or not plan:
            logger.warning(
                "Skipping SQL pipeline due to missing intent or plan",
                extra={
                    "session_id": ctx.session_id,
                    "has_intent": intent is not None,
                    "has_plan": plan is not None,
                    "flow_mode": getattr(ctx, "flow_mode", None),
                },
            )
            return
        logger.info(
            "Starting SQL pipeline",
            extra={
                "session_id": ctx.session_id,
                "intent_key": getattr(intent, "key", None),
                "selected_template": ctx.selected_template_id,
                "flow_mode": getattr(ctx, "flow_mode", None),
            },
        )
        async for event in pipeline.run_sql_pipeline(
            ctx,
            intent=intent,
            plan=plan,
            candidate_templates=ctx.candidate_templates,
            selected_template_id=ctx.selected_template_id,
        ):
            logger.debug(
                "SQL pipeline emitted event",
                extra={
                    "session_id": ctx.session_id,
                    "event": event.get("event"),
                    "flow_mode": getattr(ctx, "flow_mode", None),
                },
            )
            yield event
        logger.info(
            "Completed SQL pipeline",
            extra={
                "session_id": ctx.session_id,
                "flow_mode": getattr(ctx, "flow_mode", None),
            },
        )

    async def _run_chart(pipeline: PlannerPipeline, ctx: PlannerPhaseContext, _: Dict[str, Any]) -> AsyncGenerator[Dict[str, Any], None]:
        intent = ctx.intent
        plan = ctx.plan or ctx.provisional_plan
        if not intent or not plan:
            return
        async for event in pipeline.run_chart_phase(ctx, intent=intent, plan=plan):
            yield event

    async def _run_analysis(pipeline: PlannerPipeline, ctx: PlannerPhaseContext, _: Dict[str, Any]) -> AsyncGenerator[Dict[str, Any], None]:
        async for event in pipeline.run_analysis_phase(ctx):
            yield event

    async def _run_chart_revision(pipeline: PlannerPipeline, ctx: PlannerPhaseContext, kwargs: Dict[str, Any]) -> AsyncGenerator[Dict[str, Any], None]:
        patch = kwargs.get("patch")
        if not patch:
            return
        async for event in pipeline.emit_chart_patch(
            session_id=ctx.session_id,
            patch=patch,
            reason=kwargs.get("reason"),
            source=kwargs.get("source"),
            repository=kwargs.get("repository"),
            hooks=kwargs.get("hooks"),
        ):
            yield event

    async def _run_analysis_revision(pipeline: PlannerPipeline, ctx: PlannerPhaseContext, kwargs: Dict[str, Any]) -> AsyncGenerator[Dict[str, Any], None]:
        analysis_text = kwargs.get("analysis") or kwargs.get("revision_text")
        if not analysis_text:
            return
        async for event in pipeline.emit_analysis_revision(
            session_id=ctx.session_id,
            analysis=analysis_text,
            reason=kwargs.get("reason"),
            source=kwargs.get("source"),
            repository=kwargs.get("repository"),
            hooks=kwargs.get("hooks"),
        ):
            yield event

    async def _run_web_refresh(pipeline: PlannerPipeline, ctx: PlannerPhaseContext, kwargs: Dict[str, Any]) -> AsyncGenerator[Dict[str, Any], None]:
        lane_refresh_flags = dict(getattr(ctx, "lane_refresh_required", {}) or {})
        follow_up_route = getattr(ctx, "follow_up_route", FollowUpRoute.FULL_PIPELINE)
        guardrail_payload = getattr(ctx, "follow_up_guardrail", None)
        if follow_up_route == FollowUpRoute.STOCK_ONLY or lane_refresh_flags.get("web") is False:
            web_refresh_data = {
                "lane": "web",
                "revision": True,
                "phase": "reused",
                "from_cache": True,
                "reason": kwargs.get("reason"),
                "source": kwargs.get("source"),
            }
            if guardrail_payload is not None:
                web_refresh_data["guardrail"] = (
                    sanitize_for_json(dict(guardrail_payload)) if isinstance(guardrail_payload, Mapping) else guardrail_payload
                )
            yield {
                "event": "web_refresh",
                "data": web_refresh_data,
            }
            if hasattr(ctx, "session_snapshot") and ctx.session_snapshot:
                try:
                    ctx.session_snapshot.record_tool_receipt(
                        "web_refresh",
                        {
                            "status": "skipped",
                            "reused": True,
                            "from_cache": True,
                            "lane": "web",
                        },
                    )
                except Exception:
                    pass
            return

        async for event in pipeline.refresh_web_lane(
            ctx,
            reason=kwargs.get("reason"),
            source=kwargs.get("source"),
        ):
            yield event

    async def _run_market_refresh(pipeline: PlannerPipeline, ctx: PlannerPhaseContext, kwargs: Dict[str, Any]) -> AsyncGenerator[Dict[str, Any], None]:
        lane_refresh_flags = dict(getattr(ctx, "lane_refresh_required", {}) or {})
        guardrail_payload = getattr(ctx, "follow_up_guardrail", None)
        if lane_refresh_flags.get("market") is False:
            market_refresh_data = {
                "lane": "market",
                "revision": True,
                "phase": "reused",
                "from_cache": True,
                "reason": kwargs.get("reason"),
                "source": kwargs.get("source"),
            }
            if guardrail_payload is not None:
                market_refresh_data["guardrail"] = (
                    sanitize_for_json(dict(guardrail_payload)) if isinstance(guardrail_payload, Mapping) else guardrail_payload
                )
            yield {
                "event": "market_refresh",
                "data": market_refresh_data,
            }
            if hasattr(ctx, "session_snapshot") and ctx.session_snapshot:
                try:
                    ctx.session_snapshot.record_tool_receipt(
                        "market_refresh",
                        {
                            "status": "skipped",
                            "reused": True,
                            "from_cache": True,
                            "lane": "market",
                        },
                    )
                except Exception:
                    pass
            return

        async for event in pipeline.refresh_market_lane(
            ctx,
            reason=kwargs.get("reason"),
            source=kwargs.get("source"),
        ):
            yield event

    async def _run_search_tools(
        pipeline: PlannerPipeline,
        ctx: PlannerPhaseContext,
        kwargs: Dict[str, Any],
    ) -> AsyncGenerator[Dict[str, Any], None]:
        route_hint = kwargs.get("route") or getattr(getattr(ctx, "follow_up_route", None), "value", None)
        mode_value = getattr(ctx, "flow_mode", FlowMode.DIRECT)
        results = search_tools(
            query=kwargs.get("query"),
            route=route_hint,
            entities=kwargs.get("entities"),
            mode=mode_value,
        )
        yield {
            "event": "search_tools",
            "data": {
                "tools": results.get("tools", []),
                "count": results.get("count"),
                "route": results.get("route") or route_hint,
                "mode": results.get("mode") or getattr(mode_value, "value", None),
            },
        }

    async def _run_follow_up_route(
        pipeline: PlannerPipeline,
        ctx: PlannerPhaseContext,
        kwargs: Dict[str, Any],
    ) -> AsyncGenerator[Dict[str, Any], None]:
        route_value = kwargs.get("route") or getattr(getattr(ctx, "follow_up_route", None), "value", None)
        route_value = route_value or FollowUpRoute.FULL_PIPELINE.value
        yield {
            "event": "follow_up_route",
            "data": {
                "route": route_value,
            },
        }

    async def _run_lane_decision(
        pipeline: PlannerPipeline,
        ctx: PlannerPhaseContext,
        kwargs: Dict[str, Any],
    ) -> AsyncGenerator[Dict[str, Any], None]:
        lane_value = kwargs.get("lane") or kwargs.get("lane_decision") or "narrative"
        payload = {
            "lane": lane_value,
            "revision": True,
        }
        yield {
            "event": "lane_decision",
            "data": payload,
        }

    handler_map: Dict[ToolId, PlannerToolHandler] = {
        ToolId.CLASSIFICATION: _run_classification,
        ToolId.INTENT_DETECTION: _run_intent,
        ToolId.CLARIFICATION: _run_clarification,
        ToolId.FOLLOW_UP_ROUTE: _run_follow_up_route,
        ToolId.SEARCH_TOOLS: _run_search_tools,
        ToolId.PLAN_GENERATION: _run_plan,
        ToolId.SQL_GENERATION: _run_sql,
        ToolId.CHART_GENERATION: _run_chart,
        ToolId.ANALYSIS_GENERATION: _run_analysis,
        ToolId.LANE_DECISION: _run_lane_decision,
        ToolId.CHART_REVISION: _run_chart_revision,
        ToolId.ANALYSIS_REVISION: _run_analysis_revision,
        ToolId.WEB_REFRESH: _run_web_refresh,
        ToolId.MARKET_REFRESH: _run_market_refresh,
        ToolId.SQL_REGENERATION: _run_sql,
    }

    executor_factory_map: Dict[ToolId, Callable[..., Any]] = {
        ToolId.SQL_GENERATION: lambda pipeline, ctx, **kw: create_sql_executor(
            pipeline=pipeline,
            ctx=ctx,
            registry=kw.get("registry"),
            executed=kw.get("executed", set()),
            tool_state=kw.get("tool_state"),
            run_sql_lane=kw.get("run_sql_lane", True),
        ),
        ToolId.SQL_REGENERATION: lambda pipeline, ctx, **kw: create_sql_executor(
            pipeline=pipeline,
            ctx=ctx,
            registry=kw.get("registry"),
            executed=kw.get("executed", set()),
            tool_state=kw.get("tool_state"),
            run_sql_lane=kw.get("run_sql_lane", True),
        ),
        ToolId.CHART_GENERATION: lambda pipeline, ctx, **kw: create_chart_executor(
            pipeline=pipeline,
            ctx=ctx,
            registry=kw.get("registry"),
            executed=kw.get("executed", set()),
            tool_state=kw.get("tool_state"),
            run_chart_lane=kw.get("run_chart_lane", True),
        ),
        ToolId.ANALYSIS_GENERATION: lambda pipeline, ctx, **kw: create_analysis_executor(
            pipeline=pipeline,
            ctx=ctx,
            registry=kw.get("registry"),
            executed=kw.get("executed", set()),
            tool_state=kw.get("tool_state"),
            mode_config=kw.get("mode_config"),
        ),
        ToolId.WEB_REFRESH: lambda pipeline, ctx, **kw: create_accessory_executor(
            pipeline=pipeline,
            ctx=ctx,
            lane="web",
            reason=kw.get("reason"),
            source=kw.get("source"),
        ),
        ToolId.MARKET_REFRESH: lambda pipeline, ctx, **kw: create_accessory_executor(
            pipeline=pipeline,
            ctx=ctx,
            lane="market",
            reason=kw.get("reason"),
            source=kw.get("source"),
        ),
    }

    canonical_registry = get_canonical_registry()

    for tool_id, handler in handler_map.items():
        executor_factory = executor_factory_map.get(tool_id)
        if executor_factory is not None:
            try:
                canonical_registry.bind_executor_factory(tool_id, executor_factory)
            except Exception:
                logger.debug("Failed to bind executor factory for %s", tool_id.value, exc_info=True)
        registry.register(_build_planner_definition(tool_id, handler, executor_factory=executor_factory))

    _assert_tool_parity(registry)


def _build_planner_definition(
    tool_id: ToolId,
    handler: PlannerToolHandler,
    *,
    executor_factory: Optional[Callable[..., Any]] = None,
) -> PlannerToolDefinition:
    canonical: ToolDefinition = TOOL_REGISTRY[tool_id]
    return PlannerToolDefinition(
        name=canonical.name,
        description=canonical.description,
        handler=handler,
        executor_factory=executor_factory,
        prerequisites=tuple(dep.value for dep in canonical.depends_on),
        telemetry_step=canonical.telemetry_step,
        inputs=tuple(canonical.inputs),
        outputs=tuple(canonical.outputs),
        output_artifacts=tuple(canonical.output_artifacts or canonical.outputs),
        latency_budget_ms=canonical.latency_budget_ms,
        concurrency_limit=canonical.concurrency_limit,
        parameters_schema=copy.deepcopy(dict(canonical.parameters_schema or {})),
        response_schema=copy.deepcopy(dict(canonical.response_schema or {})),
        retryable_errors=tuple(canonical.retryable_errors),
        error_severity=canonical.error_severity,
        schema_version=canonical.schema_version,
    )


def _assert_tool_parity(registry: PlannerToolRegistry) -> None:
    canonical_names = [tool_id.value for tool_id in TOOL_REGISTRY.keys()]
    registered_names = [definition.name for definition in registry.list_tools()]
    if canonical_names != registered_names:
        missing = sorted(set(canonical_names) - set(registered_names))
        extra = sorted(set(registered_names) - set(canonical_names))
        raise AssertionError(
            f"Planner tool registry drift detected (missing={missing}, extra={extra})",
        )
    for tool_id, canonical in TOOL_REGISTRY.items():
        registered = registry.get(canonical.name)
        if registered.schema_version != canonical.schema_version:
            raise AssertionError(
                f"Planner tool '{canonical.name}' schema_version mismatch: {registered.schema_version} vs {canonical.schema_version}",
            )
        registered_parameters = registered.parameters_schema or {}
        canonical_parameters = canonical.parameters_schema or {}
        if registered_parameters != canonical_parameters:
            raise AssertionError(
                f"Planner tool '{canonical.name}' parameters schema drift detected",
            )
        registered_response = registered.response_schema or {}
        canonical_response = canonical.response_schema or {}
        if registered_response != canonical_response:
            raise AssertionError(
                f"Planner tool '{canonical.name}' response schema drift detected",
            )
