from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional

import os
import requests

DEFAULT_LOOKBACK_DAYS = 90
_POLYGON_BASE_URL = "https://api.polygon.io"


class PolygonError(Exception):
    """Raised when the Polygon API returns an error payload or bad status."""


@dataclass
class DailyBar:
    time: int
    open: float
    high: float
    low: float
    close: float
    volume: float


@dataclass
class MarketSnapshot:
    symbol: str
    bars: List[DailyBar]
    previous_close: Optional[float] = None
    latest_close: Optional[float] = None
    change_percent: Optional[float] = None


class PolygonMarketDataClient:
    """Fetches daily OHLC data from Polygon.io using minimal configuration."""

    def __init__(self, api_key: Optional[str] = None, session: Optional[requests.Session] = None) -> None:
        self.api_key = api_key or os.getenv("POLYGON_API_KEY")
        self._session = session or requests.Session()

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key)

    async def fetch_daily_bars(
        self,
        symbol: str,
        *,
        lookback_days: int = DEFAULT_LOOKBACK_DAYS,
        to_date: Optional[date] = None,
    ) -> MarketSnapshot:
        if not self.is_configured:
            raise PolygonError("POLYGON_API_KEY missing; cannot fetch market data")

        normalized_symbol = symbol.upper().strip()
        end_date = to_date or datetime.utcnow().date()
        start_date = end_date - timedelta(days=max(lookback_days, 1))

        params = {
            "adjusted": "true",
            "sort": "asc",
            "limit": "5000",
            "apiKey": self.api_key,
        }
        url = (
            f"{_POLYGON_BASE_URL}/v2/aggs/ticker/{normalized_symbol}/range/1/day/"
            f"{start_date.isoformat()}/{end_date.isoformat()}"
        )

        def _request() -> Dict[str, Any]:
            response = self._session.get(url, params=params, timeout=10)
            response.raise_for_status()
            payload = response.json()
            status = (payload.get("status") or "").upper()
            if status not in {"OK", "DELAYED"} or not payload.get("results"):
                raise PolygonError(payload.get("error") or "Polygon API returned no results")
            return payload

        payload = await asyncio.to_thread(_request)
        bars = [
            DailyBar(
                time=int(entry["t"] // 1000),
                open=float(entry["o"]),
                high=float(entry["h"]),
                low=float(entry["l"]),
                close=float(entry["c"]),
                volume=float(entry["v"]),
            )
            for entry in payload.get("results", [])
        ]
        if not bars:
            raise PolygonError("No aggregate bars returned from Polygon")

        previous_close = bars[-2].close if len(bars) > 1 else None
        latest_close = bars[-1].close
        change_percent: Optional[float] = None
        if previous_close and previous_close != 0:
            change_percent = ((latest_close - previous_close) / previous_close) * 100

        return MarketSnapshot(
            symbol=normalized_symbol,
            bars=bars,
            previous_close=previous_close,
            latest_close=latest_close,
            change_percent=change_percent,
        )


async def fetch_daily_snapshot(symbol: str, *, client: Optional[PolygonMarketDataClient] = None) -> MarketSnapshot:
    active_client = client or PolygonMarketDataClient()
    return await active_client.fetch_daily_bars(symbol)
