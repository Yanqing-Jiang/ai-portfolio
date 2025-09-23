"""
Intent Detection Shared Functions

Contains shared intent detection logic used by both analytics_memory and analytics_supervisor systems.
Extracts duplicate functions to eliminate code duplication.
"""

import re
import logging
from typing import Dict, Any, Optional, List

# Import from relative path - will be updated when integrated
from .normalization import normalize_timeframe, get_default_tickers, normalize_granularity

logger = logging.getLogger(__name__)


def heuristic_intent(query: str, configs: Dict[str, Any], resolve_alias_func=None) -> Dict[str, Any]:
    """
    Heuristic-based intent detection using pattern matching.

    Args:
        query: User query text
        configs: Configuration dictionary
        resolve_alias_func: Function to resolve company aliases to tickers

    Returns:
        Dict containing intent detection results
    """
    q = (query or "").lower()

    # Extract company from query using enhanced matching with alias resolution
    companies = get_default_tickers(configs)
    detected_company = None

    # First, try to extract any potential company reference from the query
    words = q.split()
    for word in words:
        # Try alias resolution first (handles names like "micron", "nvidia", etc.)
        if resolve_alias_func:
            resolved_ticker = resolve_alias_func(word, configs)
            if resolved_ticker:
                detected_company = resolved_ticker
                break

    # If alias resolution didn't work, try direct ticker matching
    if not detected_company:
        for ticker in companies:
            if ticker.lower() in q:
                detected_company = ticker
                break

    # Intent detection logic
    intent_key: Optional[str] = None
    if "market share" in q:
        # Prefer market_share_all when no specific company is detected
        if "all" in q or ("every" in q or "each" in q):
            intent_key = "market_share_all"
        elif detected_company:
            # Only use single if we have a specific company
            intent_key = "market_share_single"
        else:
            # No company specified - use market_share_single to trigger clarification
            intent_key = "market_share_single"
    elif "margin" in q:
        if "growth" in q and ("vs" in q or "average" in q or "compare" in q):
            # Handle "margin growth vs industry average"
            intent_key = "margin_growth_vs_peers"
        elif "peer" in q or "average" in q or "vs" in q:
            # margins_vs_peers requires company - only set if we have one
            if detected_company:
                intent_key = "margins_vs_peers"
            else:
                intent_key = None  # Trigger clarification
    elif "growth" in q or "growing" in q:
        # Check for vs industry average patterns
        if any(phrase in q for phrase in ["vs industry", "vs average", "compare industry", "industry average", "vs peers"]):
            intent_key = "revenue_growth_vs_avg"
        else:
            intent_key = "revenue_growth_analysis"
    elif "r&d" in q or "rnd" in q:
        # R&D intents require company - only set if we have one
        if detected_company:
            if "expense" in q:
                intent_key = "rnd_expense_vs_peers"
            else:
                intent_key = "rnd_intensity_vs_peers"
        else:
            intent_key = None  # Trigger clarification

    slots = {
        "tickers": get_default_tickers(configs),
        "granularity": normalize_granularity(query),
        "timeframe": normalize_timeframe(None, query, configs),
    }

    # Only add company to slots if one was detected
    if detected_company:
        slots["company"] = detected_company

    return {
        "intent_key": intent_key,
        "confidence": 0.4 if intent_key else 0.2,
        "slots_detected": slots,
        "assumptions": [],
        "clarifications_suggested": [],
        "possible_intents": [],
        "intent_reasoning": f"Heuristic detection based on keywords: {intent_key or 'none'}"
    }


def detect_company_from_query(query: str, configs: Dict[str, Any], resolve_alias_func=None) -> Optional[str]:
    """
    Detect company from query using multiple strategies.

    Args:
        query: User query text
        configs: Configuration dictionary
        resolve_alias_func: Function to resolve company aliases to tickers

    Returns:
        Detected ticker symbol or None
    """
    if not query:
        return None

    companies = get_default_tickers(configs)

    # Strategy 1: Alias resolution
    if resolve_alias_func:
        for token in re.findall(r"[A-Za-z0-9&\.']+", query):
            detected = resolve_alias_func(token, configs)
            if detected:
                return detected

    # Strategy 2: Direct ticker matching (case-insensitive)
    query_lower = query.lower()
    for ticker in companies:
        if ticker.lower() in query_lower:
            return ticker

    return None


def post_process_slots(slots: Dict[str, Any], query: str, configs: Dict[str, Any], resolve_alias_func=None) -> Dict[str, Any]:
    """
    Post-process slots to ensure consistency and completeness.

    Args:
        slots: Raw slots from LLM or heuristic detection
        query: Original query text
        configs: Configuration dictionary
        resolve_alias_func: Function to resolve company aliases

    Returns:
        Post-processed slots dictionary
    """
    processed_slots = slots.copy()

    # Company post-processing
    if not processed_slots.get("company"):
        detected_company = detect_company_from_query(query, configs, resolve_alias_func)
        if detected_company:
            processed_slots["company"] = detected_company
            logger.info("Post-processed company: %s", detected_company)

    # Timeframe normalization
    tf_raw = processed_slots.get("timeframe")
    if tf_raw and not isinstance(tf_raw, dict):
        logger.warning(f"Invalid timeframe format: {tf_raw} - attempting to normalize")

    tf = normalize_timeframe(tf_raw, query, configs)
    if tf:
        processed_slots["timeframe"] = tf

    # Granularity normalization
    current_granularity = processed_slots.get("granularity")
    processed_slots["granularity"] = normalize_granularity(query, current_granularity)

    return processed_slots


def cleanup_clarifications_after_company_detection(clarifications: List[Dict], detected_company: str) -> List[Dict]:
    """
    Remove company and comparison clarifications if company was detected.

    Args:
        clarifications: List of clarification suggestions
        detected_company: Detected company ticker

    Returns:
        Filtered list of clarifications
    """
    if not detected_company:
        return clarifications

    # Remove company and comparison clarifications since we have a specific company
    filtered = [
        c for c in clarifications
        if c.get('slot') not in ['company', 'comparison']
    ]

    logger.info("Post-processed clarifications after company detection: %d remaining", len(filtered))
    return filtered