"""
Intent Detection Shared Functions

Provides shared intent detection, classification, and slot post-processing for
analytics workflows. Centralises logic so analytics_memory and
analytics_supervisor share a single implementation.
"""

from __future__ import annotations

import asyncio
import logging
import re
from typing import Any, Dict, List, Optional

from unified_responses_client import get_unified_client

from .models import (
    ClarificationSuggestionModel,
    ClarifyRequestModel,
    IntentModel,
    LLMIntentModel,
    OffTopicClassifierSchema,
)
from .normalization import (
    get_default_tickers,
    normalize_granularity,
    normalize_timeframe,
)
from ..companies import resolve_alias_to_ticker

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Heuristic Fallbacks
# ---------------------------------------------------------------------------

REQUIRES_COMPANY_SLOTS = {
    "market_share_single",
    "margins_vs_peers",
    "margin_growth_vs_peers",
    "rnd_intensity_vs_peers",
    "rnd_expense_vs_peers",
}

HEURISTIC_CONFIDENCE_THRESHOLD = 0.70  # Minimum confidence to short-circuit LLM intent lookup

RANKING_PRONOUNS = {"who", "which", "what"}
RANKING_KEYWORDS = {
    "lead",
    "leads",
    "leading",
    "leader",
    "leaders",
    "top",
    "highest",
    "best",
    "rank",
    "ranking",
    "ranks",
    "dominates",
    "dominant",
    "biggest",
}


def _is_ranking_query(query: str) -> bool:
    if not query:
        return False
    lowered = query.lower()
    pronoun_hit = any(token in lowered for token in RANKING_PRONOUNS)
    keyword_hit = any(token in lowered for token in RANKING_KEYWORDS)
    if pronoun_hit and keyword_hit:
        return True
    # Fallback: look for explicit "top N" phrases or "leaderboard"
    if keyword_hit and ("top " in lowered or "leaderboard" in lowered):
        return True
    return False


def _build_company_clarification(companies: List[str]) -> ClarificationSuggestionModel:
    return ClarificationSuggestionModel(
        slot="company",
        reason="This analysis requires a specific company to proceed.",
        question="Which company should we analyse?",
        type="single",
        options=list(companies)[:6],
        proposed=None,
        proposed_confidence=0.0,
    )


def heuristic_intent(query: str, configs: Dict[str, Any]) -> IntentModel:
    """Simple keyword-based intent detection used as a lightweight fallback."""

    q = (query or "").lower()
    companies = get_default_tickers(configs)
    detected_company = detect_company_from_query(query, configs, resolve_alias_to_ticker)

    intent_key: Optional[str] = None
    reasoning: List[str] = []

    if "market share" in q:
        if "all" in q or any(word in q for word in ("every", "each")):
            intent_key = "market_share_all"
            reasoning.append("Detected market share intent for all companies")
        else:
            intent_key = "market_share_single"
            reasoning.append("Detected single-company market share intent")
    elif "profit" in q or "earnings" in q:
        intent_key = "margins_vs_peers"
        reasoning.append("Detected profit analysis intent")
    elif "margin" in q:
        if "growth" in q and any(token in q for token in ("vs", "average", "compare")):
            intent_key = "margin_growth_vs_peers"
            reasoning.append("Detected margin growth vs peers intent")
        else:
            intent_key = "margins_vs_peers"
            reasoning.append("Detected margin comparison intent")
    elif "growth" in q or "growing" in q:
        if any(phrase in q for phrase in ("vs industry", "vs average", "industry average", "vs peers")):
            intent_key = "revenue_growth_vs_avg"
            reasoning.append("Detected revenue growth vs average intent")
        else:
            intent_key = "revenue_growth_analysis"
            reasoning.append("Detected revenue growth intent")
    elif any(token in q for token in ("r&d", "rnd", "research and development")):
        if any(word in q for word in ("highest", "top", "leading", "leader", "largest", "biggest", "most", "rank", "dominant")):
            intent_key = "rnd_top_spender"
            reasoning.append("Detected top R&D spender intent")
        elif "expense" in q or "spending" in q:
            intent_key = "rnd_expense_vs_peers"
            reasoning.append("Detected R&D expense vs peers intent")
        else:
            intent_key = "rnd_intensity_vs_peers"
            reasoning.append("Detected R&D intensity vs peers intent")

    slots: Dict[str, Any] = {
        "tickers": companies,
        "granularity": normalize_granularity(query),
        "timeframe": normalize_timeframe(None, query, configs),
    }
    if detected_company:
        slots["company"] = detected_company
    elif intent_key in REQUIRES_COMPANY_SLOTS:
        reasoning.append("Company not detected in query")

    clarifications: List[ClarificationSuggestionModel] = []
    if intent_key in REQUIRES_COMPANY_SLOTS and not detected_company:
        clarifications.append(_build_company_clarification(companies))

    if _is_ranking_query(query):
        slots["comparison"] = "all"
        slots["statistic"] = "ranking_latest"
        reasoning.append("Detected ranking-style request; defaulting to peer comparison")
        if not slots.get("metrics"):
            slots["metrics"] = []

    confidence = 0.75 if intent_key else 0.2
    return IntentModel(
        intent_key=intent_key,
        confidence=confidence,
        slots_detected=slots,
        assumptions=[],
        clarifications_suggested=clarifications,
        possible_intents=[],
        intent_reasoning="; ".join(reasoning) or "Heuristic detection could not determine a clear intent",
    )


# ---------------------------------------------------------------------------
# Slot Utilities
# ---------------------------------------------------------------------------

def detect_company_from_query(
    query: str,
    configs: Dict[str, Any],
    resolve_alias_func=resolve_alias_to_ticker,
) -> Optional[str]:
    """Detect a company from free-form text using alias and ticker matching."""

    if not query:
        return None

    companies = get_default_tickers(configs)

    if resolve_alias_func:
        for token in re.findall(r"[A-Za-z0-9&\\.']+", query):
            detected = resolve_alias_func(token, configs)
            if detected:
                return detected

    query_lower = query.lower()
    for ticker in companies:
        if ticker.lower() in query_lower:
            return ticker

    return None



def _normalize_company_candidates(values: Any, query: str) -> List[str]:
    """Return upper-cased company symbols ordered by their appearance in the query."""
    if values is None:
        return []
    if isinstance(values, str):
        candidates = [values]
    elif isinstance(values, (list, tuple, set)):
        candidates = list(values)
    else:
        return []
    deduped: List[str] = []
    for item in candidates:
        symbol = str(item).strip().upper()
        if symbol and symbol not in deduped:
            deduped.append(symbol)
    if not query:
        return deduped
    query_lower = query.lower()
    ranked = []
    for idx, symbol in enumerate(deduped):
        position = query_lower.find(symbol.lower())
        if position == -1:
            position = len(query_lower) + idx
        ranked.append((position, idx, symbol))
    ranked.sort(key=lambda item: (item[0], item[1]))
    return [symbol for _, _, symbol in ranked]

def post_process_slots(
    slots: Dict[str, Any],
    query: str,
    configs: Dict[str, Any],
    resolve_alias_func=resolve_alias_to_ticker,
) -> Dict[str, Any]:
    """Normalise detected slots using shared heuristics."""

    processed_slots = dict(slots or {})

    company_candidates = _normalize_company_candidates(processed_slots.get("company"), query)
    if not company_candidates and processed_slots.get("tickers"):
        company_candidates = _normalize_company_candidates(processed_slots.get("tickers"), query)

    if company_candidates:
        processed_slots["company_candidates"] = company_candidates
        processed_slots["company"] = company_candidates[0]
        processed_slots["tickers"] = company_candidates
    else:
        existing_company = processed_slots.get("company")
        if isinstance(existing_company, str) and existing_company.strip():
            normalized = existing_company.strip().upper()
            processed_slots["company"] = normalized
            processed_slots.setdefault("tickers", [normalized])
            processed_slots.setdefault("company_candidates", [normalized])
        else:
            processed_slots.pop("company", None)

    if not processed_slots.get("company"):
        detected_company = detect_company_from_query(query, configs, resolve_alias_func)
        if detected_company:
            processed_slots["company"] = detected_company
            processed_slots["tickers"] = [detected_company]
            processed_slots.setdefault("company_candidates", [detected_company])
            logger.info("Post-processed company: %s", detected_company)


    timeframe = normalize_timeframe(processed_slots.get("timeframe"), query, configs)
    if timeframe:
        processed_slots["timeframe"] = timeframe

    processed_slots["granularity"] = normalize_granularity(query, processed_slots.get("granularity"))
    return processed_slots


def cleanup_clarifications_after_company_detection(
    clarifications: List[Dict[str, Any]],
    detected_company: Optional[str],
) -> List[Dict[str, Any]]:
    """Drop redundant clarifications once a company has been inferred."""

    if not detected_company:
        return clarifications

    filtered = [
        c for c in clarifications
        if c.get("slot") not in {"company", "comparison"}
    ]
    logger.info(
        "Post-processed clarifications after company detection: %d remaining",
        len(filtered),
    )
    return filtered


# ---------------------------------------------------------------------------
# LLM-backed Classification / Intent Detection
# ---------------------------------------------------------------------------

def _llm_to_runtime_intent(llm_res: LLMIntentModel) -> IntentModel:
    slots_dict: Dict[str, Any] = {}
    try:
        slots_dict = llm_res.slots_detected.model_dump()
    except Exception:  # pragma: no cover - defensive
        slots_dict = {}

    clarifications = []
    for suggestion in getattr(llm_res, "clarifications_suggested", []) or []:
        try:
            clarifications.append(
                ClarificationSuggestionModel(
                    slot=suggestion.slot,
                    reason=suggestion.reason,
                    question=suggestion.question,
                    type=suggestion.type,
                    options=suggestion.options,
                    proposed=suggestion.proposed,
                    proposed_confidence=suggestion.proposed_confidence,
                )
            )
        except Exception:  # pragma: no cover - defensive
            continue

    return IntentModel(
        intent_key=llm_res.intent_key,
        confidence=llm_res.confidence,
        slots_detected=slots_dict,
        assumptions=list(getattr(llm_res, "assumptions", []) or []),
        clarifications_suggested=clarifications,
        possible_intents=list(getattr(llm_res, "possible_intents", []) or []),
        intent_reasoning=getattr(llm_res, "intent_reasoning", "") or "",
    )


async def classify_query_async(
    query: str,
    *,
    session_id: Optional[str] = None,
    model: str = "gpt-5-mini-2025-08-07",
    reasoning_effort: str = "low",
) -> OffTopicClassifierSchema:
    """Async helper used by agents that already run inside an event loop."""

    client = get_unified_client()
    messages = [
        {
            "role": "system",
            "content": (
                "You classify user queries to decide if they request financial analytics support.\n"
                "Return JSON following the OffTopicClassifierSchema.\n"
                "- If the user is off-topic, supply a polite_decline_message under 30 words that redirects them to financial analysis.\n"
                "- When possible, include a suggested_rephrase that turns the query into a valid financial analytics request.\n"
                "- Respect prior context when judging follow-up questions."
            ),
        },
        {"role": "user", "content": f"Classify this query: '{query}'"},
    ]

    result, _ = await client.create_structured(
        response_model=OffTopicClassifierSchema,
        messages=messages,
        model=model,
        reasoning_effort=reasoning_effort,
        session_id=session_id,
    )
    return result


def classify_query(
    query: str,
    *,
    session_id: Optional[str] = None,
    model: str = "gpt-5-mini-2025-08-07",
    reasoning_effort: str = "low",
) -> OffTopicClassifierSchema:
    """Synchronous wrapper for classification."""

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(classify_query_async(
            query,
            session_id=session_id,
            model=model,
            reasoning_effort=reasoning_effort,
        ))
    else:
        return loop.run_until_complete(classify_query_async(
            query,
            session_id=session_id,
            model=model,
            reasoning_effort=reasoning_effort,
        ))


async def detect_intent_fast_async(
    query: str,
    configs: Dict[str, Any],
    *,
    session_id: Optional[str] = None,
    model: str = "gpt-5-mini-2025-08-07",
    reasoning_effort: str = "low",
) -> IntentModel:
    """Fast path: heuristic-first, at most one LLM call, low effort by default."""

    heuristic = heuristic_intent(query, configs)
    if heuristic.intent_key and heuristic.confidence >= HEURISTIC_CONFIDENCE_THRESHOLD:
        logger.info("Heuristic intent satisfied for query '%s'", query)
        return heuristic

    try:
        client = get_unified_client()
    except ValueError:
        logger.warning("OpenAI client unavailable - using heuristic intent detection")
        return heuristic

    intents_cfg = list((configs.get("queries", {}) or {}).get("query_patterns", {}).keys())
    companies = get_default_tickers(configs)

    system_content = (
        "You are an analytics intent classifier. Return JSON that matches the IntentModel schema.\n"
        "- Pick the closest supported intent; never reply with unknown.\n"
        "- Fill slots_detected with concrete values from the query text.\n"
        "- Only include clarifications_suggested when a required slot is truly missing.\n"
        "- If a company-specific intent lacks a company, add ONE clarification with slot 'company'.\n"
        "- Keep clarification questions short and decisive.\n"
        "- Do not ask for optional context (e.g. timeframe) unless it is explicitly required and missing.\n"
        "- When the user asks who/which/what along with ranking cues (top, lead/leader, highest, best, rank, dominant), set slots_detected.comparison=\"all\", slots_detected.statistic=\"ranking_latest\", and include the default ticker list unless the user specifies a narrower one.\n"
        "Return JSON only."
    )

    user_content = (
        f"Available intents: {intents_cfg}\n"
        f"Companies (tickers/aliases): {companies}\n"
        f"User query: {query}\n\n"
        "Identify the intent and any missing required slots."
    )

    messages = [
        {"role": "system", "content": system_content},
        {"role": "user", "content": user_content},
    ]

    try:
        llm_res, _ = await client.create_structured(
            response_model=LLMIntentModel,
            messages=messages,
            model=model,
            reasoning_effort=reasoning_effort,
            session_id=session_id,
        )
    except Exception as exc:
        logger.error("LLM intent detection failed - falling back to heuristic: %s", exc)
        return heuristic

    intent = _llm_to_runtime_intent(llm_res)

    original_company = intent.slots_detected.get("company")
    intent.slots_detected = post_process_slots(intent.slots_detected, query, configs)

    if not original_company and intent.slots_detected.get("company"):
        intent.clarifications_suggested = cleanup_clarifications_after_company_detection(
            [c.model_dump() for c in intent.clarifications_suggested],
            intent.slots_detected["company"],
        )
        intent.clarifications_suggested = [
            ClarificationSuggestionModel(**c) if not isinstance(c, ClarificationSuggestionModel) else c
            for c in intent.clarifications_suggested
        ]

    logger.info(
        "Intent detection succeeded: intent=%s confidence=%.2f company=%s clarifications=%d",
        intent.intent_key,
        intent.confidence,
        intent.slots_detected.get("company"),
        len(intent.clarifications_suggested),
    )
    return intent




def detect_intent_with_clarifications(
    query: str,
    configs: Dict[str, Any],
    *,
    session_id: Optional[str] = None,
    model: str = "gpt-5-mini-2025-08-07",
    reasoning_effort: str = "low",
) -> IntentModel:
    """Synchronous helper maintained for legacy pipelines."""

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(
            detect_intent_fast_async(
                query,
                configs,
                session_id=session_id,
                model=model,
                reasoning_effort=reasoning_effort,
            )
        )
    else:
        return loop.run_until_complete(
            detect_intent_fast_async(
                query,
                configs,
                session_id=session_id,
                model=model,
                reasoning_effort=reasoning_effort,
            )
        )


# Backwards-compatible alias
detect_intent_with_clarifications_async = detect_intent_fast_async

