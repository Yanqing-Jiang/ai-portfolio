import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[2]))

import pytest

from analytics.core.charting import plan_chart_rule_based, build_chart_spec
from analytics.core.config import CONFIGS
from analytics.flows.tool_bundle import _extract_stock_widget


@pytest.fixture
def sample_ohlc_data():
    return [
        {
            "calendar_date": "2024-09-01",
            "ticker": "NVDA",
            "open": 450.12,
            "high": 468.5,
            "low": 444.3,
            "close": 462.9,
            "volume": 18234567,
        },
        {
            "calendar_date": "2024-09-02",
            "ticker": "NVDA",
            "open": 463.5,
            "high": 471.2,
            "low": 455.0,
            "close": 469.4,
            "volume": 16230123,
        },
    ]


def test_plan_chart_rule_based_detects_candlestick(sample_ohlc_data):
    plan = plan_chart_rule_based(sample_ohlc_data, query="Show NVDA price candles", intent_key="market_analysis")

    assert plan.chart_type == "candlestick"
    assert plan.series, "Expected candlestick plan to include series detail"
    candle_series = plan.series[0]
    assert candle_series.open_column == "open"
    assert candle_series.high_column == "high"
    assert candle_series.low_column == "low"
    assert candle_series.close_column == "close"


def test_build_chart_spec_emits_candlestick_series(sample_ohlc_data):
    plan_model = plan_chart_rule_based(sample_ohlc_data, query="NVDA ohlc", intent_key="market_analysis")
    plan_dict = plan_model.model_dump()

    spec = build_chart_spec(sample_ohlc_data, plan_dict, CONFIGS.charts, intent_key="market_analysis")

    assert spec["series"], "Candlestick chart should include at least one series"
    primary_series = spec["series"][0]
    assert primary_series["type"] == "candlestick"
    assert primary_series["data"][0] == [pytest.approx(450.12, rel=1e-6), pytest.approx(462.9, rel=1e-6), pytest.approx(444.3, rel=1e-6), pytest.approx(468.5, rel=1e-6)]
    assert spec["meta"]["chartDesign"]["chart_type"] == "candlestick"
    assert spec["meta"]["ohlcColumns"]["open"] == "open"


def test_extract_stock_widget_preserves_new_fields():
    payload = {
        "tool": "stock_tracker",
        "payload": {
            "ready": True,
            "symbol": "NVDA",
            "tickers": ["NVDA"],
            "fetched_at": "2024-09-02T12:00:00Z",
            "chartType": "candlestick",
            "showVolume": True,
            "showMA": False,
            "autosize": True,
            "bars": [
                {"time": 1693612800, "open": 450.12, "high": 468.5, "low": 444.3, "close": 462.9, "volume": 18234567}
            ],
        },
    }

    widget = _extract_stock_widget([payload])

    assert widget is not None
    assert widget["chartType"] == "candlestick"
    assert widget["showVolume"] is True
    assert widget["showMA"] is False
    assert widget["autosize"] is True
    assert widget["bars"][0]["open"] == 450.12
def test_extract_stock_widget_returns_widget_when_ready_false():
    payload = {
        "tool": "stock_tracker",
        "payload": {
            "ready": False,
            "tickers": ["NVDA"],
            "stock_widget": {
                "symbols": [["NASDAQ:NVDA", "NVDA"]],
                "chartType": "candlesticks",
                "showVolume": True,
                "showMA": False,
                "autosize": True,
                "height": 420,
            },
        },
    }

    widget = _extract_stock_widget([payload])

    assert widget is not None
    assert widget["symbols"][0][0] == "NASDAQ:NVDA"
    assert widget["chartType"] == "candlesticks"
    assert widget["showVolume"] is True
