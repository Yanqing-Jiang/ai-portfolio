from ..safety.sql_validator import validate_sql


def test_select_star_blocked():
    errors = validate_sql("SELECT * FROM table")
    assert "select_star_not_allowed" in errors
