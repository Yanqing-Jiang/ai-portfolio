# --- Function/Class Map ---
# Class: SwapStateSnapshot
#   Role: Pydantic model for a single component's swap state at a point in time.
#   Called from: SwapStateRepository, dashboard routes
#   Invokes: n/a
#   Why: Provides typed, serializable swap state for persistence.
# Class: SwapStateBatch
#   Role: Pydantic model for batch save/load operations.
#   Called from: Dashboard swap state endpoints
#   Invokes: n/a
#   Why: Wraps multiple swap states for efficient batch persistence.
# --- End Function/Class Map ---
"""
Swap State Models

Pydantic models for A2UI component swap state persistence.
"""

from datetime import datetime
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class SwapStateSnapshot(BaseModel):
    """
    Snapshot of a single component's swap state.

    Captures the minimum state needed to restore a component's
    swap configuration across page refreshes.
    """

    component_id: str = Field(..., description="Unique component identifier")
    original_type: str = Field(..., description="Original component type before any swaps")
    current_type: str = Field(..., description="Currently rendered component type")
    history: List[str] = Field(default_factory=list, description="Swap history for undo/redo")
    history_index: int = Field(default=0, description="Current position in history stack")
    is_dirty: bool = Field(default=False, description="Whether component was modified from original")
    updated_at: datetime = Field(default_factory=datetime.utcnow, description="Last modification time")

    # Optional: Server-transformed data (for server swaps)
    transformed_data: Optional[Dict] = Field(default=None, description="Data from server swap transformation")
    warnings: Optional[List[str]] = Field(default=None, description="Warnings from last swap")

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class SwapStateBatch(BaseModel):
    """
    Batch of swap states for bulk operations.

    Used for saving/loading all component swap states for a dashboard.
    """

    dashboard_id: str = Field(..., description="Dashboard identifier")
    states: Dict[str, SwapStateSnapshot] = Field(
        default_factory=dict,
        description="Map of component_id to swap state"
    )
    saved_at: datetime = Field(default_factory=datetime.utcnow, description="Batch save timestamp")

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class SwapStateSaveRequest(BaseModel):
    """Request payload for saving swap states."""
    states: Dict[str, SwapStateSnapshot] = Field(
        ...,
        description="Map of component_id to swap state snapshot"
    )


class SwapStateLoadResponse(BaseModel):
    """Response payload for loading swap states."""
    dashboard_id: str
    states: Dict[str, SwapStateSnapshot]
    loaded_at: datetime = Field(default_factory=datetime.utcnow)
