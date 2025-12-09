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


def skill_event(skill_id: str, name: str, download_url: str) -> str:
    """Create a skill selection event for client display and download links."""
    return format_sse_event("skill", {"id": skill_id, "name": name, "download_url": download_url})


def news_event(articles: list, ticker: str, aggregate_sentiment: float, aggregate_label: str) -> str:
    """Create a news/citations event.
    
    Args:
        articles: List of news articles with title, summary, url, source, sentiment
        ticker: Stock ticker symbol
        aggregate_sentiment: Average sentiment score
        aggregate_label: Human-readable sentiment label
    
    Returns:
        SSE formatted news event string
    """
    return format_sse_event("news", {
        "articles": articles,
        "ticker": ticker,
        "aggregate_sentiment": aggregate_sentiment,
        "aggregate_label": aggregate_label,
    })


def plan_event(steps: list[dict]) -> str:
    """Create a plan event with ordered steps."""
    return format_sse_event("plan", {"steps": steps})


def plan_update_event(step_id: str, status: str, summary: str = "") -> str:
    """Update a specific plan step status."""
    return format_sse_event("plan_update", {"step_id": step_id, "status": status, "summary": summary})


def done_event() -> str:
    """Create a stream completion event."""
    return format_sse_event("done", {})


def error_event(message: str, code: str = "error", details: str = "") -> str:
    """Create an error event with optional stack trace/details for debug mode."""
    data = {"message": message, "code": code}
    if details:
        data["details"] = details
    return format_sse_event("error", data)


def debug_event(category: str, message: str, data: dict | None = None) -> str:
    """Create a debug event for verbose activity tracing.
    
    Args:
        category: Debug category (e.g., 'session', 'api', 'tool', 'agent')
        message: Human-readable debug message
        data: Optional additional debug data
    
    Returns:
        SSE formatted debug event string
    """
    import time
    payload = {
        "category": category,
        "message": message,
        "timestamp": time.time(),
    }
    if data:
        payload["data"] = data
    return format_sse_event("debug", payload)


def selection_request_event(
    request_id: str,
    title: str,
    prompt: str,
    options: list[dict],
    allow_custom: bool = True,
    timeout_seconds: int = 60,
) -> str:
    """Create a selection request event for HITL slot resolution.
    
    Args:
        request_id: Unique ID for this selection request (used to match replies)
        title: Card title (e.g., "Confirm analysis options")
        prompt: Short prompt text (e.g., "Pick the margin type")
        options: List of option dicts with id, label, description, and payload
        allow_custom: Whether to show a free-text "Other" input option
        timeout_seconds: How long to wait before auto-cancelling
    
    Returns:
        SSE formatted selection_request event string
    """
    return format_sse_event("selection_request", {
        "request_id": request_id,
        "title": title,
        "prompt": prompt,
        "options": options,
        "allow_custom": allow_custom,
        "timeout_seconds": timeout_seconds,
    })


def selection_timeout_event(request_id: str) -> str:
    """Create a selection timeout event (request expired without user response)."""
    return format_sse_event("selection_timeout", {"request_id": request_id})


def selection_cancelled_event(request_id: str) -> str:
    """Create a selection cancelled event (user dismissed or agent cancelled)."""
    return format_sse_event("selection_cancelled", {"request_id": request_id})