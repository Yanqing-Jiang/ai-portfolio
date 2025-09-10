from __future__ import annotations
from typing import Any, Dict, List, Literal, Optional, TypedDict, Union
from pydantic import BaseModel, Field, ValidationError

# LangGraph-friendly state (lightweight). Pydantic models will validate node IO.
class WorkflowState(TypedDict, total=False):
    query: str
    step: str
    intent: Dict[str, Any]
    query_plan: Dict[str, Any]
    sql_plan: Dict[str, Any]
    sql: str
    data: List[Dict[str, Any]]
    chart_plan: Dict[str, Any]
    chart_spec: Dict[str, Any]
    analysis: str
    errors: List[str]
    meta: Dict[str, Any]
    # Phase 3: Clarification support
    session_id: str
    assumptions: List[str]
    pending_slots: List[str]


# Pydantic models for validating node IO (lightweight for Phase 1)
class SQLResultModel(BaseModel):
    query: str
    data: List[Dict[str, Any]] = Field(default_factory=list)


class ChartSpecModel(BaseModel):
    title: Dict[str, Any] = Field(default_factory=dict)
    series: List[Dict[str, Any]] = Field(default_factory=list)
    xAxis: Optional[Any] = None
    yAxis: Optional[Any] = None


# ---------- Phase 2 Models ----------

class IntentModel(BaseModel):
    intent_key: Optional[str] = None
    confidence: float = Field(0.0, ge=0.0, le=1.0)
    slots_detected: Dict[str, Any] = Field(default_factory=dict)
    assumptions: List[str] = Field(default_factory=list)
    
    # Advisory fields for early clarification detection
    clarifications_suggested: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Lightweight hints: [{slot: 'company', reason: '...'}]"
    )
    possible_intents: List[Dict[str, float]] = Field(
        default_factory=list,
        description="Alternative interpretations: [{'market_share_all': 0.3}]"
    )
    intent_reasoning: str = Field(
        default="",
        description="Brief 1-2 line rationale for the chosen intent"
    )


class TimeframeModel(BaseModel):
    years_back: Optional[int] = Field(default=4, ge=0, le=10)
    start_year: Optional[int] = None
    end_year: Optional[int] = None


class QueryPlanModel(BaseModel):
    metrics: List[str] = Field(default_factory=list)
    derived_metrics: List[str] = Field(default_factory=list)
    timeframe: TimeframeModel = Field(default_factory=TimeframeModel)
    granularity: Literal['annual', 'quarterly'] = 'annual'
    comparison: Optional[str] = None  # 'vs_peers'|'vs_avg'|'single'|'all'
    group_by: List[str] = Field(default_factory=list)
    filters: Dict[str, Any] = Field(default_factory=dict)
    limit: int = 500


class SQLPlanModel(BaseModel):
    strategy: Literal['template', 'generic'] = 'template'
    template_id: Optional[str] = None
    params: Dict[str, Any] = Field(default_factory=dict)
    measures: List[str] = Field(default_factory=list)
    group_by: List[str] = Field(default_factory=list)
    constraints: List[str] = Field(default_factory=list)


class ChartSeriesModel(BaseModel):
    name: str
    data_column: str
    value_type: Literal['currency', 'percent', 'number'] = 'number'


class ChartAxisModel(BaseModel):
    field: Optional[str] = None
    type: Optional[Literal['category', 'time', 'value', 'log']] = None


class ChartPlanModel(BaseModel):
    chart_type: Literal['line', 'bar', 'scatter', 'pie', 'heatmap'] = 'line'
    x_axis: ChartAxisModel = Field(default_factory=ChartAxisModel)
    series: List[ChartSeriesModel] = Field(default_factory=list)
    title: str = 'Analytics'
    highlight_rules: List[Dict[str, Any]] = Field(default_factory=list)


# ---------- Phase 3 Clarification Models ----------

class ClarifyRequestModel(BaseModel):
    slot: str = Field(..., description="The slot name needing clarification")
    question: str = Field(..., description="The question to ask the user")
    type: Literal['single', 'multi', 'free'] = Field(..., description="Type of input expected")
    options: List[str] = Field(default_factory=list, description="Available options for single/multi selection")
    default: Optional[Any] = None
    reason: str = Field(default="", description="Why this slot needs clarification")
    required: bool = Field(True, description="Whether this slot is required")
    request_id: str = Field(..., description="Unique ID for this clarification request")
    proposed: Optional[Any] = Field(None, description="LLM-proposed value")
    proposed_confidence: float = Field(0.0, ge=0.0, le=1.0, description="Confidence in proposed value")


class ClarifyAnswerModel(BaseModel):
    session_id: str = Field(..., description="Session ID for this analytics session")
    request_id: str = Field(..., description="ID of the clarification request being answered")
    slot: str = Field(..., description="The slot being answered")
    value: Any = Field(..., description="The user's answer")
    ts: str = Field(..., description="Timestamp of the answer")


class ClarifyErrorModel(BaseModel):
    request_id: str = Field(..., description="ID of the clarification request with error")
    slot: str = Field(..., description="The slot with error")
    message: str = Field(..., description="Error message")
