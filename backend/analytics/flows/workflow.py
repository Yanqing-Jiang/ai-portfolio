# --- Analytics Function/Class Map ---
# Function: get_available_flows
#   Role: Handles get available flows logic for analytics.flows.workflow.
#   Called from: Internal to analytics.flows.workflow
#   Invokes: Internal helpers only
#   Why: Keeps analytics.flows.workflow from duplicating get available flows behavior across flows.
# Function: _get_flow_factory
#   Role: Handles get flow factory logic for analytics.flows.workflow.
#   Called from: Internal to analytics.flows.workflow
#   Invokes: Internal helpers only
#   Why: Keeps analytics.flows.workflow from duplicating get flow factory behavior across flows.
# Function: _env_flag
#   Role: Handles env flag logic for analytics.flows.workflow.
#   Called from: Internal to analytics.flows.workflow
#   Invokes: os.getenv
#   Why: Keeps analytics.flows.workflow from duplicating env flag behavior across flows.
# Function: _agentic_revision_enabled
#   Role: Handles agentic revision enabled logic for analytics.flows.workflow.
#   Called from: Internal to analytics.flows.workflow
#   Invokes: analytics.flows.workflow._env_flag
#   Why: Keeps analytics.flows.workflow from duplicating agentic revision enabled behavior across flows.
# Function: _lane_sort_key
#   Role: Handles lane sort key logic for analytics.flows.workflow.
#   Called from: Internal to analytics.flows.workflow
#   Invokes: Internal helpers only
#   Why: Keeps analytics.flows.workflow from duplicating lane sort key behavior across flows.
# Function: _normalize_revision_lanes
#   Role: Handles normalize revision lanes logic for analytics.flows.workflow.
#   Called from: Internal to analytics.flows.workflow
#   Invokes: Internal helpers only
#   Why: Keeps analytics.flows.workflow from duplicating normalize revision lanes behavior across flows.
# Function: _baseline_ready
#   Role: Handles baseline ready logic for analytics.flows.workflow.
#   Called from: Internal to analytics.flows.workflow
#   Invokes: Internal helpers only
#   Why: Keeps analytics.flows.workflow from duplicating baseline ready behavior across flows.
# Function: _lane_available
#   Role: Handles lane available logic for analytics.flows.workflow.
#   Called from: Internal to analytics.flows.workflow
#   Invokes: Internal helpers only
#   Why: Keeps analytics.flows.workflow from duplicating lane available behavior across flows.
# Function: _revision_route_label
#   Role: Handles revision route label logic for analytics.flows.workflow.
#   Called from: Internal to analytics.flows.workflow
#   Invokes: analytics.flows.workflow._normalize_revision_lanes
#   Why: Keeps analytics.flows.workflow from duplicating revision route label behavior across flows.
# Function: _initial_revision_status
#   Role: Handles initial revision status logic for analytics.flows.workflow.
#   Called from: Internal to analytics.flows.workflow
#   Invokes: analytics.flows.workflow._normalize_revision_lanes
#   Why: Keeps analytics.flows.workflow from duplicating initial revision status behavior across flows.
# Function: _build_revision_banner
#   Role: Handles build revision banner logic for analytics.flows.workflow.
#   Called from: Internal to analytics.flows.workflow
#   Invokes: Internal helpers only
#   Why: Keeps analytics.flows.workflow from duplicating build revision banner behavior across flows.
# Function: _build_cannot_revise_banner
#   Role: Handles build cannot revise banner logic for analytics.flows.workflow.
#   Called from: Internal to analytics.flows.workflow
#   Invokes: Internal helpers only
#   Why: Keeps analytics.flows.workflow from duplicating build cannot revise banner behavior across flows.
# Function: _annotate_revision_event
#   Role: Handles annotate revision event logic for analytics.flows.workflow.
#   Called from: Internal to analytics.flows.workflow
#   Invokes: Internal helpers only
#   Why: Keeps analytics.flows.workflow from duplicating annotate revision event behavior across flows.
# Function: _annotated_lane_stream
#   Role: Handles annotated lane stream logic for analytics.flows.workflow.
#   Called from: Internal to analytics.flows.workflow
#   Invokes: analytics.flows.workflow._annotate_revision_event
#   Why: Keeps analytics.flows.workflow from duplicating annotated lane stream behavior across flows.
# Function: _run_chart_lane
#   Role: Handles run chart lane logic for analytics.flows.workflow.
#   Called from: Internal to analytics.flows.workflow
#   Invokes: analytics.flows.workflow._annotated_lane_stream, analytics.flows.instrumentation.emit_revision_lane
#   Why: Keeps analytics.flows.workflow from duplicating run chart lane behavior across flows.
# Function: _run_analysis_lane
#   Role: Handles run analysis lane logic for analytics.flows.workflow.
#   Called from: Internal to analytics.flows.workflow
#   Invokes: analytics.flows.workflow._annotated_lane_stream, analytics.flows.instrumentation.emit_revision_lane
#   Why: Keeps analytics.flows.workflow from duplicating run analysis lane behavior across flows.
# Function: _run_market_lane
#   Role: Handles run market lane logic for analytics.flows.workflow.
#   Called from: Internal to analytics.flows.workflow
#   Invokes: analytics.flows.workflow._annotated_lane_stream, analytics.flows.instrumentation.emit_revision_lane
#   Why: Keeps analytics.flows.workflow from duplicating run market lane behavior across flows.
# Function: _stream_revision_fast_path
#   Role: Handles stream revision fast path logic for analytics.flows.workflow.
#   Called from: Internal to analytics.flows.workflow
#   Invokes: analytics.flows.workflow._initial_revision_status, analytics.flows.workflow._revision_route_label, analytics.flows.workflow._build_revision_banner, uuid.uuid4, +2 more
#   Why: Keeps analytics.flows.workflow from duplicating stream revision fast path behavior across flows.
# Function: _combine_queries
#   Role: Handles combine queries logic for analytics.flows.workflow.
#   Called from: Internal to analytics.flows.workflow
#   Invokes: Internal helpers only
#   Why: Keeps analytics.flows.workflow from duplicating combine queries behavior across flows.
# Function: _sanitize_topic_value
#   Role: Handles sanitize topic value logic for analytics.flows.workflow.
#   Called from: Internal to analytics.flows.workflow
#   Invokes: Internal helpers only
#   Why: Keeps analytics.flows.workflow from duplicating sanitize topic value behavior across flows.
# Function: _extract_company_token
#   Role: Handles extract company token logic for analytics.flows.workflow.
#   Called from: Internal to analytics.flows.workflow
#   Invokes: re.findall
#   Why: Keeps analytics.flows.workflow from duplicating extract company token behavior across flows.
# Function: _make_topic_entry
#   Role: Handles make topic entry logic for analytics.flows.workflow.
#   Called from: Internal to analytics.flows.workflow
#   Invokes: analytics.flows.workflow._sanitize_topic_value
#   Why: Keeps analytics.flows.workflow from duplicating make topic entry behavior across flows.
# Function: _derive_related_queries
#   Role: Handles derive related queries logic for analytics.flows.workflow.
#   Called from: Internal to analytics.flows.workflow
#   Invokes: analytics.flows.workflow._extract_company_token
#   Why: Keeps analytics.flows.workflow from duplicating derive related queries behavior across flows.
# Function: _ensure_dual_topics
#   Role: Handles ensure dual topics logic for analytics.flows.workflow.
#   Called from: Internal to analytics.flows.workflow
#   Invokes: analytics.flows.workflow._derive_related_queries, analytics.flows.workflow._sanitize_topic_value, analytics.flows.workflow._extract_company_token, analytics.flows.workflow._make_topic_entry
#   Why: Keeps analytics.flows.workflow from duplicating ensure dual topics behavior across flows.
# Function: _append_session_message
#   Role: Handles append session message logic for analytics.flows.workflow.
#   Called from: Internal to analytics.flows.workflow
#   Invokes: Internal helpers only
#   Why: Keeps analytics.flows.workflow from duplicating append session message behavior across flows.
# Function: analytics_memory_workflow
#   Role: Handles analytics memory workflow logic for analytics.flows.workflow.
#   Called from: main, temp_run, tests.analytics.test_revision_routing
#   Invokes: analytics.flows.workflow._env_flag, analytics.flows.chart_revision.infer_chart_patch_from_query, analytics.flows.workflow._baseline_ready, analytics.routing.FollowUpClassifier, +2 more
#   Why: Keeps analytics.flows.workflow from duplicating analytics memory workflow behavior across flows.
# --- End Analytics Function/Class Map ---
from __future__ import annotations

import os
import re
import uuid
import logging
from datetime import datetime, timezone
from dataclasses import asdict
from typing import Any, AsyncGenerator, Callable, Dict, Iterable, List, Optional, Set, Mapping

from analytics.core.events import EventEmitter
from analytics.core.session_state import SessionStateSnapshot, get_session_state_repository
from analytics.core.lane_refresh import compute_lane_refresh_requirements, resolve_lane_ttls
from analytics.routing import FollowUpClassifier, FollowUpRoute
from .planner_executor import PlannerExecutorFlow
from .single_agent_tools import SingleAgentController
from .multi_agent import MultiAgentFlow
from .chart_revision import (
    infer_analysis_revision_from_query,
    infer_chart_patch_from_query,
    is_analysis_revision_query,
    is_chart_revision_query,
    MissingAnalysis,
    MissingRevisionSnapshot,
    RevisionContext,
)
from .instrumentation import emit_revision_lane, instrument_events
from .revision_directive import RevisionDirective
from analytics.services.response_search import generate_search_topics, has_search_api_key
from .sequencer import PlannerSequencer, PlannerEventBus

logger = logging.getLogger(__name__)

FLOW_FACTORIES: Dict[str, Callable[[], Any]] = {
    "planner-executor": PlannerExecutorFlow,
    "single-agent": SingleAgentController,
    "multi-agent": MultiAgentFlow,
}

DEFAULT_FLOW = "planner-executor"


_FOCUS_VARIANTS: List[tuple[str, str]] = [
    ("capital expenditure", "capital expenditure drivers"),
    ("capex", "capex outlook"),
    ("opex", "operating expense outlook"),
    ("ai", "AI infrastructure investment"),
    ("data center", "data center build-out"),
    ("supply chain", "supply chain capacity"),
    ("guidance", "management guidance update"),
    ("inventory", "inventory positioning"),
]


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


REVISION_LANE_ORDER: tuple[str, ...] = ("chart", "analysis", "market")


def _lane_sort_key(lane: str) -> int:
    try:
        return REVISION_LANE_ORDER.index(lane)
    except ValueError:
        return len(REVISION_LANE_ORDER)


def _normalize_revision_lanes(lanes: Iterable[str]) -> List[str]:
    normalized: Set[str] = set()
    for lane in lanes or []:
        if not lane:
            continue
        value = str(lane).strip().lower()
        if not value:
            continue
        if value == "stock":
            value = "market"
        normalized.add(value)
    if "analysis" in normalized and "web" not in normalized:
        normalized.add("web")
    return sorted(normalized, key=_lane_sort_key)


def _baseline_ready(snapshot: Optional[SessionStateSnapshot]) -> bool:
    if snapshot is None:
        return False
    return bool(snapshot.last_chart_spec and snapshot.last_analysis)


def _lane_available(snapshot: Optional[SessionStateSnapshot], lane: str) -> bool:
    if snapshot is None:
        return False
    analytics_cache = {}
    if isinstance(snapshot.tool_cache, dict):
        analytics_cache = snapshot.tool_cache.get("analytics") or {}
    artifacts = analytics_cache.get("artifacts") or {}
    revision_snapshot = analytics_cache.get("revision_snapshot") or {}
    lane = lane.strip().lower()
    if lane == "chart":
        return bool(snapshot.last_chart_spec or artifacts.get("chart"))
    if lane == "analysis":
        return bool(snapshot.last_analysis or artifacts.get("analysis"))
    if lane == "web":
        return bool(artifacts.get("web") or revision_snapshot.get("web_context"))
    if lane == "market":
        market_artifact = artifacts.get("market")
        stock_widget = revision_snapshot.get("stock_widget")
        return bool(market_artifact or stock_widget)
    return False

SESSION_MESSAGE_LIMIT = 20
SESSION_MESSAGE_ARCHIVE_LIMIT = 50


REVISION_BANNER_COPY: Dict[str, Dict[str, str]] = {
    "chart_revision": {
        "title": "Chart Updated",
        "message": "Reapplying the cached dataset to refresh the chart.",
    },
    "analysis_only": {
        "title": "Narrative Updated",
        "message": "Refreshing the written analysis with cached evidence.",
    },
    "market_only": {
        "title": "Market Snapshot Updated",
        "message": "Refreshing live market context while keeping charts and analysis in place.",
    },
    "mixed_revision": {
        "title": "Targeted Updates",
        "message": "Applying the requested updates without rerunning SQL or planning.",
    },
    "reuse_sql": {
        "title": "Reusing Cached Dataset",
        "message": "Skipping SQL while updating downstream components.",
    },
}


def _revision_route_label(lanes: List[str]) -> str:
    normalized = _normalize_revision_lanes(lanes)
    if not normalized:
        return "reuse_sql"
    if normalized == ["chart"]:
        return "chart_revision"
    if normalized in (["analysis"], ["analysis", "web"]):
        return "analysis_only"
    if normalized == ["market"]:
        return "market_only"
    return "mixed_revision"


def _initial_revision_status(lanes: List[str]) -> tuple[str, str]:
    normalized = _normalize_revision_lanes(lanes)
    if not normalized:
        return ("revision", "Applying cached updates")
    if normalized == ["chart"]:
        return ("chart_revision", "Applying chart update")
    if normalized in (["analysis"], ["analysis", "web"]):
        return ("analysis_revision", "Refreshing analysis")
    if normalized == ["market"]:
        return ("market_revision", "Refreshing market data")
    return ("revision", "Applying targeted updates")


def _build_revision_banner(route_label: str, lanes: List[str]) -> Dict[str, Any]:
    template = REVISION_BANNER_COPY.get(route_label, REVISION_BANNER_COPY["mixed_revision"])
    payload: Dict[str, Any] = {
        "title": template["title"],
        "message": template["message"],
        "route": route_label,
        "lanes": list(lanes),
    }
    return payload


def _build_cannot_revise_banner(lanes: List[str], missing: List[str]) -> Dict[str, Any]:
    sorted_missing = sorted(set(missing), key=_lane_sort_key)
    return {
        "title": "Cached Artifacts Missing",
        "message": "Start a new question to rebuild the necessary results.",
        "route": "cannot_revise",
        "missing_components": sorted_missing,
        "lanes": list(lanes),
    }


def _annotate_revision_event(event: Dict[str, Any], *, lane: str, revision_id: str) -> Dict[str, Any]:
    if not isinstance(event, dict):
        return {"event": "error", "data": {"error": "invalid_revision_event", "lane": lane}}
    data = event.setdefault("data", {})
    data.setdefault("lane", lane)
    data["lane"] = data.get("lane") or lane
    data["revision"] = True
    data["revision_event"] = True
    data["revision_id"] = revision_id
    return event


async def _annotated_lane_stream(
    generator: AsyncGenerator[Dict[str, Any], None],
    *,
    lane: str,
    revision_id: str,
) -> AsyncGenerator[Dict[str, Any], None]:
    async for event in generator:
        yield _annotate_revision_event(event, lane=lane, revision_id=revision_id)


async def _run_chart_lane(
    flow_instance: Any,
    *,
    query: str,
    session_id: str,
    patch: Optional[Dict[str, Any]],
    revision_id: str,
    revision_kwargs: Dict[str, Any],
) -> AsyncGenerator[Dict[str, Any], None]:
    if not patch:
        skip_event = EventEmitter.status("chart_revision", "No chart update detected")
        skip_event.setdefault("data", {})
        skip_event["data"].update(
            {
                "revision": True,
                "revision_id": revision_id,
                "lane": "chart",
                "phase": "skipped",
            }
        )
        yield skip_event
        return

    try:
        if hasattr(flow_instance, "apply_chart_revision"):
            generator = flow_instance.apply_chart_revision(
                session_id=session_id,
                patch=patch,
                query=query,
                **revision_kwargs,
            )
        elif hasattr(flow_instance, "chart_revision"):
            generator = flow_instance.chart_revision(
                query=query,
                session_id=session_id,
                patch=patch,
                **revision_kwargs,
            )
        elif hasattr(flow_instance, "emit_chart_patch"):
            generator = flow_instance.emit_chart_patch(
                session_id=session_id,
                patch=patch,
                **revision_kwargs,
            )
        else:
            raise AttributeError("Flow does not expose a chart revision helper")
        annotated = _annotated_lane_stream(generator, lane="chart", revision_id=revision_id)
        async for event in emit_revision_lane(
            flow_instance,
            lane="chart",
            generator=annotated,
            session_id=session_id,
            flow_label=getattr(flow_instance, "flow_label", None),
        ):
            yield event
    except Exception as exc:  # pragma: no cover - defensive logging
        error_event = EventEmitter.error("chart_revision", str(exc))
        error_event.setdefault("data", {})
        error_event["data"].update(
            {
                "lane": "chart",
                "revision": True,
                "revision_id": revision_id,
                "phase": "error",
            }
        )
        yield error_event


async def _run_analysis_lane(
    flow_instance: Any,
    *,
    query: str,
    session_id: str,
    requested_analysis: Optional[str],
    revision_directive: Optional[RevisionDirective],
    revision_id: str,
    snapshot: Optional[SessionStateSnapshot],
    revision_kwargs: Dict[str, Any],
) -> AsyncGenerator[Dict[str, Any], None]:
    analysis_payload = requested_analysis
    if not analysis_payload and snapshot:
        analysis_payload = snapshot.last_analysis

    try:
        if hasattr(flow_instance, "run_analysis_refresh"):
            generator = flow_instance.run_analysis_refresh(  # type: ignore[attr-defined]
                session_id=session_id,
                query=query,
                requested_focus=analysis_payload,
                revision_directive=revision_directive,
                **revision_kwargs,
            )
        elif hasattr(flow_instance, "analysis_revision"):
            generator = flow_instance.analysis_revision(
                session_id=session_id,
                analysis=analysis_payload,
                query=query,
                revision_directive=revision_directive,
                refresh_web=True,
                **revision_kwargs,
            )
        else:
            generator = flow_instance.emit_analysis_revision(
                session_id=session_id,
                analysis=analysis_payload or "",
                **revision_kwargs,
            )
        annotated = _annotated_lane_stream(generator, lane="analysis", revision_id=revision_id)
        async for event in emit_revision_lane(
            flow_instance,
            lane="analysis",
            generator=annotated,
            session_id=session_id,
            flow_label=getattr(flow_instance, "flow_label", None),
        ):
            yield event
    except Exception as exc:  # pragma: no cover - defensive logging
        error_event = EventEmitter.error("analysis_revision", str(exc))
        error_event.setdefault("data", {})
        error_event["data"].update(
            {
                "lane": "analysis",
                "revision": True,
                "revision_id": revision_id,
                "phase": "error",
            }
        )
        yield error_event


async def _run_market_lane(
    flow_instance: Any,
    *,
    query: str,
    session_id: str,
    revision_id: str,
    revision_kwargs: Dict[str, Any],
) -> AsyncGenerator[Dict[str, Any], None]:
    try:
        if hasattr(flow_instance, "refresh_market_lane"):
            generator = flow_instance.refresh_market_lane(
                session_id=session_id,
                query=query,
                **revision_kwargs,
            )
        elif hasattr(flow_instance, "run_market_refresh"):
            generator = flow_instance.run_market_refresh(
                session_id=session_id,
                query=query,
                **revision_kwargs,
            )
        else:
            status_event = EventEmitter.status("market_revision", "Market lane not supported for this flow")
            status_event.setdefault("data", {})
            status_event["data"].update(
                {
                    "lane": "market",
                    "revision": True,
                    "revision_id": revision_id,
                    "phase": "skipped",
                }
            )
            yield status_event
            return
        annotated = _annotated_lane_stream(generator, lane="market", revision_id=revision_id)
        async for event in emit_revision_lane(
            flow_instance,
            lane="market",
            generator=annotated,
            session_id=session_id,
            flow_label=getattr(flow_instance, "flow_label", None),
        ):
            yield event
    except Exception as exc:  # pragma: no cover - defensive logging
        error_event = EventEmitter.error("market_revision", str(exc))
        error_event.setdefault("data", {})
        error_event["data"].update(
            {
                "lane": "market",
                "revision": True,
                "revision_id": revision_id,
                "phase": "error",
            }
        )
        yield error_event


async def _stream_revision_fast_path(
    flow_instance: Any,
    *,
    combined_query: str,
    session_id: str,
    lanes: List[str],
    chart_patch: Optional[Dict[str, Any]],
    analysis_text: Optional[str],
    revision_directive: Optional[RevisionDirective],
    selected_flow: str,
    repository: Optional[Any],
    snapshot: Optional[SessionStateSnapshot],
    lane_refresh_required: Dict[str, bool],
) -> AsyncGenerator[Dict[str, Any], None]:
    revision_id = uuid.uuid4().hex
    status_step, status_message = _initial_revision_status(lanes)
    status_event = EventEmitter.status(status_step, status_message)
    status_event.setdefault("data", {})
    status_event["data"].update(
        {
            "flow": selected_flow,
            "session_id": session_id,
            "phase": "initial",
            "lanes": list(lanes),
            "revision": True,
            "revision_id": revision_id,
            "lane_refresh_required": dict(lane_refresh_required),
        }
    )
    yield status_event

    if revision_directive:
        rev_event = revision_directive.to_event(session_id=session_id)
    else:
        rev_event = {
            "event": "revision_request",
            "data": {
                "lanes": list(lanes),
                "source": "analytics_memory_workflow",
            },
        }
    rev_event.setdefault("data", {})
    rev_event["data"].update(
        {
            "flow": selected_flow,
            "phase": "initial",
            "revision": True,
            "revision_id": revision_id,
            "lane_refresh_required": dict(lane_refresh_required),
        }
    )
    yield rev_event

    route_label = _revision_route_label(lanes)
    banner = _build_revision_banner(route_label, lanes)
    follow_up_event = {
        "event": "follow_up_route",
        "data": {
            "route": route_label,
            "flow": selected_flow,
            "lanes": list(lanes),
            "revision": True,
            "revision_id": revision_id,
            "lane_refresh_required": dict(lane_refresh_required),
            "banner": banner,
        },
    }
    yield follow_up_event

    follow_up_route = FollowUpRoute.STOCK_ONLY if lanes == ["market"] else FollowUpRoute.REUSE_SQL
    if hasattr(flow_instance, "set_revision_targets"):
        flow_instance.set_revision_targets(lanes)
    if hasattr(flow_instance, "set_follow_up_route"):
        flow_instance.set_follow_up_route(follow_up_route)
    if hasattr(flow_instance, "prime_with_snapshot") and snapshot is not None:
        flow_instance.prime_with_snapshot(snapshot)

    revision_kwargs: Dict[str, Any] = {"reason": "revision_request", "source": "analytics_memory_workflow"}

    if "chart" in lanes:
        async for event in _run_chart_lane(
            flow_instance,
            query=combined_query,
            session_id=session_id,
            patch=chart_patch,
            revision_id=revision_id,
            revision_kwargs=revision_kwargs,
        ):
            yield event

    if "analysis" in lanes:
        async for event in _run_analysis_lane(
            flow_instance,
            query=combined_query,
            session_id=session_id,
            requested_analysis=analysis_text,
            revision_directive=revision_directive,
            revision_id=revision_id,
            snapshot=snapshot,
            revision_kwargs=revision_kwargs,
        ):
            yield event

    if "market" in lanes:
        async for event in _run_market_lane(
            flow_instance,
            query=combined_query,
            session_id=session_id,
            revision_id=revision_id,
            revision_kwargs=revision_kwargs,
        ):
            yield event

    completion_event = EventEmitter.status("revision", "Revision complete")
    completion_event.setdefault("data", {})
    completion_event["data"].update(
        {
            "flow": selected_flow,
            "session_id": session_id,
            "phase": "complete",
            "lanes": list(lanes),
            "revision": True,
            "revision_id": revision_id,
            "lane_refresh_required": dict(lane_refresh_required),
        }
    )
    yield completion_event

    if repository and snapshot:
        try:
            await repository.save(snapshot)
        except Exception:  # pragma: no cover - defensive persistence
            logger.debug("Failed to persist snapshot after revision fast path", exc_info=True)


def _combine_queries(snapshot: Optional[SessionStateSnapshot], follow_up: str) -> str:
    baseline = ""
    if snapshot and isinstance(snapshot.last_query, str):
        baseline = snapshot.last_query.strip()
    follow_up_clean = follow_up.strip()
    if not baseline:
        return follow_up_clean
    if not follow_up_clean:
        return baseline
    if follow_up_clean.lower().startswith("follow-up"):
        return f"{baseline}\n\n{follow_up_clean}"
    return f"{baseline}\n\nFollow-up request: {follow_up_clean}"


def _sanitize_topic_value(value: str, *, limit: int) -> str:
    trimmed = (value or "").strip()
    if len(trimmed) > limit:
        return trimmed[:limit].rstrip()
    return trimmed


def _extract_company_token(*texts: str) -> Optional[str]:
    ignore = {"follow", "request", "analysis", "drivers"}
    for text in texts:
        if not text:
            continue
        matches = re.findall(r"\b[A-Z][A-Za-z0-9&-]{1,}\b", text)
        for candidate in matches:
            normalized = candidate.strip()
            if len(normalized) >= 3 and normalized.lower() not in ignore:
                return normalized
    return None


def _make_topic_entry(query: str, *, label: Optional[str] = None, reason: Optional[str] = None) -> Dict[str, str]:
    sanitized_query = _sanitize_topic_value(query, limit=256)
    sanitized_label = _sanitize_topic_value(label or sanitized_query, limit=80)
    entry: Dict[str, str] = {
        "label": sanitized_label or sanitized_query,
        "query": sanitized_query,
    }
    if reason:
        entry["reason"] = reason
    return entry


def _derive_related_queries(
    base_query: str,
    *,
    reference_text: Optional[str] = None,
    company_hint: Optional[str] = None,
) -> List[str]:
    reference = (reference_text or "").lower()
    company = company_hint or _extract_company_token(reference_text or "", base_query)
    prefix = f"{company} " if company else ""
    derived: List[str] = []
    for trigger, variant in _FOCUS_VARIANTS:
        if trigger in reference:
            derived.append(f"{prefix}{variant}".strip())
    if not derived:
        derived.extend(
            [
                f"{prefix}key drivers".strip(),
                f"{prefix}industry outlook".strip(),
            ]
        )
    seen: Set[str] = set()
    unique: List[str] = []
    for query in derived:
        normalized = query.lower()
        if not normalized or normalized == base_query.lower() or normalized in seen:
            continue
        seen.add(normalized)
        unique.append(query)
    return unique


def _ensure_dual_topics(
    topics: List[Dict[str, Any]],
    *,
    topic_basis: str,
    user_query: str,
    analysis_text: Optional[str],
) -> List[Dict[str, Any]]:
    working: List[Dict[str, Any]] = [dict(item) for item in topics if isinstance(item, Mapping)]
    canonical_queries: Set[str] = {
        str(item.get("query") or "").strip().lower() for item in working if item.get("query")
    }
    reference_text = " ".join(filter(None, [analysis_text, topic_basis, user_query]))
    if not working:
        fallback_query = _sanitize_topic_value(topic_basis or user_query, limit=256)
        if fallback_query:
            working.append(_make_topic_entry(fallback_query, reason="fallback_base_topic"))
            canonical_queries.add(fallback_query.lower())
    if not working:
        return working
    if len(working) >= 2:
        return working[:5]
    base_query = working[0]["query"]
    related_queries = _derive_related_queries(
        base_query,
        reference_text=reference_text,
        company_hint=_extract_company_token(topic_basis, user_query, analysis_text or ""),
    )
    for related in related_queries:
        normalized = related.lower()
        if normalized in canonical_queries or normalized == base_query.lower():
            continue
        working.append(_make_topic_entry(related, reason="derived_from_follow_up"))
        canonical_queries.add(normalized)
        if len(working) >= 2:
            break
    if len(working) < 2:
        generic = _sanitize_topic_value(f"{base_query} market context", limit=256)
        if generic.lower() not in canonical_queries and generic.lower() != base_query.lower():
            working.append(_make_topic_entry(generic, reason="derived_generic_context"))
    return working[:5]


def _append_session_message(
    snapshot: Optional[SessionStateSnapshot],
    *,
    role: str,
    content: str,
) -> None:
    if snapshot is None:
        return
    messages = snapshot.messages
    if not isinstance(messages, list):
        snapshot.messages = []
        messages = snapshot.messages
    timestamp = datetime.now(timezone.utc).isoformat()
    entry = {
        "role": role,
        "content": content,
        "ts": timestamp,
    }
    messages.append(entry)

    overflow: List[Dict[str, Any]] = []
    while len(messages) > SESSION_MESSAGE_LIMIT:
        try:
            overflow.append(messages.pop(0))
        except IndexError:  # pragma: no cover - defensive guard
            break

    if overflow:
        tool_cache = snapshot.tool_cache
        if not isinstance(tool_cache, dict):
            tool_cache = {}
            snapshot.tool_cache = tool_cache
        agent_cache = tool_cache.get("agent")
        if not isinstance(agent_cache, dict):
            agent_cache = {}
            tool_cache["agent"] = agent_cache
        backlog = agent_cache.get("message_backlog")
        if not isinstance(backlog, list):
            backlog = []
        backlog.extend(overflow)
        if len(backlog) > SESSION_MESSAGE_ARCHIVE_LIMIT:
            backlog = backlog[-SESSION_MESSAGE_ARCHIVE_LIMIT:]
        agent_cache["message_backlog"] = backlog
    snapshot.touch()

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

    baseline_ready = _baseline_ready(snapshot)
    session_follow_up = bool(session_id and baseline_ready)

    classifier = FollowUpClassifier()
    route = classifier.classify(query, snapshot)
    detected_targets = classifier.detect_revision_targets(query, snapshot)

    chart_patch = patch_probe if chart_revision_requested else None
    analysis_text = (
        infer_analysis_revision_from_query(query) if analysis_revision_requested else None
    )
    if analysis_revision_requested and session_id:
        revision_snapshot_ready = True
        try:
            revision_ctx = await RevisionContext.load(session_id, repository=repository)
            if not isinstance(revision_ctx.last_analysis, str) or not revision_ctx.last_analysis.strip():
                revision_snapshot_ready = False
        except (MissingRevisionSnapshot, MissingAnalysis):
            revision_snapshot_ready = False
        if not revision_snapshot_ready:
            missing_lanes = ["analysis", "web"]
            banner = _build_cannot_revise_banner(missing_lanes, ["analysis"])
            banner["reason"] = "missing_analysis"
            follow_up_event = {
                "event": "follow_up_route",
                "data": {
                    "route": "cannot_revise",
                    "flow": selected,
                    "session_id": session_id,
                    "lanes": missing_lanes,
                    "lane_refresh_required": {"analysis": True, "web": True},
                    "session_follow_up": session_follow_up,
                    "banner": banner,
                },
            }
            yield follow_up_event
            _append_session_message(
                snapshot,
                role="system",
                content="Revision skipped because no prior analysis was cached for this session. Start a new question to rebuild the results.",
            )
            if repository and snapshot is not None:
                await repository.save(snapshot)
            return
    analysis_focus = bool(analysis_revision_requested or analysis_text)

    factory = _get_flow_factory(selected)
    flow_instance = factory()

    if hasattr(flow_instance, "set_session_follow_up"):
        try:
            flow_instance.set_session_follow_up(session_follow_up)
        except Exception:
            logger.exception("Failed to set session_follow_up on flow %s", selected)

    agentic_enabled = _agentic_revision_enabled(selected)

    requested_lanes: Set[str] = set()
    explicit_targets: Set[str] = set(detected_targets or set())
    if chart_patch:
        requested_lanes.add("chart")
    if analysis_focus:
        requested_lanes.update({"analysis", "web"})
        explicit_targets = {lane for lane in explicit_targets if lane not in {"analysis", "web"}}
    requested_lanes.update(explicit_targets)
    if route == FollowUpRoute.STOCK_ONLY:
        requested_lanes.add("market")
    if route == FollowUpRoute.REUSE_SQL and not requested_lanes.intersection({"chart", "analysis", "market"}):
        requested_lanes.update({"analysis", "web"})
    needs_sql_lane = "sql" in requested_lanes
    requested_lanes.discard("sql")

    explicit_revision = bool(chart_patch or analysis_focus or analysis_text)
    provisional_revision = bool(requested_lanes or explicit_revision)
    if provisional_revision:
        if requested_lanes and requested_lanes.issubset({"market"}):
            route = FollowUpRoute.STOCK_ONLY
        else:
            route = FollowUpRoute.REUSE_SQL
            if not requested_lanes.intersection({"analysis", "web", "chart", "market"}):
                requested_lanes.update({"analysis", "web"})
    revision_lanes = _normalize_revision_lanes(requested_lanes)
    should_consider_revision = bool(revision_lanes or explicit_revision)
    if route in {FollowUpRoute.REUSE_SQL, FollowUpRoute.STOCK_ONLY}:
        should_consider_revision = True
    should_take_revision = (
        session_id
        and baseline_ready
        and should_consider_revision
        and not needs_sql_lane
        and (route != FollowUpRoute.FULL_PIPELINE or explicit_revision)
    )

    lane_refresh_required: Dict[str, bool] = {}
    analysis_refresh_mode = "full"
    ttl_map = resolve_lane_ttls()
    ttl_lanes: Set[str] = set(revision_lanes)
    if analysis_focus or "analysis" in ttl_lanes:
        ttl_lanes.update({"analysis", "web"})
    if chart_patch:
        ttl_lanes.add("chart")
    if "market" in revision_lanes or route == FollowUpRoute.STOCK_ONLY:
        ttl_lanes.add("market")
    if ttl_lanes:
        lane_refresh_required = compute_lane_refresh_requirements(snapshot, ttl_lanes, ttl_map)
        if (
            not analysis_focus
            and ("analysis" in ttl_lanes or analysis_focus)
            and not lane_refresh_required.get("analysis", True)
            and not lane_refresh_required.get("web", True)
        ):
            analysis_refresh_mode = "light"
    if analysis_focus:
        lane_refresh_required.setdefault("analysis", True)
        lane_refresh_required.setdefault("web", True)
        lane_refresh_required["analysis"] = True
        lane_refresh_required["web"] = True
        if "market" not in revision_lanes:
            lane_refresh_required["market"] = False

    if hasattr(flow_instance, "set_lane_refresh_requirements"):
        try:
            flow_instance.set_lane_refresh_requirements(lane_refresh_required)
        except Exception:
            logger.exception("Failed to set lane refresh requirements on flow %s", selected)
    if hasattr(flow_instance, "set_analysis_refresh_mode"):
        try:
            flow_instance.set_analysis_refresh_mode(analysis_refresh_mode)
        except Exception:
            logger.exception("Failed to set analysis refresh mode on flow %s", selected)

    missing_lanes = [lane for lane in revision_lanes if not _lane_available(snapshot, lane)]
    if should_take_revision and missing_lanes:
        banner = _build_cannot_revise_banner(revision_lanes, missing_lanes)
        follow_up_event = {
            "event": "follow_up_route",
            "data": {
                "route": "cannot_revise",
                "flow": selected,
                "session_id": session_id,
                "lanes": revision_lanes,
                "lane_refresh_required": dict(lane_refresh_required),
                "session_follow_up": session_follow_up,
                "banner": banner,
            },
        }
        yield follow_up_event
        return

    if should_take_revision and session_id:
        directive_targets: Set[str] = set(requested_lanes)
        if "analysis" in revision_lanes:
            directive_targets.add("analysis")
            directive_targets.add("web")
        if "chart" in revision_lanes and chart_patch:
            directive_targets.add("chart")
        if snapshot is None:
            snapshot = SessionStateSnapshot(session_id=session_id)
        combined_query = _combine_queries(snapshot, query)
        search_topic_entries: List[Dict[str, Any]] = []
        needs_topics = any(lane in {"analysis", "web"} for lane in directive_targets)
        if needs_topics:
            topic_basis = (analysis_text or combined_query or query or "").strip()
            if topic_basis and has_search_api_key():
                try:
                    topic_plans = await generate_search_topics(topic_basis, session_id=session_id, min_topics=2)
                except Exception as exc:  # pragma: no cover - defensive logging
                    logger.warning("Revision topic generation failed: %s", exc)
                    topic_plans = []
                for plan in topic_plans or []:
                    if not plan or not getattr(plan, "query", None):
                        continue
                    query_value = str(plan.query).strip()
                    if not query_value:
                        continue
                    entry = {key: value for key, value in asdict(plan).items() if value is not None}
                    label_value = str(entry.get("label") or query_value).strip() or query_value
                    reason_value = entry.get("reason")
                    entry = {
                        "label": label_value,
                        "query": query_value,
                    }
                    if isinstance(reason_value, str) and reason_value.strip():
                        entry["reason"] = reason_value.strip()
                    search_topic_entries.append(entry)
            if not search_topic_entries and snapshot and isinstance(snapshot.last_revision_directive, dict):
                cached_topics = snapshot.last_revision_directive.get("search_topics") or []
                for topic in cached_topics:
                    if not isinstance(topic, dict):
                        continue
                    query_value = str(topic.get("query") or "").strip()
                    if not query_value:
                        continue
                    entry = {
                        "label": str(topic.get("label") or query_value).strip() or query_value,
                        "query": query_value,
                    }
                    reason_value = topic.get("reason")
                    if isinstance(reason_value, str) and reason_value.strip():
                        entry["reason"] = reason_value.strip()
                    search_topic_entries.append(entry)
            if not search_topic_entries and topic_basis:
                condensed = " ".join(topic_basis.split())
                if condensed:
                    search_topic_entries.append(
                        {
                            "label": condensed[:80],
                            "query": condensed[:256],
                        }
                    )
            if search_topic_entries:
                deduped_topics: List[Dict[str, Any]] = []
                seen_queries: Set[str] = set()
                for topic in search_topic_entries:
                    query_value = topic.get("query")
                    if not isinstance(query_value, str):
                        continue
                    normalized = query_value.strip().lower()
                    if not normalized or normalized in seen_queries:
                        continue
                    seen_queries.add(normalized)
                    sanitized_topic = {
                        "label": str(topic.get("label") or query_value).strip() or query_value.strip(),
                        "query": query_value.strip(),
                    }
                    reason_value = topic.get("reason")
                    if isinstance(reason_value, str):
                        reason_clean = reason_value.strip()
                        if reason_clean:
                            sanitized_topic["reason"] = reason_clean
                    deduped_topics.append(sanitized_topic)
                search_topic_entries = _ensure_dual_topics(
                    deduped_topics[:5],
                    topic_basis=topic_basis,
                    user_query=query,
                    analysis_text=analysis_text,
                )
        revision_directive = RevisionDirective.from_payload(
            raw_text=combined_query,
            targets=directive_targets or set(revision_lanes) or {"analysis"},
            requested_focus=analysis_text,
            chart_patch=chart_patch,
            agentic=bool(agentic_enabled),
            search_topics=search_topic_entries,
        )
        _append_session_message(snapshot, role="user", content=query)
        snapshot.record_revision_directive(
            revision_directive,
            metadata={
                "flow": selected,
                "route": route.value if isinstance(route, FollowUpRoute) else None,
                "revision_lanes": list(revision_lanes),
                "lane_refresh_required": dict(lane_refresh_required),
            },
        )
        if repository:
            await repository.save(snapshot)
        if hasattr(flow_instance, "set_revision_directive"):
            flow_instance.set_revision_directive(revision_directive)  # type: ignore[attr-defined]
        if hasattr(flow_instance, "prime_with_snapshot"):
            flow_instance.prime_with_snapshot(snapshot)
        async for event in _stream_revision_fast_path(
            flow_instance,
            combined_query=combined_query,
            session_id=session_id,
            lanes=revision_lanes,
            chart_patch=chart_patch,
            analysis_text=analysis_text,
            revision_directive=revision_directive,
            selected_flow=selected,
            repository=repository,
            snapshot=snapshot,
            lane_refresh_required=lane_refresh_required,
        ):
            yield event
        return

    status_step = "initializing"
    status_message = "Preparing analysis"
    if chart_revision_requested:
        status_step = "chart_revision"
        status_message = "Applying chart update"
    elif analysis_revision_requested:
        status_step = "analysis_revision"
        status_message = "Refreshing analysis"

    initial_status = EventEmitter.status(status_step, status_message)
    initial_status.setdefault("data", {})
    initial_status["data"]["flow"] = selected
    if session_id:
        initial_status["data"]["session_id"] = session_id
    initial_status["data"]["phase"] = "initial"
    yield initial_status

    revision_directive: Optional[RevisionDirective] = None

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
            if hasattr(flow_instance, "run_analysis_refresh"):
                generator = flow_instance.run_analysis_refresh(
                    query,
                    session_id=session_id,
                    requested_focus=analysis_text,
                    revision_directive=revision_directive,
                    **revision_kwargs,
                )
            else:
                generator = flow_instance.analysis_revision(
                    query,
                    session_id=session_id,
                    analysis=analysis_text,
                    revision_directive=revision_directive,
                    refresh_web=True,
                    **revision_kwargs,
                )
        elif isinstance(flow_instance, SingleAgentController):
            if hasattr(flow_instance, "run_analysis_refresh"):
                generator = flow_instance.run_analysis_refresh(
                    session_id=session_id,
                    query=query or "",
                    requested_focus=analysis_text,
                    revision_directive=revision_directive,
                    **revision_kwargs,
                )
            else:
                generator = flow_instance.analysis_revision(
                    session_id=session_id,
                    analysis=analysis_text,
                    query=query,
                    revision_directive=revision_directive,
                    refresh_web=True,
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
        # No early return here — proceed to run the selected flow with the
        # revision targets already set (analysis + web).

    if analysis_revision_requested and analysis_text and supports_agentic and has_analysis:
        # Agentic revision flows handle the refresh internally; ensure explicit
        # analysis patch still records the requested focus for history.
        revision_kwargs = {"reason": "revision_request", "source": "analytics_memory_workflow"}
        if hasattr(flow_instance, "analysis_revision"):
            generator = flow_instance.analysis_revision(
                query,
                session_id=session_id,
                analysis=analysis_text,
                revision_directive=revision_directive,
                refresh_web=True,
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
            "lanes": list(revision_lanes),
            "lane_refresh_required": dict(lane_refresh_required),
            "session_follow_up": session_follow_up,
        },
    }
    yield follow_up_event
    sequencer: Optional[PlannerSequencer] = None
    sequencer_state: Optional[Any] = None
    emit_prefill_summary: Optional[bool] = None
    if isinstance(flow_instance, SingleAgentController):
        sequencer_state = await flow_instance._prepare_sequencer_state(
            query,
            session_id=session_id,
        )
        lane_refresh_config = dict(getattr(sequencer_state.ctx, "lane_refresh_required", {}) or {})
        orchestrator = flow_instance.build_planner_orchestrator()
        sequencer = PlannerSequencer(
            orchestrator,
            lane_refresh_required=lane_refresh_config,
        )
        emit_prefill_summary = None
    elif isinstance(flow_instance, MultiAgentFlow):
        sequencer_state = await flow_instance._prepare_sequencer_state(
            query,
            session_id=session_id,
        )
        lane_refresh_config = dict(getattr(sequencer_state.ctx, "lane_refresh_required", {}) or {})
        orchestrator = flow_instance.build_planner_orchestrator()
        sequencer = PlannerSequencer(
            orchestrator,
            lane_refresh_required=lane_refresh_config,
        )
        flow_instance.set_planner_event_bus(sequencer.event_bus)
        emit_prefill_summary = None
    if should_instrument:
        label = selected
        async for event in instrument_events(
            flow_instance,
            query,
            session_id=session_id,
            flow_label=label,
            sequencer=sequencer,
            emit_prefill_summary=emit_prefill_summary,
            sequencer_state=sequencer_state,
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
        if sequencer is not None:
            stream = flow_instance.events(
                query,
                session_id=session_id,
                sequencer=sequencer,
                emit_prefill_summary=emit_prefill_summary,
                sequencer_state=sequencer_state,
            )
        else:
            stream = flow_instance.events(query, session_id=session_id)
        async for event in stream:
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
