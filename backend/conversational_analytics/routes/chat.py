"""Chat routes for Conversational Analytics API."""
from __future__ import annotations

import logging
import json
from pathlib import Path
from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.responses import StreamingResponse, FileResponse

from ..agent import (
    ConversationalAnalyticsAgent,
    MissingDependencyError,
    get_conversational_analytics_agent,
)
from ..supervisor import SupervisorOrchestrator, get_supervisor_orchestrator
from ..models import ChatRequest, SelectionReply
from ..memory import session_store
from rate_limiter import conversational_analytics_rate_limit

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/conv-analytics", tags=["conversational-analytics"])


def _get_agent() -> ConversationalAnalyticsAgent:
    """Function: _get_agent — used by all Conversational Analytics endpoints to fetch the singleton agent.
    Called from: stream_chat and chat handlers.
    Invokes: get_conversational_analytics_agent to lazily create the agent.
    Purpose: Surface missing dependency errors as HTTP 503 instead of silently skipping routes."""
    try:
        return get_conversational_analytics_agent()
    except MissingDependencyError as exc:
        logger.error("Conversational Analytics unavailable: %s", exc)
        raise HTTPException(status_code=503, detail=str(exc))


def _get_supervisor() -> SupervisorOrchestrator:
    """Function: _get_supervisor — fetches the supervisor orchestrator for multi-agent routing.
    Called from: stream_chat and chat when agent_mode is supplied.
    Invokes: get_supervisor_orchestrator to reuse a singleton supervisor."""
    try:
        return get_supervisor_orchestrator()
    except MissingDependencyError as exc:
        logger.error("Conversational Analytics unavailable (supervisor): %s", exc)
        raise HTTPException(status_code=503, detail=str(exc))


@router.post("/stream")
async def stream_chat(
    request: ChatRequest,
    fastapi_request: Request,
    _: None = Depends(conversational_analytics_rate_limit),
):
    """Function: stream_chat — called by components/conversationalAnalytics/hooks/useSSEStream.ts to stream Claude responses.
    Invokes: supervisor.run_with_tools when agent_mode provided, otherwise _get_agent().run_with_tools.
    Purpose: Primary streaming endpoint for conversational analytics with rate limiting."""
    use_supervisor = request.agent_mode is not None
    supervisor = _get_supervisor() if use_supervisor else None
    agent = _get_agent() if not use_supervisor else None

    async def event_generator():
        if supervisor:
            async for event in supervisor.run(request.message, request.session_id, request.agent_mode or "auto"):
                if event.startswith("data: "):
                    try:
                        parsed = json.loads(event[6:].strip())
                        run_id = parsed.get("data", {}).get("run_id")
                        if run_id:
                            session_store.append_run_event(request.session_id, run_id, parsed)
                    except json.JSONDecodeError:
                        pass
                yield event
        else:
            async for event in agent.run_with_tools(request.message, request.session_id):  # type: ignore
                if event.startswith("data: "):
                    try:
                        parsed = json.loads(event[6:].strip())
                        run_id = parsed.get("data", {}).get("run_id")
                        if run_id:
                            session_store.append_run_event(request.session_id, run_id, parsed)
                    except json.JSONDecodeError:
                        pass
                yield event
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        }
    )


@router.post("/chat")
async def chat(
    request: ChatRequest,
    fastapi_request: Request,
    _: None = Depends(conversational_analytics_rate_limit),
):
    """Function: chat — used by non-SSE clients for conversational analytics.
    Invokes: supervisor.run when agent_mode is provided, else _get_agent().run_with_tools, and aggregates the streamed events.
    Purpose: Provide a single-response alternative to the streaming endpoint."""
    use_supervisor = request.agent_mode is not None
    supervisor = _get_supervisor() if use_supervisor else None
    agent = _get_agent() if not use_supervisor else None
    events = []
    content_parts = []
    chart_config = None
    data_result = None
    
    event_source = (
        supervisor.run(request.message, request.session_id, request.agent_mode or "auto")
        if supervisor
        else agent.run_with_tools(request.message, request.session_id)  # type: ignore
    )
    
    async for event in event_source:
        # Parse the SSE event
        if event.startswith("data: "):
            try:
                parsed = json.loads(event[6:].strip())
                events.append(parsed)
                run_id = parsed.get("data", {}).get("run_id")
                if run_id:
                    session_store.append_run_event(request.session_id, run_id, parsed)
                
                if parsed.get("type") == "content":
                    content_parts.append(parsed.get("data", {}).get("delta", ""))
                elif parsed.get("type") == "chart":
                    chart_config = parsed.get("data", {}).get("config")
                elif parsed.get("type") == "data":
                    data_result = parsed.get("data")
            except json.JSONDecodeError:
                pass
    
    return {
        "message": "".join(content_parts),
        "chart": chart_config,
        "data": data_result,
        "session_id": request.session_id
    }


@router.get("/sessions/{session_id}/history")
async def get_session_history(
    session_id: str,
    fastapi_request: Request,
    _: None = Depends(conversational_analytics_rate_limit),
):
    """Function: get_session_history — used by conversational analytics clients to retrieve stored context.
    Invokes: session_store to fetch messages.
    Purpose: Allow clients to reload prior chat turns for a session."""
    session = session_store.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    return {
        "session_id": session_id,
        "messages": [
            {
                "role": msg.role,
                "content": msg.content,
                "timestamp": msg.timestamp
            }
            for msg in session.messages
        ],
        "created_at": session.created_at
    }


@router.delete("/sessions/{session_id}")
async def clear_session(
    session_id: str,
    fastapi_request: Request,
    _: None = Depends(conversational_analytics_rate_limit),
):
    """Function: clear_session — invoked by clients when they need a fresh conversational analytics run.
    Invokes: session_store.delete to clear cached history.
    Purpose: Support session lifecycle management for conversational analytics."""
    deleted = session_store.delete(session_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Session not found")
    
    return {"message": "Session cleared", "session_id": session_id}


@router.get("/health")
async def health_check():
    """Function: health_check — called by monitors and frontend readiness checks.
    Invokes: lightweight status response only.
    Purpose: Advertise that conversational analytics routes are mounted."""
    return {"status": "healthy", "service": "conversational-analytics"}


@router.post("/cancel/{session_id}")
async def cancel_run(
    session_id: str,
    fastapi_request: Request,
    _: None = Depends(conversational_analytics_rate_limit),
):
    """Function: cancel_run — kill switch endpoint to stop an in-flight conversational analytics run.
    Invokes: session_store.request_cancel to set a cancellation flag consumed by the agent loop.
    Purpose: Provide frontend/ops a way to halt long or unwanted runs."""
    ok = session_store.request_cancel(session_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"status": "cancel_requested", "session_id": session_id}


@router.post("/selection")
async def submit_selection(
    reply: SelectionReply,
    fastapi_request: Request,
    _: None = Depends(conversational_analytics_rate_limit),
):
    """Function: submit_selection — called by frontend when user makes a HITL choice.
    Invokes: session_store to validate pending selection and merge chosen slots.
    Purpose: Accept user selection and resume the agent with resolved slots."""
    session = session_store.get(reply.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    pending = session.get_pending_selection()
    if not pending:
        raise HTTPException(status_code=400, detail="No pending selection request")
    
    if pending.request_id != reply.request_id:
        raise HTTPException(status_code=400, detail="Request ID mismatch")
    
    # Resolve the selected option
    selected_payload = {}
    if reply.option_id:
        # Find the selected option
        for opt in pending.options:
            if opt.get("id") == reply.option_id:
                selected_payload = opt.get("payload", {})
                break
        else:
            raise HTTPException(status_code=400, detail="Invalid option ID")
    elif reply.custom_value:
        # Custom free-text value - interpret it (for now, store as raw)
        selected_payload = {"custom_value": reply.custom_value}
    else:
        raise HTTPException(status_code=400, detail="No option or custom value provided")
    
    # Merge selected slots with already-resolved slots
    final_slots = {**pending.resolved_slots, **selected_payload}
    
    # Store the resolved slots in session context for agent to use
    session.update_context("resolved_slots", final_slots)
    session.update_context("skill_id", pending.skill_id)
    
    # Add a synthetic user message with the selection for conversation continuity
    selection_summary = reply.option_id or reply.custom_value
    session.add_message(
        "user",
        f"[Selected: {selection_summary}]"
    )
    
    # Clear the pending selection
    session.clear_pending_selection()
    
    logger.info("Selection submitted: session=%s, request=%s, option=%s",
                reply.session_id, reply.request_id, reply.option_id or "custom")
    
    return {
        "status": "accepted",
        "session_id": reply.session_id,
        "resolved_slots": final_slots,
    }


@router.get("/showcase")
async def serve_showcase_page():
    """Function: serve_showcase_page — called from the `open_showcase_page` tool and docs links to surface the static HTML showcase.
    Called from: showcase tool response (agent.run_with_tools) and direct browser hits to /api/conv-analytics/showcase.
    Invokes: FileResponse streaming of backend/conversational_analytics/static/showcase.html.
    Purpose: Provide a public, auth-free showcase page that can be embedded or opened directly without Supabase JWT."""
    static_path = Path(__file__).parent.parent / "static" / "showcase.html"
    if not static_path.exists():
        raise HTTPException(status_code=404, detail="Showcase not found")
    return FileResponse(path=static_path, media_type="text/html")
