from backend.analytics.core.config import CONFIGS
from backend.analytics.core.intent_impl.normalization import normalize_timeframe


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
