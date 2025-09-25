from __future__ import annotations
from typing import Any, Dict, Optional

from analytics_shared.intent import (
    IntentModel,
    detect_intent_with_clarifications as _shared_detect_intent_with_clarifications,
    detect_intent_with_clarifications_async as _shared_detect_intent_with_clarifications_async,
    heuristic_intent as _shared_heuristic_intent,
)


def detect_intent(query: str, configs: Dict[str, Any]) -> IntentModel:
    """Legacy heuristic-only intent detection used in lightweight flows."""

    return _shared_heuristic_intent(query, configs)


def detect_intent_llm(query: str, configs: Dict[str, Any], session_id: Optional[str] = None) -> IntentModel:
    """Wrapper retained for backward compatibility - delegates to shared detector."""

    return _shared_detect_intent_with_clarifications(
        query,
        configs,
        session_id=session_id,
    )


def detect_intent_with_clarifications(query: str, configs: Dict[str, Any], session_id: Optional[str] = None) -> IntentModel:
    """Primary entry point for intent detection in analytics_memory."""

    return _shared_detect_intent_with_clarifications(
        query,
        configs,
        session_id=session_id,
    )


async def detect_intent_with_clarifications_async(
    query: str,
    configs: Dict[str, Any],
    session_id: Optional[str] = None,
) -> IntentModel:
    """Async version exposed for callers already running inside an event loop."""

    return await _shared_detect_intent_with_clarifications_async(
        query,
        configs,
        session_id=session_id,
    )
