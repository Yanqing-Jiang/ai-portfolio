from __future__ import annotations

import json
import logging
import time
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional, Mapping

_TELEMETRY_LOGGER = logging.getLogger("analytics.telemetry")


def _serialize(payload: Dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=True, default=str)


def _emit(payload: Dict[str, Any]) -> None:
    try:
        _TELEMETRY_LOGGER.info(_serialize(payload))
    except Exception:
        _TELEMETRY_LOGGER.debug("Failed to emit telemetry payload", exc_info=True)


def _base_payload(event: str, *, session_id: Optional[str] = None, flow: Optional[str] = None) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "event": event,
        "ts": datetime.utcnow().isoformat(),
    }
    if session_id:
        payload["session_id"] = session_id
    if flow:
        payload["flow"] = flow
    return payload


def catalog_trace(
    *,
    intent_key: Optional[str],
    query: Optional[str],
    templates: Iterable[Dict[str, Any]],
    selected_template: Optional[str] = None,
    elapsed_ms: Optional[int] = None,
    session_id: Optional[str] = None,
    flow: Optional[str] = None,
) -> None:
    payload = _base_payload("catalog_trace", session_id=session_id, flow=flow)
    payload.update(
        {
            "intent_key": intent_key,
            "query": query,
            "selected_template": selected_template,
            "elapsed_ms": elapsed_ms,
            "templates": [
                {
                    "id": str(item.get("id") or item.get("name") or item.get("slug") or "unknown"),
                    "name": item.get("name"),
                    "score": item.get("score"),
                    "source": item.get("source"),
                }
                for item in templates
            ],
        }
    )
    _emit(payload)


def intent_resolution(
    *,
    intent_key: Optional[str],
    confidence: Optional[float],
    slot_statuses: Dict[str, Any],
    slot_followups: Iterable[Any],
    elapsed_ms: Optional[int] = None,
    session_id: Optional[str] = None,
    flow: Optional[str] = None,
    resolver_status: Optional[str] = None,
    clarification_sources: Optional[Iterable[str]] = None,
) -> None:
    payload = _base_payload('intent_resolution', session_id=session_id, flow=flow)
    payload.update(
        {
            'intent_key': intent_key,
            'confidence': confidence,
            'slot_statuses': slot_statuses,
            'slot_followups': list(slot_followups),
        }
    )
    if elapsed_ms is not None:
        payload['elapsed_ms'] = elapsed_ms
    if resolver_status:
        payload['resolver_status'] = resolver_status
    if clarification_sources is not None:
        payload['clarification_sources'] = list(clarification_sources)
    _emit(payload)

def tool_iteration(
    *,
    tool: str,
    status: str,
    step: Optional[str] = None,
    elapsed_ms: Optional[int] = None,
    details: Optional[Dict[str, Any]] = None,
    session_id: Optional[str] = None,
    flow: Optional[str] = None,
    agents_run_id: Optional[str] = None,
    agent_role: Optional[str] = None,
    retry_count: Optional[int] = None,
) -> None:
    payload = _base_payload("tool_iteration", session_id=session_id, flow=flow)
    payload.update(
        {
            "tool": tool,
            "status": status,
            "step": step,
            "elapsed_ms": elapsed_ms,
        }
    )
    if details:
        payload["details"] = details
    if agents_run_id:
        payload["agents_run_id"] = agents_run_id
    if agent_role:
        payload["agent_role"] = agent_role
    if retry_count is not None:
        payload["retry_count"] = retry_count
    _emit(payload)

def tool_parallelism(
    *,
    stage: str,
    session_id: Optional[str] = None,
    flow: Optional[str] = None,
    payload: Optional[Dict[str, Any]] = None,
) -> None:
    record = _base_payload("tool_parallelism", session_id=session_id, flow=flow)
    record["stage"] = stage
    if payload:
        record["payload"] = payload
    _emit(record)


def analysis_chunk(
    *,
    chunk: str,
    step: Optional[str] = None,
    role: Optional[str] = None,
    session_id: Optional[str] = None,
    flow: Optional[str] = None,
    agents_run_id: Optional[str] = None,
) -> None:
    payload = _base_payload("analysis_chunk", session_id=session_id, flow=flow)
    payload.update(
        {
            "step": step,
            "role": role,
            "chars": len(chunk or ""),
        }
    )
    if agents_run_id:
        payload["agents_run_id"] = agents_run_id
    _emit(payload)


def agent_handoff(
    *,
    role: str,
    status: str,
    elapsed_ms: Optional[int] = None,
    handoff: Optional[str] = None,
    retries: Optional[int] = None,
    session_id: Optional[str] = None,
    flow: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
    agents_run_id: Optional[str] = None,
    agent_role: Optional[str] = None,
    retry_count: Optional[int] = None,
) -> None:
    payload = _base_payload('agent_handoff', session_id=session_id, flow=flow)
    payload.update(
        {
            'role': role,
            'status': status,
            'elapsed_ms': elapsed_ms,
            'handoff': handoff,
            'retries': retries,
        }
    )
    if metadata:
        payload['metadata'] = metadata
    if agents_run_id:
        payload['agents_run_id'] = agents_run_id
    if agent_role:
        payload['agent_role'] = agent_role
    if retry_count is not None:
        payload['retry_count'] = retry_count
    _emit(payload)


def agent_tool_gap(
    *,
    lane: str,
    outstanding: int,
    total_calls: int,
    threshold: float,
    session_id: Optional[str] = None,
    flow: Optional[str] = None,
) -> None:
    payload = _base_payload("agent_tool_gap", session_id=session_id, flow=flow)
    payload.update(
        {
            "lane": lane,
            "outstanding": outstanding,
            "total_calls": total_calls,
            "threshold": threshold,
            "outstanding_ratio": outstanding / max(total_calls, 1),
        }
    )
    _emit(payload)


def retry_summary(
    *,
    stage: str,
    attempts: List[Dict[str, Any]],
    final_status: Optional[str] = None,
    session_id: Optional[str] = None,
    flow: Optional[str] = None,
) -> None:
    payload = _base_payload('retry_summary', session_id=session_id, flow=flow)
    payload.update(
        {
            'stage': stage,
            'attempts': attempts,
            'attempt_count': len(attempts),
            'final_status': final_status,
        }
    )
    _emit(payload)


def policy_decision(
    *,
    policy: str,
    score: float,
    threshold: float,
    action: str,
    reason: Optional[str] = None,
    session_id: Optional[str] = None,
    flow: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> None:
    payload = _base_payload('policy_decision', session_id=session_id, flow=flow)
    payload.update(
        {
            'policy': policy,
            'score': score,
            'threshold': threshold,
            'action': action,
        }
    )
    if reason:
        payload['reason'] = reason
    if metadata:
        payload['metadata'] = metadata
    _emit(payload)


def backpressure_event(
    *,
    lane: Optional[str],
    group: Optional[str],
    pending: int,
    running: int,
    limit: Optional[int],
    session_id: Optional[str] = None,
    flow: Optional[str] = None,
    duration_ms: Optional[int] = None,
) -> None:
    payload = _base_payload("backpressure_event", session_id=session_id, flow=flow)
    payload.update(
        {
            "lane": lane,
            "group": group,
            "pending": pending,
            "running": running,
            "limit": limit,
        }
    )
    if duration_ms is not None:
        payload["duration_ms"] = duration_ms
    _emit(payload)


def step_timing(
    *,
    step: str,
    elapsed_ms: Optional[int],
    session_id: Optional[str] = None,
    flow: Optional[str] = None,
) -> None:
    payload = _base_payload("step_timing", session_id=session_id, flow=flow)
    payload.update({"step": step, "elapsed_ms": elapsed_ms})
    _emit(payload)


def revision_plan(
    *,
    targets: Iterable[str],
    run_sql_lane: bool,
    run_chart_lane: bool,
    run_analysis_lane: bool,
    stock_only: bool,
    session_id: Optional[str] = None,
    flow: Optional[str] = None,
    follow_up_route: Optional[str] = None,
    revision_id: Optional[str] = None,
) -> None:
    payload = _base_payload("revision_plan", session_id=session_id, flow=flow)
    payload.update(
        {
            "targets": list(targets or []),
            "run_sql_lane": bool(run_sql_lane),
            "run_chart_lane": bool(run_chart_lane),
            "run_analysis_lane": bool(run_analysis_lane),
            "stock_only": bool(stock_only),
        }
    )
    if follow_up_route:
        payload["follow_up_route"] = follow_up_route
    if revision_id:
        payload["revision_id"] = revision_id
    _emit(payload)


def agent_run(
    *,
    session_id: Optional[str],
    flow: Optional[str],
    run_id: Optional[str],
    trace_id: Optional[str],
    manager_trace_id: Optional[str] = None,
    model: Optional[str],
    tool_attempts: Mapping[str, int],
    retry_counts: Mapping[str, int],
    parallel_groups: Optional[Mapping[str, Any]] = None,
    delegation_policy_version: Optional[str] = None,
    decisions: Optional[Iterable[Mapping[str, Any]]] = None,
) -> None:
    payload = _base_payload("agent_run", session_id=session_id, flow=flow)
    payload.update(
        {
            "run_id": run_id,
            "trace_id": trace_id,
            "manager_trace_id": manager_trace_id,
            "model": model,
            "tool_attempts": dict(tool_attempts or {}),
            "retry_counts": dict(retry_counts or {}),
        }
    )
    if parallel_groups:
        payload["parallel_groups"] = dict(parallel_groups)
    if delegation_policy_version:
        payload["delegation_policy_version"] = delegation_policy_version
    if decisions:
        payload["delegation_decisions"] = [dict(decision) for decision in decisions]
    _emit(payload)


def responses_call(
    *,
    call_type: str,
    model: Optional[str],
    reasoning_effort: Optional[str],
    duration_ms: Optional[int],
    status: str,
    session_id: Optional[str] = None,
    error: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> None:
    payload = _base_payload("responses_call", session_id=session_id)
    payload.update(
        {
            "call_type": call_type,
            "model": model,
            "reasoning_effort": reasoning_effort,
            "duration_ms": duration_ms,
            "status": status,
        }
    )
    if error:
        payload["error"] = error
    if metadata:
        payload["metadata"] = metadata
    _emit(payload)


def gemini_call(
    *,
    operation: str,
    model: Optional[str],
    duration_ms: Optional[int],
    status: str,
    session_id: Optional[str] = None,
    flow: Optional[str] = None,
    error: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> None:
    payload = _base_payload("gemini_call", session_id=session_id, flow=flow)
    payload.update(
        {
            "operation": operation,
            "model": model,
            "duration_ms": duration_ms,
            "status": status,
        }
    )
    if error:
        payload["error"] = error
    if metadata:
        payload["metadata"] = metadata
    _emit(payload)

