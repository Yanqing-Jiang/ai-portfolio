from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Any, AsyncGenerator, Dict, Optional, Tuple

from analytics.core.session_state import SessionStateSnapshot, get_session_state_repository
from analytics.artifacts import PipelineArtifacts
from analytics.validators import sanitize_for_json
from .planner_executor import PlannerExecutorFlow, run_planner_executor
from .schedulers import FlowMode, FlowStageIndex, get_stage_index, resolve_stage

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
    "tool_fanout": "web",
    "tool_execution": "web",
    "agent_turn": "agents",
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
}

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
    if name == "agent_turn":
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
        if tool == "web_retriever" and payload:
            cache_payload = dict(payload)
            cache_payload.setdefault("query", cache_payload.get("query_terms"))
            snapshot.record_tool_result("web_search", cache_payload)
            updated = True

    return updated



async def instrument_events(
    flow: Any,
    query: str,
    session_id: Optional[str],
    flow_label: Optional[str],
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
        event_stream = flow.events(query, session_id=resolved_session)
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
        yield enriched_event

        if _maybe_update_session_state(snapshot, enriched_event, query, flow_mode=flow_mode):
            await repository.save(snapshot)

    artifacts = _extract_latest_artifacts(flow)
    if artifacts:
        payload = artifacts.to_dict()
        if payload:
            snapshot.record_artifacts(payload)

    await repository.save(snapshot)






