"""Tools module for Conversational Analytics."""
from .sql_tool import SQL_TOOL_DEFINITION, execute_sql_tool
from .tradingview_tool import TRADINGVIEW_TOOL_DEFINITION, execute_tradingview_tool, generate_tradingview_config
from .analysis_tool import ANALYSIS_TOOL_DEFINITION, execute_analysis_tool
from .echarts_tool import ECHARTS_TOOL_DEFINITION, execute_echarts_tool, generate_echarts_spec
from .web_search import WEB_SEARCH_TOOL_DEFINITION, format_web_search_results, is_web_search_tool
from .news_tool import NEWS_TOOL_DEFINITION, execute_news_tool

# Custom tool definitions for Claude (excludes web_search which is a server tool)
CUSTOM_TOOL_DEFINITIONS = [
    SQL_TOOL_DEFINITION,
    ECHARTS_TOOL_DEFINITION,
    TRADINGVIEW_TOOL_DEFINITION,
    ANALYSIS_TOOL_DEFINITION,
    NEWS_TOOL_DEFINITION,
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
