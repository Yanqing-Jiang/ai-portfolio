from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Any

from homer_memory.embeddings import EmbeddingUnavailable, embed_query
from homer_memory.routes import _corpus
from homer_memory.search import BM25Index, response_to_dict, search_memory

from ..bridge import BridgeClient
from ..models import (
    MCP_ARGUMENT_MODEL_BY_TOOL,
    McpCallData,
    McpCallRequest,
    McpMemoryContextArguments,
    McpMemoryContextData,
    McpMemorySearchArguments,
    McpPreferenceData,
    McpPreferenceQueryArguments,
    McpTodoListArguments,
    McpTodoSummaryData,
    MemorySearchData,
)


PUBLIC_MCP_TOOL_NAMES = frozenset(
    {"memory_search", "memory_context", "preference_query", "todo_list"}
)

PUBLIC_MCP_TOOLS: tuple[dict[str, Any], ...] = (
    {
        "name": "memory_search",
        "description": (
            "Recall from the public Homer architecture corpus with ranked lexical and vector search. "
            "Returns approved public claims and retrieval trace data."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query (supports terms and phrase-like matching).",
                },
                "limit": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 4,
                    "default": 4,
                    "description": "Maximum public claims to return.",
                },
            },
            "required": ["query"],
            "additionalProperties": False,
        },
        "data_source": "public_corpus",
        "side_effect_class": "none",
    },
    {
        "name": "memory_context",
        "description": (
            "Returns top approved public claims for a target, grouped by claim type. "
            "No LLM call; pure in-process public-corpus read."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "target": {
                    "type": "string",
                    "pattern": "^[a-z][a-z0-9_-]*$",
                    "description": "Optional public target such as architecture, memory, or ops.",
                },
                "limit": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 6,
                    "default": 6,
                    "description": "Maximum approved claims to return.",
                },
            },
            "additionalProperties": False,
        },
        "data_source": "public_corpus",
        "side_effect_class": "none",
    },
    {
        "name": "preference_query",
        "description": (
            "Query the public architecture preference model for learned preferences. "
            "Returns top matching public preferences with lexical scores."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "topic": {
                    "type": "string",
                    "description": "Architecture preference topic to match.",
                },
            },
            "required": ["topic"],
            "additionalProperties": False,
        },
        "data_source": "public_corpus",
        "side_effect_class": "none",
    },
    {
        "name": "todo_list",
        "description": (
            "List a public-safe aggregate of open To-Dos, grouped by priority and category. "
            "Returns no titles, notes, identifiers, or checklist content."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "status": {
                    "type": "string",
                    "enum": ["open"],
                    "default": "open",
                    "description": "The public facade supports open To-Dos only.",
                },
            },
            "additionalProperties": False,
        },
        "data_source": "live_bridge",
        "side_effect_class": "none",
    },
)


@dataclass(frozen=True)
class McpHandlerResult:
    data: dict[str, Any]
    charged_micro_usd: int
    source: str
    reply: str


def list_public_tools() -> dict[str, Any]:
    return {
        "protocol": "mcp",
        "tools": [dict(tool) for tool in PUBLIC_MCP_TOOLS],
        "hidden_tool_count": 0,
    }


async def _memory_search(arguments: McpMemorySearchArguments) -> tuple[dict[str, Any], str, int]:
    query_embedding = None
    elapsed_ms = None
    vector_error = None
    if any(claim.embedding for claim in _corpus):
        try:
            query_embedding, elapsed_ms = await embed_query(arguments.query)
        except (EmbeddingUnavailable, Exception):
            vector_error = "query embedding unavailable"
    else:
        vector_error = "corpus embeddings unavailable"
    result = search_memory(
        arguments.query,
        claims=_corpus,
        query_embedding=query_embedding,
        query_embedding_ms=elapsed_ms,
        vector_unavailable_reason=vector_error,
        limit=arguments.limit,
    )
    data = MemorySearchData.model_validate(response_to_dict(arguments.query, result))
    return (
        data.model_dump(mode="json"),
        f"Found {len(data.results)} matching public memory claims.",
        20,
    )


def _memory_context(arguments: McpMemoryContextArguments) -> tuple[dict[str, Any], str, int]:
    eligible = [
        claim
        for claim in _corpus
        if claim.status == "approved"
        and (arguments.target is None or claim.target == arguments.target)
    ]
    eligible.sort(key=lambda claim: (-claim.confidence, claim.created_at, claim.id))
    selected = eligible[: arguments.limit]
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for claim in selected:
        grouped[claim.claim_type].append(
            {
                "id": claim.id,
                "content": claim.content,
                "target": claim.target,
                "status": "approved",
                "created_at": claim.created_at,
            }
        )
    raw = {
        "target": arguments.target,
        "groups": [
            {"claim_type": claim_type, "claims": grouped[claim_type]}
            for claim_type in sorted(grouped)
        ],
        "meta": {"claims_returned": len(selected), "corpus_size": len(_corpus)},
    }
    data = McpMemoryContextData.model_validate(raw)
    return (
        data.model_dump(mode="json"),
        f"Returned {len(selected)} approved public claims across {len(grouped)} claim types.",
        0,
    )


def _preference_query(arguments: McpPreferenceQueryArguments) -> tuple[dict[str, Any], str, int]:
    preferences = [
        claim for claim in _corpus if claim.status == "approved" and claim.claim_type == "preference"
    ]
    ranked = BM25Index(preferences).search(arguments.topic)[:6]
    by_id = {claim.id: claim for claim in preferences}
    hits = []
    for result in ranked:
        claim = by_id[result.claim_id]
        hits.append(
            {
                "id": claim.id,
                "content": claim.content,
                "target": claim.target,
                "status": "approved",
                "created_at": claim.created_at,
                "bm25_score": round(result.score, 6),
            }
        )
    data = McpPreferenceData.model_validate(
        {
            "topic": arguments.topic,
            "preferences": hits,
            "meta": {
                "preference_claims_scanned": len(preferences),
                "matches_returned": len(hits),
            },
        }
    )
    return (
        data.model_dump(mode="json"),
        f"Found {len(hits)} matching public architecture preferences.",
        0,
    )


async def _todo_list(
    arguments: McpTodoListArguments,
    bridge: BridgeClient,
    request_id: str,
) -> tuple[dict[str, Any], str, int]:
    raw = await bridge.execute(
        "todo.summary",
        {"status": arguments.status},
        request_id=request_id,
        timeout_seconds=1.5,
    )
    data = McpTodoSummaryData.model_validate(raw)
    return (
        data.model_dump(mode="json"),
        f"Open To-Dos: {data.open.total}; completed in the last 7 days: {data.done_last_7_days}.",
        0,
    )


async def run_mcp_call(
    payload: McpCallRequest,
    bridge: BridgeClient,
    *,
    request_id: str,
) -> McpHandlerResult:
    tool = payload.input.tool
    arguments = MCP_ARGUMENT_MODEL_BY_TOOL[tool].model_validate(payload.input.arguments)
    if tool == "memory_search":
        structured, summary, charged = await _memory_search(arguments)
        handler = "public_memory_search"
        source = "public_corpus"
    elif tool == "memory_context":
        structured, summary, charged = _memory_context(arguments)
        handler = "public_memory_context"
        source = "public_corpus"
    elif tool == "preference_query":
        structured, summary, charged = _preference_query(arguments)
        handler = "public_preference_query"
        source = "public_corpus"
    elif tool == "todo_list":
        structured, summary, charged = await _todo_list(arguments, bridge, request_id)
        handler = "public_todo_summary"
        source = "live_bridge"
    else:  # The route allowlist closes this path before dispatch.
        raise ValueError("tool_not_allowed")

    data = McpCallData.model_validate(
        {
            "protocol": "mcp",
            "tool": tool,
            "content": [{"type": "text", "text": summary}],
            "structured_content": structured,
            "is_error": False,
            "trace": {"allowlist_match": True, "handler": handler},
        }
    )
    return McpHandlerResult(
        data=data.model_dump(mode="json"),
        charged_micro_usd=charged,
        source=source,
        reply=summary,
    )
