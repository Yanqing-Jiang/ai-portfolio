from __future__ import annotations
import os
import logging
import re
from typing import Dict, Any, Optional
from .openai_client import get_openai_client
from .types import IntentModel, LLMIntentModel, LLMClarificationSuggestionModel, ClarificationSuggestionModel
from analytics_shared.companies.resolver import resolve_alias_to_ticker
from analytics_shared.intent.normalization import normalize_timeframe as shared_normalize_timeframe, get_default_tickers

logger = logging.getLogger(__name__)

# Use shared normalize_timeframe function
normalize_timeframe = shared_normalize_timeframe

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


# Use shared get_default_tickers function
_default_tickers = get_default_tickers


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


def _llm_to_runtime_intent(llm_res: LLMIntentModel) -> IntentModel:
    """Convert strict LLM schema to runtime IntentModel with dict slots."""
    # Convert SlotsModel to plain dict for downstream compatibility
    slots: Dict[str, Any] = {}
    try:
        slots = llm_res.slots_detected.model_dump() if hasattr(llm_res.slots_detected, "model_dump") else dict(llm_res.slots_detected)
    except Exception:
        slots = {}

    # Map clarification suggestions
    clar_suggestions: list[ClarificationSuggestionModel] = []
    for c in getattr(llm_res, "clarifications_suggested", []) or []:
        try:
            clar_suggestions.append(
                ClarificationSuggestionModel(
                    slot=c.slot,
                    reason=c.reason,
                    question=c.question,
                    type=c.type,
                    options=c.options,
                    proposed=c.proposed,
                    proposed_confidence=c.proposed_confidence,
                )
            )
        except Exception:
            # Skip invalid suggestion entries gracefully
            continue

    return IntentModel(
        intent_key=llm_res.intent_key,
        confidence=llm_res.confidence,
        slots_detected=slots,
        assumptions=list(getattr(llm_res, "assumptions", []) or []),
        clarifications_suggested=clar_suggestions,
        possible_intents=list(getattr(llm_res, "possible_intents", []) or []),
        intent_reasoning=getattr(llm_res, "intent_reasoning", "") or "",
    )


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
        llm_res = client.create_structured(
            response_model=LLMIntentModel,
            messages=messages,
            session_id=session_id,
            reasoning_effort="medium"
        )

        # Convert to runtime model with dict slots
        res = _llm_to_runtime_intent(llm_res)

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

Important: For "market share" queries, only suggest a 'comparison' clarification if it's ambiguous whether they want single company analysis or all companies comparison. If a specific company is mentioned (e.g., "Nvidia market share"), default to market_share_single. Only ask for clarification when the query is genuinely ambiguous (e.g., "market share trends" without specifying a company).

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
        llm_res = client.create_structured(
            response_model=LLMIntentModel,
            messages=messages,
            session_id=session_id,
            reasoning_effort="medium"
        )

        # Convert to runtime model with dict slots
        res = _llm_to_runtime_intent(llm_res)

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
                # Also remove comparison clarifications since we have a specific company
                res.clarifications_suggested = [
                    c for c in res.clarifications_suggested
                    if c.get('slot') not in ['company', 'comparison']  # Remove both company and comparison clarifications
                ]
                logger.info("Post-processed clarifications after company detection: %d remaining", len(res.clarifications_suggested))

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

        # Debug: Log clarification details
        for i, clarification in enumerate(res.clarifications_suggested):
            logger.info(
                "Clarification %d: slot=%s, reason=%s",
                i,
                clarification.get('slot', 'unknown'),
                clarification.get('reason', 'no reason')
            )
        return res
    except Exception as e:
        logger.error("Enhanced Intent Detection FAILED: %s, falling back to heuristic", str(e))
        # Fallback to heuristic on any failure
        fallback_result = _heuristic_intent(query, configs)
        logger.info("Heuristic Fallback: company=%s, intent=%s", fallback_result.slots_detected.get("company"), fallback_result.intent_key)
        return fallback_result
