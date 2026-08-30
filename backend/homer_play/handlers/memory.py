from __future__ import annotations

from dataclasses import dataclass

from homer_memory.embeddings import EmbeddingUnavailable, embed_query
from homer_memory.routes import _corpus, _sanitize_query
from homer_memory.search import response_to_dict, search_memory

from ..bridge import BridgeClient
from ..models import MemoryExtractData, MemoryExtractRequest, MemorySearchData, MemorySearchRequest


@dataclass(frozen=True)
class HandlerResult:
    data: dict
    charged_micro_usd: int


async def run_search(payload: MemorySearchRequest) -> HandlerResult:
    query = _sanitize_query(payload.message)
    query_embedding = None
    elapsed_ms = None
    vector_error = None
    if any(claim.embedding for claim in _corpus):
        try:
            query_embedding, elapsed_ms = await embed_query(query)
        except (EmbeddingUnavailable, Exception):
            vector_error = "query embedding unavailable"
    else:
        vector_error = "corpus embeddings unavailable"
    result = search_memory(
        query,
        claims=_corpus,
        query_embedding=query_embedding,
        query_embedding_ms=elapsed_ms,
        vector_unavailable_reason=vector_error,
        limit=payload.input.limit,
    )
    raw = response_to_dict(query, result)
    data = MemorySearchData.model_validate(raw)
    # The embedding helper exposes no provider usage, so retain the full
    # conservative reservation as required by the spend ledger contract.
    return HandlerResult(data.model_dump(mode="json"), 20)


async def run_extract(
    payload: MemoryExtractRequest,
    bridge: BridgeClient,
    *,
    request_id: str,
) -> HandlerResult:
    raw = await bridge.execute(
        "memory.extract_dry_run",
        {"text": payload.message, "target": payload.input.target},  # bridge field is `text`
        request_id=request_id,
        timeout_seconds=18.0,
    )
    data = MemoryExtractData.model_validate(raw)
    # The public bridge response intentionally excludes provider usage. Retain
    # the full reservation rather than undercharging from a local estimate.
    return HandlerResult(data.model_dump(mode="json"), 1_500)
