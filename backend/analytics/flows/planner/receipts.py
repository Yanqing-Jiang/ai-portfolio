# --- Analytics Function/Class Map ---
# Class: ToolInvocationReceipt
#   Role: Receipt record for tool invocations (status, reuse, guardrails, telemetry).
#   Called from: analytics.flows.planner_executor, analytics.flows.single_agent_tools,
#                analytics.flows.planner.stage_helpers, analytics.flows.receipt_helpers
#   Invokes: analytics.validators.sanitize_for_json
#   Why: Centralizes receipt schema so all modes share consistent TTL/guardrail metadata.
# --- End Analytics Function/Class Map ---
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Mapping, Optional

from analytics.validators import sanitize_for_json


@dataclass
class ToolInvocationReceipt:
    tool: str
    status: str
    attempts: int = 0
    elapsed_ms: Optional[int] = None
    latency_ms: Optional[int] = None
    input_hash: Optional[str] = None
    output_hash: Optional[str] = None
    reused: bool = False
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    source_lane: Optional[str] = None
    reused_at_ms: Optional[int] = None
    arguments_digest: Optional[str] = None
    output_digest: Optional[str] = None
    latency_guardrail: Optional[Dict[str, Any]] = None
    guardrail: Optional[Dict[str, Any]] = None
    schema_version: str = "analytics_tool_schema/2025-11-19"
    from_cache: bool = False
    age_seconds: Optional[float] = None
    ttl_seconds: int = 1800
    specialist_role: Optional[str] = None

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "ToolInvocationReceipt":
        metadata = payload.get("metadata") or {}
        latency_candidate = payload.get("latency_ms") or payload.get("elapsed_ms")
        try:
            latency_ms = int(latency_candidate) if latency_candidate is not None else None
        except (TypeError, ValueError):
            latency_ms = None

        reused_at_candidate = payload.get("reused_at_ms") or payload.get("fast_path_latency_ms")
        try:
            reused_at_ms = int(reused_at_candidate) if reused_at_candidate is not None else None
        except (TypeError, ValueError):
            reused_at_ms = None

        arguments_digest = payload.get("arguments_digest")
        if arguments_digest is not None:
            arguments_digest = str(arguments_digest)
        output_digest = payload.get("output_digest")
        if output_digest is not None:
            output_digest = str(output_digest)

        latency_guardrail = payload.get("latency_guardrail")
        if isinstance(latency_guardrail, Mapping):
            latency_guardrail = sanitize_for_json(latency_guardrail)
        else:
            latency_guardrail = None

        guardrail_payload = payload.get("guardrail")
        if isinstance(guardrail_payload, Mapping):
            guardrail_payload = sanitize_for_json(guardrail_payload)
        else:
            guardrail_payload = None

        schema_version = payload.get("schema_version", "analytics_tool_schema/2025-11-19")
        from_cache = bool(payload.get("from_cache", False))

        age_seconds_raw = payload.get("age_seconds")
        try:
            age_seconds = float(age_seconds_raw) if age_seconds_raw is not None else None
        except (TypeError, ValueError):
            age_seconds = None

        ttl_seconds = int(payload.get("ttl_seconds", 1800))
        specialist_role = payload.get("specialist_role")
        if specialist_role is not None:
            specialist_role = str(specialist_role)

        return cls(
            tool=str(payload.get("tool") or ""),
            status=str(payload.get("status") or "unknown"),
            attempts=int(payload.get("attempts") or payload.get("retry_count") or 0),
            elapsed_ms=payload.get("elapsed_ms"),
            latency_ms=latency_ms,
            input_hash=payload.get("input_hash"),
            output_hash=payload.get("output_hash"),
            reused=bool(payload.get("reused", False)),
            error=payload.get("error"),
            metadata=dict(metadata) if isinstance(metadata, Mapping) else {},
            timestamp=str(payload.get("timestamp") or datetime.utcnow().isoformat()),
            source_lane=payload.get("source_lane") or payload.get("lane"),
            reused_at_ms=reused_at_ms,
            arguments_digest=arguments_digest,
            output_digest=output_digest,
            latency_guardrail=latency_guardrail,
            guardrail=guardrail_payload,
            schema_version=str(schema_version),
            from_cache=from_cache,
            age_seconds=age_seconds,
            ttl_seconds=ttl_seconds,
            specialist_role=specialist_role,
        )

