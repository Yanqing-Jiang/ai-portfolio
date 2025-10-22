import sys
import asyncio
from pathlib import Path
from types import SimpleNamespace

sys.path.append(str(Path(__file__).resolve().parents[2]))

from analytics.flows import tooling
from analytics.services.response_search import ResponseSearchError, SearchTopicPlan
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

    def to_payload(self):
        return {
            "summary": "Stub summary",
            "snippets": [{"title": "Headline"}],
            "search_id": self.search_id,
        }


def test_web_retriever_fetches_when_api_key_present(monkeypatch):
    adapter = WebRetrieverAdapter()
    context = _build_context("sess-run", "AMD vs NVDA earnings")

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
    assert repo.saved_snapshot is not None
    assert repo.saved_snapshot.tool_cache.get("web_search", {}).get("summary") == "Stub summary"

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

    async def _fake_generate(*args, **kwargs):
        return plans

    monkeypatch.setattr(tooling, "has_search_api_key", lambda: True)
    monkeypatch.setattr(tooling, "generate_search_topics", _fake_generate)

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
    assert repo.saved_snapshot is not None
    topic_cache = repo.saved_snapshot.tool_cache.get("web_search_topics", {})
    assert adapter._topic_key in topic_cache
    assert topic_cache[adapter._topic_key].get("topic_position") == 2
