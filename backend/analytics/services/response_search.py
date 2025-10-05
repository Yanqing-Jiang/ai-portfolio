from __future__ import annotations

import asyncio
import logging
import os
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional, Tuple

import google.generativeai as genai

from analytics.core.telemetry import gemini_call

logger = logging.getLogger(__name__)

_DEFAULT_MODEL = os.getenv('GEMINI_SEARCH_MODEL', 'gemini-2.5-flash')
_MAX_SNIPPETS = int(os.getenv('WEB_SEARCH_MAX_SNIPPETS', '5'))
_MAX_ATTEMPTS = int(os.getenv('WEB_SEARCH_RETRY_ATTEMPTS', '2'))
_RETRY_BASE_DELAY = float(os.getenv('WEB_SEARCH_RETRY_BASE_DELAY', '0.6'))
_DEFAULT_TEMPERATURE = float(os.getenv('GEMINI_SEARCH_TEMPERATURE', '0.2'))
_MAX_TOKENS = int(os.getenv('GEMINI_SEARCH_MAX_TOKENS', '1024'))

_genai_configured = False
_model: Optional[genai.GenerativeModel] = None

SEARCH_API_ENV_VARS = ("GOOGLE_API_KEY", "GEMINI_API_KEY", "GEMIN_API_KEY")


class ResponseSearchError(RuntimeError):
    def __init__(self, message: str, *, stage: str = "unknown") -> None:
        super().__init__(message)
        self.stage = stage

    '''Raised when the Gemini-powered web search call fails.'''


@dataclass
class SearchSnippet:
    '''Structured snippet returned to analytics flows.'''

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
            'query': self.query,
            'search_id': self.search_id,
            'summary': self.summary,
            'snippets': [asdict(snippet) for snippet in self.snippets][: _MAX_SNIPPETS],
            'annotations': self.annotations,
            'usage': self.usage,
            'fetched_at': self.fetched_at,
            'latency_ms': self.latency_ms,
            'model': self.model,
            'from_cache': self.from_cache,
        }
        return payload


def _resolve_search_api_key() -> Optional[str]:
    for name in SEARCH_API_ENV_VARS:
        value = os.getenv(name)
        if value:
            return value
    return None


def has_search_api_key() -> bool:
    return _resolve_search_api_key() is not None


def _ensure_model() -> genai.GenerativeModel:
    global _genai_configured, _model
    if _model is not None:
        return _model

    api_key = _resolve_search_api_key()
    if not api_key:
        raise ResponseSearchError('GOOGLE_API_KEY or GEMINI_API_KEY must be configured for Gemini search', stage='configuration')

    if not _genai_configured:
        genai.configure(api_key=api_key)
        _genai_configured = True

    generation_config = {
        'temperature': _DEFAULT_TEMPERATURE,
        'top_p': 0.9,
        'top_k': 32,
        'max_output_tokens': _MAX_TOKENS,
    }

    _model = genai.GenerativeModel(
        model_name=_DEFAULT_MODEL,
        generation_config=generation_config,
    )
    return _model


def _first_str(*values: Any) -> Optional[str]:
    for value in values:
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _as_dict(obj: Any) -> Dict[str, Any]:
    if obj is None:
        return {}
    if isinstance(obj, dict):
        return obj
    for attr in ('to_dict', 'model_dump', 'dict'):
        if hasattr(obj, attr):
            try:
                data = getattr(obj, attr)()
                if isinstance(data, dict):
                    return data
            except Exception:
                continue
    return {}


def _collect_candidate_texts(response_dict: Dict[str, Any]) -> List[str]:
    texts: List[str] = []
    for candidate in response_dict.get('candidates') or []:
        if not isinstance(candidate, dict):
            continue
        content = candidate.get('content')
        if isinstance(content, dict):
            for part in content.get('parts') or []:
                if isinstance(part, dict):
                    text = part.get('text')
                    if isinstance(text, str) and text.strip():
                        texts.append(text.strip())
        text_field = candidate.get('text')
        if isinstance(text_field, str) and text_field.strip():
            texts.append(text_field.strip())
    return texts


def _extract_primary_text(response_dict: Dict[str, Any]) -> str:
    raw_text = response_dict.get('text')
    if isinstance(raw_text, str) and raw_text.strip():
        return raw_text.strip()
    candidate_texts = _collect_candidate_texts(response_dict)
    if candidate_texts:
        return candidate_texts[0].strip()
    return ''


def _sanitize_search_query(text: str, fallback: str) -> str:
    if not isinstance(text, str):
        return fallback
    cleaned = text.strip().replace('"', '').replace('`', '')
    cleaned = cleaned.splitlines()[0].strip() if cleaned else ''
    return cleaned or fallback


async def _generate_search_topic(
    model: genai.GenerativeModel,
    query: str,
    *,
    session_id: Optional[str] = None,
) -> str:
    prompt = [
        {
            'parts': [
                {
                    'text': (
                        'You rewrite investor questions into a single concise web search query that surfaces the latest context needed to answer. Output only the search query without quotes.\n'
                        f'User question: {query.strip()}\n'
                    )
                }
            ]
        }
    ]
    start = time.perf_counter()
    try:
        response = await asyncio.to_thread(
            model.generate_content,
            contents=prompt,
        )
        elapsed_ms = int((time.perf_counter() - start) * 1000)
        response_dict = _as_dict(response)
        gemini_call(
            operation='search_query',
            model=model.model_name,
            duration_ms=elapsed_ms,
            status='success',
            session_id=session_id,
        )
        generated = _extract_primary_text(response_dict)
    except Exception as exc:
        elapsed_ms = int((time.perf_counter() - start) * 1000)
        gemini_call(
            operation='search_query',
            model=getattr(model, 'model_name', None),
            duration_ms=elapsed_ms,
            status='error',
            session_id=session_id,
            error=str(exc),
        )
        return query
    return _sanitize_search_query(generated, query)


def _extract_support_text(support: Dict[str, Any], chunk_map: Dict[int, Dict[str, Any]]) -> Optional[str]:
    index_fields = (
        'chunk_indices',
        'groundingChunkIndices',
        'grounding_chunk_indices',
        'supportChunkIndices',
    )
    indices: Optional[List[Any]] = None
    for key in index_fields:
        value = support.get(key)
        if isinstance(value, list):
            indices = value
            break

    fragments: List[str] = []
    if indices:
        for raw in indices:
            try:
                idx = int(raw)
            except (TypeError, ValueError):
                continue
            chunk = chunk_map.get(idx)
            if not chunk:
                continue
            text = chunk.get('text') or chunk.get('content') or chunk.get('snippet')
            if isinstance(text, str) and text.strip():
                fragments.append(text.strip())

    support_text = support.get('text') or support.get('snippet')
    if not fragments and isinstance(support_text, str) and support_text.strip():
        fragments.append(support_text.strip())

    combined = ' '.join(fragment for fragment in fragments if fragment)
    return combined or None


def _collect_grounding_data(response_dict: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], List[SearchSnippet]]:
    annotations: List[Dict[str, Any]] = []
    snippets: List[SearchSnippet] = []
    for candidate in response_dict.get('candidates') or []:
        if not isinstance(candidate, dict):
            continue
        meta_sources: List[Dict[str, Any]] = []
        chunk_map: Dict[int, Dict[str, Any]] = {}
        for key in ('grounding', 'groundingMetadata'):
            meta = _as_dict(candidate.get(key))
            if not meta:
                continue
            meta_sources.append(meta)
            chunks = meta.get('chunks')
            if chunks is None:
                chunks = meta.get('groundingChunks')
            if isinstance(chunks, list):
                for idx, chunk in enumerate(chunks):
                    chunk_map[idx] = _as_dict(chunk)

        for meta in meta_sources:
            supports = meta.get('supports')
            if supports is None:
                supports = meta.get('supportingEvidence')
            if not isinstance(supports, list):
                continue
            for support in supports:
                support_dict = _as_dict(support)
                if not support_dict:
                    continue
                annotations.append(support_dict)
                snippet_text = _extract_support_text(support_dict, chunk_map)
                web_info = _as_dict(support_dict.get('web'))
                title = _first_str(
                    support_dict.get('title'),
                    web_info.get('title'),
                    web_info.get('headline'),
                )
                url = _first_str(
                    support_dict.get('url'),
                    support_dict.get('uri'),
                    web_info.get('uri'),
                    web_info.get('url'),
                    web_info.get('link'),
                )
                display_url = _first_str(
                    support_dict.get('display_url'),
                    web_info.get('displayUri'),
                    web_info.get('displayUrl'),
                    url,
                )
                published_at = _first_str(
                    support_dict.get('published_at'),
                    web_info.get('publishedDate'),
                    web_info.get('date'),
                )
                snippet_value = snippet_text if isinstance(snippet_text, str) else None
                if snippet_value is None:
                    raw_snippet = support_dict.get('snippet')
                    snippet_value = raw_snippet.strip() if isinstance(raw_snippet, str) else None
                snippets.append(
                    SearchSnippet(
                        title=title,
                        url=url,
                        snippet=snippet_value,
                        display_url=display_url,
                        published_at=published_at,
                        annotation=support_dict,
                    )
                )
    return annotations, snippets


def _dedupe_snippets(snippets: Iterable[SearchSnippet]) -> List[SearchSnippet]:
    seen: Dict[str, SearchSnippet] = {}
    for snippet in snippets:
        if snippet is None:
            continue
        key = (snippet.url or snippet.title or str(len(seen))).lower()
        if key in seen:
            existing = seen[key]
            if not existing.snippet and snippet.snippet:
                existing.snippet = snippet.snippet
            if not existing.title and snippet.title:
                existing.title = snippet.title
            if not existing.display_url and snippet.display_url:
                existing.display_url = snippet.display_url
            if not existing.published_at and snippet.published_at:
                existing.published_at = snippet.published_at
            if not existing.annotation and snippet.annotation:
                existing.annotation = snippet.annotation
        else:
            seen[key] = snippet
    return list(seen.values())


def _build_prompt(search_query: str) -> List[str]:
    lines: List[str] = [
        'You are a financial research assistant. Use google_search to gather breaking developments, regulatory filings, and earnings coverage related to the analytics request.',
        'Prioritize sources published within the past 30 days and focus on companies or tickers mentioned by the user.',
        'Provide a concise summary (<=80 words) that cites the returned references (e.g. [1]) and highlight why each item matters for the user question.',
        f'Search focus: {search_query.strip()}.',
    ]
    return ["\n".join(lines)]


def _build_request_args(search_query: str) -> Dict[str, Any]:
    prompt = _build_prompt(search_query)
    return {
        'contents': prompt,
        'tools': [{
            'google_search_retrieval': {},
        }],
    }


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
        raise ValueError('Search query must be provided')

    normalized_query = query.strip()
    logger.info('Starting response search', extra={'query': normalized_query, 'session_id': session_id})

    gemini_model = _ensure_model()
    logger.debug('Resolved Gemini search model: %s', getattr(gemini_model, 'model_name', _DEFAULT_MODEL))
    try:
        search_query = await _generate_search_topic(
            gemini_model,
            query,
            session_id=session_id,
        )
    except Exception as exc:
        logger.warning("Gemini topic generation failed: %s", exc)
        raise ResponseSearchError(f"Search topic generation failed: {exc}", stage="topic_generation") from exc
    logger.info('Generated search topic %s (from query %s)', search_query, normalized_query)
    logger.info(
        'ResponseSearch Step 1: chat rewrite',
        extra={
            'step': 'response_search.step1',
            'phase': 'chat',
            'query': normalized_query,
            'search_topic': search_query,
            'session_id': session_id,
        },
    )
    request_args = _build_request_args(search_query)

    attempts = max(1, _MAX_ATTEMPTS)
    attempt = 0
    last_error: Optional[Exception] = None
    response_dict: Dict[str, Any] = {}
    elapsed_ms: Optional[int] = None

    while attempt < attempts:
        attempt += 1
        start = time.perf_counter()
        logger.debug('Gemini search attempt %s/%s for topic %s', attempt, attempts, search_query)
        try:
            response = await asyncio.to_thread(
                gemini_model.generate_content,
                **request_args,
            )
            elapsed_ms = int((time.perf_counter() - start) * 1000)
            response_dict = _as_dict(response)
            gemini_call(
                operation='google_search',
                model=gemini_model.model_name,
                duration_ms=elapsed_ms,
                status='success',
                session_id=session_id,
                metadata={
                    'attempt': attempt,
                    'response_id': response_dict.get('response_id') or response_dict.get('id'),
                },
            )
            logger.info('Gemini search succeeded in %s ms on attempt %s', elapsed_ms, attempt)
            break
        except Exception as exc:
            elapsed_ms = int((time.perf_counter() - start) * 1000)
            last_error = exc
            logger.warning('Gemini search attempt %s failed: %s', attempt, exc)
            gemini_call(
                operation='google_search',
                model=gemini_model.model_name,
                duration_ms=elapsed_ms,
                status='error',
                session_id=session_id,
                error=str(exc),
                metadata={'attempt': attempt},
            )
            if attempt >= attempts:
                logger.error('Gemini Google Search failed after %s attempts', attempts)
                raise ResponseSearchError('Gemini Google Search failed', stage='search_execution') from exc
            delay = _RETRY_BASE_DELAY * (2 ** (attempt - 1))
            logger.debug('Retrying Gemini search in %.2f seconds', delay)
            await asyncio.sleep(delay)

    if not response_dict:
        raise ResponseSearchError(str(last_error) if last_error else 'Gemini Google Search produced no output', stage='search_execution')

    summary_text: Optional[str] = None
    raw_text = response_dict.get('text')
    if isinstance(raw_text, str) and raw_text.strip():
        summary_text = raw_text.strip()
    else:
        candidate_texts = _collect_candidate_texts(response_dict)
        if candidate_texts:
            summary_text = '\n'.join(candidate_texts).strip()

    annotations, annotation_snippets = _collect_grounding_data(response_dict)
    combined_snippets = _dedupe_snippets(annotation_snippets)

    result = ResponseSearchResult(
        query=query,
        search_id=response_dict.get('response_id') or response_dict.get('id'),
        summary=summary_text,
        snippets=combined_snippets[:_MAX_SNIPPETS],
        annotations=annotations,
        usage=response_dict.get('usage'),
        fetched_at=datetime.utcnow().isoformat(),
        latency_ms=elapsed_ms,
        model=model or gemini_model.model_name,
    )
    logger.info('Response search produced %s snippets (summary=%s) for query %s', len(result.snippets), bool(result.summary), normalized_query)
    logger.info(
        'ResponseSearch Step 2: search result',
        extra={
            'step': 'response_search.step2',
            'phase': 'search',
            'query': normalized_query,
            'search_topic': search_query,
            'session_id': session_id,
            'snippets': len(result.snippets),
            'summary_present': bool(result.summary),
            'latency_ms': result.latency_ms,
        },
    )
    return result



