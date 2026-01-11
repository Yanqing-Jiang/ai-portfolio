# --- Follow-up Generator Function/Class Map ---
# Module: follow_up_generator
#   Role: Unified follow-up suggestion generation for A2UI dashboards.
#   Called from: backend.generative_ui.runtime.A2UIRuntime, backend.generative_ui.routes.dashboard
#   Invokes: LLM wrapper (optional), heuristic suggestion logic
#   Why: Single source of truth for follow-up suggestion logic, avoiding divergence.
# --- End Function/Class Map ---
"""
Unified follow-up suggestion generator.

This module provides a single source of truth for generating context-aware
follow-up suggestions, preventing divergence between runtime and endpoint logic.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from pydantic import BaseModel

logger = logging.getLogger(__name__)


class FollowUpSuggestion(BaseModel):
    """
    A follow-up query suggestion.
    
    Class: FollowUpSuggestion
    Called from: generate_follow_ups, get_follow_up_suggestions endpoint
    Why: Standardized data structure for follow-up suggestions.
    """
    id: str
    label: str
    query: str
    icon: str = ">"  # ASCII-safe icon placeholder
    category: Optional[str] = None
    priority: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


# Skill-to-suggestion mapping for rule-based generation
SKILL_SUGGESTION_TEMPLATES = {
    "a2ui_explain_move": [
        {"label": "Analyst views", "query_template": "What are analysts saying about {ticker}?", "icon": "[news]"},
        {"label": "Compare peers", "query_template": "Compare {ticker} to its competitors", "icon": "[peers]"},
        {"label": "Revenue trend", "query_template": "Show {ticker} revenue trend", "icon": "[trend]"},
    ],
    "a2ui_peer_compare": [
        {"label": "Stock movement", "query_template": "Explain {ticker} stock movement", "icon": "[price]"},
        {"label": "Best margins", "query_template": "Which company has the best margins?", "icon": "[kpi]"},
        {"label": "Revenue breakdown", "query_template": "Show quarterly revenue breakdown", "icon": "[table]"},
    ],
    "a2ui_margin_analysis": [
        {"label": "Compare margins", "query_template": "Compare {ticker} margins to peers", "icon": "[peers]"},
        {"label": "Margin drivers", "query_template": "What drove {ticker} margin changes?", "icon": "[deep]"},
        {"label": "Margin trend", "query_template": "Show margin trend over time", "icon": "[trend]"},
    ],
    "a2ui_revenue_trend": [
        {"label": "Growth drivers", "query_template": "Explain {ticker} growth drivers", "icon": "[deep]"},
        {"label": "Peer comparison", "query_template": "Compare {ticker} revenue to peers", "icon": "[peers]"},
        {"label": "Earnings outlook", "query_template": "What's the earnings outlook?", "icon": "[forecast]"},
    ],
}

DEFAULT_SUGGESTIONS = [
    {"label": "Deeper analysis", "query_template": "Tell me more about {ticker}", "icon": "[analysis]"},
    {"label": "Compare peers", "query_template": "Compare to industry peers", "icon": "[peers]"},
    {"label": "What's the outlook?", "query_template": "What's the outlook for {ticker}?", "icon": "[forecast]"},
]


def generate_follow_ups(
    skill_id: str,
    tickers: List[str],
    data_model: Optional[Dict[str, Any]] = None,
    include_data_insights: bool = True,
    max_suggestions: int = 3,
) -> List[FollowUpSuggestion]:
    """
    Generate contextual follow-up suggestions.
    
    Function: generate_follow_ups — unified follow-up generation logic.
    Called from: A2UIRuntime._generate_follow_ups, dashboard.get_follow_up_suggestions
    Invokes: _extract_data_insights (when data_model provided)
    Why: Single source of truth for follow-up suggestion logic.
    
    Args:
        skill_id: The current A2UI skill ID (e.g., "a2ui_explain_move")
        tickers: List of tickers in the current context
        data_model: Optional data model for data-aware suggestions
        include_data_insights: Whether to include data-derived suggestions
        max_suggestions: Maximum number of suggestions to return
        
    Returns:
        List of FollowUpSuggestion objects
    """
    primary_ticker = tickers[0] if tickers else "the stock"
    
    suggestions: List[FollowUpSuggestion] = []
    
    # Get skill-specific templates
    templates = SKILL_SUGGESTION_TEMPLATES.get(skill_id, DEFAULT_SUGGESTIONS)
    
    # Generate base suggestions from templates
    for i, template in enumerate(templates[:max_suggestions]):
        query = template["query_template"].format(ticker=primary_ticker)
        suggestions.append(FollowUpSuggestion(
            id=f"follow_up_{i+1}",
            label=template["label"],
            query=query,
            icon=template.get("icon", ">"),
            category="skill_based",
        ))
    
    # Add data-aware suggestions if data_model is provided
    if include_data_insights and data_model:
        data_suggestions = _extract_data_insights(
            skill_id=skill_id,
            tickers=tickers,
            data_model=data_model,
            existing_count=len(suggestions),
            max_additional=max(0, max_suggestions - len(suggestions)),
        )
        suggestions.extend(data_suggestions)
    
    return suggestions[:max_suggestions]


def _extract_data_insights(
    skill_id: str,
    tickers: List[str],
    data_model: Dict[str, Any],
    existing_count: int = 0,
    max_additional: int = 2,
) -> List[FollowUpSuggestion]:
    """
    Extract data-driven follow-up suggestions from the data model.
    
    Function: _extract_data_insights
    Called from: generate_follow_ups
    Invokes: n/a
    Why: Creates intelligent follow-ups that reference specific data points.
    """
    suggestions: List[FollowUpSuggestion] = []
    primary_ticker = tickers[0] if tickers else "the stock"
    
    if max_additional <= 0:
        return suggestions
    
    kpis = data_model.get("kpis", {})
    table_rows = data_model.get("table", {}).get("rows", [])
    
    # Find significant changes
    significant_decline = None
    leader_ticker = None
    
    for row in table_rows:
        ticker = row.get("ticker", "")
        yoy = row.get("yoy_change")
        latest = row.get("latest_value")
        
        # Track significant declines
        if yoy is not None and yoy < -20:
            significant_decline = {"ticker": ticker, "change": yoy}
        
        # Track leader (highest value)
        if latest is not None:
            if leader_ticker is None or latest > leader_ticker.get("value", 0):
                leader_ticker = {"ticker": ticker, "value": latest}
    
    # Add insight-based suggestion if decline found
    if significant_decline and skill_id in ("a2ui_peer_compare", "a2ui_revenue_trend"):
        suggestions.append(FollowUpSuggestion(
            id=f"insight_{existing_count + 1}",
            label=f"Why {significant_decline['ticker']} declined",
            query=f"Why did {significant_decline['ticker']} decline {abs(significant_decline['change']):.0f}%?",
            icon="[deep]",
            category="data_insight",
            priority="high",
        ))
    
    # Add margin insight if margins seem notable
    gross_margin = kpis.get("gross_margin")
    if gross_margin is not None and gross_margin > 50 and skill_id == "a2ui_margin_analysis":
        suggestions.append(FollowUpSuggestion(
            id=f"insight_{existing_count + len(suggestions) + 1}",
            label="High margin analysis",
            query=f"Why is {primary_ticker} gross margin at {gross_margin:.1f}%?",
            icon="[kpi]",
            category="data_insight",
            priority="medium",
        ))
    
    return suggestions[:max_additional]


def generate_follow_ups_simple(
    skill_id: str,
    tickers: List[str],
) -> List[str]:
    """
    Generate simple follow-up queries as list of strings.
    
    Function: generate_follow_ups_simple — backward-compatible string-based follow-ups.
    Called from: A2UIRuntime._generate_follow_ups (legacy)
    Invokes: generate_follow_ups
    Why: Provides backward compatibility with existing runtime interface.
    
    Args:
        skill_id: The current A2UI skill ID
        tickers: List of tickers in the current context
        
    Returns:
        List of query strings
    """
    suggestions = generate_follow_ups(
        skill_id=skill_id,
        tickers=tickers,
        data_model=None,
        include_data_insights=False,
        max_suggestions=3,
    )
    return [s.query for s in suggestions]
