from __future__ import annotations

import html
import logging
import os
import re
import time
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

try:
    from rate_limiter import who_am_i, is_superuser, redis_pool
except ImportError:  # pragma: no cover - support module execution
    from ..rate_limiter import who_am_i, is_superuser, redis_pool  # type: ignore

from .embeddings import EmbeddingUnavailable, embed_query
from .search import load_corpus, response_to_dict, search_memory


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/homer", tags=["homer-memory"])

ANON_HOURLY_LIMIT = int(os.getenv("HOMER_MEMORY_SEARCH_ANON_LIMIT", "20"))
AUTH_HOURLY_LIMIT = int(os.getenv("HOMER_MEMORY_SEARCH_AUTH_LIMIT", "80"))
WINDOW_SECONDS = 60 * 60
HTML_RE = re.compile(r"<[^>]+>")

_corpus = load_corpus()
_in_memory_hourly_usage: dict[str, tuple[int, int]] = {}


class MemorySearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=200)


def _sanitize_query(raw_query: str) -> str:
    query = raw_query.strip()
    if not query:
        raise HTTPException(status_code=400, detail="Query cannot be empty.")
    if HTML_RE.search(query) or HTML_RE.search(html.unescape(query)):
        raise HTTPException(status_code=400, detail="HTML is not accepted in memory search queries.")
    return query


def _window_key(identifier: str, now: int | None = None) -> tuple[str, int, int]:
    now = now or int(time.time())
    window = now // WINDOW_SECONDS
    reset_epoch = (window + 1) * WINDOW_SECONDS
    return f"homer-memory-search:{identifier}:{window}", reset_epoch, now


async def _enforce_hourly_rate_limit(request: Request) -> None:
    """Use shared identity/IP resolution, but keep this public demo on an hourly window."""
    if os.getenv("DISABLE_RATE_LIMIT", "false").lower() == "true":
        return

    identifier = await who_am_i(request)
    if is_superuser(request):
        return

    is_authenticated = not identifier.startswith("ip:")
    limit = AUTH_HOURLY_LIMIT if is_authenticated else ANON_HOURLY_LIMIT
    key, reset_epoch, now = _window_key(identifier)
    retry_after = str(max(1, reset_epoch - now))

    if redis_pool is not None:
        try:
            current = await redis_pool.incr(key)
            ttl = await redis_pool.ttl(key)
            if ttl is None or ttl <= 0:
                await redis_pool.expire(key, max(1, reset_epoch - now))
            if int(current) > limit:
                raise HTTPException(
                    status_code=429,
                    detail={
                        "error": "rate_limited",
                        "message": "Too many Homer memory searches from this IP. Try again after the hourly window resets.",
                        "reset_epoch": reset_epoch,
                    },
                    headers={"Retry-After": retry_after},
                )
            request.state.homer_memory_rate_limit = {
                "count": int(current),
                "limit": limit,
                "reset_epoch": reset_epoch,
            }
            return
        except HTTPException:
            raise
        except Exception as exc:
            logger.warning("Homer memory Redis rate limit failed; using in-memory fallback: %s", exc)

    current, existing_reset = _in_memory_hourly_usage.get(key, (0, reset_epoch))
    if existing_reset <= now:
        current = 0
        existing_reset = reset_epoch
    current += 1
    _in_memory_hourly_usage[key] = (current, existing_reset)
    if current > limit:
        raise HTTPException(
            status_code=429,
            detail={
                "error": "rate_limited",
                "message": "Too many Homer memory searches from this IP. Try again after the hourly window resets.",
                "reset_epoch": existing_reset,
            },
            headers={"Retry-After": str(max(1, existing_reset - now))},
        )
    request.state.homer_memory_rate_limit = {
        "count": current,
        "limit": limit,
        "reset_epoch": existing_reset,
    }


async def run_memory_search_async(query: str) -> dict[str, Any]:
    query_embedding = None
    elapsed_ms = None
    vector_error = None

    if any(claim.embedding for claim in _corpus):
        try:
            query_embedding, elapsed_ms = await embed_query(query)
        except (EmbeddingUnavailable, Exception) as exc:
            vector_error = str(exc)
            logger.info("Homer memory vector leg unavailable: %s", exc)
    else:
        vector_error = "Corpus embeddings are empty"

    data = search_memory(
        query,
        claims=_corpus,
        query_embedding=query_embedding,
        query_embedding_ms=elapsed_ms,
        vector_unavailable_reason=vector_error,
    )
    return response_to_dict(query, data)


@router.post("/memory-search")
async def memory_search(payload: MemorySearchRequest, request: Request) -> dict[str, Any]:
    await _enforce_hourly_rate_limit(request)
    query = _sanitize_query(payload.query)
    return await run_memory_search_async(query)
