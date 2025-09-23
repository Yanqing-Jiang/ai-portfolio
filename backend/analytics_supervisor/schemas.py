from __future__ import annotations
from typing import List, Optional, Dict, Any, Literal
from pydantic import BaseModel, Field

class ToolInputs(BaseModel):
    """Tool inputs - flexible schema for various tool parameters"""
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

    class Config:
        extra = "forbid"

class ToolStep(BaseModel):
    """A single step in the execution plan"""
    tool: str = Field(description="Tool name to call")
    description: str = Field(description="What this step accomplishes")
    inputs: ToolInputs = Field(default_factory=ToolInputs, description="Expected inputs for the tool")
    expected_output: str = Field(description="Brief description of expected output")

    class Config:
        extra = "forbid"

class PlanSchema(BaseModel):
    """
    Planning schema for Claude Code-style single agent supervision.

    The agent proposes a plan with steps for execution.
    """
    plan: str = Field(description="Short natural-language description of the overall plan")
    steps: List[ToolStep] = Field(description="Ordered list of tool steps to execute")
    reasoning: str = Field(description="Agent's reasoning for this plan approach")

    class Config:
        extra = "forbid"

class FinalSummarySchema(BaseModel):
    """
    Final summary schema for workflow completion.

    Provides concise summaries of what was accomplished and suggestions
    for follow-up questions.
    """
    sql_summary: str = Field(description="Brief summary of the SQL query executed")
    chart_summary: str = Field(description="Brief summary of the chart generated")
    key_findings: List[str] = Field(description="2-3 key insights from the analysis")
    data_summary: str = Field(description="Summary of the data retrieved (rows, timeframe, etc.)")
    next_questions: List[str] = Field(description="Suggested follow-up questions", default_factory=list)
    execution_time: Optional[str] = Field(description="How long the analysis took", default=None)

    class Config:
        extra = "forbid"


class ToolExecution(BaseModel):
    """
    Schema for tool execution events.
    """
    tool: str = Field(description="Tool name")
    status: str = Field(description="start, success, or error")
    args_summary: Optional[str] = Field(description="Brief summary of arguments", default=None)
    output_summary: Optional[str] = Field(description="Brief summary of output", default=None)
    error_message: Optional[str] = Field(description="Error message if status is error", default=None)
    latency_ms: Optional[int] = Field(description="Execution time in milliseconds", default=None)

    class Config:
        extra = "forbid"

class ExecutionStep(BaseModel):
    """Enhanced execution tracking for individual tool calls"""
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

    class Config:
        extra = "forbid"

class WorkflowState(BaseModel):
    """
    Enhanced internal state tracking for the supervisor workflow.
    """
    session_id: str
    current_phase: str = Field(description="planning, executing, analysis, completed")
    plan: Optional[PlanSchema] = None
    executed_tools: List[str] = Field(default_factory=list)
    execution_steps: List[ExecutionStep] = Field(default_factory=list, description="Detailed execution tracking")
    sql_executed: Optional[str] = None
    data_retrieved: Optional[List[Dict[str, Any]]] = None
    chart_spec: Optional[Dict[str, Any]] = None
    structured_query_artifact: Optional[Dict[str, Any]] = None
    errors: List[str] = Field(default_factory=list)
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    clarification_answer: Optional[Any] = None
    early_exit: bool = Field(default=False, description="Flag to indicate early exit for non-financial queries")

    # Enhanced state management
    last_successful_tool: Optional[str] = None
    failed_tools: List[str] = Field(default_factory=list)
    recovery_attempts: int = Field(default=0, description="Number of workflow recovery attempts")

    # Caching fields for performance optimization
    cached_intent: Optional[Dict[str, Any]] = Field(default=None, description="Cached intent detection result")
    cached_plan: Optional[Dict[str, Any]] = Field(default=None, description="Cached query plan")
    cached_template: Optional[Dict[str, Any]] = Field(default=None, description="Cached template selection")
    cached_analysis: Optional[Dict[str, Any]] = Field(default=None, description="Cached short financial analysis")
    tool_results_cache: Dict[str, Any] = Field(default_factory=dict, description="Cache for tool execution results")
    session_metadata: Dict[str, Any] = Field(default_factory=dict, description="Session-specific metadata for optimization")

    # Performance tracking
    intent_detection_duration_ms: Optional[int] = None
    tool_execution_duration_ms: Optional[int] = None
    total_api_calls: int = Field(default=0, description="Total number of API calls made")
    cache_hits: int = Field(default=0, description="Number of cache hits for performance tracking")

    class Config:
        extra = "forbid"

class OffTopicClassifierSchema(BaseModel):
    """
    Schema for classifying whether a query is relevant to financial analytics.

    Used to implement early exit for off-topic queries with polite responses.
    """
    is_financial_query: bool = Field(description="True if query is about financial data, metrics, or analysis")
    confidence: float = Field(description="Confidence score (0.0-1.0) in the classification", ge=0.0, le=1.0)
    topic_category: Literal[
        "financial_analytics",
        "general_conversation",
        "technical_support",
        "personal_questions",
        "other"
    ] = Field(description="Category of the detected topic")
    polite_decline_message: Optional[str] = Field(
        description="Polite message to send if query is off-topic",
        default=None
    )
    suggested_rephrase: Optional[str] = Field(
        description="Suggestion for how to rephrase query to be financial analytics focused",
        default=None
    )

    class Config:
        extra = "forbid"

class ClarificationOption(BaseModel):
    """Individual option for clarification choices"""
    value: str = Field(description="Option value")
    label: str = Field(description="Display label for user")
    description: Optional[str] = Field(default=None, description="Additional context")
    recommended: bool = Field(default=False, description="Whether this is the recommended choice")

    class Config:
        extra = "forbid"

class ClarificationField(BaseModel):
    """Enhanced clarification field with modern UX features"""
    field_id: str = Field(description="Unique field identifier")
    type: Literal["select", "multi_select", "text", "number", "date", "radio"] = Field(description="Input type")
    label: str = Field(description="Field label")
    description: Optional[str] = Field(default=None, description="Help text")
    placeholder: Optional[str] = Field(default=None, description="Placeholder text")
    required: bool = Field(default=True, description="Whether field is required")

    # Options for choice fields
    options: List[ClarificationOption] = Field(default_factory=list, description="Available options")

    # Validation
    min_length: Optional[int] = None
    max_length: Optional[int] = None
    pattern: Optional[str] = None

    # Smart defaults
    suggested_value: Optional[str] = Field(default=None, description="AI-suggested value")
    confidence: float = Field(default=0.0, ge=0.0, le=1.0, description="Confidence in suggestion")

    # UX enhancements
    icon: Optional[str] = Field(default=None, description="Icon for the field")
    priority: int = Field(default=0, description="Display priority (higher first)")

    class Config:
        extra = "forbid"

class ModernClarificationRequest(BaseModel):
    """Modern clarification request with enhanced UX"""
    request_id: str = Field(description="Unique request identifier")
    session_id: str = Field(description="Session identifier")

    # Content
    title: str = Field(description="Clarification title")
    subtitle: Optional[str] = Field(default=None, description="Additional context")
    explanation: Optional[str] = Field(default=None, description="Why this is needed")

    # Fields
    fields: List[ClarificationField] = Field(description="Clarification fields")

    # UX Flow
    step_number: int = Field(default=1, description="Current step in multi-step flow")
    total_steps: int = Field(default=1, description="Total steps in flow")
    can_skip: bool = Field(default=False, description="Whether user can skip this step")

    # Smart features
    progress_percentage: float = Field(default=0.0, ge=0.0, le=100.0, description="Progress percentage")
    estimated_time_seconds: Optional[int] = Field(default=None, description="Estimated completion time")

    # Context
    original_query: str = Field(description="Original user query")
    detected_intent: Optional[str] = Field(default=None, description="Detected intent if any")

    class Config:
        extra = "forbid"

class ClarificationResponse(BaseModel):
    """User response to clarification request"""
    request_id: str = Field(description="Request being answered")
    session_id: str = Field(description="Session identifier")
    field_responses: Dict[str, Any] = Field(description="Field ID to value mapping")
    completed_at: str = Field(description="Completion timestamp")
    user_feedback: Optional[str] = Field(default=None, description="Optional user feedback")

    class Config:
        extra = "forbid"

class StructuredQueryArtifact(BaseModel):
    """
    Structured query artifact - single source of truth for SQL generation.

    This artifact consolidates all query parameters from intent detection
    and serves as the standardized input for SQL generation tools.
    """
    # Core Query Intent
    intent_key: str = Field(description="Primary intent classification (e.g., 'market_share_single')")
    confidence: float = Field(description="Confidence in intent classification", ge=0.0, le=1.0)

    # Query Components
    company: Optional[str] = Field(default=None, description="Target company for analysis")
    metrics: List[str] = Field(default_factory=list, description="Requested metrics/KPIs")
    timeframe: Optional[str] = Field(default=None, description="Time period for analysis")
    comparison_type: Optional[str] = Field(default=None, description="Single company vs all companies")

    # SQL Generation Parameters
    sql_strategy: str = Field(default="template", description="SQL generation strategy")
    template_id: Optional[str] = Field(default=None, description="Template identifier if using template strategy")

    # Analysis Parameters
    granularity: str = Field(default="annual", description="Data granularity (annual/quarterly)")
    limit: int = Field(default=500, description="Result limit")

    # Context and Metadata
    original_query: str = Field(description="Original user question")
    assumptions: List[str] = Field(default_factory=list, description="Assumptions made during processing")
    session_id: str = Field(description="Session identifier")

    # Validation Status
    is_complete: bool = Field(description="Whether artifact has all required parameters")
    missing_components: List[str] = Field(default_factory=list, description="Components still needed")

    class Config:
        extra = "forbid"