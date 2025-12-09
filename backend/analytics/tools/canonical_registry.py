"""
Module: canonical_registry.py
Purpose: Single source of truth for all tool schemas across DIRECT, SINGLE_AGENT, MULTI_AGENT modes.
Called from: analytics.flows.planner_executor, analytics.flows.single_agent_tools,
             analytics.flows.multi_agent, analytics.tools.registry (adapter)
Invokes: analytics.tools.definitions.TOOL_REGISTRY, analytics.tools.definitions.ToolId
Why: Eliminates schema drift between flow modes by providing one registry that feeds all consumers.

Part of Phase 1.1 of the analytics refactor plan.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, FrozenSet, List, Mapping, Optional, Set, Tuple, TYPE_CHECKING

from .definitions import (
    DEFAULT_SCHEMA_VERSION,
    TOOL_REGISTRY,
    ToolDefinition,
    ToolId,
)

if TYPE_CHECKING:  # pragma: no cover - typing only
    from analytics.routing import FollowUpRoute

__all__ = [
    "CanonicalToolRegistry",
    "FlowMode",
    "get_canonical_registry",
    "get_tool_allowlist",
    "MANIFEST_SIZE_LIMIT_BYTES",
]


# Maximum manifest size for OpenAI function calling (safety margin under 32KB)
MANIFEST_SIZE_LIMIT_BYTES = 24576


class FlowMode(str, Enum):
    """
    Enum: FlowMode
    Role: Identifies the execution mode for tool invocations.
    Why: Different modes may have different tool availability or schema variants.
    """
    DIRECT = "direct"
    SINGLE_AGENT = "single-agent"
    MULTI_AGENT = "multi-agent"


@dataclass
class ToolSchema:
    """
    Dataclass: ToolSchema
    Role: Represents the canonical schema for a tool across all modes.
    Called from: CanonicalToolRegistry.get_tool_schema
    Why: Provides a structured representation that can be converted to OpenAI format.
    """
    tool_id: ToolId
    name: str
    description: str
    parameters_schema: Dict[str, Any]
    response_schema: Dict[str, Any]
    schema_version: str
    specialist_role: Optional[str]
    lane: str
    telemetry_step: Optional[str]
    depends_on: Tuple[ToolId, ...]
    latency_budget_ms: Optional[int]
    retryable_errors: Tuple[str, ...]
    allowed_modes: FrozenSet[FlowMode] = field(default_factory=lambda: frozenset(FlowMode))
    executor_factory: Optional[Callable[..., Any]] = None

    def to_openai_function(self) -> Dict[str, Any]:
        """
        Method: to_openai_function
        Called from: CanonicalToolRegistry.get_openai_schemas
        Why: Converts the canonical schema to OpenAI function calling format.
        """
        return {
            "type": "function",
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters_schema,
        }

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "tool_id": self.tool_id.value,
            "name": self.name,
            "description": self.description,
            "parameters_schema": self.parameters_schema,
            "response_schema": self.response_schema,
            "schema_version": self.schema_version,
            "specialist_role": self.specialist_role,
            "lane": self.lane,
            "telemetry_step": self.telemetry_step,
            "depends_on": [t.value for t in self.depends_on],
            "latency_budget_ms": self.latency_budget_ms,
            "retryable_errors": list(self.retryable_errors),
            "allowed_modes": [m.value for m in self.allowed_modes],
        }


# Route-to-tool allowlist mappings
# These define which tools are available for each follow-up route
_ROUTE_ALLOWLISTS: Dict[str, Tuple[ToolId, ...]] = {
    "full_pipeline": (
        ToolId.SEARCH_TOOLS,
        ToolId.FOLLOW_UP_ROUTE,
        ToolId.CLASSIFICATION,
        ToolId.INTENT_DETECTION,
        ToolId.CLARIFICATION,
        ToolId.PLAN_ANALYSIS,
        ToolId.LANE_DECISION,
        ToolId.PLAN_GENERATION,
        ToolId.SQL_GENERATION,
        ToolId.CHART_GENERATION,
        ToolId.ANALYSIS_GENERATION,
        ToolId.WEB_REFRESH,
        ToolId.MARKET_REFRESH,
    ),
    "reuse_sql": (
        ToolId.SEARCH_TOOLS,
        ToolId.FOLLOW_UP_ROUTE,
        ToolId.LANE_DECISION,
        ToolId.CHART_GENERATION,
        ToolId.ANALYSIS_GENERATION,
    ),
    "stock_only": (
        ToolId.SEARCH_TOOLS,
        ToolId.FOLLOW_UP_ROUTE,
        ToolId.LANE_DECISION,
        ToolId.MARKET_REFRESH,
    ),
    "chart_revision": (
        ToolId.SEARCH_TOOLS,
        ToolId.FOLLOW_UP_ROUTE,
        ToolId.LANE_DECISION,
        ToolId.CHART_REVISION,
    ),
    "analysis_revision": (
        ToolId.SEARCH_TOOLS,
        ToolId.FOLLOW_UP_ROUTE,
        ToolId.LANE_DECISION,
        ToolId.ANALYSIS_REVISION,
    ),
    "sql_regeneration": (
        ToolId.SEARCH_TOOLS,
        ToolId.FOLLOW_UP_ROUTE,
        ToolId.LANE_DECISION,
        ToolId.SQL_REGENERATION,
        ToolId.CHART_GENERATION,
        ToolId.ANALYSIS_GENERATION,
    ),
    "web_refresh": (
        ToolId.SEARCH_TOOLS,
        ToolId.FOLLOW_UP_ROUTE,
        ToolId.LANE_DECISION,
        ToolId.WEB_REFRESH,
        ToolId.ANALYSIS_GENERATION,
    ),
    "market_refresh": (
        ToolId.SEARCH_TOOLS,
        ToolId.FOLLOW_UP_ROUTE,
        ToolId.LANE_DECISION,
        ToolId.MARKET_REFRESH,
        ToolId.ANALYSIS_GENERATION,
    ),
}


class CanonicalToolRegistry:
    """
    Class: CanonicalToolRegistry
    Role: Single source of truth for all tool schemas across DIRECT, SINGLE_AGENT, MULTI_AGENT modes.
    Called from: analytics.flows.planner_executor, analytics.flows.single_agent_tools,
                 analytics.flows.multi_agent
    Invokes: analytics.tools.definitions.TOOL_REGISTRY
    Why: Eliminates schema drift between flow modes; all consumers pull from this registry.
    """

    def __init__(self):
        """Initialize the canonical registry from TOOL_REGISTRY definitions."""
        self._schemas: Dict[ToolId, ToolSchema] = {}
        self._build_from_definitions()

    def _build_from_definitions(self) -> None:
        """
        Method: _build_from_definitions
        Called from: __init__
        Invokes: TOOL_REGISTRY
        Why: Constructs ToolSchema instances from the existing TOOL_REGISTRY definitions.
        """
        all_modes = frozenset(FlowMode)
        
        for tool_id, definition in TOOL_REGISTRY.items():
            schema = ToolSchema(
                tool_id=tool_id,
                name=definition.name,
                description=definition.description,
                parameters_schema=dict(definition.parameters_schema),
                response_schema=dict(definition.response_schema),
                schema_version=definition.schema_version,
                specialist_role=definition.specialist_role,
                lane=definition.lane,
                telemetry_step=definition.telemetry_step,
                depends_on=definition.depends_on,
                latency_budget_ms=definition.latency_budget_ms,
                retryable_errors=definition.retryable_errors,
                allowed_modes=all_modes,  # All tools available in all modes by default
            )
            self._schemas[tool_id] = schema

    def bind_executor_factory(
        self,
        tool_id: ToolId,
        executor_factory: Callable[..., Any],
    ) -> None:
        """
        Method: bind_executor_factory
        Called from: analytics.flows.pipeline_tools
        Why: Attaches lane executor factories so all modes share the same implementations.
        """
        schema = self._schemas.get(tool_id)
        if schema is not None:
            schema.executor_factory = executor_factory

    def get_tool_schema(
        self,
        tool_id: ToolId,
        mode: Optional[FlowMode] = None,
    ) -> Optional[ToolSchema]:
        """
        Method: get_tool_schema
        Called from: External consumers needing tool metadata
        Why: Returns the canonical schema for a specific tool, optionally filtered by mode.
        """
        schema = self._schemas.get(tool_id)
        if schema is None:
            return None
        if mode is not None and mode not in schema.allowed_modes:
            return None
        return schema

    def get_all_schemas(self, mode: Optional[FlowMode] = None) -> List[ToolSchema]:
        """
        Method: get_all_schemas
        Called from: get_openai_schemas, diagnostics
        Why: Returns all tool schemas, optionally filtered by mode.
        """
        schemas = list(self._schemas.values())
        if mode is not None:
            schemas = [s for s in schemas if mode in s.allowed_modes]
        return schemas

    def get_tool_allowlist(self, follow_up_route: str) -> List[ToolId]:
        """
        Method: get_tool_allowlist
        Called from: SingleAgentController, MultiAgentFlow
        Why: Returns the list of tools allowed for a specific follow-up route.
        """
        return list(_ROUTE_ALLOWLISTS.get(follow_up_route, ()))

    def get_openai_schemas(
        self,
        *,
        mode: Optional[FlowMode] = None,
        tool_ids: Optional[Set[ToolId]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Method: get_openai_schemas
        Called from: AgentRuntime, SupervisorTools adapter
        Why: Returns OpenAI function calling schemas for the specified tools/mode.
        """
        schemas = self.get_all_schemas(mode=mode)
        if tool_ids is not None:
            schemas = [s for s in schemas if s.tool_id in tool_ids]
        return [s.to_openai_function() for s in schemas]

    def get_manifest_size_bytes(self, mode: Optional[FlowMode] = None) -> int:
        """
        Method: get_manifest_size_bytes
        Called from: CI tests, diagnostics
        Why: Returns the size of the JSON manifest to ensure it stays under limits.
        """
        import json
        schemas = self.get_openai_schemas(mode=mode)
        return len(json.dumps(schemas).encode("utf-8"))

    def validate_manifest_size(self, mode: Optional[FlowMode] = None) -> Tuple[bool, int]:
        """
        Method: validate_manifest_size
        Called from: CI tests
        Why: Validates that the manifest size is under the limit.
        """
        size = self.get_manifest_size_bytes(mode=mode)
        return size < MANIFEST_SIZE_LIMIT_BYTES, size

    @property
    def schema_version(self) -> str:
        """Return the current schema version."""
        return DEFAULT_SCHEMA_VERSION


# Module-level singleton
_canonical_registry: Optional[CanonicalToolRegistry] = None


def get_canonical_registry() -> CanonicalToolRegistry:
    """
    Function: get_canonical_registry
    Called from: All flow modules needing tool schemas
    Why: Returns the singleton canonical registry instance.
    """
    global _canonical_registry
    if _canonical_registry is None:
        _canonical_registry = CanonicalToolRegistry()
    return _canonical_registry


def get_tool_allowlist(follow_up_route: str) -> List[ToolId]:
    """
    Function: get_tool_allowlist
    Called from: SingleAgentController, MultiAgentFlow
    Why: Convenience function to get the tool allowlist for a route.
    """
    return get_canonical_registry().get_tool_allowlist(follow_up_route)


def reset_canonical_registry() -> None:
    """
    Function: reset_canonical_registry
    Called from: Tests
    Why: Resets the singleton for testing purposes.
    """
    global _canonical_registry
    _canonical_registry = None

