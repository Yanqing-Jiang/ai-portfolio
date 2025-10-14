import sys
import types

if 'unified_responses_client' not in sys.modules:
    stub_module = types.ModuleType('unified_responses_client')
    stub_module.get_unified_client = lambda: None
    sys.modules['unified_responses_client'] = stub_module

from typing import Any, Dict, Optional
from backend.analytics.semantic.catalog import get_semantic_catalog
from backend.analytics.sql.sql_planner import plan_sql_rule_based
from backend.analytics.core.state import IntentModel


def _make_intent(intent_key: str, slots: Optional[Dict[str, Any]] = None, confidence: float = 0.9) -> IntentModel:
    return IntentModel(intent_key=intent_key, confidence=confidence, slots_detected=slots or {})


def test_intent_spec_market_share_all_has_semantic_defaults():
    catalog = get_semantic_catalog()
    spec = catalog.get_intent_spec("market_share_all")
    assert spec is not None
    assert spec.metrics == ["revenue"]
    assert spec.derived_metrics == []
    assert spec.comparison == "all"
    assert spec.default_granularity == "quarterly"
    assert spec.allowed_granularities == ["quarterly"]
    assert spec.default_years_back == 5

    metric_spec = catalog.get_metric("revenue")
    assert metric_spec is not None
    assert metric_spec.source == "Revenue"
    assert "quarterly" in metric_spec.allowed_granularities


def test_plan_sql_rule_based_uses_semantic_metrics_bundle():
    intent = _make_intent("margins_vs_peers")
    plan = plan_sql_rule_based(intent)

    assert plan["metrics"] == ["Revenue", "Gross Profit", "Operating Income", "Net Income"]
    assert plan["derived_metrics"] == ["gross_margin", "operating_margin", "net_margin"]
    assert plan["granularity"] == "quarterly"
    assert plan["group_by"] == ["calendar_year", "calendar_quarter_num", "calendar_quarter"]
    assert plan["timeframe"]["years_back"] == 5
    assert plan["filters"].get("granularity_filter") == "calendar_quarter_num IS NOT NULL"


def test_plan_granularity_override_respects_semantic_allow_list():
    intent = _make_intent("market_share_single", slots={"granularity": "Quarterly"})
    plan = plan_sql_rule_based(intent)

    assert plan["granularity"] == "quarterly"
    assert "calendar_quarter_num" in plan["group_by"]
    assert plan["filters"].get("granularity_filter") == "calendar_quarter_num IS NOT NULL"


def test_plan_fallback_for_unknown_intent_defaults_to_revenue():
    intent = _make_intent("unknown_intent")
    plan = plan_sql_rule_based(intent)

    assert plan["metrics"] == ["Revenue"]
    assert plan["comparison"] is None
    assert plan["timeframe"].get("years_back") is not None





