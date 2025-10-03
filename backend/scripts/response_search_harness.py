import asyncio
import json
import os
import sys
from typing import Any

from analytics.services.response_search import ResponseSearchError, perform_response_search


async def _run(query: str) -> int:
    provider = os.getenv("OPENAI_API_TYPE", "openai").lower()
    if provider == "azure":
        print("Responses API web_search_preview is not yet supported on Azure; skipping live check.")
        return 0

    if not os.getenv("OPENAI_API_KEY"):
        print("OPENAI_API_KEY not set; skipping live web search test.")
        return 0

    try:
        result = await perform_response_search(query, session_id="response_search_harness")
    except ResponseSearchError as exc:
        print(f"Responses API web search failed: {exc}")
        return 1

    payload: dict[str, Any] = {
        "query": result.query,
        "summary": result.summary,
        "snippets": [
            {"title": s.title, "url": s.url, "snippet": s.snippet}
            for s in (result.snippets or [])
        ],
        "search_id": result.search_id,
        "latency_ms": result.latency_ms,
        "model": result.model,
    }
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0


def main(argv: list[str]) -> int:
    query = "Nvidia latest earnings" if len(argv) < 2 else " ".join(argv[1:])
    return asyncio.run(_run(query))


if __name__ == "__main__":
    sys.exit(main(sys.argv))
