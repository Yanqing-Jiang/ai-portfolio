from datetime import date
import pytest
from fortune import agents


def test_full_year_end_window_is_scored_before_prefilter(monkeypatch):
    seen = []
    def chart(day, timezone):
        seen.append(day)
        return {'day': {'stem': '甲', 'branch': '子', 'stem_element': 'Wood', 'branch_element': 'Water'}}
    monkeypatch.setattr(agents, 'compute_day_chart_cached', chart)
    ctx = agents.FortuneRunContext(fortune_id='qa', surface_id='qa', focus='occasion:business:2026-09-05:2026-12-31')
    result = agents._build_occasion_window(ctx, foundation={'pillars': {'day': {'stem': '甲', 'branch': '子'}}})
    assert seen[0] == '2026-09-05'
    assert seen[-1] == '2026-12-31'
    assert len(seen) == (date(2026, 12, 31) - date(2026, 9, 5)).days + 1
    assert len(result['candidate_days']) <= 31
    assert result['end'] == '2026-12-31'


def test_repair_validation_includes_dates_after_day_62(monkeypatch):
    monkeypatch.setattr(agents, 'compute_day_chart_cached', lambda *_: {'day': {'stem': '甲', 'branch': '子', 'stem_element': 'Wood', 'branch_element': 'Water'}})
    ctx = agents.FortuneRunContext(fortune_id='qa', surface_id='qa', focus='occasion:wedding:2027-06-01:2027-08-31')
    result = agents._build_occasion_window(ctx)
    assert len(result['candidate_days']) == 92
    assert result['candidate_days'][-1]['date'] == '2027-08-31'


def test_oversized_windows_are_rejected_before_computation(monkeypatch):
    def unexpected(*_):
        pytest.fail('Oversized window must not compute charts')
    monkeypatch.setattr(agents, 'compute_day_chart_cached', unexpected)
    ctx = agents.FortuneRunContext(fortune_id='qa', surface_id='qa', focus='occasion:business:2026-01-01:2030-01-01')
    with pytest.raises(ValueError, match='18 months'):
        agents._build_occasion_window(ctx)
