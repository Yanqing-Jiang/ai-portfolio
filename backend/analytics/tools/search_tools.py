# --- Analytics Function/Class Map ---
# Function: search_tools
#   Role: Return canonical tool descriptions filtered by route, entities, or query substring.
#   Called from: analytics.flows.pipeline_tools._run_search_tools, analytics.flows.single_agent_tools (agent tool manifests)
#   Invokes: analytics.tools.canonical_registry.get_canonical_registry, analytics.tools.canonical_registry.get_tool_allowlist
#   Why: Enables agents to dynamically discover which tools are available without hard-coding manifests.
# --- End Analytics Function/Class Map ---
from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional

from analytics.tools.canonical_registry import FlowMode, get_canonical_registry, get_tool_allowlist
from analytics.tools.definitions import ToolId

__all__ = ["search_tools"]


def _normalize_mode(mode: Optional[Any]) -> FlowMode:
    try:
        if isinstance(mode, FlowMode):
            return mode
        if isinstance(mode, str):
            return FlowMode(mode)
    except Exception:
        pass
    return FlowMode.SINGLE_AGENT


def _filter_by_entities(schemas: List[Any], entities: Optional[Iterable[str]]) -> List[Any]:
    if not entities:
        return schemas
    hints = {str(entity).strip().lower() for entity in entities if isinstance(entity, str) and entity.strip()}
    if not hints:
        return schemas
    filtered: List[Any] = []
    for schema in schemas:
        lane = str(getattr(schema, "lane", "") or "").lower()
        specialist = str(getattr(schema, "specialist_role", "") or "").lower()
        name = str(getattr(schema, "name", "") or "").lower()
        if any(
            hint and (hint in lane or hint in specialist or hint == name)
            for hint in hints
        ):
            filtered.append(schema)
    return filtered or schemas


def _filter_by_query(schemas: List[Any], query: Optional[str]) -> List[Any]:
    if not query:
        return schemas
    needle = query.lower()
    filtered = [
        schema
        for schema in schemas
        if needle in schema.name.lower() or needle in str(schema.description or "").lower()
    ]
    return filtered or schemas


def search_tools(
    *,
    query: Optional[str] = None,
    route: Optional[str] = None,
    entities: Optional[Iterable[str]] = None,
    mode: Optional[Any] = None,
) -> Dict[str, Any]:
    """Discover available tools using the canonical registry."""

    registry = get_canonical_registry()
    flow_mode = _normalize_mode(mode)

    allowed: Optional[set[ToolId]] = None
    if route:
        try:
            allowed = set(get_tool_allowlist(route))
        except Exception:
            allowed = None

    schemas = registry.get_all_schemas(mode=flow_mode)
    if allowed:
        schemas = [schema for schema in schemas if schema.tool_id in allowed or schema.tool_id == ToolId.SEARCH_TOOLS]

    schemas = _filter_by_entities(schemas, entities)
    schemas = _filter_by_query(schemas, query)

    tools_payload: List[Dict[str, Any]] = []
    for schema in schemas:
        tools_payload.append(
            {
                "name": schema.name,
                "description": schema.description,
                "lane": schema.lane,
                "specialist_role": schema.specialist_role,
                "telemetry_step": schema.telemetry_step,
                "schema_version": schema.schema_version,
                "depends_on": [dep.value for dep in schema.depends_on],
            }
        )

    return {
        "tools": tools_payload,
        "count": len(tools_payload),
        "route": route,
        "mode": flow_mode.value,
    }
