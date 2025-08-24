from ..cache.keys import sql_key


def test_sql_key_deterministic():
    k1 = sql_key("SELECT 1", {"a": 1}, "schema", "2024")
    k2 = sql_key("SELECT   1", {"a": 1}, "schema", "2024")
    assert k1 == k2


def test_sql_key_window_changes():
    k1 = sql_key("SELECT 1", {}, "schema", "2024")
    k2 = sql_key("SELECT 1", {}, "schema", "2025")
    assert k1 != k2
