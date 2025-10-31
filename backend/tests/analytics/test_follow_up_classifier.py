from __future__ import annotations

import pathlib
import sys
from typing import Optional

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[3]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from analytics.core.session_state import SessionStateSnapshot
from analytics.routing import FollowUpClassifier, FollowUpRoute


def _snapshot(sql: str = "", chart_spec: Optional[dict] = None) -> SessionStateSnapshot:
    snapshot = SessionStateSnapshot(session_id="unit-test")
    snapshot.last_sql = sql or None
    snapshot.last_chart_spec = chart_spec
    return snapshot


def test_classifier_defaults_to_full_pipeline_when_no_snapshot() -> None:
    classifier = FollowUpClassifier()
    route = classifier.classify("What did we learn?", None)
    assert route is FollowUpRoute.FULL_PIPELINE


def test_classifier_stock_only_when_price_question_and_sql_exists() -> None:
    classifier = FollowUpClassifier()
    snapshot = _snapshot(sql="SELECT 1")
    route = classifier.classify("How did AMD stock move last year?", snapshot)
    assert route is FollowUpRoute.STOCK_ONLY


def test_classifier_reuse_sql_for_chart_update() -> None:
    classifier = FollowUpClassifier()
    snapshot = _snapshot(sql="SELECT 1", chart_spec={"title": {"text": "foo"}})
    route = classifier.classify("Update the revenue chart", snapshot)
    assert route is FollowUpRoute.REUSE_SQL


def test_classifier_full_when_keywords_missing_or_no_sql() -> None:
    classifier = FollowUpClassifier()
    snapshot = _snapshot(sql="")
    route = classifier.classify("Show me stock chart", snapshot)
    assert route is FollowUpRoute.FULL_PIPELINE


def test_detect_revision_targets_pairs_analysis_with_web() -> None:
    classifier = FollowUpClassifier()
    snapshot = SessionStateSnapshot(session_id="analysis-unit")
    snapshot.last_analysis = "Cached narrative"
    analytics_cache = snapshot.tool_cache.setdefault("analytics", {})
    analytics_cache["artifacts"] = {"web": {"ready": True}}
    targets = classifier.detect_revision_targets("analysis: refresh the summary", snapshot)
    assert targets == {"analysis", "web"}
