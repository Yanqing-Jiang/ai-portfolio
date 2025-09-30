import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
BACKEND_ROOT = ROOT / "backend"
for entry in (ROOT, BACKEND_ROOT):
    entry_str = str(entry)
    if entry_str not in sys.path:
        sys.path.insert(0, entry_str)

import pytest
from datetime import date

@pytest.fixture
def anyio_backend():
    return "asyncio"

from analytics.services.polygon import (
    PolygonMarketDataClient,
    PolygonError,
)


@pytest.mark.anyio("asyncio")
async def test_polygon_fetch_daily_bars(monkeypatch):
    payload = {
        "status": "OK",
        "results": [
            {"t": 1727481600000, "o": 100, "h": 110, "l": 95, "c": 108, "v": 1000000},
            {"t": 1727568000000, "o": 108, "h": 112, "l": 104, "c": 110, "v": 1200000},
        ],
    }

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self):
            return payload

    class FakeSession:
        def __init__(self):
            self.requested = None

        def get(self, url, params=None, timeout=10):
            self.requested = {"url": url, "params": params, "timeout": timeout}
            return FakeResponse()

    client = PolygonMarketDataClient(api_key="test", session=FakeSession())
    snapshot = await client.fetch_daily_bars("nvda", lookback_days=2, to_date=date(2025, 9, 29))

    assert snapshot.symbol == "NVDA"
    assert len(snapshot.bars) == 2
    assert snapshot.bars[-1].close == 110
    assert isinstance(snapshot.change_percent, float)


@pytest.mark.anyio("asyncio")
async def test_polygon_requires_api_key(monkeypatch):
    monkeypatch.delenv("POLYGON_API_KEY", raising=False)
    client = PolygonMarketDataClient(api_key=None, session=None)
    with pytest.raises(PolygonError):
        await client.fetch_daily_bars("NVDA")
