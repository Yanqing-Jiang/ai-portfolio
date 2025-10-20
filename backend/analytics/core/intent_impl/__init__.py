"""
Intent Detection Shared Module

Contains shared intent detection, normalization, and schema models used by both
analytics_memory and analytics_supervisor systems.
"""

from .models import (
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
)
from .detection import (
    heuristic_intent,
    detect_company_from_query,
    post_process_slots,
    cleanup_clarifications_after_company_detection,
    classify_query,
    classify_query_async,
    detect_intent_with_clarifications,
    detect_intent_with_clarifications_async,
)
from .normalization import (
    normalize_timeframe,
    get_default_tickers,
    normalize_granularity,
    timeframe_implies_quarterly,
)

__all__ = [
    'TimeframeModel',
    'SlotsModel',
    'ClarificationSuggestionModel',
    'PossibleIntentModel',
    'IntentModel',
    'LLMClarificationSuggestionModel',
    'LLMIntentModel',
    'ClarifyRequestModel',
    'ClarifyAnswerModel',
    'OffTopicClassifierSchema',
    'SqlCriteriaModel',
    'intent_to_sql_criteria',
    'heuristic_intent',
    'detect_company_from_query',
    'post_process_slots',
    'cleanup_clarifications_after_company_detection',
    'classify_query',
    'classify_query_async',
    'detect_intent_with_clarifications',
    'detect_intent_with_clarifications_async',
    'normalize_timeframe',
    'get_default_tickers',
    'normalize_granularity',
    'timeframe_implies_quarterly',
]
