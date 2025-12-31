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
    # News utils
    "parse_published_at",
    "map_sentiment",
    "map_news_event",
    # Ticker utils
    "AVAILABLE_TICKERS",
    "normalize_tickers",
]
