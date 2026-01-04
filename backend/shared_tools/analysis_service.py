"""
Analysis Tool for shared data access.

Function: execute_analysis_tool — generates formatted narrative analysis.
Called from: backend.generative_ui.agent_v2, backend.conversational_analytics.tools
Invokes: Pure Python formatting logic.
Purpose: Single implementation of analysis formatting for all projects.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

# Tool definition for Claude
ANALYSIS_TOOL_DEFINITION = {
    "name": "generate_analysis",
    "description": """Generate a narrative analysis of financial data.

Use this tool after querying data to provide insights, trends, and key observations.
The analysis should be clear, concise, and actionable for the user.""",
    "input_schema": {
        "type": "object",
        "properties": {
            "data_summary": {
                "type": "string",
                "description": "Summary of the data that was queried"
            },
            "key_findings": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of key findings from the data"
            },
            "comparison_context": {
                "type": "string",
                "description": "Optional context for comparisons (e.g., previous periods, competitors)"
            },
            "trend_direction": {
                "type": "string",
                "enum": ["up", "down", "stable", "mixed"],
                "description": "Overall trend direction observed in the data"
            }
        },
        "required": ["data_summary", "key_findings"]
    }
}


def _format_analysis(
    data_summary: str,
    key_findings: List[str],
    comparison_context: Optional[str] = None,
    trend_direction: Optional[str] = None
) -> Dict[str, Any]:
    """
    Format analysis results.
    
    Function: _format_analysis — structures analysis data.
    Called from: execute_analysis_tool
    Invokes: n/a
    Purpose: Consistent analysis output format.
    """
    # Format key findings as bullet points
    findings_formatted = [f"• {finding}" for finding in key_findings]
    
    analysis = {
        "summary": data_summary,
        "key_insights": key_findings,
        "findings_formatted": "\n".join(findings_formatted),
    }
    
    if trend_direction:
        trend_emoji = {
            "up": "📈",
            "down": "📉", 
            "stable": "➡️",
            "mixed": "↔️"
        }
        analysis["trend"] = {
            "direction": trend_direction,
            "emoji": trend_emoji.get(trend_direction, "")
        }
    
    if comparison_context:
        analysis["comparison_context"] = comparison_context
    
    return analysis


async def execute_analysis_tool(
    data_summary: str,
    key_findings: List[str],
    comparison_context: Optional[str] = None,
    trend_direction: Optional[str] = None
) -> Dict[str, Any]:
    """
    Execute the analysis tool and return formatted results.
    
    Function: execute_analysis_tool — generates narrative analysis.
    Called from: backend.generative_ui.agent_v2, backend.conversational_analytics.tools
    Invokes: _format_analysis
    Purpose: Single analysis implementation for all projects.
    
    Args:
        data_summary: Summary of queried data
        key_findings: List of key findings
        comparison_context: Context for comparisons
        trend_direction: Overall trend direction
        
    Returns:
        Dictionary with success status and analysis
    """
    try:
        analysis = _format_analysis(
            data_summary=data_summary,
            key_findings=key_findings,
            comparison_context=comparison_context,
            trend_direction=trend_direction
        )
        
        return {
            "success": True,
            "analysis": analysis
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


__all__ = ["ANALYSIS_TOOL_DEFINITION", "execute_analysis_tool"]
