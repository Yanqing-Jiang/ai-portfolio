import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[2]))

from analytics.core.charting import build_chart_spec, plan_chart_rule_based
from analytics.core.config import CONFIGS


def test_market_share_single_uses_percent_series_only():
    data = [
        {
            "calendar_year": 2021,
            "market_share_percent": 32.4,
            "company_revenue": 45.1,
            "total_market_revenue": 139.0,
        },
        {
            "calendar_year": 2022,
            "market_share_percent": 29.8,
            "company_revenue": 49.4,
            "total_market_revenue": 165.7,
        },
        {
            "calendar_year": 2023,
            "market_share_percent": 27.1,
            "company_revenue": 54.2,
            "total_market_revenue": 200.1,
        },
    ]

    plan = plan_chart_rule_based(data, "Show NVDA market share", intent_key="market_share_single")
    plan_dict = plan.model_dump()

    assert plan_dict["chart_type"] == "line"
    assert len(plan_dict["series"]) == 1
    series = plan_dict["series"][0]
    assert series["data_column"] == "market_share_percent"
    assert series["name"] == "Market Share"
    assert series["value_type"] == "percent"

    spec = build_chart_spec(
        data,
        plan_dict,
        CONFIGS.charts,
        intent_key="market_share_single",
    )

    assert isinstance(spec, dict)
    assert len(spec["series"]) == 1
    assert spec["series"][0]["name"] == "Market Share"
    assert spec["legend"]["data"] == ["Market Share"]
    assert spec["meta"]["defaultColumns"] == ["market_share_percent"]
    assert spec["yAxis"][0]["name"] == "Percentage"
    # Ensure no secondary currency axis sneaks in
    assert all(axis.get("name") != "Currency" for axis in spec["yAxis"])
