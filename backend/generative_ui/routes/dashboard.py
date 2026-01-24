# --- Dashboard Route Function/Class Map ---
# Class: CreateDashboardRequest
#   Role: Request payload for dashboard creation.
#   Called from: FastAPI POST /api/dash/create
#   Invokes: n/a
#   Why: Validates incoming dashboard creation requests.
# Class: CreateDashboardResponse
#   Role: Response payload for dashboard creation.
#   Called from: FastAPI POST /api/dash/create
#   Invokes: n/a
#   Why: Standardizes dashboard creation responses for clients.
# Class: ActionRequest
#   Role: Request payload for A2UI userAction messages.
#   Called from: FastAPI POST /api/dash/{dashboard_id}/action
#   Invokes: n/a
#   Why: Validates user action payloads before processing.
# Class: ClarificationSubmitRequest
#   Role: Request payload for clarification submissions.
#   Called from: FastAPI POST /api/dash/{dashboard_id}/clarification
#   Invokes: n/a
#   Why: Validates clarification submissions before plan mutation.
# Class: FollowUpSuggestion
#   Role: Response shape for follow-up query suggestions.
#   Called from: FastAPI GET /api/dash/{dashboard_id}/follow-ups
#   Invokes: n/a
#   Why: Keeps follow-up suggestions consistent for the UI.
# Function: _sse_data
#   Role: Wrap JSON payloads in SSE data envelopes.
#   Called from: stream_dashboard
#   Invokes: n/a
#   Why: Keeps SSE formatting consistent for A2UI messages.
# (moved to clarification module) _needs_* helpers handle clarification heuristics.
# Function: build_visual_clarification
#   Role: Create per-visual clarification requests for streaming.
#   Called from: stream_dashboard (runtime handles pause/resume)
#   Invokes: build_clarification_for_ambiguous_comparison, build_clarification_for_margin_detail
#   Why: Ties clarification prompts to specific dashboard visuals.
# Function: await_clarification_response
#   Role: Poll dashboard state for clarification responses.
#   Called from: runtime orchestrator
#   Invokes: asyncio.sleep
#   Why: Blocks streaming until clarifications resolve or time out.
# Function: create_dashboard
#   Role: Create a dashboard state and preselect an A2UI skill.
#   Called from: FastAPI POST /api/dash/create
#   Invokes: rate_limiter.smart_rate_limit (chat scope), backend.generative_ui.agent_v2.A2UIAgent.select_skill, backend.generative_ui.models.get_dashboard_store
#   Why: Persists dashboard metadata before streaming begins.
# Function: stream_dashboard
#   Role: Stream A2UI messages for a dashboard session.
#   Called from: FastAPI GET /api/dash/{dashboard_id}/stream
#   Invokes: rate_limiter.smart_rate_limit (chat scope), backend.generative_ui.agent_v2.A2UIAgent.execute_skill, backend.generative_ui.a2ui.emitter.A2UIMessageEmitter
#   Why: Drives the live A2UI SSE stream with clarification gating.
# Function: get_dashboard_spec
#   Role: Return stored dashboard plan metadata.
#   Called from: FastAPI GET /api/dash/{dashboard_id}/spec
#   Invokes: backend.generative_ui.models.get_dashboard_store
#   Why: Allows clients to inspect the stored dashboard definition.
# Function: get_dashboard_data
#   Role: Return the latest stored dashboard data payload.
#   Called from: FastAPI GET /api/dash/{dashboard_id}/data
#   Invokes: backend.generative_ui.models.get_dashboard_store
#   Why: Supports debugging and data export workflows.
# Function: download_debug_bundle
#   Role: Downloadable JSON bundle of trace + plan + latest data.
#   Called from: FastAPI GET /api/dash/{dashboard_id}/debug/download
#   Invokes: TraceStore.get_debug_bundle
#   Why: Shareable debug artifacts without logs access.
# Function: handle_action
#   Role: Process incoming A2UI userAction requests.
#   Called from: FastAPI POST /api/dash/{dashboard_id}/action
#   Invokes: rate_limiter.smart_rate_limit (chat scope), backend.generative_ui.runtime.A2UIRuntime.process_action
#   Why: Keeps dashboard interactions aligned with the runtime + tracing pipeline.
# Function: delete_dashboard
#   Role: Delete a dashboard state entry.
#   Called from: FastAPI DELETE /api/dash/{dashboard_id}
#   Invokes: backend.generative_ui.models.get_dashboard_store
#   Why: Cleans up server-side dashboard state.
# Function: get_follow_up_suggestions
#   Role: Return follow-up suggestions tailored to the dashboard.
#   Called from: FastAPI GET /api/dash/{dashboard_id}/follow-ups
#   Invokes: backend.generative_ui.models.get_dashboard_store
#   Why: Feeds follow-up suggestion UI chips.
# Function: submit_clarification
#   Role: Validate and apply clarification responses to the plan.
#   Called from: FastAPI POST /api/dash/{dashboard_id}/clarification
#   Invokes: validate_clarification_response
#   Why: Updates dashboard parameters before streaming resumes.
# Function: get_showcase
#   Role: Serve the A2UI showcase HTML page.
#   Called from: FastAPI GET /api/dash/showcase
#   Invokes: pathlib.Path.read_text
#   Why: Exposes the A2UI demo landing page.
# Function: handle_query
#   Role: Unified entry point for conversational commands with LLM intent classification.
#   Called from: FastAPI POST /api/dash/{dashboard_id}/query
#   Invokes: CommandRouter.classify_intent, _handle_* helper functions
#   Why: Replaces hardcoded keyword matching with LLM-driven intent detection.
# Function: _handle_new_analysis
#   Role: Create new dashboard for new analysis requests.
#   Called from: handle_query when intent is new_analysis
#   Invokes: A2UIAgent.select_skill, dashboard creation
# Function: _handle_layout_modification
#   Role: Handle layout modification commands (reorder, hide/show, emphasis).
#   Called from: handle_query when intent is modify_layout
#   Invokes: A2UIRuntime.process_action
# Function: _handle_data_modification
#   Role: Handle data modification commands (add ticker, change timeframe).
#   Called from: handle_query when intent is modify_data
#   Invokes: A2UIRuntime.process_action
# Function: _handle_component_switch
#   Role: Handle component type switching.
#   Called from: handle_query when intent is switch_component
#   Invokes: _transform_data_for_swap
# Function: _handle_follow_up
#   Role: Handle follow-up questions about current data.
#   Called from: handle_query when intent is follow_up
#   Invokes: Conversation state management
# --- End Dashboard Route Function/Class Map ---
"""
Dashboard API Routes

FastAPI endpoints for A2UI dashboard management.
"""

from __future__ import annotations
import asyncio
import calendar
import json
import logging
import re
import time
import uuid
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, Optional
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse, HTMLResponse, Response
from pydantic import BaseModel

try:
    from rate_limiter import smart_rate_limit, RateLimitScope
except ImportError:  # pragma: no cover - support module execution
    from ..rate_limiter import smart_rate_limit, RateLimitScope  # type: ignore

from ..models import get_dashboard_store
from ..agent_v2 import DEFAULT_METRIC, get_a2ui_agent, A2UIAgentError
from ..a2ui.emitter import A2UIMessageEmitter
from ..layout_planner import LayoutPlanner
from ..runtime import A2UIRuntime
from ..clarification import (
    ClarificationRequest,
    ClarificationResponse,
    await_clarification_response,
    build_visual_clarification,
    clarification_to_sse_event,
    validate_clarification_response,
)
from ..anomaly_detection import detect_anomalies, anomalies_to_suggestions
from ..command_router import get_command_router, IntentClassification
from ..conversation_state import get_conversation_store
from ..follow_up_generator import generate_follow_ups_with_llm
from ..follow_up_responder import build_follow_up_answer
from ..session_memory import load_explanation_memory
from shared_tools.news_service import execute_news_tool
from ..utils.swap_advisor import suggest_swaps_for_component, suggest_swaps_with_llm

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/dash", tags=["dashboard"])

# Rate limiting configuration (Optimization #22)
A2UI_RATE_LIMIT_SCOPE = RateLimitScope.CHAT
A2UI_CREATE_WEIGHT = 1
A2UI_STREAM_WEIGHT = 3  # Streams are more resource-intensive
A2UI_ACTION_WEIGHT = 1

# Concurrent stream limiting (Optimization #22)
MAX_CONCURRENT_STREAMS_PER_IP = 5
_active_streams: Dict[str, int] = {}
_stream_lock = asyncio.Lock()


async def _acquire_stream_slot(client_ip: str) -> bool:
    """
    Acquire a stream slot for the client IP.
    
    Function: _acquire_stream_slot — limits concurrent streams per IP.
    Called from: stream_dashboard
    Why: Prevents resource exhaustion from too many concurrent SSE connections.
    
    Returns:
        True if slot acquired, False if limit reached.
    """
    async with _stream_lock:
        current = _active_streams.get(client_ip, 0)
        if current >= MAX_CONCURRENT_STREAMS_PER_IP:
            return False
        _active_streams[client_ip] = current + 1
        return True


async def _release_stream_slot(client_ip: str) -> None:
    """
    Release a stream slot for the client IP.
    
    Function: _release_stream_slot — frees stream slot on completion.
    Called from: stream_dashboard generator
    """
    async with _stream_lock:
        current = _active_streams.get(client_ip, 0)
        if current > 0:
            _active_streams[client_ip] = current - 1


def _sse_data(payload: str) -> str:
    """Wrap a JSON payload for SSE delivery."""
    return f"data: {payload}\n\n"


# ============================================================================
# Request/Response Models
# ============================================================================

class CreateDashboardRequest(BaseModel):
    """Request to create a new dashboard."""
    question: str
    ticker: Optional[str] = None  # Optional: will be extracted from question


class CreateDashboardResponse(BaseModel):
    """Response after creating a dashboard."""
    dashboard_id: str
    surface_id: str


class ActionRequest(BaseModel):
    """User action request."""
    userAction: Dict[str, Any]


class ClarificationSubmitRequest(BaseModel):
    """Submit user's clarification response."""
    request_id: str
    values: Dict[str, Any]
    skipped: bool = False


# ============================================================================
# Endpoints
# ============================================================================

@router.post("/create", response_model=CreateDashboardResponse)
async def create_dashboard(payload: CreateDashboardRequest, request: Request):
    """
    Create a new dashboard from a user question.

    This endpoint:
    1. Selects an A2UI skill and stores the plan
    2. Creates a dashboard state
    3. Returns the dashboard ID for streaming
    """
    await smart_rate_limit(
        request,
        scope=A2UI_RATE_LIMIT_SCOPE,
        weight=A2UI_CREATE_WEIGHT,
    )
    store = get_dashboard_store()

    try:
        agent = get_a2ui_agent()
        selection = await agent.select_skill(payload.question)
        if payload.ticker:
            selection = selection.model_copy(update={"tickers": [payload.ticker]})
        plan = agent.selection_to_plan(selection)
        logger.info("[DASHBOARD] Selected skill: %s", plan.get("skill_id"))
    except A2UIAgentError as e:
        logger.warning("[DASHBOARD] Agent error: %s", e)
        raise HTTPException(status_code=500, detail=f"Skill selection failed: {e}")

    # Create dashboard state
    state = store.create(
        question=payload.question,
        plan=plan
    )
    
    return CreateDashboardResponse(
        dashboard_id=state.dashboard_id,
        surface_id=state.surface_id
    )



@router.get("/{dashboard_id}/stream")
async def stream_dashboard(dashboard_id: str, request: Request):
    """
    Stream A2UI messages for a dashboard.

    Returns Server-Sent Events with A2UI JSONL payloads.
    
    Includes concurrent stream limiting per IP (Optimization #22).
    
    For completed dashboards (back navigation), returns cached data
    immediately without re-executing the runtime.
    """
    from ..models.dashboard_state import RuntimeStatus
    
    store = get_dashboard_store()
    state = store.get(dashboard_id)

    if not state:
        raise HTTPException(status_code=404, detail="Dashboard not found")

    session_id = request.query_params.get("session_id")
    if session_id:
        try:
            state.update_params({"session_id": session_id})
        except Exception:
            pass

    await smart_rate_limit(
        request,
        scope=A2UI_RATE_LIMIT_SCOPE,
        weight=A2UI_STREAM_WEIGHT,
    )
    
    # Check if dashboard is already complete - return cached data (Issue #2 fix)
    # This handles "back navigation" case where user returns to a completed dashboard
    if state.status == RuntimeStatus.complete and state.latest_run and state.latest_run.data_json:
        logger.info(
            "[STREAM] Dashboard %s already complete, returning cached data",
            dashboard_id[:8]
        )
        
        async def generate_cached():
            """Emit cached data for completed dashboards including layout."""
            from ..skills import get_a2ui_skill
            
            emitter = A2UIMessageEmitter(surface_id=state.surface_id)
            
            # Emit beginRendering first
            yield _sse_data(emitter.begin_rendering())
            
            # Build and emit the component tree (surfaceUpdate)
            try:
                skill = get_a2ui_skill(state.plan.skill_id)
                
                if skill:
                    # Build render context from state
                    from ..a2ui.emitter import SkillRenderContext
                    context = SkillRenderContext(
                        title=state.question,
                        primary_ticker=state.plan.tickers[0] if state.plan.tickers else "",
                        tickers=state.plan.tickers,
                        time_range=state.plan.time_range,
                        metric=state.plan.metric,
                    )
                    
                    # Get layout overrides if any
                    layout_override = state.latest_run.layout_override or {}
                    
                    # Build components from skill
                    components = emitter.build_components_for_skill(
                        skill,
                        context,
                        variant=layout_override.get("variant"),
                        widget_order=layout_override.get("widget_order"),
                        hidden_widgets=layout_override.get("hidden_widgets"),
                        emphasis=layout_override.get("emphasis"),
                    )
                    
                    # Emit the surface update with components
                    yield _sse_data(emitter.surface_update(components))
            except Exception as e:
                logger.warning("[STREAM] Failed to rebuild layout: %s", e)
                # Continue anyway - data will still be rendered
            
            cached_payload = dict(state.latest_run.data_json)
            cached_payload["loading"] = False

            if session_id:
                cached_explanation = await load_explanation_memory(session_id, dashboard_id)
                if cached_explanation:
                    explanation_payload = cached_payload.get("explanation")
                    if not isinstance(explanation_payload, dict):
                        explanation_payload = {}
                    explanation_payload.update(cached_explanation)
                    explanation_payload["cached"] = True
                    cached_payload["explanation"] = explanation_payload

            # Emit the cached data model
            yield _sse_data(emitter.data_update(cached_payload, path="/data"))
            
            # Emit audit event for transparency
            yield _sse_data(emitter.audit("cache_replay", f"restored run {state.latest_run.run_id[:8]}"))
            
            # Emit done signal
            yield _sse_data(json.dumps({"done": True}))
        
        return StreamingResponse(
            generate_cached(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            }
        )
    
    # Check concurrent stream limit (Optimization #22)
    client_ip = request.client.host if request.client else "unknown"
    if not await _acquire_stream_slot(client_ip):
        raise HTTPException(
            status_code=429,
            detail=f"Too many active streams (max {MAX_CONCURRENT_STREAMS_PER_IP} per IP)"
        )

    async def generate():
        try:
            agent = get_a2ui_agent()
            runtime = A2UIRuntime(agent=agent, layout_planner=LayoutPlanner(use_model=True))
            async for message in runtime.stream_dashboard(state):
                if message.startswith("event:"):
                    # Already SSE-formatted (clarification_request)
                    yield message
                else:
                    yield _sse_data(message)
        finally:
            # Always release the stream slot when done
            await _release_stream_slot(client_ip)
    
    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )


@router.get("/{dashboard_id}/spec")
async def get_dashboard_spec(dashboard_id: str):
    """
    Get the dashboard specification (plan + current params).
    """
    store = get_dashboard_store()
    state = store.get(dashboard_id)
    
    if not state:
        raise HTTPException(status_code=404, detail="Dashboard not found")
    
    return {
        "dashboard_id": state.dashboard_id,
        "question": state.question,
        "plan": state.plan_json,
        "params": state.params,
        "surface_id": state.surface_id,
        "catalog_id": state.catalog_id,
    }


@router.get("/{dashboard_id}/data")
async def get_dashboard_data(dashboard_id: str):
    """
    Get the latest data for a dashboard.
    """
    store = get_dashboard_store()
    state = store.get(dashboard_id)
    
    if not state:
        raise HTTPException(status_code=404, detail="Dashboard not found")
    
    return {
        "dashboard_id": state.dashboard_id,
        "data": state.latest_data,
        "run_id": state.latest_run.run_id if state.latest_run else None,
    }


@router.post("/{dashboard_id}/action")
async def handle_action(dashboard_id: str, action: ActionRequest, request: Request):
    """
    Handle a user action (A2UI userAction message).

    Processes the action and returns updated data or layout.
    """
    store = get_dashboard_store()
    state = store.get(dashboard_id)

    if not state:
        raise HTTPException(status_code=404, detail="Dashboard not found")

    await smart_rate_limit(
        request,
        scope=A2UI_RATE_LIMIT_SCOPE,
        weight=A2UI_ACTION_WEIGHT,
    )

    runtime = A2UIRuntime(agent=get_a2ui_agent(), layout_planner=LayoutPlanner(use_model=True))
    try:
        return await runtime.process_action(state, action.userAction)
    except A2UIAgentError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


# ============================================================================
# Unified Query Endpoint (LLM-Driven Intent Classification)
# ============================================================================

class QueryRequest(BaseModel):
    """Request for LLM-driven conversational query."""
    query: str


class QueryResponse(BaseModel):
    """Response from unified query endpoint."""
    status: str  # 'success', 'new_dashboard', 'error'
    intent: str  # 'new_analysis', 'modify_layout', 'modify_data', 'switch_component', 'follow_up', 'unknown'
    dashboard_id: Optional[str] = None  # For new_analysis intent
    result: Optional[Dict[str, Any]] = None
    rationale: Optional[str] = None
    message: Optional[str] = None


@router.post("/{dashboard_id}/query", response_model=QueryResponse)
async def handle_query(dashboard_id: str, payload: QueryRequest, request: Request):
    """
    Handle all user text input through LLM-driven intent classification.
    
    This is the UNIFIED entry point for conversational control.
    
    Function: handle_query
    Called from: Frontend chat input, follow-up suggestions
    Invokes: CommandRouter.classify_intent, appropriate action handler
    Why: Replaces hard-coded keyword matching with LLM-driven intent classification.
    
    Intent Routing:
    - new_analysis -> Create new dashboard (returns new dashboard_id)
    - modify_layout -> Modify existing dashboard layout
    - modify_data -> Refine current analysis (add ticker, change timeframe)
    - switch_component -> Change component visualization type
    - follow_up -> Continue conversation with answer
    """
    await smart_rate_limit(
        request,
        scope=A2UI_RATE_LIMIT_SCOPE,
        weight=A2UI_ACTION_WEIGHT,
    )
    
    query = payload.query.strip()
    if not query:
        raise HTTPException(status_code=400, detail="Query is required")
    
    store = get_dashboard_store()
    state = store.get(dashboard_id)
    if not state:
        raise HTTPException(status_code=404, detail="Dashboard not found")
    
    # Get or create conversation state
    conv_store = get_conversation_store()
    conv_state = conv_store.get_or_create(dashboard_id)
    
    # Add user message to conversation
    conv_state.add_message("user", query)
    
    # Update conversation context from dashboard state
    if state.plan:
        conv_state.update_context(
            skill_id=state.plan.skill_id,
            tickers=state.plan.tickers,
            metric=getattr(state.plan, 'metric', None),
            time_range=getattr(state.plan, 'time_range', None),
        )
    
    # Classify intent using LLM
    logger.info("[QUERY] Starting intent classification for: %s", query[:50])
    router_inst = get_command_router()
    try:
        classification = await router_inst.classify_intent(
            query=query,
            dashboard_id=dashboard_id,
            current_context=conv_state.get_context(),
            recent_messages=conv_state.get_recent_messages(),
        )
    except Exception as e:
        logger.exception("[QUERY] Intent classification failed: %s", e)
        return QueryResponse(
            status="error",
            intent="unknown",
            message=f"Intent classification failed: {str(e)}",
        )
    
    logger.info(
        "[QUERY] Intent: %s, Action: %s, Rationale: %s",
        classification.intent,
        classification.action_name,
        classification.rationale[:100] if classification.rationale else "N/A",
    )
    
    # Route to appropriate handler based on intent
    try:
        if classification.intent == "new_analysis":
            return await _handle_new_analysis(query, classification, request)
        
        elif classification.intent == "modify_layout":
            result = await _handle_layout_modification(state, conv_state, classification)
            return QueryResponse(
                status="success",
                intent=classification.intent,
                result=result,
                rationale=classification.rationale,
            )
        
        elif classification.intent == "modify_data":
            result = await _handle_data_modification(state, conv_state, classification)
            return QueryResponse(
                status="success",
                intent=classification.intent,
                result=result,
                rationale=classification.rationale,
            )
        
        elif classification.intent == "switch_component":
            result = await _handle_component_switch(state, classification)
            return QueryResponse(
                status="success",
                intent=classification.intent,
                result=result,
                rationale=classification.rationale,
            )
        
        elif classification.intent == "follow_up":
            result = await _handle_follow_up(state, conv_state, query, classification)
            return QueryResponse(
                status="success",
                intent=classification.intent,
                result=result,
                rationale=classification.rationale,
            )
        
        else:
            # Unknown intent - default to new analysis
            return await _handle_new_analysis(query, classification, request)
            
    except Exception as e:
        logger.exception("Query handling failed: %s", e)
        return QueryResponse(
            status="error",
            intent=classification.intent,
            message=str(e),
            rationale=classification.rationale,
        )


async def _handle_new_analysis(
    query: str, 
    classification: IntentClassification,
    request: Request,
) -> QueryResponse:
    """
    Create a new dashboard for a new analysis request.
    
    Function: _handle_new_analysis
    Called from: handle_query when intent is new_analysis
    Invokes: A2UIAgent.select_skill, dashboard creation
    Why: Routes completely new analysis requests to dashboard creation.
    """
    try:
        agent = get_a2ui_agent()
        selection = await agent.select_skill(query)
        plan = agent.selection_to_plan(selection)
        
        store = get_dashboard_store()
        state = store.create(question=query, plan=plan)
        
        # Initialize conversation state for new dashboard
        conv_store = get_conversation_store()
        conv_state = conv_store.get_or_create(state.dashboard_id)
        conv_state.update_context(
            skill_id=plan.get("skill_id"),
            tickers=plan.get("tickers", []),
        )
        
        return QueryResponse(
            status="new_dashboard",
            intent=classification.intent,
            dashboard_id=state.dashboard_id,
            result={
                "surface_id": state.surface_id,
                "skill_id": plan.get("skill_id"),
                "tickers": plan.get("tickers", []),
            },
            rationale=classification.rationale,
        )
        
    except A2UIAgentError as e:
        raise HTTPException(status_code=500, detail=f"Skill selection failed: {e}")


async def _handle_layout_modification(
    state,
    conv_state,
    classification: IntentClassification,
) -> Dict[str, Any]:
    """
    Handle layout modification commands (reorder, hide/show, emphasis).
    
    Function: _handle_layout_modification
    Called from: handle_query when intent is modify_layout
    Why: Returns action params for client-side layout modification.
    
    Note: Layout changes are handled client-side via LayoutContext.
    The backend only classifies intent and returns the action params.
    The frontend's useLayoutEventListener applies the changes.
    """
    action_name = classification.action_name or classification.action_params.get("action", "unknown")
    params = classification.action_params or {}
    
    # Map common action names to standardized format
    action_mapping = {
        "reorder_widgets": "reorder_widgets",
        "reorder": "reorder_widgets",
        "hide_component": "hide_widget",
        "hide_widget": "hide_widget",
        "show_component": "show_widget",
        "show_widget": "show_widget",
        "toggle_component": "toggle_widget",
        "toggle_widget": "toggle_widget",
        "change_emphasis": "set_emphasis",
        "set_emphasis": "set_emphasis",
        "focus_chart": "focus_chart",
        "focus_table": "focus_table",
        "focus_news": "focus_news",
        "reset_layout": "reset_layout",
        "reset": "reset_layout",
    }
    
    # Normalize the action name
    normalized_action = action_mapping.get(action_name, action_name)
    
    # Extract relevant parameters based on action type
    action_details = {
        "original_action": action_name,
        **params,
    }
    
    # Handle reorder specifically - determine the new order if possible
    if normalized_action == "reorder_widgets":
        # Try to parse order from params or infer from query
        # If LLM provided widget_order, use it; otherwise mark as needs frontend inference
        if "order" in params or "widget_order" in params or "new_order" in params:
            action_details["order"] = params.get("order") or params.get("widget_order") or params.get("new_order")
        else:
            # Mark that frontend should infer order based on context
            action_details["infer_order"] = True
            action_details["hint"] = classification.rationale
    
    # Log for debugging
    logger.info(
        "[LAYOUT] Action: %s -> %s, Details: %s",
        action_name,
        normalized_action,
        action_details,
    )
    
    # Update conversation with result
    conv_state.add_message(
        "assistant", 
        f"Layout updated: {normalized_action}", 
        metadata=action_details
    )
    
    return {
        "action": normalized_action,
        "applied": True,
        "details": action_details,
    }


async def _handle_data_modification(
    state,
    conv_state,
    classification: IntentClassification,
) -> Dict[str, Any]:
    """
    Handle data modification commands (add ticker, change timeframe).
    
    Function: _handle_data_modification
    Called from: handle_query when intent is modify_data
    Invokes: A2UIRuntime.process_action
    Why: Refines current analysis without creating new dashboard.
    """
    action_name = classification.action_name or classification.action_params.get("action")
    params = classification.action_params
    
    action = {"name": action_name, "context": params}
    
    runtime = A2UIRuntime(
        agent=get_a2ui_agent(), 
        layout_planner=LayoutPlanner(use_model=True)
    )
    result = await runtime.process_action(state, action)
    
    # Update conversation context based on action
    if action_name == "add_ticker" and params.get("ticker"):
        conv_state.tickers.append(params["ticker"])
    elif action_name == "change_timeframe" and params.get("timeframe"):
        conv_state.time_range = params["timeframe"]
    elif action_name == "change_metric" and params.get("metric"):
        conv_state.metric = params["metric"]
    
    conv_state.add_message(
        "assistant", 
        f"Data updated: {action_name}", 
        metadata=result
    )
    
    return {
        "action": action_name,
        "params": params,
        "applied": True,
        "details": result,
    }


async def _handle_component_switch(
    state,
    classification: IntentClassification,
) -> Dict[str, Any]:
    """
    Handle component type switching.
    
    Function: _handle_component_switch
    Called from: handle_query when intent is switch_component
    Invokes: swap_component logic
    Why: Changes visualization type without changing data.
    """
    params = classification.action_params
    
    # Get the data model
    data_model = state.latest_data.get("data", {}) if state.latest_data else {}
    
    # Transform data for the swap
    transformed_data, warnings = _transform_data_for_swap(
        data_model=data_model,
        component_id=params.get("target_component", ""),
        from_type=params.get("target_component", ""),  # Best guess
        to_type=params.get("new_type", ""),
    )
    
    return {
        "from_type": params.get("target_component"),
        "to_type": params.get("new_type"),
        "transformed_data": transformed_data,
        "warnings": warnings,
        "message": f"Swapped to {params.get('new_type')}",
    }


async def _handle_follow_up(
    state,
    conv_state,
    query: str,
    classification: IntentClassification,
) -> Dict[str, Any]:
    """
    Handle follow-up questions about current data.
    
    Function: _handle_follow_up
    Called from: handle_query when intent is follow_up
    Invokes: follow_up_responder.build_follow_up_answer
    Why: Continues conversation with data-aware answers.
    """
    # Get current data model for context
    data_model = state.latest_data.get("data", {}) if state.latest_data else {}
    
    context = {
        "skill_id": conv_state.skill_id,
        "tickers": conv_state.tickers,
        "question_type": classification.action_params.get("question_type"),
        "target": classification.action_params.get("target_element"),
    }
    
    answer = build_follow_up_answer(
        question_type=classification.action_params.get("question_type"),
        target_element=classification.action_params.get("target_element"),
        data_model=data_model,
        skill_id=conv_state.skill_id,
        tickers=conv_state.tickers or [],
    )
    conv_state.add_message("assistant", answer)
    
    return {
        "question_type": classification.action_params.get("question_type"),
        "answer": answer,
        "context": context,
        "data_summary": {
            "kpis": list(data_model.get("kpis", {}).keys()) if data_model.get("kpis") else [],
            "has_chart": "chart" in data_model,
            "has_table": "table" in data_model,
        }
    }


@router.delete("/{dashboard_id}")
async def delete_dashboard(dashboard_id: str):
    """
    Delete a dashboard and emit A2UI deleteSurface message.
    
    Per A2UI v0.8 spec, emits deleteSurface to notify connected clients
    to clean up the surface from their UI.
    
    Function: delete_dashboard — deletes dashboard state and emits cleanup message.
    Called from: FastAPI DELETE /api/dash/{dashboard_id}
    Invokes: A2UIMessageEmitter.delete_surface, get_dashboard_store
    Why: Proper surface lifecycle cleanup per A2UI specification.
    """
    store = get_dashboard_store()
    state = store.get(dashboard_id)
    
    if not state:
        raise HTTPException(status_code=404, detail="Dashboard not found")
    
    # Create deleteSurface message for clients
    emitter = A2UIMessageEmitter(surface_id=state.surface_id)
    delete_message = emitter.delete_surface()

    # Delete the dashboard state
    store.delete(dashboard_id)

    # Clean up swap states (fire-and-forget)
    try:
        from ..swap_state import get_swap_state_repo
        swap_repo = get_swap_state_repo()
        await swap_repo.clear(dashboard_id)
    except Exception as e:
        logger.warning("[DELETE] Swap state cleanup failed: %s", e)

    return {
        "status": "deleted",
        "dashboard_id": dashboard_id,
        "surface_id": state.surface_id,
        "a2ui_message": delete_message,  # Client can broadcast this to clean up UI
    }


class SwapRequest(BaseModel):
    """Request to swap a component type."""
    component_id: str
    from_type: str
    to_type: str


@router.post("/{dashboard_id}/swap")
async def swap_component(dashboard_id: str, swap: SwapRequest, request: Request):
    """
    Handle component type swap with data transformation.
    
    Function: swap_component
    Called from: Client-side SwapButton or ComponentActionMenu
    Invokes: Data transformation logic
    Why: Enables swapping between component types that require different data shapes.
    
    For simple swaps (same data shape), the client can handle it via ComponentSwapContext.
    This endpoint is for swaps requiring backend data transformation.
    
    Examples:
    - PriceChart -> DataTable: Convert timeseries to tabular format
    - KpiCard -> MetricChart: Expand KPI with historical data
    - DataTable -> PriceChart: Extract timeseries from table rows
    """
    await smart_rate_limit(
        request,
        scope=A2UI_RATE_LIMIT_SCOPE,
        weight=A2UI_ACTION_WEIGHT,
    )
    
    store = get_dashboard_store()
    state = store.get(dashboard_id)
    
    if not state:
        raise HTTPException(status_code=404, detail="Dashboard not found")
    
    # Get current component data from latest data model
    # FIX: latest_data returns data_json directly, not nested under "data" key
    data_model = state.latest_data if state.latest_data else {}

    # Transform data based on swap type
    transformed_data, warnings = _transform_data_for_swap(
        data_model=data_model,
        component_id=swap.component_id,
        from_type=swap.from_type,
        to_type=swap.to_type,
    )
    
    if transformed_data is None and not warnings:
        # No transformation needed - client handles simple swaps
        return {
            "status": "no_transform_needed",
            "component_id": swap.component_id,
            "from_type": swap.from_type,
            "to_type": swap.to_type,
            "message": "This swap can be handled client-side without data transformation",
            "warnings": [],
        }
    
    return {
        "status": "success",
        "component_id": swap.component_id,
        "from_type": swap.from_type,
        "to_type": swap.to_type,
        "transformed_data": transformed_data,
        "warnings": warnings,
    }


@router.get("/{dashboard_id}/swap/suggest")
async def get_swap_suggestions(
    dashboard_id: str,
    component_type: str,
    component_id: Optional[str] = None,
    use_llm: bool = True,
):
    """
    Get ranked swap suggestions for a component.

    Function: get_swap_suggestions
    Called from: Frontend ComponentSwapContext (suggestSwaps)
    Invokes: swap_advisor.suggest_swaps_with_llm (LLM) or suggest_swaps_for_component (heuristic)
    Why: Provides AI/heuristic-driven recommendations for better visualizations.

    Query params:
        component_type: Current component type (e.g., 'KpiCard')
        component_id: Optional component ID for specific context
        use_llm: Whether to use LLM-enhanced suggestions (default: True)
    """
    store = get_dashboard_store()
    state = store.get(dashboard_id)

    if not state:
        raise HTTPException(status_code=404, detail="Dashboard not found")

    # Use latest data model to inform suggestions
    data_model = state.latest_data if state.latest_data else {}

    if use_llm:
        # Use LLM-enhanced suggestions (with heuristic fallback)
        suggestions = await suggest_swaps_with_llm(
            current_type=component_type,
            data_model=data_model,
            component_id=component_id,
            max_suggestions=3,
        )
        logger.info(
            "[SWAP_SUGGEST] LLM suggestions for %s: %d results",
            component_type,
            len(suggestions),
        )
    else:
        # Use heuristic-only suggestions
        suggestions = suggest_swaps_for_component(component_type, data_model)

    return {"suggestions": suggestions}


# ============================================================================
# Swap State Persistence Endpoints
# ============================================================================

@router.post("/{dashboard_id}/swap/state")
async def save_swap_states(dashboard_id: str, request: Request):
    """
    Save swap states for components in a dashboard.

    Function: save_swap_states
    Called from: Frontend useSwapPersistence hook after commitSwap
    Invokes: SwapStateRepository.save_batch
    Why: Persists swap states to Redis for cross-refresh restoration.

    Request body: { "states": { componentId: SwapStateSnapshot, ... } }
    """
    from ..swap_state import get_swap_state_repo
    from ..models.swap_state import SwapStateSnapshot

    store = get_dashboard_store()
    state = store.get(dashboard_id)
    if not state:
        raise HTTPException(status_code=404, detail="Dashboard not found")

    try:
        body = await request.json()
        states_raw = body.get("states", {})

        # Parse and validate states
        states = {}
        for component_id, state_data in states_raw.items():
            if isinstance(state_data, dict):
                states[component_id] = SwapStateSnapshot.model_validate(state_data)
            else:
                logger.warning("[SWAP_STATE] Invalid state format for %s", component_id)

        if not states:
            return {"status": "no_op", "message": "No valid states to save"}

        repo = get_swap_state_repo()
        await repo.save_batch(dashboard_id, states)

        return {
            "status": "success",
            "saved_count": len(states),
            "dashboard_id": dashboard_id,
        }

    except Exception as e:
        logger.exception("[SWAP_STATE] Save failed: %s", e)
        raise HTTPException(status_code=500, detail=f"Failed to save swap states: {e}")


@router.get("/{dashboard_id}/swap/state")
async def load_swap_states(dashboard_id: str):
    """
    Load all swap states for a dashboard.

    Function: load_swap_states
    Called from: Frontend useSwapPersistence hook on mount
    Invokes: SwapStateRepository.load_all
    Why: Restores swap states from Redis on page refresh.

    Returns: { "states": { componentId: SwapStateSnapshot, ... } }
    """
    from ..swap_state import get_swap_state_repo

    store = get_dashboard_store()
    state = store.get(dashboard_id)
    if not state:
        raise HTTPException(status_code=404, detail="Dashboard not found")

    repo = get_swap_state_repo()
    states = await repo.load_all(dashboard_id)

    return {
        "status": "success",
        "dashboard_id": dashboard_id,
        "states": {cid: s.model_dump() for cid, s in states.items()},
        "loaded_count": len(states),
    }


@router.delete("/{dashboard_id}/swap/state/{component_id}")
async def delete_swap_state(dashboard_id: str, component_id: str):
    """
    Delete swap state for a single component.

    Function: delete_swap_state
    Called from: Frontend when resetting a specific component
    Invokes: SwapStateRepository.delete
    Why: Allows selective cleanup of individual component states.
    """
    from ..swap_state import get_swap_state_repo

    store = get_dashboard_store()
    state = store.get(dashboard_id)
    if not state:
        raise HTTPException(status_code=404, detail="Dashboard not found")

    repo = get_swap_state_repo()
    await repo.delete(dashboard_id, component_id)

    return {
        "status": "success",
        "dashboard_id": dashboard_id,
        "component_id": component_id,
    }


@router.post("/{dashboard_id}/swap/state/clear")
async def clear_swap_states(dashboard_id: str):
    """
    Clear all swap states for a dashboard.

    Function: clear_swap_states
    Called from: Frontend on dashboard unmount or session end
    Invokes: SwapStateRepository.clear
    Why: Cleans up swap state storage when dashboard/session ends.
    """
    from ..swap_state import get_swap_state_repo

    # Note: Don't require dashboard to exist - might be cleaning up after deletion
    repo = get_swap_state_repo()
    cleared_count = await repo.clear(dashboard_id)

    return {
        "status": "success",
        "dashboard_id": dashboard_id,
        "cleared_count": cleared_count,
    }


def _transform_data_for_swap(
    data_model: Dict[str, Any],
    component_id: str,
    from_type: str,
    to_type: str,
) -> tuple[Optional[Dict[str, Any]], list[str]]:
    """
    Transform data for component type swap.

    Function: _transform_data_for_swap
    Called from: swap_component endpoint
    Invokes: Type-specific transformation functions
    Why: Different visualizations need different data shapes.

    Returns (transformed_data, warnings).
    """
    warnings: list[str] = []

    # PriceChart/MetricChart -> DataTable: Convert timeseries to rows
    if from_type in ("PriceChart", "MetricChart") and to_type == "DataTable":
        series_data = data_model.get("chart", {}).get("series", [])
        if not series_data:
            return None, ["No chart data available to convert"]

        # Convert series data to table rows
        rows = []
        for series in series_data:
            values = series.get("values", [])
            labels = series.get("labels", [])
            name = series.get("name", series.get("metric", "Value"))

            for i, value in enumerate(values):
                label = labels[i] if i < len(labels) else f"Period {i+1}"
                rows.append({
                    "period": label,
                    name: value,
                })
        
        if len(rows) > 50:
            warnings.append(f"Data truncated: showing first 50 of {len(rows)} rows")
            rows = rows[:50]

        # Return FLAT props for frontend compatibility
        return {
            "columns": [
                {"key": "period", "label": "Period"},
                {"key": series_data[0].get("name", "Value"), "label": series_data[0].get("name", "Value")},
            ],
            "rows": rows,
            "sortable": True,
        }, warnings

    # DataTable -> MetricChart: Convert rows to series
    if from_type == "DataTable" and to_type in ("MetricChart", "PriceChart"):
        table_data = data_model.get("table", {})
        rows = table_data.get("rows", [])
        if not rows:
            return None, ["No table data available to convert"]

        # Find numeric columns for chart series
        numeric_cols = []
        for key, val in rows[0].items():
            if isinstance(val, (int, float)) and key.lower() not in ("year", "quarter", "period"):
                numeric_cols.append(key)

        if not numeric_cols:
            return None, ["No numeric columns found for chart"]

        # Extract series from first numeric column
        values = [row.get(numeric_cols[0]) for row in rows]
        labels = [row.get("period", row.get("ticker", f"Row {i}")) for i, row in enumerate(rows)]

        # Return FLAT props for frontend compatibility
        return {
            "series": [{
                "name": numeric_cols[0],
                "values": values,
                "labels": labels,
            }],
            "title": f"{numeric_cols[0]} Over Time",
            "chartType": "line",
        }, warnings

    # KpiCard -> MetricChart: Use existing chart series from data model
    if from_type == "KpiCard" and to_type == "MetricChart":
        # Chart data is already available in the data model from skill executor
        chart_data = data_model.get("chart", {})
        existing_series = chart_data.get("series", [])

        if existing_series:
            # Filter out series with empty data arrays
            valid_series = [s for s in existing_series if s.get("data")]

            if not valid_series:
                return None, ["No valid historical data found"]

            # Series are already in correct format: {"ticker": "...", "data": [{period, value}]}
            # MetricChart expects the same format - just pass through
            return {
                "series": valid_series,
                "title": data_model.get("title", "Margin Trend Over Time"),
                "chartType": "line",
                "annotations": chart_data.get("annotations", []),
            }, warnings

        # Fallback: No chart data available
        return None, ["No historical data available for this KPI"]

    # PeerComparePanel -> DataTable: Extract comparison table
    if from_type == "PeerComparePanel" and to_type == "DataTable":
        table_data = data_model.get("table", {})
        if not table_data:
            return None, ["No comparison data available"]

        # Return FLAT props for frontend compatibility
        return {
            "columns": table_data.get("columns", []),
            "rows": table_data.get("rows", []),
            "sortable": True,
            "title": data_model.get("title", "Peer Comparison Data"),
        }, warnings

    # PeerComparePanel -> MetricChart: Extract chart data
    if from_type == "PeerComparePanel" and to_type == "MetricChart":
        chart_data = data_model.get("chart", {})
        if not chart_data:
            return None, ["No chart data available"]

        # Return FLAT props for frontend compatibility
        return {
            "series": chart_data.get("series", []),
            "title": data_model.get("title", "Peer Comparison"),
            "chartType": "line",
            "annotations": chart_data.get("annotations", []),
        }, warnings

    # PeerComparePanel -> SplitView: Decompose into separate components
    if from_type == "PeerComparePanel" and to_type == "SplitView":
        chart_data = data_model.get("chart", {})
        table_data = data_model.get("table", {})
        explanation = data_model.get("explanation", {})

        components = []

        # Add MetricChart component
        if chart_data and chart_data.get("series"):
            components.append({
                "componentId": f"{component_id}_chart",
                "type": "MetricChart",
                "props": {
                    "series": chart_data.get("series", []),
                    "title": "Comparison Chart",
                    "chartType": "line",
                },
            })

        # Add DataTable component
        if table_data and table_data.get("rows"):
            components.append({
                "componentId": f"{component_id}_table",
                "type": "DataTable",
                "props": {
                    "columns": table_data.get("columns", []),
                    "rows": table_data.get("rows", []),
                    "sortable": True,
                },
            })

        # Add ExplainMovePanel component for insights
        if explanation and explanation.get("text"):
            components.append({
                "componentId": f"{component_id}_insight",
                "type": "ExplainMovePanel",
                "props": {
                    "title": explanation.get("title", "Analysis"),
                    "explanation": explanation.get("text", ""),
                    "factors": explanation.get("factors", []),
                },
            })

        if not components:
            return None, ["No content available to split"]

        return {
            "type": "SplitView",
            "originalComponentId": component_id,
            "components": components,
            "layout": "column",  # Stack vertically by default
        }, warnings

    # No transformation needed - client can handle this swap
    return None, []


class FollowUpSuggestion(BaseModel):
    """A follow-up query suggestion."""
    id: str
    label: str
    query: str
    icon: str = ">"  # ASCII-safe icon placeholder
    category: Optional[str] = None
    priority: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


@router.get("/{dashboard_id}/follow-ups")
async def get_follow_up_suggestions(dashboard_id: str):
    """
    Get AI-enhanced follow-up suggestions based on the current dashboard data.
    
    Function: get_follow_up_suggestions
    Called from: GenerativeUIPage.tsx after dashboard completes
    Invokes: Dashboard state analysis
    Why: Provides contextual next steps based on actual analysis results.
    """
    store = get_dashboard_store()
    state = store.get(dashboard_id)
    
    if not state:
        raise HTTPException(status_code=404, detail="Dashboard not found")
    
    # Extract context from dashboard
    skill_id = state.plan.skill_id if state.plan else None
    tickers = state.plan.tickers if state.plan else []
    primary_ticker = tickers[0] if tickers else "NVDA"
    metric = state.plan.metric if state.plan and hasattr(state.plan, 'metric') else "Revenue"
    
    # Try to extract data context from state (use latest_data from most recent run)
    data_model = state.latest_data or {}
    table_rows = data_model.get("table", {}).get("rows", [])
    
    # Detect anomalies in the data (proactive insights)
    anomalies = detect_anomalies(data_model, primary_ticker)
    anomaly_suggestions = anomalies_to_suggestions(anomalies)

    # Insight discovery suggestions removed - now handled by anomaly alerts above
    # Per user request: limit to 3-4 buttons total

    # Generate contextual follow-ups via shared generator (LLM + fallback)
    skill_suggestions = await generate_follow_ups_with_llm(
        skill_id=skill_id,
        primary_ticker=primary_ticker,
        tickers=tickers,
        metric=metric,
        data_model=data_model,
        anomalies=anomalies,
        max_suggestions=3,
    )

    # Web/news fallback suggestion if data is stale or missing
    latest_date: Optional[date] = None
    if table_rows:
        for row in table_rows:
            row_date: Optional[date] = None
            year = row.get("calendar_year")
            quarter = row.get("calendar_quarter_num") or row.get("calendar_quarter")
            if year and quarter:
                try:
                    y = int(year)
                    q = int(str(quarter).replace("Q", "").strip())
                    month = q * 3
                    last_day = calendar.monthrange(y, month)[1]
                    row_date = date(y, month, last_day)
                except (ValueError, calendar.IllegalMonthError):
                    row_date = None
            if not row_date and row.get("period"):
                period_val = str(row.get("period"))
                match = re.search(r"Q([1-4])\\s*[-/\\s]?\\s*(\\d{4})", period_val, re.IGNORECASE)
                if match:
                    y = int(match.group(2))
                    q = int(match.group(1))
                    month = q * 3
                    last_day = calendar.monthrange(y, month)[1]
                    row_date = date(y, month, last_day)
                else:
                    try:
                        row_date = datetime.fromisoformat(period_val.replace("Z", "+00:00")).date()
                    except ValueError:
                        row_date = None
            if row_date and (latest_date is None or row_date > latest_date):
                latest_date = row_date

    is_stale = latest_date is None or (datetime.utcnow().date() - latest_date).days > 30
    news_suggestion: Optional[Dict[str, Any]] = None
    if is_stale and primary_ticker:
        news_result = await execute_news_tool(ticker=primary_ticker, limit=3)
        if news_result.get("success") and news_result.get("articles"):
            news_suggestion = {
                "id": f"news_{primary_ticker.lower()}",
                "label": "Recent news",
                "query": f"What's the latest news on {primary_ticker}?",
                "icon": "[news]",
                "category": "web_search",
                "metadata": {"articles": news_result.get("articles", [])},
            }
    
    # Merge skill suggestions only (anomalies shown separately as alerts)
    # Limit to 4 suggestions max per user request
    all_suggestions = [s.model_dump() for s in skill_suggestions[:3]]
    if news_suggestion:
        all_suggestions.append(news_suggestion)
    
    return {
        "suggestions": all_suggestions,
        "anomalies": [{
            "ticker": a.ticker,
            "metric": a.metric,
            "value": a.value,
            "unit": a.unit,
            "comparison": {
                "type": a.comparison_type,
                "baseline": a.baseline,
                "percentageDiff": a.percentage_diff,
                "description": a.description,
            },
            "importance": a.importance,
            "explanation": a.explanation,
        } for a in anomalies[:3]],  # Top 3 anomalies for UI display
    }


@router.post("/{dashboard_id}/clarification")
async def submit_clarification(dashboard_id: str, request: ClarificationSubmitRequest):
    """
    Submit user's clarification response.
    
    This endpoint:
    1. Validates the clarification response
    2. Merges values into dashboard plan/params
    3. Returns updated plan for streaming
    """
    store = get_dashboard_store()
    state = store.get(dashboard_id)
    
    if not state:
        raise HTTPException(status_code=404, detail="Dashboard not found")
    
    pending_request = state.params.get("pending_clarification")
    original_request = ClarificationRequest(**pending_request) if isinstance(pending_request, dict) else None
    response_payload = ClarificationResponse(
        request_id=request.request_id,
        values=request.values,
        skipped=request.skipped,
    )

    if request.skipped:
        validated_values: Dict[str, Any] = {}
    elif original_request:
        validated_values = validate_clarification_response(response_payload, original_request)
    else:
        validated_values = request.values

    # Extract clarification values and merge into plan
    values = validated_values
    plan = dict(state.plan_json)  # Make a copy to modify

    # Direct field mapping - LLM clarifications use field_id directly as plan field
    # NO skill_id switching - skills auto-reveal and clarification only refines params

    # Handle new LLM-generated field IDs (metric, time_range, tickers)
    if "metric" in values and values["metric"]:
        plan["metric"] = values["metric"]

    if "time_range" in values and values["time_range"]:
        plan["time_range"] = values["time_range"]

    if "tickers" in values and values["tickers"]:
        if isinstance(values["tickers"], list):
            plan["tickers"] = values["tickers"]
        else:
            plan["tickers"] = [values["tickers"]]

    # Legacy field support (for backwards compatibility with old clarifications)
    if "ticker" in values and values["ticker"]:
        tickers = plan.get("tickers", [])
        if values["ticker"] not in tickers:
            tickers.insert(0, values["ticker"])
            plan["tickers"] = tickers

    if "custom_ticker" in values and values["custom_ticker"]:
        custom = values["custom_ticker"].upper().strip()
        tickers = plan.get("tickers", [])
        if custom not in tickers:
            tickers.insert(0, custom)
            plan["tickers"] = tickers

    if "timeframe" in values:
        plan["time_range"] = values["timeframe"]

    if "period" in values:
        plan["period"] = values["period"]

    if "margin_types" in values:
        plan["margin_types"] = values["margin_types"]
    
    # Update state
    state.plan_json = plan
    responses = state.params.get("clarification_responses") or {}
    if isinstance(responses, dict):
        responses[request.request_id] = {"values": values, "skipped": request.skipped}
    state.update_params({
        "clarified": True,
        "pending_clarification": None,
        "clarification_responses": responses,
        **values,
    })
    
    return {
        "status": "success",
        "dashboard_id": dashboard_id,
        "plan": plan,
        "values": values,
    }


@router.get("/showcase", response_class=HTMLResponse)
async def get_showcase():
    """
    Serve the Generative UI showcase/demo page.
    
    Returns static HTML with skills overview, architecture diagram,
    and click-to-try example queries.
    """
    showcase_path = Path(__file__).parent.parent / "static" / "showcase.html"
    if not showcase_path.exists():
        raise HTTPException(status_code=404, detail="Showcase not found")
    
    return HTMLResponse(content=showcase_path.read_text(encoding="utf-8"))


@router.get("/catalog")
async def get_catalog():
    """
    Get the A2UI component catalog definition.
    
    Per A2UI v0.8 spec (Section 3.2), this endpoint provides catalog negotiation
    allowing clients to discover available components before rendering.
    
    Function: get_catalog — returns A2UI component catalog for client negotiation.
    Called from: Frontend A2UI clients during initialization
    Invokes: backend.generative_ui.a2ui.catalog.get_catalog
    Why: Enables proper A2UI client-server catalog negotiation per spec.
    
    See: https://a2ui.org/specification/v0.8-a2ui/#section-3-basic-concepts
    """
    from ..a2ui.catalog import get_catalog as get_a2ui_catalog
    catalog = get_a2ui_catalog()
    
    return {
        "catalogId": catalog.catalog_id,
        "extends": catalog.definition.extends,
        "components": {
            name: {
                "description": comp.description,
                "properties": {
                    prop_name: {
                        "type": prop.type,
                        "required": prop.required,
                        **({"default": prop.default} if prop.default else {}),
                        **({"enum": prop.enum} if prop.enum else {}),
                        **({"description": prop.description} if prop.description else {}),
                    }
                    for prop_name, prop in comp.properties.items()
                }
            }
            for name, comp in catalog.definition.components.items()
        },
    }


# helper removed in favor of a2ui.error_surface


@router.get("/{dashboard_id}/debug")
async def get_debug_bundle(dashboard_id: str):
    """
    Get a complete debug bundle for a dashboard.
    
    Returns structured trace data for debugging without reading logs.
    """
    from ..traces import get_trace_store
    
    store = get_dashboard_store()
    state = store.get(dashboard_id)
    
    if not state:
        raise HTTPException(status_code=404, detail="Dashboard not found")
    
    trace_store = get_trace_store()
    bundle = trace_store.get_debug_bundle(dashboard_id)
    
    # Merge in plan data
    bundle["plan"] = state.plan_json
    bundle["params"] = state.params
    
    return bundle


@router.get("/{dashboard_id}/debug/download")
async def download_debug_bundle(dashboard_id: str):
    """
    Download the debug bundle as a JSON attachment.
    
    Includes trace data, plan, params, and latest run snapshot for offline triage.
    """
    from ..traces import get_trace_store

    store = get_dashboard_store()
    state = store.get(dashboard_id)

    if not state:
        raise HTTPException(status_code=404, detail="Dashboard not found")

    trace_store = get_trace_store()
    bundle = trace_store.get_debug_bundle(dashboard_id)
    payload = {
        "dashboard_id": dashboard_id,
        "plan": state.plan_json,
        "params": state.params,
        "latest_run": state.latest_run.model_dump() if state.latest_run else None,
        "trace_bundle": bundle,
    }
    content = json.dumps(payload, default=str)
    return Response(
        content=content,
        media_type="application/json",
        headers={
            "Content-Disposition": f'attachment; filename=\"dashboard-{dashboard_id}-debug.json\"'
        },
    )


@router.get("/{dashboard_id}/traces")
async def get_traces(dashboard_id: str):
    """
    Get all traces for a dashboard.
    """
    from ..traces import get_trace_store
    
    store = get_dashboard_store()
    state = store.get(dashboard_id)
    
    if not state:
        raise HTTPException(status_code=404, detail="Dashboard not found")
    
    trace_store = get_trace_store()
    traces = trace_store.get_for_dashboard(dashboard_id)
    
    return {
        "dashboard_id": dashboard_id,
        "trace_count": len(traces),
        "traces": [t.to_dict() for t in traces],
    }
