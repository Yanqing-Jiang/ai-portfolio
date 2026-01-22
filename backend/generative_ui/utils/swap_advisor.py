# --- Swap Advisor Function/Class Map ---
# Module: swap_advisor
#   Role: Generate ranked component swap suggestions (heuristic + LLM).
#   Called from: backend.generative_ui.routes.dashboard.get_swap_suggestions
#   Invokes: LLM wrapper (optional), heuristic fallback logic
#   Why: Provides intelligent swap recommendations based on data context.
# Function: suggest_swaps_for_component — heuristic-based suggestion generation.
# Function: suggest_swaps_with_llm — LLM-enhanced suggestion generation with fallback.
# --- End Function/Class Map ---
"""
Swap advisor for component visualization recommendations.

This module provides both heuristic and LLM-driven suggestions for
swapping dashboard components to better visualizations.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Available swap targets with metadata
SWAP_TARGETS = {
    "MetricChart": {
        "icon": "📊",
        "label": "Metric Chart",
        "description": "Line/area chart for trends over time",
        "best_for": ["time series", "trends", "comparisons"],
    },
    "DataTable": {
        "icon": "📋",
        "label": "Data Table",
        "description": "Sortable table for detailed data",
        "best_for": ["exact values", "filtering", "many records"],
    },
    "KpiCard": {
        "icon": "🎯",
        "label": "KPI Card",
        "description": "Single metric highlight",
        "best_for": ["key metrics", "at-a-glance", "changes"],
    },
    "PriceChart": {
        "icon": "📈",
        "label": "Price Chart",
        "description": "Stock price visualization",
        "best_for": ["stock prices", "trading data"],
    },
}


def suggest_swaps_for_component(current_type: str, data_model: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Generate ranked swap suggestions based on component type and data characteristics.
    
    Args:
        current_type: The current component type (e.g. 'PriceChart')
        data_model: The full dashboard data model (to inspect available data shapes)
        
    Returns:
        List of suggestion dicts with targetType, reason, score, icon.
    """
    suggestions = []
    
    # 1. Analyze Data Characteristics from the shared model
    # Note: This is a simplification. Ideally we'd look at the specific component's bound data.
    # But for now, we look at what's available globally in the latest_run.
    
    has_chart_data = bool(data_model.get("chart", {}).get("series"))
    has_table_data = bool(data_model.get("table", {}).get("rows"))
    table_rows = data_model.get("table", {}).get("rows", [])
    row_count = len(table_rows)
    
    # 2. Heuristic Rules
    
    # Case: Chart -> Table
    if current_type in ("MetricChart", "PriceChart"):
        score = 0.8
        reason = "View exact values"

        if row_count > 10:
            score = 0.9
            reason = "View, sort, and filter detailed data"

        suggestions.append({
            "targetType": "DataTable",
            "reason": reason,
            "score": score,
            "icon": SWAP_TARGETS["DataTable"]["icon"],
            "label": SWAP_TARGETS["DataTable"]["label"],
        })
        
    # Case: Table -> Chart
    if current_type == "DataTable":
        if has_chart_data or _infer_chart_compatibility(table_rows):
            suggestions.append({
                "targetType": "MetricChart",
                "reason": "Visualize trends and patterns",
                "score": 0.9,
                "icon": SWAP_TARGETS["MetricChart"]["icon"],
                "label": SWAP_TARGETS["MetricChart"]["label"],
            })

    # Case: KPI -> Chart or Table
    if current_type == "KpiCard":
        if has_chart_data:
            suggestions.append({
                "targetType": "MetricChart",
                "reason": "See historical trend context",
                "score": 0.85,
                "icon": SWAP_TARGETS["MetricChart"]["icon"],
                "label": SWAP_TARGETS["MetricChart"]["label"],
            })
        if has_table_data:
            suggestions.append({
                "targetType": "DataTable",
                "reason": "View underlying data records",
                "score": 0.75,
                "icon": SWAP_TARGETS["DataTable"]["icon"],
                "label": SWAP_TARGETS["DataTable"]["label"],
            })

    # Case: Peer Comparison
    if current_type == "PeerComparePanel":
        suggestions.append({
            "targetType": "SplitView",
            "reason": "Separate Chart and Table for clarity",
            "score": 0.85,
            "icon": "📐",
            "label": "Split View",
        })
        suggestions.append({
            "targetType": "DataTable",
            "reason": "Focus on ranking metrics",
            "score": 0.8,
            "icon": SWAP_TARGETS["DataTable"]["icon"],
            "label": SWAP_TARGETS["DataTable"]["label"],
        })

    # Sort by score descending
    return sorted(suggestions, key=lambda x: x["score"], reverse=True)

def _infer_chart_compatibility(rows: List[Dict[str, Any]]) -> bool:
    """Check if table rows look like they can be charted (numeric values + time/category)."""
    if not rows:
        return False

    has_numeric = False
    has_label = False

    sample = rows[0]
    for key, val in sample.items():
        if isinstance(val, (int, float)) and not isinstance(val, bool):
            has_numeric = True
        if key in ("period", "date", "year", "quarter", "ticker", "name"):
            has_label = True

    return has_numeric and has_label


def _summarize_data_for_llm(data_model: Dict[str, Any]) -> str:
    """
    Create a concise summary of the data model for LLM context.

    Function: _summarize_data_for_llm
    Called from: suggest_swaps_with_llm
    Why: Provides data context without overwhelming the LLM.
    """
    parts = []

    # KPIs summary
    kpis = data_model.get("kpis", {})
    if kpis:
        kpi_items = [f"{k}: {v}" for k, v in list(kpis.items())[:5] if v is not None]
        if kpi_items:
            parts.append(f"KPIs: {', '.join(kpi_items)}")

    # Chart data summary
    chart = data_model.get("chart", {})
    series = chart.get("series", [])
    if series:
        series_names = [s.get("name", s.get("metric", "Series")) for s in series[:3]]
        data_points = len(series[0].get("values", [])) if series else 0
        parts.append(f"Chart: {len(series)} series ({', '.join(series_names)}), {data_points} points")

    # Table data summary
    table = data_model.get("table", {})
    rows = table.get("rows", [])
    if rows:
        columns = list(rows[0].keys()) if rows else []
        parts.append(f"Table: {len(rows)} rows, columns: {', '.join(columns[:5])}")

    # Tickers
    tickers = data_model.get("tickers", [])
    if tickers:
        parts.append(f"Tickers: {', '.join(tickers[:5])}")

    return "; ".join(parts) if parts else "No data available"


async def suggest_swaps_with_llm(
    current_type: str,
    data_model: Dict[str, Any],
    component_id: Optional[str] = None,
    max_suggestions: int = 3,
) -> List[Dict[str, Any]]:
    """
    Generate LLM-enhanced swap suggestions based on component and data context.

    Function: suggest_swaps_with_llm — LLM-driven suggestions with fallback.
    Called from: backend.generative_ui.routes.dashboard.get_swap_suggestions.
    Invokes: A2UISDKWrapper.query, suggest_swaps_for_component.
    Why: Provides intelligent, context-aware swap recommendations.

    Args:
        current_type: Current component type (e.g., 'KpiCard')
        data_model: Dashboard data model for context
        component_id: Optional component ID for specific context
        max_suggestions: Maximum suggestions to return

    Returns:
        List of suggestion dicts with targetType, reason, score, icon.
    """
    # Get heuristic fallback first
    fallback = suggest_swaps_for_component(current_type, data_model)

    # Try to import Anthropic SDK
    try:
        from ..sdk_wrapper import ANTHROPIC_AVAILABLE, get_sdk_wrapper
    except ImportError:
        logger.warning("[SWAP_ADVISOR] SDK wrapper not available, using heuristic")
        return fallback

    if not ANTHROPIC_AVAILABLE:
        return fallback

    # Build data summary for LLM
    data_summary = _summarize_data_for_llm(data_model)

    # Build list of available targets (excluding current type)
    available_targets = [
        f"- {name}: {info['description']} (best for: {', '.join(info['best_for'])})"
        for name, info in SWAP_TARGETS.items()
        if name != current_type
    ]

    prompt = f"""You are a data visualization expert. A user is viewing a {current_type} component showing financial data.

Data Context:
{data_summary}

Available visualization options:
{chr(10).join(available_targets)}

Based on the data characteristics, rank the top {max_suggestions} alternative visualizations from the list above.
Consider:
- Data shape (time series vs categories vs single values)
- Number of data points (few vs many)
- User intent (exploring trends, comparing values, finding details)

Return ONLY a JSON array with {max_suggestions} objects:
[
  {{"targetType": "ComponentName", "reason": "Brief reason (10 words max)", "score": 0.85}},
  ...
]

Score should be 0.0-1.0 based on how well the visualization fits the data.
Return ONLY valid JSON, no other text."""

    try:
        wrapper = get_sdk_wrapper()
        if not wrapper.is_initialized:
            await wrapper.initialize()

        response = await wrapper.query(
            prompt=prompt,
            max_tokens=300,
            temperature=0.3,  # Lower temp for more consistent rankings
        )

        if response.error or not response.content:
            logger.warning("[SWAP_ADVISOR] LLM query failed: %s", response.error)
            return fallback

        content = response.content.strip()

        # Extract JSON array from response
        start_idx = content.find('[')
        end_idx = content.rfind(']') + 1
        if start_idx < 0 or end_idx <= start_idx:
            logger.warning("[SWAP_ADVISOR] LLM response missing JSON array")
            return fallback

        suggestions_data = json.loads(content[start_idx:end_idx])

        # Validate and format suggestions
        suggestions: List[Dict[str, Any]] = []
        for item in suggestions_data[:max_suggestions]:
            target_type = item.get("targetType", "")
            if target_type not in SWAP_TARGETS:
                continue  # Skip invalid targets

            target_info = SWAP_TARGETS[target_type]
            suggestions.append({
                "targetType": target_type,
                "reason": item.get("reason", target_info["description"]),
                "score": min(1.0, max(0.0, float(item.get("score", 0.7)))),
                "icon": target_info["icon"],
                "label": target_info["label"],
                "llm_generated": True,
            })

        if suggestions:
            logger.info("[SWAP_ADVISOR] LLM generated %d suggestions", len(suggestions))
            return sorted(suggestions, key=lambda x: x["score"], reverse=True)

        return fallback

    except json.JSONDecodeError as e:
        logger.error("[SWAP_ADVISOR] JSON parse error: %s", e)
        return fallback
    except Exception as exc:
        logger.error("[SWAP_ADVISOR] LLM suggestion error: %s", exc)
        return fallback
