# --- Dashboard Models Function/Class Map ---
# Class: DashboardPlan
#   Role: Typed dashboard plan (skill, widgets, slots).
#   Called from: DashboardState, DashboardStore.create, runtime/layout planner.
#   Invokes: n/a
#   Why: Keeps stored plans structured for validation and serialization.
# Class: RuntimeParams
#   Role: Typed mutable params (timeframe, peers, clarifications).
#   Called from: DashboardState, runtime/clarification handlers.
#   Invokes: n/a
#   Why: Maintains runtime inputs safely while allowing dict-like access.
# Class: DashboardRun
#   Role: Persist a single execution run (data + citations + trace/layout signatures).
#   Called from: DashboardState.add_run
#   Invokes: n/a
#   Why: Enables replay/debug of prior executions with layout context.
# Class: DashboardState
#   Role: Aggregate dashboard plan, params, runs, status, and metadata.
#   Called from: runtime orchestrator, API routes, DashboardStore.
#   Invokes: RuntimeParams, DashboardPlan.
#   Why: Central server-side state for streaming + actions.
# Class: DashboardStore
#   Role: In-memory repository for DashboardState objects.
#   Called from: API routes (create/get/delete/list).
#   Invokes: DashboardState
#   Why: Simplifies dashboard lifecycle without DB dependencies.
# Method: DashboardState.signature
#   Role: Generate a stable hash of plan + params for caching.
#   Called from: runtime orchestrator (stream_dashboard), tests.
#   Invokes: hashlib, json
#   Why: Enables cache hits to skip redundant tool execution.
# Method: DashboardState.find_cached_run
#   Role: Retrieve most recent run matching a signature.
#   Called from: runtime orchestrator.
#   Invokes: list traversal
#   Why: Supports cached reuse without recomputation.
# Function: get_dashboard_store
#   Role: Singleton accessor for DashboardStore.
#   Called from: API routes, runtime helpers.
#   Invokes: DashboardStore constructor (once)
#   Why: Avoids multiple stores per process.
# --- End Dashboard Models Function/Class Map ---
"""
Dashboard State Models

Runtime state management for active dashboards.
"""

from __future__ import annotations
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
import uuid


class RuntimeStatus(str, Enum):
    """Deterministic runtime statuses for dashboards."""
    initialized = "initialized"
    streaming = "streaming"
    awaiting_clarification = "awaiting_clarification"
    complete = "complete"
    error = "error"


class DashboardPlan(BaseModel):
    """Typed dashboard plan persisted between requests."""

    skill_id: str
    skill_name: Optional[str] = None
    layout: Optional[str] = None
    layout_variant: Optional[str] = None
    widgets: List[str] = Field(default_factory=list)
    ticker: Optional[str] = None
    peers: List[str] = Field(default_factory=list)
    tickers: List[str] = Field(default_factory=list)
    metric: str = "Revenue"
    time_range: str = "3M"

    def as_dict(self) -> Dict[str, Any]:
        """Export plan as plain dict for downstream consumers."""
        return self.model_dump()


class RuntimeParams(BaseModel):
    """Typed runtime parameters (mutable during interactions)."""

    ticker: Optional[str] = None
    timeRange: str = "3M"
    peers: List[str] = Field(default_factory=list)
    pending_clarification: Optional[Dict[str, Any]] = None
    clarification_responses: Dict[str, Any] = Field(default_factory=dict)
    clarified: bool = False
    extra: Dict[str, Any] = Field(default_factory=dict)

    def get(self, key: str, default: Any = None) -> Any:
        return self.model_dump().get(key, default)

    class Config:
        extra = "allow"


class DashboardRun(BaseModel):
    """A single data execution run for a dashboard."""
    run_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = Field(default_factory=datetime.utcnow)
    data_json: Dict[str, Any] = Field(default_factory=dict)
    citations_json: List[Dict[str, Any]] = Field(default_factory=list)
    error: Optional[str] = None
    trace_id: Optional[str] = None
    layout_override: Optional[Dict[str, Any]] = None
    plan_signature: Optional[str] = None
    params_signature: Optional[str] = None


class DashboardState(BaseModel):
    """
    Runtime state for an active dashboard.
    
    This is stored server-side and used to:
    - Track the current plan and layout
    - Store execution results
    - Handle user actions with deterministic status transitions
    """
    
    # Identity
    dashboard_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: Optional[str] = None
    
    # Original question
    question: str
    
    # Plan (typed)
    plan: DashboardPlan
    
    # A2UI Layout (generated from plan)
    surface_id: str = "dashboard_main"
    
    # Current parameters (can be modified by actions)
    params: RuntimeParams = Field(default_factory=RuntimeParams)
    
    # Data runs
    runs: List[DashboardRun] = Field(default_factory=list)
    
    # Status
    status: RuntimeStatus = RuntimeStatus.initialized
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Configuration
    catalog_id: str = "financial-standard-v1"
    
    @property
    def plan_json(self) -> Dict[str, Any]:
        """Backward compatible plan dict view."""
        return self.plan.as_dict()

    @plan_json.setter
    def plan_json(self, value: Dict[str, Any]) -> None:
        """Allow legacy callers to replace the plan using dicts."""
        self.plan = DashboardPlan(**value)
        self.updated_at = datetime.utcnow()
    
    @property
    def latest_run(self) -> Optional[DashboardRun]:
        """Get the most recent data run."""
        return self.runs[-1] if self.runs else None
    
    @property
    def latest_data(self) -> Dict[str, Any]:
        """Get data from the most recent run."""
        run = self.latest_run
        return run.data_json if run else {}
    
    def add_run(
        self,
        data: Dict[str, Any],
        citations: List[Dict] = None,
        trace_id: str = None,
        layout_override: Optional[Dict[str, Any]] = None,
        plan_signature: Optional[str] = None,
        params_signature: Optional[str] = None,
    ) -> DashboardRun:
        """Add a new data run with optional trace/layout signatures for caching."""
        run = DashboardRun(
            data_json=data,
            citations_json=citations or [],
            trace_id=trace_id,
            layout_override=layout_override,
            plan_signature=plan_signature,
            params_signature=params_signature,
        )
        self.runs.append(run)
        self.updated_at = datetime.utcnow()
        return run

    def update_plan_fields(self, **updates: Any) -> None:
        """Apply validated field updates to the stored plan."""
        self.plan = self.plan.model_copy(update=updates)
        self.updated_at = datetime.utcnow()
    
    def update_params(self, new_params: Dict[str, Any]) -> None:
        """Update dashboard parameters (e.g., after user action)."""
        merged = self.params.model_dump()
        merged.update(new_params)
        self.params = RuntimeParams(**merged)
        self.updated_at = datetime.utcnow()

    def signature(self) -> str:
        """Compute a stable signature of the current plan/params for caching."""
        import hashlib
        import json

        payload = {
            "plan": self.plan_json,
            "params": self.params.model_dump(),
        }
        digest = hashlib.md5(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()
        return digest

    def find_cached_run(self, signature: str) -> Optional[DashboardRun]:
        """Find the latest run matching a given signature."""
        for run in reversed(self.runs):
            if run.plan_signature == signature or run.params_signature == signature:
                return run
        return None

    def transition(self, new_status: RuntimeStatus) -> None:
        """Apply deterministic state transition guardrails."""
        allowed = {
            RuntimeStatus.initialized: {RuntimeStatus.streaming, RuntimeStatus.awaiting_clarification, RuntimeStatus.error},
            RuntimeStatus.streaming: {RuntimeStatus.awaiting_clarification, RuntimeStatus.complete, RuntimeStatus.error},
            RuntimeStatus.awaiting_clarification: {RuntimeStatus.streaming, RuntimeStatus.error},
            RuntimeStatus.complete: {RuntimeStatus.streaming, RuntimeStatus.error},
            RuntimeStatus.error: set(),
        }
        if new_status not in allowed.get(self.status, set()):
            raise ValueError(f"Invalid transition from {self.status} to {new_status}")
        self.status = new_status
        self.updated_at = datetime.utcnow()
    
    class Config:
        extra = "allow"


class DashboardStore:
    """
    In-memory store for active dashboards.
    
    In production, this would be backed by a database.
    """
    
    def __init__(self):
        self._dashboards: Dict[str, DashboardState] = {}
    
    def create(self, question: str, plan: Dict[str, Any], user_id: str = None) -> DashboardState:
        """Create a new dashboard."""
        state = DashboardState(
            question=question,
            plan=DashboardPlan(**plan),
            user_id=user_id,
            params=RuntimeParams(
                ticker=plan.get("ticker", ""),
                timeRange=plan.get("time_range", "3M"),
                peers=plan.get("peers", []),
            )
        )
        self._dashboards[state.dashboard_id] = state
        return state
    
    def get(self, dashboard_id: str) -> Optional[DashboardState]:
        """Get dashboard by ID."""
        return self._dashboards.get(dashboard_id)
    
    def delete(self, dashboard_id: str) -> bool:
        """Delete a dashboard."""
        if dashboard_id in self._dashboards:
            del self._dashboards[dashboard_id]
            return True
        return False
    
    def list_for_user(self, user_id: str) -> List[DashboardState]:
        """List dashboards for a user."""
        return [d for d in self._dashboards.values() if d.user_id == user_id]


# Singleton store
_store: Optional[DashboardStore] = None


def get_dashboard_store() -> DashboardStore:
    """Get the dashboard store singleton."""
    global _store
    if _store is None:
        _store = DashboardStore()
    return _store
