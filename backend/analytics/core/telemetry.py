# --- Analytics Function/Class Map ---
# Function: _serialize
#   Role: Handles serialize logic for analytics.core.telemetry.
#   Called from: Internal to analytics.core.telemetry
#   Invokes: json.dumps
#   Why: Keeps analytics.core.telemetry from duplicating serialize behavior across flows.
# Function: _emit
#   Role: Handles emit logic for analytics.core.telemetry.
#   Called from: Internal to analytics.core.telemetry
#   Invokes: analytics.core.telemetry._serialize
#   Why: Keeps analytics.core.telemetry from duplicating emit behavior across flows.
# Function: _base_payload
#   Role: Handles base payload logic for analytics.core.telemetry.
#   Called from: Internal to analytics.core.telemetry
#   Invokes: Internal helpers only
#   Why: Keeps analytics.core.telemetry from duplicating base payload behavior across flows.
# Function: catalog_trace
#   Role: Handles catalog trace logic for analytics.core.telemetry.
#   Called from: analytics.core.events
#   Invokes: analytics.core.telemetry._base_payload, analytics.core.telemetry._emit
#   Why: Keeps analytics.core.telemetry from duplicating catalog trace behavior across flows.
# Function: intent_resolution
#   Role: Handles intent resolution logic for analytics.core.telemetry.
#   Called from: analytics.flows.planner_executor
#   Invokes: analytics.core.telemetry._base_payload, analytics.core.telemetry._emit
#   Why: Keeps analytics.core.telemetry from duplicating intent resolution behavior across flows.
# Function: tool_iteration
#   Role: Handles tool iteration logic for analytics.core.telemetry.
#   Called from: analytics.agent_orchestrator.agent_runtime, analytics.flows.multi_agent, analytics.flows.single_agent_tools
#   Invokes: analytics.core.telemetry._base_payload, analytics.core.telemetry._emit
#   Why: Keeps analytics.core.telemetry from duplicating tool iteration behavior across flows.
# Function: tool_parallelism
#   Role: Handles tool parallelism logic for analytics.core.telemetry.
#   Called from: analytics.flows.planner.analysis_lane, analytics.flows.tooling
#   Invokes: analytics.core.telemetry._base_payload, analytics.core.telemetry._emit
#   Why: Keeps analytics.core.telemetry from duplicating tool parallelism behavior across flows.
# Function: analysis_chunk
#   Role: Handles analysis chunk logic for analytics.core.telemetry.
#   Called from: analytics.flows.multi_agent, analytics.flows.planner_executor
#   Invokes: analytics.core.telemetry._base_payload, analytics.core.telemetry._emit
#   Why: Keeps analytics.core.telemetry from duplicating analysis chunk behavior across flows.
# Function: agent_handoff
#   Role: Handles agent handoff logic for analytics.core.telemetry.
#   Called from: analytics.flows.multi_agent
#   Invokes: analytics.core.telemetry._base_payload, analytics.core.telemetry._emit
#   Why: Keeps analytics.core.telemetry from duplicating agent handoff behavior across flows.
# Function: allowlist_enforcement
#   Role: Emits telemetry when supervisor tool allowlists are computed or pruned.
#   Called from: analytics.flows.multi_agent
#   Invokes: analytics.core.telemetry._base_payload, analytics.core.telemetry._emit
#   Why: Provides observability into allowlist decisions and guardrail pruning.
# Function: supervisor_handoff
#   Role: Emits telemetry when supervisor initiates handoff to a specialist.
#   Called from: analytics.flows.multi_agent
#   Invokes: analytics.core.telemetry._base_payload, analytics.core.telemetry._emit
#   Why: Tracks supervisor → specialist delegation with route and guardrail context.
# Function: agent_tool_gap
#   Role: Handles agent tool gap logic for analytics.core.telemetry.
#   Called from: analytics.flows.instrumentation
#   Invokes: analytics.core.telemetry._base_payload, analytics.core.telemetry._emit
#   Why: Keeps analytics.core.telemetry from duplicating agent tool gap behavior across flows.
# Function: retry_summary
#   Role: Handles retry summary logic for analytics.core.telemetry.
#   Called from: Internal to analytics.core.telemetry
#   Invokes: analytics.core.telemetry._base_payload, analytics.core.telemetry._emit
#   Why: Keeps analytics.core.telemetry from duplicating retry summary behavior across flows.
# Function: policy_decision
#   Role: Handles policy decision logic for analytics.core.telemetry.
#   Called from: analytics.flows.multi_agent
#   Invokes: analytics.core.telemetry._base_payload, analytics.core.telemetry._emit
#   Why: Keeps analytics.core.telemetry from duplicating policy decision behavior across flows.
# Function: backpressure_event
#   Role: Handles backpressure event logic for analytics.core.telemetry.
#   Called from: analytics.flows.multi_agent
#   Invokes: analytics.core.telemetry._base_payload, analytics.core.telemetry._emit
#   Why: Keeps analytics.core.telemetry from duplicating backpressure event behavior across flows.
# Function: step_timing
#   Role: Handles step timing logic for analytics.core.telemetry.
#   Called from: analytics.core.events
#   Invokes: analytics.core.telemetry._base_payload, analytics.core.telemetry._emit
#   Why: Keeps analytics.core.telemetry from duplicating step timing behavior across flows.
# Function: revision_plan
#   Role: Handles revision plan logic for analytics.core.telemetry.
#   Called from: analytics.flows.planner_executor, analytics.flows.single_agent_tools
#   Invokes: analytics.core.telemetry._base_payload, analytics.core.telemetry._emit
#   Why: Keeps analytics.core.telemetry from duplicating revision plan behavior across flows.
# Function: fresh_pipeline_lane
#   Role: Emits telemetry markers for deterministic fresh pipeline lanes.
#   Called from: analytics.flows.planner_executor
#   Invokes: analytics.core.telemetry._base_payload, analytics.core.telemetry._emit
#   Why: Keeps analytics.flows.planner_executor from duplicating fresh lane telemetry wiring across flows.
# Function: agent_run
#   Role: Handles agent run logic for analytics.core.telemetry.
#   Called from: analytics.flows.multi_agent, analytics.flows.single_agent_tools
#   Invokes: analytics.core.telemetry._base_payload, analytics.core.telemetry._emit
#   Why: Keeps analytics.core.telemetry from duplicating agent run behavior across flows.
# Function: responses_call
#   Role: Handles responses call logic for analytics.core.telemetry.
#   Called from: unified_responses_client
#   Invokes: analytics.core.telemetry._base_payload, analytics.core.telemetry._emit
#   Why: Keeps analytics.core.telemetry from duplicating responses call behavior across flows.
# Function: intent_resolution_schema_error
#   Role: Emits telemetry when Responses rejects structured intent schemas.
#   Called from: unified_responses_client
#   Invokes: analytics.core.telemetry._base_payload, analytics.core.telemetry._emit
#   Why: Surfaces schema regressions before they impact users.
# Function: analysis_inputs_missing
#   Role: Emits telemetry when revision prerequisites (sql, dataset preview, market, web) are unavailable.
#   Called from: analytics.flows.workflow, analytics.core.session_state
#   Invokes: analytics.core.telemetry._base_payload, analytics.core.telemetry._emit
#   Why: Alerts operators when manifest invariants block revisions.
# Function: analysis_lane_missing_artifact
#   Role: Emits telemetry when a planner lane finishes without persisting its required artifacts.
#   Called from: analytics.core.session_state
#   Invokes: analytics.core.telemetry._base_payload, analytics.core.telemetry._emit
#   Why: Highlights gaps between lane completion and persisted receipts for operators.
# Function: analysis_inputs_manifest_sealed
#   Role: Emits telemetry when the analysis inputs manifest transitions to a sealed state.
#   Called from: analytics.core.session_state
#   Invokes: analytics.core.telemetry._base_payload, analytics.core.telemetry._emit
#   Why: Provides observability around revision-ready snapshots.
# Function: gemini_call
#   Role: Handles gemini call logic for analytics.core.telemetry.
#   Called from: analytics.services.response_search
#   Invokes: analytics.core.telemetry._base_payload, analytics.core.telemetry._emit
#   Why: Keeps analytics.core.telemetry from duplicating gemini call behavior across flows.
# Function: agent_lane_decision
#   Role: Emits telemetry for the lane chosen by the agent runtime during revisions.
#   Called from: analytics.flows.single_agent_tools, analytics.flows.multi_agent
#   Invokes: analytics.core.telemetry._base_payload, analytics.core.telemetry._emit
#   Why: Audits whether chart vs narrative revisions align with Gemini hints.
# Function: lane_decision_mismatch
#   Role: Emits telemetry when the executed lane diverges from the planned route.
#   Called from: analytics.flows.single_agent_tools, analytics.flows.multi_agent
#   Invokes: analytics.core.telemetry._base_payload, analytics.core.telemetry._emit
#   Why: Flags enforcement gaps so ops can triage agent drift.
# --- End Analytics Function/Class Map ---
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


def allowlist_enforcement(
    *,
    follow_up_route: Optional[str],
    allowed_tools: Iterable[str],
    decisions: Optional[Iterable[Mapping[str, Any]]] = None,
    lane_refresh: Optional[Mapping[str, Any]] = None,
    guardrail: Optional[Mapping[str, Any]] = None,
    session_id: Optional[str] = None,
    flow: Optional[str] = None,
) -> None:
    payload = _base_payload("allowlist_enforcement", session_id=session_id, flow=flow)
    payload.update(
        {
            "follow_up_route": follow_up_route,
            "allowed_tools": sorted({tool for tool in allowed_tools if tool}),
        }
    )
    if decisions:
        payload["decisions"] = [dict(decision) for decision in decisions]
    if lane_refresh:
        payload["lane_refresh"] = dict(lane_refresh)
    if guardrail:
        payload["guardrail"] = dict(guardrail)
    _emit(payload)


def supervisor_handoff(
    *,
    lane: str,
    specialist: Optional[str],
    follow_up_route: Optional[str],
    allowlist: Optional[Iterable[str]],
    guardrail: Optional[Mapping[str, Any]] = None,
    session_id: Optional[str] = None,
    flow: Optional[str] = None,
) -> None:
    payload = _base_payload("supervisor_handoff", session_id=session_id, flow=flow)
    payload.update(
        {
            "lane": lane,
            "specialist": specialist,
            "follow_up_route": follow_up_route,
        }
    )
    if allowlist is not None:
        payload["allowed_tools"] = sorted({tool for tool in allowlist if tool})
    if guardrail:
        payload["guardrail"] = dict(guardrail)
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


def fresh_pipeline_lane(
    *,
    lane: str,
    status: str,
    session_id: Optional[str] = None,
    flow: Optional[str] = None,
    reasoning_effort: Optional[str] = None,
    metadata: Optional[Mapping[str, Any]] = None,
) -> None:
    payload = _base_payload("fresh_pipeline_lane", session_id=session_id, flow=flow)
    payload.update({"lane": lane, "status": status})
    if reasoning_effort:
        payload["reasoning_effort"] = reasoning_effort
    if metadata:
        payload["metadata"] = dict(metadata)
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


def intent_resolution_schema_error(
    *,
    session_id: Optional[str],
    response_model: str,
    error: str,
    metadata: Optional[Dict[str, Any]] = None,
) -> None:
    payload = _base_payload("intent_resolution_schema_error", session_id=session_id)
    payload.update(
        {
            "response_model": response_model,
            "error": error,
        }
    )
    if metadata:
        payload["metadata"] = dict(metadata)
    _emit(payload)


def analysis_inputs_missing(
    *,
    session_id: Optional[str],
    missing_components: Iterable[str],
    lane_readiness: Optional[Mapping[str, Any]] = None,
    route: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> None:
    payload = _base_payload("analysis_inputs_missing", session_id=session_id)
    payload["missing_components"] = [component for component in missing_components or []]
    if lane_readiness is not None:
        payload["lane_readiness"] = dict(lane_readiness)
    if route:
        payload["route"] = route
    if metadata:
        payload["metadata"] = dict(metadata)
    _emit(payload)


def analysis_lane_missing_artifact(
    *,
    session_id: Optional[str],
    lane: str,
    component: str,
    reason: str,
    metadata: Optional[Dict[str, Any]] = None,
) -> None:
    payload = _base_payload("analysis_lane_missing_artifact", session_id=session_id)
    payload.update(
        {
            "lane": lane,
            "component": component,
            "reason": reason,
        }
    )
    if metadata:
        payload["metadata"] = dict(metadata)
    _emit(payload)


def analysis_inputs_manifest_sealed(
    *,
    session_id: Optional[str],
    version: Optional[int],
    ready_components: Iterable[str],
    captured_at: Optional[str] = None,
    receipts: Optional[Mapping[str, Any]] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> None:
    payload = _base_payload("analysis_inputs_manifest_sealed", session_id=session_id)
    payload.update(
        {
            "version": version,
            "ready_components": list(ready_components or []),
        }
    )
    if captured_at:
        payload["sealed_at"] = captured_at
    if receipts:
        payload["receipts"] = dict(receipts)
    if metadata:
        payload["metadata"] = dict(metadata)
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


def agent_lane_decision(
    *,
    lane: str,
    rationale: Optional[str],
    bundle: Optional[Mapping[str, Any]] = None,
    session_id: Optional[str] = None,
    flow: Optional[str] = None,
    source: Optional[str] = None,
) -> None:
    payload = _base_payload("agent_lane_decision", session_id=session_id, flow=flow)
    payload.update(
        {
            "lane": lane,
            "rationale": rationale,
            "source": source,
        }
    )
    if bundle and isinstance(bundle, Mapping):
        payload["bundle"] = {key: value for key, value in bundle.items() if value is not None}
    _emit(payload)


def lane_decision_mismatch(
    *,
    expected_lane: str,
    actual_lane: str,
    session_id: Optional[str],
    flow: Optional[str] = None,
    reason: Optional[str] = None,
) -> None:
    payload = _base_payload("agent_lane_decision_mismatch", session_id=session_id, flow=flow)
    payload.update(
        {
            "expected_lane": expected_lane,
            "actual_lane": actual_lane,
        }
    )
    if reason:
        payload["reason"] = reason
    _emit(payload)
