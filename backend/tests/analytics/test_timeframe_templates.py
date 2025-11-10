from datetime import datetime

import pytest

from analytics.core.context import get_configs
from analytics.core.intent import IntentModel
from analytics.sql import compiler as sql_compiler
from analytics.sql.sql_planner import build_query_plan
import analytics.sql.sql_planner as sql_planner_module


class _FixedDateTime(datetime):
    @classmethod
    def utcnow(cls) -> "datetime":
        return cls(2025, 11, 9)


def test_last_five_years_excludes_current_year(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sql_planner_module, "datetime", _FixedDateTime)

    intent = IntentModel(
        intent_key="revenue_growth_vs_avg",
        confidence=0.9,
        slots_detected={
            "company": "AMD",
            "timeframe": {"preset": "last_5_years", "years_back": 5},
        },
    )

    plan = build_query_plan(intent)
    timeframe = getattr(plan, "timeframe", None)
    assert timeframe is not None
    assert timeframe.start_year == 2020
    assert timeframe.end_year == 2024

    configs = get_configs()
    template = configs.queries.get("query_patterns", {}).get("revenue_growth_vs_avg")
    assert template, "Expected revenue_growth_vs_avg template to be configured"

    sql = sql_compiler.compile_sql_from_plan(plan, intent, configs.__dict__, template)
    assert "calendar_year BETWEEN 2020 AND 2024" in sql
