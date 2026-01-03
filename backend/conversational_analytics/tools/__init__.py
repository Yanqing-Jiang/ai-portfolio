"""Tools module for Conversational Analytics.

This module re-exports shared tools from backend.shared_tools for backward compatibility.
New code should import directly from shared_tools.
"""
# Re-export shared tools for backward compatibility
from shared_tools import (
    execute_sql_tool,
    execute_news_tool,
    execute_analysis_tool,
)
from shared_tools.sql_executor import SQL_TOOL_DEFINITION
from shared_tools.news_service import NEWS_TOOL_DEFINITION
from shared_tools.analysis_service import ANALYSIS_TOOL_DEFINITION

# Local tools (not shared)
from .tradingview_tool import TRADINGVIEW_TOOL_DEFINITION, execute_tradingview_tool, generate_tradingview_config
from .echarts_tool import ECHARTS_TOOL_DEFINITION, execute_echarts_tool, generate_echarts_spec
from .web_search import WEB_SEARCH_TOOL_DEFINITION, format_web_search_results, is_web_search_tool
from .showcase_tool import SHOWCASE_TOOL_DEFINITION, execute_showcase_tool

# Custom tool definitions for Claude (excludes web_search which is a server tool)
CUSTOM_TOOL_DEFINITIONS = [
    SQL_TOOL_DEFINITION,
    ECHARTS_TOOL_DEFINITION,
    TRADINGVIEW_TOOL_DEFINITION,
    ANALYSIS_TOOL_DEFINITION,
    NEWS_TOOL_DEFINITION,
    SHOWCASE_TOOL_DEFINITION,
]

# Web search is a server tool, handled separately
SERVER_TOOLS = [
    WEB_SEARCH_TOOL_DEFINITION,
]

# Combined tools for Claude API
ALL_TOOLS = CUSTOM_TOOL_DEFINITIONS + SERVER_TOOLS

# Tool executor mapping (custom tools only - web_search runs on Claude's servers)
TOOL_EXECUTORS = {
    "query_database": execute_sql_tool,
    "generate_echarts": execute_echarts_tool,
    "create_tradingview_chart": execute_tradingview_tool,
    "generate_analysis": execute_analysis_tool,
    "get_news_sentiment": execute_news_tool,
    "open_showcase_page": execute_showcase_tool,
}

__all__ = [
    "CUSTOM_TOOL_DEFINITIONS",
    "SERVER_TOOLS",
    "ALL_TOOLS",
    "TOOL_EXECUTORS",
    "SQL_TOOL_DEFINITION",
    "ECHARTS_TOOL_DEFINITION",
    "TRADINGVIEW_TOOL_DEFINITION", 
    "ANALYSIS_TOOL_DEFINITION",
    "NEWS_TOOL_DEFINITION",
    "WEB_SEARCH_TOOL_DEFINITION",
    "execute_sql_tool",
    "execute_echarts_tool",
    "execute_tradingview_tool",
    "execute_analysis_tool",
    "execute_news_tool",
    "generate_tradingview_config",
    "generate_echarts_spec",
    "format_web_search_results",
    "is_web_search_tool",
]
