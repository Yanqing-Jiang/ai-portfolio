from __future__ import annotations

import os
from typing import Any, AsyncGenerator, Callable, Dict, Optional

from .planner_executor import PlannerExecutorFlow
from .single_agent_tools import SingleAgentToolsFlow
from .single_agent_runtime_flow import SingleAgentRuntimeFlow
from .multi_agent import MultiAgentFlow
from .multi_agent_runtime_flow import MultiAgentRuntimeFlow
from .instrumentation import instrument_events

FLOW_FACTORIES: Dict[str, Callable[[], Any]] = {
    "planner-executor": PlannerExecutorFlow,
    "single-agent": SingleAgentRuntimeFlow,
    "single-agent-runtime": SingleAgentRuntimeFlow,
    "single-agent-legacy": SingleAgentToolsFlow,
    "multi-agent": MultiAgentRuntimeFlow,
    "multi-agent-runtime": MultiAgentRuntimeFlow,
    "multi-agent-legacy": MultiAgentFlow,
}

DEFAULT_FLOW = "planner-executor"

RUNTIME_FLAG_MAP: Dict[str, str] = {
    "planner": "planner-executor",
    "planner-executor": "planner-executor",
    "planner_legacy": "planner-executor",
    "single": "single-agent",
    "single-agent": "single-agent",
    "single-runtime": "single-agent",
    "single-legacy": "single-agent-legacy",
    "single-agent-legacy": "single-agent-legacy",
    "multi": "multi-agent",
    "multi-agent": "multi-agent",
    "multi-runtime": "multi-agent",
    "multi-legacy": "multi-agent-legacy",
    "multi-agent-legacy": "multi-agent-legacy",
}


def get_available_flows() -> Dict[str, str]:
    return {
        "planner-executor": "Deterministic planner/executor pipeline",
        "single-agent": "Tool-native agent runtime (Responses API)",
        "multi-agent": "Tool-native multi-agent runtime (Responses API)",
        "single-agent-legacy": "Legacy Claude single-agent wrapper",
        "multi-agent-legacy": "Legacy planner-based multi-agent flow",
    }


def _normalize_flow_name(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    normalized = value.strip().lower()
    return RUNTIME_FLAG_MAP.get(normalized, normalized)


def _get_flow_factory(name: Optional[str]) -> Callable[[], Any]:
    normalized = _normalize_flow_name(name)
    if not normalized:
        return FLOW_FACTORIES[DEFAULT_FLOW]
    return FLOW_FACTORIES.get(normalized, FLOW_FACTORIES[DEFAULT_FLOW])


def _env_flag(name: str, *, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    return default


def _resolve_flow_argument(flow: Optional[str]) -> Optional[str]:
    return _normalize_flow_name(flow)


def _resolve_env_flow() -> Optional[str]:
    runtime_override = _normalize_flow_name(os.getenv("ANALYTICS_AGENT_RUNTIME"))
    if runtime_override:
        return runtime_override
    legacy_override = _normalize_flow_name(os.getenv("ANALYTICS_FLOW_MODE"))
    return legacy_override


async def run_flow(
    flow_name: Optional[str],
    query: str,
    session_id: Optional[str] = None,
    *,
    instrument: bool = False,
    flow_label: Optional[str] = None,
) -> AsyncGenerator[Dict[str, Any], None]:
    factory = _get_flow_factory(flow_name)
    flow = factory()
    if instrument:
        label = flow_label or getattr(flow, "flow_label", flow_name or DEFAULT_FLOW)
        async for event in instrument_events(
            flow,
            query,
            session_id=session_id,
            flow_label=label,
        ):
            yield event
    else:
        async for event in flow.events(query, session_id=session_id):
            yield event


async def analytics_memory_workflow(
    query: str,
    session_id: Optional[str] = None,
    flow: Optional[str] = None,
) -> AsyncGenerator[Dict[str, Any], None]:
    explicit = _resolve_flow_argument(flow)
    fallback = _resolve_env_flow()
    selected = explicit or fallback or DEFAULT_FLOW
    should_instrument = _env_flag("ANALYTICS_MEMORY_INSTRUMENT", default=True)
    async for event in run_flow(
        selected,
        query,
        session_id=session_id,
        instrument=should_instrument,
        flow_label=selected,
    ):
        yield event
