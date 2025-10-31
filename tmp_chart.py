import sys
import types
from pprint import pprint

stub = types.ModuleType("unified_responses_client")

def _raise(*args, **kwargs):
    raise ValueError("stub")

stub.get_unified_client = _raise
sys.modules["unified_responses_client"] = stub

from backend.analytics.core.charting import build_chart_spec, plan_chart_rule_based
from backend.analytics.core.config import CONFIGS

data = [
    {"ticker": "AMD", "calendar_year": 2021, "revenue": 3.8e10},
    {"ticker": "NVDA", "calendar_year": 2021, "revenue": 5.3e10},
    {"ticker": "AMD", "calendar_year": 2022, "revenue": 4.7e10},
    {"ticker": "NVDA", "calendar_year": 2022, "revenue": 7.1e10},
]
plan = plan_chart_rule_based(data, "Compare AMD vs NVDA revenue", intent_key="revenue_comparison")
spec = build_chart_spec(data, plan.model_dump(), CONFIGS.charts, intent_key="revenue_comparison", comparison="all")
pprint(spec["series"])
