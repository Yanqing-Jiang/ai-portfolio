"""Market data tool definitions for analytics agents."""
from __future__ import annotations

from typing import Any, Dict, List

from analytics.services.polygon import PolygonError, PolygonMarketDataClient

from ..tool_registry import AnalyticsTool, ToolSpec


class MarketSnapshotTool(AnalyticsTool):
    """Fetches recent market snapshots for supplied tickers via Polygon."""

    def __init__(self) -> None:
        spec = ToolSpec(
            name="market.snapshot",
            description="Fetch recent market performance snapshots for the provided tickers.",
            input_schema={
                "type": "object",
                "properties": {
                    "tickers": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "lookback_days": {"type": "integer", "minimum": 1, "maximum": 365},
                },
                "required": ["tickers"],
            },
            output_schema={
                "type": "object",
                "properties": {
                    "status": {"type": "string"},
                    "tickers": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "snapshots": {
                        "type": "array",
                        "items": {"type": "object"},
                    },
                    "errors": {
                        "type": "array",
                        "items": {"type": "object"},
                    },
                },
            },
        )
        super().__init__(spec)

    async def ainvoke(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        raw_tickers = payload.get("tickers")
        if not isinstance(raw_tickers, list):
            raise ValueError("'tickers' must be a list of ticker symbols")

        normalized = self._normalize(raw_tickers)
        response: Dict[str, Any] = {
            "tickers": normalized,
            "snapshots": [],
            "status": "skipped" if not normalized else "pending",
        }
        if not normalized:
            return response

        lookback_days = int(payload.get("lookback_days", 90))
        client = PolygonMarketDataClient()
        if not client.is_configured:
            response.update(
                {
                    "status": "unavailable",
                    "errors": [
                        {
                            "reason": "missing_polygon_api_key",
                            "message": "POLYGON_API_KEY missing; cannot fetch market data",
                        }
                    ],
                }
            )
            return response

        snapshots: List[Dict[str, Any]] = []
        errors: List[Dict[str, Any]] = []

        for ticker in normalized[:3]:
            try:
                market_snapshot = await client.fetch_daily_bars(ticker, lookback_days=lookback_days)
                snapshots.append(
                    {
                        "symbol": market_snapshot.symbol,
                        "latest_close": market_snapshot.latest_close,
                        "previous_close": market_snapshot.previous_close,
                        "change_percent": market_snapshot.change_percent,
                    }
                )
            except PolygonError as exc:
                errors.append({"symbol": ticker, "error": str(exc)})

        response.update({
            "status": "ok" if snapshots else "error",
            "snapshots": snapshots,
        })
        if errors:
            response["errors"] = errors
        return response

    def _normalize(self, tickers: List[Any]) -> List[str]:
        normalized: List[str] = []
        seen = set()
        for value in tickers:
            if not isinstance(value, str):
                continue
            candidate = value.strip().upper()
            if not candidate or candidate in seen:
                continue
            seen.add(candidate)
            normalized.append(candidate)
        return normalized


__all__ = ["MarketSnapshotTool"]
