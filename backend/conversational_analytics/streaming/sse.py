"""SSE streaming utilities for Conversational Analytics."""
from __future__ import annotations

import json
from contextvars import ContextVar
from typing import Any, Dict, Optional

_run_id_ctx: ContextVar[Optional[str]] = ContextVar("run_id_ctx", default=None)
_step_id_ctx: ContextVar[Optional[str]] = ContextVar("step_id_ctx", default=None)


def _safe_dumps(payload: Any) -> str:
    """JSON dump with robust fallback to string conversion."""
    try:
        return json.dumps(payload, default=str)
    except Exception:
        # Last-resort stringify to avoid crashing the stream
        return json.dumps(str(payload))


def format_sse(event: Dict[str, Any]) -> str:
    """Format a dictionary as an SSE event string.
    
    Args:
        event: Dictionary with 'type' and 'data' keys
        
    Returns:
        SSE formatted string (data: {...}\n\n)
    """
    return f"data: {_safe_dumps(event)}\n\n"


def format_sse_event(event_type: str, data: Dict[str, Any]) -> str:
    """Format an SSE event with type and data.
    
    Args:
        event_type: Event type (status, thinking, content, etc.)
        data: Event payload
        
    Returns:
        SSE formatted string
    """
    payload = {"type": event_type, "data": data}
    run_id = _run_id_ctx.get()
    step_id = _step_id_ctx.get()
    if run_id and isinstance(payload.get("data"), dict):
        payload["data"]["run_id"] = run_id
    if step_id and isinstance(payload.get("data"), dict):
        payload["data"]["step_id"] = step_id
    return format_sse(payload)


def set_run_context(run_id: Optional[str], step_id: Optional[str] = None) -> None:
    """Function: set_run_context — sets per-run contextvars so SSE events carry tracing metadata.
    Called from: agent.run_with_tools at run start and teardown.
    Invokes: ContextVar.set for run_id and step_id.
    Purpose: Adds run_id/step_id to every event without changing individual call sites."""
    _run_id_ctx.set(run_id)
    _step_id_ctx.set(step_id)


def set_step_context(step_id: Optional[str]) -> None:
    """Function: set_step_context — updates the current step identifier for downstream SSE events."""
    _step_id_ctx.set(step_id)


def clear_run_context() -> None:
    """Function: clear_run_context — clears tracing context after a run completes."""
    _run_id_ctx.set(None)
    _step_id_ctx.set(None)


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


def data_event(rows: list, columns: list, sql: str | None = None) -> str:
    """Create a data result event.
    
    Args:
        rows: List of row dictionaries from query result
        columns: List of column names
        sql: Optional SQL statement that was executed (for transparency widget)
    
    Returns:
        SSE formatted data event string
    """
    payload = {"rows": rows, "columns": columns}
    if sql:
        payload["sql"] = sql
    return format_sse_event("data", payload)


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


def html_artifact_event(url: str, title: str, description: str) -> str:
    """Function: html_artifact_event — emits a link to an HTML artifact for inline rendering.
    Called from: agent when the showcase tool returns a URL.
    Invokes: format_sse_event to broadcast the artifact metadata to the frontend.
    Purpose: Allow the UI to embed the static showcase page without relying on Claude text alone."""
    return format_sse_event("html_artifact", {
        "url": url,
        "title": title,
        "description": description,
    })


def agent_event(agent_id: str, name: str, role: str) -> str:
    """Create an agent activation event so the UI can show which agent is working."""
    return format_sse_event("agent", {"id": agent_id, "name": name, "role": role})


def handoff_event(from_agent: str, to_agent: str, reason: str = "") -> str:
    """Create a handoff event to surface supervisor-to-specialist delegation."""
    payload = {"from": from_agent, "to": to_agent}
    if reason:
        payload["reason"] = reason
    return format_sse_event("handoff", payload)


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


# ============================================================================
# Process Visualization Events
# ============================================================================

def process_node_event(
    node_id: str,
    node_type: str,
    label: str,
    status: str = "pending",
    parent_id: str | None = None,
    data: dict | None = None,
    description: str = "",
) -> str:
    """Create a process node event for agent decision visualization.
    
    Args:
        node_id: Unique ID for this node in the process graph
        node_type: Type of node (decision, action, tool, agent, routing, output)
        label: Display label for the node
        status: Node status (pending, running, completed, error, skipped)
        parent_id: ID of parent node (for hierarchy/connections)
        data: Optional additional data for the node
        description: Optional detailed description of what this node does
    
    Returns:
        SSE formatted process_node event string
    """
    import time
    payload = {
        "node_id": node_id,
        "node_type": node_type,
        "label": label,
        "status": status,
        "timestamp": time.time(),
    }
    if parent_id:
        payload["parent_id"] = parent_id
    if data:
        payload["data"] = data
    if description:
        payload["description"] = description
    return format_sse_event("process_node", payload)


def process_edge_event(
    from_node: str,
    to_node: str,
    edge_type: str = "default",
    label: str = "",
    animated: bool = False,
) -> str:
    """Create a process edge event to connect nodes in the visualization.
    
    Args:
        from_node: Source node ID
        to_node: Target node ID
        edge_type: Edge type (default, decision_yes, decision_no, handoff)
        label: Optional edge label
        animated: Whether to animate the edge flow
    
    Returns:
        SSE formatted process_edge event string
    """
    payload = {
        "from_node": from_node,
        "to_node": to_node,
        "edge_type": edge_type,
        "animated": animated,
    }
    if label:
        payload["label"] = label
    return format_sse_event("process_edge", payload)


def process_update_event(
    node_id: str,
    status: str,
    summary: str = "",
    data: dict | None = None,
) -> str:
    """Update an existing process node's status.
    
    Args:
        node_id: ID of the node to update
        status: New status (pending, running, completed, error, skipped)
        summary: Optional summary text
        data: Optional additional data
    
    Returns:
        SSE formatted process_update event string
    """
    import time
    payload = {
        "node_id": node_id,
        "status": status,
        "timestamp": time.time(),
    }
    if summary:
        payload["summary"] = summary
    if data:
        payload["data"] = data
    return format_sse_event("process_update", payload)


def process_clear_event() -> str:
    """Clear all process visualization nodes for a new request.
    
    Returns:
        SSE formatted process_clear event string
    """
    return format_sse_event("process_clear", {})