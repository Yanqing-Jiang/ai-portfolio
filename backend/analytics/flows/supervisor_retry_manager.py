# --- Analytics Function/Class Map ---
# Class: SupervisorRetryManager
#   Role: Applies delegation policy guardrails to supervisor retries and records audit payloads for downstream telemetry / SSE consumers.
#   Called from: analytics.flows.multi_agent
#   Collaborators: collections.defaultdict, analytics.policies.delegation_policy.DelegationDecision, datetime.timedelta
#   Why: Supports downstream analytics workflows that rely on SupervisorRetryManager.
# --- End Analytics Function/Class Map ---
from __future__ import annotations

from collections import defaultdict, deque
from datetime import datetime, timedelta
from typing import Any, Deque, Dict, Iterable, Mapping, Optional, Tuple

from analytics.policies.delegation_policy import DelegationDecision, DelegationPolicy

RetryCallbackResponse = Tuple[bool, Optional[Dict[str, Any]]]


class SupervisorRetryManager:
    """
    Applies delegation policy guardrails to supervisor retries and records audit
    payloads for downstream telemetry / SSE consumers.
    """

    def __init__(
        self,
        policy: DelegationPolicy,
        *,
        task_roles: Mapping[str, str],
        role_lanes: Mapping[str, str],
    ) -> None:
        self._policy = policy
        self._task_roles = dict(task_roles)
        self._role_lanes = dict(role_lanes)
        self._window_history: Dict[str, Deque[datetime]] = defaultdict(deque)
        self._daily_history: Dict[str, Deque[datetime]] = defaultdict(deque)
        self._decisions: list[Dict[str, Any]] = []

    def reset(self) -> None:
        """Clear cached decisions between supervisor runs."""
        self._decisions.clear()

    def decisions(self) -> Iterable[Dict[str, Any]]:
        return tuple(self._decisions)

    def should_retry(
        self,
        task_name: str,
        spec: Any,
        attempts: int,
        context: Any,
        retry_entry: Mapping[str, Any],
    ) -> RetryCallbackResponse:
        lane = self._lane_for_task(task_name)
        if not lane:
            return True, None

        lane_policy = self._policy.lane_policy(lane)
        if not lane_policy:
            return True, None

        now = datetime.utcnow()
        window_queue = self._window_history[lane]
        day_queue = self._daily_history[lane]

        if lane_policy.window_minutes:
            cutoff = now - timedelta(minutes=lane_policy.window_minutes)
            while window_queue and window_queue[0] < cutoff:
                window_queue.popleft()
        if lane_policy.max_attempts_per_day is not None:
            day_cutoff = now - timedelta(hours=24)
            while day_queue and day_queue[0] < day_cutoff:
                day_queue.popleft()

        projected_window_used = len(window_queue) + 1
        projected_day_used = len(day_queue) + 1

        metadata: Dict[str, Any] = {
            "attempt": attempts,
            "window": {
                "limit": lane_policy.max_attempts_per_window,
                "used": projected_window_used,
                "minutes": lane_policy.window_minutes,
            },
        }
        if lane_policy.max_attempts_per_day is not None:
            metadata["daily"] = {
                "limit": lane_policy.max_attempts_per_day,
                "used": projected_day_used,
            }

        allowed = True
        reason = "allow"

        if attempts > lane_policy.max_attempts_per_run:
            allowed = False
            reason = "per_run_limit_exceeded"
        elif (
            lane_policy.max_attempts_per_window is not None
            and projected_window_used > lane_policy.max_attempts_per_window
        ):
            allowed = False
            reason = "window_limit_exceeded"
        elif (
            lane_policy.max_attempts_per_day is not None
            and projected_day_used > lane_policy.max_attempts_per_day
        ):
            allowed = False
            reason = "daily_limit_exceeded"

        entry_metadata = {}
        if isinstance(retry_entry, Mapping):
            raw_meta = retry_entry.get("metadata")
            if isinstance(raw_meta, Mapping):
                entry_metadata = dict(raw_meta)

        raw_tags = entry_metadata.get("tags") or entry_metadata.get("compliance_tags")
        tags: set[str] = set()
        if raw_tags:
            if isinstance(raw_tags, str):
                tags = {raw_tags}
            else:
                try:
                    tags = {str(tag) for tag in raw_tags if tag is not None}
                except TypeError:
                    tags = {str(raw_tags)}

        context_obj = DelegationContext(
            lane=lane,
            cost=entry_metadata.get("cost") or entry_metadata.get("estimated_cost"),
            spent_today=entry_metadata.get("spent_today"),
            region=entry_metadata.get("region"),
            tags=tags,
            metadata={
                "task": task_name,
                "agent": getattr(spec, "name", None),
                **entry_metadata,
            },
        )

        policy_decision = self._policy.should_delegate(context_obj)
        merged_metadata: Dict[str, Any] = dict(policy_decision.metadata or {})
        merged_metadata.setdefault("attempt", attempts)
        merged_metadata.setdefault("window", metadata["window"])
        if "daily" in metadata:
            merged_metadata.setdefault("daily", metadata["daily"])

        decision = DelegationDecision(
            allowed=allowed and policy_decision.allowed,
            reason=policy_decision.reason if policy_decision.reason != "allow" else reason,
            metadata=merged_metadata,
        )

        window_queue.append(now)
        day_queue.append(now)
        audit_payload = self._policy.audit_payload(lane, decision)
        if retry_entry:
            audit_payload.setdefault("error", retry_entry.get("error"))
            audit_payload.setdefault("error_code", retry_entry.get("error_code"))
        self._decisions.append(audit_payload)

        if allowed:
            return True, None
        return False, audit_payload

    def _lane_for_task(self, task_name: str) -> Optional[str]:
        role = self._task_roles.get(task_name)
        if not role:
            return None
        lane = self._role_lanes.get(role)
        if not lane:
            return None
        return lane
