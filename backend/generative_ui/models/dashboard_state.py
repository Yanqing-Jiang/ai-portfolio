"""
Dashboard State Models

Runtime state management for active dashboards.
"""

from __future__ import annotations
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
import uuid


class DashboardRun(BaseModel):
    """A single data execution run for a dashboard."""
    run_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = Field(default_factory=datetime.utcnow)
    data_json: Dict[str, Any] = Field(default_factory=dict)
    citations_json: List[Dict[str, Any]] = Field(default_factory=list)
    error: Optional[str] = None


class DashboardState(BaseModel):
    """
    Runtime state for an active dashboard.
    
    This is stored server-side and used to:
    - Track the current plan and layout
    - Store execution results
    - Handle user actions
    """
    
    # Identity
    dashboard_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: Optional[str] = None
    
    # Original question
    question: str
    
    # Plan (from Claude)
    plan_json: Dict[str, Any]
    
    # A2UI Layout (generated from plan)
    surface_id: str = "dashboard_main"
    
    # Current parameters (can be modified by actions)
    params: Dict[str, Any] = Field(default_factory=dict)
    
    # Data runs
    runs: List[DashboardRun] = Field(default_factory=list)
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Configuration
    catalog_id: str = "financial-standard-v1"
    
    @property
    def latest_run(self) -> Optional[DashboardRun]:
        """Get the most recent data run."""
        return self.runs[-1] if self.runs else None
    
    @property
    def latest_data(self) -> Dict[str, Any]:
        """Get data from the most recent run."""
        run = self.latest_run
        return run.data_json if run else {}
    
    def add_run(self, data: Dict[str, Any], citations: List[Dict] = None) -> DashboardRun:
        """Add a new data run."""
        run = DashboardRun(
            data_json=data,
            citations_json=citations or []
        )
        self.runs.append(run)
        self.updated_at = datetime.utcnow()
        return run
    
    def update_params(self, new_params: Dict[str, Any]) -> None:
        """Update dashboard parameters (e.g., after user action)."""
        self.params.update(new_params)
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
            plan_json=plan,
            user_id=user_id,
            params={
                "ticker": plan.get("ticker", ""),
                "timeRange": plan.get("time_range", "3M"),
                "peers": plan.get("peers", []),
            }
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
