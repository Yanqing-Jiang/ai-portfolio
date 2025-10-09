import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[2]))

from analytics.core.charting import build_chart_spec, plan_chart_rule_based
from analytics.core.config import CONFIGS


def test_plan_chart_rule_based_emits_ranking_bar():
    data = [
        {"ticker": "AMD", "operating_margin": 0.28},
        {"ticker": "NVDA", "operating_margin": 0.42},
        {"ticker": "INTC", "operating_margin": 0.18},
    ]
    plan = plan_chart_rule_based(data, "Who leads operating margin?", intent_key="margins_vs_peers", statistic="ranking_latest")
    assert plan.chart_type == "ranking_bar"
    assert plan.ranking_metric == "operating_margin"
    assert plan.statistic == "ranking_latest"

    spec = build_chart_spec(
        data,
        plan.dict(),
        CONFIGS.charts,
        intent_key="margins_vs_peers",
        comparison="all",
        statistic="ranking_latest",
    )

    assert spec["yAxis"]["data"] == ["NVDA", "AMD", "INTC"]
    assert spec["series"][0]["type"] == "bar"
    series_values = [point["value"] for point in spec["series"][0]["data"]]
    assert series_values == [0.42, 0.28, 0.18]
    meta = spec.get("meta", {})
    assert meta.get("ranking", {}).get("statistic") == "ranking_latest"
    assert "Ranking latest" in meta.get("scopeBanner", "")
