from analytics.flows.chart_revision import is_analysis_revision_query


def test_is_analysis_revision_query_accepts_insight_revision():
    query = "Revise the insight to focus on margin resilience."
    assert is_analysis_revision_query(query)


def test_is_analysis_revision_query_rejects_chart_only_phrase():
    query = "Change the chart to a stacked column."
    assert not is_analysis_revision_query(query)
