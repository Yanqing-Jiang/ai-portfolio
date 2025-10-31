from __future__ import annotations

from datetime import datetime
from typing import Any, AsyncGenerator, Dict, Optional, Sequence, Set, TYPE_CHECKING

from analytics.core import telemetry
from analytics.validators import sanitize_for_json

from ..tooling import get_default_tool_adapters, run_tool_parallelism
from .revision import mark_revision_completion

if TYPE_CHECKING:  # pragma: no cover - typing only
    from ..schedulers import ModeConfig
    from .planner_executor import PlannerPipeline, PlannerPhaseContext
    from ..pipeline_tools import PlannerToolRegistry


__all__ = [
    "ensure_analysis_dependencies",
    "stream_analysis_lane",
]


async def ensure_analysis_dependencies(
    pipeline: "PlannerPipeline",
    ctx: "PlannerPhaseContext",
    *,
    mode_config: "ModeConfig",
) -> AsyncGenerator[Dict[str, Any], None]:
    if getattr(ctx, "accessories_prefetched", False):
        return

    required_tools: Set[str] = set()
    lane_refresh_flags = dict(getattr(ctx, "lane_refresh_required", {}) or {})
    stock_refresh_required = bool(lane_refresh_flags.get("market", True))
    web_refresh_required = bool(lane_refresh_flags.get("web", True))
    has_cached_stock = bool(ctx.artifacts.analysis and ctx.artifacts.analysis.stock_widget)
    if not has_cached_stock:
        market_artifact = getattr(ctx.artifacts, "market", None)
        has_cached_stock = bool(market_artifact and getattr(market_artifact, "snapshot", None))
    if not has_cached_stock and getattr(ctx, "stock_widget_seeded", False):
        has_cached_stock = True
    has_cached_web = bool(ctx.artifacts.analysis and ctx.artifacts.analysis.web_context)

    if ctx.parallelism_enabled:
        existing = getattr(ctx, "tool_parallel_results", []) or []

        def _has_completed(tool_name: str) -> bool:
            return any(
                result.get("tool") == tool_name
                and str(result.get("status") or "").strip().lower() in {"completed", "complete", "success"}
                for result in existing
            )

        def _ready_entry(event_name: str) -> Optional[Dict[str, Any]]:
            normalized_event = event_name.strip().lower()
            for result in existing:
                if str(result.get("event") or "").strip().lower() == normalized_event:
                    return result
            return None

        stock_ready_entry = _ready_entry("stock_ready")
        web_ready_entry = _ready_entry("web_ready")

        def _emit_cache_hit(tool_name: str, ready_entry: Dict[str, Any]) -> None:
            if not isinstance(ready_entry, dict):
                return
            payload = ready_entry.get("payload")
            telemetry_payload: Dict[str, Any] = {
                "tool": tool_name,
                "event": ready_entry.get("event"),
                "reason": "ready_cached",
                "parallel_group": "tool_fanout",
            }
            if isinstance(payload, dict):
                lane_val = payload.get("lane")
                if isinstance(lane_val, str):
                    telemetry_payload["lane"] = lane_val
                reused_flag = payload.get("reused")
                if reused_flag is not None:
                    telemetry_payload["reused"] = reused_flag
                payload_hash = payload.get("payloadHash") or payload.get("hash")
                if payload_hash:
                    telemetry_payload["payload_hash"] = payload_hash
            telemetry.tool_parallelism(
                stage="cache_hit",
                session_id=getattr(ctx, "session_id", None),
                flow=getattr(ctx, "flow_label", None),
                payload=telemetry_payload,
            )

        if not has_cached_stock and stock_refresh_required:
            if stock_ready_entry:
                _emit_cache_hit("stock_tracker", stock_ready_entry)
            elif not _has_completed("stock_tracker"):
                required_tools.add("stock_tracker")
        if not has_cached_web and web_refresh_required:
            if web_ready_entry:
                _emit_cache_hit("web_retriever", web_ready_entry)
            elif not _has_completed("web_retriever"):
                required_tools.add("web_retriever")

    if required_tools:
        adapter_lookup = {adapter.name: adapter for adapter in get_default_tool_adapters()}
        subset = [adapter_lookup[name] for name in required_tools if name in adapter_lookup]
        if subset:
            async for event in run_tool_parallelism(ctx, adapters=subset, concurrency_override=len(subset)):
                derived_events = pipeline._ingest_tool_event(ctx, event)
                yield pipeline._mark_delta_event(event, ctx)
                for derived_event in derived_events:
                    yield derived_event

    has_web_context = (
        ctx.web_search is not None
        or has_cached_web
        or getattr(ctx, "web_search_seeded", False)
    )
    if not has_web_context and not web_refresh_required:
        has_web_context = True
    if not has_web_context and mode_config.accessories_in_critical_path:
        if web_refresh_required:
            async for event in pipeline._web_search_phase(ctx):
                yield event

    ctx.accessories_prefetched = True


async def stream_analysis_lane(
    pipeline: "PlannerPipeline",
    *,
    ctx: "PlannerPhaseContext",
    registry: "PlannerToolRegistry",
    executed: Set[str],
    tool_state: Optional[Dict[str, Any]],
    mode_config: "ModeConfig",
) -> AsyncGenerator[Dict[str, Any], None]:
    if mode_config.accessories_in_critical_path:
        async for event in pipeline._stream_with_tool_state(
            pipeline._web_search_phase(ctx),
            tool_state,
            ctx,
        ):
            yield event
        await pipeline._persist_session_state(ctx, record_artifacts=True)

    async for event in pipeline._stream_with_tool_state(
        registry.invoke("analysis_generation", pipeline, ctx, executed=executed),
        tool_state,
        ctx,
    ):
        yield event
    await pipeline._persist_session_state(
        ctx,
        record_analysis=bool(
            ctx.artifacts.analysis and ctx.artifacts.analysis.analysis_text
        ),
        record_artifacts=True,
    )
    mark_revision_completion(ctx, "analysis")
    async for tool_event in pipeline._drain_tool_state_async(tool_state, ctx):
        yield tool_event
