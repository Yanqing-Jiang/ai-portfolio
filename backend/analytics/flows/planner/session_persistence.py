# --- Analytics Function/Class Map ---
# Function: persist_session_state
#   Role: Persist planner artifacts/receipts and metadata into SessionStateSnapshot.
#   Called from: analytics.flows.planner_executor (facade helper)
#   Invokes: session_state repository, snapshot helpers, receipt serialization
#   Why: Isolate snapshot persistence so planner_executor stays thin.
# --- End Analytics Function/Class Map ---
from __future__ import annotations

import copy
from typing import Any, Dict, Mapping, Optional

from analytics.core.config_store import get_config_store
from analytics.core.session_state import (
    SessionStateSnapshot,
    digest_tool_payload,
    get_session_state_repository,
    normalize_row_count,
)
from analytics.validators import sanitize_for_json
from analytics.routing import FollowUpRoute
from .receipts import ToolInvocationReceipt
from .stage_helpers import _build_revision_snapshot_payload
from .result_payload import compose_web_ready_payload


async def persist_session_state(
    ctx: Any,
    *,
    record_sql: bool = False,
    record_chart: bool = False,
    record_analysis: bool = False,
    record_web: bool = False,
    record_dataset_preview: bool = False,
    tool_bundle: Optional[Dict[str, Any]] = None,
    record_artifacts: bool = True,
) -> None:
    session_id = getattr(ctx, "session_id", None)
    if not session_id:
        return
    repository = get_session_state_repository()
    snapshot = await repository.load(session_id)
    if snapshot is None:
        snapshot = SessionStateSnapshot(session_id=session_id)
    updated = False
    sql_artifact = ctx.artifacts.sql_generation if record_sql else None
    if sql_artifact and sql_artifact.sql:
        snapshot.record_outputs(sql=sql_artifact.sql)
        updated = True
    execution_artifact = ctx.artifacts.sql_execution if hasattr(ctx.artifacts, "sql_execution") else None
    row_count_value: Optional[int] = None
    raw_row_count: Any = None
    dataset_receipt_expected = False
    dataset_receipt_written = False
    if execution_artifact:
        preview_rows = getattr(execution_artifact, "dataset_preview", None) or getattr(
            execution_artifact, "sample_rows", None
        )
        raw_row_count = getattr(execution_artifact, "row_count", None)
        row_count_value = normalize_row_count(raw_row_count)
        if row_count_value is not None and row_count_value != raw_row_count:
            try:
                execution_artifact.row_count = row_count_value
            except Exception:
                pass
        row_count_provided = False
        if raw_row_count is not None:
            if isinstance(raw_row_count, str):
                row_count_provided = bool(raw_row_count.strip())
            else:
                row_count_provided = True
        has_preview_rows = bool(preview_rows and any(preview_rows))
        dataset_receipt_expected = has_preview_rows or row_count_value is not None or row_count_provided
        persist_preview_requested = any(
            [
                record_dataset_preview,
                record_artifacts,
                record_sql,
                record_web,
                record_chart,
                record_analysis,
                bool(tool_bundle),
            ]
        )
        should_persist_preview = persist_preview_requested and (has_preview_rows or row_count_value is not None)
        if should_persist_preview:
            sanitized_preview = sanitize_for_json(
                {
                    "rows": preview_rows or [],
                    "row_count": row_count_value,
                }
            )
            snapshot.record_tool_result("planner_dataset_preview", sanitized_preview)
            dataset_receipt_written = True
            updated = True
    chart_artifact = ctx.artifacts.chart if record_chart else None
    if chart_artifact and chart_artifact.spec:
        snapshot.record_outputs(chart_spec=chart_artifact.spec)
        updated = True
    market_artifact = getattr(ctx.artifacts, "market", None)
    if market_artifact and getattr(market_artifact, "snapshot", None):
        snapshot.record_tool_result(
            "planner_stock_widget",
            sanitize_for_json(market_artifact.snapshot),
        )
        snapshot.touch_lane("market")
        updated = True
    web_artifact = ctx.artifacts.web if record_web else None
    if web_artifact:
        web_payload = web_artifact.to_dict()
        summary = web_payload.get("summary")
        snippets = web_payload.get("snippets")
        if (isinstance(summary, str) and summary.strip()) or (isinstance(snippets, list) and any(snippets)):
            snapshot.record_tool_result("web_search", sanitize_for_json(web_payload))
            updated = True
    analysis_artifact = ctx.artifacts.analysis if record_analysis else None
    if analysis_artifact and analysis_artifact.analysis_text:
        snapshot.record_outputs(analysis=analysis_artifact.analysis_text)
        updated = True
    if tool_bundle:
        sanitized_bundle = sanitize_for_json(tool_bundle)
        snapshot.record_tool_result("planner_bundle", sanitized_bundle)
        if isinstance(tool_bundle, Mapping):
            if tool_bundle.get("web_context"):
                snapshot.touch_lane("web")
            if tool_bundle.get("stock_widget"):
                snapshot.touch_lane("market")
        updated = True
    if record_artifacts:
        artifacts_payload = ctx.artifacts.to_dict()
        if artifacts_payload:
            snapshot.record_artifacts(artifacts_payload)
            if isinstance(artifacts_payload, Mapping):
                web_payload = artifacts_payload.get("web")
                if (
                    web_payload
                    and not record_web
                    and isinstance(web_payload, Mapping)
                    and (
                        (isinstance(web_payload.get("summary"), str) and web_payload.get("summary").strip())
                        or (
                            isinstance(web_payload.get("snippets"), list)
                            and any(web_payload.get("snippets"))
                        )
                    )
                ):
                    snapshot.record_tool_result("web_search", sanitize_for_json(web_payload))
                    updated = True
                if artifacts_payload.get("web"):
                    snapshot.touch_lane("web")
                analysis_payload = artifacts_payload.get("analysis")
                if isinstance(analysis_payload, Mapping) and analysis_payload.get("web_context"):
                    snapshot.touch_lane("web")
                market_payload = artifacts_payload.get("market")
                if isinstance(market_payload, Mapping) and market_payload.get("snapshot"):
                    snapshot.touch_lane("market")
            updated = True
    revision_payload = _build_revision_snapshot_payload(ctx)
    if revision_payload:
        snapshot.record_revision_snapshot(revision_payload)
        ctx.revision_snapshot = revision_payload
        updated = True
    planner_meta = snapshot.tool_cache.setdefault("planner_metadata", {})
    route_value = getattr(ctx, "follow_up_route", FollowUpRoute.FULL_PIPELINE).value
    if planner_meta.get("follow_up_route") != route_value:
        planner_meta["follow_up_route"] = route_value
        snapshot.tool_cache["planner_metadata"] = planner_meta
        updated = True
    clar_answers = getattr(ctx, "clarification_answers", None)
    if clar_answers:
        cleaned_answers = [ans for ans in clar_answers if isinstance(ans, Mapping)]
        if cleaned_answers:
            try:
                answers_payload = sanitize_for_json(list(cleaned_answers))
            except Exception:
                answers_payload = list(cleaned_answers)
            snapshot.agents_clarifications = (
                answers_payload if isinstance(answers_payload, list) else list(cleaned_answers)
            )
            snapshot.routing["clarifications_needed"] = False
            updated = True
    clar_needed_flag = getattr(ctx, "clarifications_needed", None)
    if clar_needed_flag is not None:
        snapshot.routing["clarifications_needed"] = bool(clar_needed_flag)
        updated = True
    receipts = getattr(ctx, "tool_receipts", None)
    if receipts:
        for tool_name, receipt in receipts.items():
            if isinstance(receipt, ToolInvocationReceipt):
                snapshot.record_tool_receipt(tool_name, receipt.to_dict())
            elif isinstance(receipt, dict):
                snapshot.record_tool_receipt(tool_name, sanitize_for_json(receipt))
        updated = True
    snapshot.tool_cache["pipeline_mode"] = getattr(ctx, "flow_mode", None)
    if record_analysis or tool_bundle:
        digest_payload = digest_tool_payload(
            {
                "analysis": getattr(ctx.artifacts, "analysis", None),
                "tool_bundle": tool_bundle,
                "web_context": getattr(ctx.artifacts, "web", None),
            }
        )
        if digest_payload:
            snapshot.record_tool_result("planner_digest", digest_payload)
            updated = True
    # Record web summary from ctx.web_search if present and not already in artifacts
    if getattr(ctx, "web_search", None):
        web_summary = getattr(ctx.web_search, "summary", None)
        web_snippets = getattr(ctx.web_search, "snippets", None)
        if web_summary or web_snippets:
            web_payload = {
                "summary": web_summary,
                "snippets": web_snippets,
                "latency_ms": getattr(ctx.web_search, "latency_ms", None),
            }
            snapshot.record_tool_result("web_search", sanitize_for_json(web_payload))
            snapshot.touch_lane("web")
            updated = True

    # Compose and persist web payload from artifacts/snapshot when present
    web_ready_payload = compose_web_ready_payload(ctx)
    if web_ready_payload:
        snapshot.record_tool_result("web_ready", web_ready_payload)
        updated = True

    # Persist dataset receipt when expected but not yet written
    if dataset_receipt_expected and not dataset_receipt_written and record_dataset_preview:
        snapshot.record_tool_result(
            "planner_dataset_preview",
            {"rows": [], "row_count": row_count_value},
        )
        updated = True
    if updated:
        await repository.save(snapshot)


