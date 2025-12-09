# --- Analytics Function/Class Map ---
# Function: _set_analysis_artifact
#   Role: Build analysis artifact with evidence/web/stock context.
#   Called from: analytics.flows.planner_executor analysis phase helpers
#   Invokes: analytics.artifacts.AnalysisArtifact, analytics.flows.planner.stage_helpers._build_evidence_entries
#   Why: Centralizes analysis artifact creation across modes.
# Function: _compose_reused_analysis_payload
#   Role: Compose reusable analysis payload from artifacts/snapshot.
#   Called from: analytics.flows.planner_executor, analytics.flows.multi_agent
#   Invokes: analytics.validators.sanitize_for_json
#   Why: Enables cache-friendly analysis reuse with TTLs.
# Function: _build_reused_analysis_event
#   Role: Emit analysis_complete event for reused analysis payload.
#   Called from: analytics.flows.planner_executor, analytics.flows.multi_agent
#   Invokes: analytics.core.events.EventEmitter
#   Why: Provides SSE-compatible reused analysis events.
# Function: _build_analysis_source_summaries
#   Role: Summarize lane sources (sql/stock/web) for analysis displays.
#   Called from: analytics.flows.planner_executor
#   Invokes: sanitize_for_json
#   Why: Supplies concise source summaries for frontend banners.
# Function: run_analysis_stage
#   Role: Prefetch accessories then stream analysis lane.
#   Called from: analytics.flows.planner_executor._plan_phase
#   Invokes: analytics.flows.planner.analysis_lane.ensure_analysis_dependencies, analytics.flows.planner.analysis_lane.stream_analysis_lane, pipeline._stream_with_tool_state
#   Why: Reuses analysis lane orchestration across single-/multi-agent flows.
# --- End Analytics Function/Class Map ---
from __future__ import annotations

import copy
from datetime import datetime
from typing import Any, AsyncGenerator, Dict, List, Mapping, Optional, Set

from analytics.artifacts import AnalysisArtifact, PipelineArtifacts
from analytics.core.events import EventEmitter
from analytics.validators import sanitize_for_json

from .analysis_lane import ensure_analysis_dependencies, stream_analysis_lane
from .stage_helpers import _build_evidence_entries
from ..schedulers import FlowMode

_TOOL_TO_ANALYSIS_LANE: Dict[str, str] = {
    "sql_generator": "sql",
    "sql_generation": "sql",
    "sql_executor": "sql",
    "sql_execution": "sql",
    "sql_planner": "sql",
    "chart_designer": "chart",
    "chart_builder": "chart",
    "chart_generation": "chart",
    "stock_tracker": "stock",
    "market_question_a": "stock",
    "market_question_b": "stock",
    "market_research": "stock",
    "web_retriever": "web",
    "web_retriever_cached": "web",
    "web_retriever_live": "web",
    "web_research": "web",
}


def _set_analysis_artifact(
    ctx: Any,
    *,
    analysis_text: str,
    fragments: List[str],
    tool_bundle: Optional[Dict[str, Any]],
    summary: Optional[str],
    bullets: Optional[List[str]],
    key_numbers: Optional[List[str]],
    risk_watch: Optional[List[str]],
    next_steps: Optional[List[str]],
) -> None:
    stock_widget = None
    if tool_bundle:
        stock_widget = tool_bundle.get("stock_widget")
    web_context = None
    if getattr(ctx, "artifacts", None) and getattr(ctx.artifacts, "web", None):
        web_context = ctx.artifacts.web.to_dict()
    elif getattr(ctx, "web_search", None) is not None:
        web_context = ctx.web_search.to_payload()
    elif getattr(ctx, "snapshot_artifacts", None) and getattr(ctx.snapshot_artifacts, "web", None):
        web_context = ctx.snapshot_artifacts.web.to_dict()
    evidence_entries = _build_evidence_entries(
        web_context=web_context,
        highlights=bullets,
        summary=summary,
    )
    ctx.artifacts.analysis = AnalysisArtifact(
        query=ctx.query,
        analysis_text=analysis_text or None,
        fragments=fragments,
        length=len(analysis_text),
        summary=summary,
        highlights=bullets or [],
        key_numbers=key_numbers or [],
        risk_watch=risk_watch or [],
        next_steps=next_steps or [],
        evidence=evidence_entries,
        stock_widget=stock_widget,
        web_context=web_context,
        tool_bundle=tool_bundle or None,
    )


def _compose_reused_analysis_payload(ctx: Any) -> Optional[Dict[str, Any]]:
    artifact = ctx.artifacts.analysis
    if artifact is None and getattr(ctx, "snapshot_artifacts", None) and ctx.snapshot_artifacts.analysis:
        artifact = ctx.snapshot_artifacts.analysis
    if artifact is None:
        return None

    artifact_dict = artifact.to_dict()
    if not artifact_dict:
        return None

    payload: Dict[str, Any] = {}
    analysis_text = artifact_dict.get("analysis_text")
    if analysis_text:
        payload["analysis"] = analysis_text
        payload["analysis_length"] = artifact_dict.get("length") or len(analysis_text)
    summary = artifact_dict.get("summary")
    if summary:
        payload["tldr"] = summary
    highlights = artifact_dict.get("highlights")
    if highlights:
        payload["bullets"] = highlights
    key_numbers = artifact_dict.get("key_numbers")
    if key_numbers:
        payload["key_numbers"] = key_numbers
    risk_watch = artifact_dict.get("risk_watch")
    if risk_watch:
        payload["risk_watch"] = risk_watch
    next_steps = artifact_dict.get("next_steps")
    if next_steps:
        payload["next_steps"] = next_steps
    stock_widget = artifact_dict.get("stock_widget")
    if stock_widget:
        payload["stock_widget"] = stock_widget
    web_context = artifact_dict.get("web_context")
    if web_context:
        payload["web_context"] = web_context
    evidence = artifact_dict.get("evidence")
    if evidence:
        payload["evidence"] = evidence
    tool_bundle = artifact_dict.get("tool_bundle")
    if tool_bundle:
        payload["tool_bundle"] = tool_bundle

    payload["refresh_mode"] = getattr(ctx, "analysis_refresh_mode", "full")

    sanitized = sanitize_for_json(payload)
    return sanitized or None


def _build_reused_analysis_event(flow_mode: FlowMode, ctx: Any) -> Optional[Dict[str, Any]]:
    payload = _compose_reused_analysis_payload(ctx)
    if not payload:
        return None
    event = EventEmitter.result("analysis_complete", payload, key="analysis")
    event["event"] = "analysis_complete"
    event["data"]["ts"] = datetime.utcnow().isoformat()
    event["data"]["reused"] = True
    event["data"]["flow_mode"] = flow_mode.value
    event["data"]["lane"] = "analysis"
    event["data"]["refresh_mode"] = getattr(ctx, "analysis_refresh_mode", "full")
    return event


def _build_analysis_source_summaries(
    *,
    artifacts: Optional[PipelineArtifacts],
    tool_sources: Optional[Mapping[str, Any]] = None,
    stock_widget: Optional[Mapping[str, Any]] = None,
    web_context: Optional[Mapping[str, Any]] = None,
    reused_flags: Optional[Mapping[str, bool]] = None,
) -> Dict[str, Any]:
    if artifacts is None:
        artifacts = PipelineArtifacts()

    lane_status: Dict[str, str] = {}
    if isinstance(tool_sources, Mapping):
        for raw_name, status in tool_sources.items():
            if not isinstance(raw_name, str):
                continue
            tool_name = raw_name.strip().lower()
            lane = _TOOL_TO_ANALYSIS_LANE.get(tool_name)
            if not lane:
                continue
            normalized = str(status).strip().lower()
            if not normalized:
                continue
            lane_status.setdefault(lane, normalized)

    reused_lookup = {key: bool(value) for key, value in (reused_flags or {}).items()}

    def lane_reused(lane: str) -> bool:
        if lane in reused_lookup:
            return reused_lookup[lane]
        return lane_status.get(lane) == "cached"

    def compact(entry: Dict[str, Any]) -> Dict[str, Any]:
        cleaned: Dict[str, Any] = {}
        for key, value in entry.items():
            if value is None:
                continue
            if isinstance(value, (list, dict)) and not value:
                continue
            if isinstance(value, str) and not value.strip():
                continue
            cleaned[key] = value
        return cleaned

    sources: Dict[str, Dict[str, Any]] = {}

    sql_execution = getattr(artifacts, "sql_execution", None)
    if sql_execution:
        columns = list(sql_execution.columns[:6]) if isinstance(sql_execution.columns, list) else []
        metrics = list(sql_execution.metrics[:3]) if isinstance(sql_execution.metrics, list) else []
        timeframe = sql_execution.timeframe if isinstance(sql_execution.timeframe, Mapping) else None
        summary_parts: List[str] = []
        if isinstance(sql_execution.row_count, int):
            summary_parts.append(f"{sql_execution.row_count:,} rows")
        if columns:
            summary_parts.append(f"columns: {', '.join(columns[:4])}")
        if timeframe and timeframe.get("start") and timeframe.get("end"):
            summary_parts.append(f"timeframe: {timeframe['start']} to {timeframe['end']}")
        entry = compact(
            {
                "lane": "sql",
                "label": "SQL data",
                "summary": " | ".join(summary_parts) if summary_parts else None,
                "row_count": sql_execution.row_count,
                "columns": columns,
                "metrics": metrics,
                "reused": lane_reused("sql"),
            }
        )
        if entry:
            sources["sql"] = entry

    widget_candidate: Optional[Mapping[str, Any]] = None
    if isinstance(stock_widget, Mapping):
        widget_candidate = stock_widget
    elif artifacts.analysis and isinstance(artifacts.analysis.stock_widget, Mapping):
        widget_candidate = artifacts.analysis.stock_widget
    elif artifacts.market and isinstance(artifacts.market.snapshot, Mapping):
        widget_candidate = artifacts.market.snapshot

    if widget_candidate:
        symbols: List[str] = []
        raw_symbols = widget_candidate.get("symbols")
        if isinstance(raw_symbols, list):
            for entry in raw_symbols:
                if isinstance(entry, (list, tuple)) and entry:
                    candidate = entry[1] if len(entry) > 1 else entry[0]
                else:
                    candidate = entry
                if isinstance(candidate, str) and candidate.strip():
                    symbols.append(candidate.strip().upper())
        summary_parts: List[str] = []
        if symbols:
            summary_parts.append(f"symbols: {', '.join(symbols[:3])}")
        insights = widget_candidate.get("insights") if isinstance(widget_candidate.get("insights"), Mapping) else None
        latest_close = insights.get("latest_close") if insights else widget_candidate.get("latest_close")
        change_percent = insights.get("change_percent") if insights else widget_candidate.get("change_percent")
        if isinstance(latest_close, (int, float)):
            summary_parts.append(f"latest close: {latest_close}")
        if isinstance(change_percent, (int, float)):
            summary_parts.append(f"change: {change_percent:+.2f}%")
        entry = compact(
            {
                "lane": "stock",
                "label": "Stock data",
                "summary": " | ".join(summary_parts) if summary_parts else None,
                "symbols": symbols[:4],
                "latest_close": latest_close if isinstance(latest_close, (int, float)) else None,
                "change_percent": change_percent if isinstance(change_percent, (int, float)) else None,
                "reused": lane_reused("stock"),
            }
        )
        if entry:
            sources["stock"] = entry

    context_candidate: Optional[Mapping[str, Any]] = None
    if isinstance(web_context, Mapping):
        context_candidate = web_context
    elif artifacts.analysis and isinstance(artifacts.analysis.web_context, Mapping):
        context_candidate = artifacts.analysis.web_context
    elif artifacts.web and isinstance(artifacts.web.to_dict(), dict):
        context_candidate = artifacts.web.to_dict()

    if context_candidate:
        summary_text = context_candidate.get("summary")
        topic = (
            context_candidate.get("search_topic")
            or context_candidate.get("searchTopic")
            or context_candidate.get("query")
        )
        snippets = context_candidate.get("snippets") or context_candidate.get("articles")
        snippet_count = len(snippets) if isinstance(snippets, list) else 0
        entry = compact(
            {
                "lane": "web",
                "label": "Online research",
                "summary": summary_text if isinstance(summary_text, str) else None,
                "topic": topic if isinstance(topic, str) else None,
                "snippet_count": snippet_count,
                "reused": lane_reused("web"),
            }
        )
        if entry:
            sources["web"] = entry

    if not sources:
        return {}
    sanitized = sanitize_for_json(sources)
    return sanitized if isinstance(sanitized, dict) else {}



async def run_analysis_stage(
    pipeline: Any,
    *,
    ctx: Any,
    registry: Any,
    executed: Set[str],
    tool_state: Optional[Dict[str, Any]],
    mode_config: Any,
) -> AsyncGenerator[Dict[str, Any], None]:
    """Prefetch accessories (if needed) then stream the analysis lane."""
    async for event in pipeline._stream_with_tool_state(  # type: ignore[attr-defined]
        ensure_analysis_dependencies(pipeline, ctx, mode_config=mode_config),
        tool_state,
        ctx,
    ):
        yield event

    async for event in stream_analysis_lane(
        pipeline,
        ctx=ctx,
        registry=registry,
        executed=executed,
        tool_state=tool_state,
        mode_config=mode_config,
    ):
        yield event

