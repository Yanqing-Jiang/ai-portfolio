# --- Analytics Function/Class Map ---
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

import logging
import time
from datetime import datetime
from typing import Any, AsyncGenerator, Dict, List, Optional, Set

from pydantic import ValidationError

from analytics.core.context import get_configs
from analytics.core.events import EventEmitter
from analytics.core.charting import plan_chart_rule_based, build_chart_spec
from analytics.validators import sanitize_for_json

from .stage_helpers import ensure_tool_receipt, hash_payload
from .sql_lane import stream_chart_lane, compose_chart_ready_payload, _cached_event

logger = logging.getLogger(__name__)
CONFIGS = get_configs()
_hash_payload = hash_payload


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

