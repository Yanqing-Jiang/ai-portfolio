from __future__ import annotations

from typing import Any, Dict, List, Optional, Set, Tuple
import copy
import json
from analytics.validators import sanitize_for_json

_WEB_SNIPPET_LIMIT = 5


def _merge_web_payloads(payloads: List[Dict[str, Any]], *, base_query: Optional[str] = None) -> Dict[str, Any]:
    merged_entries: List[Dict[str, Any]] = [dict(payload) for payload in payloads if isinstance(payload, dict)]
    if not merged_entries:
        return {}

    summaries: List[str] = []
    annotations: List[Dict[str, Any]] = []
    topics: List[Dict[str, Any]] = []
    snippets: List[Dict[str, Any]] = []
    search_topics: List[str] = []
    ready_any = False
    from_cache_all = True
    model: Optional[str] = None
    usage: Optional[Dict[str, Any]] = None
    fetched_at: Optional[str] = None
    search_id: Optional[str] = None
    latency_total = 0
    query_value = base_query

    for entry in merged_entries:
        ready_any = ready_any or bool(entry.get("ready"))
        if not entry.get("from_cache"):
            from_cache_all = False
        model = entry.get("model") or model
        usage = entry.get("usage") or usage
        fetched_at = entry.get("fetched_at") or fetched_at
        if not search_id:
            search_id = entry.get("search_id")
        if not query_value:
            query_value = entry.get("query") or entry.get("query_terms")

        summary = entry.get("summary")
        if isinstance(summary, str) and summary.strip():
            summaries.append(summary.strip())

        entry_topics = entry.get("topics")
        if isinstance(entry_topics, list):
            topics.extend(entry_topics)

        entry_snippets = entry.get("snippets")
        if isinstance(entry_snippets, list):
            snippets.extend(entry_snippets)

        entry_annotations = entry.get("annotations")
        if isinstance(entry_annotations, list):
            annotations.extend(entry_annotations)

        entry_search_topics = entry.get("search_topics")
        if isinstance(entry_search_topics, list):
            for topic in entry_search_topics:
                if isinstance(topic, str) and topic.strip() and topic not in search_topics:
                    search_topics.append(topic)
        else:
            topic_value = entry.get("search_topic")
            if isinstance(topic_value, str) and topic_value.strip() and topic_value not in search_topics:
                search_topics.append(topic_value)

        latency = entry.get("latency_ms")
        if isinstance(latency, (int, float)):
            latency_total += int(latency)

    deduped_snippets: List[Dict[str, Any]] = []
    seen_snippet_keys: Set[str] = set()
    for snippet in snippets:
        if not isinstance(snippet, dict):
            continue
        key = snippet.get("url") or snippet.get("display_url") or snippet.get("snippet") or json.dumps(snippet, sort_keys=True)
        key_lower = key.lower() if isinstance(key, str) else str(key)
        if key_lower in seen_snippet_keys:
            continue
        seen_snippet_keys.add(key_lower)
        deduped_snippets.append(snippet)
        if len(deduped_snippets) >= _WEB_SNIPPET_LIMIT:
            break

    combined_summary = None
    if summaries:
        combined_summary = "\n\n".join(dict.fromkeys(summaries))

    merged_context: Dict[str, Any] = {
        "query": query_value,
        "query_terms": query_value,
        "search_topic": search_topics[0] if search_topics else None,
        "search_topics": search_topics,
        "summary": combined_summary,
        "snippets": deduped_snippets,
        "annotations": annotations,
        "topics": topics,
        "usage": usage,
        "fetched_at": fetched_at,
        "latency_ms": latency_total or None,
        "model": model,
        "from_cache": from_cache_all,
        "ready": ready_any,
        "search_id": search_id,
        "topic_count": len(merged_entries),
    }
    return merged_context


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

    payloads: List[Dict[str, Any]] = []
    base_query: Optional[str] = None
    topic_total: int = 0

    for entry in results:
        if not isinstance(entry, dict):
            continue
        tool_name = str(entry.get("tool") or "").strip()
        if not tool_name.startswith("web_retriever"):
            continue
        payload = entry.get("payload") or {}
        if not isinstance(payload, dict):
            continue
        if not payload.get("ready") and not payload.get("snippets"):
            continue

        payload_copy = copy.deepcopy(payload)
        metadata = entry.get("metadata")
        if isinstance(metadata, dict):
            summary = metadata.get("summary")
            if summary and not payload_copy.get("summary"):
                payload_copy["summary"] = summary
            cache_hit = metadata.get("cache_hit")
            if cache_hit is not None and "from_cache" not in payload_copy:
                payload_copy["from_cache"] = cache_hit
            for key in ("topic_index", "topic_total", "topic_label", "topic_position"):
                if key in metadata and key not in payload_copy:
                    payload_copy[key] = metadata[key]
        if base_query is None:
            base_query = payload_copy.get("query") or payload_copy.get("query_terms")
        try:
            topic_total = max(topic_total, int(payload_copy.get("topic_total") or 0))
        except (TypeError, ValueError):
            pass
        payloads.append(payload_copy)

    if not payloads:
        return None

    merged_context = _merge_web_payloads(payloads, base_query=base_query)
    if topic_total:
        merged_context["topic_total"] = topic_total

    topics = merged_context.get("topics")
    if isinstance(topics, list):
        merged_context["topics"] = sorted(
            topics,
            key=lambda topic: (
                topic.get("topic_index")
                if isinstance(topic.get("topic_index"), int)
                else float("inf"),
                topic.get("query") or "",
            ),
        )
    return merged_context


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
    sources: Dict[str, str] = {}
    if results:
        bundle["tool_results"] = copy.deepcopy(results)
        stock_widget = stock_widget or _extract_stock_widget(results)
        web_context = web_context or _extract_web_context(results)
        for entry in results:
            if not isinstance(entry, dict):
                continue
            tool_name = str(entry.get("tool") or "").strip()
            if not tool_name:
                continue
            payload = entry.get("payload") or {}
            status = str(entry.get("status") or "").strip().lower()
            base_tool = tool_name
            if base_tool.startswith("web_retriever"):
                base_tool = "web_retriever"
            reused_flag = bool(entry.get("reused"))
            from_cache = bool(payload.get("from_cache"))
            if reused_flag or from_cache:
                sources[base_tool] = "cached"
            elif status in {"completed", "complete", "success"}:
                sources.setdefault(base_tool, "fanout")
            elif status in {"queued"}:
                sources.setdefault(base_tool, "queued")
    if stock_widget:
        bundle["stock_widget"] = copy.deepcopy(stock_widget)
    if web_context:
        bundle["web_context"] = copy.deepcopy(web_context)
    if sources:
        bundle["sources"] = copy.deepcopy(sources)
    return sanitize_for_json(bundle)



