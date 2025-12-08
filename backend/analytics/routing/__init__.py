# --- Analytics Function/Class Map ---
# Module: analytics.routing
#   Role: Exports centralized FollowUpRoute enum and banner helpers for agent-driven routing.
#   Called from: analytics.flows.*, tests.analytics.*
#   Why: Single import point for routing primitives used across flows.
# --- End Analytics Function/Class Map ---
"""
Analytics routing module.

Exports FollowUpRoute enum and banner helpers for agent-driven lane planning.
The heuristic FollowUpClassifier has been deprecated in favor of agent runtime decisions.
"""
from .follow_up_route import (
    FollowUpRoute,
    FOLLOW_UP_BANNERS,
    get_banner_for_route,
    route_requires_market_web,
)

__all__ = [
    "FollowUpRoute",
    "FOLLOW_UP_BANNERS",
    "get_banner_for_route",
    "route_requires_market_web",
]
