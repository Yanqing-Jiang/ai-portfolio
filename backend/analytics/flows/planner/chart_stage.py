# --- Analytics Function/Class Map ---
# Function: _generate_chart_design
#   Role: Generate chart design metadata for downstream chart rendering.
#   Called from: analytics.flows.planner_executor (chart phase helpers)
#   Invokes: analytics.core.margins.detect_margin_choice_from_plan
#   Why: Optimizes chart defaults per intent/plan.
# Function: _summarize_chart_series
#   Role: Summarize chart series definitions for artifact metadata.
#   Called from: analytics.flows.planner_executor chart artifact helper
#   Invokes: None
#   Why: Provides concise series metadata for receipts and datasets.
# Function: _get_sql_dataset
#   Role: Read SQL dataset from planner context artifacts.
#   Called from: analytics.flows.planner_executor chart helpers
#   Invokes: ctx.artifacts.sql_execution dataset/sample rows
#   Why: Supplies chart scope banner and dataset summaries.
# Function: _derive_scope_banner
#   Role: Build scope banner text from market artifacts/spec datasets.
#   Called from: analytics.flows.planner_executor _set_chart_artifact
#   Invokes: _get_sql_dataset
#   Why: Adds basis banner to chart artifacts for frontend context.
# Function: _set_chart_artifact
#   Role: Populate chart artifact with spec/design metadata.
#   Called from: analytics.flows.planner_executor chart phase
#   Invokes: _summarize_chart_series, _derive_scope_banner, analytics.artifacts.ChartArtifact
#   Why: Centralizes chart artifact construction for all modes.
# Function: run_chart_stage
#   Role: Streams chart lane via shared lane helper.
#   Called from: analytics.flows.planner_executor._plan_phase
#   Invokes: analytics.flows.planner.sql_lane.stream_chart_lane
#   Why: Provides a reusable chart lane entrypoint for single-/multi-agent flows.
# Function: run_chart_pipeline_stage
#   Role: Execute full chart pipeline (planning, building, emitting events).
#   Called from: analytics.flows.planner_executor.PlannerPipeline.run_chart_phase
#   Invokes: plan_chart_rule_based, build_chart_spec, compose_chart_ready_payload
#   Why: Consolidates chart lane logic for reuse across DIRECT, SINGLE_AGENT, MULTI_AGENT modes.
# --- End Analytics Function/Class Map ---
from __future__ import annotations

import hashlib
import logging
import json
import time
from datetime import datetime
from typing import Any, AsyncGenerator, Dict, List, Optional, Set

from pydantic import ValidationError

from analytics.artifacts import ChartArtifact
from analytics.core.context import get_configs
from analytics.core.events import EventEmitter
from analytics.core.charting import plan_chart_rule_based, build_chart_spec
from analytics.core.margins import detect_margin_choice_from_plan
from analytics.core.state import QueryPlanModel
from analytics.validators import sanitize_for_json

from .stage_helpers import ensure_tool_receipt, hash_payload
from .sql_lane import stream_chart_lane, compose_chart_ready_payload, _cached_event

logger = logging.getLogger(__name__)
CONFIGS = get_configs()
_hash_payload = hash_payload


def _make_identifier(session_id: Optional[str], prefix: str, payload: str) -> str:
    """Deterministic identifier for chart artifacts."""
    base = f"{session_id or 'anon'}:{prefix}:{payload}"
    return hashlib.sha1(base.encode("utf-8")).hexdigest()


def _generate_chart_design(
    intent_key: Optional[str],
    plan: QueryPlanModel,
    data: List[Dict[str, Any]],
    spec: Dict[str, Any],
) -> Dict[str, Any]:
    """Generate smart chart design metadata for frontend optimization."""
    if not intent_key or not data:
        return {}
    cols = list(data[0].keys()) if data else []
    has_multiple_tickers = len(set(row.get("ticker") for row in data if row.get("ticker"))) > 1
    comparison = getattr(plan, "comparison", None)
    design: Dict[str, Any] = {
        "intent": intent_key,
        "grouping": "ticker" if has_multiple_tickers else "metric",
        "chart_type": "line_multi",
        "y_axis": {"type": "dual"},
        "legend_order": [],
        "defaultLegendSelection": {},
        "color_by": "ticker" if has_multiple_tickers else "metric",
    }
    if comparison:
        design["comparison"] = comparison
        if comparison == "all" and has_multiple_tickers:
            design["comparison_mode"] = "multi_company"
    if getattr(plan, "statistic", None) == "ranking_latest":
        primary_metric = (plan.metrics or [None])[0]
        design.update(
            {
                "chart_type": "ranking_bar",
                "grouping": "ticker",
                "y_axis": {"type": "single"},
                "measure": primary_metric,
                "statistic": plan.statistic,
            }
        )
    if intent_key == "market_share_all":
        design.update(
            {
                "chart_type": "stacked_area_100",
                "measure": "market_share_percent",
                "top_n": 3,
                "aggregate_rest": True,
                "rest_label": "Others",
                "y_axis": {"type": "percent_only"},
            }
        )
    elif intent_key == "market_share_single":
        design.update(
            {
                "measure": "market_share_percent",
                "y_axis": {"type": "dual"},
                "defaultLegendSelection": {"market_share_percent": True},
            }
        )
    elif intent_key in ["revenue_growth_analysis"]:
        design.update(
            {
                "measure": ["qoq_growth_percent", "yoy_growth_percent"],
                "y_axis": {"type": "dual"},
                "defaultLegendSelection": {
                    "qoq_growth_percent": True,
                    "yoy_growth_percent": True,
                    "quarterly_revenue": False,
                },
            }
        )
    elif intent_key in ["margins_vs_peers", "margin_growth_vs_peers"]:
        choice = detect_margin_choice_from_plan(plan)
        if choice:
            measures = (
                [choice.value_alias, choice.peer_alias]
                if intent_key == "margins_vs_peers"
                else [choice.growth_alias, choice.growth_peer_alias]
            )
            default_selection = {alias: True for alias in measures}
        else:
            if intent_key == "margins_vs_peers":
                measures = ["gross_margin", "operating_margin", "net_margin"]
                default_selection = {"operating_margin": True, "net_margin": True}
            else:
                measures = [
                    "company_gross_margin_change_pp",
                    "company_operating_margin_change_pp",
                    "company_net_margin_change_pp",
                    "peer_avg_gross_margin_change_pp",
                    "peer_avg_operating_margin_change_pp",
                    "peer_avg_net_margin_change_pp",
                ]
                default_selection = {
                    "company_operating_margin_change_pp": True,
                    "company_net_margin_change_pp": True,
                }
        design.update(
            {
                "measure": measures,
                "y_axis": {"type": "percent_only"},
                "defaultLegendSelection": default_selection,
            }
        )
    elif intent_key in ["rnd_intensity_vs_peers", "rnd_expense_vs_peers"]:
        design.update(
            {
                "measure": "company_rnd_intensity" if "intensity" in intent_key else "company_rnd_expense",
                "y_axis": {"type": "percent_only"} if "intensity" in intent_key else {"type": "currency_only"},
                "chart_type": "line_multi",
            }
        )
    return design


def _summarize_chart_series(plan: Any, spec: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    series_summary: List[Dict[str, Any]] = []
    plan_dict: Dict[str, Any] = {}
    if hasattr(plan, "dict"):
        try:
            plan_dict = plan.dict()
        except Exception:
            plan_dict = {}
    elif isinstance(plan, dict):
        plan_dict = dict(plan)
    for entry in plan_dict.get("series", []) or []:
        if isinstance(entry, dict):
            summary = {key: entry.get(key) for key in ("id", "metric", "measure", "comparison", "axis") if entry.get(key) is not None}
            if summary:
                series_summary.append(summary)
    if not series_summary and isinstance(spec, dict):
        datasets = spec.get("datasets")
        if isinstance(datasets, list):
            for dataset in datasets:
                if isinstance(dataset, dict):
                    label = dataset.get("label") or dataset.get("name")
                    series_summary.append(
                        {
                            "label": label,
                            "id": dataset.get("id"),
                            "metric": dataset.get("metric"),
                        }
                    )
    return series_summary


def _get_sql_dataset(ctx: Any) -> List[Dict[str, Any]]:
    """Get SQL dataset from context artifacts."""
    execution_artifact = getattr(ctx.artifacts, "sql_execution", None)
    if execution_artifact is None:
        return []
    dataset = getattr(execution_artifact, "dataset", None) or []
    if dataset:
        return list(dataset)
    preview = getattr(execution_artifact, "dataset_preview", None) or []
    if preview:
        return list(preview)
    return list(execution_artifact.sample_rows)


def _derive_scope_banner(ctx: Any, spec: Dict[str, Any]) -> Optional[str]:
    tickers: List[str] = []
    market_artifact = getattr(ctx.artifacts, "market", None)
    if market_artifact and market_artifact.tickers:
        tickers.extend(market_artifact.tickers)
    datasets = spec.get("datasets")
    if not tickers and isinstance(datasets, list):
        for dataset in datasets:
            if isinstance(dataset, dict):
                symbol = dataset.get("ticker") or dataset.get("symbol")
                if isinstance(symbol, str):
                    tickers.append(symbol)
    if not tickers:
        dataset_rows = _get_sql_dataset(ctx)
        for row in dataset_rows:
            symbol = row.get("ticker")
            if isinstance(symbol, str):
                tickers.append(symbol)
    deduped: List[str] = []
    for symbol in tickers:
        upper = symbol.strip().upper()
        if upper and upper not in deduped:
            deduped.append(upper)
    if not deduped:
        return None
    basis = ", ".join(deduped[:7])
    return f"Basis: Revenue share across {basis}"


def _set_chart_artifact(
    ctx: Any,
    *,
    spec: Dict[str, Any],
    chart_plan: Any,
    chart_design: Dict[str, Any],
) -> None:
    series_summary = _summarize_chart_series(chart_plan, spec)
    chart_type = getattr(chart_plan, "chart_type", None)
    try:
        serialized_spec = json.dumps(spec, sort_keys=True)
    except Exception:
        serialized_spec = repr(spec)
    spec_id: Optional[str] = None
    try:
        spec_id = _make_identifier(getattr(ctx, "session_id", None), "chart", serialized_spec)
        spec.setdefault("meta", {})["artifactSpecId"] = spec_id
    except Exception:
        spec_id = None
    scope_banner = _derive_scope_banner(ctx, spec)
    if scope_banner:
        spec.setdefault("meta", {})["scopeBanner"] = scope_banner
    ctx.artifacts.chart = ChartArtifact(
        query=ctx.query,
        spec=spec,
        spec_id=spec_id,
        design=chart_design or {},
        datasets_summary=series_summary,
        series_count=len(series_summary) if series_summary else None,
        chart_type=chart_type,
        scope_banner=scope_banner,
    )


async def run_chart_stage(
    pipeline: Any,
    *,
    ctx: Any,
    registry: Any,
    executed: Set[str],
    tool_state: Optional[Dict[str, Any]],
    run_chart_lane: bool,
) -> AsyncGenerator[Dict[str, Any], None]:
    """Run the chart lane using the shared lane helper."""
    async for event in stream_chart_lane(
        pipeline,
        ctx=ctx,
        registry=registry,
        executed=executed,
        tool_state=tool_state,
        run_chart_lane=run_chart_lane,
    ):
        yield event


async def run_chart_pipeline_stage(
    pipeline: Any,
    ctx: Any,
    *,
    intent: Any,
    plan: Any,
) -> AsyncGenerator[Dict[str, Any], None]:
    """
    Execute the full chart pipeline: planning, building spec, and emitting events.

    This function consolidates chart lane logic for reuse across DIRECT, SINGLE_AGENT,
    and MULTI_AGENT modes. It handles:
    - Cached chart reuse
    - Rule-based chart planning
    - ECharts spec building
    - Chart design generation
    - Event emission (chart_planned, chart_generated, chart_ready)

    Args:
        pipeline: The planner pipeline instance
        ctx: The planner phase context
        intent: The resolved intent model
        plan: The query plan model

    Yields:
        SSE events from chart pipeline execution
    """
    plan_payload: Optional[Dict[str, Any]] = None
    if hasattr(plan, "model_dump"):
        plan_payload = plan.model_dump()
    elif hasattr(plan, "dict"):
        plan_payload = plan.dict()

    input_payload = {
        "query": ctx.query,
        "intent": getattr(intent, "intent_key", None),
        "plan": plan_payload,
    }

    receipt = ensure_tool_receipt(
        ctx,
        "chart_builder",
        status="reused" if ctx.reused_chart else "running",
        reused=bool(ctx.reused_chart),
        attempts=0,
        input_hash=_hash_payload(input_payload),
    )

    # Handle cached chart reuse
    if ctx.reused_chart:
        cached_payload = compose_chart_ready_payload(ctx)
        if cached_payload:
            cached_chart = _cached_event(
                "chart_ready",
                cached_payload,
                schedule_stage="chart",
                flow_mode=pipeline.flow_mode,
                parallel_group="core_sequential",
                lane="chart",
            )
            yield pipeline._annotate_revision(cached_chart, ctx)
        return

    chart_start = time.time()

    # Get dataset from SQL execution
    data = pipeline._get_sql_dataset(ctx)
    if not data:
        receipt.status = "skipped"
        receipt.elapsed_ms = int((time.time() - chart_start) * 1000)
        return

    query = ctx.query

    # Emit progress event
    chart_progress = EventEmitter.progress("chart_generation", "Planning chart...")
    chart_progress["data"]["ts"] = datetime.utcnow().isoformat()
    yield chart_progress

    # Rule-based chart planning
    chart_plan = plan_chart_rule_based(
        data,
        query,
        intent.intent_key,
        statistic=getattr(plan, "statistic", None),
    )

    # Build chart spec
    spec = build_chart_spec(
        data,
        chart_plan.dict(),
        CONFIGS.charts,
        intent_key=intent.intent_key,
        comparison=plan.comparison,
        statistic=getattr(plan, "statistic", None),
    )

    # Generate chart design metadata
    chart_design = pipeline._generate_chart_design(intent.intent_key, plan, data, spec)
    spec.setdefault("meta", {}).setdefault("chartDesign", chart_design)

    # Set artifact
    pipeline._set_chart_artifact(
        ctx,
        spec=spec,
        chart_plan=chart_plan,
        chart_design=chart_design,
    )
    pipeline._capture_artifacts(ctx)
    await pipeline._persist_session_state(ctx, record_chart=True)

    chart_elapsed = int((time.time() - chart_start) * 1000)
    receipt.status = "completed"
    receipt.elapsed_ms = chart_elapsed
    receipt.output_hash = _hash_payload(spec)

    # Emit chart_planned event
    chart_event = EventEmitter.result(
        "chart_planned",
        {
            "chart_type": chart_plan.chart_type,
            "series_count": len(chart_plan.series),
        },
    )
    chart_event["event"] = "chart_planned"
    chart_event["data"].update(
        {
            "ts": datetime.utcnow().isoformat(),
            "elapsed_ms": chart_elapsed,
        }
    )
    yield chart_event

    # Emit chart_generated event with validation
    try:
        # Import ChartSpecModel for validation
        from analytics.core.models import ChartSpecModel
        ChartSpecModel(**spec)
        generated_chart = EventEmitter.result(
            "chart_generated",
            {
                "chart_type": spec.get("meta", {}).get("chartDesign", {}).get("chart_type", "unknown"),
                "chart_spec": spec,
            },
            key="chart_spec",
        )
        generated_chart["event"] = "chart_generated"
        generated_chart["data"]["ts"] = datetime.utcnow().isoformat()
        yield generated_chart
    except ValidationError as ve:
        receipt.metadata["validation_warning"] = str(ve)
        warning_event = EventEmitter.progress("warning", f"Chart spec validation warning: {str(ve)}")
        warning_event["data"]["ts"] = datetime.utcnow().isoformat()
        yield warning_event
        # Still emit chart with fallback
        fallback_chart = EventEmitter.result(
            "chart_generated",
            {
                "chart_type": spec.get("meta", {}).get("chartDesign", {}).get("chart_type", "unknown"),
                "chart_spec": spec,
            },
            key="chart_spec",
        )
        fallback_chart["event"] = "chart_generated"
        fallback_chart["data"]["ts"] = datetime.utcnow().isoformat()
        yield fallback_chart
    except ImportError:
        # ChartSpecModel not available, skip validation
        generated_chart = EventEmitter.result(
            "chart_generated",
            {
                "chart_type": spec.get("meta", {}).get("chartDesign", {}).get("chart_type", "unknown"),
                "chart_spec": spec,
            },
            key="chart_spec",
        )
        generated_chart["event"] = "chart_generated"
        generated_chart["data"]["ts"] = datetime.utcnow().isoformat()
        yield generated_chart

    # Emit chart_ready event
    ready_payload = compose_chart_ready_payload(ctx)
    if ready_payload:
        ready_payload["reused"] = False
        ready_payload.setdefault("schedule_stage", "chart")
        ready_payload.setdefault("parallel_group", "core_sequential")
        ready_payload.setdefault("flow_mode", pipeline.flow_mode.value)
        ready_payload.setdefault("ts", datetime.utcnow().isoformat())
        ready_payload.setdefault("lane", "chart")
        yield pipeline._annotate_revision(
            {
                "event": "chart_ready",
                "data": sanitize_for_json(ready_payload),
            },
            ctx,
        )

