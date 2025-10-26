from __future__ import annotations

import os
import logging
from dataclasses import asdict
from typing import Any, AsyncGenerator, Callable, Dict, Optional, Set

from analytics.core.events import EventEmitter
from analytics.core.session_state import SessionStateSnapshot, get_session_state_repository
from analytics.routing import FollowUpClassifier, FollowUpRoute
from .planner_executor import PlannerExecutorFlow
from .single_agent_tools import SingleAgentController
from .multi_agent import MultiAgentFlow
from .chart_revision import (
    infer_analysis_revision_from_query,
    infer_chart_patch_from_query,
    is_analysis_revision_query,
    is_chart_revision_query,
)
from .instrumentation import instrument_events
from .revision_directive import RevisionDirective
from analytics.services.response_search import generate_search_topics, has_search_api_key

logger = logging.getLogger(__name__)

FLOW_FACTORIES: Dict[str, Callable[[], Any]] = {
    "planner-executor": PlannerExecutorFlow,
    "single-agent": SingleAgentController,
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


def _agentic_revision_enabled(flow_name: Optional[str]) -> bool:
    if not _env_flag("AGENTIC_REVISIONS_ENABLED", default=False):
        return False
    normalized = (flow_name or "").strip().lower() or DEFAULT_FLOW
    overrides = {
        "single-agent": _env_flag("AGENTIC_REVISION_SINGLE_AGENT", default=True),
        "multi-agent": _env_flag("AGENTIC_REVISION_MULTI_AGENT", default=True),
        "planner-executor": _env_flag("AGENTIC_REVISION_PLANNER_EXECUTOR", default=False),
    }
    if normalized in overrides:
        return overrides[normalized]
    env_key = "AGENTIC_REVISION_" + normalized.replace("-", "_").upper()
    return _env_flag(env_key, default=False)

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

    # Compute chart patch first; only treat as a chart revision when a concrete
    # patch is inferable. This prevents a generic mention of "chart" from
    # suppressing valid analysis revisions.
    patch_probe = infer_chart_patch_from_query(query)
    chart_revision_requested = bool(session_id and patch_probe)
    analysis_revision_requested = bool(
        session_id and not chart_revision_requested and is_analysis_revision_query(query)
    )

    repository = get_session_state_repository() if session_id else None
    snapshot: Optional[SessionStateSnapshot] = None
    if repository and session_id:
        snapshot = await repository.load(session_id)

    status_step = "initializing"
    status_message = "Preparing analysis"
    if chart_revision_requested:
        status_step = "chart_revision"
        status_message = "Applying chart update"
    elif analysis_revision_requested:
        status_step = "analysis_revision"
        status_message = "Refreshing analysis"

    initial_status = EventEmitter.status(status_step, status_message)
    initial_status["data"]["flow"] = selected
    if session_id:
        initial_status["data"]["session_id"] = session_id
    initial_status["data"]["phase"] = "initial"
    yield initial_status

    classifier = FollowUpClassifier()
    route = classifier.classify(query, snapshot)
    detected_targets = classifier.detect_revision_targets(query, snapshot)

    chart_patch = patch_probe if chart_revision_requested else None
    analysis_text = (
        infer_analysis_revision_from_query(query) if analysis_revision_requested else None
    )

    factory = _get_flow_factory(selected)
    flow_instance = factory()

    agentic_enabled = _agentic_revision_enabled(selected)
    inferred_targets: Set[str] = set(detected_targets or set())
    if chart_patch:
        inferred_targets.add("chart")
    if analysis_text:
        inferred_targets.add("analysis")
        inferred_targets.add("web")

    revision_directive: Optional[RevisionDirective] = None
    search_topic_entries = []
    if analysis_text and has_search_api_key():
        try:
            topic_plans = await generate_search_topics(analysis_text, session_id=session_id, min_topics=2)
            for plan in topic_plans:
                if plan and plan.query and plan.query.strip():
                    search_topic_entries.append(asdict(plan))
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.warning("Revision topic generation failed: %s", exc)

    if session_id and (chart_patch or analysis_text):
        directive_agentic = bool(agentic_enabled)
        revision_directive = RevisionDirective.from_payload(
            raw_text=query,
            targets=inferred_targets or {"analysis" if analysis_text else "chart"},
            requested_focus=analysis_text,
            chart_patch=chart_patch,
            agentic=directive_agentic,
            search_topics=search_topic_entries,
        )
        if snapshot is None:
            snapshot = SessionStateSnapshot(session_id=session_id)
        snapshot.record_revision_directive(
            revision_directive,
            metadata={
                "flow": selected,
                "route": route.value if isinstance(route, FollowUpRoute) else None,
            },
        )
        if repository:
            await repository.save(snapshot)

    if revision_directive and hasattr(flow_instance, "set_revision_directive"):
        flow_instance.set_revision_directive(revision_directive)  # type: ignore[attr-defined]

    # Treat presence of a revision directive as sufficient to let the active flow
    # handle the revision inside the normal pipeline (even if not explicitly
    # marked as "agentic"). This avoids short‑circuiting analysis revisions and
    # allows accessory fan‑out (e.g., concurrent web retrievers) to run.
    supports_agentic = bool(
        revision_directive and hasattr(flow_instance, "set_revision_directive")
    )

    # Always surface a revision_request event for UI/telemetry, even when not
    # running in agentic mode. This helps diagnostics when a session snapshot
    # is missing and lanes cannot be restricted yet.
    if revision_directive:
        rev_event = revision_directive.to_event(session_id=session_id)
        rev_event.setdefault("data", {})
        rev_event["data"]["flow"] = selected
        rev_event["data"]["phase"] = "initial"
        yield rev_event

    # Determine whether we can apply revisions immediately or need to defer
    has_chart = bool(getattr(snapshot, "last_chart_spec", None))
    has_analysis = bool(getattr(snapshot, "last_analysis", None))
    defer_chart_revision = bool(chart_revision_requested and not has_chart)
    defer_analysis_revision = bool(analysis_revision_requested and not has_analysis)

    if chart_revision_requested and chart_patch and not supports_agentic and has_chart:
        revision_kwargs = {"reason": "revision_request", "source": "analytics_memory_workflow"}

        if isinstance(flow_instance, MultiAgentFlow):
            generator = flow_instance.chart_revision(
                query,
                session_id=session_id,
                patch=chart_patch,
                **revision_kwargs,
            )
        elif isinstance(flow_instance, SingleAgentController):
            generator = flow_instance.chart_revision(
                session_id=session_id,
                patch=chart_patch,
                query=query,
                **revision_kwargs,
            )
        elif isinstance(flow_instance, PlannerExecutorFlow):
            generator = flow_instance.emit_chart_patch(
                session_id=session_id,
                patch=chart_patch,
                **revision_kwargs,
            )
        else:
            generator = flow_instance.emit_chart_patch(
                session_id=session_id,
                patch=chart_patch,
                **revision_kwargs,
            )

        async for event in generator:
            yield event

    if analysis_revision_requested and analysis_text and not supports_agentic and has_analysis:
        # Apply the analysis patch for audit/history, but do not return early —
        # continue into the main pipeline so accessory tools (web retrievers)
        # can run and the analysis can be regenerated using fresh context.
        revision_kwargs = {"reason": "revision_request", "source": "analytics_memory_workflow"}

        if isinstance(flow_instance, MultiAgentFlow):
            generator = flow_instance.analysis_revision(
                query,
                session_id=session_id,
                analysis=analysis_text,
                revision_directive=revision_directive,
                **revision_kwargs,
            )
        elif isinstance(flow_instance, SingleAgentController):
            generator = flow_instance.analysis_revision(
                session_id=session_id,
                analysis=analysis_text,
                query=query,
                revision_directive=revision_directive,
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
        # No early return here — proceed to run the selected flow with the
        # revision targets already set (analysis + web).

    revision_targets = detected_targets
    # If a revision directive supplied explicit targets, merge them with any
    # classifier-detected targets so planner can skip unrelated lanes.
    if revision_directive and getattr(revision_directive, "targets", None):
        merged = set(revision_targets or set()) | set(revision_directive.targets)
        revision_targets = sorted(merged)
    if session_id and revision_targets and hasattr(flow_instance, "set_revision_targets"):
        flow_instance.set_revision_targets(revision_targets)
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
        # Deferred revisions after initial build
        if defer_chart_revision and chart_patch:
            revision_kwargs = {"reason": "post_initial_build", "source": "analytics_memory_workflow"}
            if isinstance(flow_instance, MultiAgentFlow):
                gen2 = flow_instance.chart_revision(query, session_id=session_id, patch=chart_patch, **revision_kwargs)
            elif isinstance(flow_instance, SingleAgentController):
                gen2 = flow_instance.chart_revision(session_id=session_id, patch=chart_patch, query=query, **revision_kwargs)
            else:
                gen2 = flow_instance.emit_chart_patch(session_id=session_id, patch=chart_patch, **revision_kwargs)
            async for evt in gen2:
                yield evt
        if defer_analysis_revision and analysis_text:
            revision_kwargs = {"reason": "post_initial_build", "source": "analytics_memory_workflow"}
            if isinstance(flow_instance, MultiAgentFlow):
                gen3 = flow_instance.analysis_revision(query, session_id=session_id, analysis=analysis_text, revision_directive=revision_directive, **revision_kwargs)
            elif isinstance(flow_instance, SingleAgentController):
                gen3 = flow_instance.analysis_revision(session_id=session_id, analysis=analysis_text, query=query, revision_directive=revision_directive, **revision_kwargs)
            else:
                gen3 = flow_instance.emit_analysis_revision(session_id=session_id, analysis=analysis_text, **revision_kwargs)
            async for evt in gen3:
                yield evt
    else:
        async for event in flow_instance.events(query, session_id=session_id):
            yield event
        # Deferred revisions after initial build
        if defer_chart_revision and chart_patch:
            revision_kwargs = {"reason": "post_initial_build", "source": "analytics_memory_workflow"}
            if isinstance(flow_instance, MultiAgentFlow):
                gen2 = flow_instance.chart_revision(query, session_id=session_id, patch=chart_patch, **revision_kwargs)
            elif isinstance(flow_instance, SingleAgentController):
                gen2 = flow_instance.chart_revision(session_id=session_id, patch=chart_patch, query=query, **revision_kwargs)
            else:
                gen2 = flow_instance.emit_chart_patch(session_id=session_id, patch=chart_patch, **revision_kwargs)
            async for evt in gen2:
                yield evt
        if defer_analysis_revision and analysis_text:
            revision_kwargs = {"reason": "post_initial_build", "source": "analytics_memory_workflow"}
            if isinstance(flow_instance, MultiAgentFlow):
                gen3 = flow_instance.analysis_revision(query, session_id=session_id, analysis=analysis_text, revision_directive=revision_directive, **revision_kwargs)
            elif isinstance(flow_instance, SingleAgentController):
                gen3 = flow_instance.analysis_revision(session_id=session_id, analysis=analysis_text, query=query, revision_directive=revision_directive, **revision_kwargs)
            else:
                gen3 = flow_instance.emit_analysis_revision(session_id=session_id, analysis=analysis_text, **revision_kwargs)
            async for evt in gen3:
                yield evt

