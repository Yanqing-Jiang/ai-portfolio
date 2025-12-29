"""
Dashboard Plan Models

Pydantic models for structured dashboard planning output from Claude.
"""

from __future__ import annotations
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field


class DashboardWidget(BaseModel):
    """A single widget in the dashboard."""
    type: Literal["price_chart", "kpi", "table", "news_timeline", "correlation", "explain_move"]
    config: Dict[str, Any] = Field(default_factory=dict)
    
    class Config:
        extra = "allow"


class DashboardPlan(BaseModel):
    """
    Structured dashboard plan output from Claude.
    
    Claude analyzes the user's question and produces this structured plan,
    which is then converted to A2UI messages by the generator.
    """
    
    # Core metadata
    title: str = Field(description="Dashboard title")
    ticker: str = Field(description="Primary ticker symbol")
    peers: List[str] = Field(default_factory=list, description="Peer/comparison tickers")
    time_range: str = Field(default="3M", description="Default time range")
    
    # Question classification
    archetype: Literal["explain_move", "compare", "screen", "monitor", "portfolio_doctor"] = Field(
        description="Type of analysis question"
    )
    
    # Dashboard composition
    widgets: List[DashboardWidget] = Field(
        default_factory=list,
        description="Widgets to display"
    )
    
    # Data requirements
    sql_queries: List[str] = Field(
        default_factory=list,
        description="SQL queries to execute for data"
    )
    research_queries: List[str] = Field(
        default_factory=list,
        description="Web research queries for context/news"
    )
    
    # Optional actions
    available_actions: List[str] = Field(
        default_factory=lambda: ["change_timeframe", "add_ticker", "toggle_indicator", "export_csv"],
        description="Actions available to user"
    )
    
    class Config:
        extra = "allow"
    
    @classmethod
    def example_explain_move(cls) -> "DashboardPlan":
        """Example plan for 'explain move' question."""
        return cls(
            title="NVDA Price Movement Analysis - Dec 18, 2024",
            ticker="NVDA",
            peers=["AMD", "INTC"],
            time_range="1M",
            archetype="explain_move",
            widgets=[
                DashboardWidget(type="price_chart", config={"interval": "1D", "showVolume": True}),
                DashboardWidget(type="kpi", config={"label": "Price", "dataKey": "price", "unit": "$"}),
                DashboardWidget(type="kpi", config={"label": "Change", "dataKey": "change", "unit": "%", "deltaKey": "changeDelta"}),
                DashboardWidget(type="kpi", config={"label": "Volume", "dataKey": "volume", "unit": "M"}),
                DashboardWidget(type="news_timeline", config={}),
                DashboardWidget(type="explain_move", config={"showCitations": True}),
            ],
            sql_queries=[
                "SELECT date, close, volume FROM stock_prices WHERE ticker = 'NVDA' AND date >= '2024-11-18'",
            ],
            research_queries=[
                "NVDA stock news December 18 2024",
                "NVIDIA earnings guidance December 2024",
            ],
        )
    
    @classmethod
    def example_compare(cls) -> "DashboardPlan":
        """Example plan for 'compare' question."""
        return cls(
            title="AAPL vs MSFT vs SPY Comparison",
            ticker="AAPL",
            peers=["MSFT", "SPY"],
            time_range="1Y",
            archetype="compare",
            widgets=[
                DashboardWidget(type="price_chart", config={"interval": "1W", "showVolume": False}),
                DashboardWidget(type="table", config={"sortable": True}),
                DashboardWidget(type="correlation", config={}),
            ],
            sql_queries=[
                "SELECT ticker, date, close FROM stock_prices WHERE ticker IN ('AAPL', 'MSFT', 'SPY') AND date >= '2023-01-01'",
                "SELECT ticker, revenue, eps, pe_ratio FROM fundamentals WHERE ticker IN ('AAPL', 'MSFT')",
            ],
            research_queries=[],
        )
