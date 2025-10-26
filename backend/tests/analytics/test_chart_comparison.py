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

    included_columns = meta.get("includedColumns")
    assert set(included_columns) == {"AMD|revenue", "NVDA|revenue"}
    assert meta.get("metricColumns") == ["revenue"]
    assert meta.get("metricSeriesColumns", {}).get("revenue") == ["AMD|revenue", "NVDA|revenue"]
    assert meta.get("metricLegendMap", {}).get("revenue") == ["AMD", "NVDA"]
    assert meta.get("metricDisplayNames", {}).get("revenue") == "Revenue"
    assert meta.get("displayNames", {}).get("revenue") == "Revenue"

    chart_design = meta.get("chartDesign") or {}
    if chart_design:
        assert chart_design.get("comparison") == "all"
        assert chart_design.get("comparison_mode") == "multi_company"


def test_margin_growth_chart_keeps_peer_average_series():
    data = [
        {
            "ticker": "NVDA",
            "calendar_year": 2024,
            "calendar_quarter_num": 1,
            "calendar_quarter": "Q1",
            "company_gross_margin_change_pp": 2.1,
            "company_operating_margin_change_pp": 1.3,
            "company_net_margin_change_pp": 1.1,
            "peer_avg_gross_margin_change_pp": 0.7,
            "peer_avg_operating_margin_change_pp": 0.5,
            "peer_avg_net_margin_change_pp": 0.4,
        },
        {
            "ticker": "NVDA",
            "calendar_year": 2024,
            "calendar_quarter_num": 2,
            "calendar_quarter": "Q2",
            "company_gross_margin_change_pp": 1.8,
            "company_operating_margin_change_pp": 1.1,
            "company_net_margin_change_pp": 0.9,
            "peer_avg_gross_margin_change_pp": 0.6,
            "peer_avg_operating_margin_change_pp": 0.45,
            "peer_avg_net_margin_change_pp": 0.35,
        },
    ]

    plan = plan_chart_rule_based(
        data,
        "NVDA margin growth vs industry average",
        intent_key="margin_growth_vs_peers",
    )
    spec = build_chart_spec(
        data,
        plan.model_dump(),
        CONFIGS.charts,
        intent_key="margin_growth_vs_peers",
        comparison="vs_avg",
    )

    legend_names = spec["legend"]["data"]
    assert "Industry Average - Gross Margin Change" in legend_names
    assert "Industry Average - Operating Margin Change" in legend_names
    assert "Industry Average - Net Margin Change" in legend_names

    meta = spec.get("meta", {})
    included = set(meta.get("includedColumns", []))
    expected_columns = {
        "company_gross_margin_change_pp",
        "company_operating_margin_change_pp",
        "company_net_margin_change_pp",
        "peer_avg_gross_margin_change_pp",
        "peer_avg_operating_margin_change_pp",
        "peer_avg_net_margin_change_pp",
    }
    assert expected_columns.issubset(included)
