from __future__ import annotations
from typing import Any, Dict, List, Literal, Optional, TypedDict, Union
from pydantic import BaseModel, Field, ValidationError, ConfigDict

from .intent import (
    ClarifyAnswerModel,
    ClarificationSuggestionModel,
    ClarifyRequestModel,
    IntentModel,
    LLMClarificationSuggestionModel,
    LLMIntentModel,
    OffTopicClassifierSchema,
    PossibleIntentModel,
    SlotsModel,
    TimeframeModel,
)

__all__ = [
    "PlannerResultModel",
    "WorkflowState",
    "SQLResultModel",
    "ChartSpecModel",
    "QueryPlanModel",
    "SQLPlanModel",
    "ChartSeriesModel",
    "ChartAxisModel",
    "ChartPlanModel",
    "ClarifyErrorModel",
    "QuestionAnalysisModel",
    "ClarificationArtifactModel",
    "SupervisorToolInputs",
    "SupervisorToolStep",
    "SupervisorPlanSchema",
    "SupervisorToolExecution",
    "SupervisorExecutionStep",
    "SupervisorWorkflowState",
    "FinalSummarySchema",
    "ClarificationOption",
    "ClarificationField",
    "ModernClarificationRequest",
    "ClarificationResponse",
    "StructuredQueryArtifact",
    "ClarifyRequestModel",
    "ClarifyAnswerModel",
    "ClarificationSuggestionModel",
    "LLMClarificationSuggestionModel",
    "IntentModel",
    "LLMIntentModel",
    "PossibleIntentModel",
    "SlotsModel",
    "TimeframeModel",
    "OffTopicClassifierSchema",
    "ValidationError",
]

class PlannerResultModel(BaseModel):
    """Aggregated outputs from PlannerExecutorFlow."""

    intent: Optional[IntentModel] = None
    clarification_requests: List[ClarifyRequestModel] = Field(default_factory=list)
    sql_attempts: List[Dict[str, Any]] = Field(default_factory=list)
    sql_text: Optional[str] = None
    data_row_count: Optional[int] = None
    chart_summary: Optional[Dict[str, Any]] = None
    analysis: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)






class WorkflowState(TypedDict, total=False):
    """Shared lightweight workflow state passed between analytics agents."""

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
    session_id: str
    assumptions: List[str]
    pending_slots: List[str]
    thinking: str
    years_back: int
    granularity: str


class SQLResultModel(BaseModel):
    query: str
    data: List[Dict[str, Any]] = Field(default_factory=list)


class ChartSpecModel(BaseModel):
    title: Dict[str, Any] = Field(default_factory=dict)
    series: List[Dict[str, Any]] = Field(default_factory=list)
    xAxis: Optional[Any] = None
    yAxis: Optional[Any] = None


class QueryPlanModel(BaseModel):
    metrics: List[str] = Field(default_factory=list)
    derived_metrics: List[str] = Field(default_factory=list)
    timeframe: TimeframeModel = Field(default_factory=TimeframeModel)
    granularity: Literal["annual", "quarterly"] = "annual"
    comparison: Optional[str] = None
    statistic: Optional[str] = None
    group_by: List[str] = Field(default_factory=list)
    filters: Dict[str, Any] = Field(default_factory=dict)
    limit: int = 500


class SQLPlanModel(BaseModel):
    strategy: Literal["template", "generic"] = "template"
    template_id: Optional[str] = None
    params: Dict[str, Any] = Field(default_factory=dict)
    measures: List[str] = Field(default_factory=list)
    group_by: List[str] = Field(default_factory=list)
    constraints: List[str] = Field(default_factory=list)


class ChartSeriesModel(BaseModel):
    name: str
    data_column: Optional[str] = None
    value_type: Literal["currency", "percent", "number"] = "number"
    open_column: Optional[str] = None
    high_column: Optional[str] = None
    low_column: Optional[str] = None
    close_column: Optional[str] = None
    volume_column: Optional[str] = None
    ticker_filter: Optional[str] = None
    sort: Optional[Literal["ascending", "descending"]] = None

    model_config = ConfigDict(extra="ignore")


class ChartAxisModel(BaseModel):
    field: Optional[str] = None
    type: Optional[Literal["category", "time", "value", "log"]] = None


class ChartPlanModel(BaseModel):
    chart_type: Literal["line", "bar", "scatter", "pie", "heatmap", "candlestick", "ranking_bar"] = "line"
    x_axis: ChartAxisModel = Field(default_factory=ChartAxisModel)
    series: List[ChartSeriesModel] = Field(default_factory=list)
    title: str = "Analytics"
    highlight_rules: List[Dict[str, Any]] = Field(default_factory=list)
    statistic: Optional[str] = None
    ranking_metric: Optional[str] = None

    model_config = ConfigDict(extra="ignore")


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
    clarification_state: Literal["pending", "partial", "complete"] = Field("pending", description="State of clarification process")


# ---------------------------------------------------------------------------
# Supervisor-oriented models (formerly analytics_supervisor.schemas)
# ---------------------------------------------------------------------------


class SupervisorToolInputs(BaseModel):
    """Tool inputs - flexible schema for various tool parameters."""

    query: Optional[str] = None
    question: Optional[str] = None
    sql: Optional[str] = None
    data: Optional[str] = None
    intent: Optional[str] = None
    plan: Optional[str] = None
    template: Optional[str] = None
    intent_key: Optional[str] = None
    top_k: Optional[int] = None
    granularity: Optional[str] = None
    chart_plan: Optional[str] = None

    model_config = ConfigDict(extra="forbid")


class SupervisorToolStep(BaseModel):
    """A single step in a supervisor-managed execution plan."""

    tool: str = Field(description="Tool name to call")
    description: str = Field(description="What this step accomplishes")
    inputs: SupervisorToolInputs = Field(default_factory=SupervisorToolInputs, description="Expected inputs for the tool")
    expected_output: str = Field(description="Brief description of expected output")

    model_config = ConfigDict(extra="forbid")


class SupervisorPlanSchema(BaseModel):
    """Planning schema for Claude Code-style single agent supervision."""

    plan: str = Field(description="Short natural-language description of the overall plan")
    steps: List[SupervisorToolStep] = Field(description="Ordered list of tool steps to execute")
    reasoning: str = Field(description="Agent's reasoning for this plan approach")

    model_config = ConfigDict(extra="forbid")


class FinalSummarySchema(BaseModel):
    """Final summary schema for workflow completion."""

    sql_summary: str = Field(description="Brief summary of the SQL query executed")
    chart_summary: str = Field(description="Brief summary of the chart generated")
    key_findings: List[str] = Field(description="2-3 key insights from the analysis")
    data_summary: str = Field(description="Summary of the data retrieved (rows, timeframe, etc.)")
    next_questions: List[str] = Field(default_factory=list, description="Suggested follow-up questions")
    execution_time: Optional[str] = Field(default=None, description="How long the analysis took")

    model_config = ConfigDict(extra="forbid")


class SupervisorToolExecution(BaseModel):
    """Schema for tool execution events."""

    tool: str = Field(description="Tool name")
    status: str = Field(description="start, success, or error")
    args_summary: Optional[str] = Field(default=None, description="Brief summary of arguments")
    output_summary: Optional[str] = Field(default=None, description="Brief summary of output")
    error_message: Optional[str] = Field(default=None, description="Error message if status is error")
    latency_ms: Optional[int] = Field(default=None, description="Execution time in milliseconds")

    model_config = ConfigDict(extra="forbid")


class SupervisorExecutionStep(BaseModel):
    """Enhanced execution tracking for individual tool calls."""

    step_id: str = Field(description="Unique identifier for this execution step")
    tool_name: str = Field(description="Name of the tool being executed")
    status: Literal["pending", "running", "success", "error", "retrying"] = Field(description="Current execution status")
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    duration_ms: Optional[int] = None
    retry_count: int = Field(default=0, description="Number of retry attempts")
    error_message: Optional[str] = None
    input_summary: Optional[str] = None
    output_summary: Optional[str] = None

    model_config = ConfigDict(extra="forbid")


class SupervisorWorkflowState(BaseModel):
    """Enhanced internal state tracking for supervisor-driven workflows."""

    session_id: str
    current_phase: str = Field(description="planning, executing, analysis, completed")
    plan: Optional[SupervisorPlanSchema] = None
    executed_tools: List[str] = Field(default_factory=list)
    execution_steps: List[SupervisorExecutionStep] = Field(default_factory=list, description="Detailed execution tracking")
    sql_executed: Optional[str] = None
    data_retrieved: Optional[List[Dict[str, Any]]] = None
    chart_spec: Optional[Dict[str, Any]] = None
    structured_query_artifact: Optional[Dict[str, Any]] = None
    errors: List[str] = Field(default_factory=list)
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    clarification_answer: Optional[Any] = None
    early_exit: bool = Field(default=False, description="Flag to indicate early exit for non-financial queries")
    last_successful_tool: Optional[str] = None
    failed_tools: List[str] = Field(default_factory=list)
    recovery_attempts: int = Field(default=0, description="Number of workflow recovery attempts")
    cached_intent: Optional[Dict[str, Any]] = Field(default=None, description="Cached intent detection result")

    model_config = ConfigDict(extra="forbid")


# Backwards compatibility exports
ValidationError = ValidationError
ClarificationSuggestionModel = ClarificationSuggestionModel
LLMClarificationSuggestionModel = LLMClarificationSuggestionModel
LLMIntentModel = LLMIntentModel
PossibleIntentModel = PossibleIntentModel
SlotsModel = SlotsModel
OffTopicClassifierSchema = OffTopicClassifierSchema
TimeframeModel = TimeframeModel
ClarifyAnswerModel = ClarifyAnswerModel
ClarifyRequestModel = ClarifyRequestModel
IntentModel = IntentModel
class ClarificationOption(BaseModel):
    """Individual option for clarification choices."""

    value: str = Field(description="Option value")
    label: str = Field(description="Display label for user")
    description: Optional[str] = Field(default=None, description="Additional context")
    recommended: bool = Field(default=False, description="Whether this is the recommended choice")

    model_config = ConfigDict(extra="forbid")


class ClarificationField(BaseModel):
    """Enhanced clarification field with modern UX features."""

    field_id: str = Field(description="Unique field identifier")
    type: Literal["select", "multi_select", "text", "number", "date", "radio"] = Field(description="Input type")
    label: str = Field(description="Field label")
    description: Optional[str] = Field(default=None, description="Help text")
    placeholder: Optional[str] = Field(default=None, description="Placeholder text")
    required: bool = Field(default=True, description="Whether field is required")
    options: List[ClarificationOption] = Field(default_factory=list, description="Available options")
    min_length: Optional[int] = None
    max_length: Optional[int] = None
    pattern: Optional[str] = None
    suggested_value: Optional[str] = Field(default=None, description="AI-suggested value")
    confidence: float = Field(default=0.0, ge=0.0, le=1.0, description="Confidence in suggestion")
    icon: Optional[str] = Field(default=None, description="Icon for the field")
    priority: int = Field(default=0, description="Display priority (higher first)")

    model_config = ConfigDict(extra="forbid")


class ModernClarificationRequest(BaseModel):
    """Modern clarification request with enhanced UX."""

    request_id: str = Field(description="Unique request identifier")
    session_id: str = Field(description="Session identifier")
    title: str = Field(description="Clarification title")
    subtitle: Optional[str] = Field(default=None, description="Additional context")
    explanation: Optional[str] = Field(default=None, description="Why this is needed")
    fields: List[ClarificationField] = Field(description="Clarification fields")
    step_number: int = Field(default=1, description="Current step in multi-step flow")
    total_steps: int = Field(default=1, description="Total steps in flow")
    can_skip: bool = Field(default=False, description="Whether user can skip this step")
    progress_percentage: float = Field(default=0.0, ge=0.0, le=100.0, description="Progress percentage")
    estimated_time_seconds: Optional[int] = Field(default=None, description="Estimated completion time")
    original_query: str = Field(description="Original user query")
    detected_intent: Optional[str] = Field(default=None, description="Detected intent if any")

    model_config = ConfigDict(extra="forbid")


class ClarificationResponse(BaseModel):
    """User response to clarification request."""

    request_id: str = Field(description="Request being answered")
    session_id: str = Field(description="Session identifier")
    field_responses: Dict[str, Any] = Field(description="Field ID to value mapping")
    completed_at: str = Field(description="Completion timestamp")
    user_feedback: Optional[str] = Field(default=None, description="Optional user feedback")

    model_config = ConfigDict(extra="forbid")


class StructuredQueryArtifact(BaseModel):
    """Structured query artifact used as single source of truth for SQL generation."""

    intent_key: str = Field(description="Primary intent classification (e.g., 'market_share_single')")
    confidence: float = Field(description="Confidence in intent classification", ge=0.0, le=1.0)
    company: Optional[str] = Field(default=None, description="Target company for analysis")
    metrics: List[str] = Field(default_factory=list, description="Requested metrics/KPIs")
    timeframe: Optional[str] = Field(default=None, description="Time period for analysis")
    comparison_type: Optional[str] = Field(default=None, description="Single company vs all companies")
    sql_strategy: str = Field(default="template", description="SQL generation strategy")
    template_id: Optional[str] = Field(default=None, description="Template identifier if using template strategy")
    granularity: str = Field(default="annual", description="Data granularity (annual/quarterly)")
    limit: int = Field(default=500, description="Result limit")
    original_query: str = Field(description="Original user question")
    assumptions: List[str] = Field(default_factory=list, description="Assumptions made during processing")
    session_id: str = Field(description="Session identifier")
    is_complete: bool = Field(description="Whether artifact has all required parameters")
    missing_components: List[str] = Field(default_factory=list, description="Components still needed")

    model_config = ConfigDict(extra="forbid")
