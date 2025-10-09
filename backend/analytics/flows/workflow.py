from __future__ import annotations

import os
from typing import Any, AsyncGenerator, Callable, Dict, Optional

from analytics.core.session_state import get_session_state_repository
from analytics.routing import FollowUpClassifier, FollowUpRoute
from .planner_executor import PlannerExecutorFlow
from .single_agent_tools import SingleAgentToolsFlow
from .multi_agent import MultiAgentFlow
from .chart_revision import (
    infer_analysis_revision_from_query,
    infer_chart_patch_from_query,
    is_analysis_revision_query,
    is_chart_revision_query,
)
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

    if session_id and is_chart_revision_query(query):
        patch = infer_chart_patch_from_query(query)
        if patch:
            factory = _get_flow_factory(selected)
            flow_instance = factory()
            revision_kwargs = {"reason": "revision_request", "source": "analytics_memory_workflow"}

            if isinstance(flow_instance, MultiAgentFlow):
                generator = flow_instance.chart_revision(
                    query,
                    session_id=session_id,
                    patch=patch,
                    **revision_kwargs,
                )
            elif isinstance(flow_instance, SingleAgentToolsFlow):
                generator = flow_instance.chart_revision(
                    session_id=session_id,
                    patch=patch,
                    query=query,
                    **revision_kwargs,
                )
            elif isinstance(flow_instance, PlannerExecutorFlow):
                generator = flow_instance.emit_chart_patch(
                    session_id=session_id,
                    patch=patch,
                    **revision_kwargs,
                )
            else:
                generator = flow_instance.emit_chart_patch(
                    session_id=session_id,
                    patch=patch,
                    **revision_kwargs,
                )

            async for event in generator:
                yield event
            return

    if session_id and is_analysis_revision_query(query):
        analysis_text = infer_analysis_revision_from_query(query)
        if analysis_text:
            factory = _get_flow_factory(selected)
            flow_instance = factory()
            revision_kwargs = {"reason": "revision_request", "source": "analytics_memory_workflow"}

            if isinstance(flow_instance, MultiAgentFlow):
                generator = flow_instance.analysis_revision(
                    query,
                    session_id=session_id,
                    analysis=analysis_text,
                    **revision_kwargs,
                )
            elif isinstance(flow_instance, SingleAgentToolsFlow):
                generator = flow_instance.analysis_revision(
                    session_id=session_id,
                    analysis=analysis_text,
                    query=query,
                    **revision_kwargs,
                )
            elif isinstance(flow_instance, PlannerExecutorFlow):
                generator = flow_instance.emit_analysis_revision(
                    session_id=session_id,
                    analysis=analysis_text,
                    **revision_kwargs,
                )
            else:
                generator = flow_instance.emit_analysis_revision(
                    session_id=session_id,
                    analysis=analysis_text,
                    **revision_kwargs,
                )

            async for event in generator:
                yield event
            return

    snapshot = None
    if session_id:
        repository = get_session_state_repository()
        snapshot = await repository.load(session_id)
    classifier = FollowUpClassifier()
    route = classifier.classify(query, snapshot)
    factory = _get_flow_factory(selected)
    flow_instance = factory()
    if hasattr(flow_instance, "prime_with_snapshot"):
        flow_instance.prime_with_snapshot(snapshot)
    if hasattr(flow_instance, "set_follow_up_route"):
        flow_instance.set_follow_up_route(route)
    follow_up_event = {
        "event": "follow_up_route",
        "data": {
            "route": route.value,
            "flow": selected,
        },
    }
    yield follow_up_event
    if should_instrument:
        label = selected
        async for event in instrument_events(
            flow_instance,
            query,
            session_id=session_id,
            flow_label=label,
        ):
            yield event
    else:
        async for event in flow_instance.events(query, session_id=session_id):
            yield event

