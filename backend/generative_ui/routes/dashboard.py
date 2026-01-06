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
# --- End Dashboard Route Function/Class Map ---
"""
Dashboard API Routes

FastAPI endpoints for A2UI dashboard management.
"""

from __future__ import annotations
import asyncio
import json
import logging
import time
import uuid
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
    """
    store = get_dashboard_store()
    state = store.get(dashboard_id)

    if not state:
        raise HTTPException(status_code=404, detail="Dashboard not found")

    await smart_rate_limit(
        request,
        scope=A2UI_RATE_LIMIT_SCOPE,
        weight=A2UI_STREAM_WEIGHT,
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
    
    return {
        "status": "deleted",
        "dashboard_id": dashboard_id,
        "surface_id": state.surface_id,
        "a2ui_message": delete_message,  # Client can broadcast this to clean up UI
    }


class FollowUpSuggestion(BaseModel):
    """A follow-up query suggestion."""
    id: str
    label: str
    query: str
    icon: str = ">"  # ASCII-safe icon placeholder


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
    data_model = state.latest_data.get("data", {}) if state.latest_data else {}
    kpis = data_model.get("kpis", {})
    table_rows = data_model.get("table", {}).get("rows", [])
    
    # Generate contextual follow-ups based on data findings
    suggestions = _generate_data_aware_follow_ups(
        skill_id=skill_id,
        primary_ticker=primary_ticker,
        tickers=tickers,
        metric=metric,
        kpis=kpis,
        table_rows=table_rows,
    )
    
    return {"suggestions": [s.model_dump() for s in suggestions]}


def _generate_data_aware_follow_ups(
    skill_id: str,
    primary_ticker: str,
    tickers: list,
    metric: str,
    kpis: dict,
    table_rows: list,
) -> list:
    """
    Generate follow-up suggestions based on actual data findings.
    
    Function: _generate_data_aware_follow_ups
    Called from: get_follow_up_suggestions
    Why: Creates intelligent follow-ups that reference specific data points.
    """
    suggestions = []
    
    # Find interesting data points for contextual follow-ups
    significant_decline = None
    leader_ticker = None
    
    for row in table_rows:
        ticker = row.get("ticker", "")
        yoy = row.get("yoy_change")
        latest = row.get("latest_value")
        
        # Track significant declines
        if yoy is not None and yoy < -20:
            significant_decline = {"ticker": ticker, "change": yoy}
        
        # Track leader (highest value)
        if latest is not None:
            if leader_ticker is None or latest > leader_ticker.get("value", 0):
                leader_ticker = {"ticker": ticker, "value": latest}
    
    # Skill-specific base suggestions
    if skill_id == "a2ui_explain_move":
        suggestions = [
            FollowUpSuggestion(id="1", label="Margin analysis", query=f"Show {primary_ticker} margin analysis", icon="[kpi]"),
            FollowUpSuggestion(id="2", label="Compare peers", query=f"Compare {primary_ticker} to its peers", icon="[peers]"),
            FollowUpSuggestion(id="3", label="Revenue trend", query=f"Show {primary_ticker} revenue trend", icon="[trend]"),
        ]
        
    elif skill_id == "a2ui_margin_analysis":
        # Add context-aware suggestions based on margin values
        gm = kpis.get("gross_margin", 0)
        nm = kpis.get("net_margin", 0)
        
        suggestions = [
            FollowUpSuggestion(id="1", label="Revenue breakdown", query=f"Show {primary_ticker} revenue trend", icon="[trend]"),
        ]
        
        # Add peer comparison if there's only one ticker
        if len(tickers) <= 1:
            suggestions.append(
                FollowUpSuggestion(id="2", label="Compare margins", query=f"Compare {primary_ticker} margins vs AMD and NVDA", icon="[peers]")
            )
        else:
            peer_list = ", ".join(tickers[:3])
            suggestions.append(
                FollowUpSuggestion(id="2", label="Deeper comparison", query=f"Why does {tickers[0] if tickers else primary_ticker} have different margins than {tickers[1] if len(tickers) > 1 else 'peers'}?", icon="[deep]")
            )
        
        suggestions.append(
            FollowUpSuggestion(id="3", label="Stock movement", query=f"Explain recent {primary_ticker} stock movement", icon="[price]")
        )
        
    elif skill_id == "a2ui_revenue_trend":
        suggestions = [
            FollowUpSuggestion(id="1", label="Margin analysis", query=f"Show {primary_ticker} margin analysis", icon="[kpi]"),
            FollowUpSuggestion(id="2", label="YoY comparison", query=f"Compare {primary_ticker} revenue year over year", icon="[trend]"),
            FollowUpSuggestion(id="3", label="Peer comparison", query=f"Compare {primary_ticker} vs INTC revenue", icon="[peers]"),
        ]
        
    elif skill_id == "a2ui_peer_compare":
        peer_list = ", ".join(tickers[:3]) if len(tickers) > 1 else f"{primary_ticker} and INTC"
        
        suggestions = []
        
        # If there's a significant decline, suggest investigating it
        if significant_decline:
            suggestions.append(
                FollowUpSuggestion(
                    id="1", 
                    label=f"Why {significant_decline['ticker']} declined", 
                    query=f"Why did {significant_decline['ticker']} {metric} decline {abs(significant_decline['change']):.0f}%?", 
                    icon="[deep]"
                )
            )
        else:
            suggestions.append(
                FollowUpSuggestion(id="1", label="Deeper on leader", query=f"Show {leader_ticker['ticker'] if leader_ticker else primary_ticker} detailed analysis", icon="[deep]")
            )
        
        suggestions.extend([
            FollowUpSuggestion(id="2", label="Stock comparison", query=f"Compare {peer_list} stock performance", icon="[price]"),
            FollowUpSuggestion(id="3", label="Margin comparison", query=f"Compare {peer_list} margins", icon="[kpi]"),
        ])
        
    else:
        # Default suggestions
        suggestions = [
            FollowUpSuggestion(id="1", label="Deeper analysis", query=f"Tell me more about {primary_ticker}", icon="[analysis]"),
            FollowUpSuggestion(id="2", label="Compare peers", query=f"Compare to industry peers", icon="[peers]"),
        ]
    
    return suggestions


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
    plan = state.plan_json
    
    # Map clarification fields to plan properties
    if "comparison_type" in values:
        comp_type = values["comparison_type"]
        # Switch skill based on comparison type
        if comp_type == "margins":
            plan["skill_id"] = "a2ui_margin_analysis"
        elif comp_type == "revenue":
            plan["skill_id"] = "a2ui_peer_compare"
            plan["metric"] = "Revenue"
        elif comp_type == "stock":
            primary = plan.get("ticker") or (plan.get("tickers") or [None])[0]
            if primary:
                plan["ticker"] = primary
                plan["tickers"] = [primary]
                plan["peers"] = []
            plan["skill_id"] = "a2ui_explain_move"
            plan["metric"] = DEFAULT_METRIC
    
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
