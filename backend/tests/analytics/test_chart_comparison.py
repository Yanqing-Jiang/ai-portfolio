import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[2]))

from analytics.core.charting import build_chart_spec, plan_chart_rule_based
from analytics.core.config import CONFIGS


def test_multi_company_revenue_chart_selects_all_series():
    data = [
        {"ticker": "AMD", "calendar_year": 2021, "revenue": 3.8e10},
        {"ticker": "NVDA", "calendar_year": 2021, "revenue": 5.3e10},
        {"ticker": "AMD", "calendar_year": 2022, "revenue": 4.7e10},
        {"ticker": "NVDA", "calendar_year": 2022, "revenue": 7.1e10},
    ]

    plan = plan_chart_rule_based(
        data,
        "Compare AMD vs NVDA revenue 2021-2024",
        intent_key="revenue_comparison",
    )
    spec = build_chart_spec(
        data,
        plan.model_dump(),
        CONFIGS.charts,
        intent_key="revenue_comparison",
        comparison="all",
    )

    legend_selected = spec["legend"]["selected"]
    assert legend_selected == {"AMD": True, "NVDA": True}

    meta = spec.get("meta", {})
    assert meta.get("comparison") == "all"

    default_selection = meta.get("defaultLegendSelection") or {}
    assert default_selection == {"AMD": True, "NVDA": True}
    assert meta.get("primarySeries") == ["AMD", "NVDA"]
    assert meta.get("highlightRules", {}).get("mutedSecondary", False) is False

    chart_design = meta.get("chartDesign", {})
    assert chart_design.get("comparison") == "all"
    assert chart_design.get("comparison_mode") == "multi_company"
