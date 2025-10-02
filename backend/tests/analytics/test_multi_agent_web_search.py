import asyncio
import pytest
from types import SimpleNamespace

from analytics.flows.multi_agent import _web_research_agent
from analytics.flows.orchestrator import AgentRunContext
from analytics.core.session_state import SessionStateSnapshot, close_session_state_repository, get_session_state_repository
from analytics.services.response_search import ResponseSearchResult, SearchSnippet


@pytest.fixture(autouse=True)
def reset_repo():
    asyncio.run(close_session_state_repository())
    yield
    asyncio.run(close_session_state_repository())


def test_web_research_agent_fetches_and_caches(monkeypatch):
    async def run():
        session_id = "test-session"
        repo = get_session_state_repository()
        snapshot = SessionStateSnapshot(session_id=session_id)
        await repo.save(snapshot)

        search_result = ResponseSearchResult(
            query="Latest Nvidia earnings",
            summary="Fresh web summary",
            snippets=[
                SearchSnippet(
                    title="Article",
                    url="https://example.com",
                    snippet="Latest guidance from Nvidia.",
                )
            ],
            annotations=[{"url": "https://example.com", "title": "Article"}],
            usage={"total_tokens": 42},
            fetched_at="2025-10-02T12:00:00Z",
            latency_ms=150,
            model="gpt-test",
        )

        async def fake_search(query: str, **kwargs):
            return search_result

        monkeypatch.setattr("analytics.flows.multi_agent.perform_response_search", fake_search)

        shared = {
            'query': 'Nvidia revenue Q2 2024',
            'planner': {'tickers': ['NVDA']},
            'web': {},
        }
        context = AgentRunContext(
            query='Nvidia revenue Q2 2024',
            session_id=session_id,
            shared=shared,
            dependencies={},
            inputs={},
        )

        result = await _web_research_agent(context)

        assert result.output.get('status') == 'run'
        assert result.output.get('snippets')
        assert shared['web'].get('snippets')
        cached = (await repo.load(session_id)).tool_cache.get('web_search')
        assert cached is not None
        assert cached.get('query') == 'Nvidia revenue Q2 2024'

    asyncio.run(run())


def test_web_research_agent_reuses_cache(monkeypatch):
    async def run():
        session_id = "cached-session"
        repo = get_session_state_repository()
        snapshot = SessionStateSnapshot(
            session_id=session_id,
            tool_cache={'web_search': {
                'query': 'Nvidia revenue Q2 2024',
                'summary': 'Cached summary',
                'snippets': [{'title': 'Cached', 'url': 'https://example.com'}],
                'ready': True,
                'from_cache': True,
            }}
        )
        await repo.save(snapshot)

        called = False

        async def fake_search(*args, **kwargs):
            nonlocal called
            called = True
            return ResponseSearchResult(query='noop')

        monkeypatch.setattr("analytics.flows.multi_agent.perform_response_search", fake_search)

        shared = {
            'query': 'Nvidia revenue Q2 2024',
            'planner': {'tickers': ['NVDA']},
            'web': {
                'query': 'Nvidia revenue Q2 2024',
                'snippets': [{'title': 'Cached', 'url': 'https://example.com'}],
                'ready': True,
                'from_cache': True,
            },
        }
        context = AgentRunContext(
            query='Nvidia revenue Q2 2024',
            session_id=session_id,
            shared=shared,
            dependencies={},
            inputs={},
        )

        result = await _web_research_agent(context)
        assert result.output.get('status') == 'reuse'
        assert shared['web'].get('from_cache') is True
        cached = shared['web'].get('snippets')
        assert cached and cached[0]['title'] == 'Cached'
        assert called is False

    asyncio.run(run())
