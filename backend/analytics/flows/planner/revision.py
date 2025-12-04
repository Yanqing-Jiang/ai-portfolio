# --- Analytics Function/Class Map ---
# Function: normalize_revision_targets
#   Role: Handles normalize revision targets logic for analytics.flows.planner.revision.
#   Called from: analytics.flows.planner, analytics.flows.planner_executor
#   Invokes: Internal helpers only
#   Why: Keeps analytics.flows.planner.revision from duplicating normalize revision targets behavior across flows.
# Function: annotate_revision_event
#   Role: Handles annotate revision event logic for analytics.flows.planner.revision.
#   Called from: analytics.flows.multi_agent, analytics.flows.planner, analytics.flows.planner_executor, analytics.flows.single_agent_tools
#   Invokes: Internal helpers only
#   Why: Keeps analytics.flows.planner.revision from duplicating annotate revision event behavior across flows.
# Function: build_revision_request_event
#   Role: Handles build revision request event logic for analytics.flows.planner.revision.
#   Called from: analytics.flows.multi_agent, analytics.flows.planner, analytics.flows.planner_executor, analytics.flows.single_agent_tools
#   Invokes: Internal helpers only
#   Why: Keeps analytics.flows.planner.revision from duplicating build revision request event behavior across flows.
# Function: derive_revision_targets
#   Role: Handles derive revision targets logic for analytics.flows.planner.revision.
#   Called from: analytics.flows.multi_agent, analytics.flows.planner, analytics.flows.planner_executor, analytics.flows.single_agent_tools, +1 more
#   Invokes: analytics.flows.planner.revision.normalize_revision_targets
#   Why: Keeps analytics.flows.planner.revision from duplicating derive revision targets behavior across flows.
# Function: mark_revision_completion
#   Role: Handles mark revision completion logic for analytics.flows.planner.revision.
#   Called from: analytics.flows.planner, analytics.flows.planner.analysis_lane, analytics.flows.planner.sql_lane
#   Invokes: Internal helpers only
#   Why: Keeps analytics.flows.planner.revision from duplicating mark revision completion behavior across flows.
# Class: RevisionPlan
#   Role: Handles RevisionPlan logic for analytics.flows.planner.revision.
#   Called from: Internal to analytics.flows.planner.revision
#   Collaborators: dataclasses.dataclass
#   Why: Keeps analytics.flows.planner.revision from duplicating RevisionPlan behavior across flows.
# Function: build_revision_plan
#   Role: Handles build revision plan logic for analytics.flows.planner.revision.
#   Called from: analytics.flows.multi_agent, analytics.flows.planner, analytics.flows.planner_executor, analytics.flows.single_agent_tools, +1 more
#   Invokes: analytics.flows.planner.revision.normalize_revision_targets, analytics.flows.planner.revision.RevisionPlan, analytics.flows.planner.revision.derive_revision_targets
#   Why: Keeps analytics.flows.planner.revision from duplicating build revision plan behavior across flows.
# Function: apply_revision_plan
#   Role: Handles apply revision plan logic for analytics.flows.planner.revision.
#   Called from: analytics.flows.multi_agent, analytics.flows.planner, analytics.flows.planner_executor, analytics.flows.single_agent_tools, +1 more
#   Invokes: uuid.uuid4
#   Why: Keeps analytics.flows.planner.revision from duplicating apply revision plan behavior across flows.
# --- End Analytics Function/Class Map ---
from __future__ import annotations

from datetime import datetime
from dataclasses import dataclass
from typing import Any, Dict, Iterable, Mapping, Optional, Set, TYPE_CHECKING
import uuid

if TYPE_CHECKING:  # pragma: no cover - typing only
    from ..planner_executor import PlannerPhaseContext


REVISION_EVENT_ALIASES: Mapping[str, str] = {
    "stock_ready": "stock_revision_ready",
    "web_ready": "web_revision_ready",
    "sql_ready": "sql_revision_ready",
    "chart_ready": "chart_revision_ready",
    "analysis_ready": "analysis_revision_ready",
}

__all__ = [
    "REVISION_EVENT_ALIASES",
    "annotate_revision_event",
    "build_revision_request_event",
    "derive_revision_targets",
    "build_revision_plan",
    "apply_revision_plan",
    "mark_revision_completion",
    "normalize_revision_targets",
]


def normalize_revision_targets(targets: Iterable[str]) -> Set[str]:
    normalized: Set[str] = set()
    for target in targets or []:
        if not target:
            continue
        normalized.add(str(target).strip().lower())
    return normalized


def annotate_revision_event(
    event: Dict[str, Any],
    ctx: Optional["PlannerPhaseContext"],
    *,
    aliases: Mapping[str, str] = REVISION_EVENT_ALIASES,
) -> Dict[str, Any]:
    if not ctx or not ctx.revision_targets:
        return event
    alias = aliases.get(event.get("event"))
    if alias:
        event["event"] = alias
    data = event.setdefault("data", {})
    data.setdefault("revision_id", ctx.revision_id)
    data.setdefault("revision", True)
    data.setdefault("revision_lanes", sorted(ctx.revision_targets))
    if alias:
        data.setdefault("revision_event", True)
    return event


def build_revision_request_event(
    ctx: "PlannerPhaseContext",
    *,
    flow_mode_value: str,
    follow_up_route_value: Optional[str],
) -> Dict[str, Any]:
    event: Dict[str, Any] = {
        "event": "revision_request",
        "data": {
            "revision_id": ctx.revision_id,
            "lanes": sorted(ctx.revision_targets),
            "ts": datetime.utcnow().isoformat(),
            "flow_mode": flow_mode_value,
        },
    }
    if follow_up_route_value is not None:
        event["data"]["follow_up_route"] = follow_up_route_value
    return event


def derive_revision_targets(
    ctx: "PlannerPhaseContext",
    *,
    intent_lane_map: Optional[Mapping[str, Iterable[str]]] = None,
    default: Optional[Iterable[str]] = None,
) -> Set[str]:
    from analytics.routing import FollowUpRoute  # local import to avoid circular at module import

    explicit_targets = set(getattr(ctx, "revision_targets", set()) or set())
    revision_snapshot = getattr(ctx, "revision_snapshot", None)
    if explicit_targets:
        return explicit_targets

    if not revision_snapshot:
        return set()

    hint_active = bool(getattr(ctx, "revision_hint_active", False))
    if not hint_active:
        return set()

    targets: Set[str] = set()
    intent_obj = getattr(ctx, "intent", None)
    if intent_obj is not None:
        intent_key = str(getattr(intent_obj, "intent_key", "") or "").lower()
        if intent_lane_map:
            for key, lanes in intent_lane_map.items():
                normalized_key = str(key or "").strip().lower()
                if not normalized_key or normalized_key not in intent_key:
                    continue
                targets.update(normalize_revision_targets(lanes))
        if not targets and intent_key:
            if "chart" in intent_key or "visual" in intent_key:
                targets.add("chart")
            if any(segment in intent_key for segment in ("analysis", "insight", "summary", "report")):
                targets.add("analysis")
            if any(segment in intent_key for segment in ("market", "stock", "price", "trading", "ticker")):
                targets.add("stock")
            if any(segment in intent_key for segment in ("web", "news", "headline", "search")):
                targets.add("web")
            if not targets and intent_key:
                targets.add("sql")
    if targets:
        return targets

    follow_up = getattr(ctx, "follow_up_route", FollowUpRoute.FULL_PIPELINE)
    if follow_up == FollowUpRoute.STOCK_ONLY:
        targets.add("stock")
        return targets
    if follow_up == FollowUpRoute.REUSE_SQL:
        targets.update({"chart", "analysis"})
        return targets
    if default is None:
        default = ("sql", "chart", "analysis", "market", "web")
    for lane in default:
        targets.add(str(lane))
    return targets


def mark_revision_completion(ctx: "PlannerPhaseContext", lane: str) -> None:
    completed: Optional[Set[str]] = getattr(ctx, "revision_completed_lanes", None)
    if completed is None:
        completed = set()
        ctx.revision_completed_lanes = completed
    completed.add(lane)


@dataclass(frozen=True)
class RevisionPlan:
    targets: Set[str]
    run_sql_lane: bool
    run_chart_lane: bool
    run_analysis_lane: bool
    stock_only: bool


def build_revision_plan(
    ctx: "PlannerPhaseContext",
    *,
    targets: Optional[Iterable[str]] = None,
) -> RevisionPlan:
    normalized_targets = normalize_revision_targets(targets or ctx.revision_targets or ())
    if not normalized_targets:
        normalized_targets = derive_revision_targets(ctx)
    if "analysis" in normalized_targets and "web" not in normalized_targets:
        normalized_targets.add("web")
    stock_only = normalized_targets == {"stock"}
    run_sql_lane = not normalized_targets or "sql" in normalized_targets
    run_chart_lane = not normalized_targets or bool({"sql", "chart"} & normalized_targets)
    run_analysis_lane = not normalized_targets or bool({"sql", "analysis"} & normalized_targets)
    if stock_only:
        run_sql_lane = False
        run_chart_lane = False
        run_analysis_lane = False
    return RevisionPlan(
        targets=normalized_targets,
        run_sql_lane=run_sql_lane,
        run_chart_lane=run_chart_lane,
        run_analysis_lane=run_analysis_lane,
        stock_only=stock_only,
    )


def apply_revision_plan(ctx: "PlannerPhaseContext", plan: RevisionPlan) -> None:
    ctx.revision_targets = set(plan.targets)
    ctx.revision_hint_active = bool(plan.targets)
    if plan.targets:
        ctx.revision_id = getattr(ctx, "revision_id", None) or str(uuid.uuid4())
    lane_refresh_required = getattr(ctx, "lane_refresh_required", None)
    if not isinstance(lane_refresh_required, dict):
        lane_refresh_required = {}
        ctx.lane_refresh_required = lane_refresh_required
    if "web" in plan.targets:
        lane_refresh_required["web"] = True
        ctx.reused_web = False
    if "market" in plan.targets or "stock" in plan.targets:
        lane_refresh_required["market"] = True
    if plan.stock_only:
        ctx.stock_only = True
        ctx.reuse_sql = True
        ctx.reused_sql = True
        ctx.reused_chart = True
        ctx.reused_analysis = True
        ctx.reused_web = True
        ctx.parallelism_enabled = False
        return
    if not plan.run_sql_lane:
        ctx.reuse_sql = True
        ctx.reused_sql = True
    if not plan.run_chart_lane:
        ctx.reused_chart = True
    if not plan.run_analysis_lane:
        ctx.reused_analysis = True
