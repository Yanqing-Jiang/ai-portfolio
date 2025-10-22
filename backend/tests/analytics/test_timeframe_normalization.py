from backend.analytics.core.config import CONFIGS
from backend.analytics.core.intent_impl.models import TimeframeModel
from backend.analytics.core.intent_impl.normalization import normalize_timeframe
from backend.analytics.core.state import QueryPlanModel


def test_normalize_timeframe_without_defaults():
    result = normalize_timeframe(None, '', CONFIGS.__dict__, apply_defaults=False)
    assert result == {}


def test_normalize_timeframe_phrase_detection():
    result = normalize_timeframe('last 5 years', '', CONFIGS.__dict__, apply_defaults=False)
    assert result.get('years_back') == 5
    assert result.get('source') == 'query'


def test_normalize_timeframe_applies_defaults():
    result = normalize_timeframe(None, '', CONFIGS.__dict__)
    assert result.get('years_back') is not None
    assert result.get('source') == 'default'


def test_timeframe_model_accepts_heuristic_source():
    heuristic_raw = {
        "start_year": 2021,
        "end_year": 2024,
        "years_back": 4,
    }
    normalized = normalize_timeframe(
        heuristic_raw,
        "AMD vs NVIDIA revenue comparison 2021-2024",
        CONFIGS.__dict__,
        apply_defaults=False,
        origin="heuristic",
    )
    assert normalized.get("source") == "heuristic"

    timeframe = TimeframeModel(**normalized)
    plan = QueryPlanModel(timeframe=timeframe)

    assert plan.timeframe.source == "heuristic"
    assert plan.timeframe.start_year == 2021
    assert plan.timeframe.end_year == 2024
