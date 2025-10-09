from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Iterable, Mapping, MutableMapping, Optional, Sequence, Tuple


class CohesiveResultValidationError(ValueError):
    """Raised when a cohesive_result payload is incomplete."""


def _encode_slice(value: slice) -> Mapping[str, Any]:
    return {
        "start": value.start,
        "stop": value.stop,
        "step": value.step,
    }


def sanitize_for_json(value: Any) -> Any:
    """Convert arbitrary objects into JSON-safe structures."""
    if isinstance(value, Mapping):
        sanitized: MutableMapping[str, Any] = {}
        for key, item in value.items():
            sanitized[str(key)] = sanitize_for_json(item)
        return sanitized
    if isinstance(value, (list, tuple, set)):
        return [sanitize_for_json(item) for item in value]
    if isinstance(value, slice):
        return _encode_slice(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if hasattr(value, "model_dump"):
        try:
            return sanitize_for_json(value.model_dump())
        except Exception:
            return str(value)
    if hasattr(value, "dict"):
        try:
            return sanitize_for_json(value.dict())
        except Exception:
            return str(value)
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    try:
        json.dumps(value)
        return value
    except TypeError:
        return str(value)


def _value_missing(payload: Mapping[str, Any], key: str) -> bool:
    if key not in payload:
        return True
    value = payload.get(key)
    if value is None:
        return True
    if isinstance(value, (str, Sequence)) and not value:
        return True
    if isinstance(value, Mapping) and not value:
        return True
    return False


@dataclass
class CohesiveResultValidator:
    required_keys: Tuple[str, ...] = (
        "sql",
        "chart_spec",
        "chart_spec_id",
        "stock_widget",
        "web_context",
    )
    optional_keys: Tuple[str, ...] = ("analysis", "data_sample")
    sanitize: bool = True
    raise_on_missing: bool = True

    def validate(self, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        sanitized = sanitize_for_json(payload) if self.sanitize else payload
        missing = tuple(key for key in self.required_keys if _value_missing(sanitized, key))
        if missing and self.raise_on_missing:
            raise CohesiveResultValidationError(
                f"cohesive_result missing required fields: {', '.join(missing)}"
            )
        return sanitized

    def ensure(self, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        """Validate and always return a sanitized payload."""
        sanitized = sanitize_for_json(payload) if self.sanitize else payload
        missing = tuple(key for key in self.required_keys if _value_missing(sanitized, key))
        if missing:
            raise CohesiveResultValidationError(
                f"cohesive_result missing required fields: {', '.join(missing)}"
            )
        return sanitized
