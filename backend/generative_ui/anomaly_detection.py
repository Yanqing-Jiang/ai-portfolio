"""
Anomaly Detection Service for A2UI Dashboard.

Function: detect_anomalies
Called from: dashboard.py follow-up suggestions endpoint, agent skill execution
Invokes: Statistical analysis functions
Why: Proactively surfaces non-obvious insights from dashboard data.

Detection Methods:
1. Historical deviation: > 2 std dev from trailing average
2. Quarter-over-quarter change: > 20% change
3. Peer comparison: > 15% deviation from peer average
"""

from typing import Dict, Any, List, Optional
from dataclasses import dataclass
import statistics
from datetime import datetime


@dataclass
class Anomaly:
    """Represents a detected anomaly in the data."""
    ticker: str
    metric: str
    value: float
    unit: Optional[str]
    anomaly_type: str  # 'historical_deviation', 'qoq_change', 'peer_deviation'
    comparison_type: str  # 'historical', 'sector', 'peer'
    baseline: float
    percentage_diff: float
    description: str
    importance: str  # 'high', 'medium', 'low'
    explanation: Optional[str] = None


def detect_anomalies(data_model: Dict[str, Any], primary_ticker: str = "") -> List[Anomaly]:
    """
    Analyze current dashboard data for anomalies.
    
    Function: detect_anomalies
    Called from: FollowUpSuggestions generation, dashboard routes
    Invokes: Statistical analysis functions
    Why: Proactively surfaces non-obvious insights.
    
    Detection Methods:
    1. Historical deviation: > 2 std dev from trailing average
    2. Quarter-over-quarter change: > 20% change
    3. Peer comparison: > 15% deviation from peer average
    
    Args:
        data_model: The dashboard data model containing kpis, chart, table data
        primary_ticker: The main ticker being analyzed
        
    Returns:
        List of Anomaly objects sorted by importance
    """
    anomalies: List[Anomaly] = []
    
    if not data_model:
        return anomalies
    
    # Extract data sections
    kpis = data_model.get("kpis", {})
    chart_data = data_model.get("chart", {})
    table_data = data_model.get("table", {})
    ticker = primary_ticker or data_model.get("ticker", "")
    
    # 1. Analyze KPI values for historical deviations
    for metric_key, metric_value in kpis.items():
        if not isinstance(metric_value, (int, float)):
            continue
            
        # Check chart series for historical data to compare against
        series_data = chart_data.get("series", [])
        for series in series_data:
            if series.get("metric", "").lower() == metric_key.lower():
                historical_values = series.get("values", [])
                if len(historical_values) >= 4:
                    anomaly = _check_historical_deviation(
                        ticker, metric_key, metric_value, historical_values
                    )
                    if anomaly:
                        anomalies.append(anomaly)
    
    # 2. Analyze table rows for peer deviation
    table_rows = table_data.get("rows", [])
    if len(table_rows) > 1:
        peer_anomalies = _check_peer_deviations(ticker, table_rows)
        anomalies.extend(peer_anomalies)
    
    # 3. Check for QoQ changes in chart series
    for series in chart_data.get("series", []):
        qoq_anomaly = _check_qoq_change(ticker, series)
        if qoq_anomaly:
            anomalies.append(qoq_anomaly)
    
    # Sort by importance (high first)
    importance_order = {"high": 0, "medium": 1, "low": 2}
    anomalies.sort(key=lambda a: importance_order.get(a.importance, 2))
    
    return anomalies


def _check_historical_deviation(
    ticker: str, 
    metric: str, 
    current_value: float, 
    historical_values: List[float]
) -> Optional[Anomaly]:
    """
    Check if current value deviates significantly from historical average.
    Triggers if deviation > 2 standard deviations.
    """
    if len(historical_values) < 4:
        return None
    
    try:
        avg = statistics.mean(historical_values)
        std = statistics.stdev(historical_values)
        
        if std == 0:
            return None
            
        deviation = (current_value - avg) / std
        percentage_diff = ((current_value - avg) / avg) * 100 if avg != 0 else 0
        
        if abs(deviation) > 2:
            importance = "high" if abs(deviation) > 3 else "medium"
            direction = "highest" if current_value > avg else "lowest"
            
            return Anomaly(
                ticker=ticker,
                metric=metric,
                value=current_value,
                unit="%" if "margin" in metric.lower() or "percentage" in metric.lower() else None,
                anomaly_type="historical_deviation",
                comparison_type="historical",
                baseline=avg,
                percentage_diff=percentage_diff,
                description=f"{direction} in the dataset ({deviation:.1f} std dev from average)",
                importance=importance,
                explanation=f"Current value of {current_value:.1f} is {abs(percentage_diff):.1f}% {'above' if percentage_diff > 0 else 'below'} the historical average of {avg:.1f}"
            )
    except (statistics.StatisticsError, ZeroDivisionError):
        pass
    
    return None


def _check_peer_deviations(ticker: str, table_rows: List[Dict[str, Any]]) -> List[Anomaly]:
    """
    Check if any metric deviates significantly from peer average.
    Triggers if deviation > 15% from peer average.
    """
    anomalies = []
    
    if len(table_rows) < 2:
        return anomalies
    
    # Get all numeric columns
    numeric_columns = set()
    for row in table_rows:
        for key, value in row.items():
            if isinstance(value, (int, float)) and key.lower() not in ("year", "quarter", "period"):
                numeric_columns.add(key)
    
    # Check each column for deviations
    for column in numeric_columns:
        values = []
        ticker_value = None
        
        for row in table_rows:
            row_ticker = row.get("ticker", row.get("symbol", ""))
            col_value = row.get(column)
            
            if isinstance(col_value, (int, float)):
                values.append(col_value)
                if row_ticker.upper() == ticker.upper():
                    ticker_value = col_value
        
        if len(values) < 2 or ticker_value is None:
            continue
        
        peer_avg = statistics.mean(values)
        if peer_avg == 0:
            continue
            
        deviation_pct = ((ticker_value - peer_avg) / peer_avg) * 100
        
        if abs(deviation_pct) > 15:
            importance = "high" if abs(deviation_pct) > 25 else "medium"
            direction = "above" if deviation_pct > 0 else "below"
            
            unit = "%" if "margin" in column.lower() or "ratio" in column.lower() else None
            
            anomalies.append(Anomaly(
                ticker=ticker,
                metric=column,
                value=ticker_value,
                unit=unit,
                anomaly_type="peer_deviation",
                comparison_type="peer",
                baseline=peer_avg,
                percentage_diff=deviation_pct,
                description=f"{abs(deviation_pct):.1f}% {direction} peer average",
                importance=importance,
                explanation=f"{ticker}'s {column} of {ticker_value:.1f} is {abs(deviation_pct):.1f}% {direction} the peer average of {peer_avg:.1f}"
            ))
    
    return anomalies


def _check_qoq_change(ticker: str, series: Dict[str, Any]) -> Optional[Anomaly]:
    """
    Check for significant quarter-over-quarter changes.
    Triggers if change > 20% between consecutive periods.
    """
    values = series.get("values", [])
    metric = series.get("metric", series.get("name", "value"))
    
    if len(values) < 2:
        return None
    
    # Get the last two values
    current = values[-1]
    previous = values[-2]
    
    if not isinstance(current, (int, float)) or not isinstance(previous, (int, float)):
        return None
    
    if previous == 0:
        return None
    
    change_pct = ((current - previous) / abs(previous)) * 100
    
    if abs(change_pct) > 20:
        importance = "high" if abs(change_pct) > 30 else "medium"
        direction = "increased" if change_pct > 0 else "decreased"
        
        return Anomaly(
            ticker=ticker,
            metric=metric,
            value=current,
            unit=None,
            anomaly_type="qoq_change",
            comparison_type="historical",
            baseline=previous,
            percentage_diff=change_pct,
            description=f"{direction} {abs(change_pct):.1f}% from previous period",
            importance=importance,
            explanation=f"{metric} went from {previous:.1f} to {current:.1f}, a {abs(change_pct):.1f}% change"
        )
    
    return None


def anomaly_to_dict(anomaly: Anomaly) -> Dict[str, Any]:
    """Convert Anomaly dataclass to dictionary for JSON serialization."""
    return {
        "ticker": anomaly.ticker,
        "metric": anomaly.metric,
        "value": anomaly.value,
        "unit": anomaly.unit,
        "comparison": {
            "type": anomaly.comparison_type,
            "baseline": anomaly.baseline,
            "percentageDiff": anomaly.percentage_diff,
            "description": anomaly.description,
        },
        "importance": anomaly.importance,
        "explanation": anomaly.explanation,
    }


def anomalies_to_suggestions(anomalies: List[Anomaly]) -> List[Dict[str, Any]]:
    """
    Convert detected anomalies to follow-up suggestion format.
    
    Function: anomalies_to_suggestions
    Called from: Follow-up suggestion generation
    Invokes: anomaly_to_dict
    Why: Transforms anomalies into actionable follow-up queries.
    """
    suggestions = []
    
    for anomaly in anomalies[:3]:  # Limit to top 3 anomalies
        direction = "high" if anomaly.percentage_diff > 0 else "low"
        
        suggestions.append({
            "id": f"anomaly_{anomaly.ticker}_{anomaly.metric}".replace(" ", "_").lower(),
            "label": f"Why is {anomaly.metric} {direction}?",
            "query": f"Explain why {anomaly.ticker}'s {anomaly.metric} is {direction}",
            "icon": "💡",
            "category": "anomaly",
            "priority": anomaly.importance,
            "metadata": anomaly_to_dict(anomaly),
        })
    
    return suggestions
