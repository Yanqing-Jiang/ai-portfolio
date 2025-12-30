"""
Dashboard API Routes

FastAPI endpoints for A2UI dashboard management.
"""

from __future__ import annotations
import logging
from typing import Any, Dict, Optional
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import json

from ..a2ui import A2UIMessageGenerator
from ..models import DashboardPlan, get_dashboard_store
from ..agent import get_dashboard_agent, DashboardAgentError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/dash", tags=["dashboard"])


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


# ============================================================================
# Endpoints
# ============================================================================

@router.post("/create", response_model=CreateDashboardResponse)
async def create_dashboard(request: CreateDashboardRequest):
    """
    Create a new dashboard from a user question.
    
    This endpoint:
    1. Sends the question to Claude for planning
    2. Creates a dashboard state
    3. Returns the dashboard ID for streaming
    """
    store = get_dashboard_store()
    
    try:
        # Use Claude agent for plan generation
        agent = get_dashboard_agent()
        plan = await agent.generate_plan(request.question)
        logger.info("[DASHBOARD] Generated plan: archetype=%s, widgets=%d", 
                   plan.archetype, len(plan.widgets))
    except DashboardAgentError as e:
        logger.warning("[DASHBOARD] Agent error: %s", e)
        raise HTTPException(status_code=500, detail=f"Plan generation failed: {e}")
    
    # Override ticker if provided
    if request.ticker:
        plan.ticker = request.ticker
    
    # Create dashboard state
    state = store.create(
        question=request.question,
        plan=plan.model_dump()
    )
    
    return CreateDashboardResponse(
        dashboard_id=state.dashboard_id,
        surface_id=state.surface_id
    )



@router.get("/{dashboard_id}/stream")
async def stream_dashboard(dashboard_id: str):
    """
    Stream A2UI messages for a dashboard.
    
    Returns Server-Sent Events with A2UI JSONL payloads.
    """
    store = get_dashboard_store()
    state = store.get(dashboard_id)
    
    if not state:
        raise HTTPException(status_code=404, detail="Dashboard not found")
    
    async def generate():
        # Create A2UI generator
        a2ui = A2UIMessageGenerator(
            surface_id=state.surface_id,
            catalog_id=state.catalog_id
        )
        
        # Reconstruct plan from stored JSON
        plan = DashboardPlan(**state.plan_json)
        
        # Stream structure
        for msg in a2ui.generate_from_plan(plan):
            yield f"data: {msg}\n\n"
        
        # Execute SQL queries via shared tool
        agent = get_dashboard_agent()
        try:
            query_data = await agent.execute_queries(plan)
        except Exception as exc:
            for msg in a2ui.error_surface("query_execution_failed", str(exc)):
                yield f"data: {msg}\n\n"
            yield f"data: {json.dumps({'done': True})}\n\n"
            return

        # Persist run results
        state.add_run(query_data)

        # Attempt to stream data to widgets
        first_query = query_data.get("query_0") if query_data else None
        if first_query and first_query.get("success") and first_query.get("rows"):
            first_row = first_query["rows"][0]
            data_msg = a2ui.update_price_data(
                price=first_row.get("close", first_row.get("value", 0)),
                volume=first_row.get("volume", 0),
                change=first_row.get("change", 0),
                change_percent=first_row.get("change_percent", 0)
            )
            yield f"data: {data_msg}\n\n"
        else:
            # Stream error into data model so the frontend can render JSON dump
            details = first_query.get("error") if first_query else "No query results"
            for msg in a2ui.error_surface("query_failed", details):
                yield f"data: {msg}\n\n"
        
        # Signal completion
        yield f"data: {json.dumps({'done': True})}\n\n"
    
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
async def handle_action(dashboard_id: str, request: ActionRequest):
    """
    Handle a user action (A2UI userAction message).
    
    Processes the action and returns updated data or layout.
    """
    store = get_dashboard_store()
    state = store.get(dashboard_id)
    
    if not state:
        raise HTTPException(status_code=404, detail="Dashboard not found")
    
    action = request.userAction
    action_name = action.get("name")
    context = action.get("context", {})
    
    # Route to action handlers
    if action_name == "change_timeframe":
        new_timeframe = context.get("timeframe", "1M")
        state.update_params({"timeRange": new_timeframe})
        
        # Re-run data queries with updated timeframe
        agent = get_dashboard_agent()
        plan = DashboardPlan(**state.plan_json)
        plan.time_range = new_timeframe
        query_data = await agent.execute_queries(plan)
        state.add_run(query_data)
        return {
            "status": "success",
            "action": action_name,
            "updated_params": {"timeRange": new_timeframe},
            "data": query_data,
        }
    
    elif action_name == "add_ticker":
        new_ticker = context.get("ticker")
        if new_ticker:
            peers = state.params.get("peers", [])
            if new_ticker not in peers:
                peers.append(new_ticker)
                state.update_params({"peers": peers})
        
        return {
            "status": "success",
            "action": action_name,
            "updated_params": {"peers": state.params.get("peers", [])},
            "refresh_data": True,
        }
    
    elif action_name == "export_csv":
        # TODO: Generate CSV export
        return {
            "status": "success",
            "action": action_name,
            "download_url": f"/api/dash/{dashboard_id}/export/csv",
        }
    
    else:
        return {
            "status": "unknown_action",
            "action": action_name,
        }


@router.delete("/{dashboard_id}")
async def delete_dashboard(dashboard_id: str):
    """
    Delete a dashboard.
    """
    store = get_dashboard_store()
    
    if store.delete(dashboard_id):
        return {"status": "deleted", "dashboard_id": dashboard_id}
    else:
        raise HTTPException(status_code=404, detail="Dashboard not found")


# helper removed in favor of a2ui.error_surface
