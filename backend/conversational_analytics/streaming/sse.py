"""SSE streaming utilities for Conversational Analytics."""
from __future__ import annotations

import json
from typing import Any, Dict


def format_sse(event: Dict[str, Any]) -> str:
    """Format a dictionary as an SSE event string.
    
    Args:
        event: Dictionary with 'type' and 'data' keys
        
    Returns:
        SSE formatted string (data: {...}\n\n)
    """
    return f"data: {json.dumps(event)}\n\n"


def format_sse_event(event_type: str, data: Dict[str, Any]) -> str:
    """Format an SSE event with type and data.
    
    Args:
        event_type: Event type (status, thinking, content, etc.)
        data: Event payload
        
    Returns:
        SSE formatted string
    """
    return format_sse({"type": event_type, "data": data})


# Convenience functions for common events
def status_event(message: str) -> str:
    """Create a status event."""
    return format_sse_event("status", {"message": message})


def thinking_event(step: str, status: str, message: str = "") -> str:
    """Create a thinking process event.
    
    Args:
        step: Step identifier (e.g., 'query_analysis', 'sql_generation')
        status: Step status (pending, running, completed, error)
        message: Optional status message
    """
    return format_sse_event("thinking", {"step": step, "status": status, "message": message})


def tool_start_event(tool: str, input_data: Dict[str, Any]) -> str:
    """Create a tool start event."""
    return format_sse_event("tool_start", {"tool": tool, "input": input_data})


def tool_end_event(tool: str, result: Dict[str, Any], success: bool = True) -> str:
    """Create a tool end event."""
    return format_sse_event("tool_end", {"tool": tool, "result": result, "success": success})


def content_event(delta: str) -> str:
    """Create a content streaming event."""
    return format_sse_event("content", {"delta": delta})


def chart_event(config: Dict[str, Any]) -> str:
    """Create a chart configuration event."""
    return format_sse_event("chart", {"config": config})


def data_event(rows: list, columns: list) -> str:
    """Create a data result event."""
    return format_sse_event("data", {"rows": rows, "columns": columns})


def done_event() -> str:
    """Create a stream completion event."""
    return format_sse_event("done", {})


def error_event(message: str, code: str = "error") -> str:
    """Create an error event."""
    return format_sse_event("error", {"message": message, "code": code})
