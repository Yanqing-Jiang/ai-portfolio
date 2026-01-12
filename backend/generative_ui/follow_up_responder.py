# --- Follow-up Responder Function/Class Map ---
# Function: build_follow_up_answer — generate a data-aware answer for follow-up queries.
#   Called from: backend.generative_ui.routes.dashboard._handle_follow_up.
#   Invokes: _summarize_kpis, _summarize_table_rows, _format_value.
#   Why: Replaces placeholder follow-up responses with data-aware summaries.
# Function: _summarize_kpis — build a concise KPI summary line.
#   Called from: build_follow_up_answer.
#   Invokes: _format_value.
#   Why: Provides quick numeric context for summaries and explanations.
# Function: _summarize_table_rows — build a concise table summary line.
#   Called from: build_follow_up_answer.
#   Invokes: _format_value.
#   Why: Surfaces comparison context when table data is present.
# Function: _format_value — format numeric values for display.
#   Called from: _summarize_kpis, _summarize_table_rows.
#   Invokes: n/a.
#   Why: Keeps numeric formatting consistent across follow-up answers.
# --- End Follow-up Responder Function/Class Map ---
"""
Follow-up responder utilities.

Provides data-aware answers for follow-up questions using the current data model.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional


def _format_value(value: Any, key: str = "") -> str:
    """
    Format a numeric value for follow-up answers.
    
    Function: _format_value — normalize numeric display for KPIs and tables.
    Called from: _summarize_kpis, _summarize_table_rows.
    Invokes: n/a.
    Why: Keeps follow-up answers concise and readable.
    """
    if value is None:
        return "n/a"
    if isinstance(value, (int, float)):
        if any(token in key.lower() for token in ("margin", "rate", "yoy", "delta", "change", "pct", "%")):
            return f"{value:.2f}%"
        if abs(value) >= 1_000_000:
            return f"${value / 1_000_000:.2f}M"
        if abs(value) >= 1_000:
            return f"${value:,.0f}"
        return f"{value:.2f}"
    return str(value)


def _summarize_kpis(kpis: Dict[str, Any]) -> str:
    """
    Build a concise KPI summary string.
    
    Function: _summarize_kpis — extract key KPI highlights.
    Called from: build_follow_up_answer.
    Invokes: _format_value.
    Why: Adds quick numeric context to follow-up answers.
    """
    if not kpis:
        return ""

    summary_parts: List[str] = []
    for key, value in kpis.items():
        if value is None:
            continue
        if any(token in key.lower() for token in ("delta", "compare")):
            continue
        summary_parts.append(f"{key.replace('_', ' ').title()}: {_format_value(value, key)}")
        if len(summary_parts) >= 3:
            break

    return "; ".join(summary_parts)


def _summarize_table_rows(rows: List[Dict[str, Any]], primary_ticker: str) -> str:
    """
    Build a concise table summary string.
    
    Function: _summarize_table_rows — extract leader or primary row highlights.
    Called from: build_follow_up_answer.
    Invokes: _format_value.
    Why: Adds comparison context when tabular data exists.
    """
    if not rows:
        return ""

    target_row = None
    for row in rows:
        if str(row.get("ticker", "")).upper() == primary_ticker.upper():
            target_row = row
            break

    if target_row is None:
        target_row = rows[0]

    latest_value = target_row.get("latest_value")
    yoy_change = target_row.get("yoy_change")
    ticker = target_row.get("ticker", primary_ticker)

    parts = [f"{ticker} latest: {_format_value(latest_value, 'latest_value')}"]
    if yoy_change is not None:
        parts.append(f"YoY: {_format_value(yoy_change, 'yoy_change')}")
    return "; ".join(parts)


def build_follow_up_answer(
    question_type: Optional[str],
    target_element: Optional[str],
    data_model: Dict[str, Any],
    skill_id: Optional[str],
    tickers: List[str],
) -> str:
    """
    Generate a data-aware response for follow-up questions.
    
    Function: build_follow_up_answer — produce concise follow-up answers.
    Called from: backend.generative_ui.routes.dashboard._handle_follow_up.
    Invokes: _summarize_kpis, _summarize_table_rows, _format_value.
    Why: Replaces placeholder answers with data-backed responses.
    """
    kpis = data_model.get("kpis", {}) if isinstance(data_model, dict) else {}
    table_rows = data_model.get("table", {}).get("rows", []) if isinstance(data_model, dict) else []
    explanation = data_model.get("explanation", {}) if isinstance(data_model, dict) else {}
    primary_ticker = tickers[0] if tickers else ""

    if question_type in ("explain", "detail") and isinstance(explanation, dict):
        explanation_text = explanation.get("text")
        if isinstance(explanation_text, str) and explanation_text.strip():
            return explanation_text.strip()

    if target_element:
        target_lower = target_element.lower()
        for key, value in kpis.items():
            if target_lower in key.lower():
                return f"{key.replace('_', ' ').title()} is {_format_value(value, key)}."

    kpi_summary = _summarize_kpis(kpis)
    table_summary = _summarize_table_rows(table_rows, primary_ticker)

    if question_type == "summarize":
        summary = "; ".join(part for part in [kpi_summary, table_summary] if part)
        return summary or "No summary available yet."

    if question_type == "compare" and table_rows:
        leader = max(table_rows, key=lambda row: row.get("latest_value") or 0)
        leader_ticker = leader.get("ticker", primary_ticker)
        leader_value = _format_value(leader.get("latest_value"), "latest_value")
        return f"Leader: {leader_ticker} at {leader_value}. {table_summary}".strip()

    if question_type == "predict":
        summary = "; ".join(part for part in [kpi_summary, table_summary] if part)
        return summary or "No forecast model available; use recent KPIs and trends as context."

    summary = "; ".join(part for part in [kpi_summary, table_summary] if part)
    return summary or "No additional data available for this follow-up."
