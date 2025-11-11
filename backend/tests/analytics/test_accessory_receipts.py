from datetime import datetime, timedelta

from analytics.accessory_receipts import _compute_age_seconds, _normalize_timestamp


def test_normalize_timestamp_sets_timezone_for_naive_strings() -> None:
    naive_text = "2025-11-11T06:00:00"
    parsed = _normalize_timestamp(naive_text)
    assert parsed is not None
    assert parsed.tzinfo is not None


def test_compute_age_seconds_accepts_naive_strings() -> None:
    naive = datetime.now() - timedelta(seconds=5)
    receipt = {"timestamp": naive.strftime("%Y-%m-%dT%H:%M:%S")}
    age = _compute_age_seconds(receipt)
    assert age is not None
    assert age >= 0
