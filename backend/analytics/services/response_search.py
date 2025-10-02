from __future__ import annotations

import asyncio
import logging
import os
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional, Tuple

from analytics.core.telemetry import responses_call
from unified_responses_client import get_unified_client

logger = logging.getLogger(__name__)

_DEFAULT_MODEL = os.getenv("OPENAI_RESPONSES_SEARCH_MODEL") or os.getenv("OPENAI_MODEL", "gpt-5-mini-2025-08-07")
_DEFAULT_CONTEXT_SIZE = os.getenv("WEB_SEARCH_CONTEXT_SIZE", "medium")
_DEFAULT_COUNTRY = os.getenv("WEB_SEARCH_COUNTRY", "US")
_DEFAULT_CITY = os.getenv("WEB_SEARCH_CITY")
_MAX_SNIPPETS = int(os.getenv("WEB_SEARCH_MAX_SNIPPETS", "5"))
_RETRY_ATTEMPTS = int(os.getenv("WEB_SEARCH_RETRY_ATTEMPTS", "2"))
_RETRY_BASE_DELAY = float(os.getenv("WEB_SEARCH_RETRY_BASE_DELAY", "0.6"))


class ResponseSearchError(RuntimeError):
    """Raised when the Responses API web search call fails."""


@dataclass
class SearchSnippet:
    """Structured snippet returned to analytics flows."""

    title: Optional[str] = None
    url: Optional[str] = None
    snippet: Optional[str] = None
    display_url: Optional[str] = None
    published_at: Optional[str] = None
    annotation: Optional[Dict[str, Any]] = None


@dataclass
class ResponseSearchResult:
    query: str
    search_id: Optional[str] = None
    summary: Optional[str] = None
    snippets: List[SearchSnippet] = field(default_factory=list)
    annotations: List[Dict[str, Any]] = field(default_factory=list)
    usage: Optional[Dict[str, Any]] = None
    fetched_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    latency_ms: Optional[int] = None
    model: Optional[str] = None
    from_cache: bool = False

    def to_payload(self) -> Dict[str, Any]:
        payload = {
            "query": self.query,
            "search_id": self.search_id,
            "summary": self.summary,
            "snippets": [asdict(snippet) for snippet in self.snippets][: _MAX_SNIPPETS],
            "annotations": self.annotations,
            "usage": self.usage,
            "fetched_at": self.fetched_at,
            "latency_ms": self.latency_ms,
            "model": self.model,
            "from_cache": self.from_cache,
        }
        return payload


def _format_messages(query: str, *, context: Optional[str] = None) -> List[Dict[str, Any]]:
    system_prompt = (
        "You enrich analytics answers with factual, recent snippets from trusted sources. "
        "Summaries must stay concise (<=75 words) and cite the annotations returned by the web search tool."
    )
    user_prompt = context.strip() if context else query.strip()
    return [
        {
            "role": "system",
            "content": [{"type": "input_text", "text": system_prompt}],
        },
        {
            "role": "user",
            "content": [{"type": "input_text", "text": user_prompt or query}],
        },
    ]


def _build_tool_payload(*, country: Optional[str], city: Optional[str], context_size: str) -> Dict[str, Any]:
    user_location: Dict[str, Any] = {}
    if country:
        user_location["country"] = country
    if city:
        user_location["city"] = city
    payload: Dict[str, Any] = {"type": "web_search_preview", "search_context_size": context_size}
    if user_location:
        payload["user_location"] = user_location
    return payload


def _as_dict(obj: Any) -> Dict[str, Any]:
    if obj is None:
        return {}
    if isinstance(obj, dict):
        return obj
    for attr in ("model_dump", "dict", "to_dict"):
        if hasattr(obj, attr):
            try:
                data = getattr(obj, attr)()
                if isinstance(data, dict):
                    return data
            except Exception:  # pragma: no cover - defensive
                continue
    return {}


def _dedupe_snippets(snippets: Iterable[SearchSnippet]) -> List[SearchSnippet]:
    seen: Dict[str, SearchSnippet] = {}
    for snippet in snippets:
        key = (snippet.url or snippet.title or str(len(seen))).lower()
        if key in seen:
            existing = seen[key]
            if not existing.snippet and snippet.snippet:
                existing.snippet = snippet.snippet
            if not existing.title and snippet.title:
                existing.title = snippet.title
            if not existing.display_url and snippet.display_url:
                existing.display_url = snippet.display_url
            if not existing.annotation and snippet.annotation:
                existing.annotation = snippet.annotation
            if not existing.published_at and snippet.published_at:
                existing.published_at = snippet.published_at
        else:
            seen[key] = snippet
    return list(seen.values())[: _MAX_SNIPPETS]


def _extract_annotations(message_blocks: List[Dict[str, Any]]) -> Tuple[str, List[Dict[str, Any]], List[SearchSnippet]]:
    summary_chunks: List[str] = []
    annotations: List[Dict[str, Any]] = []
    snippets: List[SearchSnippet] = []

    for block in message_blocks:
        if block.get("type") != "message":
            continue
        for segment in block.get("content", []) or []:
            if segment.get("type") != "output_text":
                continue
            text = segment.get("text") or ""
            if text:
                summary_chunks.append(text)
            for annotation in segment.get("annotations", []) or []:
                if annotation.get("type") != "url_citation":
                    continue
                annotations.append(annotation)
                snippet_text = None
                try:
                    start = annotation.get("start_index")
                    end = annotation.get("end_index")
                    if isinstance(start, int) and isinstance(end, int) and start < end and len(text) >= end:
                        snippet_text = text[start:end].strip()
                except Exception:  # pragma: no cover - defensive
                    snippet_text = None
                display = annotation.get("display") or {}
                snippets.append(
                    SearchSnippet(
                        title=annotation.get("title") or display.get("friendly_name"),
                        url=annotation.get("url"),
                        snippet=snippet_text,
                        display_url=display.get("url"),
                        published_at=annotation.get("published_at"),
                        annotation=annotation,
                    )
                )

    summary = "\n".join(chunk.strip() for chunk in summary_chunks if chunk.strip())
    return summary, annotations, snippets


def _extract_results(output_blocks: List[Dict[str, Any]]) -> Tuple[Optional[str], List[SearchSnippet]]:
    search_id: Optional[str] = None
    snippets: List[SearchSnippet] = []
    for block in output_blocks:
        if block.get("type") != "web_search_call":
            continue
        search_id = block.get("id") or search_id
        for result in block.get("results", []) or []:
            snippets.append(
                SearchSnippet(
                    title=result.get("title") or result.get("url"),
                    url=result.get("url"),
                    snippet=result.get("snippet"),
                    display_url=result.get("display_url") or result.get("url"),
                    published_at=result.get("published_at"),
                )
            )
    return search_id, snippets


async def perform_response_search(
    query: str,
    *,
    session_id: Optional[str] = None,
    context: Optional[str] = None,
    country: Optional[str] = None,
    city: Optional[str] = None,
    context_size: Optional[str] = None,
    model: Optional[str] = None,
) -> ResponseSearchResult:
    if not query or not query.strip():
        raise ValueError("Search query must be provided")

    client = get_unified_client()
    if not client:
        raise ResponseSearchError("Unified OpenAI client is not configured")

    messages = _format_messages(query, context=context)
    tool_payload = _build_tool_payload(
        country=country or _DEFAULT_COUNTRY,
        city=city or _DEFAULT_CITY,
        context_size=context_size or _DEFAULT_CONTEXT_SIZE,
    )
    params = {
        "model": model or _DEFAULT_MODEL,
        "input": messages,
        "tools": [tool_payload],
        "tool_choice": {"type": "tool", "name": "web_search_preview"},
    }

    attempts = max(1, _RETRY_ATTEMPTS)
    attempt = 0
    last_error: Optional[Exception] = None
    response_dict: Dict[str, Any] = {}
    elapsed_ms: Optional[int] = None

    while attempt < attempts:
        start = time.perf_counter()
        try:
            raw_response = await client.client.responses.create(**params)
            elapsed_ms = int((time.perf_counter() - start) * 1000)
            response_dict = _as_dict(raw_response)
            responses_call(
                call_type="web_search_preview",
                model=params["model"],
                reasoning_effort=None,
                duration_ms=elapsed_ms,
                status="success",
                session_id=session_id,
                metadata={"attempt": attempt + 1, "response_id": response_dict.get("id")},
            )
            break
        except Exception as exc:  # pragma: no cover - network/SDK failure
            elapsed_ms = int((time.perf_counter() - start) * 1000)
            last_error = exc
            responses_call(
                call_type="web_search_preview",
                model=params["model"],
                reasoning_effort=None,
                duration_ms=elapsed_ms,
                status="error",
                session_id=session_id,
                error=str(exc),
                metadata={"attempt": attempt + 1},
            )
            attempt += 1
            if attempt >= attempts:
                logger.error("Responses API web search failed after %s attempts", attempts)
                raise ResponseSearchError("Responses API web search failed") from exc
            delay = _RETRY_BASE_DELAY * (2 ** (attempt - 1))
            await asyncio.sleep(delay)

    output_blocks = response_dict.get("output") or []
    summary, annotations, annotation_snippets = _extract_annotations(output_blocks)
    search_id, result_snippets = _extract_results(output_blocks)

    combined_snippets = _dedupe_snippets([*result_snippets, *annotation_snippets])

    result = ResponseSearchResult(
        query=query,
        search_id=search_id,
        summary=summary or None,
        snippets=combined_snippets,
        annotations=annotations,
        usage=response_dict.get("usage"),
        fetched_at=datetime.utcnow().isoformat(),
        latency_ms=elapsed_ms,
        model=params["model"],
    )
    return result
