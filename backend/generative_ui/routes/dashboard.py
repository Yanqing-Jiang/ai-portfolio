"""
Dashboard API Routes

FastAPI endpoints for A2UI dashboard management.
"""

from __future__ import annotations
from typing import Any, Dict, Optional
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import json

from ..a2ui import A2UIMessageGenerator
from ..models import DashboardPlan, get_dashboard_store


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
    
    # TODO: Replace with actual Claude call
    # For now, use example plan based on question keywords
    if "drop" in request.question.lower() or "why" in request.question.lower():
        plan = DashboardPlan.example_explain_move()
    else:
        plan = DashboardPlan.example_compare()
    
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
        
        # TODO: Execute SQL queries and stream data
        # For now, send mock data
        mock_data = {
            "price": 134.25,
            "volume": 89000000,
            "change": -5.2,
            "changePercent": -3.8,
        }
        
        data_msg = a2ui.update_price_data(
            price=mock_data["price"],
            volume=mock_data["volume"],
            change=mock_data["change"],
            change_percent=mock_data["changePercent"]
        )
        yield f"data: {data_msg}\n\n"
        
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
        
        # TODO: Re-run data queries with new timeframe
        return {
            "status": "success",
            "action": action_name,
            "updated_params": {"timeRange": new_timeframe},
            "refresh_data": True,
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
