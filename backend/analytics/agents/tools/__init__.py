"""Default tool registrations for analytics agents."""
from __future__ import annotations

from .analysis import AnalysisSummaryTool
from .charting import ChartPlanningTool
from .clarification import ClarificationTool
from .market import MarketSnapshotTool
from .sql_execution import SqlExecutionTool
from .sql_generation import SqlMessageTool
from .web_search import WebSearchTool
from ..tool_registry import ToolRegistry


def register_default_tools(registry: ToolRegistry) -> None:
    """Register baseline analytics tools on the provided registry."""

    registry.register(ClarificationTool())
    registry.register(SqlMessageTool())
    registry.register(SqlExecutionTool())
    registry.register(ChartPlanningTool())
    registry.register(AnalysisSummaryTool())
    registry.register(MarketSnapshotTool())
    registry.register(WebSearchTool())


__all__ = ["register_default_tools"]
