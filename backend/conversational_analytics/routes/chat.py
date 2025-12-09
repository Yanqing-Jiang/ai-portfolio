"""Chat routes for Conversational Analytics API."""
from __future__ import annotations

import logging
from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.responses import StreamingResponse

from ..agent import ConversationalAnalyticsAgent
from ..models import ChatRequest
from ..memory import session_store
from rate_limiter import conversational_analytics_rate_limit

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/conv-analytics", tags=["conversational-analytics"])

# Single agent instance
agent = ConversationalAnalyticsAgent()


@router.post("/stream")
async def stream_chat(
    request: ChatRequest,
    fastapi_request: Request,
    _: None = Depends(conversational_analytics_rate_limit),
):
    """Stream a chat response with SSE.
    
    This endpoint accepts a user message and session ID, then streams
    back events as the agent processes the request.
    
    Event types:
    - status: Connection/processing status updates
    - thinking: Step-by-step thinking process
    - tool_start: Tool execution started
    - tool_end: Tool execution completed
    - content: Streamed response content
    - chart: TradingView chart configuration
    - data: Query result data
    - done: Stream completed
    - error: Error occurred
    """
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
    """Non-streaming chat endpoint for simpler integrations.
    
    This collects all events and returns a final response.
    """
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
    """Get conversation history for a session."""
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
    """Clear a session's history."""
    deleted = session_store.delete(session_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Session not found")
    
    return {"message": "Session cleared", "session_id": session_id}


@router.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "conversational-analytics"}
