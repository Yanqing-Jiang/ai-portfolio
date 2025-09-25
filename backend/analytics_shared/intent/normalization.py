"""
Intent Normalization Functions

Shared functions for normalizing and processing intent-related data across
analytics_memory and analytics_supervisor systems.
"""

import re
from typing import Dict, Any, Optional, List


def normalize_timeframe(tf_raw: Any, query_text: str = "", configs: Dict = None) -> Dict[str, Any]:
    """
    Normalize timeframe from various formats to a consistent dict structure.

    Args:
        tf_raw: Raw timeframe from LLM (could be dict, string, or None)
        query_text: Original query text for fallback parsing
        configs: Configuration dict for defaults

    Returns:
        Dict with normalized timeframe structure
    """
    text = (query_text or "").lower()

    if isinstance(tf_raw, dict):
        tf = tf_raw.copy()
    else:
        tf = {}

        # Handle string formats like "5 years", "past 5 years", etc.
        if isinstance(tf_raw, str):
            tf_str = tf_raw.lower()
            # Extract numbers from string formats
            years_match = re.search(r"(\d{1,2})\s*years?", tf_str)
            quarters_match = re.search(r"(\d{1,2})\s*quarters?", tf_str)

            if years_match:
                tf["years_back"] = int(years_match.group(1))
            elif quarters_match:
                tf["quarters_back"] = int(quarters_match.group(1))

    # Fallback: parse from original query text
    years_m = re.search(r"(past|last)\s+(\d{1,2})\s+years?", text)
    quarters_m = re.search(r"(past|last)\s+(\d{1,2})\s+quarters?", text)

    if years_m and not tf.get("years_back"):
        tf["years_back"] = int(years_m.group(2))
    if quarters_m and not tf.get("quarters_back"):
        tf["quarters_back"] = int(quarters_m.group(2))

    # Apply defaults and bounds
    if configs:
        dbq = (configs.get("database", {}) or {}).get("query_defaults", {})
        max_years = int(dbq.get("max_years_back", 10))
        default_years = int(dbq.get("default_years_back", 5))

        if not tf.get("years_back") and not tf.get("quarters_back"):
            tf["years_back"] = default_years

        if tf.get("years_back"):
            tf["years_back"] = min(max(tf["years_back"], 1), max_years)
        if tf.get("quarters_back"):
            tf["quarters_back"] = min(max(tf["quarters_back"], 1), max_years * 4)

    return tf


def get_default_tickers(configs: Dict[str, Any]) -> List[str]:
    """
    Get default ticker list from configuration.

    Args:
        configs: Configuration dictionary

    Returns:
        List of default ticker symbols
    """
    return (
        configs.get("companies", {})
        .get("selection_rules", {})
        .get("default_companies", {})
        .get("tickers", ["NVDA", "AMD", "INTC", "MU", "QCOM", "AVGO", "TXN"])
    )


def normalize_granularity(query: str, current_granularity: Optional[str] = None) -> str:
    """
    Normalize granularity from query or use provided value.

    Args:
        query: Original query text
        current_granularity: Current granularity value from slots

    Returns:
        Normalized granularity ("annual" or "quarterly")
    """
    if current_granularity and current_granularity in ["annual", "quarterly"]:
        return current_granularity

    if any(k in (query or "").lower() for k in ["quarter", "qoq", "q1", "q2", "q3", "q4"]):
        return "quarterly"
    else:
        return "annual"