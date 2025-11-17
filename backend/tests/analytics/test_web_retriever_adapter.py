import sys
import asyncio
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.append(str(Path(__file__).resolve().parents[2]))

from analytics.flows import tooling
from analytics.services.response_search import (
    ResponseSearchError,
    ResponseSearchResult,
    SearchTopicPlan,
    WebResearchQuestionBundle,
)
from analytics.flows.tooling import WebRetrieverAdapter, ToolExecutionContext
from analytics.core.session_state import SessionStateSnapshot


def _build_context(session_id: str, query: str) -> ToolExecutionContext:
    return ToolExecutionContext(
        session_id=session_id,
        query=query,
        intent=SimpleNamespace(slots_detected={"original_query": query}),
        plan=SimpleNamespace(),
        template=None,
        configs={},
    )


def test_web_retriever_skip_without_api_key(monkeypatch):
    adapter = WebRetrieverAdapter()
    context = _build_context("sess-skip", "NVDA latest guidance")

    monkeypatch.setattr(tooling, "has_search_api_key", lambda: False)

    result = asyncio.run(adapter.execute(context))

    assert result.status == "skip"
    assert result.payload.get("error") == "search_api_missing"
    assert result.metadata.get("summary", "").lower().startswith("web search disabled")


class _DummyRepo:
    def __init__(self) -> None:
        self.saved_snapshot = None
        self.loaded_snapshot = None

    async def load(self, session_id: str):
        snapshot = SessionStateSnapshot(session_id=session_id)
        self.loaded_snapshot = snapshot
        return snapshot

    async def save(self, snapshot: SessionStateSnapshot):
        self.saved_snapshot = snapshot


class _DummySearchResult:
    def __init__(self) -> None:
        self.latency_ms = 123
        self.search_id = "search-123"
        self.summary = "Stub summary"
        self.questions = None

    def to_payload(self):
        return {
            "summary": "Stub summary",
            "snippets": [{"title": "Headline"}],
            "search_id": self.search_id,
        }

    def to_agent_envelope(self, *, status: str = "completed", cached: bool = False):
        return {
            "status": status,
            "summary": self.summary,
            "from_cache": cached,
        }


def test_web_retriever_fetches_when_api_key_present(monkeypatch):
    adapter = WebRetrieverAdapter()
    context = _build_context("sess-run", "AMD vs NVDA earnings")
    adapter._research_bundle = WebResearchQuestionBundle(
        keyword_focus="AMD vs NVDA",
        user_question="What updates compare AMD vs NVDA earnings?",
        industry_question="How is the semiconductor industry trending overall?",
    )

    repo = _DummyRepo()

    async def _fake_search(*args, **kwargs):
        return _DummySearchResult()

    monkeypatch.setattr(tooling, "has_search_api_key", lambda: True)
    monkeypatch.setattr(tooling, "get_session_state_repository", lambda: repo)
    monkeypatch.setattr(tooling, "perform_response_search", _fake_search)

    result = asyncio.run(adapter.execute(context))

    assert result.status == "completed"
    assert result.payload.get("ready") is True
    assert result.payload.get("summary") == "Stub summary"
    assert result.payload.get("questions", {}).get("user_question")
    assert repo.saved_snapshot is not None
    assert repo.saved_snapshot.tool_cache.get("web_search", {}).get("summary") == "Stub summary"
    assert repo.saved_snapshot.web_research_questions

def test_web_retriever_reports_error_stage(monkeypatch):
    adapter = WebRetrieverAdapter()
    context = _build_context("sess-fail", "AMD news today")

    repo = _DummyRepo()

    async def _failing_search(*args, **kwargs):
        raise ResponseSearchError("search boom", stage="topic_generation")

    monkeypatch.setattr(tooling, "has_search_api_key", lambda: True)
    monkeypatch.setattr(tooling, "get_session_state_repository", lambda: repo)
    monkeypatch.setattr(tooling, "perform_response_search", _failing_search)

    result = asyncio.run(adapter.execute(context))

    assert result.status == "error"
    assert result.metadata.get("error_stage") == "topic_generation"
    assert result.payload.get("error_stage") == "topic_generation"
    assert result.metadata.get("error") == "search boom"


def test_expand_generates_unique_names_for_duplicate_labels(monkeypatch):
    adapter = WebRetrieverAdapter()
    context = _build_context("sess-fanout", "Market outlook 2025")
    plans = [
        SearchTopicPlan(label="Market Outlook", query="market outlook 2025"),
        SearchTopicPlan(label="Market Outlook", query="market outlook by region"),
    ]

    bundle = WebResearchQuestionBundle(
        keyword_focus="Market outlook",
        user_question="market outlook 2025",
        industry_question="market outlook by region",
    )

    async def _fake_build(*args, **kwargs):
        return bundle, plans

    monkeypatch.setattr(tooling, "has_search_api_key", lambda: True)
    monkeypatch.setattr(tooling, "build_web_research_questions", _fake_build)

    expanded = asyncio.run(adapter.expand(context))

    assert len(expanded) == 2
    first, second = expanded
    assert first.name != second.name
    assert second.name.startswith("web_retriever_market-outlook-")
    assert first.display_name.endswith("(Topic 1 of 2)")
    assert second.display_name.endswith("(Topic 2 of 2)")


def test_topic_execute_includes_position_metadata(monkeypatch):
    topic_plan = SearchTopicPlan(label="Regulation Watch", query="regulation watch 2025")
    adapter = WebRetrieverAdapter(
        topic_plan=topic_plan,
        topic_index=1,
        topic_total=3,
        base_query="regulation watch 2025",
        label_occurrence=2,
        label_total=2,
    )
    adapter._research_bundle = WebResearchQuestionBundle(
        keyword_focus="Regulation",
        user_question="regulation watch 2025",
        industry_question="industry regulation outlook 2025",
    )
    context = _build_context("sess-topic", "regulation watch 2025")

    repo = _DummyRepo()

    class _TopicSearchResult(_DummySearchResult):
        def to_payload(self):
            payload = super().to_payload()
            payload.setdefault("search_topics", [topic_plan.query])
            return payload

    async def _fake_search(*args, **kwargs):
        return _TopicSearchResult()

    monkeypatch.setattr(tooling, "has_search_api_key", lambda: True)
    monkeypatch.setattr(tooling, "get_session_state_repository", lambda: repo)
    monkeypatch.setattr(tooling, "perform_response_search", _fake_search)

    result = asyncio.run(adapter.execute(context))

    assert result.payload.get("topic_index") == 1
    assert result.payload.get("topic_total") == 3
    assert result.payload.get("topic_position") == 2
    assert result.metadata.get("topic_position") == 2
    assert result.payload.get("questions", {}).get("user_question")
    assert repo.saved_snapshot is not None
    topic_cache = repo.saved_snapshot.tool_cache.get("web_search_topics", {})
    assert adapter._topic_key in topic_cache
    assert topic_cache[adapter._topic_key].get("topic_position") == 2


def test_expand_uses_revision_topics_when_available(monkeypatch):
    adapter = WebRetrieverAdapter()
    revision_topics = (
        {"label": "CapEx Drivers", "query": "AMD capital expenditure drivers 2025"},
        {"label": "Manufacturing Investments", "query": "AMD manufacturing investments"},
    )
    context = ToolExecutionContext(
        session_id="sess-revision",
        query="Rewrite the analysis to highlight capital expenditure drivers for AMD",
        intent=SimpleNamespace(slots_detected={"original_query": "Rewrite the analysis to highlight capital expenditure drivers for AMD"}),
        plan=SimpleNamespace(),
        template=None,
        configs={},
        revision_focus="highlight capital expenditure drivers for AMD",
        revision_search_topics=tuple(revision_topics),
    )

    monkeypatch.setattr(tooling, "has_search_api_key", lambda: True)

    async def _fail_build(*args, **kwargs):
        raise AssertionError("build_web_research_questions should not be called")

    monkeypatch.setattr(tooling, "build_web_research_questions", _fail_build)

    expanded = asyncio.run(adapter.expand(context))

    assert len(expanded) == len(revision_topics)
    queries = {child._topic_plan.query for child in expanded if child._topic_plan}
    assert "AMD capital expenditure drivers 2025" in queries
    assert "AMD manufacturing investments" in queries


# Function: test_web_retriever_revision_refresh_busts_cache — called from pytest to validate that revision-driven web refreshes bypass cached payloads; invokes WebRetrieverAdapter.execute with a cached snapshot and a forced refresh expectation; ensures the project detects when analysis revisions silently reuse stale web context.
@pytest.mark.asyncio
async def test_web_retriever_revision_refresh_busts_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    session_id = "revision-web-cache"
    query = "Extend AMD vs NVDA outlook"

    snapshot = SessionStateSnapshot(session_id=session_id)
    snapshot.record_tool_result(
        "web_search",
        {
            "query": query,
            "query_terms": query.lower(),
            "summary": "cached summary",
            "snippets": [{"title": "cached", "snippet": "cached body"}],
            "ready": True,
            "from_cache": True,
        },
    )

    class _Repo:
        def __init__(self, snap: SessionStateSnapshot) -> None:
            self.snapshot = snap

        async def load(self, sid: str) -> SessionStateSnapshot:
            assert sid == self.snapshot.session_id
            return self.snapshot

        async def save(self, snap: SessionStateSnapshot) -> SessionStateSnapshot:
            self.snapshot = snap
            return snap

    repo = _Repo(snapshot)
    monkeypatch.setattr(tooling, "get_session_state_repository", lambda: repo)
    monkeypatch.setattr(tooling, "has_search_api_key", lambda: True)

    adapter = WebRetrieverAdapter()
    context = SimpleNamespace(
        session_id=session_id,
        query=query,
        intent=SimpleNamespace(slots_detected={"original_query": query}),
        plan=SimpleNamespace(group_by=[], timeframe=None, metrics=[]),
        template=None,
        configs={},
        revision_directive=None,
        revision_focus=None,
        revision_search_topics=(),
        force_revision_refresh=True,
    )

    search_called = False

    async def fake_perform_response_search(*args, **kwargs) -> ResponseSearchResult:
        nonlocal search_called
        search_called = True
        return ResponseSearchResult(query=query, summary="fresh summary")

    monkeypatch.setattr(tooling, "perform_response_search", fake_perform_response_search)

    result = await adapter.execute(context)

    assert search_called, "analysis revisions should force a fresh web search even if cache exists"
    assert result.status == "completed", "adapter should emit completed payload when refresh is required"
    assert result.payload.get("from_cache") is False


def test_revision_skips_cache_and_forces_search(monkeypatch):
    adapter = WebRetrieverAdapter()
    context = ToolExecutionContext(
        session_id="sess-refresh",
        query="Rewrite the analysis to highlight capital expenditure drivers for AMD",
        intent=SimpleNamespace(slots_detected={"original_query": "Rewrite the analysis to highlight capital expenditure drivers for AMD"}),
        plan=SimpleNamespace(),
        template=None,
        configs={},
        revision_directive=SimpleNamespace(agentic=False, search_topics=[], requested_focus="highlight capital expenditure drivers for AMD"),
        revision_focus="highlight capital expenditure drivers for AMD",
        revision_search_topics=tuple(),
    )

    repo = _DummyRepo()
    cached_snapshot = SessionStateSnapshot(session_id="sess-refresh")
    cached_snapshot.tool_cache["web_search"] = {"query": "highlight capital expenditure drivers for amd", "summary": "Old summary", "ready": True}
    repo.saved_snapshot = cached_snapshot

    async def _fake_load(session_id: str):
        return cached_snapshot

    async def _fake_search(*args, **kwargs):
        return _DummySearchResult()

    monkeypatch.setattr(tooling, "has_search_api_key", lambda: True)
    monkeypatch.setattr(tooling, "get_session_state_repository", lambda: repo)
    monkeypatch.setattr(repo, "load", _fake_load)
    search_called = {"count": 0}

    async def _tracking_search(*args, **kwargs):
        search_called["count"] += 1
        return await _fake_search(*args, **kwargs)

    monkeypatch.setattr(tooling, "perform_response_search", _tracking_search)

    result = asyncio.run(adapter.execute(context))

    assert result.status == "completed"
    assert search_called["count"] == 1
    assert result.payload.get("from_cache") is not True


def test_revision_refresh_web_lane(monkeypatch):
    adapter = WebRetrieverAdapter()
    context = ToolExecutionContext(
        session_id="sess-web-lane",
        query="Analysis: refresh the AMD capex focus",
        intent=SimpleNamespace(slots_detected={"original_query": "Analysis: refresh the AMD capex focus"}),
        plan=SimpleNamespace(),
        template=None,
        configs={},
        revision_directive=SimpleNamespace(agentic=False, search_topics=[], requested_focus="highlight capex drivers for AMD"),
        revision_focus="highlight capex drivers for AMD",
        revision_search_topics=tuple(),
    )

    repo = _DummyRepo()

    async def _fake_load(session_id: str):
        snapshot = SessionStateSnapshot(session_id=session_id)
        snapshot.tool_cache["web_search"] = {"query": "analysis: refresh the amd capex focus", "summary": "Old summary", "ready": True}
        return snapshot

    async def _fake_search(*args, **kwargs):
        return _DummySearchResult()

    monkeypatch.setattr(tooling, "has_search_api_key", lambda: True)
    monkeypatch.setattr(tooling, "get_session_state_repository", lambda: repo)
    monkeypatch.setattr(repo, "load", _fake_load)
    monkeypatch.setattr(tooling.WebRetrieverAdapter, "_maybe_get_cached", lambda self, snapshot, query_terms: None)
    monkeypatch.setattr(tooling.WebRetrieverAdapter, "_should_refresh", lambda self, query_terms, snapshot: True)
    monkeypatch.setattr(tooling, "perform_response_search", _fake_search)

    result = asyncio.run(adapter.execute(context))

    assert result.status == "completed"
    assert result.payload.get("from_cache") is False
    assert result.payload.get("summary") == "Stub summary"


@pytest.mark.asyncio
async def test_revision_topics_emit_question_bundle(monkeypatch):
    adapter = WebRetrieverAdapter()
    base_context = _build_context("sess-revision-topics", "AMD refresh")
    context = replace(
        base_context,
        revision_search_topics=tuple(
            [
                {"label": "User focus", "query": "AMD latest guidance"},
                {"label": "Industry context", "query": "semiconductor industry outlook"},
            ]
        ),
    )

    monkeypatch.setattr(tooling, "has_search_api_key", lambda: True)

    adapters = await adapter.expand(context)
    assert adapters
    for child in adapters:
        assert isinstance(child, WebRetrieverAdapter)
        assert child._research_bundle is not None
        bundle = child._research_bundle.to_dict()
        assert bundle["user_question"].startswith("AMD")
        assert bundle["industry_question"]
        assert child._topic_plan.question_kind in {"user", "industry"}
