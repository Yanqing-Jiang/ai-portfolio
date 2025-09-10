from __future__ import annotations
import os
import logging
import re
from typing import Dict, Any, Optional
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from .types import IntentModel
from .sql_planner import resolve_alias_to_ticker

logger = logging.getLogger(__name__)

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
        intent_key = "market_share_single"
        if "all" in q:
            intent_key = "market_share_all"
    elif "margin" in q and ("peer" in q or "average" in q or "vs" in q):
        intent_key = "margins_vs_peers"
    elif "growth" in q:
        intent_key = "revenue_growth_analysis"
    elif "r&d" in q or "rnd" in q:
        if "expense" in q:
            intent_key = "rnd_expense_vs_peers"
        else:
            intent_key = "rnd_intensity_vs_peers"

    slots = {
        "tickers": _default_tickers(configs),
        "granularity": "annual",
        "timeframe": {"years_back": 4},
    }
    
    # Only add company to slots if one was detected
    if detected_company:
        slots["company"] = detected_company
    
    return IntentModel(intent_key=intent_key, confidence=0.4 if intent_key else 0.2, slots_detected=slots)


def detect_intent_llm(query: str, configs: Dict[str, Any]) -> IntentModel:
    """Detect intent using a reliable structured-output LLM with deterministic
    post-processing to ensure critical slots are populated when present in the
    query text.
    """
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return _heuristic_intent(query, configs)

    # Prefer 4o-mini for function-calling; allow override for experimentation
    model_name = os.getenv("OPENAI_INTENT_MODEL", "gpt-4o-mini-2024-07-18")
    llm = ChatOpenAI(model=model_name, temperature=0, api_key=api_key)

    intents_cfg = list((configs.get("queries", {}) or {}).get("query_patterns", {}).keys())
    companies = _default_tickers(configs)

    system = (
        "You classify analytics intents and extract slots. "
        "Return ONLY JSON conforming to IntentModel. "
        "Populate slots_detected with actual values from the query; omit a field if truly absent."
    )
    content = (
        f"Known intents: {intents_cfg}.\n"
        f"Companies (tickers/aliases): {companies}.\n"
        f"User query: {query}"
    )

    try:
        method = "json_schema" if model_name.startswith("gpt-5") else "function_calling"
        res = llm.with_structured_output(IntentModel, method=method).invoke([
            SystemMessage(content=system),
            HumanMessage(content=content),
        ])

        # Ensure dict exists
        res.slots_detected = dict(res.slots_detected or {})

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

        # Timeframe: parse years/quarters and clamp to bounds if needed
        tf = dict(res.slots_detected.get("timeframe") or {})
        text = (query or "").lower()
        years_m = re.search(r"(past|last)\s+(\d{1,2})\s+years?", text)
        quarters_m = re.search(r"(past|last)\s+(\d{1,2})\s+quarters?", text)
        if years_m and not tf.get("years_back"):
            tf["years_back"] = int(years_m.group(2))
        if quarters_m and not tf.get("quarters_back"):
            tf["quarters_back"] = int(quarters_m.group(2))

        dbq = (configs.get("database", {}) or {}).get("query_defaults", {})
        max_years = int(dbq.get("max_years_back", 10))
        default_years = int(dbq.get("default_years_back", 5))
        if tf.get("years_back") is not None:
            tf["years_back"] = max(1, min(int(tf["years_back"]), max_years))
        elif tf.get("quarters_back") is None:
            tf["years_back"] = default_years
        if tf:
            res.slots_detected["timeframe"] = tf

        # Granularity: infer if missing
        if not res.slots_detected.get("granularity"):
            if any(k in text for k in ["quarter", "qoq", "q1", "q2", "q3", "q4"]):
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


def detect_intent_with_clarifications(query: str, configs: Dict[str, Any]) -> IntentModel:
    """Enhanced intent detection that suggests missing slots.
    
    Returns IntentModel with advisory clarification hints while maintaining
    all existing deterministic post-processing. LLM only identifies what's 
    missing - server decides how to ask.
    """
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return _heuristic_intent(query, configs)

    # Prefer 4o-mini for function-calling; allow override for experimentation  
    model_name = os.getenv("OPENAI_INTENT_MODEL", "gpt-4o-mini-2024-07-18")
    llm = ChatOpenAI(model=model_name, temperature=0, api_key=api_key)

    intents_cfg = list((configs.get("queries", {}) or {}).get("query_patterns", {}).keys())
    companies = _default_tickers(configs)

    system = """You classify analytics intents and identify missing information.

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
- market_share_single: requires company
- market_share_all: no company needed
- margins_vs_peers: requires company
- revenue_growth_analysis: company optional
- rnd_intensity_vs_peers: requires company
- rnd_expense_vs_peers: requires company"""

    content = f"""Available intents: {intents_cfg}
Companies (tickers/aliases): {companies}
User query: {query}

Identify the intent and any missing required slots."""

    try:
        method = "json_schema" if model_name.startswith("gpt-5") else "function_calling"
        res = llm.with_structured_output(IntentModel, method=method).invoke([
            SystemMessage(content=system),
            HumanMessage(content=content),
        ])

        # Ensure dict exists
        res.slots_detected = dict(res.slots_detected or {})

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

        # Timeframe: parse years/quarters and clamp to bounds if needed
        tf = dict(res.slots_detected.get("timeframe") or {})
        text = (query or "").lower()
        years_m = re.search(r"(past|last)\s+(\d{1,2})\s+years?", text)
        quarters_m = re.search(r"(past|last)\s+(\d{1,2})\s+quarters?", text)
        if years_m and not tf.get("years_back"):
            tf["years_back"] = int(years_m.group(2))
        if quarters_m and not tf.get("quarters_back"):
            tf["quarters_back"] = int(quarters_m.group(2))

        dbq = (configs.get("database", {}) or {}).get("query_defaults", {})
        max_years = int(dbq.get("max_years_back", 10))
        default_years = int(dbq.get("default_years_back", 5))
        if tf.get("years_back") is not None:
            tf["years_back"] = max(1, min(int(tf["years_back"]), max_years))
        elif tf.get("quarters_back") is None:
            tf["years_back"] = default_years
        if tf:
            res.slots_detected["timeframe"] = tf

        # Granularity: infer if missing
        if not res.slots_detected.get("granularity"):
            if any(k in text for k in ["quarter", "qoq", "q1", "q2", "q3", "q4"]):
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
