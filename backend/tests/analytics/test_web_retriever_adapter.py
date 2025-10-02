import asyncio
import pytest
from types import SimpleNamespace

from analytics.flows.tooling import ToolExecutionContext, WebRetrieverAdapter
from analytics.core.session_state import (
    SessionStateSnapshot,
    close_session_state_repository,
    get_session_state_repository,
)
from analytics.services.response_search import ResponseSearchError, ResponseSearchResult, SearchSnippet


@pytest.fixture(autouse=True)
def reset_session_repo():
    asyncio.run(close_session_state_repository())
    yield
    asyncio.run(close_session_state_repository())


def _make_context(query: str, session_id: str) -> ToolExecutionContext:
    intent = SimpleNamespace(slots_detected={"original_query": query})
    return ToolExecutionContext(
        session_id=session_id,
        query=query,
        intent=intent,
        plan=SimpleNamespace(metrics=["revenue"]),
        template=None,
        configs={},
    )


def test_web_retriever_returns_cached_result(monkeypatch):
    async def run():
        session_id = "session-cache"
        repo = get_session_state_repository()
        snapshot = SessionStateSnapshot(session_id=session_id)
        snapshot.record_tool_result(
            "web_search",
            {
                "query": "latest nvidia earnings",
                "summary": "Cached summary",
                "snippets": [{"title": "Example", "url": "https://example.com"}],
                "ready": True,
                "from_cache": True,
            },
        )
        await repo.save(snapshot)

        adapter = WebRetrieverAdapter()
        context = _make_context("Latest Nvidia earnings", session_id)

        called = False

        async def fake_search(*args, **kwargs):
            nonlocal called
            called = True
            return ResponseSearchResult(query="noop")

        monkeypatch.setattr("analytics.flows.tooling.perform_response_search", fake_search)

        result = await adapter.execute(context)

        assert result.status == "completed"
        assert result.payload["ready"] is True
        assert result.payload["from_cache"] is True
        assert result.metadata.get("cache_hit") is True
        assert called is False

    asyncio.run(run())


def test_web_retriever_triggers_search_and_caches(monkeypatch):
    async def run():
        session_id = "session-fresh"
        adapter = WebRetrieverAdapter()

        search_result = ResponseSearchResult(
            query="Latest Nvidia earnings",
            summary="Fresh summary",
            snippets=[
                SearchSnippet(
                    title="Article",
                    url="https://example.com",
                    snippet="Nvidia beat expectations last quarter.",
                )
            ],
            annotations=[{"url": "https://example.com", "title": "Article"}],
            usage={"total_tokens": 120},
            fetched_at="2025-10-02T12:00:00Z",
            latency_ms=128,
            model="gpt-test",
        )

        async def fake_search(query: str, **_: object) -> ResponseSearchResult:
            return search_result

        monkeypatch.setattr("analytics.flows.tooling.perform_response_search", fake_search)

        context = _make_context("Latest Nvidia earnings", session_id)
        result = await adapter.execute(context)

        assert result.status == "completed"
        assert result.payload["ready"] is True
        assert result.payload["from_cache"] is False
        assert result.payload["snippets"]
        assert result.metadata.get("snippets_count") == 1

        repo = get_session_state_repository()
        stored = await repo.load(session_id)
        assert stored is not None
        cached = stored.tool_cache.get("web_search")
        assert cached is not None
        assert cached.get("query") == "Latest Nvidia earnings"
        assert cached.get("ready") is True

    asyncio.run(run())


def test_web_retriever_handles_response_error(monkeypatch):
    async def run():
        adapter = WebRetrieverAdapter()
        context = _make_context("Latest Nvidia earnings", "session-error")

        async def failing_search(*args, **kwargs):
            raise ResponseSearchError("boom")

        monkeypatch.setattr("analytics.flows.tooling.perform_response_search", failing_search)

        result = await adapter.execute(context)

        assert result.status == "error"
        assert result.error == "boom"
        assert result.payload["ready"] is False
        assert result.metadata.get("preview_only") is True

    asyncio.run(run())
