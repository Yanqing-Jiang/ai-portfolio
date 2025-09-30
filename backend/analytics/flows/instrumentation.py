from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, AsyncGenerator, Dict, Optional, Tuple

from analytics.core.memory_gate import MemoryGate, MemoryGateDecision
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

_memory_gate: Optional[MemoryGate] = None


def _get_memory_gate() -> MemoryGate:
    global _memory_gate
    if _memory_gate is None:
        repository = get_session_state_repository()
        _memory_gate = MemoryGate(repository=repository)
    return _memory_gate


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


def _format_gate_event(decision: MemoryGateDecision) -> Dict[str, Any]:
    return {
        "event": "memory_gate_decision",
        "data": {
            "policy": decision.policy,
            "reasons": decision.reasons,
            "reuse_sql": decision.reuse_sql,
            "reuse_chart": decision.reuse_chart,
            "reuse_analysis": decision.reuse_analysis,
            "tool_directives": {
                name: directive.model_dump()
                for name, directive in decision.tool_directives.items()
            },
            "ts": datetime.utcnow().isoformat(),
        },
    }


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
    elif name == "chart_generated":
        chart_spec = data.get("chart_spec")
        if chart_spec:
            snapshot.record_outputs(chart_spec=chart_spec)
            updated = True
    elif name == "analysis_complete":
        analysis = data.get("analysis")
        if analysis:
            snapshot.record_outputs(analysis=analysis)
            updated = True
    return updated


def _ensure_session_id(session_id: Optional[str]) -> str:
    return session_id or str(uuid.uuid4())


async def instrument_events(
    flow: Any,
    query: str,
    session_id: Optional[str],
    flow_label: Optional[str],
) -> AsyncGenerator[Dict[str, Any], None]:
    memory_gate = _get_memory_gate()
    resolved_session = _ensure_session_id(session_id)
    decision = await memory_gate.evaluate(
        session_id=resolved_session,
        query=query,
        flow_label=flow_label or getattr(flow, "flow_label", None) or "planner-executor",
    )
    session_snapshot = decision.state
    await memory_gate.repository.save(session_snapshot)

    sequence = 0
    gate_event_emitted = False

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

        if not gate_event_emitted and raw_event.get("event") == "classification_complete":
            gate_event_emitted = True
            gate_event, sequence = _enrich_event(
                _format_gate_event(decision),
                sequence=sequence,
                parallel_group="memory",
            )
            yield gate_event

        if _maybe_update_session_state(session_snapshot, enriched_event, query):
            await memory_gate.repository.save(session_snapshot)

    if not gate_event_emitted:
        gate_event, sequence = _enrich_event(
            _format_gate_event(decision),
            sequence=sequence,
            parallel_group="memory",
        )
        yield gate_event

    await memory_gate.repository.save(session_snapshot)
