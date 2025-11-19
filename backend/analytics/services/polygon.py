# --- Analytics Function/Class Map ---
# Class: PolygonError
#   Role: Raised when the Polygon API returns an error payload or bad status.
#   Called from: analytics.flows.multi_agent, analytics.flows.tooling
#   Collaborators: Internal helpers only
#   Why: Supports downstream analytics workflows that rely on PolygonError.
# Class: DailyBar
#   Role: Handles DailyBar logic for analytics.services.polygon.
#   Called from: tests.analytics.test_revision_routing
#   Collaborators: Internal helpers only
#   Why: Keeps analytics.services.polygon from duplicating DailyBar behavior across flows.
# Class: MarketSnapshot
#   Role: Handles MarketSnapshot logic for analytics.services.polygon.
#   Called from: tests.analytics.test_revision_routing
#   Collaborators: Internal helpers only
#   Why: Keeps analytics.services.polygon from duplicating MarketSnapshot behavior across flows.
# Class: PolygonMarketDataClient
#   Role: Fetches daily OHLC data from Polygon.io using minimal configuration.
#   Called from: analytics.flows.multi_agent, analytics.flows.tooling
#   Collaborators: analytics.services.polygon.MarketSnapshot, os.getenv, requests.Session, analytics.services.polygon.PolygonError, +2 more
#   Why: Supports downstream analytics workflows that rely on PolygonMarketDataClient.
# Function: fetch_daily_snapshot
#   Role: Handles fetch daily snapshot logic for analytics.services.polygon.
#   Called from: analytics.flows.multi_agent, analytics.flows.tooling
#   Invokes: analytics.services.polygon.PolygonMarketDataClient
#   Why: Keeps analytics.services.polygon from duplicating fetch daily snapshot behavior across flows.
# --- End Analytics Function/Class Map ---
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

    def __init__(
        self,
        message: str,
        *,
        status_code: Optional[int] = None,
        retry_after: Optional[float] = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.retry_after = retry_after


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
            try:
                response = self._session.get(url, params=params, timeout=10)
                response.raise_for_status()
            except requests.HTTPError as exc:
                status_code = getattr(exc.response, "status_code", None)
                retry_after_header = (
                    exc.response.headers.get("Retry-After") if getattr(exc, "response", None) else None
                )
                retry_after = None
                if retry_after_header:
                    try:
                        retry_after = float(retry_after_header)
                    except ValueError:
                        retry_after = None
                raise PolygonError(
                    exc.response.text if getattr(exc, "response", None) else str(exc),
                    status_code=status_code,
                    retry_after=retry_after,
                ) from exc
            except requests.RequestException as exc:
                raise PolygonError(str(exc)) from exc
            payload = response.json()
            status = (payload.get("status") or "").upper()
            if status not in {"OK", "DELAYED"} or not payload.get("results"):
                raise PolygonError(
                    payload.get("error") or "Polygon API returned no results",
                    status_code=response.status_code,
                )
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
