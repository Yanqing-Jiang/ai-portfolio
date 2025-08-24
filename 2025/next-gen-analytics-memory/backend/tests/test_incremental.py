from ..nodes.incremental_sql import incremental_sql


def test_incremental_sql_returns_dict():
    result = incremental_sql({})
    assert isinstance(result, dict)
