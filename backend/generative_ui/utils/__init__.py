# --- Generative UI Utils Function/Class Map ---
# Function: row_sort_key
#   Role: Build sortable keys for comp_financials rows.
#   Called from: backend.generative_ui.utils.sorted_rows, backend.generative_ui.agent_v2
#   Invokes: n/a
#   Why: Keeps time-series ordering consistent across data utilities.
# Function: sorted_rows
#   Role: Sort comp_financials rows descending by period.
#   Called from: backend.generative_ui.agent_v2
#   Invokes: backend.generative_ui.utils.row_sort_key
#   Why: Simplifies latest/previous metric calculations.
# Function: period_label
#   Role: Generate human-readable period labels (e.g., Q1 2024).
#   Called from: backend.generative_ui.agent_v2
#   Invokes: n/a
#   Why: Normalizes period strings for tables and charts.
# Function: coerce_float
#   Role: Convert numeric inputs to floats safely.
#   Called from: backend.generative_ui.utils.metric_series, backend.generative_ui.agent_v2
#   Invokes: n/a
#   Why: Prevents invalid numeric values from breaking calculations.
# Function: metric_series
#   Role: Build ordered series lists for a metric.
#   Called from: backend.generative_ui.agent_v2
#   Invokes: backend.generative_ui.utils.sorted_rows, backend.generative_ui.utils.coerce_float
#   Why: Feeds MetricChart and KPI computations.
# Function: latest_and_previous
#   Role: Extract latest and previous values from a series.
#   Called from: backend.generative_ui.agent_v2
#   Invokes: backend.generative_ui.utils.coerce_float
#   Why: Enables delta math for KPI widgets.
# Function: percentage_change
#   Role: Calculate percent change between two values.
#   Called from: backend.generative_ui.agent_v2
#   Invokes: n/a
#   Why: Standardizes delta calculations for KPIs and tables.
# Function: compute_correlation_matrix
#   Role: Produce correlation matrices for peer comparisons.
#   Called from: backend.generative_ui.agent_v2
#   Invokes: math.sqrt
#   Why: Supplies correlation visuals in peer dashboards.
# Function: date_to_period_label
#   Role: Convert date strings into period labels for annotations.
#   Called from: backend.generative_ui.agent_v2
#   Invokes: datetime parsing
#   Why: Aligns news events with chart periods.
# Function: parse_published_at
#   Role: Normalize news timestamps into readable strings.
#   Called from: backend.generative_ui.agent_v2
#   Invokes: datetime parsing
#   Why: Keeps citation dates consistent.
# Function: map_sentiment
#   Role: Normalize sentiment labels/scores.
#   Called from: backend.generative_ui.agent_v2
#   Invokes: n/a
#   Why: Drives consistent sentiment styling in news visuals.
# Function: map_news_event
#   Role: Convert news payloads into timeline events.
#   Called from: backend.generative_ui.agent_v2
#   Invokes: backend.generative_ui.utils.map_sentiment, backend.generative_ui.utils.parse_published_at
#   Why: Feeds NewsTimeline widgets.
# Constant: AVAILABLE_TICKERS
#   Role: Allowed ticker universe for A2UI queries.
#   Called from: backend.generative_ui.agent_v2, backend.generative_ui.clarification
#   Invokes: n/a
#   Why: Keeps model/tool queries constrained to known data.
# Function: normalize_tickers
#   Role: Filter and normalize ticker inputs to supported tickers.
#   Called from: backend.generative_ui.agent_v2
#   Invokes: n/a
#   Why: Ensures only supported tickers reach SQL tooling.
# --- End Generative UI Utils Function/Class Map ---
"""
Generative UI Utilities Package

Provides helper functions extracted from agent_v2 for cleaner separation.
"""

from .data_utils import (
    row_sort_key,
    sorted_rows,
    period_label,
    coerce_float,
    metric_series,
    latest_and_previous,
    percentage_change,
    compute_correlation_matrix,
    date_to_period_label,
)
from .news_utils import (
    parse_published_at,
    map_sentiment,
    map_news_event,
)
from .ticker_utils import (
    AVAILABLE_TICKERS,
    normalize_tickers,
)

__all__ = [
    # Data utils
    "row_sort_key",
    "sorted_rows",
    "period_label",
    "coerce_float",
    "metric_series",
    "latest_and_previous",
    "percentage_change",
    "compute_correlation_matrix",
    "date_to_period_label",
    # News utils
    "parse_published_at",
    "map_sentiment",
    "map_news_event",
    # Ticker utils
    "AVAILABLE_TICKERS",
    "normalize_tickers",
]
