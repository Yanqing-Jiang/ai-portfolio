# --- Ticker Utils Function Map ---
# Constant: AVAILABLE_TICKERS
#   Role: Define the allowed ticker universe for A2UI queries.
#   Called from: agent_v2.A2UIAgent.select_skill, normalize_tickers
#   Invokes: n/a
#   Why: Keeps tool queries within supported tickers.
# Function: normalize_tickers
#   Role: Filter and normalize tickers to the allowed universe.
#   Called from: agent_v2.A2UIAgent._validate_selection, agent_v2.A2UIAgent.selection_from_plan
#   Invokes: n/a
#   Why: Ensures only valid tickers are passed to tools.
# --- End Ticker Utils Function Map ---
"""
Ticker normalization and universe definitions.
"""

from __future__ import annotations

from typing import Iterable, List


AVAILABLE_TICKERS = ["AMD", "AVGO", "INTC", "MU", "NVDA", "QCOM", "TXN"]


def normalize_tickers(tickers: Iterable[str]) -> List[str]:
    """Filter and normalize tickers to the allowed universe."""
    normalized = []
    for ticker in tickers:
        if not ticker:
            continue
        candidate = str(ticker).upper().strip()
        if candidate and candidate in AVAILABLE_TICKERS and candidate not in normalized:
            normalized.append(candidate)
    return normalized


__all__ = [
    "AVAILABLE_TICKERS",
    "normalize_tickers",
]
