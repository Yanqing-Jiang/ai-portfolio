from backend.analytics.core.slot_catalog import get_slot_catalog


def test_market_share_single_has_company_slot():
    catalog = get_slot_catalog(refresh=True)
    definition = catalog.get_intent_definition("market_share_single")
    assert definition is not None
    assert "company" in definition.required_slots
    company_options = definition.slot_options["company"]
    assert "AMD" in company_options.suggestions
    assert "NVDA" in company_options.suggestions
    assert company_options.allow_custom is True


def test_timeframe_presets_available_for_market_share():
    catalog = get_slot_catalog(refresh=True)
    definition = catalog.get_intent_definition("market_share_single")
    assert definition is not None
    timeframe_options = definition.slot_options["timeframe"]
    assert "last 4 quarters" in timeframe_options.presets
    assert "last 5 years" in timeframe_options.suggestions
    assert timeframe_options.allow_custom is True


def test_catalog_lists_all_known_intents():
    catalog = get_slot_catalog(refresh=True)
    intents = catalog.list_intents()
    assert "market_share_single" in intents
    assert "market_share_all" in intents


def test_metric_suggestions_use_curated_list():
    catalog = get_slot_catalog(refresh=True)
    metric_options = catalog.get_slot_options("metric")
    assert metric_options is not None
    expected = [
        "Revenue",
        "Net Income",
        "Capital Expenditures",
        "EPS Basic",
        "Income Before Tax",
        "Operating Income",
        "Stockholders' Equity",
        "R&D Expense",
        "Gross Profit",
    ]
    assert metric_options.suggestions[: len(expected)] == expected
