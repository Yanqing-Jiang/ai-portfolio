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
# Function: _resolve_agentic_revision_flag
#   Role: Resolves whether the current flow instance is operating in agentic revision mode.
#   Called from: analytics.flows.workflow
#   Invokes: Flow/controller attributes only
#   Why: Ensures telemetry + UI events reflect the true agent runtime when env heuristics disagree.
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
# Function: _lane_readiness
#   Role: Builds a per-lane readiness map for chart, analysis, web, market, and sql artifacts.
#   Called from: analytics.flows.workflow
#   Invokes: analytics.core.session_state.chart_spec_has_numeric_payload
#   Why: Prevents revision routing from depending on a single coarse baseline flag.
# Function: _lanes_for_missing_inputs
#   Role: Maps missing analysis input components to the revision lanes they block.
#   Called from: analytics.flows.workflow
#   Invokes: None (pure helper)
#   Why: Keeps banner + telemetry logic consistent when analysis inputs manifest is incomplete.
# Function: _build_revision_inputs_plan
#   Role: Builds the `{lane, web}` revision plan using Gemini hints plus manifest readiness.
#   Called from: analytics.flows.workflow
#   Invokes: analytics.services.revision_focus.RevisionQuestionBundle.to_dict
#   Why: Centralizes how revision lanes choose between chart vs narrative while coordinating web refreshes.
# Function: _build_web_topic_branches
#   Role: Builds structured topic-branch payloads for Gemini topic telemetry events.
#   Called from: analytics.flows.workflow._stream_revision_fast_path
#   Invokes: analytics.services.revision_focus.RevisionQuestionBundle accessors
#   Why: Keeps web topic progress SSE events consistent between pending and ready transitions.
# Function: _suppress_fresh_pipeline_latch
#   Role: Tells PlannerExecutorFlow instances to stop emitting `fresh_*` events once agentic revisions begin.
#   Called from: analytics.flows.workflow._stream_revision_fast_path
#   Invokes: Flow/controller suppressor hooks only
#   Why: Prevents stale fresh-run telemetry from replaying after an agentic revision request.
# Function: _requires_revision_directive
#   Role: Determines when revision lanes must force a directive so accessory lanes refresh.
#   Called from: analytics.flows.workflow
#   Invokes: None (pure helper)
#   Why: Keeps analytics.flows.workflow from duplicating lane inspection logic before forcing directives.
# Function: _synthesize_minimal_revision_directive
#   Role: Synthesizes a fallback RevisionDirective with search topics when accessories must refresh.
#   Called from: analytics.flows.workflow
#   Invokes: analytics.flows.workflow._normalize_revision_lanes, analytics.flows.workflow._make_topic_entry, analytics.flows.workflow._ensure_dual_topics
#   Why: Keeps analytics.flows.workflow from duplicating forced refresh directive construction across execution paths.
# Function: _extract_revision_inputs_outcome
#   Role: Extracts the `{lane, web}` outcome emitted by revision-aware flows.
#   Called from: analytics.flows.workflow
#   Invokes: Flow-provided getters only
#   Why: Keeps analytics.flows.workflow decoupled from controller-specific bookkeeping for revision inputs.
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
#   Role: Streams the revision fast path, including Gemini question derivation and the new follow-up routing.
#   Called from: Internal to analytics.flows.workflow
#   Invokes: analytics.services.revision_focus.derive_revision_questions, analytics.services.revision_focus.cache_revision_questions, analytics.flows.workflow._build_revision_banner, uuid.uuid4, +2 more
#   Why: Ensures plan metadata, SSE payloads, and telemetry stay in sync when revisions bypass the full pipeline.
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
# Function: _parse_snapshot_timestamp
#   Role: Normalizes ISO8601 timestamps from session snapshots into timezone-aware datetime objects.
#   Called from: analytics.flows.workflow
#   Invokes: datetime.fromisoformat
#   Why: Prevents idle timeout logic from duplicating timestamp parsing across workflows.
# Function: _session_idle_expired
#   Role: Determines whether a session snapshot has exceeded the 30-minute idle timeout for agent reuse.
#   Called from: analytics.flows.workflow
#   Invokes: analytics.flows.workflow._parse_snapshot_timestamp, datetime.now
#   Why: Keeps analytics.flows.workflow from duplicating idle timeout logic when aligning agent sessions.
# Function: _hydrate_inputs_manifest
#   Role: Rebuilds and persists the analysis inputs manifest plus receipts before revision routing begins.
#   Called from: analytics.flows.workflow
#   Invokes: analytics.core.session_state.SessionStateSnapshot.ensure_analysis_lane_receipts, analytics.core.session_state.SessionStateSnapshot.refresh_analysis_inputs_manifest
#   Why: Prevents revision routing from acting on stale manifest data when receipts already exist.
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
from analytics.core.session_state import (
    SessionStateRepository,
    SessionStateSnapshot,
    chart_spec_has_numeric_payload,
    get_session_state_repository,
)
from analytics.core.lane_refresh import compute_lane_refresh_requirements, resolve_lane_ttls
from analytics.core.telemetry import analysis_inputs_missing
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
from analytics.services.revision_focus import (
    RevisionQuestionBundle,
    cache_revision_questions,
    derive_revision_questions,
)
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


def _resolve_agentic_revision_flag(
    flow_instance: Any,
    prefer_agentic_revision: bool,
    revision_directive: Optional[RevisionDirective],
) -> bool:
    """Determine whether the active flow is operating in agentic revision mode."""
    if prefer_agentic_revision:
        return True
    if revision_directive is not None:
        return True
    flow_flags = (
        getattr(flow_instance, "_agentic_revision_mode", False),
        getattr(flow_instance, "agentic_revision_mode", False),
    )
    if any(flow_flags):
        return True
    planner = getattr(flow_instance, "_planner", None)
    if planner:
        planner_flags = (
            getattr(planner, "_agentic_revision_mode", False),
            getattr(planner, "agentic_revision_mode", False),
        )
        if any(planner_flags):
            return True
    return False


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


def _baseline_ready(
    snapshot: Optional[SessionStateSnapshot],
    *,
    lanes: Optional[Iterable[str]] = None,
    lane_readiness: Optional[Mapping[str, bool]] = None,
) -> bool:
    if snapshot is None:
        return False
    readiness_map = dict(lane_readiness or _lane_readiness(snapshot))
    if lanes:
        normalized = {
            str(lane).strip().lower()
            for lane in lanes
            if isinstance(lane, str) and lane.strip()
        }
        if not normalized:
            return any(readiness_map.values())
        return all(readiness_map.get(lane, False) for lane in normalized)
    return any(readiness_map.values())


def _lane_available(
    snapshot: Optional[SessionStateSnapshot],
    lane: str,
    lane_readiness: Optional[Mapping[str, bool]] = None,
) -> bool:
    if snapshot is None:
        return False
    readiness_map = lane_readiness or _lane_readiness(snapshot)
    normalized = str(lane or "").strip().lower()
    if not normalized:
        return False
    if normalized == "stock":
        normalized = "market"
    return bool(readiness_map.get(normalized, False))


def _lane_readiness(snapshot: Optional[SessionStateSnapshot]) -> Dict[str, bool]:
    readiness = {"sql": False, "chart": False, "analysis": False, "web": False, "market": False}
    if snapshot is None:
        return readiness
    analytics_cache: Mapping[str, Any] = {}
    artifacts: Mapping[str, Any] = {}
    revision_snapshot: Mapping[str, Any] = {}
    if isinstance(snapshot.tool_cache, dict):
        analytics_cache = snapshot.tool_cache.get("analytics") or {}
    if isinstance(analytics_cache, Mapping):
        artifacts = analytics_cache.get("artifacts") or {}
        revision_snapshot = analytics_cache.get("revision_snapshot") or {}
        if not isinstance(artifacts, Mapping):
            artifacts = {}
        if not isinstance(revision_snapshot, Mapping):
            revision_snapshot = {}

    def _analysis_ready(payload: Any) -> bool:
        if isinstance(payload, Mapping):
            for key in ("analysis_text", "analysis"):
                text_value = payload.get(key)
                if isinstance(text_value, str) and text_value.strip():
                    return True
        if isinstance(payload, str) and payload.strip():
            return True
        return False

    def _web_ready(payload: Any) -> bool:
        if isinstance(payload, Mapping):
            summary = payload.get("summary") or payload.get("analysis")
            if isinstance(summary, str) and summary.strip():
                return True
            snippets = payload.get("snippets") or payload.get("documents") or payload.get("articles")
            if isinstance(snippets, Mapping):
                snippets = list(snippets.values())
            if isinstance(snippets, (list, tuple)) and any(snippets):
                return True
        return False

    def _market_ready(payload: Any) -> bool:
        if isinstance(payload, Mapping):
            if payload.get("snapshot") or payload.get("stocks") or payload.get("series"):
                return True
        return False

    analysis_payload = snapshot.last_analysis
    readiness["analysis"] = bool(
        _analysis_ready(analysis_payload)
        or _analysis_ready(artifacts.get("analysis"))
        or _analysis_ready(revision_snapshot.get("analysis"))
    )
    chart_candidates: List[Mapping[str, Any]] = []
    if isinstance(snapshot.last_chart_spec, Mapping):
        chart_candidates.append(snapshot.last_chart_spec)
    chart_artifact = artifacts.get("chart")
    if isinstance(chart_artifact, Mapping):
        if isinstance(chart_artifact.get("chart_spec"), Mapping):
            chart_candidates.append(chart_artifact["chart_spec"])
        if isinstance(chart_artifact.get("spec"), Mapping):
            chart_candidates.append(chart_artifact["spec"])
        if not chart_candidates:
            chart_candidates.append(chart_artifact)
    revision_chart = revision_snapshot.get("chart_spec")
    if isinstance(revision_chart, Mapping):
        chart_candidates.append(revision_chart)
    readiness["chart"] = any(chart_spec_has_numeric_payload(candidate) for candidate in chart_candidates)
    sql_artifact = artifacts.get("sql_generation") if isinstance(artifacts, Mapping) else None
    readiness["sql"] = bool(
        snapshot.last_sql
        or (isinstance(sql_artifact, Mapping) and sql_artifact.get("sql"))
    )
    readiness["web"] = bool(
        _web_ready(artifacts.get("web"))
        or _web_ready(revision_snapshot.get("web_context"))
    )
    readiness["market"] = bool(
        _market_ready(artifacts.get("market"))
        or revision_snapshot.get("stock_widget")
    )
    return readiness


def _lanes_for_missing_inputs(missing_components: Iterable[str]) -> List[str]:
    mapping = {
        "sql": ["analysis", "web"],
        "dataset_preview": ["analysis", "web"],
        "market": ["market"],
        "web": ["web"],
    }
    lanes: List[str] = []
    for component in missing_components or []:
        for lane in mapping.get(component, []):
            if lane not in lanes:
                lanes.append(lane)
    return lanes


def _build_revision_inputs_plan(
    lane_readiness: Mapping[str, bool],
    lane_refresh_required: Mapping[str, bool],
    missing_components: Iterable[str],
    *,
    question_bundle: Optional[RevisionQuestionBundle],
    revision_lanes: Iterable[str],
) -> Dict[str, str]:
    missing_set = {
        str(component or "").strip().lower()
        for component in (missing_components or [])
        if isinstance(component, str) and component.strip()
    }
    normalized_lanes = set(_normalize_revision_lanes(revision_lanes))
    chart_ready = lane_readiness.get("chart", False)
    narrative_ready = lane_readiness.get("analysis", False)

    def _chart_hint_from_bundle(bundle: RevisionQuestionBundle) -> bool:
        focus = (bundle.keyword_focus or "").lower()
        industry = (bundle.industry_question or "").lower()
        chart_tokens = ("chart", "visual", "plot", "graph", "trend", "line", "bar", "series", "metric")
        return any(token in industry for token in chart_tokens) or any(token in focus for token in chart_tokens)

    lane_choice = "narrative"
    if normalized_lanes == {"chart"} or (normalized_lanes == ["chart"]):
        lane_choice = "chart"
    elif "chart" in normalized_lanes and "analysis" not in normalized_lanes:
        lane_choice = "chart"
    elif "analysis" in normalized_lanes or "web" in normalized_lanes:
        lane_choice = "narrative"
    elif "chart" in normalized_lanes:
        lane_choice = "chart"

    if question_bundle:
        lane_choice = "chart" if _chart_hint_from_bundle(question_bundle) else "narrative"

    if lane_choice == "chart" and not chart_ready and narrative_ready:
        lane_choice = "narrative"
    elif lane_choice == "narrative" and not narrative_ready and chart_ready:
        lane_choice = "chart"

    web_refresh = (
        missing_set.intersection({"web"})
        or lane_refresh_required.get("web")
        or False
    )
    plan: Dict[str, str] = {
        "lane": lane_choice if lane_choice in {"chart", "narrative"} else "narrative",
        "web": "refresh" if web_refresh else "reuse",
    }
    if question_bundle:
        plan["questions"] = question_bundle.to_dict()
    return plan


def _build_web_topic_branches(
    bundle: Optional[RevisionQuestionBundle],
    *,
    status: str,
) -> List[Dict[str, Any]]:
    definitions = (
        ("user_question", "User Question", "user"),
        ("industry_question", "Industry Question", "industry"),
    )
    branches: List[Dict[str, Any]] = []
    for key, label, question_kind in definitions:
        question_value = getattr(bundle, key, None) if bundle else None
        if bundle is None or (isinstance(question_value, str) and question_value.strip()):
            entry: Dict[str, Any] = {
                "id": key,
                "label": label,
                "question_kind": question_kind,
                "status": status,
            }
            if isinstance(question_value, str) and question_value.strip():
                entry["summary"] = question_value.strip()
            branches.append(entry)
    return branches


def _suppress_fresh_pipeline_latch(flow_instance: Any) -> None:
    targets = [flow_instance]
    planner = getattr(flow_instance, "_planner", None)
    if planner:
        targets.append(planner)
    for target in targets:
        suppress_fn = getattr(target, "suppress_fresh_pipeline_events", None)
        if callable(suppress_fn):
            try:
                suppress_fn()
            except Exception:
                logger.debug("Failed to suppress fresh pipeline events", exc_info=True)


def _requires_revision_directive(lanes: Iterable[str]) -> bool:
    for lane in lanes or []:
        normalized = str(lane or "").strip().lower()
        if normalized in {"analysis", "web"}:
            return True
    return False


def _synthesize_minimal_revision_directive(
    *,
    query: Optional[str],
    analysis_text: Optional[str],
    chart_patch: Optional[Dict[str, Any]],
    lanes: Iterable[str],
    prefer_agentic_revision: bool,
) -> Optional[RevisionDirective]:
    if not _requires_revision_directive(lanes):
        return None
    normalized_targets = set(_normalize_revision_lanes(lanes))
    if not normalized_targets:
        normalized_targets = {"analysis", "web"}
    elif normalized_targets.intersection({"analysis", "web"}):
        normalized_targets.update({"analysis", "web"})
    condensed_basis = " ".join((analysis_text or query or "").split())
    topic_basis = condensed_basis or (query or "")
    sanitized_query = _sanitize_topic_value(topic_basis, limit=256) if topic_basis else ""
    sanitized_label = _sanitize_topic_value(topic_basis, limit=80) if topic_basis else ""
    search_topics: List[Dict[str, Any]] = []
    if topic_basis:
        seed_entry = _make_topic_entry(
            sanitized_query or topic_basis[:256],
            label=sanitized_label or topic_basis[:80],
            reason="forced_refresh_topic",
        )
        search_topics = _ensure_dual_topics(
            [seed_entry],
            topic_basis=topic_basis,
            user_query=query or "",
            analysis_text=analysis_text,
        )
    raw_text = (analysis_text or query or topic_basis or "").strip()
    return RevisionDirective.from_payload(
        raw_text=raw_text,
        targets=sorted(normalized_targets),
        requested_focus=analysis_text,
        chart_patch=chart_patch,
        agentic=bool(prefer_agentic_revision),
        search_topics=search_topics,
    )


def _extract_revision_inputs_outcome(flow_instance: Any) -> Optional[Dict[str, str]]:
    getter = getattr(flow_instance, "get_revision_inputs_outcome", None)
    if getter is None:
        return None
    try:
        outcome = getter()
    except Exception:  # pragma: no cover - defensive guard
        return None
    if not isinstance(outcome, Mapping):
        return None
    normalized: Dict[str, str] = {}
    lane_value = outcome.get("lane")
    if isinstance(lane_value, str) and lane_value.strip():
        normalized["lane"] = lane_value.strip().lower()
    web_value = outcome.get("web")
    if isinstance(web_value, str) and web_value.strip():
        normalized["web"] = web_value.strip().lower()
    return normalized or None

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
    snapshot: Optional[SessionStateSnapshot],
) -> AsyncGenerator[Dict[str, Any], None]:
    missing_chart_cache = not (
        snapshot
        and isinstance(getattr(snapshot, "last_chart_spec", None), dict)
        and snapshot.last_chart_spec
    )
    if missing_chart_cache:
        logger.warning(
            "snapshot_missing",
            extra={"lane": "chart", "session_id": session_id, "reason": "missing_chart_spec"},
        )
    if missing_chart_cache:
        warning_event = EventEmitter.status(
            "snapshot_missing",
            "Chart snapshot unavailable; rebuilding lane.",
        )
        warning_event.setdefault("data", {})
        warning_event["data"].update(
            {
                "lane": "chart",
                "revision": True,
                "revision_id": revision_id,
                "session_id": session_id,
            }
        )
        yield warning_event

    if not patch:
        skip_event = EventEmitter.status("chart_revision", "No chart update detected")
        skip_event.setdefault("data", {})
        skip_event["data"].update(
            {
                "revision": True,
                "revision_id": revision_id,
                "lane": "chart",
                "phase": "skipped",
                "reason": "snapshot_missing" if missing_chart_cache else "no_patch",
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
    revision_inputs_plan: Optional[Dict[str, str]] = None,
) -> AsyncGenerator[Dict[str, Any], None]:
    analysis_payload = requested_analysis
    if not analysis_payload and snapshot:
        analysis_payload = snapshot.last_analysis

    if not analysis_payload:
        logger.warning(
            "snapshot_missing",
            extra={"lane": "analysis", "session_id": session_id, "reason": "missing_analysis_snapshot"},
        )
        warning_event = EventEmitter.status(
            "snapshot_missing",
            "Analysis snapshot unavailable; rebuilding lane.",
        )
        warning_event.setdefault("data", {})
        warning_event["data"].update(
            {
                "lane": "analysis",
                "revision": True,
                "revision_id": revision_id,
                "session_id": session_id,
            }
        )
        yield warning_event

    try:
        if hasattr(flow_instance, "run_analysis_refresh"):
            generator = flow_instance.run_analysis_refresh(  # type: ignore[attr-defined]
                session_id=session_id,
                query=query,
                requested_focus=analysis_payload,
                revision_directive=revision_directive,
                revision_inputs_plan=revision_inputs_plan,
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
    snapshot: Optional[SessionStateSnapshot],
) -> AsyncGenerator[Dict[str, Any], None]:
    missing_market_cache = True
    if snapshot is not None:
        analytics_cache = (snapshot.tool_cache or {}).get("analytics") or {}
        market_cache = analytics_cache.get("market")
        if isinstance(market_cache, Mapping):
            payload = market_cache.get("snapshot") or market_cache.get("payload")
            missing_market_cache = not bool(payload)
        else:
            missing_market_cache = True
    if missing_market_cache:
        logger.warning(
            "snapshot_missing",
            extra={"lane": "market", "session_id": session_id, "reason": "missing_market_snapshot"},
        )
        warning_event = EventEmitter.status(
            "snapshot_missing",
            "Market snapshot unavailable; rebuilding lane.",
        )
        warning_event.setdefault("data", {})
        warning_event["data"].update(
            {
                "lane": "market",
                "revision": True,
                "revision_id": revision_id,
                "session_id": session_id,
            }
        )
        yield warning_event
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
                    "reason": "snapshot_missing" if missing_market_cache else "not_supported",
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
    revision_inputs_plan: Optional[Dict[str, str]] = None,
    agentic_revision: bool = False,
    revision_questions: Optional[RevisionQuestionBundle] = None,
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
            "agentic_revision": agentic_revision,
        }
    )
    yield status_event

    plan_metadata: Dict[str, Any] = {
        "flow": selected_flow,
        "session_id": session_id,
        "revision_id": revision_id,
        "agentic_revision": agentic_revision,
    }
    should_emit_topics = any(lane in {"analysis", "web"} for lane in lanes)
    pending_topics_sent = False
    pending_topic_total = 0
    topic_branch_states: Dict[str, Dict[str, Any]] = {}
    topic_ready_emitted = False
    topic_questions_payload: Optional[Dict[str, Any]] = None

    if agentic_revision:
        _suppress_fresh_pipeline_latch(flow_instance)

    if revision_inputs_plan:
        plan_payload = dict(revision_inputs_plan)
        plan_event = EventEmitter.status("revision_inputs_plan", "Revision plan prepared.")
        plan_event["event"] = "revision_inputs_plan"
        plan_event.setdefault("data", {}).update({**plan_metadata, "plan": plan_payload})
        yield plan_event
        if snapshot:
            try:
                snapshot.record_revision_inputs_plan(plan_payload, metadata=plan_metadata)
            except Exception:
                logger.debug("Failed to persist revision inputs plan", exc_info=True)

    if should_emit_topics:
        pending_branches = _build_web_topic_branches(None, status="pending")
        if pending_branches:
            pending_topic_total = len(pending_branches)
            pending_event = EventEmitter.status("web_topics_pending", "Generating revision web topics.")
            pending_event["event"] = "web_topics_pending"
            pending_payload = {
                **plan_metadata,
                "total": pending_topic_total,
                "completed": 0,
                "pending": pending_topic_total,
                "branches": pending_branches,
            }
            pending_event.setdefault("data", {}).update(pending_payload)
            yield pending_event
            pending_topics_sent = True
            for branch in pending_branches:
                branch_id = str(branch.get("id") or branch.get("branch") or "").strip()
                if branch_id:
                    topic_branch_states[branch_id] = dict(branch)

    questions_bundle = revision_questions
    if questions_bundle is None:
        try:
            questions_bundle = derive_revision_questions(
                query=combined_query,
                revision_directive=revision_directive,
                snapshot=snapshot,
                session_id=session_id,
            )
        except Exception:
            logger.debug("Failed to derive revision questions", exc_info=True)
            questions_bundle = None
    if questions_bundle:
        if snapshot:
            try:
                snapshot.record_revision_questions(questions_bundle)
            except Exception:
                logger.debug("Failed to record revision questions on snapshot", exc_info=True)
        try:
            cache_revision_questions(snapshot, questions_bundle)
        except Exception:
            logger.debug("Failed to cache revision questions bundle", exc_info=True)
        if revision_directive:
            if questions_bundle.keyword_focus and not revision_directive.keyword_focus:
                revision_directive.keyword_focus = questions_bundle.keyword_focus
            if questions_bundle.user_question and not revision_directive.user_question:
                revision_directive.user_question = questions_bundle.user_question
            if questions_bundle.industry_question and not revision_directive.industry_question:
                revision_directive.industry_question = questions_bundle.industry_question

    if questions_bundle:
        try:
            topic_questions_payload = questions_bundle.to_dict()
        except Exception:
            topic_questions_payload = None

    if revision_directive is None:
        revision_directive = _synthesize_minimal_revision_directive(
            query=combined_query,
            analysis_text=analysis_text,
            chart_patch=chart_patch,
            lanes=lanes,
            prefer_agentic_revision=agentic_revision,
        )

    def _update_topic_branch_state(branch_payload: Mapping[str, Any]) -> None:
        if not should_emit_topics or not isinstance(branch_payload, Mapping):
            return
        branch_id = str(branch_payload.get("branch") or branch_payload.get("id") or "").strip()
        if not branch_id:
            return
        entry = topic_branch_states.setdefault(branch_id, {"id": branch_id, "status": "pending"})
        status_value = str(branch_payload.get("status") or "").strip() or "ready"
        entry["status"] = status_value
        summary_value = branch_payload.get("summary")
        if isinstance(summary_value, str) and summary_value.strip():
            entry["summary"] = summary_value.strip()
        question_kind = branch_payload.get("question_kind")
        if isinstance(question_kind, str) and question_kind.strip():
            entry["question_kind"] = question_kind.strip()

    def _maybe_emit_topics_ready() -> Optional[Dict[str, Any]]:
        nonlocal topic_ready_emitted
        if not should_emit_topics or topic_ready_emitted:
            return None
        total_topics = pending_topic_total or len(topic_branch_states)
        if total_topics <= 0:
            return None
        completed_topics = sum(
            1
            for branch in topic_branch_states.values()
            if str(branch.get("status") or "").strip().lower() in {"ready", "error"}
        )
        pending_count = max(total_topics - completed_topics, 0)
        if pending_count > 0:
            return None
        branches_payload: List[Dict[str, Any]] = list(topic_branch_states.values())
        if not branches_payload and questions_bundle:
            branches_payload = _build_web_topic_branches(questions_bundle, status="ready")
        ready_event = EventEmitter.status("web_topics_ready", "Revision web topics ready.")
        ready_event["event"] = "web_topics_ready"
        ready_payload: Dict[str, Any] = {
            **plan_metadata,
            "total": total_topics,
            "completed": completed_topics,
            "pending": pending_count,
            "branches": branches_payload,
        }
        if topic_questions_payload:
            ready_payload["questions"] = dict(topic_questions_payload)
        ready_event.setdefault("data", {}).update(ready_payload)
        topic_ready_emitted = True
        if snapshot:
            try:
                snapshot.record_web_topics_ready(ready_payload, metadata=plan_metadata)
            except Exception:
                logger.debug("Failed to persist web topics ready payload", exc_info=True)
        return ready_event

    def _process_topic_signal(event: Mapping[str, Any]) -> Optional[Dict[str, Any]]:
        nonlocal topic_questions_payload
        if not should_emit_topics or not isinstance(event, Mapping):
            return None
        name = str(event.get("event") or "")
        if not name:
            return None
        data = event.get("data") or {}
        if name == "web_topics_branch":
            _update_topic_branch_state(data)
            questions = data.get("questions")
            if isinstance(questions, Mapping):
                topic_questions_payload = dict(questions)
            return _maybe_emit_topics_ready()
        if name in {"web_ready", "web_revision_ready"}:
            questions = data.get("questions")
            if isinstance(questions, Mapping):
                topic_questions_payload = dict(questions)
            for branch in topic_branch_states.values():
                status_value = str(branch.get("status") or "").strip().lower()
                if status_value not in {"ready", "error"}:
                    branch["status"] = "ready"
            return _maybe_emit_topics_ready()
        return None

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
            "agentic_revision": agentic_revision,
        }
    )
    yield rev_event

    route_label = _revision_route_label(lanes)
    banner = _build_revision_banner(route_label, lanes)

    if lanes == ["market"]:
        follow_up_route = FollowUpRoute.STOCK_ONLY
    else:
        lane_hint = (revision_inputs_plan or {}).get("lane")
        if lane_hint == "chart":
            follow_up_route = FollowUpRoute.CHART_ONLY
        else:
            follow_up_route = FollowUpRoute.NARRATIVE_ONLY
    revision_guardrail = classifier.build_guardrail_payload(
        route=follow_up_route,
        query=combined_query or "",
        snapshot=snapshot,
        lane_readiness=lane_readiness,
        session_follow_up=True,
    )
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
            "agentic_revision": agentic_revision,
        },
    }
    if revision_guardrail:
        follow_up_event["data"]["guardrail"] = revision_guardrail
    if revision_inputs_plan:
        follow_up_event["data"]["revision_inputs_plan"] = dict(revision_inputs_plan)
    if questions_bundle:
        follow_up_event["data"]["revision_questions"] = questions_bundle.to_dict()
    yield follow_up_event
    if hasattr(flow_instance, "set_revision_targets"):
        flow_instance.set_revision_targets(lanes)
    if revision_inputs_plan and hasattr(flow_instance, "set_revision_inputs_plan"):
        try:
            flow_instance.set_revision_inputs_plan(revision_inputs_plan)
        except Exception:
            logger.exception("Failed to set revision inputs plan on flow %s", selected_flow)
    if hasattr(flow_instance, "set_follow_up_route"):
        flow_instance.set_follow_up_route(follow_up_route)
    if revision_guardrail and hasattr(flow_instance, "set_follow_up_guardrail"):
        try:
            flow_instance.set_follow_up_guardrail(revision_guardrail)  # type: ignore[attr-defined]
        except Exception:
            logger.exception("Failed to set revision guardrail on flow %s", selected_flow)
    if hasattr(flow_instance, "prime_with_snapshot"):
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
            snapshot=snapshot,
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
            revision_inputs_plan=revision_inputs_plan,
        ):
            yield event
            topic_event = _process_topic_signal(event)
            if topic_event:
                yield topic_event

    if "market" in lanes:
        async for event in _run_market_lane(
            flow_instance,
            query=combined_query,
            session_id=session_id,
            revision_id=revision_id,
            revision_kwargs=revision_kwargs,
            snapshot=snapshot,
        ):
            yield event

    if revision_inputs_plan:
        outcome_payload = _extract_revision_inputs_outcome(flow_instance)
        if outcome_payload:
            outcome_status = EventEmitter.status("revision_inputs_outcome", "Revision plan executed.")
            outcome_status["event"] = "revision_inputs_outcome"
            outcome_status.setdefault("data", {}).update(
                {**plan_metadata, "outcome": dict(outcome_payload)}
            )
            yield outcome_status
            if snapshot:
                try:
                    snapshot.record_revision_inputs_outcome(outcome_payload, metadata=plan_metadata)
                except Exception:
                    logger.debug("Failed to persist revision inputs outcome", exc_info=True)
            outcome_event = {
                "event": "follow_up_route",
                "data": {
                    "route": follow_up_route.value,
                    "flow": selected_flow,
                    "session_id": session_id,
                    "revision": True,
                    "revision_id": revision_id,
                    "phase": "refresh_outcome",
                    "revision_inputs_plan": dict(revision_inputs_plan),
                    "revision_inputs_outcome": dict(outcome_payload),
                },
            }
            yield outcome_event

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
        backlog = list(snapshot.agents_message_backlog)
        backlog.extend(overflow)
        if len(backlog) > SESSION_MESSAGE_ARCHIVE_LIMIT:
            backlog = backlog[-SESSION_MESSAGE_ARCHIVE_LIMIT:]
        snapshot.agents_message_backlog = backlog
    snapshot.touch()


def _parse_snapshot_timestamp(value: Optional[str]) -> Optional[datetime]:
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    if not normalized:
        return None
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(normalized)
    except ValueError:
        return None


def _session_idle_expired(
    snapshot: SessionStateSnapshot,
    *,
    idle_timeout_seconds: int = 30 * 60,
) -> bool:
    recorded_at = _parse_snapshot_timestamp(snapshot.agents_recorded_at)
    reference_ts = recorded_at or getattr(snapshot, "updated_at", None)
    if not isinstance(reference_ts, datetime):
        return False
    delta = datetime.now(timezone.utc) - reference_ts
    return delta.total_seconds() >= idle_timeout_seconds


async def _hydrate_inputs_manifest(
    session_id: str,
    repository: SessionStateRepository,
    *,
    snapshot: Optional[SessionStateSnapshot] = None,
) -> Optional[SessionStateSnapshot]:
    working_snapshot = snapshot or await repository.load(session_id)
    if working_snapshot is None:
        return None
    try:
        working_snapshot.ensure_dataset_preview_from_revision()
        working_snapshot.ensure_analysis_lane_receipts()
        working_snapshot.refresh_analysis_inputs_manifest(persist=True)
    except Exception:
        logger.debug("Failed to hydrate analysis manifest for session %s", session_id, exc_info=True)
        return working_snapshot
    await repository.save(working_snapshot)
    return working_snapshot

async def analytics_memory_workflow(
    query: str,
    session_id: Optional[str] = None,
    flow: Optional[str] = None,
    *,
    reset_session: bool = False,
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
    revision_requested = bool(chart_revision_requested or analysis_revision_requested)
    if revision_requested:
        # Skip planner instrumentation for revision-only runs so we do not
        # replay the deterministic planner pipeline ahead of targeted lanes.
        should_instrument = False
    revision_questions_bundle: Optional[RevisionQuestionBundle] = None

    repository = get_session_state_repository() if session_id else None
    snapshot: Optional[SessionStateSnapshot] = None
    if repository and session_id:
        snapshot = await repository.load(session_id)
        if snapshot is not None:
            snapshot_reset = False
            dataset_seeded = snapshot.ensure_dataset_preview_from_revision()
            analysis_seeded = snapshot.ensure_analysis_outputs_from_revision()
            snapshot_dirty = bool(dataset_seeded or analysis_seeded)
            if reset_session:
                snapshot.reset_agent_session()
                snapshot_reset = True
            elif _session_idle_expired(snapshot):
                snapshot.reset_agent_session()
                snapshot_reset = True
            try:
                snapshot.refresh_analysis_inputs_manifest(persist=False)
            except Exception:  # pragma: no cover - defensive guard
                logger.debug("Failed to refresh manifest before workflow start", exc_info=True)
            if snapshot_reset or snapshot_dirty:
                try:
                    await repository.save(snapshot)
                except Exception:  # pragma: no cover - defensive guard
                    logger.debug("Failed to persist reset snapshot state", exc_info=True)
    if (
        repository
        and session_id
        and snapshot is not None
        and isinstance(snapshot.analysis_inputs_manifest, dict)
        and snapshot.analysis_inputs_manifest.get("status") != "sealed"
        and analysis_revision_requested
    ):
        hydrated = await _hydrate_inputs_manifest(session_id, repository, snapshot=snapshot)
        if hydrated is not None:
            snapshot = hydrated

    has_chart = bool(getattr(snapshot, "last_chart_spec", None)) if snapshot else False
    has_analysis = bool(getattr(snapshot, "last_analysis", None)) if snapshot else False

    lane_readiness = _lane_readiness(snapshot)
    baseline_ready = _baseline_ready(snapshot, lane_readiness=lane_readiness)
    session_follow_up = bool(session_id and baseline_ready)

    classifier = FollowUpClassifier()
    route = classifier.classify(query, snapshot, lane_readiness=lane_readiness)
    follow_up_guardrail = classifier.build_guardrail_payload(
        route=route,
        query=query or "",
        snapshot=snapshot,
        lane_readiness=lane_readiness,
        session_follow_up=session_follow_up,
    )
    detected_targets = classifier.detect_revision_targets(query, snapshot, lane_readiness=lane_readiness)

    chart_patch = patch_probe if chart_revision_requested else None
    analysis_text = (
        infer_analysis_revision_from_query(query) if analysis_revision_requested else None
    )
    manifest_missing_components: List[str] = []
    manifest_pending_components: List[str] = []
    manifest_inputs_ready = False
    revision_inputs_plan: Optional[Dict[str, str]] = None
    if analysis_revision_requested and session_id:
        revision_snapshot_ready = True
        try:
            revision_ctx = await RevisionContext.load(session_id, repository=repository)
            manifest_inputs_ready = revision_ctx.analysis_inputs_ready()
            manifest_missing_components = revision_ctx.analysis_inputs_missing()
            manifest_payload = (
                revision_ctx.analysis_inputs_manifest
                if isinstance(revision_ctx.analysis_inputs_manifest, dict)
                else {}
            )
            manifest_components = manifest_payload.get("components")
            if isinstance(manifest_components, Mapping):
                manifest_pending_components = [
                    component
                    for component, entry in manifest_components.items()
                    if isinstance(entry, Mapping) and str(entry.get("state") or "").strip().lower() == "pending"
                ]
            if not revision_ctx.has_analysis_text() and not manifest_inputs_ready:
                revision_snapshot_ready = False
        except MissingRevisionSnapshot:
            revision_snapshot_ready = False
        except MissingAnalysis:
            revision_snapshot_ready = bool(manifest_inputs_ready)
        pending_set = set(manifest_pending_components)
        missing_subset_of_pending = bool(pending_set) and all(
            component in pending_set for component in manifest_missing_components
        )
        baseline_pending = session_follow_up and (not manifest_inputs_ready) and missing_subset_of_pending
        if baseline_pending:
            pending_lanes = _lanes_for_missing_inputs(manifest_pending_components) or ["analysis", "web"]
            lane_refresh_required = {lane: True for lane in pending_lanes}
            banner = {
                "title": "Baseline Still Running",
                "message": "Hold tight while the current run seals analysis inputs before revisions can start.",
                "pending_components": manifest_pending_components,
            }
            streaming_event = {
                "event": "baseline_still_streaming",
                "data": {
                    "flow": selected,
                    "session_id": session_id,
                    "lanes": pending_lanes,
                    "pending_components": manifest_pending_components,
                    "lane_refresh_required": lane_refresh_required,
                    "session_follow_up": session_follow_up,
                    "banner": banner,
                },
            }
            if revision_inputs_plan:
                streaming_event["data"]["revision_inputs_plan"] = dict(revision_inputs_plan)
            yield streaming_event
            _append_session_message(
                snapshot,
                role="system",
                content="Revision delayed until the current analysis run finishes sealing web and dataset inputs.",
            )
            if repository and snapshot is not None:
                await repository.save(snapshot)
            return
        if not revision_snapshot_ready:
            missing_lanes = _lanes_for_missing_inputs(manifest_missing_components) or ["analysis", "web"]
            lane_refresh_required = {lane: True for lane in missing_lanes}
            banner = _build_cannot_revise_banner(missing_lanes, ["analysis"])
            reason = "missing_analysis_inputs" if manifest_missing_components else "missing_analysis"
            banner["reason"] = reason
            if manifest_missing_components:
                banner["missing_components"] = manifest_missing_components
            follow_up_event = {
                "event": "follow_up_route",
                "data": {
                    "route": "cannot_revise",
                    "flow": selected,
                    "session_id": session_id,
                    "lanes": missing_lanes,
                    "lane_refresh_required": lane_refresh_required,
                    "session_follow_up": session_follow_up,
                    "banner": banner,
                },
            }
            if revision_inputs_plan:
                follow_up_event["data"]["revision_inputs_plan"] = dict(revision_inputs_plan)
            yield follow_up_event
            _append_session_message(
                snapshot,
                role="system",
                content="Revision skipped because required analysis inputs are still streaming. Start a new question if you need a fresh run.",
            )
            if session_id:
                analysis_inputs_missing(
                    session_id=session_id,
                    missing_components=manifest_missing_components or missing_lanes,
                    lane_readiness=lane_readiness,
                    route="cannot_revise",
                    metadata={"analysis_revision_requested": True, "flow": selected},
                )
            if repository and snapshot is not None:
                await repository.save(snapshot)
            return
        if not has_analysis:
            lanes = ["analysis", "web"]
            lane_refresh_required = {lane: True for lane in lanes}
            banner = _build_cannot_revise_banner(lanes, ["analysis"])
            banner["reason"] = "missing_analysis"
            follow_up_event = {
                "event": "follow_up_route",
                "data": {
                    "route": "cannot_revise",
                    "flow": selected,
                    "session_id": session_id,
                    "lanes": lanes,
                    "lane_refresh_required": lane_refresh_required,
                    "session_follow_up": session_follow_up,
                    "banner": banner,
                },
            }
            if revision_inputs_plan:
                follow_up_event["data"]["revision_inputs_plan"] = dict(revision_inputs_plan)
            yield follow_up_event
            _append_session_message(
                snapshot,
                role="system",
                content="Revision skipped because the baseline chart and narrative were never recorded. Start a new analytics run to capture them before revising.",
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

    prefer_agentic_revision = bool(
        session_follow_up
        and isinstance(flow_instance, (SingleAgentController, MultiAgentFlow))
        and revision_requested
    )
    if prefer_agentic_revision:
        # Agentic revisions stream their own agent_coordination/tool events,
        # so planner instrumentation would only duplicate the lane timelines.
        should_instrument = False
        setattr(flow_instance, "_agentic_revision_mode", True)

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
    if session_follow_up and route == FollowUpRoute.REUSE_SQL:
        ttl_lanes.add("sql")
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
        if "market" not in revision_lanes and "market" not in lane_refresh_required:
            lane_refresh_required["market"] = False

    lane_refresh_required.setdefault("sql", False)

    missing_revision_lanes = [
        lane for lane in revision_lanes if not _lane_available(snapshot, lane, lane_readiness)
    ]

    for lane in missing_revision_lanes:
        normalized = str(lane or "").strip().lower()
        if not normalized:
            continue
        lane_refresh_required[normalized] = True
        if normalized == "analysis":
            lane_refresh_required["web"] = True
    if lane_refresh_required.get("analysis"):
        analysis_refresh_mode = "full"

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
        if revision_questions_bundle is None:
            try:
                revision_questions_bundle = derive_revision_questions(
                    query=combined_query,
                    revision_directive=revision_directive,
                    snapshot=snapshot,
                    session_id=session_id,
                )
            except Exception:
                logger.debug("Failed to derive revision questions upstream", exc_info=True)
                revision_questions_bundle = None
        if revision_questions_bundle and revision_directive:
            if revision_questions_bundle.keyword_focus:
                revision_directive.keyword_focus = revision_questions_bundle.keyword_focus
            if revision_questions_bundle.user_question:
                revision_directive.user_question = revision_questions_bundle.user_question
            if revision_questions_bundle.industry_question:
                revision_directive.industry_question = revision_questions_bundle.industry_question
        if revision_inputs_plan is None:
            revision_inputs_plan = _build_revision_inputs_plan(
                lane_readiness,
                lane_refresh_required,
                manifest_missing_components,
                question_bundle=revision_questions_bundle,
                revision_lanes=revision_lanes,
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
        if revision_inputs_plan and hasattr(flow_instance, "set_revision_inputs_plan"):
            try:
                flow_instance.set_revision_inputs_plan(revision_inputs_plan)
            except Exception:
                logger.exception("Failed to set revision inputs plan on flow %s", selected)
        agentic_revision_flag = _resolve_agentic_revision_flag(
            flow_instance,
            prefer_agentic_revision,
            revision_directive,
        )
        if agentic_revision_flag:
            should_instrument = False
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
            revision_inputs_plan=revision_inputs_plan,
            agentic_revision=agentic_revision_flag,
            revision_questions=revision_questions_bundle,
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

    if _requires_revision_directive(revision_lanes) and revision_directive is None:
        revision_directive = _synthesize_minimal_revision_directive(
            query=query,
            analysis_text=analysis_text,
            chart_patch=chart_patch,
            lanes=revision_lanes,
            prefer_agentic_revision=prefer_agentic_revision,
        )
    if revision_directive and hasattr(flow_instance, "set_revision_directive"):
        try:
            flow_instance.set_revision_directive(revision_directive)  # type: ignore[attr-defined]
        except Exception:
            logger.exception("Failed to set revision directive on flow %s", selected)

    # Treat presence of a revision directive as sufficient to let the active flow
    # handle the revision inside the normal pipeline (even if not explicitly
    # marked as "agentic"). This avoids short‑circuiting analysis revisions and
    # allows accessory fan‑out (e.g., concurrent web retrievers) to run.
    supports_agentic = bool(
        revision_directive and hasattr(flow_instance, "set_revision_directive")
    )

    agentic_revision_flag = _resolve_agentic_revision_flag(
        flow_instance,
        prefer_agentic_revision,
        revision_directive,
    )
    if agentic_revision_flag:
        should_instrument = False

    # Always surface a revision_request event for UI/telemetry, even when not
    # running in agentic mode. This helps diagnostics when a session snapshot
    # is missing and lanes cannot be restricted yet.
    if revision_directive:
        rev_event = revision_directive.to_event(session_id=session_id)
        rev_event.setdefault("data", {})
        rev_event["data"]["flow"] = selected
        rev_event["data"]["phase"] = "initial"
        rev_event["data"]["agentic_revision"] = agentic_revision_flag
        yield rev_event

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
                    revision_inputs_plan=revision_inputs_plan,
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
                    revision_inputs_plan=revision_inputs_plan,
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
    if revision_inputs_plan and hasattr(flow_instance, "set_revision_inputs_plan"):
        try:
            flow_instance.set_revision_inputs_plan(revision_inputs_plan)
        except Exception:
            logger.exception("Failed to set revision inputs plan on flow %s", selected)
    if hasattr(flow_instance, "set_follow_up_route"):
        flow_instance.set_follow_up_route(route)
    if follow_up_guardrail and hasattr(flow_instance, "set_follow_up_guardrail"):
        try:
            flow_instance.set_follow_up_guardrail(follow_up_guardrail)  # type: ignore[attr-defined]
        except Exception:
            logger.exception("Failed to set follow-up guardrail on flow %s", selected)
    follow_up_event = {
        "event": "follow_up_route",
        "data": {
            "route": route.value,
            "flow": selected,
            "lanes": list(revision_lanes),
            "lane_refresh_required": dict(lane_refresh_required),
            "session_follow_up": session_follow_up,
            "agentic_revision": agentic_revision_flag,
        },
    }
    if follow_up_guardrail:
        follow_up_event["data"]["guardrail"] = follow_up_guardrail
    if revision_inputs_plan:
        follow_up_event["data"]["revision_inputs_plan"] = dict(revision_inputs_plan)
    if missing_revision_lanes:
        follow_up_event["data"]["missing_lanes"] = list(missing_revision_lanes)
    yield follow_up_event
    sequencer: Optional[PlannerSequencer] = None
    sequencer_state: Optional[Any] = None
    emit_prefill_summary: Optional[bool] = None
    if isinstance(flow_instance, SingleAgentController) and not prefer_agentic_revision:
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
    elif isinstance(flow_instance, MultiAgentFlow) and not prefer_agentic_revision:
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
            revision_requested=revision_requested,
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
        event_kwargs: Dict[str, Any] = {"session_id": session_id}
        if sequencer is not None:
            event_kwargs.update(
                {
                    "sequencer": sequencer,
                    "emit_prefill_summary": emit_prefill_summary,
                    "sequencer_state": sequencer_state,
                }
            )
        if revision_requested and isinstance(flow_instance, PlannerExecutorFlow):
            event_kwargs["revision_requested"] = True
        stream = flow_instance.events(query, **event_kwargs)
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
