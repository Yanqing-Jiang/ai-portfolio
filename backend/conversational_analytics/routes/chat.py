"""Chat routes for Conversational Analytics API."""
from __future__ import annotations

import logging
from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.responses import StreamingResponse

from ..agent import (
    ConversationalAnalyticsAgent,
    MissingDependencyError,
    get_conversational_analytics_agent,
)
from ..models import ChatRequest
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


@router.post("/stream")
async def stream_chat(
    request: ChatRequest,
    fastapi_request: Request,
    _: None = Depends(conversational_analytics_rate_limit),
):
    """Function: stream_chat — called by components/conversationalAnalytics/hooks/useSSEStream.ts to stream Claude responses.
    Invokes: _get_agent().run_with_tools to produce SSE events.
    Purpose: Primary streaming endpoint for conversational analytics with rate limiting."""
    agent = _get_agent()

    async def event_generator():
        async for event in agent.run_with_tools(request.message, request.session_id):
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
    Invokes: _get_agent().run_with_tools and aggregates the streamed events.
    Purpose: Provide a single-response alternative to the streaming endpoint."""
    agent = _get_agent()
    events = []
    content_parts = []
    chart_config = None
    data_result = None
    
    async for event in agent.run_with_tools(request.message, request.session_id):
        # Parse the SSE event
        if event.startswith("data: "):
            import json
            try:
                parsed = json.loads(event[6:].strip())
                events.append(parsed)
                
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
