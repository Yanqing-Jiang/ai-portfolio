# --- Analytics Function/Class Map ---
# Class: ResponseSearchError
#   Role: Handles ResponseSearchError logic for analytics.services.response_search.
#   Called from: analytics.flows.multi_agent, analytics.flows.planner_executor, analytics.flows.tooling, tests.analytics.test_web_retriever_adapter
#   Collaborators: Internal helpers only
#   Why: Keeps analytics.services.response_search from duplicating ResponseSearchError behavior across flows.
# Class: SearchSnippet
#   Role: Structured snippet returned to analytics flows.
#   Called from: tests.analytics.test_web_research
#   Collaborators: Internal helpers only
#   Why: Supports downstream analytics workflows that rely on SearchSnippet.
# Class: SearchTopicPlan
#   Role: Handles SearchTopicPlan logic for analytics.services.response_search.
#   Called from: analytics.flows.revision_directive, analytics.flows.tooling, tests.analytics.test_response_search, tests.analytics.test_revision_routing, +1 more
#   Collaborators: Internal helpers only
#   Why: Keeps analytics.services.response_search from duplicating SearchTopicPlan behavior across flows.
# Class: TopicSearchResult
#   Role: Handles TopicSearchResult logic for analytics.services.response_search.
#   Called from: tests.analytics.test_web_research
#   Collaborators: dataclasses.field
#   Why: Keeps analytics.services.response_search from duplicating TopicSearchResult behavior across flows.
# Class: ResponseSearchResult
#   Role: Handles ResponseSearchResult logic for analytics.services.response_search.
#   Called from: tests.analytics.test_web_research
#   Collaborators: dataclasses.field, dataclasses.asdict
#   Why: Keeps analytics.services.response_search from duplicating ResponseSearchResult behavior across flows.
# Function: _resolve_search_api_key
#   Role: Find a configured API key env var without logging secrets.
#   Called from: Internal to analytics.services.response_search
#   Invokes: os.getenv
#   Why: Returns the value but also emits a DEBUG log indicating which env var provided the key (never logs the key itself).
# Function: has_search_api_key
#   Role: Handles has search api key logic for analytics.services.response_search.
#   Called from: analytics.flows.planner_executor, analytics.flows.tooling, analytics.flows.workflow
#   Invokes: analytics.services.response_search._resolve_search_api_key
#   Why: Keeps analytics.services.response_search from duplicating has search api key behavior across flows.
# Function: _ensure_google_genai
#   Role: Handles ensure google genai logic for analytics.services.response_search.
#   Called from: Internal to analytics.services.response_search
#   Invokes: analytics.services.response_search.ResponseSearchError
#   Why: Keeps analytics.services.response_search from duplicating ensure google genai behavior across flows.
# Function: _ensure_model
#   Role: Handles ensure model logic for analytics.services.response_search.
#   Called from: Internal to analytics.services.response_search
#   Invokes: analytics.services.response_search._resolve_search_api_key, analytics.services.response_search.ResponseSearchError
#   Why: Keeps analytics.services.response_search from duplicating ensure model behavior across flows.
# Function: _first_str
#   Role: Handles first str logic for analytics.services.response_search.
#   Called from: Internal to analytics.services.response_search
#   Invokes: Internal helpers only
#   Why: Keeps analytics.services.response_search from duplicating first str behavior across flows.
# Function: _as_dict
#   Role: Handles as dict logic for analytics.services.response_search.
#   Called from: Internal to analytics.services.response_search
#   Invokes: Internal helpers only
#   Why: Keeps analytics.services.response_search from duplicating as dict behavior across flows.
# Function: _collect_candidate_texts
#   Role: Handles collect candidate texts logic for analytics.services.response_search.
#   Called from: Internal to analytics.services.response_search
#   Invokes: Internal helpers only
#   Why: Keeps analytics.services.response_search from duplicating collect candidate texts behavior across flows.
# Function: _extract_primary_text
#   Role: Handles extract primary text logic for analytics.services.response_search.
#   Called from: Internal to analytics.services.response_search
#   Invokes: analytics.services.response_search._collect_candidate_texts
#   Why: Keeps analytics.services.response_search from duplicating extract primary text behavior across flows.
# Function: _sanitize_search_query
#   Role: Handles sanitize search query logic for analytics.services.response_search.
#   Called from: Internal to analytics.services.response_search
#   Invokes: Internal helpers only
#   Why: Keeps analytics.services.response_search from duplicating sanitize search query behavior across flows.
# Function: _clean_html_text
#   Role: Handles clean html text logic for analytics.services.response_search.
#   Called from: Internal to analytics.services.response_search
#   Invokes: re.sub, html.unescape
#   Why: Keeps analytics.services.response_search from duplicating clean html text behavior across flows.
# Function: _ensure_client
#   Role: Handles ensure client logic for analytics.services.response_search.
#   Called from: Internal to analytics.services.response_search
#   Invokes: analytics.services.response_search._ensure_google_genai
#   Why: Keeps analytics.services.response_search from duplicating ensure client behavior across flows.
# Function: configure
#   Role: Handles configure logic for analytics.services.response_search.
#   Called from: Internal to analytics.services.response_search
#   Invokes: analytics.services.response_search._ensure_google_genai
#   Why: Keeps analytics.services.response_search from duplicating configure behavior across flows.
# Class: GenerativeModel
#   Role: Handles GenerativeModel logic for analytics.services.response_search.
#   Called from: Internal to analytics.services.response_search
#   Collaborators: analytics.services.response_search._ensure_google_genai, analytics.services.response_search._ensure_client
#   Why: Keeps analytics.services.response_search from duplicating GenerativeModel behavior across flows.
# Function: _generate_search_topics
#   Role: Handles generate search topics logic for analytics.services.response_search.
#   Called from: Internal to analytics.services.response_search
#   Invokes: analytics.services.response_search._extract_primary_text, analytics.services.response_search._sanitize_search_query, asyncio.to_thread, analytics.services.response_search._as_dict, +2 more
#   Why: Keeps analytics.services.response_search from duplicating generate search topics behavior across flows.
# Function: _generate_search_topic
#   Role: Handles generate search topic logic for analytics.services.response_search.
#   Called from: Internal to analytics.services.response_search
#   Invokes: analytics.services.response_search._sanitize_search_query, analytics.services.response_search._generate_search_topics
#   Why: Keeps analytics.services.response_search from duplicating generate search topic behavior across flows.
# Function: generate_search_topic
#   Role: Public helper to compute the search topic without executing search.
#   Called from: analytics.flows.planner_executor
#   Invokes: analytics.services.response_search._ensure_model, analytics.services.response_search._generate_search_topic
#   Why: Used by flows to emit the 'question' step before the web call.
# Function: generate_search_topics
#   Role: Return structured topic prompts without issuing live web calls.
#   Called from: analytics.flows.tooling, analytics.flows.workflow
#   Invokes: analytics.services.response_search._ensure_model, analytics.services.response_search._generate_search_topics
#   Why: Supports downstream analytics workflows that rely on generate_search_topics.
# Function: _extract_support_text
#   Role: Handles extract support text logic for analytics.services.response_search.
#   Called from: Internal to analytics.services.response_search
#   Invokes: analytics.services.response_search._as_dict
#   Why: Keeps analytics.services.response_search from duplicating extract support text behavior across flows.
# Function: _extract_web_metadata
#   Role: Handles extract web metadata logic for analytics.services.response_search.
#   Called from: Internal to analytics.services.response_search
#   Invokes: analytics.services.response_search._as_dict, analytics.services.response_search._first_str
#   Why: Keeps analytics.services.response_search from duplicating extract web metadata behavior across flows.
# Function: _collect_search_grounding_snippets
#   Role: Handles collect search grounding snippets logic for analytics.services.response_search.
#   Called from: Internal to analytics.services.response_search
#   Invokes: analytics.services.response_search._as_dict, analytics.services.response_search._first_str, analytics.services.response_search._extract_web_metadata, analytics.services.response_search.SearchSnippet
#   Why: Keeps analytics.services.response_search from duplicating collect search grounding snippets behavior across flows.
# Function: _collect_grounding_data
#   Role: Handles collect grounding data logic for analytics.services.response_search.
#   Called from: Internal to analytics.services.response_search
#   Invokes: analytics.services.response_search._as_dict, analytics.services.response_search._collect_search_grounding_snippets, analytics.services.response_search._first_str, analytics.services.response_search._extract_support_text, +2 more
#   Why: Keeps analytics.services.response_search from duplicating collect grounding data behavior across flows.
# Function: _dedupe_snippets
#   Role: Handles dedupe snippets logic for analytics.services.response_search.
#   Called from: Internal to analytics.services.response_search
#   Invokes: Internal helpers only
#   Why: Keeps analytics.services.response_search from duplicating dedupe snippets behavior across flows.
# Function: _build_prompt
#   Role: Handles build prompt logic for analytics.services.response_search.
#   Called from: Internal to analytics.services.response_search
#   Invokes: Internal helpers only
#   Why: Keeps analytics.services.response_search from duplicating build prompt behavior across flows.
# Function: _build_request_args
#   Role: Handles build request args logic for analytics.services.response_search.
#   Called from: Internal to analytics.services.response_search
#   Invokes: analytics.services.response_search._build_prompt
#   Why: Keeps analytics.services.response_search from duplicating build request args behavior across flows.
# Function: perform_response_search
#   Role: Handles perform response search logic for analytics.services.response_search.
#   Called from: analytics.flows.multi_agent, analytics.flows.planner_executor, analytics.flows.tooling, tests.analytics.test_response_search
#   Invokes: analytics.services.response_search._ensure_model, analytics.services.response_search._dedupe_snippets, analytics.services.response_search.ResponseSearchResult, analytics.services.response_search._sanitize_search_query, +2 more
#   Why: Keeps analytics.services.response_search from duplicating perform response search behavior across flows.
# --- End Analytics Function/Class Map ---
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
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple, TYPE_CHECKING
from urllib.parse import urlparse
from types import SimpleNamespace

try:  # pragma: no cover - optional dependency
    from google import genai as google_genai  # type: ignore[import]
    from google.genai import types as genai_types  # type: ignore[import]
except ImportError:  # pragma: no cover - dependency is optional in tests
    google_genai = None  # type: ignore[assignment]
    genai_types = None  # type: ignore[assignment]

if TYPE_CHECKING:  # pragma: no cover - typing only
    from google import genai as _google_genai  # type: ignore[import]
    from google.genai import types as _genai_types  # type: ignore[import]
else:  # pragma: no cover - keep runtime lightweight
    _google_genai = Any  # type: ignore[assignment]
    _genai_types = Any  # type: ignore[assignment]

from analytics.core.telemetry import gemini_call
from analytics.core.session_state import SessionStateSnapshot

logger = logging.getLogger(__name__)

_DEFAULT_MODEL = os.getenv('GEMINI_SEARCH_MODEL', 'gemini-2.5-flash-lite')
_MAX_SNIPPETS = int(os.getenv('WEB_SEARCH_MAX_SNIPPETS', '5'))
_MAX_TOPICS = int(os.getenv('WEB_SEARCH_MAX_TOPICS', '2'))
_MAX_ATTEMPTS = int(os.getenv('WEB_SEARCH_RETRY_ATTEMPTS', '2'))
_RETRY_BASE_DELAY = float(os.getenv('WEB_SEARCH_RETRY_BASE_DELAY', '0.6'))
_DEFAULT_TEMPERATURE = float(os.getenv('GEMINI_SEARCH_TEMPERATURE', '0.2'))
_MAX_TOKENS = int(os.getenv('GEMINI_SEARCH_MAX_TOKENS', '1024'))
_REQUEST_TIMEOUT_SECONDS = float(os.getenv('WEB_SEARCH_TIMEOUT_SECONDS', '20'))

_genai_configured = False
_model: Optional["GenerativeModel"] = None
_model_name: Optional[str] = None

SEARCH_API_ENV_VARS = ("GOOGLE_API_KEY", "GEMINI_API_KEY", "GEMIN_API_KEY")

_ANCHOR_TAG_RE = re.compile(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', re.IGNORECASE)


class ResponseSearchError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        stage: str = "unknown",
        retryable: bool = True,
        code: Optional[str] = None,
    ) -> None:
        super().__init__(message)
        self.stage = stage
        self.retryable = retryable
        self.code = code

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
    question_kind: Optional[str] = None


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
    questions: Optional[Dict[str, Any]] = None

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
        if self.questions:
            payload['questions'] = dict(self.questions)
        return payload

    def to_agent_envelope(self, *, status: str = "completed", cached: bool = False) -> Dict[str, Any]:
        snippets_payload = [
            {
                "title": snippet.title,
                "url": snippet.url,
                "summary": snippet.snippet,
                "published_at": snippet.published_at,
            }
            for snippet in self.snippets[:3]
        ]
        topics_payload = [
            {
                "label": topic.label,
                "query": topic.query,
                "summary": topic.summary,
                "snippets": len(topic.snippets),
                "question_kind": topic.question_kind,
            }
            for topic in self.topics
        ]
        return {
            "status": status,
            "query": self.query,
            "summary": self.summary,
            "search_id": self.search_id,
            "model": self.model,
            "latency_ms": self.latency_ms,
            "from_cache": cached or self.from_cache,
            "snippets": snippets_payload,
            "topics": topics_payload,
            "questions": dict(self.questions) if self.questions else None,
        }


@dataclass
class WebResearchQuestionBundle:
    """Structured Gemini metadata for baseline web research prompts."""

    keyword_focus: str
    user_question: str
    industry_question: str
    model: Optional[str] = None
    latency_ms: Optional[int] = None
    generated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    source: str = "gemini"
    fallback_reason: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "keyword_focus": self.keyword_focus,
            "user_question": self.user_question,
            "industry_question": self.industry_question,
            "generated_at": self.generated_at,
            "source": self.source,
        }
        if self.model:
            payload["model"] = self.model
        if self.latency_ms is not None:
            payload["latency_ms"] = self.latency_ms
        if self.fallback_reason:
            payload["fallback_reason"] = self.fallback_reason
        return payload

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "WebResearchQuestionBundle":
        return cls(
            keyword_focus=str(payload.get("keyword_focus") or "").strip(),
            user_question=str(payload.get("user_question") or "").strip(),
            industry_question=str(payload.get("industry_question") or "").strip(),
            model=str(payload.get("model") or "").strip() or None,
            latency_ms=payload.get("latency_ms"),
            generated_at=str(payload.get("generated_at") or datetime.utcnow().isoformat()),
            source=str(payload.get("source") or "gemini"),
            fallback_reason=str(payload.get("fallback_reason") or "").strip() or None,
        )


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


def _ensure_google_genai(stage: str) -> None:
    if google_genai is None or genai_types is None:
        raise ResponseSearchError(
            "google-genai SDK not available; install google-genai to enable response_search integration.",
            stage=stage,
            retryable=False,
            code="sdk_missing",
        )


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
            retryable=False,
            code='configuration_missing',
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
_client: Optional[Any] = None


def _ensure_client() -> Any:
    global _client
    _ensure_google_genai(stage="client_init")
    if _client is None:
        _client = google_genai.Client()
    return _client


def configure(*, api_key: str) -> None:
    global _client
    _ensure_google_genai(stage="client_configure")
    _client = google_genai.Client(api_key=api_key)


class GenerativeModel:
    def __init__(self, model_name: str, generation_config: Optional[Dict[str, Any]] = None) -> None:
        self.model_name = model_name
        self._gen_cfg = dict(generation_config or {})

    def generate_content(self, *, contents: Any, tools: Optional[List[Dict[str, Any]]] = None, **_: Any) -> Dict[str, Any]:
        _ensure_google_genai(stage="generate_content")
        client = _ensure_client()
        # Map tools to new SDK tool objects (google_search only for Gemini 2.x)
        tool_objs: Optional[List[Any]] = None
        if tools and genai_types is not None:
            Tool = getattr(genai_types, "Tool", None)
            GoogleSearch = getattr(genai_types, "GoogleSearch", None)
            for item in tools:
                if not isinstance(item, dict):
                    continue
                if "google_search" in item:
                    tool_objs = tool_objs or []
                    if Tool and GoogleSearch:
                        tool_objs.append(Tool(google_search=GoogleSearch()))
        cfg_dict = dict(self._gen_cfg)
        if tool_objs is not None:
            cfg_dict["tools"] = tool_objs
        config = None
        if cfg_dict and genai_types is not None:
            GenerateContentConfig = getattr(genai_types, "GenerateContentConfig", None)
            if callable(GenerateContentConfig):
                config = GenerateContentConfig(**cfg_dict)

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

    configured_max = max(1, min_topics, _MAX_TOPICS)
    desired_count = min(2, configured_max)
    normalized = _select_primary_and_industry(deduped[:desired_count], original_query=query)
    return normalized[:desired_count]


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


async def build_web_research_questions(
    query: str,
    *,
    snapshot: Optional[SessionStateSnapshot] = None,
    session_id: Optional[str] = None,
    min_topics: int = 2,
) -> Tuple[WebResearchQuestionBundle, List[SearchTopicPlan]]:
    """Return Gemini-derived user + industry web prompts plus sanitized topic plans."""
    normalized_query = (query or getattr(snapshot, "last_query", "") or "").strip()
    if not normalized_query:
        normalized_query = "latest market outlook"
    gemini_model = _ensure_model()
    start = time.perf_counter()
    fallback_reason: Optional[str] = None
    try:
        generated_topics = await _generate_search_topics(
            gemini_model,
            normalized_query,
            session_id=session_id,
            min_topics=max(2, min_topics),
        )
        duration_ms = int((time.perf_counter() - start) * 1000)
        gemini_call(
            operation="web_research_keywords",
            model=gemini_model.model_name,
            duration_ms=duration_ms,
            status="success",
            session_id=session_id,
            metadata={"topic_count": len(generated_topics)},
        )
    except Exception as exc:
        duration_ms = int((time.perf_counter() - start) * 1000)
        fallback_reason = str(exc)
        gemini_call(
            operation="web_research_keywords",
            model=getattr(gemini_model, "model_name", _DEFAULT_MODEL),
            duration_ms=duration_ms,
            status="error",
            session_id=session_id,
            error=str(exc),
        )
        generated_topics = []
    selected_plans = _select_primary_and_industry(generated_topics, original_query=normalized_query)
    keyword_focus = selected_plans[0].label or normalized_query
    bundle = WebResearchQuestionBundle(
        keyword_focus=keyword_focus,
        user_question=selected_plans[0].query,
        industry_question=selected_plans[1].query,
        model=getattr(gemini_model, "model_name", _DEFAULT_MODEL),
        latency_ms=duration_ms,
        source="fallback" if fallback_reason else "gemini",
        fallback_reason=fallback_reason,
    )
    if snapshot is not None:
        try:
            snapshot.record_web_research_questions(bundle.to_dict())
        except Exception:
            logger.debug("Failed to persist web research question bundle", exc_info=True)
    return bundle, selected_plans


async def generate_search_topics(
    query: str,
    *,
    session_id: Optional[str] = None,
    min_topics: int = 2,
) -> List[SearchTopicPlan]:
    """Return structured topic prompts without issuing live web calls."""
    _, plans = await build_web_research_questions(
        query,
        snapshot=None,
        session_id=session_id,
        min_topics=min_topics,
    )
    return plans


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


def _select_primary_and_industry(
    candidate_plans: Sequence[SearchTopicPlan],
    *,
    original_query: str,
) -> List[SearchTopicPlan]:
    """Ensure at least two distinct topic plans covering user + industry context."""
    plans: List[SearchTopicPlan] = [plan for plan in candidate_plans if plan.query]
    if not plans:
        primary_query = _sanitize_search_query(original_query, original_query)
        industry_query = _sanitize_search_query(f"{primary_query} industry outlook", primary_query)
        return [
            SearchTopicPlan(label="Primary question", query=primary_query, reason="User focus", question_kind="user"),
            SearchTopicPlan(
                label="Industry context",
                query=industry_query,
                reason="Broader sector trend",
                question_kind="industry",
            ),
        ]

    primary = plans[0]
    industry: Optional[SearchTopicPlan] = None
    for plan in plans[1:]:
        normalized_blob = " ".join(filter(None, [plan.label, plan.query, plan.reason or ""])).lower()
        if any(token in normalized_blob for token in ("industry", "sector", "market")):
            industry = plan
            break
    if industry is None and len(plans) > 1:
        industry = plans[1]

    primary_query = _sanitize_search_query(primary.query, original_query)
    if industry is None or _sanitize_search_query(industry.query, original_query).lower() == primary_query.lower():
        fallback_seed = primary_query or original_query
        fallback_query = _sanitize_search_query(f"{fallback_seed} industry outlook", fallback_seed or original_query)
        industry = SearchTopicPlan(
            label="Industry context",
            query=fallback_query,
            reason="Provide wider sector context",
        )

    sanitized_industry_query = _sanitize_search_query(industry.query, original_query)
    if sanitized_industry_query.lower() == primary_query.lower():
        sanitized_industry_query = _sanitize_search_query(
            f"{primary_query} broader industry trend",
            primary_query,
        )
    finalized = [
        SearchTopicPlan(
            label=primary.label or "Primary question",
            query=primary_query,
            reason=primary.reason,
            question_kind="user",
        ),
        SearchTopicPlan(
            label=industry.label or "Industry context",
            query=sanitized_industry_query,
            reason=industry.reason or "Broader sector context",
            question_kind="industry",
        ),
    ]
    return finalized


def _bundle_from_topic_plans(
    plans: Sequence[SearchTopicPlan],
    *,
    original_query: str,
    model_name: Optional[str],
    source: str = "gemini",
) -> Tuple[WebResearchQuestionBundle, List[SearchTopicPlan]]:
    normalized_plans = _select_primary_and_industry(plans, original_query=original_query)
    primary, industry = normalized_plans[0], normalized_plans[1]
    bundle = WebResearchQuestionBundle(
        keyword_focus=primary.label or primary.query or original_query,
        user_question=primary.query or original_query,
        industry_question=industry.query or f"{original_query} industry outlook",
        model=model_name,
        source=source,
    )
    return bundle, normalized_plans


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
    topic_plans: Optional[Sequence[SearchTopicPlan]] = None,
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
    questions_payload: Optional[Dict[str, Any]] = None
    model_name = getattr(gemini_model, "model_name", _DEFAULT_MODEL)
    if topic_plans:
        provided_plans: List[SearchTopicPlan] = []
        for plan in topic_plans:
            if not isinstance(plan, SearchTopicPlan):
                continue
            sanitized_query = _sanitize_search_query(plan.query, plan.query)
            if not sanitized_query:
                continue
            provided_plans.append(
                SearchTopicPlan(
                    label=plan.label or "Research focus",
                    query=sanitized_query,
                    reason=plan.reason,
                    question_kind=getattr(plan, "question_kind", None),
                )
            )
        if provided_plans:
            bundle, normalized_plans = _bundle_from_topic_plans(
                provided_plans,
                original_query=normalized_query,
                model_name=model_name,
                source="revision_topics",
            )
            questions_payload = bundle.to_dict()
            plans = normalized_plans
    else:
        if search_topic and isinstance(search_topic, str) and search_topic.strip():
            bundle, generated_plans = await build_web_research_questions(
                normalized_query,
                snapshot=None,
                session_id=session_id,
                min_topics=2,
            )
            sanitized = _sanitize_search_query(search_topic, search_topic)
            user_plan = SearchTopicPlan(
                label='Primary question',
                query=sanitized,
                reason='User supplied topic',
                question_kind='user',
            )
            industry_plan = generated_plans[1] if len(generated_plans) > 1 else generated_plans[0]
            industry_plan.question_kind = industry_plan.question_kind or 'industry'
            plans = [user_plan, industry_plan]
            bundle.keyword_focus = bundle.keyword_focus or sanitized
            bundle.user_question = user_plan.query
            questions_payload = bundle.to_dict()
        else:
            bundle, bundle_plans = await build_web_research_questions(
                normalized_query,
                snapshot=None,
                session_id=session_id,
                min_topics=2,
            )
            plans = bundle_plans
            questions_payload = bundle.to_dict()
    if not plans:
        plans = _select_primary_and_industry([], original_query=normalized_query)
        questions_payload = {
            "keyword_focus": normalized_query,
            "user_question": plans[0].query,
            "industry_question": plans[1].query,
            "generated_at": datetime.utcnow().isoformat(),
            "source": "fallback",
        }
    elif not questions_payload:
        plans = _select_primary_and_industry(plans, original_query=normalized_query)

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

    timeout_seconds = max(0.1, _REQUEST_TIMEOUT_SECONDS)

    async def _execute_plan(plan: SearchTopicPlan) -> Dict[str, Any]:
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
                response = await asyncio.wait_for(
                    asyncio.to_thread(
                        gemini_model.generate_content,
                        **request_args,
                    ),
                    timeout=timeout_seconds,
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
            except asyncio.TimeoutError as exc:
                elapsed_ms = int((time.perf_counter() - start_time) * 1000)
                last_error = exc
                logger.warning(
                    'Gemini search attempt %s timed out for %s after %sms',
                    attempt,
                    plan.query,
                    elapsed_ms,
                )
                gemini_call(
                    operation='google_search',
                    model=gemini_model.model_name,
                    duration_ms=elapsed_ms,
                    status='error',
                    session_id=session_id,
                    error='timeout',
                    metadata={'attempt': attempt, 'search_query': plan.query},
                )
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
            if response_dict:
                break
            if attempt >= attempts:
                error_message = (
                    'Gemini Google Search timed out'
                    if isinstance(last_error, asyncio.TimeoutError)
                    else 'Gemini Google Search failed'
                )
                logger.error('%s after %s attempts (last_error=%s)', error_message, attempts, type(last_error).__name__ if last_error else 'unknown')
                raise ResponseSearchError(
                    error_message,
                    stage='search_execution',
                    retryable=True,
                    code='search_execution_error',
                ) from last_error
            delay = _RETRY_BASE_DELAY * (2 ** (attempt - 1))
            logger.debug('Retrying Gemini search in %.2f seconds', delay)
            await asyncio.sleep(delay)

        if not response_dict:
            raise ResponseSearchError(
                last_error or 'Gemini Google Search produced no output',
                stage='search_execution',
                retryable=True,
                code='search_empty',
            )
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
        topic_result = TopicSearchResult(
            label=plan.label,
            query=plan.query,
            reason=plan.reason,
            question_kind=getattr(plan, "question_kind", None),
            summary=topic_summary,
            snippets=topic_snippets,
            search_id=response_dict.get('response_id') or response_dict.get('id'),
            latency_ms=elapsed_ms,
        )
        summary_text = f"{plan.label}: {topic_summary}" if topic_summary else None

        return {
            'topic_result': topic_result,
            'annotations': topic_annotations,
            'snippets': topic_snippets,
            'summary': summary_text,
            'elapsed_ms': elapsed_ms,
            'usage': response_dict.get('usage'),
        }

    execution_results = await asyncio.gather(*[_execute_plan(plan) for plan in plans])

    for execution in execution_results:
        topic_results.append(execution['topic_result'])
        aggregated_annotations.extend(execution['annotations'])
        aggregated_snippets.extend(execution['snippets'])
        if execution['summary']:
            summary_sections.append(execution['summary'])
        if execution['elapsed_ms']:
            total_latency += execution['elapsed_ms']
        if execution['usage']:
            last_usage = execution['usage']

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
    if questions_payload:
        result.questions = dict(questions_payload)

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




