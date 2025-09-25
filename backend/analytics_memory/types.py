from __future__ import annotations
from typing import Any, Dict, List, Literal, Optional, TypedDict, Union
from pydantic import BaseModel, Field, ValidationError, ConfigDict
from analytics_shared.intent import (
    ClarifyAnswerModel,
    ClarificationSuggestionModel,
    ClarifyRequestModel,
    IntentModel,
    LLMClarificationSuggestionModel,
    LLMIntentModel,
    PossibleIntentModel,
    SlotsModel,
    TimeframeModel,
)


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

class QueryPlanModel(BaseModel):
    metrics: List[str] = Field(default_factory=list)
    derived_metrics: List[str] = Field(default_factory=list)
    timeframe: TimeframeModel = Field(default_factory=TimeframeModel)
    granularity: Literal['annual', 'quarterly'] = 'annual'
    comparison: Optional[str] = None
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


class ClarifyErrorModel(BaseModel):
    request_id: str = Field(..., description="ID of the clarification request with error")
    slot: str = Field(..., description="The slot with error")
    message: str = Field(..., description="Error message")


class QuestionAnalysisModel(BaseModel):
    question: str = Field(..., description="The original question")
    intent_confidence: float = Field(0.0, ge=0.0, le=1.0, description="Confidence in intent detection")
    missing_slots: List[str] = Field(default_factory=list, description="Slots that need clarification")
    assumptions: List[str] = Field(default_factory=list, description="Assumptions made in analysis")
    ready_to_proceed: bool = Field(False, description="Whether we can proceed without clarification")


class ClarificationArtifactModel(BaseModel):
    session_id: str = Field(..., description="Session ID for this clarification")
    pending_requests: List[ClarifyRequestModel] = Field(default_factory=list, description="Outstanding clarification requests")
    answered_requests: List[ClarifyAnswerModel] = Field(default_factory=list, description="Completed clarification answers")
    clarification_state: Literal['pending', 'partial', 'complete'] = Field('pending', description="State of clarification process")

