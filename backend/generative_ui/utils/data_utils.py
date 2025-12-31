# --- Data Utils Function Map ---
# Function: row_sort_key
#   Role: Produce a sortable key for comp_financials rows.
#   Called from: sorted_rows, metric_series
#   Invokes: n/a
#   Why: Ensures time-series values are ordered consistently.
# Function: sorted_rows
#   Role: Sort comp_financials rows descending by period.
#   Called from: agent_v2.A2UIAgent._execute_* methods
#   Invokes: row_sort_key
#   Why: Simplifies latest value extraction.
# Function: period_label
#   Role: Build a readable period label from row metadata.
#   Called from: agent_v2.A2UIAgent._execute_* methods
#   Invokes: n/a
#   Why: Feeds DataTable period columns.
# Function: coerce_float
#   Role: Convert numeric inputs to float when possible.
#   Called from: metric_series
#   Invokes: n/a
#   Why: Normalizes SQL values for calculations.
# Function: metric_series
#   Role: Extract ordered metric values from SQL rows.
#   Called from: agent_v2.A2UIAgent._execute_* methods
#   Invokes: sorted_rows, coerce_float
#   Why: Provides consistent time-series inputs.
# Function: latest_and_previous
#   Role: Return latest + previous numeric values from a series.
#   Called from: agent_v2.A2UIAgent._execute_* methods
#   Invokes: coerce_float
#   Why: Enables delta calculations for KPIs.
# Function: percentage_change
#   Role: Compute percentage change between two values.
#   Called from: agent_v2.A2UIAgent._execute_* methods
#   Invokes: n/a
#   Why: Standardizes percent delta logic.
# Function: compute_correlation_matrix
#   Role: Generate a Pearson correlation matrix from series data.
#   Called from: agent_v2.A2UIAgent._execute_peer_compare
#   Invokes: math.sqrt
#   Why: Supplies correlation data for A2UI visualization.
# --- End Data Utils Function Map ---
"""
Data transformation utilities for comp_financials rows.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple


def row_sort_key(row: Mapping[str, Any]) -> Tuple[int, int]:
    """Produce a sortable key for comp_financials rows."""
    year = int(row.get("calendar_year") or 0)
    quarter = int(row.get("calendar_quarter_num") or 0)
    return (year, quarter)


def sorted_rows(rows: Sequence[Mapping[str, Any]]) -> List[Mapping[str, Any]]:
    """Sort comp_financials rows descending by period."""
    return sorted(rows, key=row_sort_key, reverse=True)


def period_label(row: Mapping[str, Any]) -> str:
    """Build a readable period label from row metadata."""
    year = row.get("calendar_year")
    quarter = row.get("calendar_quarter_num")
    if year and quarter:
        return f"Q{quarter} {year}"
    if year:
        return str(year)
    return "Unknown"


def coerce_float(value: Any) -> Optional[float]:
    """Convert numeric inputs to float when possible."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def metric_series(rows: Sequence[Mapping[str, Any]], metric: str) -> List[Dict[str, Any]]:
    """Extract ordered metric values from SQL rows."""
    filtered = [row for row in rows if str(row.get("metric", "")) == metric]
    series: List[Dict[str, Any]] = []
    for row in sorted_rows(filtered):
        value = coerce_float(row.get("value"))
        if value is None:
            continue
        series.append({"period": period_label(row), "value": value})
    return series


def latest_and_previous(series: Sequence[Mapping[str, Any]]) -> Tuple[Optional[float], Optional[float]]:
    """Return latest + previous numeric values from a series."""
    if not series:
        return None, None
    latest = coerce_float(series[0].get("value"))
    previous = coerce_float(series[1].get("value")) if len(series) > 1 else None
    return latest, previous


def percentage_change(current: Optional[float], previous: Optional[float]) -> Optional[float]:
    """Compute percentage change between two values."""
    if current is None or previous is None:
        return None
    if previous == 0:
        return None
    return (current - previous) / previous * 100


def compute_correlation_matrix(
    series_by_ticker: Mapping[str, Sequence[float]], tickers: Sequence[str]
) -> List[List[float]]:
    """Generate a Pearson correlation matrix from series data."""
    matrix: List[List[float]] = []
    for i, ticker_a in enumerate(tickers):
        row: List[float] = []
        series_a = list(series_by_ticker.get(ticker_a, []))
        for j, ticker_b in enumerate(tickers):
            if i == j:
                row.append(1.0)
                continue
            series_b = list(series_by_ticker.get(ticker_b, []))
            n = min(len(series_a), len(series_b))
            if n < 2:
                row.append(0.0)
                continue
            a = series_a[:n]
            b = series_b[:n]
            mean_a = sum(a) / n
            mean_b = sum(b) / n
            cov = sum((a[k] - mean_a) * (b[k] - mean_b) for k in range(n)) / n
            var_a = sum((a[k] - mean_a) ** 2 for k in range(n)) / n
            var_b = sum((b[k] - mean_b) ** 2 for k in range(n)) / n
            if var_a == 0 or var_b == 0:
                row.append(0.0)
                continue
            corr = cov / math.sqrt(var_a * var_b)
            row.append(round(corr, 3))
        matrix.append(row)
    return matrix


def date_to_period_label(date_str: str) -> str:
    """Map a date string (ISO or similar) to a QX YYYY period label."""
    try:
        from datetime import datetime
        # Simple ISO parse
        if 'T' in date_str:
            dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        else:
            dt = datetime.strptime(date_str[:10], "%Y-%m-%d")
        
        quarter = (dt.month - 1) // 3 + 1
        return f"Q{quarter} {dt.year}"
    except Exception:
        return "Unknown"


__all__ = [
    "row_sort_key",
    "sorted_rows",
    "period_label",
    "coerce_float",
    "metric_series",
    "latest_and_previous",
    "percentage_change",
    "compute_correlation_matrix",
    "date_to_period_label",
]
