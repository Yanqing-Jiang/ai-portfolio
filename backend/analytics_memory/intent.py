from __future__ import annotations
import os
import logging
import re
from typing import Dict, Any, Optional
from .openai_client import get_openai_client
from .types import IntentModel
from .sql_planner import resolve_alias_to_ticker

logger = logging.getLogger(__name__)

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
    if isinstance(tf_raw, dict):
        return tf_raw.copy()
    
    tf = {}
    text = (query_text or "").lower()
    
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

# Placeholder for intent detection node (structured output to be implemented in Phase 2/3)
def detect_intent(query: str, configs: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "intent_key": None,
        "confidence": 0.0,
        "slots_detected": {},
        "missing_slots": ["company"],
        "ask": [
            {
                "slot": "company",
                "question": "Which company do you want to analyze?",
                "type": "single",
                "options": configs.get("companies", {}).get("selection_rules", {}).get("default_companies", {}).get("tickers", []),
                "suggested_default": "NVDA"
            }
        ],
        "assumptions": []
    }


def _default_tickers(configs: Dict[str, Any]) -> list[str]:
    return (
        configs.get("companies", {})
        .get("selection_rules", {})
        .get("default_companies", {})
        .get("tickers", ["NVDA", "AMD", "INTC", "MU", "QCOM", "AVGO", "TXN"])
    )


def _heuristic_intent(query: str, configs: Dict[str, Any]) -> IntentModel:
    q = (query or "").lower()
    
    # Extract company from query using enhanced matching with alias resolution
    companies = _default_tickers(configs)
    detected_company = None
    
    # First, try to extract any potential company reference from the query
    words = q.split()
    for word in words:
        # Try alias resolution first (handles names like "micron", "nvidia", etc.)
        resolved_ticker = resolve_alias_to_ticker(word, configs)
        if resolved_ticker:
            detected_company = resolved_ticker
            break
    
    # If alias resolution didn't work, try direct ticker matching
    if not detected_company:
        for ticker in companies:
            if ticker.lower() in q:
                detected_company = ticker
                break
    
    # No NVDA default - leave as None if no company detected
    
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
            # This will cause the clarification system to ask for company selection
            intent_key = "market_share_single"
    elif "margin" in q:
        if "growth" in q and ("vs" in q or "average" in q or "compare" in q):
            # Handle "margin growth vs industry average"
            intent_key = "margin_growth_vs_peers"  # Use margin growth intent
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
        "tickers": _default_tickers(configs),
        "granularity": "annual",
        "timeframe": {"years_back": 4},
    }
    
    # Only add company to slots if one was detected
    if detected_company:
        slots["company"] = detected_company
    
    return IntentModel(intent_key=intent_key, confidence=0.4 if intent_key else 0.2, slots_detected=slots)


def detect_intent_llm(query: str, configs: Dict[str, Any], session_id: Optional[str] = None) -> IntentModel:
    """Detect intent using a reliable structured-output LLM with deterministic
    post-processing to ensure critical slots are populated when present in the
    query text.
    """
    client = get_openai_client()
    if not client:
        return _heuristic_intent(query, configs)

    intents_cfg = list((configs.get("queries", {}) or {}).get("query_patterns", {}).keys())
    companies = _default_tickers(configs)

    system_content = (
        "You classify analytics intents and extract slots. "
        "Return ONLY JSON conforming to IntentModel. "
        "Populate slots_detected with actual values from the query; omit a field if truly absent."
    )
    user_content = (
        f"Known intents: {intents_cfg}.\n"
        f"Companies (tickers/aliases): {companies}.\n"
        f"User query: {query}"
    )

    messages = [
        {"role": "system", "content": system_content},
        {"role": "user", "content": user_content}
    ]

    try:
        res = client.create_structured(
            response_model=IntentModel,
            messages=messages,
            session_id=session_id,
            reasoning_effort="medium"
        )

        # Ensure dict exists with robust type checking
        if isinstance(res.slots_detected, dict):
            res.slots_detected = res.slots_detected
        elif isinstance(res.slots_detected, (list, tuple)):
            try:
                res.slots_detected = dict(res.slots_detected) if res.slots_detected else {}
            except (ValueError, TypeError):
                logger.warning(f"Invalid slots_detected format: {res.slots_detected}")
                res.slots_detected = {}
        else:
            res.slots_detected = {}

        # Company: scan tokens for alias/ticker if missing
        if not res.slots_detected.get("company"):
            detected = None
            for token in re.findall(r"[A-Za-z0-9&\.']+", (query or "")):
                detected = resolve_alias_to_ticker(token, configs)
                if detected:
                    break
            # Also check assumptions text (case-insensitive)
            if not detected and getattr(res, "assumptions", None):
                low_assumptions = " ".join([a or "" for a in res.assumptions]).lower()
                for tk in companies:
                    if tk.lower() in low_assumptions:
                        detected = tk
                        break
            if detected:
                res.slots_detected["company"] = detected
                logger.info("Post-processed company: %s", detected)

        # Timeframe: normalize to consistent dict structure
        tf_raw = res.slots_detected.get("timeframe")
        if tf_raw and not isinstance(tf_raw, dict):
            logger.warning(f"Invalid timeframe format: {tf_raw} - attempting to normalize")
        
        tf = normalize_timeframe(tf_raw, query, configs)
        if tf:
            res.slots_detected["timeframe"] = tf

        # Granularity: infer if missing or invalid
        current_granularity = res.slots_detected.get("granularity")
        if not current_granularity or current_granularity not in ["annual", "quarterly"]:
            if any(k in (query or "").lower() for k in ["quarter", "qoq", "q1", "q2", "q3", "q4"]):
                res.slots_detected["granularity"] = "quarterly"
            else:
                res.slots_detected["granularity"] = "annual"

        logger.info(
            "LLM Intent Detection OK: intent=%s conf=%.2f company=%s timeframe=%s",
            res.intent_key,
            res.confidence,
            res.slots_detected.get("company"),
            res.slots_detected.get("timeframe"),
        )
        return res
    except Exception as e:
        logger.error("LLM Intent Detection FAILED: %s", str(e))
        return _heuristic_intent(query, configs)


def detect_intent_with_clarifications(query: str, configs: Dict[str, Any], session_id: Optional[str] = None) -> IntentModel:
    """Enhanced intent detection that suggests missing slots.
    
    Returns IntentModel with advisory clarification hints while maintaining
    all existing deterministic post-processing. LLM only identifies what's 
    missing - server decides how to ask.
    """
    client = get_openai_client()
    if not client:
        return _heuristic_intent(query, configs)

    intents_cfg = list((configs.get("queries", {}) or {}).get("query_patterns", {}).keys())
    companies = _default_tickers(configs)

    system_content = """You classify analytics intents and identify missing information.

Return JSON with:
- intent_key: most likely intent from the known intents
- confidence: 0-1 confidence score
- slots_detected: extracted values (company, timeframe, granularity)
- assumptions: reasoning steps
- clarifications_suggested: [{slot: 'company', reason: 'single-company analysis requires ticker'}] for missing slots
- possible_intents: [{'market_share_single': 0.8, 'market_share_all': 0.2}] alternative interpretations
- intent_reasoning: 1-2 sentence explanation of why this intent was chosen

Rules:
1. Only identify MISSING slots - do NOT generate options or questions
2. Company slot needed for: market_share_single, margins_vs_peers, rnd_*_vs_peers
3. Timeframe defaults to 5 years if not specified
4. Be conservative with clarifications_suggested - only when truly required

Known intent patterns and their slot requirements:
- market_share_single: requires company (if no company specified, suggest clarification)
- market_share_all: no company needed (use when "all" companies or no specific company mentioned)
- margins_vs_peers: requires company
- revenue_growth_analysis: company optional
- revenue_growth_vs_avg: company optional (handles margin growth vs industry average)
- rnd_intensity_vs_peers: requires company
- rnd_expense_vs_peers: requires company

Important: For "market share" queries, you MUST suggest a 'comparison' clarification to ask if they want single company analysis or all companies comparison, EVEN IF a company is mentioned. This helps users choose between analyzing that specific company's market share or comparing all companies including that one. Do not default to market_share_all or market_share_single without clarification.

Note: "margin growth vs industry average" queries should use margin_growth_vs_peers intent."""

    user_content = f"""Available intents: {intents_cfg}
Companies (tickers/aliases): {companies}
User query: {query}

Identify the intent and any missing required slots."""

    messages = [
        {"role": "system", "content": system_content},
        {"role": "user", "content": user_content}
    ]

    try:
        res = client.create_structured(
            response_model=IntentModel,
            messages=messages,
            session_id=session_id,
            reasoning_effort="medium"
        )

        # Ensure dict exists with robust type checking
        if isinstance(res.slots_detected, dict):
            res.slots_detected = res.slots_detected
        elif isinstance(res.slots_detected, (list, tuple)):
            try:
                res.slots_detected = dict(res.slots_detected) if res.slots_detected else {}
            except (ValueError, TypeError):
                logger.warning(f"Invalid slots_detected format: {res.slots_detected}")
                res.slots_detected = {}
        else:
            res.slots_detected = {}

        # Apply existing deterministic post-processing
        # Company: scan tokens for alias/ticker if missing
        if not res.slots_detected.get("company"):
            detected = None
            for token in re.findall(r"[A-Za-z0-9&\.']+", (query or "")):
                detected = resolve_alias_to_ticker(token, configs)
                if detected:
                    break
            # Also check assumptions text (case-insensitive)
            if not detected and getattr(res, "assumptions", None):
                low_assumptions = " ".join([a or "" for a in res.assumptions]).lower()
                for tk in companies:
                    if tk.lower() in low_assumptions:
                        detected = tk
                        break
            if detected:
                res.slots_detected["company"] = detected
                logger.info("Post-processed company: %s", detected)
                
                # Remove company from clarifications_suggested if we found it
                res.clarifications_suggested = [
                    c for c in res.clarifications_suggested 
                    if c.get('slot') != 'company'
                ]

        # Timeframe: normalize to consistent dict structure
        tf_raw = res.slots_detected.get("timeframe")
        if tf_raw and not isinstance(tf_raw, dict):
            logger.warning(f"Invalid timeframe format: {tf_raw} - attempting to normalize")
        
        tf = normalize_timeframe(tf_raw, query, configs)
        if tf:
            res.slots_detected["timeframe"] = tf

        # Granularity: infer if missing or invalid
        current_granularity = res.slots_detected.get("granularity")
        if not current_granularity or current_granularity not in ["annual", "quarterly"]:
            if any(k in (query or "").lower() for k in ["quarter", "qoq", "q1", "q2", "q3", "q4"]):
                res.slots_detected["granularity"] = "quarterly"
            else:
                res.slots_detected["granularity"] = "annual"

        logger.info(
            "Enhanced Intent Detection OK: intent=%s conf=%.2f company=%s timeframe=%s clarifications=%d",
            res.intent_key,
            res.confidence,
            res.slots_detected.get("company"),
            res.slots_detected.get("timeframe"),
            len(res.clarifications_suggested)
        )
        return res
    except Exception as e:
        logger.error("Enhanced Intent Detection FAILED: %s, falling back to heuristic", str(e))
        # Fallback to heuristic on any failure
        fallback_result = _heuristic_intent(query, configs)
        logger.info("Heuristic Fallback: company=%s, intent=%s", fallback_result.slots_detected.get("company"), fallback_result.intent_key)
        return fallback_result
