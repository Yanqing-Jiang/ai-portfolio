"""
Dashboard Models

Provides DashboardState for runtime state and DashboardStore for persistence.
DashboardPlan now captures typed plans; RuntimeParams + RuntimeStatus guard runtime transitions.
SwapState models support component swap persistence.
"""

from .dashboard_state import (
    DashboardPlan,
    RuntimeParams,
    RuntimeStatus,
    DashboardState,
    DashboardRun,
    DashboardStore,
    get_dashboard_store,
)
from .swap_state import (
    SwapStateSnapshot,
    SwapStateBatch,
    SwapStateSaveRequest,
    SwapStateLoadResponse,
)

__all__ = [
    "DashboardPlan",
    "RuntimeParams",
    "RuntimeStatus",
    "DashboardState",
    "DashboardRun",
    "DashboardStore",
    "get_dashboard_store",
    # Swap state models
    "SwapStateSnapshot",
    "SwapStateBatch",
    "SwapStateSaveRequest",
    "SwapStateLoadResponse",
]
