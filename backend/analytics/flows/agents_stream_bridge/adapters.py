# --- Analytics Function/Class Map ---
# Constant: LANE_EVENT_BY_TOOL
#   Role: Map tool names to lane-ready SSE events and lane keys.
#   Called from: analytics.flows.agents_stream_bridge.core.AgentsStreamBridge._maybe_emit_lane_ready/_ensure_missing_lane_ready
#   Invokes: N/A
#   Why: Keeps Agent SDK tool completions aligned with planner lane telemetry.
# Function: agent_role_for_tool
#   Role: Derive specialist role used in agent_turn payloads.
#   Called from: analytics.flows.agents_stream_bridge.core.agent_turn_payload
#   Invokes: Internal helpers only
#   Why: Ensures agent turn events carry consistent specialist labels.
# Function: agent_turn_payload
#   Role: Build agent_turn_start/end payloads with lane/schema/cache metadata.
#   Called from: analytics.flows.agents_stream_bridge.core._record_turn_start/_record_turn_end/_ensure_agent_turn_envelope
#   Invokes: agent_role_for_tool
#   Why: Normalizes turn envelopes for UI/telemetry consumers.
# Function: merge_tool_metadata
#   Role: Combine runtime metadata with canonical tool definitions and guardrails.
#   Called from: analytics.flows.agents_stream_bridge.core._merge_tool_metadata callers
#   Invokes: DEFAULT_SCHEMA_VERSION fallback map
#   Why: Ensures tool events carry lane/specialist/schema/guardrail fields.
# Function: build_latency_guardrail
#   Role: Construct latency guardrail payloads using tool definitions and elapsed_ms.
#   Called from: analytics.flows.agents_stream_bridge.core._emit_tool_completion
#   Invokes: analytics.flows.planner_executor._evaluate_latency_guardrail
#   Why: Surfaces latency guardrail badges for slow tools in telemetry.
# --- End Analytics Function/Class Map ---
from __future__ import annotations

from typing import Any, Dict, Iterable, Mapping, Optional

from analytics.tools import DEFAULT_SCHEMA_VERSION
from analytics.flows.planner_executor import _evaluate_latency_guardrail

LANE_EVENT_BY_TOOL: Dict[str, tuple[str, str]] = {
    "sql_generation": ("sql_ready", "sql"),
    "sql_generator": ("sql_ready", "sql"),
    "sql_specialist": ("sql_ready", "sql"),
    "chart_generation": ("chart_ready", "chart"),
    "chart_revision": ("chart_ready", "chart"),
    "chart_designer": ("chart_ready", "chart"),
    "chart_specialist": ("chart_ready", "chart"),
    "analysis_generation": ("analysis_ready", "analysis"),
    "analysis_revision": ("analysis_ready", "analysis"),
    "analysis_writer": ("analysis_ready", "analysis"),
    "analysis_specialist": ("analysis_ready", "analysis"),
    "market_refresh": ("stock_ready", "market"),
    "market_snapshot": ("stock_ready", "market"),
    "stock_tracker": ("stock_ready", "market"),
    "market_specialist": ("stock_ready", "market"),
    "web_refresh": ("web_ready", "web"),
    "web_retriever": ("web_ready", "web"),
    "web_retriever_cached": ("web_ready", "web"),
    "web_retriever_live": ("web_ready", "web"),
    "web_research": ("web_ready", "web"),
    "web_specialist": ("web_ready", "web"),
    # Ensure analysis completions trigger lane readiness when emitted by AgentRuntime
    "analysis_complete": ("analysis_ready", "analysis"),
    "analysis_writer_complete": ("analysis_ready", "analysis"),
}

_FALLBACK_TOOL_METADATA: Dict[str, Dict[str, Any]] = {
    "chart_designer": {"lane": "chart", "specialist_role": "chart_designer", "schema_version": DEFAULT_SCHEMA_VERSION},
    "analysis_writer": {"lane": "analysis", "specialist_role": "analysis_specialist", "schema_version": DEFAULT_SCHEMA_VERSION},
    "agent_coordination": {"lane": "analysis", "specialist_role": "planner_agent", "schema_version": DEFAULT_SCHEMA_VERSION},
}


def _clean_dict(data: Dict[str, Any]) -> Dict[str, Any]:
    return {key: value for key, value in data.items() if value is not None}


def agent_role_for_tool(tool_name: Optional[str], metadata: Mapping[str, Any]) -> str:
    specialist_role = metadata.get("specialist_role")
    if isinstance(specialist_role, str) and specialist_role.strip():
        return specialist_role.strip()
    if isinstance(tool_name, str) and tool_name.strip():
        return tool_name.strip()
    return "planner_agent"


def agent_turn_payload(
    *,
    tool_id: Optional[str],
    tool_name: Optional[str],
    metadata: Mapping[str, Any],
    status: str,
    elapsed_ms: Optional[int] = None,
    agent_turn_id: Optional[str] = None,
) -> Dict[str, Any]:
    role = agent_role_for_tool(tool_name, metadata)
    lane = metadata.get("lane") or metadata.get("telemetry_step")
    guardrail_payload = metadata.get("guardrail")
    from_cache_flag = metadata.get("from_cache")
    if from_cache_flag is None and metadata.get("reused") is True:
        from_cache_flag = True
    payload: Dict[str, Any] = {
        "role": role,
        "status": status,
        "tool": tool_name,
        "tool_call_id": tool_id,
        "agent_turn_id": agent_turn_id or tool_id,
        "lane": lane,
        "schema_version": metadata.get("schema_version"),
        "specialist_role": metadata.get("specialist_role"),
    }
    if elapsed_ms is not None:
        payload["elapsed_ms"] = elapsed_ms
    if guardrail_payload:
        payload["guardrail"] = guardrail_payload
    if from_cache_flag is not None:
        payload["from_cache"] = bool(from_cache_flag)
    for key in ("latency_budget_ms", "output_artifacts", "concurrency_limit"):
        if metadata.get(key) is not None:
            payload[key] = metadata.get(key)
    return _clean_dict(payload)


def merge_tool_metadata(
    *,
    tool_id: Optional[str],
    tool_name: Optional[str],
    runtime_metadata: Optional[Any],
    definition_metadata: Mapping[str, Dict[str, Any]],
    guardrail_metadata: Optional[Mapping[str, Any]],
    tool_metadata_store: Dict[str, Dict[str, Any]],
) -> Dict[str, Any]:
    merged: Dict[str, Any] = {}
    if tool_id and tool_id in tool_metadata_store:
        merged.update(tool_metadata_store[tool_id])
    if isinstance(runtime_metadata, dict):
        merged.update({key: value for key, value in runtime_metadata.items() if value is not None})
    canonical = definition_metadata.get(str(tool_name)) if tool_name else None
    if canonical:
        merged.setdefault("lane", canonical.get("lane"))
        merged.setdefault("specialist_role", canonical.get("specialist_role"))
        merged.setdefault("schema_version", canonical.get("schema_version"))
        merged.setdefault("latency_budget_ms", canonical.get("latency_budget_ms"))
        merged.setdefault("concurrency_limit", canonical.get("concurrency_limit"))
        if canonical.get("output_artifacts") is not None:
            merged.setdefault("output_artifacts", canonical.get("output_artifacts"))
    if not merged:
        fallback = _FALLBACK_TOOL_METADATA.get(str(tool_name or "").strip())
        if fallback:
            merged.update(fallback)
    if guardrail_metadata:
        merged.setdefault("guardrail", dict(guardrail_metadata))
    clean = {key: value for key, value in merged.items() if value is not None}
    if tool_id:
        if clean:
            tool_metadata_store[tool_id] = clean
        else:
            tool_metadata_store.pop(tool_id, None)
    return clean


def build_latency_guardrail(
    *,
    tool_name: Optional[str],
    elapsed_ms: Optional[int],
    definitions_by_name: Mapping[str, Any],
) -> Optional[Dict[str, Any]]:
    if not tool_name or elapsed_ms is None:
        return None
    definition = definitions_by_name.get(tool_name)
    if definition is None or definition.latency_budget_ms is None:
        return None
    stats = {"p50_ms": elapsed_ms, "p95_ms": elapsed_ms, "total_ms": elapsed_ms}
    guardrail = _evaluate_latency_guardrail(
        stats,
        p50_threshold=definition.latency_budget_ms,
        p95_threshold=definition.latency_budget_ms,
    )
    if not guardrail:
        return None
    guardrail["source"] = "agent_latency_budget"
    guardrail["tool"] = tool_name
    guardrail["threshold_ms"] = definition.latency_budget_ms
    return guardrail


__all__ = [
    "LANE_EVENT_BY_TOOL",
    "agent_role_for_tool",
    "agent_turn_payload",
    "merge_tool_metadata",
    "build_latency_guardrail",
]


