# --- Analytics Function/Class Map ---
# Class: RevisionQuestionBundle
#   Role: Structured container for Gemini-derived revision focus questions and metadata.
#   Called from: analytics.services.revision_focus, analytics.flows.workflow, analytics.flows.single_agent_tools
#   Collaborators: dataclasses.dataclass, datetime.now, analytics.services.revision_focus._fingerprint_revision_query
#   Why: Persists normalized revision prompts so controllers, telemetry, and ledgers share a single schema.
# Function: _normalize_text
#   Role: Trims and lowers arbitrary text for hashing and prompt assembly.
#   Called from: analytics.services.revision_focus
#   Invokes: str.split
#   Why: Keeps normalization logic centralized so query fingerprints remain consistent across callers.
# Function: _fingerprint_revision_query
#   Role: Builds a stable fingerprint for the prior + follow-up query pair.
#   Called from: analytics.services.revision_focus
#   Invokes: hashlib.sha256, analytics.services.revision_focus._normalize_text
#   Why: Prevents redundant Gemini calls by keying cached bundles on identical revision context.
# Function: _extract_response_text
#   Role: Coerces Gemini response payloads into raw text for JSON parsing.
#   Called from: analytics.services.revision_focus
#   Invokes: json.dumps
#   Why: Shields downstream parsing from SDK-specific response objects.
# Function: _coerce_question
#   Role: Sanitizes model-produced question strings and enforces max length.
#   Called from: analytics.services.revision_focus
#   Invokes: analytics.services.revision_focus._normalize_text
#   Why: Prevents unbounded strings from leaking into SSE payloads or telemetry.
# Function: _fallback_revision_questions
#   Role: Synthesizes keyword + question bundle when Gemini is unavailable.
#   Called from: analytics.services.revision_focus
#   Invokes: analytics.services.revision_focus._coerce_question, analytics.services.revision_focus._normalize_text
#   Why: Guarantees revisions still route even if the LLM tier is degraded.
# Function: _build_question_prompt
#   Role: Renders the Gemini system/user prompt using session context.
#   Called from: analytics.services.revision_focus
#   Invokes: analytics.services.revision_focus._normalize_text
#   Why: Keeps prompt wording aligned with docs/gpt5-best-practices.md without duplicating string templates.
# Function: _call_gemini_revision_model
#   Role: Executes the Gemini Flash model and logs telemetry around the call.
#   Called from: analytics.services.revision_focus
#   Invokes: gemini_service._GenerativeModel, analytics.services.revision_focus._extract_response_text, analytics.core.telemetry.gemini_call
#   Why: Centralizes retries, error mapping, and logging for revision keyword generation.
# Function: get_cached_revision_questions
#   Role: Reads the latest cached bundle from the session snapshot.
#   Called from: analytics.services.revision_focus, analytics.flows.workflow
#   Invokes: analytics.services.revision_focus.RevisionQuestionBundle.from_dict
#   Why: Lets flows reuse prior Gemini answers without reissuing API calls.
# Function: cache_revision_questions
#   Role: Persists the supplied bundle under snapshot.agents_revision_question_store.
#   Called from: analytics.services.revision_focus, analytics.flows.workflow
#   Invokes: analytics.services.revision_focus.RevisionQuestionBundle.to_dict
#   Why: Provides a single mutation point for revision question caching and history trimming.
# Function: derive_revision_questions
#   Role: Public entry that returns the Gemini (or fallback) bundle for the current revision query.
#   Called from: analytics.flows.workflow, analytics.flows.single_agent_tools, analytics.flows.multi_agent
#   Invokes: analytics.services.revision_focus.get_cached_revision_questions, analytics.services.revision_focus._call_gemini_revision_model, analytics.services.revision_focus.cache_revision_questions
#   Why: Powers the True Agentic Revision Plan by supplying consistent keyword + question hints per revision.
# --- End Analytics Function/Class Map ---
from __future__ import annotations

import json
import logging
import os
import time
import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Mapping, Optional, Tuple, Iterable

from analytics.core.session_state import SessionStateSnapshot
from analytics.core.telemetry import gemini_call

try:  # pragma: no cover - optional Gemini dependency
    from gemini_service import (  # type: ignore
        GEMINI_API_KEY as _GEMINI_API_KEY,
        _GenerativeModel as _GeminiGenerativeModel,
        _genai_configure as _gemini_configure,
    )
except ImportError:  # pragma: no cover - shim fallback when Gemini absent
    _GeminiGenerativeModel = None
    _gemini_configure = None
    _GEMINI_API_KEY = None

logger = logging.getLogger(__name__)

_DEFAULT_MODEL = os.getenv("GEMINI_REVISION_MODEL", "gemini-2.5-flash")
_GENERATION_CONFIG: Dict[str, Any] = {
    "temperature": float(os.getenv("GEMINI_REVISION_TEMPERATURE", "0.2")),
    "top_p": 0.8,
    "top_k": 40,
    "max_output_tokens": 512,
    "response_mime_type": "application/json",
}


@dataclass
class RevisionQuestionBundle:
    """Structured container for revision keyword prompts."""

    keyword_focus: str
    user_question: str
    industry_question: str
    model: Optional[str] = None
    latency_ms: Optional[int] = None
    generated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    follow_up_query: Optional[str] = None
    fingerprint: Optional[str] = None
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
        if self.follow_up_query:
            payload["follow_up_query"] = self.follow_up_query
        if self.fingerprint:
            payload["fingerprint"] = self.fingerprint
        if self.fallback_reason:
            payload["fallback_reason"] = self.fallback_reason
        return payload

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "RevisionQuestionBundle":
        return cls(
            keyword_focus=str(payload.get("keyword_focus") or "").strip(),
            user_question=str(payload.get("user_question") or "").strip(),
            industry_question=str(payload.get("industry_question") or "").strip(),
            model=str(payload.get("model") or "").strip() or None,
            latency_ms=payload.get("latency_ms"),
            generated_at=str(payload.get("generated_at") or datetime.now(timezone.utc).isoformat()),
            follow_up_query=str(payload.get("follow_up_query") or "").strip() or None,
            fingerprint=str(payload.get("fingerprint") or "").strip() or None,
            source=str(payload.get("source") or "gemini"),
            fallback_reason=str(payload.get("fallback_reason") or "").strip() or None,
        )


def _normalize_text(value: Optional[str], *, limit: Optional[int] = None) -> str:
    trimmed = " ".join(str(value or "").strip().split())
    if limit is not None and len(trimmed) > limit:
        return trimmed[:limit].rstrip()
    return trimmed


def _fingerprint_revision_query(
    follow_up_query: str,
    snapshot: Optional[SessionStateSnapshot],
) -> str:
    basis_parts = [
        _normalize_text(getattr(snapshot, "last_query", None)).lower(),
        _normalize_text(follow_up_query).lower(),
    ]
    joined = " || ".join(part for part in basis_parts if part)
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()[:24]


def _extract_response_text(response: Any) -> str:
    if response is None:
        return ""
    if isinstance(response, str):
        return response
    if isinstance(response, Mapping):
        text_value = response.get("text")
        if isinstance(text_value, str) and text_value.strip():
            return text_value
        try:
            return json.dumps(response)
        except TypeError:
            return str(response)
    return str(response)


def _coerce_question(value: Any, *, default: str) -> str:
    normalized = _normalize_text(value, limit=280)
    return normalized or _normalize_text(default, limit=280) or default


def _fallback_revision_questions(
    follow_up_query: str,
    *,
    snapshot: Optional[SessionStateSnapshot],
    fingerprint: Optional[str],
    revision_directive: Optional[Any],
    reason: str,
) -> RevisionQuestionBundle:
    topic_basis = (
        getattr(revision_directive, "requested_focus", None)
        or follow_up_query
        or getattr(snapshot, "last_query", None)
        or ""
    )
    analysis_text = getattr(snapshot, "last_analysis", None)
    initial_topics: Iterable[Mapping[str, Any]] = getattr(revision_directive, "search_topics", None) or ()
    topics_list: Iterable[Mapping[str, Any]] = list(initial_topics)
    try:
        from analytics.flows.workflow import _ensure_dual_topics  # type: ignore
    except Exception:  # pragma: no cover - fallback when workflow unavailable
        derived_topics = [
            {"label": topic_basis[:80] or "analysis revision", "query": topic_basis[:256] or follow_up_query}
        ]
    else:
        derived_topics = _ensure_dual_topics(
            list(topics_list),
            topic_basis=topic_basis,
            user_query=follow_up_query,
            analysis_text=analysis_text,
        )
    primary_topic = derived_topics[0] if derived_topics else {"label": topic_basis or "analysis revision", "query": follow_up_query}
    secondary_topic = derived_topics[1] if len(derived_topics) > 1 else primary_topic
    keyword_focus = _coerce_question(
        primary_topic.get("label") or primary_topic.get("query"),
        default=topic_basis or follow_up_query or "analysis update",
    )
    user_question = _coerce_question(
        follow_up_query,
        default=primary_topic.get("query") or keyword_focus,
    )
    industry_question = _coerce_question(
        secondary_topic.get("query") or secondary_topic.get("label"),
        default=f"What industry factors impact {keyword_focus}?",
    )
    return RevisionQuestionBundle(
        keyword_focus=keyword_focus,
        user_question=user_question,
        industry_question=industry_question,
        model="fallback",
        latency_ms=None,
        follow_up_query=follow_up_query,
        fingerprint=fingerprint,
        source="fallback",
        fallback_reason=reason,
    )


def _build_question_prompt(snapshot: Optional[SessionStateSnapshot], follow_up_query: str) -> str:
    baseline_query = _normalize_text(getattr(snapshot, "last_query", None), limit=600)
    analysis_summary = _normalize_text(getattr(snapshot, "last_analysis", None), limit=900)
    follow_up = _normalize_text(follow_up_query, limit=600)
    prompt_parts = [
        "You are a Gemini Flash assistant that prepares revision keywords for an analytics copilot.",
        "Return strictly JSON with keys keyword_focus, user_question, industry_question (strings).",
        "Each value must stay under 40 words and focus on evidence the agent should gather.",
        "Prefer concise imperatives and highlight concrete metrics or entities.",
        "Model configuration: reasoning_effort=\"medium\", temperature=0.2 as outlined in docs/gpt5-best-practices.md.",
    ]
    if baseline_query:
        prompt_parts.append(f"Original analytics question: {baseline_query}")
    if analysis_summary:
        prompt_parts.append(f"Previous analysis summary: {analysis_summary}")
    prompt_parts.append(f"Follow-up request: {follow_up}")
    prompt_parts.append(
        "Safety: no PII, no investment advice. If unsure, anchor on the follow-up request."
    )
    prompt_parts.append(
        "JSON example: {\"keyword_focus\": \"AI hiring plans\", \"user_question\": \"Detail how AMD described AI workforce expansion\", \"industry_question\": \"What are peers signaling about AI hiring?\"}"
    )
    return "\n".join(prompt_parts)


def _call_gemini_revision_model(
    *,
    follow_up_query: str,
    snapshot: Optional[SessionStateSnapshot],
    session_id: Optional[str],
) -> RevisionQuestionBundle:
    if _GeminiGenerativeModel is None or _gemini_configure is None:
        raise RuntimeError("Gemini SDK unavailable")

    api_key = os.getenv("GEMINI_API_KEY") or _GEMINI_API_KEY
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY not configured")

    _gemini_configure(api_key=api_key)
    prompt = _build_question_prompt(snapshot, follow_up_query)
    generator = _GeminiGenerativeModel(_DEFAULT_MODEL, dict(_GENERATION_CONFIG))
    start = time.time()
    try:
        response = generator.generate_content(contents=prompt)
        raw_text = _extract_response_text(response)
        parsed = json.loads(raw_text or "{}")
    except Exception as exc:  # pragma: no cover - network path
        duration_ms = int((time.time() - start) * 1000)
        gemini_call(
            operation="revision_keywords",
            model=_DEFAULT_MODEL,
            duration_ms=duration_ms,
            status="error",
            session_id=session_id,
            error=str(exc),
        )
        raise
    duration_ms = int((time.time() - start) * 1000)
    gemini_call(
        operation="revision_keywords",
        model=_DEFAULT_MODEL,
        duration_ms=duration_ms,
        status="success",
        session_id=session_id,
    )
    if not isinstance(parsed, Mapping):
        raise ValueError("Gemini revision payload must be an object")
    keyword_focus = _coerce_question(parsed.get("keyword_focus"), default=follow_up_query)
    user_question = _coerce_question(parsed.get("user_question"), default=follow_up_query)
    industry_question = _coerce_question(
        parsed.get("industry_question"),
        default=f"What industry context matters for {keyword_focus}?",
    )
    return RevisionQuestionBundle(
        keyword_focus=keyword_focus,
        user_question=user_question,
        industry_question=industry_question,
        model=_DEFAULT_MODEL,
        latency_ms=duration_ms,
        follow_up_query=follow_up_query,
    )


def get_cached_revision_questions(
    snapshot: Optional[SessionStateSnapshot],
    *,
    fingerprint: Optional[str] = None,
) -> Optional[RevisionQuestionBundle]:
    if snapshot is None:
        return None
    tool_cache = snapshot.tool_cache if isinstance(snapshot.tool_cache, dict) else {}
    agent_cache = tool_cache.get("agent")
    if not isinstance(agent_cache, dict):
        return None
    store = agent_cache.get("revision_questions")
    if not isinstance(store, dict):
        return None
    entry: Optional[Mapping[str, Any]] = None
    if fingerprint:
        by_fingerprint = store.get("by_fingerprint")
        if isinstance(by_fingerprint, Mapping):
            candidate = by_fingerprint.get(fingerprint)
            if isinstance(candidate, Mapping):
                entry = candidate
    if entry is None:
        latest = store.get("latest")
        if isinstance(latest, Mapping):
            entry = latest
    if not entry:
        return None
    bundle_payload = entry.get("bundle") if isinstance(entry.get("bundle"), Mapping) else entry
    try:
        bundle = RevisionQuestionBundle.from_dict(bundle_payload)  # type: ignore[arg-type]
    except Exception:
        return None
    if not bundle.fingerprint and fingerprint:
        bundle.fingerprint = fingerprint
    return bundle


def cache_revision_questions(
    snapshot: Optional[SessionStateSnapshot],
    bundle: RevisionQuestionBundle,
) -> RevisionQuestionBundle:
    if snapshot is None:
        return bundle
    store = snapshot.agents_revision_question_store
    payload = {
        "fingerprint": bundle.fingerprint,
        "bundle": bundle.to_dict(),
    }
    store["latest"] = payload
    if bundle.fingerprint:
        by_fingerprint = store.setdefault("by_fingerprint", {})
        if isinstance(by_fingerprint, dict):
            by_fingerprint[bundle.fingerprint] = payload
    history = store.setdefault("history", [])
    if isinstance(history, list):
        history.append(payload)
        if len(history) > 5:
            del history[:-5]
    snapshot.touch()
    return RevisionQuestionBundle.from_dict(payload["bundle"])


def derive_revision_questions(
    *,
    query: str,
    revision_directive: Optional[Any],
    snapshot: Optional[SessionStateSnapshot],
    session_id: Optional[str],
) -> RevisionQuestionBundle:
    follow_up_query = (
        getattr(revision_directive, "requested_focus", None)
        or query
        or getattr(snapshot, "last_query", None)
        or ""
    )
    fingerprint = _fingerprint_revision_query(follow_up_query, snapshot)
    cached = get_cached_revision_questions(snapshot, fingerprint=fingerprint)
    if cached:
        return cached

    attempts = int(os.getenv("GEMINI_REVISION_RETRY_LIMIT", "2"))
    last_error: Optional[Exception] = None
    for attempt in range(1, max(attempts, 1) + 1):
        try:
            bundle = _call_gemini_revision_model(
                follow_up_query=follow_up_query,
                snapshot=snapshot,
                session_id=session_id,
            )
            bundle.fingerprint = fingerprint
            return cache_revision_questions(snapshot, bundle)
        except Exception as exc:
            last_error = exc
            logger.warning("Gemini revision keywords attempt %s failed: %s", attempt, exc)
            if attempt < attempts:
                time.sleep(0.2)
    fallback_bundle = _fallback_revision_questions(
        follow_up_query,
        snapshot=snapshot,
        fingerprint=fingerprint,
        revision_directive=revision_directive,
        reason=f"fallback_due_to_error:{last_error}",
    )
    return cache_revision_questions(snapshot, fallback_bundle)
