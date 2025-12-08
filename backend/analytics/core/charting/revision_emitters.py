# --- Analytics Function/Class Map ---
# Functions: emit_chart_patch, emit_analysis_revision
#   Role: Apply chart/analysis revisions and emit telemetry events.
#   Called from: analytics.flows.chart_revision facade, tests.analytics.test_chart_revision
#   Invokes: RevisionContext, patch_ops.normalize_chart_patch/apply_chart_patch_to_spec, EventEmitter
#   Why: Centralizes revision emission logic for reuse across flows and keeps facade thin.
# Helpers: build_patch_event, build_analysis_event
#   Role: Construct SSE payloads for chart/analysis revisions.
# --- End Analytics Function/Class Map ---
from __future__ import annotations

import copy
from datetime import datetime
from typing import Any, AsyncGenerator, Dict, Optional

from analytics.core.events import EventEmitter
from analytics.core.session_state import SessionStateRepository, get_session_state_repository

from .revision_context import (
    RevisionContext,
    MissingRevisionSnapshot,
    MissingChartSpec,
    MissingAnalysis,
    ChartPatch,
)
from .patch_ops import normalize_chart_patch, apply_chart_patch_to_spec


async def emit_chart_patch(
    *,
    session_id: str,
    patch: Dict[str, Any],
    reason: Optional[str] = None,
    source: Optional[str] = None,
    repository: Optional[SessionStateRepository] = None,
) -> AsyncGenerator[Dict[str, Any], None]:
    """Apply a chart patch and emit progress + patch events."""
    normalized = normalize_chart_patch(patch, reason=reason, source=source)
    repo = repository or get_session_state_repository()

    progress = EventEmitter.progress("chart_revision", "Applying chart revision patch...")
    progress["data"]["ts"] = datetime.utcnow().isoformat()
    yield progress

    try:
        revision = await RevisionContext.load(session_id, repository=repo)
        base_spec = revision.require_chart_spec()
    except MissingRevisionSnapshot as exc:
        error_event = EventEmitter.error(
            "chart_revision",
            str(exc),
            details={"session_id": session_id},
            code="CHART_REVISION_MISSING_SESSION",
        )
        error_event["data"]["ts"] = datetime.utcnow().isoformat()
        yield error_event
        yield build_patch_event(
            normalized,
            status="skipped",
            session_id=session_id,
            error="missing_session",
        )
        return
    except MissingChartSpec as exc:
        error_event = EventEmitter.error(
            "chart_revision",
            str(exc),
            details={"session_id": session_id},
            code="CHART_REVISION_MISSING_SPEC",
        )
        error_event["data"]["ts"] = datetime.utcnow().isoformat()
        yield error_event
        yield build_patch_event(
            normalized,
            status="skipped",
            session_id=session_id,
            error="missing_chart_spec",
        )
        return

    next_spec = apply_chart_patch_to_spec(base_spec, normalized)
    revision.record_chart_spec(next_spec, patch=normalized)
    await revision.persist(repository=repo)

    yield build_patch_event(
        normalized,
        status="applied",
        session_id=session_id,
    )


async def emit_analysis_revision(
    *,
    session_id: str,
    analysis: str,
    reason: Optional[str] = None,
    source: Optional[str] = None,
    repository: Optional[SessionStateRepository] = None,
) -> AsyncGenerator[Dict[str, Any], None]:
    """Apply an analysis revision and emit progress + result events."""
    progress = EventEmitter.progress("analysis_revision", "Applying analysis revision...")
    progress["data"]["ts"] = datetime.utcnow().isoformat()
    yield progress

    repo = repository or get_session_state_repository()
    try:
        revision = await RevisionContext.load(session_id, repository=repo)
        base_analysis = revision.require_analysis()
    except MissingRevisionSnapshot as exc:
        error_event = EventEmitter.error(
            "analysis_revision",
            str(exc),
            details={"session_id": session_id},
            code="ANALYSIS_REVISION_MISSING_SESSION",
        )
        error_event["data"]["ts"] = datetime.utcnow().isoformat()
        yield error_event
        yield build_analysis_event(
            analysis,
            session_id=session_id,
            status="skipped",
            reason=reason,
            source=source,
            error="missing_session",
        )
        return
    except MissingAnalysis as exc:
        error_event = EventEmitter.error(
            "analysis_revision",
            str(exc),
            details={"session_id": session_id},
            code="ANALYSIS_REVISION_MISSING_ANALYSIS",
        )
        error_event["data"]["ts"] = datetime.utcnow().isoformat()
        yield error_event
        yield build_analysis_event(
            analysis,
            session_id=session_id,
            status="skipped",
            reason=reason,
            source=source,
            error="missing_analysis",
        )
        return

    updated_analysis = analysis.strip() or base_analysis
    revision.record_analysis(updated_analysis, reason=reason)
    await revision.persist(repository=repo)

    yield build_analysis_event(
        updated_analysis,
        session_id=session_id,
        status="applied",
        reason=reason,
        source=source,
    )


def build_analysis_event(
    analysis: str,
    *,
    session_id: str,
    status: str,
    reason: Optional[str] = None,
    source: Optional[str] = None,
    error: Optional[str] = None,
) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "analysis": analysis,
        "status": status,
        "ts": datetime.utcnow().isoformat(),
        "session_id": session_id,
        "analysis_length": len(analysis or ""),
    }
    if reason:
        payload["reason"] = reason
    if source:
        payload["source"] = source
    if error:
        payload["error"] = error
    event = EventEmitter.result("analysis_revision", payload)
    event["event"] = "analysis_revision"
    event_data = event.setdefault("data", {})
    event_data.setdefault("ts", datetime.utcnow().isoformat())
    return event


def build_patch_event(
    patch: Dict[str, Any],
    *,
    status: str,
    session_id: str,
    error: Optional[str] = None,
) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "ops": patch["ops"],
        "status": status,
        "ts": datetime.utcnow().isoformat(),
        "session_id": session_id,
    }
    chart_type: Optional[str] = None
    stack_enabled: Optional[bool] = None
    stack_mode: Optional[str] = None
    for op in patch.get("ops", []):
        if not isinstance(op, dict):
            continue
        name = op.get("op")
        if name == "set_chart_type":
            value = op.get("value")
            if isinstance(value, str):
                stripped = value.strip()
                if stripped:
                    chart_type = stripped
        elif name == "set_stack":
            stack_flag = op.get("stack")
            if isinstance(stack_flag, bool):
                stack_enabled = stack_flag
            mode_value = op.get("mode")
            if isinstance(mode_value, str):
                stripped_mode = mode_value.strip()
                if stripped_mode:
                    stack_mode = stripped_mode
    if "reason" in patch:
        payload["reason"] = patch["reason"]
    if "source" in patch:
        payload["source"] = patch["source"]
    if "chart_id" in patch:
        payload["chart_id"] = patch["chart_id"]
    if chart_type:
        payload["chart_type"] = chart_type
    if stack_enabled is not None:
        payload["stack"] = stack_enabled
    if stack_mode:
        payload["stack_mode"] = stack_mode
    if error:
        payload["error"] = error
    event = EventEmitter.result("chart_patch", payload)
    event["event"] = "chart_patch"
    event_data = event.setdefault("data", {})
    event_data.setdefault("ts", datetime.utcnow().isoformat())
    return event

