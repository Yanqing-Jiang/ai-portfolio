# --- Analytics Function/Class Map ---
# Class: CohesiveResultValidationError
#   Role: Raised when a cohesive_result payload is incomplete.
#   Called from: analytics.flows.multi_agent, analytics.validators, tests.analytics.test_cohesive_result_validator
#   Collaborators: Internal helpers only
#   Why: Supports downstream analytics workflows that rely on CohesiveResultValidationError.
# Function: _encode_slice
#   Role: Handles encode slice logic for analytics.validators.cohesive_result.
#   Called from: Internal to analytics.validators.cohesive_result
#   Invokes: Internal helpers only
#   Why: Keeps analytics.validators.cohesive_result from duplicating encode slice behavior across flows.
# Function: sanitize_for_json
#   Role: Convert arbitrary objects into JSON-safe structures.
#   Called from: analytics.agent_orchestrator.agent_runtime, analytics.agent_orchestrator.event_bus, analytics.core.events, analytics.core.revision_snapshot, +13 more
#   Invokes: analytics.validators.cohesive_result._encode_slice, json.dumps, analytics.validators.cohesive_result.sanitize_for_json
#   Why: Supports downstream analytics workflows that rely on sanitize_for_json.
# Function: _value_missing
#   Role: Handles value missing logic for analytics.validators.cohesive_result.
#   Called from: Internal to analytics.validators.cohesive_result
#   Invokes: Internal helpers only
#   Why: Keeps analytics.validators.cohesive_result from duplicating value missing behavior across flows.
# Class: CohesiveResultValidator
#   Role: Handles CohesiveResultValidator logic for analytics.validators.cohesive_result.
#   Called from: analytics.flows.multi_agent, analytics.validators, tests.analytics.test_cohesive_result_validator
#   Collaborators: analytics.validators.cohesive_result.sanitize_for_json, analytics.validators.cohesive_result.CohesiveResultValidationError, analytics.validators.cohesive_result._value_missing
#   Why: Keeps analytics.validators.cohesive_result from duplicating CohesiveResultValidator behavior across flows.
# --- End Analytics Function/Class Map ---
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
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
    if isinstance(value, Decimal):
        # Preserve numeric structure for downstream chart specs and analytics payloads
        return float(value)
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
