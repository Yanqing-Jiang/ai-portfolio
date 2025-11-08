from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any, AsyncGenerator, Dict, Mapping, Optional, Set, Tuple

from analytics.core import telemetry
from analytics.core.session_state import SessionStateSnapshot, get_session_state_repository
from analytics.artifacts import PipelineArtifacts
from analytics.core.events import EventEmitter, TimedEventEmitter
from analytics.validators import sanitize_for_json
from .planner_executor import PlannerExecutorFlow, run_planner_executor
from .schedulers import FlowMode, FlowStageIndex, get_stage_index, resolve_stage
from .sequencer import LANE_TOOL_MAP, LANE_TOOL_LOOKUP

PARALLEL_GROUP_BY_EVENT = {
    "session_started": "session",
    "classification_started": "classification",
    "classification_reasoning": "classification",
    "classification_complete": "classification",
    "classification_fallback": "classification",
    "intent_detection_started": "intent",
    "intent_detection_complete": "intent",
    "clarification_progress": "clarification",
    "clarification_request": "clarification",
    "clarification_resolved": "clarification",
    "clarification_timeout": "clarification",
    "clarification": "clarification",
    "schema_validation": "intent",
    "schema_clarifier": "classification",
    "schema_clarifier_result": "classification",
    "sql_compiled": "sql",
    "sql_generated": "sql",
    "sql_validated": "sql",
    "execution_stats": "sql",
    "sql_ready": "sql",
    "chart_planned": "chart",
    "chart_generated": "chart",
    "chart_ready": "chart",
    "analysis_complete": "analysis",
    "analysis_streaming": "analysis",
    "analysis_chunk": "analysis",
    "analysis_ready": "analysis",
    "workflow_complete": "workflow",
    "tool_call": "tools",
    "tool_call_delta": "agents",
    "tool_call_arguments": "agents",
    "agent_tool_complete": "agents",
    "tool_fanout": "web",
    "tool_execution": "web",
    "agent_turn": "agents",
    "agent_turn_start": "agents",
    "agent_turn_end": "agents",
    "tool_retry": "agents",
    "agent_reasoning": "agents",
    "web_research_agent": "web",
    "web_ready": "web",
    "stock_ready": "web",
    "hedged_accessories_complete": "web",
}

PARALLEL_GROUP_BY_STEP = {
    "intent_detection": "intent",
    "clarification": "clarification",
    "sql_compilation": "sql",
    "sql_execution": "sql",
    "analysis_generation": "analysis",
    "analysis_revision": "analysis",
    "chart_generation": "chart",
    "web_search": "web",
    "web_refresh": "web",
    "market_refresh": "web",
}

AGENT_TOOL_ALERT_THRESHOLD = 0.10
AGENT_TOOL_ALERT_MIN_CALLS = 5


def _resolve_lane_for_tool(tool_call: Mapping[str, Any]) -> Optional[str]:
    lane = tool_call.get("lane")
    if isinstance(lane, str) and lane.strip():
        return lane.strip().lower()
    tool_name = tool_call.get("name") or tool_call.get("tool")
    if isinstance(tool_name, str):
        normalized = tool_name.strip().lower()
        if normalized:
            return LANE_TOOL_LOOKUP.get(normalized)
    return None


def _update_agent_tool_metrics(
    snapshot: SessionStateSnapshot,
    lane: str,
    *,
    bucket: str,
    flow_mode: FlowMode,
    session_id: Optional[str],
) -> None:
    metrics = snapshot.tool_cache.setdefault(
        "agent_tool_metrics",
        {"call": {}, "complete": {}},
    )
    for key in ("call", "complete"):
        metrics.setdefault(key, {})
    counters = metrics[bucket]
    counters[lane] = int(counters.get(lane, 0)) + 1
    if bucket != "call":
        return
    total_calls = int(metrics["call"].get(lane, 0))
    total_completions = int(metrics["complete"].get(lane, 0))
    outstanding = max(total_calls - total_completions, 0)
    if total_calls < AGENT_TOOL_ALERT_MIN_CALLS:
        return
    if outstanding <= 0:
        return
    ratio = outstanding / max(total_calls, 1)
    if ratio >= AGENT_TOOL_ALERT_THRESHOLD:
        telemetry.agent_tool_gap(
            lane=lane,
            outstanding=outstanding,
            total_calls=total_calls,
            threshold=AGENT_TOOL_ALERT_THRESHOLD,
            session_id=session_id,
            flow=flow_mode.value,
        )

def _resolve_flow_mode(flow: Any) -> FlowMode:
    raw_mode = getattr(flow, "flow_mode", FlowMode.DIRECT)
    if isinstance(raw_mode, FlowMode):
        return raw_mode
    if isinstance(raw_mode, str):
        try:
            return FlowMode(raw_mode)
        except ValueError:
            return FlowMode.DIRECT
    return FlowMode.DIRECT


def _resolve_parallel_group(
    event: Dict[str, Any],
    *,
    stage_index: Optional[FlowStageIndex] = None,
) -> Tuple[Optional[str], Optional[str], Optional[bool]]:
    stage = None
    if stage_index is not None:
        name = event.get("event")
        data = event.get("data") or {}
        step = data.get("step")
        stage = resolve_stage(stage_index, event_name=name if isinstance(name, str) else None, step_name=step if isinstance(step, str) else None)
        if stage is not None:
            return stage.parallel_group, stage.key, stage.allows_parallel
    name = event.get("event")
    if isinstance(name, str) and name in PARALLEL_GROUP_BY_EVENT:
        return PARALLEL_GROUP_BY_EVENT[name], None, None
    step = (event.get("data") or {}).get("step")
    if isinstance(step, str) and step in PARALLEL_GROUP_BY_STEP:
        return PARALLEL_GROUP_BY_STEP[step], None, None
    return None, None, None


def _resolve_tool_group(event: Dict[str, Any]) -> Optional[str]:
    name = event.get("event")
    data = event.get("data") or {}
    if name == "tool_call":
        return data.get("tool")
    if name in {"tool_call_delta", "tool_call_arguments", "agent_tool_complete"}:
        tool_call = data.get("tool_call")
        if isinstance(tool_call, Mapping):
            tool_name = tool_call.get("name") or tool_call.get("tool")
            if tool_name:
                return str(tool_name)
    if name in {"agent_turn", "agent_turn_start", "agent_turn_end", "tool_retry"}:
        return data.get("role")
    if name == "agent_reasoning":
        return data.get("role")
    return None


def _extract_latest_artifacts(flow: Any) -> Optional[PipelineArtifacts]:
    candidates = []
    obj = flow
    if hasattr(obj, "latest_artifacts"):
        candidates.append(getattr(obj, "latest_artifacts"))
    if hasattr(obj, "_pipeline") and hasattr(obj._pipeline, "latest_artifacts"):
        candidates.append(obj._pipeline.latest_artifacts)
    if hasattr(obj, "_planner"):
        planner = getattr(obj, "_planner")
        if hasattr(planner, "latest_artifacts"):
            candidates.append(planner.latest_artifacts)
        if hasattr(planner, "_pipeline") and hasattr(planner._pipeline, "latest_artifacts"):
            candidates.append(planner._pipeline.latest_artifacts)
    for candidate in candidates:
        try:
            value = candidate() if callable(candidate) else candidate
        except Exception:
            continue
        if isinstance(value, PipelineArtifacts):
            return value
    return None


def _attach_agent_metadata(event: Dict[str, Any], snapshot: SessionStateSnapshot) -> Dict[str, Any]:
    metadata = snapshot.agent_run_metadata()
    if not metadata:
        return event
    data = event.setdefault("data", {})
    if not isinstance(data, dict):
        return event
    agent_block = data.get("agent_metadata")
    if isinstance(agent_block, dict):
        merged = {**metadata, **agent_block}
    else:
        merged = metadata
    data["agent_metadata"] = sanitize_for_json(merged)
    event["data"] = sanitize_for_json(data)
    return event


def _enrich_event(
    event: Dict[str, Any],
    *,
    sequence: int,
    parallel_group: Optional[str] = None,
    tool_group: Optional[str] = None,
    stage_key: Optional[str] = None,
    stage_allows_parallel: Optional[bool] = None,
) -> Tuple[Dict[str, Any], int]:
    seq = sequence + 1
    data = event.setdefault("data", {})
    data.setdefault("ts", datetime.utcnow().isoformat())
    event["seq"] = seq
    data["sequence"] = seq
    if parallel_group:
        data["parallel_group"] = parallel_group
    if tool_group:
        data["tool_group"] = tool_group
    if stage_key:
        data.setdefault("schedule_stage", stage_key)
    if stage_allows_parallel is not None:
        data.setdefault("stage_allows_parallel", stage_allows_parallel)
    event["data"] = sanitize_for_json(data)
    return event, seq


def _ensure_session_id(session_id: Optional[str]) -> str:
    return session_id or str(uuid.uuid4())


def _maybe_update_session_state(
    snapshot: SessionStateSnapshot,
    event: Dict[str, Any],
    query: str,
    *,
    flow_mode: FlowMode,
) -> bool:
    name = event.get("event")
    data = event.get("data") or {}
    updated = False
    now_ts = datetime.now(timezone.utc)
    schedule_stage = data.get("schedule_stage")
    parallel_group = data.get("parallel_group")
    if schedule_stage:
        snapshot.record_schedule_stage(
            stage=schedule_stage,
            parallel_group=parallel_group,
            event=name if isinstance(name, str) else None,
            ts=data.get("ts"),
            flow_mode=flow_mode.value,
        )
        updated = True

    if name == "intent_detection_complete":
        snapshot.record_query(query, data.get("intent_key"))
        updated = True
    elif name == "sql_generated":
        sql_text = data.get("sql")
        if sql_text:
            snapshot.record_outputs(sql=sql_text)
            updated = True
    elif name == "sql_attempts":
        attempts = data.get("attempts") or []
        analytics_cache = snapshot.tool_cache.setdefault("analytics", {})
        analytics_cache["sql_attempts"] = attempts
        snapshot.touch()
        updated = True
    elif name == "chart_generated":
        chart_spec = data.get("chart_spec")
        if chart_spec is not None:
            snapshot.record_outputs(chart_spec=chart_spec)
            updated = True
    elif name in {"analysis_complete", "analysis_ready", "analysis_revision_ready"}:
        analysis_text = data.get("analysis") or data.get("analysis_text")
        if isinstance(analysis_text, str) and analysis_text.strip():
            snapshot.record_outputs(analysis=analysis_text)
            metadata = snapshot.tool_cache.setdefault("analytics", {})
            analysis_length = data.get("analysis_length")
            if isinstance(analysis_length, int):
                metadata["last_analysis_length"] = analysis_length
            updated = True
    elif name == "analysis_complete":
        analysis = data.get("analysis")
        analysis_text: Optional[str] = None
        if isinstance(analysis, str) and analysis.strip():
            analysis_text = analysis
        elif isinstance(analysis, dict):
            nested = analysis.get("analysis")
            if isinstance(nested, str) and nested.strip():
                analysis_text = nested
            else:
                try:
                    analysis_text = json.dumps(analysis)
                except Exception:
                    analysis_text = str(analysis)
        if analysis_text:
            snapshot.record_outputs(analysis=analysis_text)
            updated = True
    elif name == "tool_parallel_result":
        tool = (data.get("tool") or "").strip()
        payload = data.get("payload") or {}
        if tool.startswith("web_retriever") and payload:
            cache_payload = dict(payload)
            cache_payload.setdefault("query", cache_payload.get("query_terms"))
            snapshot.record_tool_result("web_search", cache_payload)
            updated = True
    elif name in {"sql_ready", "sql_revision_ready"}:
        snapshot.record_lane_fast_path_marker("sql_ready_seen_at", at=now_ts)
        updated = True
    elif name == "lane_reused":
        lane = (data.get("lane") or "").strip().lower()
        if lane:
            metadata = {
                "lane": lane,
                "reason": data.get("reason"),
                "source": data.get("source"),
                "age_seconds": data.get("age_seconds"),
                "ts": data.get("ts") or now_ts.isoformat(),
            }
            latency_ms = snapshot.lane_fast_path_latency_ms("sql_ready_seen_at", now=now_ts)
            if latency_ms is not None:
                metadata["fast_path_latency_ms"] = latency_ms
            snapshot.record_lane_reuse(lane, metadata)
            snapshot.record_agent_reasoning(
                f"lane_reuse:{lane}",
                f"{lane.title()} lane reused",
                lane=lane,
                metadata=metadata,
            )
            for tool in LANE_TOOL_MAP.get(lane, ()):
                synthetic_receipt = {
                    "status": "reused",
                    "lane": lane,
                    "reused": True,
                    "reason": data.get("reason"),
                    "source": data.get("source"),
                    "ts": metadata["ts"],
                }
                if latency_ms is not None:
                    synthetic_receipt["fast_path_latency_ms"] = latency_ms
                age_seconds = data.get("age_seconds")
                if age_seconds is not None:
                    synthetic_receipt["age_seconds"] = age_seconds
                snapshot.record_tool_receipt(tool, synthetic_receipt)
            updated = True
    elif name in {"tool_call_delta", "tool_call_arguments", "agent_tool_call"}:
        tool_call = data.get("tool_call")
        if isinstance(tool_call, Mapping):
            tool_name = tool_call.get("name") or tool_call.get("id")
            if tool_name:
                receipt_payload = {
                    "call_id": tool_call.get("id"),
                    "arguments": tool_call.get("arguments"),
                    "arguments_delta": tool_call.get("arguments_delta"),
                    "sequence_number": tool_call.get("sequence_number"),
                    "output_index": tool_call.get("output_index"),
                    "status": tool_call.get("status"),
                    "lane": tool_call.get("lane"),
                }
                snapshot.record_tool_receipt(str(tool_name), receipt_payload)
                updated = True
            lane = _resolve_lane_for_tool(tool_call)
            if lane:
                _update_agent_tool_metrics(
                    snapshot,
                    lane,
                    bucket="call",
                    flow_mode=flow_mode,
                    session_id=snapshot.session_id,
                )
    elif name == "agent_tool_complete":
        tool_call = data.get("tool_call")
        if isinstance(tool_call, Mapping):
            tool_name = tool_call.get("name") or tool_call.get("id")
            if tool_name:
                receipt_payload = {
                    "call_id": tool_call.get("id"),
                    "status": tool_call.get("status"),
                    "sequence_number": tool_call.get("sequence_number"),
                    "output_index": tool_call.get("output_index"),
                }
                existing = snapshot.tool_cache.get("tool_receipts", {}).get(str(tool_name))
                if isinstance(existing, Mapping):
                    merged = dict(existing)
                    merged.update({k: v for k, v in receipt_payload.items() if v is not None})
                    receipt_payload = merged
                snapshot.record_tool_receipt(str(tool_name), receipt_payload)
                updated = True
            lane = _resolve_lane_for_tool(tool_call)
            if lane:
                _update_agent_tool_metrics(
                    snapshot,
                    lane,
                    bucket="complete",
                    flow_mode=flow_mode,
                    session_id=snapshot.session_id,
                )

    return updated



async def emit_revision_lane(
    flow: Any,
    *,
    lane: str,
    generator: AsyncGenerator[Dict[str, Any], None],
    session_id: Optional[str],
    flow_label: Optional[str],
) -> AsyncGenerator[Dict[str, Any], None]:
    """Wrap a revision lane generator with start/complete telemetry events."""
    step_name = f"{lane}_revision"
    emitter = TimedEventEmitter(session_id=session_id, flow=flow_label)
    start_event = EventEmitter.status(step_name, f"Refreshing {lane} lane")
    start_event.setdefault("data", {})
    start_event["data"].update(
        {
            "lane": lane,
            "revision": True,
            "phase": "start",
        }
    )
    yield start_event
    emitter.start_step(step_name)
    try:
        async for event in generator:
            yield event
    finally:
        elapsed_ms = emitter.end_step(step_name)
        complete_event = EventEmitter.status(step_name, f"{lane.title()} lane complete")
        complete_event.setdefault("data", {})
        complete_event["data"].update(
            {
                "lane": lane,
                "revision": True,
                "phase": "complete",
            }
        )
        if elapsed_ms:
            complete_event["data"]["elapsed_ms"] = elapsed_ms
        yield complete_event


async def instrument_events(
    flow: Any,
    query: str,
    session_id: Optional[str],
    flow_label: Optional[str],
    *,
    sequencer: Optional[Any] = None,
    lane_states: Optional[Dict[str, str]] = None,
    revision_targets: Optional[Set[str]] = None,
    emit_prefill_summary: Optional[bool] = None,
    sequencer_state: Optional[Any] = None,
) -> AsyncGenerator[Dict[str, Any], None]:
    repository = get_session_state_repository()
    resolved_session = _ensure_session_id(session_id)
    snapshot = await repository.load(resolved_session)
    if snapshot is None:
        snapshot = SessionStateSnapshot(session_id=resolved_session)
        await repository.save(snapshot)

    sequence = 0
    flow_mode = _resolve_flow_mode(flow)
    stage_index = get_stage_index(flow_mode)

    if hasattr(flow, "events") and callable(getattr(flow, "events")):
        event_kwargs: Dict[str, Any] = {"session_id": resolved_session}
        if sequencer is not None:
            event_kwargs["sequencer"] = sequencer
            if lane_states is not None:
                event_kwargs["lane_states"] = lane_states
            if revision_targets is not None:
                event_kwargs["revision_targets"] = revision_targets
            if emit_prefill_summary is not None:
                event_kwargs["emit_prefill_summary"] = emit_prefill_summary
            if sequencer_state is not None:
                event_kwargs["sequencer_state"] = sequencer_state
        event_stream = flow.events(query, **event_kwargs)
    elif isinstance(flow, PlannerExecutorFlow):
        event_stream = run_planner_executor(query, session_id=resolved_session)
    else:
        raise AttributeError("Flow object does not expose an events() coroutine")

    async for raw_event in event_stream:
        parallel_group, stage_key, stage_allows_parallel = _resolve_parallel_group(raw_event, stage_index=stage_index)
        tool_group = _resolve_tool_group(raw_event)
        enriched_event, sequence = _enrich_event(
            raw_event,
            sequence=sequence,
            parallel_group=parallel_group,
            tool_group=tool_group,
            stage_key=stage_key,
            stage_allows_parallel=stage_allows_parallel,
        )
        enriched_event = _attach_agent_metadata(enriched_event, snapshot)
        yield enriched_event

        if _maybe_update_session_state(snapshot, enriched_event, query, flow_mode=flow_mode):
            await repository.save(snapshot)

    artifacts = _extract_latest_artifacts(flow)
    if artifacts:
        payload = artifacts.to_dict()
        if payload:
            snapshot.record_artifacts(payload)

    await repository.save(snapshot)








