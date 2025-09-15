from __future__ import annotations
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

class ToolStep(BaseModel):
    """A single step in the execution plan"""
    tool: str = Field(description="Tool name to call")
    description: str = Field(description="What this step accomplishes")
    inputs: Dict[str, Any] = Field(description="Expected inputs for the tool")
    expected_output: str = Field(description="Brief description of expected output")

class PlanSchema(BaseModel):
    """
    Planning schema for Claude Code-style single agent supervision.
    
    The agent proposes a plan with steps and identifies if approval is needed
    for any side-effects (apply_execute_sql).
    """
    plan: str = Field(description="Short natural-language description of the overall plan")
    steps: List[ToolStep] = Field(description="Ordered list of tool steps to execute")
    requires_approval: bool = Field(description="True if any step requires user approval (e.g., SQL execution)")
    apply_targets: List[str] = Field(description="List of apply tools that need approval", default_factory=list)
    risks: List[str] = Field(description="Brief list of potential risks or side-effects", default_factory=list)
    reasoning: str = Field(description="Agent's reasoning for this plan approach")

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

class ApprovalRequest(BaseModel):
    """
    Schema for approval requests sent to the UI.
    """
    session_id: str = Field(description="Session identifier")
    plan_id: str = Field(description="Unique identifier for this plan")
    plan: PlanSchema = Field(description="The proposed plan requiring approval")
    apply_steps: List[ToolStep] = Field(description="Specific steps requiring approval")
    preview_sql: Optional[str] = Field(description="Preview of SQL that will be executed", default=None)

class ApprovalResponse(BaseModel):
    """
    Schema for approval responses from the UI.
    """
    session_id: str = Field(description="Session identifier")
    plan_id: str = Field(description="Plan identifier being responded to")
    approved: bool = Field(description="Whether the plan is approved")
    modifications: Optional[str] = Field(description="Requested modifications if not approved", default=None)

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

class WorkflowState(BaseModel):
    """
    Internal state tracking for the supervisor workflow.
    """
    session_id: str
    current_phase: str = Field(description="planning, approval_pending, executing, analysis, completed")
    plan: Optional[PlanSchema] = None
    approval_granted: bool = False
    executed_tools: List[str] = Field(default_factory=list)
    sql_executed: Optional[str] = None
    data_retrieved: Optional[List[Dict[str, Any]]] = None
    chart_spec: Optional[Dict[str, Any]] = None
    errors: List[str] = Field(default_factory=list)
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    clarification_answer: Optional[Any] = None  # Store the latest clarification answer