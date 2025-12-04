# --- Analytics Function/Class Map ---
# Function: _cached_event
#   Role: Handles cached event logic for analytics.flows.planner.sql_lane.
#   Called from: analytics.flows.planner, analytics.flows.planner_executor
#   Invokes: analytics.validators.sanitize_for_json
#   Why: Keeps analytics.flows.planner.sql_lane from duplicating cached event behavior across flows.
# Function: compose_sql_ready_payload
#   Role: Handles compose sql ready payload logic for analytics.flows.planner.sql_lane.
#   Called from: analytics.flows.planner, analytics.flows.planner_executor
#   Invokes: types.SimpleNamespace, analytics.flows.planner.sql_lane.limit_sample_rows
#   Why: Keeps analytics.flows.planner.sql_lane from duplicating compose sql ready payload behavior across flows.
# Function: compose_chart_ready_payload
#   Role: Handles compose chart ready payload logic for analytics.flows.planner.sql_lane.
#   Called from: analytics.flows.planner, analytics.flows.planner_executor
#   Invokes: copy.deepcopy
#   Why: Keeps analytics.flows.planner.sql_lane from duplicating compose chart ready payload behavior across flows.
# Function: compose_stock_ready_payload
#   Role: Handles compose stock ready payload logic for analytics.flows.planner.sql_lane.
#   Called from: analytics.flows.planner, analytics.flows.planner_executor
#   Invokes: copy.deepcopy
#   Why: Keeps analytics.flows.planner.sql_lane from duplicating compose stock ready payload behavior across flows.
# Function: compose_web_ready_payload
#   Role: Handles compose web ready payload logic for analytics.flows.planner.sql_lane.
#   Called from: analytics.flows.planner
#   Invokes: copy.deepcopy, analytics.validators.sanitize_for_json
#   Why: Keeps analytics.flows.planner.sql_lane from duplicating compose web ready payload behavior across flows.
# Function: stream_sql_lane
#   Role: Handles stream sql lane logic for analytics.flows.planner.sql_lane.
#   Called from: analytics.flows.multi_agent, analytics.flows.planner, analytics.flows.planner_executor, analytics.flows.single_agent_tools
#   Invokes: analytics.flows.planner.sql_lane.compose_sql_ready_payload, analytics.flows.planner.sql_lane.compose_stock_ready_payload, analytics.flows.planner.sql_lane.compose_web_ready_payload, analytics.flows.planner.sql_lane._cached_event, +2 more
#   Why: Keeps analytics.flows.planner.sql_lane from duplicating stream sql lane behavior across flows.
# Function: stream_chart_lane
#   Role: Handles stream chart lane logic for analytics.flows.planner.sql_lane.
#   Called from: analytics.flows.multi_agent, analytics.flows.planner, analytics.flows.planner_executor, analytics.flows.single_agent_tools
#   Invokes: analytics.flows.planner.revision.mark_revision_completion, analytics.flows.planner.sql_lane.compose_chart_ready_payload, analytics.flows.planner.sql_lane._cached_event
#   Why: Keeps analytics.flows.planner.sql_lane from duplicating stream chart lane behavior across flows.
# Function: limit_sample_rows
#   Role: Handles limit sample rows logic for analytics.flows.planner.sql_lane.
#   Called from: analytics.flows.planner, analytics.flows.planner_executor, tests.analytics.test_planner_executor_sql
#   Invokes: copy.deepcopy
#   Why: Keeps analytics.flows.planner.sql_lane from duplicating limit sample rows behavior across flows.
# --- End Analytics Function/Class Map ---
from __future__ import annotations

import copy
from datetime import datetime
from types import SimpleNamespace
from typing import Any, AsyncGenerator, Dict, List, Optional, Sequence, Set, TYPE_CHECKING

from analytics.core.events import EventEmitter
from analytics.validators import sanitize_for_json

from ..schedulers import FlowMode
from .revision import mark_revision_completion

if TYPE_CHECKING:  # pragma: no cover - typing only
    from ..pipeline_tools import PlannerToolRegistry
    from ..planner_executor import PlannerPipeline, PlannerPhaseContext


__all__ = [
    "_cached_event",
    "compose_sql_ready_payload",
    "compose_chart_ready_payload",
    "compose_stock_ready_payload",
    "compose_web_ready_payload",
    "stream_sql_lane",
    "stream_chart_lane",
]


def _cached_event(
    name: str,
    payload: Dict[str, Any],
    *,
    schedule_stage: str,
    flow_mode: FlowMode,
    parallel_group: Optional[str] = None,
    lane: Optional[str] = None,
) -> Dict[str, Any]:
    sanitized = sanitize_for_json(payload) if isinstance(payload, dict) else {"payload": sanitize_for_json(payload)}
    if not isinstance(sanitized, dict):
        sanitized = {"payload": sanitized}
    sanitized.setdefault("schedule_stage", schedule_stage)
    if parallel_group:
        sanitized.setdefault("parallel_group", parallel_group)
    if lane:
        sanitized.setdefault("lane", lane)
    sanitized.setdefault("flow_mode", flow_mode.value)
    sanitized.setdefault("reused", True)
    sanitized.setdefault("ts", datetime.utcnow().isoformat())
    return {
        "event": name,
        "data": sanitized,
    }


def compose_sql_ready_payload(ctx: "PlannerPhaseContext") -> Optional[Dict[str, Any]]:
    generation = getattr(ctx.artifacts, "sql_generation", None)
    execution = getattr(ctx.artifacts, "sql_execution", None)
    snapshot = ctx.revision_snapshot if isinstance(ctx.revision_snapshot, dict) else None
    if not generation and snapshot and snapshot.get("sql"):
        generation = SimpleNamespace(sql=snapshot.get("sql"))
    if not execution and snapshot and (
        snapshot.get("sql_row_count") is not None
        or snapshot.get("columns")
        or snapshot.get("data_sample")
    ):
        execution = SimpleNamespace(
            row_count=snapshot.get("sql_row_count"),
            columns=list(snapshot.get("columns") or []),
            sample_rows=limit_sample_rows(snapshot.get("data_sample") or []),
            dataset_preview=limit_sample_rows(snapshot.get("data_sample") or []),
        )
    if not generation and not execution:
        return None
    payload: Dict[str, Any] = {
        "reused": bool(ctx.reused_sql),
        "schedule_stage": "sql",
    }
    if generation and generation.sql:
        payload["sql"] = generation.sql
    if execution:
        if execution.row_count is not None:
            payload["row_count"] = execution.row_count
        if execution.columns:
            payload["columns"] = list(execution.columns)
        samples = execution.sample_rows or execution.dataset_preview
        sample_rows = limit_sample_rows(samples)
        if sample_rows:
            payload["sample_data"] = sample_rows
    if ctx.snapshot_age_seconds is not None:
        payload["snapshot_age_seconds"] = ctx.snapshot_age_seconds
    elif ctx.reused_sql:
        payload["snapshot_age_seconds"] = 0.0
    return payload


def compose_chart_ready_payload(ctx: "PlannerPhaseContext") -> Optional[Dict[str, Any]]:
    chart_artifact = getattr(ctx.artifacts, "chart", None)
    if not chart_artifact or not chart_artifact.spec:
        return None
    summary: Dict[str, Any] = {}
    if chart_artifact.chart_type:
        summary["chart_type"] = chart_artifact.chart_type
    if chart_artifact.series_count is not None:
        summary["series_count"] = chart_artifact.series_count
    if chart_artifact.design:
        summary["design"] = copy.deepcopy(chart_artifact.design)
    payload: Dict[str, Any] = {
        "chart_spec": copy.deepcopy(chart_artifact.spec),
        "chart_spec_id": chart_artifact.spec_id,
        "chart_summary": summary or None,
        "reused": True,
        "schedule_stage": "chart",
    }
    if ctx.snapshot_age_seconds is not None:
        payload["snapshot_age_seconds"] = ctx.snapshot_age_seconds
    return payload


def compose_stock_ready_payload(ctx: "PlannerPhaseContext") -> Optional[Dict[str, Any]]:
    stock_widget: Optional[Dict[str, Any]] = None
    if ctx.artifacts.analysis and ctx.artifacts.analysis.stock_widget:
        stock_widget = copy.deepcopy(ctx.artifacts.analysis.stock_widget)
    elif ctx.revision_snapshot and ctx.revision_snapshot.get("stock_widget"):
        stock_widget = copy.deepcopy(ctx.revision_snapshot["stock_widget"])
    elif ctx.artifacts.market and ctx.artifacts.market.snapshot:
        stock_widget = copy.deepcopy(ctx.artifacts.market.snapshot)
    if not stock_widget:
        return None
    payload: Dict[str, Any] = {
        "stock_widget": stock_widget,
        "reused": bool(getattr(ctx, "reused_stock", False)),
        "schedule_stage": "hedged_accessories",
    }
    if ctx.snapshot_age_seconds is not None:
        payload["snapshot_age_seconds"] = ctx.snapshot_age_seconds
    return payload


def compose_web_ready_payload(ctx: "PlannerPhaseContext") -> Optional[Dict[str, Any]]:
    web_payload: Optional[Dict[str, Any]] = None
    if ctx.artifacts.analysis and ctx.artifacts.analysis.web_context:
        web_payload = copy.deepcopy(ctx.artifacts.analysis.web_context)
    elif ctx.revision_snapshot and ctx.revision_snapshot.get("web_context"):
        web_payload = copy.deepcopy(ctx.revision_snapshot["web_context"])
    elif ctx.artifacts.web and ctx.artifacts.web.to_dict():
        web_payload = ctx.artifacts.web.to_dict()
    if not web_payload:
        return None
    payload: Dict[str, Any] = {
        "web_context": sanitize_for_json(web_payload),
        "reused": bool(getattr(ctx, "reused_web", False)),
        "schedule_stage": "hedged_accessories",
    }
    if ctx.snapshot_age_seconds is not None:
        payload["snapshot_age_seconds"] = ctx.snapshot_age_seconds
    return payload


async def stream_sql_lane(
    pipeline: "PlannerPipeline",
    *,
    ctx: "PlannerPhaseContext",
    registry: "PlannerToolRegistry",
    executed: Set[str],
    tool_state: Optional[Dict[str, Any]],
    run_sql_lane: bool,
) -> AsyncGenerator[Dict[str, Any], None]:
    reuse_sql = (ctx.reuse_sql and ctx.revision_snapshot is not None) or not run_sql_lane
    if not reuse_sql and ctx.snapshot_stale and ctx.revision_snapshot:
        stale_progress = EventEmitter.progress("sql_generation", "Cached SQL snapshot expired - rerunning dataset")
        stale_progress["data"]["ts"] = datetime.utcnow().isoformat()
        stale_progress["data"]["schedule_stage"] = "sql"
        stale_progress["data"]["parallel_group"] = "core_sequential"
        stale_progress["data"]["flow_mode"] = pipeline.flow_mode.value
        stale_progress["data"]["reused"] = False
        yield stale_progress
        for tool_event in pipeline._collect_tool_deltas_now(tool_state, ctx):
            yield tool_event

    if not reuse_sql:
        async for event in pipeline._stream_with_tool_state(
            registry.invoke("sql_generation", pipeline, ctx, executed=executed),
            tool_state,
            ctx,
        ):
            yield event
    else:
        ctx.reused_sql = True
        reuse_status = EventEmitter.progress("sql_generation", "Reusing cached SQL dataset")
        reuse_status["data"]["ts"] = datetime.utcnow().isoformat()
        reuse_status["data"]["schedule_stage"] = "sql"
        reuse_status["data"]["parallel_group"] = "core_sequential"
        reuse_status["data"]["flow_mode"] = pipeline.flow_mode.value
        reuse_status["data"]["reused"] = True
        yield reuse_status
        for tool_event in pipeline._collect_tool_deltas_now(tool_state, ctx):
            yield tool_event
        receipt = ctx.tool_receipts.get("sql_chain")
        if receipt:
            receipt.status = "reused"
            receipt.reused = True
            receipt.error = None
        sql_payload = compose_sql_ready_payload(ctx)
        if sql_payload:
            cached_sql = _cached_event(
                "sql_ready",
                sql_payload,
                schedule_stage="sql",
                flow_mode=pipeline.flow_mode,
                parallel_group="core_sequential",
                lane="sql",
            )
            yield pipeline._annotate_revision(cached_sql, ctx)
            mark_revision_completion(ctx, "sql")
            for tool_event in pipeline._collect_tool_deltas_now(tool_state, ctx):
                yield tool_event

    await pipeline._persist_session_state(
        ctx,
        record_sql=(not reuse_sql) and bool(ctx.artifacts.sql_generation and ctx.artifacts.sql_generation.sql),
        record_dataset_preview=True,
        record_artifacts=True,
    )
    # Ensure accessory readiness is emitted in parallel mode even if the tool stream failed to surface web readiness.
    if ctx.parallelism_enabled and not getattr(ctx, "web_ready_emitted", False):
        synthetic_web = {
            "event": "web_ready",
            "data": {
                "lane": "web",
                "reused": False,
                "schedule_stage": "hedged_accessories",
                "parallel_group": "tool_fanout",
                "flow_mode": pipeline.flow_mode.value,
                "ts": datetime.utcnow().isoformat(),
            },
        }
        yield pipeline._annotate_revision(synthetic_web, ctx)
        ctx.web_ready_emitted = True  # type: ignore[attr-defined]
    if not reuse_sql:
        sql_payload = compose_sql_ready_payload(ctx)
        if sql_payload:
            sql_payload.setdefault("parallel_group", "core_sequential")
            sql_payload.setdefault("flow_mode", pipeline.flow_mode.value)
            sql_payload.setdefault("ts", datetime.utcnow().isoformat())
            sql_payload.setdefault("lane", "sql")
            sql_payload["reused"] = False
            yield pipeline._annotate_revision(
                {
                    "event": "sql_ready",
                    "data": sanitize_for_json(sql_payload),
                },
                ctx,
            )
            mark_revision_completion(ctx, "sql")
    for tool_event in pipeline._collect_tool_deltas_now(tool_state, ctx):
        yield tool_event

    if reuse_sql:
        stock_payload = compose_stock_ready_payload(ctx)
        if stock_payload and not ctx.stock_only:
            ctx.reused_stock = True
            cached_stock = _cached_event(
                "stock_ready",
                stock_payload,
                schedule_stage="hedged_accessories",
                flow_mode=pipeline.flow_mode,
                parallel_group="tool_fanout",
                lane="market",
            )
            yield pipeline._annotate_revision(cached_stock, ctx)
            mark_revision_completion(ctx, "stock")
        web_payload = compose_web_ready_payload(ctx)
        if web_payload:
            ctx.reused_web = True
            cached_web = _cached_event(
                "web_ready",
                web_payload,
                schedule_stage="hedged_accessories",
                flow_mode=pipeline.flow_mode,
                parallel_group="tool_fanout",
                lane="web",
            )
            yield pipeline._annotate_revision(cached_web, ctx)
            mark_revision_completion(ctx, "web")
        if ctx.revision_targets and "stock" in ctx.revision_targets and not getattr(ctx, "stock_ready_emitted", False):
            synthetic_stock = {
                "event": "stock_ready",
                "data": {
                    "lane": "market",
                    "reused": False,
                    "schedule_stage": "hedged_accessories",
                    "parallel_group": "tool_fanout",
                    "flow_mode": pipeline.flow_mode.value,
                    "ts": datetime.utcnow().isoformat(),
                },
            }
            yield pipeline._annotate_revision(synthetic_stock, ctx)
            ctx.stock_ready_emitted = True  # type: ignore[attr-defined]
        ctx.accessories_prefetched = True


async def stream_chart_lane(
    pipeline: "PlannerPipeline",
    *,
    ctx: "PlannerPhaseContext",
    registry: "PlannerToolRegistry",
    executed: Set[str],
    tool_state: Optional[Dict[str, Any]],
    run_chart_lane: bool,
) -> AsyncGenerator[Dict[str, Any], None]:
    if not run_chart_lane:
        chart_payload = compose_chart_ready_payload(ctx)
        if chart_payload:
            cached_chart = _cached_event(
                "chart_ready",
                chart_payload,
                schedule_stage="chart",
                flow_mode=pipeline.flow_mode,
                parallel_group="core_sequential",
                lane="chart",
            )
            yield pipeline._annotate_revision(cached_chart, ctx)
            mark_revision_completion(ctx, "chart")
        return

    async for event in pipeline._stream_with_tool_state(
        registry.invoke("chart_generation", pipeline, ctx, executed=executed),
        tool_state,
        ctx,
    ):
        yield event
    await pipeline._persist_session_state(
        ctx,
        record_chart=bool(ctx.artifacts.chart and ctx.artifacts.chart.spec),
        record_artifacts=True,
    )
    mark_revision_completion(ctx, "chart")


def limit_sample_rows(rows: Optional[Sequence[Dict[str, Any]]], *, limit: int = 50) -> List[Dict[str, Any]]:
    if not isinstance(rows, Sequence):
        return []
    limited: List[Dict[str, Any]] = []
    for row in rows[:limit]:
        if isinstance(row, dict):
            limited.append(copy.deepcopy(row))
    return limited


# Backwards compatibility for callers still importing the old private helper name.
_limit_sample_rows = limit_sample_rows
