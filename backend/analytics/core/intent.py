from __future__ import annotations

from typing import Any, Dict, Optional

from .intent_impl import (
    TimeframeModel,
    SlotsModel,
    ClarificationSuggestionModel,
    PossibleIntentModel,
    IntentModel,
    SqlCriteriaModel,
    LLMClarificationSuggestionModel,
    LLMIntentModel,
    ClarifyRequestModel,
    ClarifyAnswerModel,
    OffTopicClassifierSchema,
    intent_to_sql_criteria,
    heuristic_intent,
    detect_company_from_query,
    post_process_slots,
    cleanup_clarifications_after_company_detection,
    classify_query,
    classify_query_async,
    detect_intent_with_clarifications as _detect_intent_with_clarifications_impl,
    detect_intent_with_clarifications_async as _detect_intent_with_clarifications_async_impl,
    normalize_timeframe,
    get_default_tickers,
    normalize_granularity,
)

__all__ = [
    "TimeframeModel",
    "SlotsModel",
    "ClarificationSuggestionModel",
    "PossibleIntentModel",
    "IntentModel",
    "SqlCriteriaModel",
    "LLMClarificationSuggestionModel",
    "LLMIntentModel",
    "ClarifyRequestModel",
    "ClarifyAnswerModel",
    "OffTopicClassifierSchema",
    "intent_to_sql_criteria",
    "heuristic_intent",
    "detect_company_from_query",
    "post_process_slots",
    "cleanup_clarifications_after_company_detection",
    "classify_query",
    "classify_query_async",
    "detect_intent",
    "detect_intent_llm",
    "detect_intent_with_clarifications",
    "detect_intent_with_clarifications_async",
    "normalize_timeframe",
    "get_default_tickers",
    "normalize_granularity",
]


def detect_intent(query: str, configs: Dict[str, Any]) -> IntentModel:
    """Lightweight heuristic intent detection used in streamlined flows."""

    return heuristic_intent(query, configs)


def detect_intent_llm(
    query: str,
    configs: Dict[str, Any],
    session_id: Optional[str] = None,
    *,
    model: str = "gpt-5-nano-2025-08-07",
    reasoning_effort: str = "low",
) -> IntentModel:
    """Backwards-compatible sync helper for LLM-powered intent detection."""

    return _detect_intent_with_clarifications_impl(
        query,
        configs,
        session_id=session_id,
        model=model,
        reasoning_effort=reasoning_effort,
    )


def detect_intent_with_clarifications(
    query: str,
    configs: Dict[str, Any],
    session_id: Optional[str] = None,
    *,
    model: str = "gpt-5-nano-2025-08-07",
    reasoning_effort: str = "low",
) -> IntentModel:
    """Primary entry point for the analytics flows (sync)."""

    return _detect_intent_with_clarifications_impl(
        query,
        configs,
        session_id=session_id,
        model=model,
        reasoning_effort=reasoning_effort,
    )


async def detect_intent_with_clarifications_async(
    query: str,
    configs: Dict[str, Any],
    session_id: Optional[str] = None,
    *,
    model: str = "gpt-5-nano-2025-08-07",
    reasoning_effort: str = "low",
) -> IntentModel:
    """Async variant retained for event-loop callers."""

    return await _detect_intent_with_clarifications_async_impl(
        query,
        configs,
        session_id=session_id,
        model=model,
        reasoning_effort=reasoning_effort,
    )
