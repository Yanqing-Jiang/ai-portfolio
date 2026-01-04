"""
Shared data access and analysis tools.

This module provides dependency-light primitives that can be used by both:
- backend/generative_ui (A2UI dashboards)
- backend/conversational_analytics (Claude-based agent)

Function: Re-exports core data access functions to decouple project dependencies.
Called from: backend.generative_ui.agent_v2, backend.conversational_analytics.tools
Invokes: Individual tool implementations in this package.
Purpose: Create a clean boundary so A2UI does not depend on conversational_analytics.
"""

from .sql_executor import execute_sql_tool
from .news_service import execute_news_tool
from .analysis_service import execute_analysis_tool
from .sdk_helpers import (
    CLAUDE_DIR,
    get_allowed_tools,
    load_project_settings,
    should_use_sdk_assets,
)

__all__ = [
    "execute_sql_tool",
    "execute_news_tool",
    "execute_analysis_tool",
    "CLAUDE_DIR",
    "get_allowed_tools",
    "load_project_settings",
    "should_use_sdk_assets",
]
