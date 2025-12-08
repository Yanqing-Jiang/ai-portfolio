"""Pydantic models for Conversational Analytics API."""
from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional, Union
from pydantic import BaseModel, Field


# Request Models
class ChatRequest(BaseModel):
    """Request body for chat endpoint."""
    message: str = Field(..., description="User's analytics question")
    session_id: str = Field(..., description="Session identifier for conversation history")


# SSE Event Models
class StatusEvent(BaseModel):
    """Status update event."""
    type: Literal["status"] = "status"
    data: Dict[str, str]


class ThinkingEvent(BaseModel):
    """Thinking process step event."""
    type: Literal["thinking"] = "thinking"
    data: Dict[str, Any]  # step, status (pending/running/completed/error), message


class ToolStartEvent(BaseModel):
    """Tool execution start event."""
    type: Literal["tool_start"] = "tool_start"
    data: Dict[str, Any]  # tool, input


class ToolEndEvent(BaseModel):
    """Tool execution end event."""
    type: Literal["tool_end"] = "tool_end"
    data: Dict[str, Any]  # tool, result, success


class ContentEvent(BaseModel):
    """Streaming content delta event."""
    type: Literal["content"] = "content"
    data: Dict[str, str]  # delta


class ChartEvent(BaseModel):
    """Chart configuration event."""
    type: Literal["chart"] = "chart"
    data: Dict[str, Any]  # config (TradingView widget config)


class DataEvent(BaseModel):
    """Data result event."""
    type: Literal["data"] = "data"
    data: Dict[str, Any]  # rows, columns


class DoneEvent(BaseModel):
    """Stream completion event."""
    type: Literal["done"] = "done"
    data: Dict[str, Any] = Field(default_factory=dict)


class ErrorEvent(BaseModel):
    """Error event."""
    type: Literal["error"] = "error"
    data: Dict[str, str]  # message, code


SSEEvent = Union[
    StatusEvent, ThinkingEvent, ToolStartEvent, ToolEndEvent,
    ContentEvent, ChartEvent, DataEvent, DoneEvent, ErrorEvent
]


# Tool Input/Output Models
class SQLQueryInput(BaseModel):
    """Input for SQL query tool."""
    query: str = Field(..., description="Natural language query to convert to SQL")


class SQLQueryOutput(BaseModel):
    """Output from SQL query tool."""
    sql: str
    rows: List[Dict[str, Any]]
    columns: List[str]
    row_count: int


class TradingViewConfig(BaseModel):
    """TradingView widget configuration."""
    symbol: str
    interval: str = "D"
    timezone: str = "America/New_York"
    theme: str = "dark"
    style: str = "1"  # Candlestick
    locale: str = "en"
    toolbar_bg: str = "#1e1e1e"
    enable_publishing: bool = False
    hide_side_toolbar: bool = False
    allow_symbol_change: bool = True
    container_id: str = ""
    width: str = "100%"
    height: int = 400


class AnalysisOutput(BaseModel):
    """Output from analysis tool."""
    summary: str
    key_insights: List[str]
    trends: Optional[List[str]] = None
