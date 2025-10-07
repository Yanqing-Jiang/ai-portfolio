from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Mapping, Optional


def _safe_float(value: Any) -> Optional[float]:
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _normalise_slots(slots: Any) -> Dict[str, Any]:
    if isinstance(slots, Mapping):
        return dict(slots)
    return {}


@dataclass
class ClassificationArtifact:
    """Prototype artifact produced by the classification phase."""

    category: Optional[str]
    confidence: Optional[float]
    is_financial: Optional[bool]
    model: Optional[str] = None
    raw: Dict[str, Any] = field(default_factory=dict)

    def as_payload(self) -> Dict[str, Any]:
        return {
            "category": self.category,
            "confidence": self.confidence,
            "is_financial": self.is_financial,
            "model": self.model,
            "raw": self.raw,
        }

    @classmethod
    def from_event(cls, event: Mapping[str, Any]) -> "ClassificationArtifact":
        data = dict(event.get("data", {})) if isinstance(event, Mapping) else {}
        return cls(
            category=data.get("category"),
            confidence=_safe_float(data.get("confidence")),
            is_financial=bool(data.get("is_financial")) if "is_financial" in data else None,
            model=data.get("model"),
            raw=data,
        )


@dataclass
class IntentArtifact:
    """Prototype artifact produced by the intent detection phase."""

    intent_key: Optional[str]
    confidence: Optional[float]
    slots: Dict[str, Any] = field(default_factory=dict)
    clarifications_needed: Optional[bool] = None
    low_confidence: Optional[bool] = None
    raw: Dict[str, Any] = field(default_factory=dict)

    def as_payload(self) -> Dict[str, Any]:
        return {
            "intent_key": self.intent_key,
            "confidence": self.confidence,
            "slots": self.slots,
            "clarifications_needed": self.clarifications_needed,
            "low_confidence": self.low_confidence,
            "raw": self.raw,
        }

    @classmethod
    def from_event(cls, event: Mapping[str, Any]) -> "IntentArtifact":
        data = dict(event.get("data", {})) if isinstance(event, Mapping) else {}
        slots = _normalise_slots(data.get("slots_detected"))
        return cls(
            intent_key=data.get("intent_key"),
            confidence=_safe_float(data.get("confidence")),
            slots=slots,
            clarifications_needed=data.get("clarifications_needed"),
            low_confidence=data.get("low_confidence"),
            raw=data,
        )


def classification_from_event(event: Mapping[str, Any]) -> ClassificationArtifact:
    return ClassificationArtifact.from_event(event)


def intent_from_event(event: Mapping[str, Any]) -> IntentArtifact:
    return IntentArtifact.from_event(event)

