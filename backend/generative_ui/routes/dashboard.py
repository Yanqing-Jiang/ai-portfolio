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
# Function: create_dashboard
#   Role: Create a dashboard state and preselect an A2UI skill.
#   Called from: FastAPI POST /api/dash/create
#   Invokes: backend.generative_ui.agent_v2.A2UIAgent.select_skill, backend.generative_ui.models.get_dashboard_store
#   Why: Persists dashboard metadata before streaming begins.
# Function: stream_dashboard
#   Role: Stream A2UI messages for a dashboard session.
#   Called from: FastAPI GET /api/dash/{dashboard_id}/stream
#   Invokes: backend.generative_ui.agent_v2.A2UIAgent.stream_dashboard
#   Why: Drives the live A2UI SSE stream for the frontend.
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
# Function: handle_action
#   Role: Process incoming A2UI userAction requests.
#   Called from: FastAPI POST /api/dash/{dashboard_id}/action
#   Invokes: backend.generative_ui.agent_v2.A2UIAgent.execute_skill
#   Why: Keeps dashboard interactions aligned with the A2UI agent pipeline.
# Function: delete_dashboard
#   Role: Delete a dashboard state entry.
#   Called from: FastAPI DELETE /api/dash/{dashboard_id}
#   Invokes: backend.generative_ui.models.get_dashboard_store
#   Why: Cleans up server-side dashboard state.
# --- End Dashboard Route Function/Class Map ---
"""
Dashboard API Routes

FastAPI endpoints for A2UI dashboard management.
"""

from __future__ import annotations
import logging
from pathlib import Path
from typing import Any, Dict, Optional
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse, HTMLResponse
from pydantic import BaseModel

from ..models import get_dashboard_store
from ..agent_v2 import get_a2ui_agent, A2UIAgentError
from ..clarification import (
    ClarificationResponse,
    validate_clarification_response,
)

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


class ClarificationSubmitRequest(BaseModel):
    """Submit user's clarification response."""
    request_id: str
    values: Dict[str, Any]
    skipped: bool = False


# ============================================================================
# Endpoints
# ============================================================================

@router.post("/create", response_model=CreateDashboardResponse)
async def create_dashboard(request: CreateDashboardRequest):
    """
    Create a new dashboard from a user question.
    
    This endpoint:
    1. Selects an A2UI skill and stores the plan
    2. Creates a dashboard state
    3. Returns the dashboard ID for streaming
    """
    store = get_dashboard_store()
    
    try:
        agent = get_a2ui_agent()
        selection = await agent.select_skill(request.question)
        if request.ticker:
            selection = selection.model_copy(update={"tickers": [request.ticker]})
        plan = agent.selection_to_plan(selection)
        logger.info("[DASHBOARD] Selected skill: %s", plan.get("skill_id"))
    except A2UIAgentError as e:
        logger.warning("[DASHBOARD] Agent error: %s", e)
        raise HTTPException(status_code=500, detail=f"Skill selection failed: {e}")
    
    # Create dashboard state
    state = store.create(
        question=request.question,
        plan=plan
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
        agent = get_a2ui_agent()

        def _record_result(result):
            state.add_run(result.data_model, result.citations)

        async for msg in agent.stream_dashboard(
            question=state.question,
            surface_id=state.surface_id,
            plan=state.plan_json,
            on_result=_record_result,
        ):
            yield f"data: {msg}\n\n"
    
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

        try:
            state.plan_json["time_range"] = new_timeframe
            agent = get_a2ui_agent()
            selection = agent.selection_from_plan(state.plan_json)
            skill = agent.skill_lookup[selection.skill_id]
            result = await agent.execute_skill(skill, selection)
            state.add_run(result.data_model, result.citations)
            return {
                "status": "success",
                "action": action_name,
                "updated_params": {"timeRange": new_timeframe},
                "data": result.data_model,
            }
        except A2UIAgentError as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    elif action_name == "add_ticker":
        new_ticker = context.get("ticker")
        if new_ticker:
            tickers = list(state.plan_json.get("tickers") or [])
            if new_ticker not in tickers:
                tickers.append(new_ticker)
                state.plan_json["tickers"] = tickers
                state.update_params({"peers": tickers[1:]})
        
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
    
    # If user skipped, just return to let LLM decide
    if request.skipped:
        return {
            "status": "skipped",
            "dashboard_id": dashboard_id,
            "message": "Proceeding with AI-selected options",
        }
    
    # Extract clarification values and merge into plan
    values = request.values
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
            plan["skill_id"] = "a2ui_peer_compare"
            plan["metric"] = "Stock Price"
    
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
    state.update_params({"clarified": True, **values})
    
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


# helper removed in favor of a2ui.error_surface
