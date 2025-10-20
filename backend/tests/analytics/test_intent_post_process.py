import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[2]))

from analytics.core.intent_impl.detection import post_process_slots


def test_post_process_slots_prioritises_query_order():
    slots = {
        "company": ["NVDA", "AMD", "INTC"],
        "tickers": ["NVDA", "AMD", "INTC"],
    }
    query = "How did AMD margins compare to NVDA last quarter?"

    processed = post_process_slots(slots, query, configs={})

    assert processed["company"] == "AMD"
    assert processed["tickers"][:2] == ["AMD", "NVDA"]
    assert processed["company_candidates"] == ["AMD", "NVDA", "INTC"]


def test_post_process_slots_detects_company_when_missing():
    query = "Give me the latest on TSLA revenue guidance"

    processed = post_process_slots(
        slots={},
        query=query,
        configs={},
        resolve_alias_func=lambda token, _cfg: "TSLA" if token.lower() == "tsla" else None,
    )

    assert processed["company"] == "TSLA"
    assert processed["tickers"] == ["TSLA"]
    assert processed["company_candidates"] == ["TSLA"]


def test_post_process_slots_timeframe_forces_quarterly():
    slots = {
        "timeframe": "last 4 quarters",
        "granularity": "annual",
    }
    processed = post_process_slots(slots, "Compare revenue over the last 4 quarters", configs={})

    assert processed["timeframe"]["quarters_back"] == 4
    assert processed["granularity"] == "quarterly"


def test_post_process_slots_last_five_years_promotes_quarterly():
    slots = {
        "timeframe": "last 5 years",
        "granularity": "annual",
    }
    processed = post_process_slots(slots, "Show last 5 years quarterly performance", configs={})

    assert processed["timeframe"]["years_back"] == 5
    assert processed["granularity"] == "quarterly"


def test_post_process_slots_last_five_years_defaults_to_annual_without_quarter_hint():
    slots = {
        "timeframe": "last 5 years",
    }
    processed = post_process_slots(slots, "Nvidia market share in the past 5 years?", configs={})

    assert processed["timeframe"]["years_back"] == 5
    assert processed["granularity"] == "annual"
