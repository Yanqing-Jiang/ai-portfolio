"""
MCP tool definitions for Claude Agent SDK integration.

Module: mcp_tools.py
Role: Wraps existing shared_tools as SDK-compatible MCP tools using the @tool decorator.
Called from: sdk_wrapper.py, agent_v2.py
Invokes: backend.shared_tools (sql_tool, news_tool, analysis_tool)
Why: The Claude Agent SDK uses MCP (Model Context Protocol) tools. This module 
     bridges our existing tool implementations to the SDK's expected format.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Awaitable, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

# Try importing Claude Agent SDK's @tool decorator
try:
    from claude_agent_sdk import tool as sdk_tool
    SDK_TOOL_AVAILABLE = True
except ImportError:
    SDK_TOOL_AVAILABLE = False
    sdk_tool = None

# Import existing shared tools
from backend.shared_tools.sql_executor import execute_sql_tool
from backend.shared_tools.news_service import execute_news_tool
from backend.shared_tools.analysis_service import execute_analysis_tool


def _make_mcp_response(
    text: str,
    is_error: bool = False,
) -> Dict[str, Any]:
    """Create a properly formatted MCP tool response."""
    response = {
        "content": [{
            "type": "text",
            "text": text,
        }]
    }
    if is_error:
        response["is_error"] = True
    return response


# ============================================================================
# SDK MCP Tool Definitions (only created when SDK is available)
# ============================================================================

if SDK_TOOL_AVAILABLE and sdk_tool:
    
    @sdk_tool(
        "query_database",
        "Execute a SQL query against the financial database. Returns structured data with columns and rows.",
        {"query": str, "reason": str}
    )
    async def query_database_mcp(args: Dict[str, Any]) -> Dict[str, Any]:
        """
        MCP wrapper for SQL query execution.
        
        Function: query_database_mcp
        Role: Execute SQL queries against the financial database.
        Called from: Claude Agent SDK skill execution.
        Invokes: backend.shared_tools.sql_tool.execute_sql_tool
        Why: Enables Claude to query financial data using natural SQL.
        """
        try:
            query = args.get("query", "")
            reason = args.get("reason", "A2UI skill execution")
            
            result = await execute_sql_tool(query, reason=reason)
            
            if result.get("success"):
                return _make_mcp_response(json.dumps({
                    "success": True,
                    "columns": result.get("columns", []),
                    "rows": result.get("rows", []),
                    "row_count": result.get("row_count", 0),
                }))
            else:
                return _make_mcp_response(
                    f"SQL Error: {result.get('error', 'Unknown error')}",
                    is_error=True
                )
        except Exception as e:
            logger.error(f"query_database_mcp failed: {e}")
            return _make_mcp_response(f"Error: {str(e)}", is_error=True)

    @sdk_tool(
        "get_news_sentiment",
        "Fetch recent news articles with sentiment analysis for a stock ticker. Returns articles with titles, summaries, and sentiment scores.",
        {"ticker": str, "limit": int}
    )
    async def get_news_sentiment_mcp(args: Dict[str, Any]) -> Dict[str, Any]:
        """
        MCP wrapper for news sentiment retrieval.
        
        Function: get_news_sentiment_mcp
        Role: Fetch news with sentiment for a ticker.
        Called from: Claude Agent SDK skill execution.
        Invokes: backend.shared_tools.news_tool.execute_news_tool
        Why: Provides market news context for price movement analysis.
        """
        try:
            ticker = args.get("ticker", "")
            limit = args.get("limit", 5)
            
            result = await execute_news_tool(ticker=ticker, limit=limit)
            
            if result.get("success"):
                return _make_mcp_response(json.dumps({
                    "success": True,
                    "articles": result.get("articles", []),
                    "aggregate_sentiment": result.get("aggregate_sentiment"),
                    "aggregate_label": result.get("aggregate_label"),
                }))
            else:
                return _make_mcp_response(
                    f"News Error: {result.get('error', 'Unknown error')}",
                    is_error=True
                )
        except Exception as e:
            logger.error(f"get_news_sentiment_mcp failed: {e}")
            return _make_mcp_response(f"Error: {str(e)}", is_error=True)

    @sdk_tool(
        "generate_analysis",
        "Generate an AI-powered analysis narrative from financial data. Returns a concise summary with key insights.",
        {"data_summary": str, "key_findings": list, "trend_direction": str}
    )
    async def generate_analysis_mcp(args: Dict[str, Any]) -> Dict[str, Any]:
        """
        MCP wrapper for AI analysis generation.
        
        Function: generate_analysis_mcp
        Role: Generate narrative analysis from data.
        Called from: Claude Agent SDK skill execution.
        Invokes: backend.shared_tools.analysis_tool.execute_analysis_tool
        Why: Provides human-readable insights for dashboard panels.
        """
        try:
            data_summary = args.get("data_summary", "")
            key_findings = args.get("key_findings", [])
            trend_direction = args.get("trend_direction", "neutral")
            
            result = await execute_analysis_tool(
                data_summary=data_summary,
                key_findings=key_findings,
                trend_direction=trend_direction,
            )
            
            if result.get("success"):
                analysis = result.get("analysis", {})
                return _make_mcp_response(json.dumps({
                    "success": True,
                    "summary": analysis.get("summary", ""),
                    "sentiment": analysis.get("sentiment", "neutral"),
                    "confidence": analysis.get("confidence", 0.5),
                }))
            else:
                return _make_mcp_response(
                    f"Analysis Error: {result.get('error', 'Unknown error')}",
                    is_error=True
                )
        except Exception as e:
            logger.error(f"generate_analysis_mcp failed: {e}")
            return _make_mcp_response(f"Error: {str(e)}", is_error=True)

    # Export all MCP tools
    A2UI_MCP_TOOLS: List[Any] = [
        query_database_mcp,
        get_news_sentiment_mcp,
        generate_analysis_mcp,
    ]
    
    # Tool names for allowed_tools configuration
    A2UI_MCP_TOOL_NAMES: List[str] = [
        "mcp__a2ui__query_database",
        "mcp__a2ui__get_news_sentiment",
        "mcp__a2ui__generate_analysis",
    ]

else:
    # SDK not available - provide empty lists
    A2UI_MCP_TOOLS: List[Any] = []
    A2UI_MCP_TOOL_NAMES: List[str] = []


# ============================================================================
# Fallback Tool Executors (for non-SDK path)
# ============================================================================

async def execute_query_database(
    query: str,
    reason: str = "A2UI execution",
) -> Dict[str, Any]:
    """Direct tool execution without SDK wrapper."""
    return await execute_sql_tool(query, reason=reason)


async def execute_get_news_sentiment(
    ticker: str,
    limit: int = 5,
) -> Dict[str, Any]:
    """Direct tool execution without SDK wrapper."""
    return await execute_news_tool(ticker=ticker, limit=limit)


async def execute_generate_analysis(
    data_summary: str,
    key_findings: List[str],
    trend_direction: str = "neutral",
) -> Dict[str, Any]:
    """Direct tool execution without SDK wrapper."""
    return await execute_analysis_tool(
        data_summary=data_summary,
        key_findings=key_findings,
        trend_direction=trend_direction,
    )


__all__ = [
    "SDK_TOOL_AVAILABLE",
    "A2UI_MCP_TOOLS",
    "A2UI_MCP_TOOL_NAMES",
    "execute_query_database",
    "execute_get_news_sentiment",
    "execute_generate_analysis",
]
