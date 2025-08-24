"""LangGraph implementation for Next Gen Analytics (Memory).

This module defines the state model and a supervisor that performs
cache-aware routing. Most nodes are implemented as lightweight
functions in `nodes/`.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple, TypedDict


class DataFrameArtifact(TypedDict):
    location: str
    schema: Dict[str, Any]
    stats: Dict[str, Any]
    created_at: float


class ChartArtifact(TypedDict):
    spec: Dict[str, Any]
    created_at: float


class SQLArtifact(TypedDict):
    sql: str
    params: Dict[str, Any]
    sql_hash: str
    schema_fp: str
    window: str
    created_at: float


class PlanStep(TypedDict):
    node: str
    inputs: Dict[str, Any]
    outputs: Dict[str, Any]
    cache_hit: bool
    latency_ms: float
    ts: float


class BudgetState(TypedDict):
    time_ms_left: int
    tokens_left: int
    bytes_left: int


class AnalyticsState(TypedDict):
    """Full conversation and artifact state for the analytics agent."""

    # Core conversation state
    messages: List[dict]
    current_query: str
    params: Dict[str, Any]

    # Typed artifact registries
    df_registry: Dict[str, DataFrameArtifact]
    chart_registry: Dict[Tuple[str, str], ChartArtifact]
    sql_registry: Dict[str, SQLArtifact]

    # Execution tracking
    plan_history: List[PlanStep]
    last_df_key: Optional[str]
    last_sql_key: Optional[str]
    last_chart_key: Optional[Tuple[str, str]]

    # Human interaction
    needs_clarification: bool
    clarification_options: List[str]

    # Resource management
    budget: BudgetState

    # Analysis outputs
    analysis_memo: Optional[str]
    suggested_questions: List[str]


class SmartSupervisor:
    """Supervisor that routes requests based on cache state."""

    def route(self, state: AnalyticsState) -> str:
        """Return the next node to execute based on available artifacts."""
        # 1. Reuse existing chart if user is pivoting visualization
        if state.get("last_chart_key") in state.get("chart_registry", {}):
            return "render_chart"

        # 2. Reuse dataframe if SQL already executed
        if state.get("last_sql_key") in state.get("df_registry", {}):
            return "render_chart"

        # 3. Need to plan if no SQL available
        if not state.get("last_sql_key"):
            return "planning"

        # 4. Default to SQL execution
        return "sql_executor"


__all__ = [
    "AnalyticsState",
    "SmartSupervisor",
]
