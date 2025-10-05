import sys
import asyncio
from pathlib import Path
from types import SimpleNamespace

sys.path.append(str(Path(__file__).resolve().parents[2]))

from analytics.flows import tooling
from analytics.services.response_search import ResponseSearchError
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
