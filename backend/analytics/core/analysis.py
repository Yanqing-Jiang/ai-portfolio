# --- Analytics Function/Class Map ---
# Function: _prepare_data_preview
#   Role: Handles prepare data preview logic for analytics.core.analysis.
#   Called from: Internal to analytics.core.analysis
#   Invokes: json.dumps
#   Why: Keeps analytics.core.analysis from duplicating prepare data preview behavior across flows.
# Function: _summarize_chart_spec
#   Role: Handles summarize chart spec logic for analytics.core.analysis.
#   Called from: Internal to analytics.core.analysis
#   Invokes: Internal helpers only
#   Why: Keeps analytics.core.analysis from duplicating summarize chart spec behavior across flows.
# Function: _summarize_search_result
#   Role: Handles summarize search result logic for analytics.core.analysis.
#   Called from: Internal to analytics.core.analysis
#   Invokes: Internal helpers only
#   Why: Keeps analytics.core.analysis from duplicating summarize search result behavior across flows.
# Function: _normalize_analysis_chunk
#   Role: Handles normalize analysis chunk logic for analytics.core.analysis.
#   Called from: Internal to analytics.core.analysis
#   Invokes: re.sub
#   Why: Keeps analytics.core.analysis from duplicating normalize analysis chunk behavior across flows.
# Function: _build_analysis_prompt
#   Role: Handles build analysis prompt logic for analytics.core.analysis.
#   Called from: Internal to analytics.core.analysis
#   Invokes: Internal helpers only
#   Why: Keeps analytics.core.analysis from duplicating build analysis prompt behavior across flows.
# Function: stream_insights_llm
#   Role: Handles stream insights llm logic for analytics.core.analysis.
#   Called from: analytics.flows.planner_executor
#   Invokes: analytics.core.analysis._prepare_data_preview, analytics.core.analysis._summarize_chart_spec, analytics.core.analysis._summarize_search_result, analytics.core.openai_client.get_openai_client, +2 more
#   Why: Keeps analytics.core.analysis from duplicating stream insights llm behavior across flows.
# --- End Analytics Function/Class Map ---
from __future__ import annotations
from typing import Dict, Any, List, AsyncGenerator, Optional
import json
import re
from .openai_client import get_openai_client
def _prepare_data_preview(rows: List[Dict[str, Any]], limit: int = 8) -> str:
    if not rows:
        return "No rows returned from SQL execution."
    preview = rows[:limit]
    try:
        return json.dumps(preview, indent=2, ensure_ascii=False)
    except Exception:
        return str(preview)
def _summarize_chart_spec(chart_spec: Optional[Dict[str, Any]]) -> str:
    if not isinstance(chart_spec, dict):
        return "No chart generated for this query."
    meta = chart_spec.get("meta") or {}
    design = meta.get("chartDesign") or {}
    summary_parts: List[str] = []
    chart_type = design.get("chart_type") or chart_spec.get("mark") or chart_spec.get("chartType")
    if chart_type:
        summary_parts.append(f"Chart type: {chart_type}.")
    measures = design.get("measure")
    if measures:
        if isinstance(measures, list):
            summary_parts.append("Measures: " + ", ".join(str(m) for m in measures))
        else:
            summary_parts.append(f"Measure: {measures}")
    grouping = design.get("grouping") or chart_spec.get("encoding", {}).get("color", {}).get("field")
    if grouping:
        summary_parts.append(f"Grouped by {grouping}.")
    if not summary_parts:
        summary_parts.append("Chart spec present but no additional metadata available.")
    return " ".join(summary_parts)
def _summarize_search_result(search_result: Optional[Any], article_limit: int = 3) -> str:
    if search_result is None:
        return "No external headlines retrieved."
    if hasattr(search_result, "to_payload"):
        payload = search_result.to_payload()
    elif isinstance(search_result, dict):
        payload = dict(search_result)
    else:
        return "No external headlines retrieved."
    summary_lines: List[str] = []
    summary_text = payload.get("summary")
    if isinstance(summary_text, str) and summary_text.strip():
        summary_lines.append(summary_text.strip())
    snippets = payload.get("snippets")
    if isinstance(snippets, list):
        for idx, snippet in enumerate(snippets[:article_limit], start=1):
            if not isinstance(snippet, dict):
                continue
            headline = snippet.get("title") or snippet.get("display_url") or snippet.get("url")
            note = snippet.get("snippet")
            pub_date = snippet.get("published_at")
            parts: List[str] = []
            if headline:
                parts.append(f"[{idx}] {headline}")
            if note:
                parts.append(note)
            if pub_date:
                parts.append(f"Published: {pub_date}")
            if parts:
                summary_lines.append(" ".join(parts))
    if not summary_lines:
        return "External search completed but produced no snippets."
    return "\n".join(summary_lines)

_PROMPT_INSTRUCTIONS = (
    "You are an equity research assistant. Fuse fundamentals, chart behaviour, and fresh headlines into a single cohesive story.\n"
    "Output requirements:\n"
    "1. Begin with `TL;DR:` followed by two concise sentences covering web research result, metrics, and chart direction.\n"
    "2. Add a `Key points:` heading and provide 3-5 markdown bullets (each starting with `- `) mixing SQL values, chart takeaways, and headline references using bracketed [n] citations.\n"
    "3. When fundamentals and headlines diverge, append a `Watchouts:` sentence after the bullets.\n"
    "4. Return clean markdown only - avoid raw JSON or code fences unless explicitly asked.\n"
)


def _normalize_analysis_chunk(chunk: str) -> str:
    if not chunk:
        return chunk
    normalized = chunk.replace("\r\n", "\n")
    normalized = re.sub(r"\n{3,}", "\n\n", normalized)
    if normalized.lstrip().startswith("```json"):
        normalized = normalized.replace("```json", "```", 1)
    return normalized
def _build_analysis_prompt(
    *,
    query: str,
    sql: str,
    data_preview: str,
    chart_summary: str,
    news_summary: str,
    focus: Optional[str] = None,
) -> str:
    focus_block = ""
    if focus:
        focus_block = f"\nFollow-up emphasis: {focus}"
    # Post-clarification guardrail: the user-facing questions were already asked upstream.
    no_more_questions = (
        "\nDo NOT ask the user any more questions. Assume the provided inputs and defaults are final; "
        "deliver the analysis with the data you have."
    )
    return f"""
User question: {query}
SQL query executed:
{sql}
SQL result:
{data_preview}
Chart summary:
{chart_summary}
Headline summary (ordered for references):
{news_summary}
{focus_block}
{no_more_questions}
{_PROMPT_INSTRUCTIONS}
""".strip()
async def stream_insights_llm(
    data: List[Dict[str, Any]],
    sql: str,
    query: str,
    *,
    chart_spec: Optional[Dict[str, Any]] = None,
    search_result: Optional[Any] = None,
    session_id: Optional[str] = None,
    focus: Optional[str] = None,
) -> AsyncGenerator[str, None]:
    data_preview = _prepare_data_preview(data)
    chart_summary = _summarize_chart_spec(chart_spec)
    news_summary = _summarize_search_result(search_result)
    client = get_openai_client()
    if not client:
        yield "TL;DR: Analysis unavailable because no OpenAI credentials are configured.\n"
        yield "Key points:\n"
        yield f"- SQL insight preview: {data_preview[:240]}...\n"
        yield f"- Chart summary: {chart_summary}\n"
        yield f"- Headlines: {news_summary}\n"
        return
    system_prompt = "You are an equity research assistant who writes concise markdown narratives with TL;DR and bullet points."
    user_prompt = _build_analysis_prompt(
        query=query,
        sql=sql,
        data_preview=data_preview,
        chart_summary=chart_summary,
        news_summary=news_summary,
        focus=focus,
    )
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]
    async for chunk in client.stream_completion(messages, session_id=session_id):
        if chunk:
            yield _normalize_analysis_chunk(chunk)
