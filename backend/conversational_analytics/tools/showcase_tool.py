"""Showcase tool that returns the static project showcase URL for embedding."""

from __future__ import annotations

from typing import Any, Dict

# Tool definition exposed to Claude
SHOWCASE_TOOL_DEFINITION = {
    "name": "open_showcase_page",
    "description": (
        "Returns the URL to the interactive project showcase page that explains the Next Gen Analytics "
        "agent architecture, single vs multi-agent flows, and how skills.md files work. "
        "Call this once to share the link with the user."
    ),
    "input_schema": {"type": "object", "properties": {}, "required": []},
}


async def execute_showcase_tool() -> Dict[str, Any]:
    """Function: execute_showcase_tool — called from agent.run_with_tools when Claude invokes open_showcase_page.
    Called from: ConversationalAnalyticsAgent.run_with_tools tool dispatch.
    Invokes: No downstream modules; returns static metadata for the showcase.
    Purpose: Provide a safe, non-data tool that surfaces the static showcase HTML for demos."""
    return {
        "success": True,
        "url": "/api/conv-analytics/showcase",
        "title": "Project Showcase",
        "description": "Interactive overview of the Next Gen Analytics agents, flows, and skills.",
    }

