from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, AsyncGenerator, Dict, Optional, Tuple

from analytics.core.session_state import SessionStateSnapshot, get_session_state_repository

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
    "sql_compiled": "sql",
    "sql_generated": "sql",
    "sql_validated": "sql",
    "execution_stats": "sql",
    "chart_planned": "chart",
    "chart_generated": "chart",
    "analysis_complete": "analysis",
    "analysis_streaming": "analysis",
    "workflow_complete": "workflow",
    "tool_call": "tools",
    "agent_turn": "agents",
    "agent_reasoning": "agents",
}

PARALLEL_GROUP_BY_STEP = {
    "intent_detection": "intent",
    "clarification": "clarification",
    "sql_compilation": "sql",
    "sql_execution": "sql",
    "analysis_generation": "analysis",
    "chart_generation": "chart",
}

def _resolve_parallel_group(event: Dict[str, Any]) -> Optional[str]:
    name = event.get("event")
    if isinstance(name, str) and name in PARALLEL_GROUP_BY_EVENT:
        return PARALLEL_GROUP_BY_EVENT[name]
    step = (event.get("data") or {}).get("step")
    if isinstance(step, str) and step in PARALLEL_GROUP_BY_STEP:
        return PARALLEL_GROUP_BY_STEP[step]
    return None


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


def _enrich_event(
    event: Dict[str, Any],
    *,
    sequence: int,
    parallel_group: Optional[str] = None,
    tool_group: Optional[str] = None,
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
    return event, seq


def _ensure_session_id(session_id: Optional[str]) -> str:
    return session_id or str(uuid.uuid4())


def _maybe_update_session_state(
    snapshot: SessionStateSnapshot,
    event: Dict[str, Any],
    query: str,
) -> bool:
    name = event.get("event")
    data = event.get("data") or {}
    updated = False

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
        if analysis:
            snapshot.record_outputs(analysis=analysis)
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

    async for raw_event in flow.events(query, session_id=resolved_session):
        parallel_group = _resolve_parallel_group(raw_event)
        tool_group = _resolve_tool_group(raw_event)
        enriched_event, sequence = _enrich_event(
            raw_event,
            sequence=sequence,
            parallel_group=parallel_group,
            tool_group=tool_group,
        )
        yield enriched_event

        if _maybe_update_session_state(snapshot, enriched_event, query):
            await repository.save(snapshot)

    await repository.save(snapshot)

