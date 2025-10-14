from __future__ import annotations

from typing import Any, Dict, List, Optional
import copy
from analytics.validators import sanitize_for_json



def _extract_stock_widget(results: Optional[List[Dict[str, Any]]]) -> Optional[Dict[str, Any]]:
    if not isinstance(results, list):
        return None
    for entry in reversed(results):
        if not isinstance(entry, dict) or entry.get("tool") != "stock_tracker":
            continue
        payload = entry.get("payload") or {}
        if not isinstance(payload, dict):
            continue

        widget_payload = payload.get("stock_widget")
        ready = bool(payload.get("ready"))

        if isinstance(widget_payload, dict):
            widget: Dict[str, Any] = copy.deepcopy(widget_payload)
        elif ready:
            widget = {}
        else:
            continue

        symbols: List[Any] = []
        symbols_value = widget.get("symbols") if isinstance(widget, dict) else None
        if isinstance(symbols_value, list) and symbols_value:
            symbols = copy.deepcopy(symbols_value)
        else:
            symbol = payload.get("symbol")
            if isinstance(symbol, str) and symbol.strip():
                symbols.append(symbol.strip().upper())
            tickers = payload.get("tickers")
            if not symbols and isinstance(tickers, list):
                for candidate in tickers:
                    if isinstance(candidate, str) and candidate.strip():
                        symbols.append(candidate.strip().upper())
                        break
        if not symbols:
            continue
        widget["symbols"] = symbols

        tickers = payload.get("tickers")
        if isinstance(tickers, list) and tickers:
            widget.setdefault(
                "original",
                [
                    str(ticker).strip().upper()
                    for ticker in tickers
                    if isinstance(ticker, str) and ticker.strip()
                ],
            )

        fetched_at = payload.get("fetched_at")
        if isinstance(fetched_at, str) and fetched_at:
            widget.setdefault("generated_at", fetched_at)

        locale = payload.get("locale")
        if isinstance(locale, str) and locale:
            widget.setdefault("locale", locale)

        color_theme = payload.get("colorTheme") or payload.get("color_theme")
        if isinstance(color_theme, str) and color_theme:
            widget.setdefault("colorTheme", color_theme)

        height = payload.get("height")
        if isinstance(height, (int, float)) and height > 0:
            widget.setdefault("height", int(height))

        chart_type = payload.get("chartType") or payload.get("chart_type")
        if isinstance(chart_type, str) and chart_type:
            widget.setdefault("chartType", chart_type)

        show_volume = payload.get("showVolume")
        if isinstance(show_volume, bool):
            widget.setdefault("showVolume", show_volume)

        show_ma = payload.get("showMA")
        if isinstance(show_ma, bool):
            widget.setdefault("showMA", show_ma)

        autosize = payload.get("autosize")
        if isinstance(autosize, bool):
            widget.setdefault("autosize", autosize)

        bars = payload.get("bars")
        if "bars" not in widget and isinstance(bars, list) and bars:
            widget["bars"] = copy.deepcopy(bars)

        return widget
    return None



def _extract_web_context(results: Optional[List[Dict[str, Any]]]) -> Optional[Dict[str, Any]]:
    if not isinstance(results, list):
        return None
    for entry in reversed(results):
        if not isinstance(entry, dict) or entry.get("tool") != "web_retriever":
            continue
        payload = entry.get("payload") or {}
        if not isinstance(payload, dict) or not payload.get("ready"):
            continue
        context = copy.deepcopy(payload)
        metadata = entry.get("metadata")
        if isinstance(metadata, dict):
            summary = metadata.get("summary")
            if summary and not context.get("summary"):
                context["summary"] = summary
            cache_hit = metadata.get("cache_hit")
            if cache_hit is not None and "from_cache" not in context:
                context["from_cache"] = cache_hit
        return context
    return None


def collect_tool_bundle(
    *,
    manifest: Optional[List[Dict[str, Any]]] = None,
    results: Optional[List[Dict[str, Any]]] = None,
    stock_widget: Optional[Dict[str, Any]] = None,
    web_context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    bundle: Dict[str, Any] = {}
    if manifest:
        bundle["tool_manifest"] = copy.deepcopy(manifest)
    if results:
        bundle["tool_results"] = copy.deepcopy(results)
        stock_widget = stock_widget or _extract_stock_widget(results)
        web_context = web_context or _extract_web_context(results)
    if stock_widget:
        bundle["stock_widget"] = copy.deepcopy(stock_widget)
    if web_context:
        bundle["web_context"] = copy.deepcopy(web_context)
    return sanitize_for_json(bundle)

