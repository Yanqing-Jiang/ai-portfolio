# --- Analytics Function/Class Map ---
# Function: _build_planner_result_payload
#   Role: Construct planner result payload (intent, clarifications, sql/chart/analysis summaries, metadata).
#   Called from: analytics.flows.planner_executor (facade); intended for reuse by pipeline orchestrators.
#   Invokes: analytics.core.types.PlannerResultModel, stage_helpers guardrails/evidence builders.
#   Why: Keep result-shaping logic out of the planner facade so lanes/stages stay reusable across modes.
# --- End Analytics Function/Class Map ---
from __future__ import annotations

import copy
from typing import Any, Dict, List, Optional

from analytics.core.types import ClarifyRequestModel, IntentModel, PlannerResultModel
from analytics.validators import sanitize_for_json

from .stage_helpers import _build_evidence_entries, _evaluate_latency_guardrail


def _build_planner_result_payload(ctx: Any) -> Dict[str, Any]:
    intent_model = ctx.intent
    if intent_model is not None and not isinstance(intent_model, IntentModel):
        intent_payload: Optional[Dict[str, Any]] = None
        if hasattr(intent_model, "model_dump"):
            intent_payload = intent_model.model_dump()
        elif hasattr(intent_model, "__dict__"):
            intent_payload = dict(intent_model.__dict__)
        if isinstance(intent_payload, dict):
            try:
                intent_model = IntentModel(**intent_payload)
            except Exception:
                intent_model = None

    clarification_requests_raw = list(ctx.clarifications)
    clarification_requests: List[ClarifyRequestModel] = []
    for request in clarification_requests_raw:
        if isinstance(request, ClarifyRequestModel):
            clarification_requests.append(request)
            continue
        request_payload: Optional[Dict[str, Any]] = None
        if hasattr(request, "model_dump"):
            request_payload = request.model_dump()
        elif isinstance(request, dict):
            request_payload = request
        elif hasattr(request, "__dict__"):
            request_payload = dict(request.__dict__)
        if isinstance(request_payload, dict):
            try:
                clarification_requests.append(ClarifyRequestModel(**request_payload))
            except Exception:
                continue

    sql_attempts: List[Dict[str, Any]] = []
    sql_text: Optional[str] = None
    if ctx.artifacts.sql_generation:
        sql_attempts = list(ctx.artifacts.sql_generation.attempts or [])
        sql_text = ctx.artifacts.sql_generation.sql

    row_count: Optional[int] = None
    if ctx.artifacts.sql_execution:
        row_count = ctx.artifacts.sql_execution.row_count

    chart_summary: Optional[Dict[str, Any]] = None
    if ctx.artifacts.chart:
        chart_summary = {
            "chart_type": ctx.artifacts.chart.chart_type,
            "series_count": ctx.artifacts.chart.series_count,
            "design": copy.deepcopy(ctx.artifacts.chart.design),
        }
        if ctx.artifacts.chart.scope_banner:
            chart_summary["scope_banner"] = ctx.artifacts.chart.scope_banner

    analysis_text = ctx.artifacts.analysis.analysis_text if ctx.artifacts.analysis else None

    metadata: Dict[str, Any] = {}
    if ctx.classification is not None:
        metadata["classification"] = copy.deepcopy(ctx.classification.model_dump())
    if ctx.clarification_sources:
        metadata["clarification_sources"] = sorted(ctx.clarification_sources)

    web_payload: Optional[Dict[str, Any]] = None
    if ctx.artifacts.web:
        web_payload = ctx.artifacts.web.to_dict()
    elif ctx.web_search is not None:
        web_payload = ctx.web_search.to_payload()
    elif ctx.snapshot_artifacts and ctx.snapshot_artifacts.web:
        web_payload = ctx.snapshot_artifacts.web.to_dict()
    web_latency: Optional[Dict[str, Any]] = None
    if web_payload:
        metadata["web_search"] = copy.deepcopy(web_payload)
        stats = web_payload.get("latency_stats")
        if isinstance(stats, dict):
            web_latency = {
                "total_ms": stats.get("total_ms") or stats.get("totalMs"),
                "p50_ms": stats.get("p50_ms") or stats.get("p50Ms"),
                "max_ms": stats.get("max_ms") or stats.get("maxMs"),
                "min_ms": stats.get("min_ms") or stats.get("minMs"),
                "samples": stats.get("samples") or stats.get("latency_samples") or stats.get("sample_count"),
            }
    elif ctx.web_search is not None and ctx.web_search.latency_ms is not None:
        web_latency = {
            "total_ms": ctx.web_search.latency_ms,
        }

    if web_latency:
        cleaned_latency = {key: value for key, value in web_latency.items() if value is not None}
        if cleaned_latency:
            metadata["web_search_latency"] = cleaned_latency
        guardrail_payload = _evaluate_latency_guardrail(web_latency)
        if guardrail_payload:
            metadata["web_search_guardrail"] = guardrail_payload

    if ctx.artifacts.analysis:
        overview: Dict[str, Any] = {}
        if ctx.artifacts.analysis.summary:
            overview["tldr"] = ctx.artifacts.analysis.summary
        if ctx.artifacts.analysis.highlights:
            overview["highlights"] = list(ctx.artifacts.analysis.highlights)
        if ctx.artifacts.analysis.key_numbers:
            overview["key_numbers"] = list(ctx.artifacts.analysis.key_numbers)
        if ctx.artifacts.analysis.risk_watch:
            overview["risk_watch"] = list(ctx.artifacts.analysis.risk_watch)
        if ctx.artifacts.analysis.next_steps:
            overview["next_steps"] = list(ctx.artifacts.analysis.next_steps)
        evidence_entries = list(ctx.artifacts.analysis.evidence or [])
        if not evidence_entries:
            web_source: Optional[Dict[str, Any]] = None
            if metadata.get("web_search"):
                web_candidate = metadata.get("web_search")
                if isinstance(web_candidate, dict):
                    web_source = web_candidate
            elif ctx.artifacts.web:
                web_source = ctx.artifacts.web.to_dict()
            evidence_entries = _build_evidence_entries(
                web_context=web_source,
                highlights=ctx.artifacts.analysis.highlights,
                summary=ctx.artifacts.analysis.summary or ctx.artifacts.analysis.analysis_text,
            )
            if evidence_entries:
                ctx.artifacts.analysis.evidence = evidence_entries
        if evidence_entries:
            overview["evidence"] = evidence_entries
        if overview:
            metadata["analysis_overview"] = overview

    if getattr(ctx, "schema_clarifier_decision", None):
        decision = ctx.schema_clarifier_decision
        metadata["schema_clarifier"] = {
            "enabled": True,
            "action": decision.action if decision else "disabled",
            "missing_slots": list(decision.missing_slots) if decision and decision.missing_slots else [],
            "slot": decision.slot if decision else None,
        }

    metadata["follow_up_route"] = ctx.follow_up_route.value
    metadata["snapshot_reuse"] = {
        "reused_sql": ctx.reused_sql,
        "reused_chart": ctx.reused_chart,
        "reused_stock": ctx.reused_stock,
        "reused_web": ctx.reused_web,
        "reused_analysis": ctx.reused_analysis,
        "criteria_changed": ctx.criteria_changed,
        "follow_up_route": ctx.follow_up_route.value,
        "source": "snapshot" if ctx.reuse_snapshot_active else None,
        "snapshot_age_seconds": ctx.snapshot_age_seconds,
        "snapshot_stale": ctx.snapshot_stale,
    }
    metadata["reuse_snapshot"] = metadata["snapshot_reuse"]

    planner_result_model = PlannerResultModel(
        intent=intent_model,
        clarification_requests=clarification_requests,
        sql_attempts=sql_attempts,
        sql_text=sql_text,
        data_row_count=row_count,
        chart_summary=chart_summary,
        analysis=analysis_text,
        metadata=metadata,
    )
    return planner_result_model.model_dump()


def compose_web_ready_payload(ctx: Any) -> Optional[Dict[str, Any]]:
    web_payload: Optional[Dict[str, Any]] = None
    if getattr(ctx, "artifacts", None) and getattr(ctx.artifacts, "analysis", None) and ctx.artifacts.analysis.web_context:
        web_payload = copy.deepcopy(ctx.artifacts.analysis.web_context)
    elif getattr(ctx, "revision_snapshot", None) and ctx.revision_snapshot.get("web_context"):
        web_payload = copy.deepcopy(ctx.revision_snapshot["web_context"])
    elif getattr(ctx, "artifacts", None) and getattr(ctx.artifacts, "web", None) and ctx.artifacts.web.to_dict():
        web_payload = ctx.artifacts.web.to_dict()
    if not web_payload:
        return None
    payload = sanitize_for_json(web_payload) or {}
    if not isinstance(payload, dict):
        return None
    payload["reused"] = bool(getattr(ctx, "reused_web", False))
    payload["from_cache"] = bool(payload.get("reused"))
    if "source" not in payload and getattr(ctx, "is_revision_follow_up", False):
        payload["source"] = "fresh_revision"
    payload.setdefault("schedule_stage", "hedged_accessories")
    if getattr(ctx, "snapshot_age_seconds", None) is not None:
        payload["snapshot_age_seconds"] = ctx.snapshot_age_seconds
    return payload

