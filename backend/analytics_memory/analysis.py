from __future__ import annotations
from typing import Dict, Any, List, AsyncGenerator, Optional
import os

from .openai_client import get_openai_client


def summarize(data: List[Dict[str, Any]], sql: str, query: str) -> str:
    return "Analysis will stream here (Phase 2/3)."


async def stream_insights_llm(data: List[Dict[str, Any]], sql: str, query: str, session_id: Optional[str] = None) -> AsyncGenerator[str, None]:
    client = get_openai_client()
    if not client:
        # Fallback: yield a simple summary
        yield "- Analysis unavailable (no API key). Showing data sample instead.\n"
        for row in data[:3]:
            yield f"- Sample row: {row}\n"
        return

    data_preview = data[:8]
    prompt = f"""
You are a concise financial analyst. Provide a TLDR to summerize the data. Then 2-3 bullets to highlight your findings.

USER QUESTION:
{query}

SQL USED:
{sql}

DATA PREVIEW (first rows):
{data_preview}
"""
    
    messages = [
        {"role": "system", "content": prompt}
    ]
    
    async for chunk in client.stream_completion(messages, session_id=session_id):
        if chunk:
            yield chunk
