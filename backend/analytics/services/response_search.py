from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import time
import html
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional, Tuple
from urllib.parse import urlparse
from types import SimpleNamespace
from google import genai as google_genai
from google.genai import types as genai_types

from analytics.core.telemetry import gemini_call

logger = logging.getLogger(__name__)

_DEFAULT_MODEL = os.getenv('GEMINI_SEARCH_MODEL', 'gemini-2.5-flash-lite')
_MAX_SNIPPETS = int(os.getenv('WEB_SEARCH_MAX_SNIPPETS', '5'))
_MAX_TOPICS = int(os.getenv('WEB_SEARCH_MAX_TOPICS', '2'))
_MAX_ATTEMPTS = int(os.getenv('WEB_SEARCH_RETRY_ATTEMPTS', '2'))
_RETRY_BASE_DELAY = float(os.getenv('WEB_SEARCH_RETRY_BASE_DELAY', '0.6'))
_DEFAULT_TEMPERATURE = float(os.getenv('GEMINI_SEARCH_TEMPERATURE', '0.2'))
_MAX_TOKENS = int(os.getenv('GEMINI_SEARCH_MAX_TOKENS', '1024'))

_genai_configured = False
_model: Optional["GenerativeModel"] = None
_model_name: Optional[str] = None

SEARCH_API_ENV_VARS = ("GOOGLE_API_KEY", "GEMINI_API_KEY", "GEMIN_API_KEY")

_ANCHOR_TAG_RE = re.compile(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', re.IGNORECASE)


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
class SearchTopicPlan:
    label: str
    query: str
    reason: Optional[str] = None


@dataclass
class TopicSearchResult(SearchTopicPlan):
    summary: Optional[str] = None
    snippets: List[SearchSnippet] = field(default_factory=list)
    search_id: Optional[str] = None
    latency_ms: Optional[int] = None


@dataclass
class ResponseSearchResult:
    query: str
    search_topic: Optional[str] = None
    search_topics: List[str] = field(default_factory=list)
    search_id: Optional[str] = None
    summary: Optional[str] = None
    snippets: List[SearchSnippet] = field(default_factory=list)
    annotations: List[Dict[str, Any]] = field(default_factory=list)
    topics: List[TopicSearchResult] = field(default_factory=list)
    usage: Optional[Dict[str, Any]] = None
    fetched_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    latency_ms: Optional[int] = None
    model: Optional[str] = None
    from_cache: bool = False

    def to_payload(self) -> Dict[str, Any]:
        payload = {
            'query': self.query,
            'search_topic': self.search_topic,
            'search_topics': self.search_topics,
            'search_id': self.search_id,
            'summary': self.summary,
            'snippets': [asdict(snippet) for snippet in self.snippets][: _MAX_SNIPPETS],
            'annotations': self.annotations,
            'topics': [asdict(topic) for topic in self.topics],
            'usage': self.usage,
            'fetched_at': self.fetched_at,
            'latency_ms': self.latency_ms,
            'model': self.model,
            'from_cache': self.from_cache,
        }
        return payload


def _resolve_search_api_key() -> Optional[str]:
    """Find a configured API key env var without logging secrets.

    Returns the value but also emits a DEBUG log indicating which env var
    provided the key (never logs the key itself). This helps operators quickly
    identify misconfiguration at runtime.
    """
    for name in SEARCH_API_ENV_VARS:
        value = os.getenv(name)
        if value:
            logger.debug("ResponseSearch using API key from %s", name)
            return value
    logger.debug("ResponseSearch no API key env var found among %s", ", ".join(SEARCH_API_ENV_VARS))
    return None


def has_search_api_key() -> bool:
    return _resolve_search_api_key() is not None


def _ensure_model(preferred_model: Optional[str] = None) -> "GenerativeModel":
    global _genai_configured, _model, _model_name
    target_model = (preferred_model or '').strip() or _DEFAULT_MODEL
    if _model is not None and _model_name == target_model:
        logger.debug(
            "ResponseSearch reusing existing Gemini model: %s",
            getattr(_model, 'model_name', target_model),
        )
        return _model

    api_key = _resolve_search_api_key()
    if not api_key:
        raise ResponseSearchError(
            'GOOGLE_API_KEY or GEMINI_API_KEY must be configured for Gemini search',
            stage='configuration',
        )

    if not _genai_configured:
        genai.configure(api_key=api_key)
        _genai_configured = True
        logger.info(
            'ResponseSearch configured Gemini SDK (model=%s)',
            target_model,
            extra={'step': 'response_search.config', 'model': target_model},
        )

    generation_config = {
        'temperature': _DEFAULT_TEMPERATURE,
        'top_p': 0.9,
        'top_k': 32,
        'max_output_tokens': _MAX_TOKENS,
    }

    _model = genai.GenerativeModel(
        model_name=target_model,
        generation_config=generation_config,
    )
    _model_name = target_model
    logger.debug(
        'ResponseSearch created GenerativeModel %s with config: temp=%s, top_p=%s, top_k=%s, max_tokens=%s',
        target_model,
        generation_config.get('temperature'),
        generation_config.get('top_p'),
        generation_config.get('top_k'),
        generation_config.get('max_output_tokens'),
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
    for candidate_idx, candidate in enumerate(response_dict.get('candidates') or []):
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


def _clean_html_text(value: Any) -> str:
    if not isinstance(value, str):
        return ''
    stripped = re.sub('<[^>]+>', '', value)
    return html.unescape(stripped).strip()


# --- Inline minimal google-genai wrapper (keeps test monkeypatching stable) ---
_client: Optional[google_genai.Client] = None


def _ensure_client() -> google_genai.Client:
    global _client
    if _client is None:
        _client = google_genai.Client()
    return _client


def configure(*, api_key: str) -> None:
    global _client
    _client = google_genai.Client(api_key=api_key)


class GenerativeModel:
    def __init__(self, model_name: str, generation_config: Optional[Dict[str, Any]] = None) -> None:
        self.model_name = model_name
        self._gen_cfg = dict(generation_config or {})

    def generate_content(self, *, contents: Any, tools: Optional[List[Dict[str, Any]]] = None, **_: Any) -> Dict[str, Any]:
        client = _ensure_client()
        # Map tools to new SDK tool objects (google_search only for Gemini 2.x)
        tool_objs: Optional[List[genai_types.Tool]] = None
        if tools:
            for item in tools:
                if not isinstance(item, dict):
                    continue
                if "google_search" in item:
                    tool_objs = tool_objs or []
                    tool_objs.append(genai_types.Tool(google_search=genai_types.GoogleSearch()))
        cfg_dict = dict(self._gen_cfg)
        if tool_objs is not None:
            cfg_dict["tools"] = tool_objs
        config = genai_types.GenerateContentConfig(**cfg_dict) if cfg_dict else None

        # Coerce contents to list[str]
        content_list: List[str] = []
        if isinstance(contents, str):
            content_list = [contents]
        elif isinstance(contents, list):
            for entry in contents:
                if isinstance(entry, dict) and "parts" in entry:
                    for p in entry.get("parts") or []:
                        text = p.get("text") if isinstance(p, dict) else None
                        if isinstance(text, str):
                            content_list.append(text)
                elif isinstance(entry, str):
                    content_list.append(entry)
        else:
            content_list = [str(contents)]

        resp = client.models.generate_content(model=self.model_name, contents=content_list, config=config)
        # Convert to plain dict similar to old SDK
        for attr in ("to_dict", "model_dump"):
            fn = getattr(resp, attr, None)
            if callable(fn):
                try:
                    data = fn()
                    if isinstance(data, dict):
                        return data
                except Exception:
                    pass
        text = getattr(resp, "text", None)
        return {"text": text} if isinstance(text, str) else {}


# Expose a module-like object for tests to monkeypatch
genai = SimpleNamespace(configure=configure, GenerativeModel=GenerativeModel)

async def _generate_search_topics(
    model: "GenerativeModel",
    query: str,
    *,
    session_id: Optional[str] = None,
    min_topics: int = 2,
) -> List[SearchTopicPlan]:
    prompt_text = (
        "You are a senior financial researcher. Break the user's request into at least two focused web searches."
        " Always include: (1) a question targeting the specific company/ticker news and (2) a question providing broader industry or regulatory context."
        " Respond as JSON with a 'topics' array. Each topic must include 'label', 'query', and 'reason'."
        " Keep queries under 90 characters and avoid quotation marks or boolean operators."
        f"\nUser question: {query.strip()}"
    )
    prompt = [
        {
            'parts': [
                {'text': prompt_text}
            ]
        }
    ]
    try:
        response = await asyncio.to_thread(
            model.generate_content,
            contents=prompt,
        )
        raw_text = _extract_primary_text(_as_dict(response))
        data = json.loads(raw_text) if raw_text else {}
        topic_items = data.get('topics') if isinstance(data, dict) else None
    except Exception as exc:
        logger.debug("ResponseSearch topic plan generation failed: %s", exc)
        topic_items = None

    plans: List[SearchTopicPlan] = []
    if isinstance(topic_items, list):
        for item in topic_items:
            entry = _as_dict(item)
            query_value = _sanitize_search_query(entry.get('query'), query)
            if not query_value:
                continue
            label = (entry.get('label') or 'Research focus').strip()
            reason = (entry.get('reason') or '').strip() or None
            plans.append(SearchTopicPlan(label=label, query=query_value, reason=reason))

    if not plans:
        primary = _sanitize_search_query(query, query)
        plans.append(SearchTopicPlan(label='Primary question', query=primary))

    if len(plans) < max(1, min_topics):
        primary_query = plans[0].query
        background_seed = primary_query.split()[0] if primary_query else query.split()[0]
        background_query = f"{background_seed} semiconductor industry outlook 2025" if background_seed else f"{query} industry outlook"
        background = _sanitize_search_query(background_query, background_query)
        if background.lower() != plans[0].query.lower():
            plans.append(SearchTopicPlan(label='Industry context', query=background, reason='Provide wider sector context'))

    deduped: List[SearchTopicPlan] = []
    seen = set()
    for plan in plans:
        key = plan.query.lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(plan)

    max_topics = max(1, min_topics, _MAX_TOPICS)
    return deduped[:max_topics]


async def _generate_search_topic(
    model: GenerativeModel,
    query: str,
    *,
    session_id: Optional[str] = None,
) -> str:
    topics = await _generate_search_topics(model, query, session_id=session_id, min_topics=1)
    if topics:
        return topics[0].query
    return _sanitize_search_query(query, query)



async def generate_search_topic(query: str, *, session_id: Optional[str] = None) -> str:
    """Public helper to compute the search topic without executing search.

    Used by flows to emit the 'question' step before the web call.
    """
    gemini_model = _ensure_model()
    return await _generate_search_topic(gemini_model, query, session_id=session_id)


def _extract_support_text(support: Dict[str, Any], chunk_map: Dict[int, Dict[str, Any]]) -> Optional[str]:
    # Prefer new API: text lives on the support.segment
    segment = _as_dict(support.get('segment'))
    seg_text = segment.get('text') if isinstance(segment, dict) else None
    if isinstance(seg_text, str) and seg_text.strip():
        return seg_text.strip()

    # Back-compat: gather chunk text via indices if present
    index_fields = (
        'groundingChunkIndices',  # preferred in 2.x
        'chunk_indices', 'grounding_chunk_indices', 'supportChunkIndices',
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


def _extract_web_metadata(*objects: Any) -> Tuple[Optional[str], Optional[str], Optional[str], Optional[str]]:
    url: Optional[str] = None
    title: Optional[str] = None
    display: Optional[str] = None
    published: Optional[str] = None

    def _visit(data: Dict[str, Any]) -> None:
        nonlocal url, title, display, published
        if not data:
            return
        web_info = _as_dict(data.get('web'))
        candidates = [data]
        for key in ('source', 'primarySource', 'document', 'webSource', 'snippetSource'):
            nested = _as_dict(data.get(key))
            if nested:
                candidates.append(nested)
        if web_info:
            candidates.append(web_info)
        for item in candidates:
            if not item:
                continue
            if url is None:
                url = _first_str(
                    item.get('uri'),
                    item.get('url'),
                    item.get('link'),
                    item.get('sourceUri'),
                    item.get('sourceUrl'),
                    item.get('source_uri'),
                    item.get('source_url'),
                )
            if title is None:
                title = _first_str(
                    item.get('title'),
                    item.get('headline'),
                    item.get('name'),
                    item.get('label'),
                    item.get('sourceTitle'),
                )
            if display is None:
                display = _first_str(
                    item.get('displayUri'),
                    item.get('displayUrl'),
                    item.get('display'),
                    item.get('site'),
                    item.get('siteName'),
                    item.get('publisher'),
                    item.get('domain'),
                )
            if published is None:
                published = _first_str(
                    item.get('published_at'),
                    item.get('publishedAt'),
                    item.get('publishTime'),
                    item.get('publishedDate'),
                    item.get('date'),
                    item.get('timestamp'),
                )
        if display is None and url:
            display = url

    for obj in objects:
        data = _as_dict(obj)
        _visit(data)

    return url, title, display, published


def _collect_search_grounding_snippets(meta: Dict[str, Any], annotations: List[Dict[str, Any]]) -> List[SearchSnippet]:
    snippets: List[SearchSnippet] = []
    search_grounding = (
        _as_dict(meta.get('searchGrounding'))
        or _as_dict(meta.get('search_grounding'))
    )
    if not search_grounding:
        return snippets

    entries = search_grounding.get('searchEntries') or search_grounding.get('search_entries') or []
    if not isinstance(entries, list):
        return snippets

    for entry in entries:
        entry_dict = _as_dict(entry)
        if not entry_dict:
            continue
        annotations.append(entry_dict)
        chunk_snippets = entry_dict.get('chunkSnippets') or entry_dict.get('chunk_snippets') or []
        if isinstance(chunk_snippets, list) and chunk_snippets:
            for chunk in chunk_snippets:
                chunk_dict = _as_dict(chunk)
                if not chunk_dict:
                    continue
                segment = _as_dict(chunk_dict.get('segment'))
                snippet_text = _first_str(
                    chunk_dict.get('text'),
                    chunk_dict.get('snippet'),
                    chunk_dict.get('content'),
                    segment.get('text') if segment else None,
                    segment.get('snippet') if segment else None,
                )
                if snippet_text:
                    snippet_text = snippet_text.strip()
                if not snippet_text:
                    continue
                url, title, display, published = _extract_web_metadata(
                    chunk_dict,
                    chunk_dict.get('source'),
                    entry_dict,
                    entry_dict.get('source'),
                    entry_dict.get('document'),
                )
                snippets.append(
                    SearchSnippet(
                        title=title,
                        url=url,
                        snippet=snippet_text,
                        display_url=display,
                        published_at=published,
                        annotation={
                            'entry_id': entry_dict.get('id'),
                            'chunk_snippet': chunk_dict,
                        },
                    )
                )
        else:
            snippet_text = _first_str(
                entry_dict.get('summary'),
                entry_dict.get('snippet'),
                entry_dict.get('text'),
            )
            if snippet_text:
                snippet_text = snippet_text.strip()
            if not snippet_text:
                continue
            url, title, display, published = _extract_web_metadata(entry_dict, entry_dict.get('source'))
            snippets.append(
                SearchSnippet(
                    title=title,
                    url=url,
                    snippet=snippet_text,
                    display_url=display,
                    published_at=published,
                    annotation={'entry': entry_dict},
                )
            )

    return snippets



def _collect_grounding_data(response_dict: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], List[SearchSnippet]]:
    annotations: List[Dict[str, Any]] = []
    snippets: List[SearchSnippet] = []
    for candidate_idx, candidate in enumerate(response_dict.get('candidates') or []):
        candidate_dict = _as_dict(candidate)
        if not candidate_dict:
            continue

        meta = (
            _as_dict(candidate_dict.get('groundingMetadata'))
            or _as_dict(candidate_dict.get('grounding_metadata'))
            or _as_dict(candidate_dict.get('grounding'))
        )
        candidate_label = _first_str(
            candidate_dict.get('id'),
            candidate_dict.get('response_id'),
            candidate_dict.get('candidate_id'),
        ) or str(candidate_idx)

        if not meta:
            logger.debug(
                'ResponseSearch candidate %s missing grounding metadata; keys=%s',
                candidate_label,
                list(candidate_dict.keys()),
            )
            continue

        chunk_map: Dict[int, Dict[str, Any]] = {}
        chunks = (
            meta.get('groundingChunks')
            or meta.get('grounding_chunks')
            or meta.get('chunks')
            or []
        )
        if isinstance(chunks, list):
            for idx, chunk in enumerate(chunks):
                chunk_map[idx] = _as_dict(chunk)
        chunk_count = len(chunk_map)

        supports = (
            meta.get('groundingSupports')
            or meta.get('grounding_supports')
            or meta.get('supports')
            or meta.get('supportingEvidence')
        )
        support_count = len(supports) if isinstance(supports, list) else 0
        logger.debug(
            'ResponseSearch candidate %s grounding summary: supports=%s, chunks=%s, search_entry_point=%s',
            candidate_label,
            support_count,
            chunk_count,
            bool(meta.get('search_entry_point') or meta.get('searchEntryPoint')),
        )

        before_topic_snippets = len(snippets)
        if isinstance(supports, list):
            for support in supports:
                support_dict = _as_dict(support)
                if not support_dict:
                    continue

                annotations.append(support_dict)
                snippet_text = _extract_support_text(support_dict, chunk_map)

                idxs = (
                    support_dict.get('groundingChunkIndices')
                    or support_dict.get('grounding_chunk_indices')
                    or support_dict.get('chunk_indices')
                    or support_dict.get('supportChunkIndices')
                    or []
                )
                first_uri: Optional[str] = None
                first_title: Optional[str] = None
                first_display: Optional[str] = None
                if isinstance(idxs, list):
                    for raw in idxs:
                        try:
                            i = int(raw)
                        except (TypeError, ValueError):
                            continue
                        chunk = _as_dict(chunk_map.get(i) or {})
                        web_info = _as_dict(chunk.get('web')) if chunk else {}
                        if web_info and not first_uri:
                            first_uri = _first_str(web_info.get('uri'), web_info.get('url'), web_info.get('link'))
                            first_title = _first_str(web_info.get('title'), web_info.get('headline'))
                            first_display = _first_str(web_info.get('displayUri'), web_info.get('displayUrl'), first_uri)

                url = first_uri or _first_str(support_dict.get('url'), support_dict.get('uri'))
                title = first_title or _first_str(support_dict.get('title'))
                display_url = first_display or url

                published_at = _first_str(support_dict.get('published_at'))
                if not published_at and isinstance(idxs, list):
                    for raw in idxs:
                        try:
                            i = int(raw)
                        except (TypeError, ValueError):
                            continue
                        web_info = _as_dict(_as_dict(chunk_map.get(i) or {}).get('web'))
                        published_at = _first_str(web_info.get('publishedDate'), web_info.get('date'))
                        if published_at:
                            break

                snippet_value = snippet_text.strip() if isinstance(snippet_text, str) else None
                if snippet_value is None:
                    raw_snippet = support_dict.get('snippet')
                    snippet_value = raw_snippet.strip() if isinstance(raw_snippet, str) and raw_snippet.strip() else None
                    if snippet_value is None:
                        logger.debug(
                            'ResponseSearch support missing snippet text; candidate=%s indices=%s keys=%s',
                            candidate_label,
                            idxs,
                            list(support_dict.keys()),
                        )

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
        else:
            logger.debug(
                'ResponseSearch candidate %s has non-list supports payload (type=%s)',
                candidate_label,
                type(supports).__name__,
            )

        search_snippets = _collect_search_grounding_snippets(meta, annotations)
        if search_snippets:
            snippets.extend(search_snippets)

        if len(snippets) == before_topic_snippets:
            logger.debug('ResponseSearch candidate %s produced no grounded snippets after parsing supports/searchGrounding', candidate_label)
            search_entry = _as_dict(meta.get('search_entry_point') or meta.get('searchEntryPoint'))
            html_content = _first_str(search_entry.get('rendered_content'), search_entry.get('renderedContent'))
            if isinstance(html_content, str) and html_content.strip():
                for href, label in _ANCHOR_TAG_RE.findall(html_content):
                    url_candidate = href.strip()
                    if not url_candidate:
                        continue
                    clean_label = _clean_html_text(label) or url_candidate
                    display_host = urlparse(url_candidate).netloc or url_candidate
                    snippets.append(
                        SearchSnippet(
                            title=clean_label,
                            url=url_candidate,
                            snippet=None,
                            display_url=display_host,
                            published_at=None,
                            annotation={'anchor': label},
                        )
                    )

    for cite in response_dict.get('citations') or []:
        citation = _as_dict(cite)
        uri = _first_str(citation.get('uri'), citation.get('url'))
        if uri:
            snippets.append(
                SearchSnippet(
                    title=citation.get('title'),
                    url=uri,
                    snippet=citation.get('snippet'),
                    display_url=uri,
                    annotation=citation,
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
        'You are a financial research assistant. You MUST use google_search and ground every statement in returned sources. If no sources are found, reply: "no sources found" and stop.',
        'Prioritize sources published within the past 30 days and focus on companies or tickers mentioned by the user.',
        'Provide a concise summary (<=80 words) that cites the returned references (e.g. [1]) and highlight why each item matters for the user question.',
        f'Search focus: {search_query.strip()}.',
    ]
    return ["\n".join(lines)]


def _build_request_args(search_query: str) -> Dict[str, Any]:
    prompt = _build_prompt(search_query)
    tools = [{ 'google_search': {} }]
    return {
        'contents': prompt,
        'tools': tools,
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
    search_topic: Optional[str] = None,
) -> ResponseSearchResult:
    if not query or not query.strip():
        raise ValueError('Search query must be provided')

    normalized_query = query.strip()
    logger.info(
        'Starting response search',
        extra={'query': normalized_query, 'session_id': session_id, 'context': context},
    )

    gemini_model = _ensure_model(model)
    logger.debug('Resolved Gemini search model: %s', getattr(gemini_model, 'model_name', _DEFAULT_MODEL))

    plans: List[SearchTopicPlan] = []
    if search_topic and isinstance(search_topic, str) and search_topic.strip():
        plans.append(SearchTopicPlan(label='Primary question', query=_sanitize_search_query(search_topic, search_topic)))
    generated_plans = await _generate_search_topics(gemini_model, query, session_id=session_id, min_topics=2)
    for candidate_plan in generated_plans:
        if all(candidate_plan.query.lower() != existing.query.lower() for existing in plans):
            plans.append(candidate_plan)
    if not plans:
        plans.append(SearchTopicPlan(label='Primary question', query=_sanitize_search_query(query, query)))
    plans = plans[: max(1, _MAX_TOPICS)]

    logger.info('Generated search topics %s', [plan.query for plan in plans])
    logger.info(
        'ResponseSearch Step 1: chat rewrite',
        extra={
            'step': 'response_search.step1',
            'phase': 'chat',
            'query': normalized_query,
            'search_topics': [plan.query for plan in plans],
            'session_id': session_id,
        },
    )

    attempts = max(1, _MAX_ATTEMPTS)
    aggregated_annotations: List[Dict[str, Any]] = []
    aggregated_snippets: List[SearchSnippet] = []
    topic_results: List[TopicSearchResult] = []
    summary_sections: List[str] = []
    total_latency = 0
    last_usage: Optional[Dict[str, Any]] = None

    for plan in plans:
        request_args = _build_request_args(plan.query)
        try:
            preview_prompt = request_args.get('contents', [None])[0]
            if isinstance(preview_prompt, str):
                preview = (preview_prompt[:200] + '...') if len(preview_prompt) > 200 else preview_prompt
            elif isinstance(preview_prompt, dict):
                preview_text = _first_str(preview_prompt.get('text'), '') or str(preview_prompt)[:200]
                preview = (preview_text[:200] + '...') if len(preview_text) > 200 else preview_text
            else:
                preview = str(preview_prompt)
            logger.debug(
                "ResponseSearch request args built: has_tools=%s, prompt_preview='%s'",
                bool(request_args.get('tools')),
                preview,
            )
        except Exception:
            logger.debug("ResponseSearch unable to preview request args")

        attempt = 0
        last_error: Optional[Exception] = None
        response_dict: Dict[str, Any] = {}
        elapsed_ms: Optional[int] = None

        while attempt < attempts:
            attempt += 1
            start_time = time.perf_counter()
            logger.debug('Gemini search attempt %s/%s for topic %s', attempt, attempts, plan.query)
            try:
                response = await asyncio.to_thread(
                    gemini_model.generate_content,
                    **request_args,
                )
                elapsed_ms = int((time.perf_counter() - start_time) * 1000)
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
                        'search_query': plan.query,
                    },
                )
                logger.info('Gemini search succeeded in %s ms on attempt %s', elapsed_ms, attempt)
                break
            except Exception as exc:
                elapsed_ms = int((time.perf_counter() - start_time) * 1000)
                last_error = exc
                logger.warning(
                    'Gemini search attempt %s failed: %s (%s) in %sms',
                    attempt,
                    exc,
                    type(exc).__name__,
                    elapsed_ms,
                )
                gemini_call(
                    operation='google_search',
                    model=gemini_model.model_name,
                    duration_ms=elapsed_ms,
                    status='error',
                    session_id=session_id,
                    error=str(exc),
                    metadata={'attempt': attempt, 'search_query': plan.query},
                )
                if attempt >= attempts:
                    logger.error('Gemini Google Search failed after %s attempts (last_error=%s)', attempts, type(exc).__name__)
                    raise ResponseSearchError('Gemini Google Search failed', stage='search_execution') from exc
                delay = _RETRY_BASE_DELAY * (2 ** (attempt - 1))
                logger.debug('Retrying Gemini search in %.2f seconds', delay)
                await asyncio.sleep(delay)

        if not response_dict:
            raise ResponseSearchError(last_error or 'Gemini Google Search produced no output', stage='search_execution')

        last_usage = response_dict.get('usage')
        topic_summary: Optional[str] = None
        raw_text = response_dict.get('text')
        if isinstance(raw_text, str) and raw_text.strip():
            topic_summary = raw_text.strip()
        else:
            candidate_texts = _collect_candidate_texts(response_dict)
            if candidate_texts:
                topic_summary = '\n'.join(candidate_texts).strip()

        topic_annotations, topic_snippets = _collect_grounding_data(response_dict)
        topic_support_count = len(topic_annotations)
        first_snippet = topic_snippets[0] if topic_snippets else None
        logger.info(
            'ResponseSearch topic result',
            extra={
                'step': 'response_search.topic',
                'phase': 'search',
                'session_id': session_id,
                'topic_label': plan.label,
                'topic_query': plan.query,
                'snippets': len(topic_snippets),
                'supports': topic_support_count,
                'summary_present': bool(topic_summary),
                'latency_ms': elapsed_ms,
                'first_snippet_title': getattr(first_snippet, 'title', None),
                'first_snippet_url': getattr(first_snippet, 'url', None),
            },
        )

        if topic_snippets:
            first_snippet_preview = topic_snippets[0].snippet or topic_snippets[0].title or topic_snippets[0].display_url
            if isinstance(first_snippet_preview, str) and first_snippet_preview.strip():
                preview = first_snippet_preview.strip()
                if len(preview) > 200:
                    preview = preview[:197].rstrip() + '...'
                logger.debug(
                    "ResponseSearch topic '%s' first snippet preview: %s",
                    plan.query,
                    preview,
                )
        if not topic_snippets:
            logger.info(
                "ResponseSearch returned no grounded snippets for topic '%s'; response_id=%s",
                plan.query,
                response_dict.get('response_id') or response_dict.get('id'),
            )
        aggregated_annotations.extend(topic_annotations)
        aggregated_snippets.extend(topic_snippets)

        topic_result = TopicSearchResult(
            label=plan.label,
            query=plan.query,
            reason=plan.reason,
            summary=topic_summary,
            snippets=topic_snippets,
            search_id=response_dict.get('response_id') or response_dict.get('id'),
            latency_ms=elapsed_ms,
        )
        topic_results.append(topic_result)

        if topic_summary:
            summary_sections.append(f"{plan.label}: {topic_summary}")
        if elapsed_ms:
            total_latency += elapsed_ms

    combined_snippets = _dedupe_snippets(aggregated_snippets)
    summary_text = '\n\n'.join(summary_sections) if summary_sections else None

    if not combined_snippets:
        logger.info(
            "ResponseSearch produced no grounded snippets across topics; queries=%s",
            [plan.query for plan in plans],
        )

    result = ResponseSearchResult(
        query=query,
        search_topic=plans[0].query if plans else None,
        search_topics=[plan.query for plan in plans],
        search_id=topic_results[0].search_id if topic_results else None,
        summary=summary_text,
        snippets=combined_snippets[: _MAX_SNIPPETS],
        annotations=aggregated_annotations,
        topics=topic_results,
        usage=last_usage,
        fetched_at=datetime.utcnow().isoformat(),
        latency_ms=total_latency or None,
        model=getattr(gemini_model, 'model_name', model or _DEFAULT_MODEL),
    )

    logger.info('Response search produced %s snippets (summary=%s) for query %s', len(result.snippets), bool(result.summary), normalized_query)
    logger.info(
        'ResponseSearch Step 2: search result',
        extra={
            'step': 'response_search.step2',
            'phase': 'search',
            'query': normalized_query,
            'search_topics': [plan.query for plan in plans],
            'session_id': session_id,
            'topic_count': len(topic_results),
            'snippets': len(result.snippets),
            'summary_present': bool(result.summary),
            'latency_ms': result.latency_ms,
            'topics_overview': '; '.join(f"{topic.label}:{len(topic.snippets)}" for topic in topic_results),
            'first_snippet_title': result.snippets[0].title if result.snippets else None,
            'first_snippet_url': result.snippets[0].url if result.snippets else None,
        },
    )
    return result







