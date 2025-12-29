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

from ..a2ui import A2UIMessageGenerator, DashboardPlanner, DashboardSynthesizer
from ..models import DashboardPlan, get_dashboard_store
from ..config import get_settings
from conversational_analytics.database.executor import execute_sql


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
    """
    store = get_dashboard_store()
    settings = get_settings()
    
    # Use LLM Planner
    planner = DashboardPlanner(api_key=settings.claude_api_key)
    try:
        plan = await planner.generate_plan(request.question)
    except Exception as e:
        print(f"Planning failed: {e}")
        # Fallback to keyword-based examples if LLM fails
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
    """
    store = get_dashboard_store()
    state = store.get(dashboard_id)
    settings = get_settings()
    
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
        
        # 1. Stream structure immediately
        for msg in a2ui.generate_from_plan(plan):
            yield f"data: {msg}\n\n"
        
        # 2. Execute Data Fetching
        tool_results = {}
        
        # Execute SQL if present
        if plan.sql_queries:
            sql_results = []
            for query in plan.sql_queries:
                try:
                    result = await execute_sql(query)
                    sql_results.append(result)
                except Exception as e:
                    print(f"SQL Error: {e}")
            tool_results["sql"] = sql_results
            
        # TODO: Execute Search if present
        
        # 3. Synthesize with Gemini
        synthesizer = DashboardSynthesizer(api_key=settings.gemini_api_key)
        data_model_dict = await synthesizer.synthesize(plan, tool_results)
        
        # 4. Stream data updates
        if data_model_dict:
            entries = a2ui.dict_to_data_entries(data_model_dict)
            msg = a2ui.data_model_update(entries)
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
