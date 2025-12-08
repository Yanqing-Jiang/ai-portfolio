"""Web Search Tool wrapper for Conversational Analytics.

Claude's web_search is a server tool that runs on Anthropic's infrastructure.
This module provides the tool definition and result processing.
"""
from __future__ import annotations

from typing import Any, Dict, List

# Web search is a Claude server tool - no custom execution needed
# Just define the tool specification to include in the API call
WEB_SEARCH_TOOL_DEFINITION = {
    "type": "web_search_20250305",
    "name": "web_search",
    "max_uses": 3  # Limit searches per request to control costs
}


def format_web_search_results(tool_result: Dict[str, Any]) -> Dict[str, Any]:
    """Format web search results for display.
    
    Args:
        tool_result: Raw result from Claude's web_search tool
        
    Returns:
        Formatted result with sources and citations
    """
    # The web search tool returns results with citations
    # This helper formats them for the frontend
    sources = []
    
    if isinstance(tool_result, dict):
        content = tool_result.get("content", [])
        if isinstance(content, list):
            for item in content:
                if isinstance(item, dict) and item.get("type") == "web_search_result":
                    sources.append({
                        "title": item.get("title", ""),
                        "url": item.get("url", ""),
                        "snippet": item.get("snippet", ""),
                    })
    
    return {
        "sources": sources,
        "source_count": len(sources)
    }


def is_web_search_tool(tool_name: str) -> bool:
    """Check if a tool name is the web search tool."""
    return tool_name == "web_search"
