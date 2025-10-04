"""Web search tool leveraging the Responses API integration."""
from __future__ import annotations

from typing import Any, Dict, Optional

from analytics.services.response_search import ResponseSearchError, perform_response_search

from ..tool_registry import AnalyticsTool, ToolSpec


class WebSearchTool(AnalyticsTool):
    """Executes web search via the unified Responses client."""

    def __init__(self) -> None:
        spec = ToolSpec(
            name="web.search",
            description="Run a web search using the configured Responses client and return snippets.",
            input_schema={
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "session_id": {"type": ["string", "null"]},
                    "context": {"type": ["string", "null"]},
                    "context_size": {"type": ["string", "null"]},
                    "model": {"type": ["string", "null"]},
                },
                "required": ["query"],
            },
            output_schema={
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "summary": {"type": ["string", "null"]},
                    "snippets": {
                        "type": "array",
                        "items": {"type": "object"},
                    },
                    "annotations": {
                        "type": "array",
                        "items": {"type": "object"},
                    },
                },
            },
        )
        super().__init__(spec)

    async def ainvoke(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        query = payload.get("query")
        if not query:
            raise ValueError("'query' is required for web.search")
        session_id: Optional[str] = payload.get("session_id")
        context: Optional[str] = payload.get("context")
        context_size: Optional[str] = payload.get("context_size")
        model: Optional[str] = payload.get("model")
        try:
            result = await perform_response_search(
                query,
                session_id=session_id,
                context=context,
                context_size=context_size,
                model=model,
            )
        except ResponseSearchError as exc:
            raise RuntimeError(f"Web search failed: {exc}") from exc
        payload_dict = result.to_payload()
        payload_dict.update({
            "latency_ms": result.latency_ms,
            "model": result.model,
            "from_cache": result.from_cache,
        })
        return payload_dict
