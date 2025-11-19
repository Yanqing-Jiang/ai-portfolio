# --- Analytics Function/Class Map ---
# Class: ToolId
#   Role: Provides canonical identifiers for analytics tools shared across planner and agent flows.
#   Called from: analytics.tools.definitions.TOOL_REGISTRY, analytics.tools.definitions.run_tool_by_id
#   Invokes: enum.Enum
#   Why: Keeps tool identifiers synchronized between FlowMode.DIRECT and agent runtimes.
# Class: ToolDefinition
#   Role: Stores shared tool metadata (schemas, telemetry, dependencies) for deterministic and agentic execution paths.
#   Called from: analytics.tools.definitions.TOOL_REGISTRY, analytics.flows.pipeline_tools
#   Invokes: dataclasses.dataclass
#   Why: Ensures every flow consumes the same schema_versioned definition for each analytics tool.
# Function: run_tool_by_id
#   Role: Dispatches a tool invocation through the planner tool registry so every flow mode reuses the golden handlers.
#   Called from: Future agent orchestrators, diagnostics utilities
#   Invokes: analytics.flows.pipeline_tools.get_planner_tool_registry
#   Why: Avoids duplicating planner execution logic when other modes need to run a tool by id.
# --- End Analytics Function/Class Map ---
from __future__ import annotations

import copy
from collections import OrderedDict
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, AsyncGenerator, Dict, Mapping, Optional, Tuple, TYPE_CHECKING, Union

if TYPE_CHECKING:  # pragma: no cover - typing only
    from analytics.flows.planner_executor import PlannerPhaseContext, PlannerPipeline

__all__ = [
    "ToolDefinition",
    "ToolId",
    "TOOL_REGISTRY",
    "run_tool_by_id",
]

DEFAULT_SCHEMA_VERSION = "analytics_tool_schema/2025-11-19"
RETRYABLE_DEFAULT = ("transient_tool_error", "rate_limit", "upstream_timeout")


def _response_schema() -> Dict[str, Any]:
    """Return the shared response schema for analytics tools."""
    return {
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
    properties: Optional[Mapping[str, Any]] = None,
    *,
    required: Optional[Tuple[str, ...]] = None,
    allow_extra: bool = False,
) -> Dict[str, Any]:
    schema: Dict[str, Any] = {
        "type": "object",
        "properties": dict(properties or {}),
        "additionalProperties": allow_extra,
    }
    if required is not None:
        schema["required"] = list(required)
    return schema


class ToolId(str, Enum):
    CLASSIFICATION = "classification"
    INTENT_DETECTION = "intent_detection"
    CLARIFICATION = "clarification"
    PLAN_GENERATION = "plan_generation"
    SQL_GENERATION = "sql_generation"
    CHART_GENERATION = "chart_generation"
    ANALYSIS_GENERATION = "analysis_generation"
    CHART_REVISION = "chart_revision"
    ANALYSIS_REVISION = "analysis_revision"
    WEB_REFRESH = "web_refresh"
    MARKET_REFRESH = "market_refresh"
    SQL_REGENERATION = "sql_regeneration"


@dataclass(frozen=True)
class ToolDefinition:
    id: ToolId
    description: str
    telemetry_step: Optional[str]
    inputs: Tuple[str, ...] = field(default_factory=tuple)
    outputs: Tuple[str, ...] = field(default_factory=tuple)
    output_artifacts: Tuple[str, ...] = field(default_factory=tuple)
    latency_budget_ms: Optional[int] = None
    concurrency_limit: Optional[int] = None
    parameters_schema: Mapping[str, Any] = field(default_factory=dict)
    response_schema: Mapping[str, Any] = field(default_factory=dict)
    retryable_errors: Tuple[str, ...] = field(default_factory=tuple)
    error_severity: str = "transient"
    schema_version: str = DEFAULT_SCHEMA_VERSION
    depends_on: Tuple[ToolId, ...] = field(default_factory=tuple)

    @property
    def name(self) -> str:
        return self.id.value


def _response_schema_copy() -> Dict[str, Any]:
    return copy.deepcopy(_response_schema())


TOOL_REGISTRY: "OrderedDict[ToolId, ToolDefinition]" = OrderedDict(
    [
        (
            ToolId.CLASSIFICATION,
            ToolDefinition(
                id=ToolId.CLASSIFICATION,
                description="Run query classification and record topic metadata",
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
                            "type": ["string", "null"],
                            "description": "Optional rationale for telemetry and audits.",
                        },
                    },
                    required=("query",),
                ),
                response_schema=_response_schema_copy(),
                retryable_errors=RETRYABLE_DEFAULT,
            ),
        ),
        (
            ToolId.INTENT_DETECTION,
            ToolDefinition(
                id=ToolId.INTENT_DETECTION,
                description="Detect analytics intent and required slots",
                telemetry_step="intent_detection",
                inputs=("classification",),
                outputs=("intent",),
                output_artifacts=("intent",),
                latency_budget_ms=1500,
                concurrency_limit=1,
                depends_on=(ToolId.CLASSIFICATION,),
                parameters_schema=_schema({}, required=()),
                response_schema=_response_schema_copy(),
                retryable_errors=RETRYABLE_DEFAULT,
            ),
        ),
        (
            ToolId.CLARIFICATION,
            ToolDefinition(
                id=ToolId.CLARIFICATION,
                description="Collect missing slot answers before planning",
                telemetry_step="clarification",
                inputs=("intent",),
                outputs=("clarification",),
                output_artifacts=("clarification",),
                latency_budget_ms=1000,
                concurrency_limit=1,
                depends_on=(ToolId.INTENT_DETECTION,),
                parameters_schema=_schema(
                    {
                        "reason": {"type": "string"},
                        "ask_follow_up": {"type": "boolean"},
                        "clarification_id": {"type": "string"},
                    }
                ),
                response_schema=_response_schema_copy(),
                retryable_errors=RETRYABLE_DEFAULT,
            ),
        ),
        (
            ToolId.PLAN_GENERATION,
            ToolDefinition(
                id=ToolId.PLAN_GENERATION,
                description="Construct query plan and select template",
                telemetry_step="plan_generation",
                inputs=("clarification",),
                outputs=("plan",),
                output_artifacts=("plan",),
                latency_budget_ms=2000,
                concurrency_limit=1,
                depends_on=(ToolId.CLARIFICATION,),
                parameters_schema=_schema(
                    {
                        "reason": {"type": "string"},
                        "force_template": {"type": "string"},
                        "allow_cached_execution": {"type": "boolean"},
                    }
                ),
                response_schema=_response_schema_copy(),
                retryable_errors=RETRYABLE_DEFAULT,
            ),
        ),
        (
            ToolId.SQL_GENERATION,
            ToolDefinition(
                id=ToolId.SQL_GENERATION,
                description="Generate, validate, and execute SQL for the current plan",
                telemetry_step="sql_generation",
                inputs=("plan",),
                outputs=("sql",),
                output_artifacts=("sql_generation", "sql_execution"),
                latency_budget_ms=7000,
                concurrency_limit=1,
                depends_on=(ToolId.PLAN_GENERATION,),
                parameters_schema=_schema(
                    {
                        "reason": {"type": "string"},
                        "allow_cached_execution": {
                            "type": "boolean",
                            "description": "Permit reuse of previous execution results.",
                        },
                    }
                ),
                response_schema=_response_schema_copy(),
                retryable_errors=RETRYABLE_DEFAULT,
            ),
        ),
        (
            ToolId.CHART_GENERATION,
            ToolDefinition(
                id=ToolId.CHART_GENERATION,
                description="Design chart specification for the current dataset",
                telemetry_step="chart_generation",
                inputs=("sql",),
                outputs=("chart_spec",),
                output_artifacts=("chart",),
                latency_budget_ms=1500,
                concurrency_limit=1,
                depends_on=(ToolId.SQL_GENERATION,),
                parameters_schema=_schema(
                    {
                        "reason": {"type": "string"},
                        "chart_intent": {
                            "type": "string",
                            "description": "Override detected chart intent for experimentation.",
                        },
                    }
                ),
                response_schema=_response_schema_copy(),
                retryable_errors=RETRYABLE_DEFAULT,
            ),
        ),
        (
            ToolId.ANALYSIS_GENERATION,
            ToolDefinition(
                id=ToolId.ANALYSIS_GENERATION,
                description="Synthesize narrative analysis from dataset and chart",
                telemetry_step="analysis_generation",
                inputs=("chart_spec",),
                outputs=("analysis",),
                output_artifacts=("analysis",),
                latency_budget_ms=5000,
                concurrency_limit=1,
                depends_on=(ToolId.CHART_GENERATION,),
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
                response_schema=_response_schema_copy(),
                retryable_errors=RETRYABLE_DEFAULT,
            ),
        ),
        (
            ToolId.CHART_REVISION,
            ToolDefinition(
                id=ToolId.CHART_REVISION,
                description="Apply chart patch operations to the last saved spec",
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
                    required=("patch",),
                ),
                response_schema=_response_schema_copy(),
                retryable_errors=RETRYABLE_DEFAULT,
            ),
        ),
        (
            ToolId.ANALYSIS_REVISION,
            ToolDefinition(
                id=ToolId.ANALYSIS_REVISION,
                description="Apply narrative edits to the last saved analysis",
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
                    required=("analysis",),
                ),
                response_schema=_response_schema_copy(),
                retryable_errors=RETRYABLE_DEFAULT,
            ),
        ),
        (
            ToolId.WEB_REFRESH,
            ToolDefinition(
                id=ToolId.WEB_REFRESH,
                description="Refresh cached web research artifacts for revision lanes",
                telemetry_step="web_refresh",
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
                response_schema=_response_schema_copy(),
                retryable_errors=RETRYABLE_DEFAULT,
            ),
        ),
        (
            ToolId.MARKET_REFRESH,
            ToolDefinition(
                id=ToolId.MARKET_REFRESH,
                description="Refresh cached market data for revision lanes",
                telemetry_step="market_refresh",
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
                response_schema=_response_schema_copy(),
                retryable_errors=RETRYABLE_DEFAULT,
            ),
        ),
        (
            ToolId.SQL_REGENERATION,
            ToolDefinition(
                id=ToolId.SQL_REGENERATION,
                description="Regenerate SQL using the current plan context",
                telemetry_step="sql_regeneration",
                inputs=("plan",),
                outputs=("sql",),
                output_artifacts=("sql_generation", "sql_execution"),
                latency_budget_ms=7000,
                concurrency_limit=1,
                depends_on=(ToolId.PLAN_GENERATION,),
                parameters_schema=_schema(
                    {
                        "reason": {"type": "string"},
                        "strategy": {
                            "type": "string",
                            "description": "Planner strategy override (e.g., 'fallback_template').",
                        },
                    }
                ),
                response_schema=_response_schema_copy(),
                retryable_errors=RETRYABLE_DEFAULT,
            ),
        ),
    ]
)


async def run_tool_by_id(
    tool_id: Union[ToolId, str],
    *,
    pipeline: "PlannerPipeline",
    ctx: "PlannerPhaseContext",
    **kwargs: Any,
) -> AsyncGenerator[Dict[str, Any], None]:
    """Execute a canonical analytics tool through the planner registry."""

    from analytics.flows.pipeline_tools import get_planner_tool_registry

    normalized = tool_id.value if isinstance(tool_id, ToolId) else str(tool_id)
    registry = get_planner_tool_registry()
    async for event in registry.invoke(normalized, pipeline, ctx, **kwargs):
        yield event
