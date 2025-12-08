# --- Analytics Function/Class Map ---
# Module: analytics.tools.lanes
#   Role: Lane tool wrappers for Canonical Registry integration.
#   Called from: analytics.tools.canonical_registry, analytics.tools.definitions
#   Why: Exposes lane executors as OpenAI/Claude-compatible tools for SINGLE_AGENT and MULTI_AGENT modes.
# --- End Analytics Function/Class Map ---
"""
Lane tool wrappers that expose lane executors as callable tools.

These wrappers provide a tool-callable interface for lane executors,
enabling them to be registered in the Canonical Tool Registry and
invoked by Single Agent and Multi-Agent flows.
"""
from .sql_lane_wrapper import invoke_sql_lane, SQL_LANE_TOOL_SCHEMA
from .chart_lane_wrapper import invoke_chart_lane, CHART_LANE_TOOL_SCHEMA
from .analysis_lane_wrapper import invoke_analysis_lane, ANALYSIS_LANE_TOOL_SCHEMA
from .accessory_lane_wrapper import (
    invoke_web_lane,
    invoke_market_lane,
    WEB_LANE_TOOL_SCHEMA,
    MARKET_LANE_TOOL_SCHEMA,
)

__all__ = [
    "invoke_sql_lane",
    "invoke_chart_lane",
    "invoke_analysis_lane",
    "invoke_web_lane",
    "invoke_market_lane",
    "SQL_LANE_TOOL_SCHEMA",
    "CHART_LANE_TOOL_SCHEMA",
    "ANALYSIS_LANE_TOOL_SCHEMA",
    "WEB_LANE_TOOL_SCHEMA",
    "MARKET_LANE_TOOL_SCHEMA",
]
