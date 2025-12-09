# --- Analytics Function/Class Map ---
# Class: PlannerRevisionContext
#   Role: Hydrates and tracks revision receipts/TTL metadata for cached sessions.
#   Called from: analytics.flows.planner_executor, analytics.flows.single_agent_tools
#   Invokes: analytics.core.session_state.SessionStateSnapshot, resolve_lane_ttls
#   Why: Centralizes revision TTL + accessory snapshot handling across modes.
# Class: PlannerPhaseContext
#   Role: Shared planner state bag used by planner pipeline, agents, and tools.
#   Called from: analytics.flows.planner_executor, analytics.flows.pipeline_tools,
#                analytics.flows.single_agent_tools, analytics.flows.multi_agent
#   Invokes: dataclasses.field
#   Why: Provides a single context model reused across Direct, Single-Agent, Multi-Agent flows.
# --- End Analytics Function/Class Map ---
from __future__ import annotations

import copy
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Mapping, Optional, Set, TYPE_CHECKING

from analytics.agents.schema_clarifier import ClarifierDecision
from analytics.artifacts import PipelineArtifacts
from analytics.core.events import TimedEventEmitter
from analytics.core.intent import OffTopicClassifierSchema, IntentModel
from analytics.core.intent_impl.models import IntentResolutionModel, SlotStatusModel, FollowUpModel
from analytics.core.lane_refresh import resolve_lane_ttls
from analytics.core.session_state import SnapshotRevisionContext, SessionStateSnapshot
from analytics.core.types import ClarifyRequestModel, QueryPlanModel
from analytics.flows.planner.receipts import ToolInvocationReceipt
from analytics.flows.schedulers import FlowMode
from analytics.routing import FollowUpRoute
from analytics.services.response_search import ResponseSearchResult

if TYPE_CHECKING:  # pragma: no cover - typing only
    from analytics.flows.revision_directive import RevisionDirective


@dataclass
class PlannerRevisionContext:
    session_id: str
    receipts: Dict[str, ToolInvocationReceipt] = field(default_factory=dict)
    lane_refresh_overrides: Dict[str, bool] = field(default_factory=dict)
    lane_ttls: Dict[str, int] = field(default_factory=dict)
    lane_timestamps: Dict[str, datetime] = field(default_factory=dict)
    reasoning_summaries: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    accessories: Dict[str, Any] = field(default_factory=dict)
    last_analysis: Optional[str] = None
    last_chart_spec: Optional[Dict[str, Any]] = None
    snapshot_payload: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_snapshot(
        cls,
        snapshot: Optional[SessionStateSnapshot],
        *,
        lane_refresh_overrides: Mapping[str, bool],
    ) -> Optional["PlannerRevisionContext"]:
        if snapshot is None:
            return None
        snapshot_ctx: SnapshotRevisionContext = snapshot.revision_context()
        lane_ttls = dict(snapshot_ctx.lane_ttls) if snapshot_ctx.lane_ttls else resolve_lane_ttls()
        receipts: Dict[str, ToolInvocationReceipt] = {}
        for tool_name, payload in snapshot_ctx.tool_receipts.items():
            try:
                receipts[tool_name] = ToolInvocationReceipt.from_dict(payload)
            except Exception:
                continue
        normalized_overrides: Dict[str, bool] = {}
        for lane, required in (lane_refresh_overrides or {}).items():
            key = cls._normalize_lane(lane)
            if key:
                normalized_overrides[key] = bool(required)
        accessories: Dict[str, Any] = {}
        snapshot_payload: Dict[str, Any] = {}
        revision_snapshot = snapshot_ctx.revision_snapshot or {}
        if isinstance(revision_snapshot, Mapping):
            snapshot_payload = copy.deepcopy(revision_snapshot)
            web_snapshot = revision_snapshot.get("web_context")
            if isinstance(web_snapshot, Mapping):
                accessories["web"] = copy.deepcopy(web_snapshot)
            stock_snapshot = revision_snapshot.get("stock_widget")
            if stock_snapshot is not None:
                accessories["market"] = copy.deepcopy(stock_snapshot)
        return cls(
            session_id=snapshot_ctx.session_id,
            receipts=receipts,
            lane_refresh_overrides=normalized_overrides,
            lane_ttls=lane_ttls,
            lane_timestamps=dict(snapshot_ctx.lane_timestamps),
            reasoning_summaries=copy.deepcopy(snapshot_ctx.agent_reasoning),
            accessories=accessories,
            last_analysis=snapshot_ctx.last_analysis,
            last_chart_spec=copy.deepcopy(snapshot_ctx.last_chart_spec) if snapshot_ctx.last_chart_spec else None,
            snapshot_payload=snapshot_payload,
        )

    @staticmethod
    def _normalize_lane(lane: Optional[str]) -> Optional[str]:
        if lane is None:
            return None
        normalized = str(lane).strip().lower()
        return normalized or None

    def lane_age_seconds(self, lane: str, *, now: Optional[datetime] = None) -> Optional[float]:
        normalized = self._normalize_lane(lane)
        if not normalized:
            return None
        timestamp = self.lane_timestamps.get(normalized)
        if timestamp is None:
            return None
        now_dt = now or datetime.now(timezone.utc)
        try:
            delta = now_dt - timestamp
            return max(delta.total_seconds(), 0.0)
        except Exception:
            return None

    def should_refresh(self, lane: str) -> bool:
        normalized = self._normalize_lane(lane)
        if not normalized:
            return True
        if normalized in self.lane_refresh_overrides:
            return self.lane_refresh_overrides[normalized]
        ttl = self.lane_ttls.get(normalized)
        if ttl is None or ttl <= 0:
            return True
        age = self.lane_age_seconds(normalized)
        if age is None:
            return True
        return age > ttl

    def accessory_snapshot(self, lane: str) -> Optional[Dict[str, Any]]:
        normalized = self._normalize_lane(lane)
        if not normalized:
            return None
        payload = self.accessories.get(normalized)
        if payload is None:
            return None
        return copy.deepcopy(payload)


@dataclass
class PlannerPhaseContext:
    query: str
    session_id: str
    workflow_start: float
    timed_emitter: TimedEventEmitter
    flow_mode: FlowMode = FlowMode.DIRECT
    configs: Dict[str, Any] = field(default_factory=dict)
    classification: Optional[OffTopicClassifierSchema] = None
    is_financial_query: bool = True
    intent: Optional[IntentModel] = None
    provisional_plan: Optional[QueryPlanModel] = None
    template: Optional[Any] = None
    clarifications: List[ClarifyRequestModel] = field(default_factory=list)
    clarification_sources: Set[str] = field(default_factory=set)
    assumptions: List[str] = field(default_factory=list)
    intent_resolution: Optional[IntentResolutionModel] = None
    slot_statuses: Dict[str, SlotStatusModel] = field(default_factory=dict)
    slot_followups: List[FollowUpModel] = field(default_factory=list)
    clarification_rounds: int = 0
    clarifier_agent_invoked: bool = False
    schema_clarifier_decision: Optional[ClarifierDecision] = None
    plan: Optional[QueryPlanModel] = None
    candidate_templates: List[Dict[str, Any]] = field(default_factory=list)
    selected_template_id: Optional[str] = None
    web_search: Optional[ResponseSearchResult] = None
    web_search_seeded: bool = False
    stock_widget_seeded: bool = False
    parallelism_enabled: bool = False
    follow_up_route: FollowUpRoute = FollowUpRoute.FULL_PIPELINE
    reuse_sql: bool = False
    stock_only: bool = False
    blocking_clarification: bool = False
    clarification_timeout_seconds: float = 60.0
    clarification_answers: List[Dict[str, Any]] = field(default_factory=list)
    clarifications_needed: Optional[bool] = None
    artifacts: PipelineArtifacts = field(default_factory=PipelineArtifacts)
    snapshot_artifacts: Optional[PipelineArtifacts] = None
    revision_snapshot: Optional[Dict[str, Any]] = None
    prior_intent_signature: Optional[Dict[str, Any]] = None
    intent_signature: Optional[Dict[str, Any]] = None
    criteria_changed: bool = False
    reuse_snapshot_active: bool = False
    reused_sql: bool = False
    reused_chart: bool = False
    reused_stock: bool = False
    reused_web: bool = False
    reused_analysis: bool = False
    snapshot_age_seconds: Optional[float] = None
    snapshot_stale: bool = False
    tool_receipts: Dict[str, ToolInvocationReceipt] = field(default_factory=dict)
    revision_targets: Set[str] = field(default_factory=set)
    revision_id: Optional[str] = None
    revision_hint_active: bool = False
    revision_directive: Optional["RevisionDirective"] = None
    agentic_revision_mode: bool = False
    force_full_fresh_pipeline: bool = False
    halted: bool = False
    halt_reason: Optional[str] = None
    lane_refresh_required: Dict[str, bool] = field(default_factory=dict)
    analysis_refresh_mode: str = "full"
    session_follow_up: bool = False
    revision_context: Optional[PlannerRevisionContext] = None
    revision_reasoning: Dict[str, Dict[str, Any]] = field(default_factory=dict)

