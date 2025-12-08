# --- Analytics Function/Class Map ---
# Class: FollowUpRoute
#   Role: Centralized enum for follow-up routing decisions made by agent runtime.
#   Called from: analytics.flows.multi_agent, analytics.flows.planner_executor, analytics.flows.single_agent_tools, analytics.flows.workflow, +tests
#   Collaborators: Internal helpers only
#   Why: Single source of truth for route values and banner config used by all flows.
# --- End Analytics Function/Class Map ---
"""
Centralized FollowUpRoute enum and banner configuration.

Agent runtime selects a route during lane planning (fresh runs) or revision routing;
downstream flows derive accessory requirements from the chosen route.
"""
from __future__ import annotations

from enum import Enum
from typing import Dict


class FollowUpRoute(str, Enum):
    """
    Enum representing the routing decision for analytics follow-up runs.

    - FULL_PIPELINE: Run SQL, chart, analysis, market, and web lanes from scratch.
    - REUSE_SQL: Skip SQL generation; update chart/analysis using cached dataset.
    - STOCK_ONLY: Refresh market/stock data only; reuse other cached artifacts.
    - CHART_ONLY: Revision targets chart lane; market/web optional.
    - NARRATIVE_ONLY: Revision targets analysis lane; market/web required.
    """
    STOCK_ONLY = "stock_only"
    REUSE_SQL = "reuse_sql"
    FULL_PIPELINE = "full_pipeline"
    CHART_ONLY = "chart_only"
    NARRATIVE_ONLY = "narrative_only"


FOLLOW_UP_BANNERS: Dict[FollowUpRoute, Dict[str, str]] = {
    FollowUpRoute.FULL_PIPELINE: {
        "title": "Fresh Run Scheduled",
        "message": "Running SQL, charts, and narrative again to deliver a fully refreshed answer.",
    },
    FollowUpRoute.REUSE_SQL: {
        "title": "Reusing Last Dataset",
        "message": "Skipping the SQL rerun - updating visuals and narrative on top of the validated table.",
    },
    FollowUpRoute.STOCK_ONLY: {
        "title": "Market Snapshot Only",
        "message": "Pulling fresh price data while charts and analysis stay pinned to the prior run.",
    },
    FollowUpRoute.CHART_ONLY: {
        "title": "Chart Revision",
        "message": "Updating the chart based on your feedback; market/web context is optional.",
    },
    FollowUpRoute.NARRATIVE_ONLY: {
        "title": "Narrative Revision",
        "message": "Refreshing the analysis narrative; market/web context will be included.",
    },
}


def get_banner_for_route(route: FollowUpRoute) -> Dict[str, str]:
    """
    Return the banner config for a given route, falling back to FULL_PIPELINE.

    Function: get_banner_for_route
      Role: Retrieves banner title/message for a FollowUpRoute.
      Called from: analytics.flows.planner_executor, analytics.flows.single_agent_tools, analytics.flows.multi_agent
      Invokes: Internal dict lookup
      Why: Centralizes banner lookup so flows don't duplicate FOLLOW_UP_BANNERS access.
    """
    return FOLLOW_UP_BANNERS.get(route, FOLLOW_UP_BANNERS[FollowUpRoute.FULL_PIPELINE])


def route_requires_market_web(route: FollowUpRoute, *, is_revision: bool = False) -> bool:
    """
    Determine whether market/web lanes are required for the given route.

    Function: route_requires_market_web
      Role: Encodes the rule that market/web are required for narrative/analysis revisions but optional for chart-only.
      Called from: analytics.flows.planner_executor, analytics.flows.single_agent_tools, analytics.flows.multi_agent
      Invokes: None
      Why: Single source of truth for accessory lane requirements.
    """
    if not is_revision:
        # Fresh runs always schedule market/web
        return True
    # Revision runs: market/web required except for pure chart revisions
    if route == FollowUpRoute.CHART_ONLY:
        return False
    return True
