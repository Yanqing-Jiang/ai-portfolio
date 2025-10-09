from __future__ import annotations

import pathlib
import sys
from datetime import datetime

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[3]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from analytics.validators import CohesiveResultValidationError, CohesiveResultValidator, sanitize_for_json


def test_sanitize_for_json_handles_slice_and_datetime() -> None:
    payload = {
        "slice": slice(0, 5, 1),
        "timestamp": datetime(2025, 10, 8, 18, 44, 0),
        "nested": {"values": {0: slice(1, 3)}},
    }
    sanitized = sanitize_for_json(payload)
    assert sanitized["slice"] == {"start": 0, "stop": 5, "step": 1}
    assert sanitized["timestamp"].startswith("2025-10-08T18:44:00")
    assert sanitized["nested"]["values"]["0"] == {"start": 1, "stop": 3, "step": None}


def test_validator_raises_when_required_fields_missing() -> None:
    validator = CohesiveResultValidator()
    incomplete = {"sql": {"text": "select 1"}}
    with pytest.raises(CohesiveResultValidationError):
        validator.ensure(incomplete)


def test_validator_passes_with_required_fields() -> None:
    validator = CohesiveResultValidator()
    payload = {
        "sql": {"text": "SELECT 1"},
        "chart_spec": {"title": "Demo"},
        "chart_spec_id": "chart-123",
        "stock_widget": {"symbols": ["AMD"]},
        "web_context": {"summary": "Sample"},
        "analysis": "TL;DR: Demo analysis.",
    }
    sanitized = validator.ensure(payload)
    assert sanitized["chart_spec_id"] == "chart-123"
    assert sanitized["stock_widget"]["symbols"] == ["AMD"]
