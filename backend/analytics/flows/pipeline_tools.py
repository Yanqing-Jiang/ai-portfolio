from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, AsyncGenerator, Awaitable, Callable, Dict, Iterable, Optional, Sequence, Set
import logging

from .planner_executor import PlannerPipeline, PlannerPhaseContext


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
        **kwargs: Any,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        if executed is None:
            executed = set()
        if name in executed:
            return

        definition = self.get(name)
        for prerequisite in definition.prerequisites:
            async for event in self.invoke(prerequisite, pipeline, ctx, executed=executed, **kwargs):
                yield event
        executed.add(name)
        async for event in definition.handler(pipeline, ctx, dict(kwargs)):
            yield event

    def list_tools(self) -> Sequence[PlannerToolDefinition]:
        return tuple(self._tools.values())

    def describe_tools(self) -> Sequence[Dict[str, Any]]:
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
            }
            for definition in self.list_tools()
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
        async for event in pipeline.refresh_web_lane(
            ctx,
            reason=kwargs.get("reason"),
            source=kwargs.get("source"),
        ):
            yield event

    async def _run_market_refresh(pipeline: PlannerPipeline, ctx: PlannerPhaseContext, kwargs: Dict[str, Any]) -> AsyncGenerator[Dict[str, Any], None]:
        async for event in pipeline.refresh_market_lane(
            ctx,
            reason=kwargs.get("reason"),
            source=kwargs.get("source"),
        ):
            yield event

    base_response_schema: Dict[str, Any] = {
        "type": "object",
        "properties": {
            "status": {
                "type": "string",
                "enum": ["completed", "skipped", "error"],
            },
            "summary": {"type": "string"},
            "artifacts": {"type": "object"},
            "error_code": {"type": "string"},
            "reused": {"type": "boolean"},
        },
        "required": ["status"],
        "additionalProperties": True,
    }

    def _schema(
        properties: Optional[Dict[str, Any]] = None,
        *,
        required: Optional[Sequence[str]] = None,
        allow_extra: bool = False,
    ) -> Dict[str, Any]:
        schema: Dict[str, Any] = {
            "type": "object",
            "properties": properties or {},
            "additionalProperties": allow_extra,
        }
        if required:
            schema["required"] = list(required)
        return schema

    retryable_default = ("transient_tool_error", "rate_limit", "upstream_timeout")

    registry.register(
        PlannerToolDefinition(
            name="classification",
            description="Run query classification and record topic metadata",
            handler=_run_classification,
            telemetry_step="classification",
            inputs=("query",),
            outputs=("classification",),
            output_artifacts=("classification",),
            latency_budget_ms=500,
            concurrency_limit=1,
            parameters_schema=_schema(
                {
                    "query": {
                        "type": "string",
                        "description": "User query to classify; defaults to pipeline context when omitted.",
                    },
                    "reason": {
                        "type": "string",
                        "description": "Optional rationale for telemetry and audits.",
                    },
                }
            ),
            response_schema=base_response_schema,
            retryable_errors=retryable_default,
        )
    )
    registry.register(
        PlannerToolDefinition(
            name="intent_detection",
            description="Detect analytics intent and required slots",
            handler=_run_intent,
            prerequisites=("classification",),
            telemetry_step="intent_detection",
            inputs=("classification",),
            outputs=("intent",),
            output_artifacts=("intent",),
            latency_budget_ms=1500,
            concurrency_limit=1,
            parameters_schema=_schema(
                {
                    "classification": {
                        "type": "object",
                        "description": "Structured classification result to reuse instead of recomputing.",
                    },
                    "reason": {"type": "string"},
                }
            ),
            response_schema=base_response_schema,
            retryable_errors=retryable_default,
        )
    )
    registry.register(
        PlannerToolDefinition(
            name="clarification",
            description="Collect missing slot answers before planning",
            handler=_run_clarification,
            prerequisites=("intent_detection",),
            telemetry_step="clarification",
            inputs=("intent",),
            outputs=("clarifications",),
            output_artifacts=("clarification",),
            latency_budget_ms=2000,
            concurrency_limit=1,
            parameters_schema=_schema(
                {
                    "clarification_budget": {
                        "type": "integer",
                        "minimum": 1,
                        "description": "Max clarification rounds to run.",
                    },
                    "reason": {"type": "string"},
                }
            ),
            response_schema=base_response_schema,
            retryable_errors=retryable_default,
        )
    )
    registry.register(
        PlannerToolDefinition(
            name="plan_generation",
            description="Construct query plan and select template",
            handler=_run_plan,
            prerequisites=("clarification",),
            telemetry_step="plan_generation",
            inputs=("clarifications",),
            outputs=("plan",),
            output_artifacts=("plan",),
            latency_budget_ms=2000,
            concurrency_limit=1,
            parameters_schema=_schema(
                {
                    "reason": {"type": "string"},
                    "force_template": {
                        "type": "string",
                        "description": "Template identifier to force when planner should reuse a cached template.",
                    },
                }
            ),
            response_schema=base_response_schema,
            retryable_errors=retryable_default,
        )
    )
    registry.register(
        PlannerToolDefinition(
            name="sql_generation",
            description="Generate, validate, and execute SQL for the current plan",
            handler=_run_sql,
            prerequisites=("plan_generation",),
            telemetry_step="sql_generation",
            inputs=("plan",),
            outputs=("sql",),
            output_artifacts=("sql_generation", "sql_execution"),
            latency_budget_ms=7000,
            concurrency_limit=1,
            parameters_schema=_schema(
                {
                    "reason": {"type": "string"},
                    "rerun": {
                        "type": "boolean",
                        "description": "Force SQL generation even when cached receipts exist.",
                    },
                    "allow_cached_execution": {
                        "type": "boolean",
                        "description": "Permit reuse of previous execution results.",
                    },
                }
            ),
            response_schema=base_response_schema,
            retryable_errors=retryable_default,
        )
    )
    registry.register(
        PlannerToolDefinition(
            name="chart_generation",
            description="Design chart specification for the current dataset",
            handler=_run_chart,
            prerequisites=("sql_generation",),
            telemetry_step="chart_generation",
            inputs=("sql",),
            outputs=("chart_spec",),
            output_artifacts=("chart",),
            latency_budget_ms=1500,
            concurrency_limit=1,
            parameters_schema=_schema(
                {
                    "reason": {"type": "string"},
                    "chart_intent": {
                        "type": "string",
                        "description": "Override detected chart intent for experimentation.",
                    },
                }
            ),
            response_schema=base_response_schema,
            retryable_errors=retryable_default,
        )
    )
    registry.register(
        PlannerToolDefinition(
            name="analysis_generation",
            description="Synthesize narrative analysis from dataset and chart",
            handler=_run_analysis,
            prerequisites=("chart_generation",),
            telemetry_step="analysis_generation",
            inputs=("chart_spec",),
            outputs=("analysis",),
            output_artifacts=("analysis",),
            latency_budget_ms=5000,
            concurrency_limit=1,
            parameters_schema=_schema(
                {
                    "reason": {"type": "string"},
                    "include_market": {
                        "type": "boolean",
                        "description": "Indicate whether market context must be incorporated.",
                    },
                    "clarity_mode": {
                        "type": "string",
                        "description": "Optional style override for summarization.",
                    },
                }
            ),
            response_schema=base_response_schema,
            retryable_errors=retryable_default,
        )
    )
    registry.register(
        PlannerToolDefinition(
            name="chart_revision",
            description="Apply chart patch operations to the last saved spec",
            handler=_run_chart_revision,
            prerequisites=(),
            telemetry_step="chart_revision",
            inputs=("patch",),
            outputs=("chart_patch",),
            output_artifacts=("revision",),
            latency_budget_ms=800,
            concurrency_limit=2,
            parameters_schema=_schema(
                {
                    "patch": {
                        "oneOf": [{"type": "object"}, {"type": "string"}],
                        "description": "Chart patch operations to apply.",
                    },
                    "reason": {"type": "string"},
                    "source": {"type": "string"},
                },
                required=["patch"],
            ),
            response_schema=base_response_schema,
            retryable_errors=retryable_default,
        )
    )

    registry.register(
        PlannerToolDefinition(
            name="analysis_revision",
            description="Apply narrative edits to the last saved analysis",
            handler=_run_analysis_revision,
            prerequisites=(),
            telemetry_step="analysis_revision",
            inputs=("analysis",),
            outputs=("analysis",),
            output_artifacts=("revision",),
            latency_budget_ms=1200,
            concurrency_limit=2,
            parameters_schema=_schema(
                {
                    "analysis": {
                        "type": "string",
                        "description": "Revised analysis text to apply.",
                    },
                    "reason": {"type": "string"},
                    "source": {"type": "string"},
                },
                required=["analysis"],
            ),
            response_schema=base_response_schema,
            retryable_errors=retryable_default,
        )
    )

    registry.register(
        PlannerToolDefinition(
            name="web_refresh",
            description="Refresh cached web research artifacts for revision lanes",
            handler=_run_web_refresh,
            prerequisites=(),
            telemetry_step="web_refresh",
            inputs=(),
            outputs=("web_ready",),
            output_artifacts=("web",),
            latency_budget_ms=800,
            concurrency_limit=2,
            parameters_schema=_schema(
                {
                    "queries": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Optional override queries to fetch.",
                    },
                    "reason": {"type": "string"},
                    "force_live": {
                        "type": "boolean",
                        "description": "Set true to bypass cached web receipts.",
                    },
                }
            ),
            response_schema=base_response_schema,
            retryable_errors=retryable_default,
        )
    )

    registry.register(
        PlannerToolDefinition(
            name="market_refresh",
            description="Refresh cached market data for revision lanes",
            handler=_run_market_refresh,
            prerequisites=(),
            telemetry_step="market_refresh",
            inputs=(),
            outputs=("stock_ready",),
            output_artifacts=("market",),
            latency_budget_ms=800,
            concurrency_limit=2,
            parameters_schema=_schema(
                {
                    "tickers": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Tickers to refresh; defaults to session tickers.",
                    },
                    "reason": {"type": "string"},
                    "force_live": {
                        "type": "boolean",
                        "description": "Bypass cached market data when true.",
                    },
                }
            ),
            response_schema=base_response_schema,
            retryable_errors=retryable_default,
        )
    )

    registry.register(
        PlannerToolDefinition(
            name="sql_regeneration",
            description="Regenerate SQL using the current plan context",
            handler=_run_sql,
            prerequisites=("plan_generation",),
            telemetry_step="sql_regeneration",
            inputs=("plan",),
            outputs=("sql",),
            output_artifacts=("sql_generation", "sql_execution"),
            latency_budget_ms=7000,
            concurrency_limit=1,
            parameters_schema=_schema(
                {
                    "reason": {"type": "string"},
                    "strategy": {
                        "type": "string",
                        "description": "Planner strategy override (e.g., 'fallback_template').",
                    },
                }
            ),
            response_schema=base_response_schema,
            retryable_errors=retryable_default,
        )
    )

