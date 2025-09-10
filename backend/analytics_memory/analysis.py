from __future__ import annotations
from typing import Dict, Any, List, AsyncGenerator
import os

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage


def summarize(data: List[Dict[str, Any]], sql: str, query: str) -> str:
    return "Analysis will stream here (Phase 2/3)."


async def stream_insights_llm(data: List[Dict[str, Any]], sql: str, query: str) -> AsyncGenerator[str, None]:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        # Fallback: yield a simple summary
        yield "- Analysis unavailable (no API key). Showing data sample instead.\n"
        for row in data[:3]:
            yield f"- Sample row: {row}\n"
        return

    llm = ChatOpenAI(model="gpt-4o-mini-2024-07-18", api_key=api_key, temperature=0, streaming=True)
    data_preview = data[:8]
    prompt = f"""
You are a concise financial analyst. Provide 4-6 bullet insights with concrete numbers and time references.

USER QUESTION:
{query}

SQL USED:
{sql}

DATA PREVIEW (first rows):
{data_preview}
"""
    async for chunk in llm.astream([SystemMessage(content=prompt)]):
        if hasattr(chunk, 'content') and chunk.content:
            yield chunk.content
