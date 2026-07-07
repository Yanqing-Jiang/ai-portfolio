from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from homer_memory import routes  # noqa: E402
from homer_memory.search import (  # noqa: E402
    CorpusClaim,
    LegResult,
    claim_tier_multiplier,
    fuse_candidates,
    recency_multiplier,
    search_memory,
)


def _claim(
    claim_id: str,
    *,
    content: str = "memory retrieval claim",
    status: str = "approved",
    created_at: str = "2026-07-01",
    embedding: tuple[float, ...] = (),
) -> CorpusClaim:
    return CorpusClaim(
        id=claim_id,
        content=content,
        claim_type="fact",
        target="memory",
        confidence=0.9,
        status=status,
        created_at=created_at,
        embedding=embedding,
    )


def test_rrf_prefers_claim_present_in_both_legs():
    claims = (
        _claim("a", content="lexical only"),
        _claim("b", content="hybrid result"),
        _claim("c", content="vector only"),
    )
    hits = fuse_candidates(
        claims,
        [
            LegResult(claim_id="a", rank=1, score=7.0),
            LegResult(claim_id="b", rank=2, score=3.0),
        ],
        [
            LegResult(claim_id="b", rank=1, score=0.91),
            LegResult(claim_id="c", rank=2, score=0.88),
        ],
        query="hybrid memory",
        now=datetime(2026, 7, 7, tzinfo=timezone.utc),
    )

    assert [hit.claim.id for hit in hits] == ["b", "a", "c"]
    assert hits[0].trace.bm25_rank == 2
    assert hits[0].trace.vector_rank == 1
    assert hits[0].trace.rrf_score == pytest.approx((1 / 22) + (1 / 21))


def test_tier_and_recency_multipliers_match_homer_constants():
    now = datetime(2026, 7, 7, tzinfo=timezone.utc)

    assert claim_tier_multiplier("approved", False) == pytest.approx(1.02)
    assert claim_tier_multiplier("approved", True) == pytest.approx(1.20)
    assert claim_tier_multiplier("candidate", False) == pytest.approx(0.90)
    assert claim_tier_multiplier("archived", False) == pytest.approx(0.85)
    assert recency_multiplier("2026-07-07", now) == pytest.approx(1.0)
    assert recency_multiplier("2026-04-08", now) == pytest.approx(0.875, abs=0.002)


def test_degraded_lexical_only_search_uses_bm25_without_vectors():
    claims = (
        _claim("sqlite", content="Homer stores operational claims in SQLite with FTS5 indexing."),
        _claim("voice", content="Homer uses a managed voice agent for phone escalation."),
    )

    response = search_memory(
        "SQLite FTS5 claims",
        claims=claims,
        query_embedding=None,
        query_embedding_ms=None,
        vector_unavailable_reason="embedding unavailable",
        now=datetime(2026, 7, 7, tzinfo=timezone.utc),
    )

    assert response.meta.vector_leg == "unavailable"
    assert response.meta.legs_used == ("bm25",)
    assert response.hits[0].claim.id == "sqlite"
    assert response.hits[0].trace.vector_rank is None
    assert response.hits[0].trace.bm25_rank == 1


def test_rate_limit_response_shape(monkeypatch):
    async def fake_search(query: str):
        return {
            "query": query,
            "vector_leg": "unavailable",
            "results": [],
            "meta": {
                "query_embedding_ms": None,
                "legs_used": ["bm25"],
                "corpus_size": 0,
                "fused_candidates": 0,
            },
        }

    monkeypatch.setattr(routes, "run_memory_search_async", fake_search)
    monkeypatch.setattr(routes, "redis_pool", None)
    monkeypatch.setattr(routes, "ANON_HOURLY_LIMIT", 1)
    monkeypatch.setenv("DISABLE_RATE_LIMIT", "false")
    routes._in_memory_hourly_usage.clear()

    app = FastAPI()
    app.include_router(routes.router)
    client = TestClient(app)

    first = client.post("/api/homer/memory-search", json={"query": "memory ranking"})
    second = client.post("/api/homer/memory-search", json={"query": "memory ranking"})

    assert first.status_code == 200
    assert second.status_code == 429
    assert second.headers.get("retry-after")
    detail = second.json()["detail"]
    assert detail["error"] == "rate_limited"
    assert "hourly window" in detail["message"]


def test_html_queries_are_rejected(monkeypatch):
    async def fake_search(query: str):
        return {"query": query, "vector_leg": "unavailable", "results": [], "meta": {}}

    monkeypatch.setattr(routes, "run_memory_search_async", fake_search)
    monkeypatch.setattr(routes, "ANON_HOURLY_LIMIT", 20)
    monkeypatch.setenv("DISABLE_RATE_LIMIT", "false")
    routes._in_memory_hourly_usage.clear()

    app = FastAPI()
    app.include_router(routes.router)
    client = TestClient(app)
    response = client.post("/api/homer/memory-search", json={"query": "<b>memory</b>"})

    assert response.status_code == 400
    assert "HTML" in response.json()["detail"]
