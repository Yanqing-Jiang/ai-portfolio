from __future__ import annotations

import os
from typing import Any, AsyncGenerator, Callable, Dict, Optional

from .planner_executor import PlannerExecutorFlow
from .single_agent_tools import SingleAgentToolsFlow
from .multi_agent import MultiAgentFlow
from .instrumentation import instrument_events

FLOW_FACTORIES: Dict[str, Callable[[], Any]] = {
    "planner-executor": PlannerExecutorFlow,
    "single-agent": SingleAgentToolsFlow,
    "multi-agent": MultiAgentFlow,
}

DEFAULT_FLOW = "planner-executor"


def get_available_flows() -> Dict[str, str]:
    return {
        "planner-executor": "Deterministic planner/executor pipeline",
        "single-agent": "Single-agent, tool-call annotated workflow",
        "multi-agent": "Lightweight multi-agent coordination workflow",
    }


def _get_flow_factory(name: Optional[str]) -> Callable[[], Any]:
    if not name:
        return FLOW_FACTORIES[DEFAULT_FLOW]
    name = name.lower()
    return FLOW_FACTORIES.get(name, FLOW_FACTORIES[DEFAULT_FLOW])


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
    selected = flow or os.getenv("ANALYTICS_FLOW_MODE") or DEFAULT_FLOW
    should_instrument = _env_flag("ANALYTICS_MEMORY_INSTRUMENT", default=True)
    async for event in run_flow(
        selected,
        query,
        session_id=session_id,
        instrument=should_instrument,
        flow_label=selected,
    ):
        yield event





