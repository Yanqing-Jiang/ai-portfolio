# --- Analytics Function/Class Map ---
# Class: AgentMemory
#   Role: Persistence helper that stores agent artifacts inside SessionStateSnapshot.
#   Called from: analytics.agent_orchestrator, analytics.agent_orchestrator.agent_runtime, analytics.flows.single_agent_tools, tests.analytics.test_agent_orchestrator
#   Collaborators: copy.deepcopy
#   Why: Supports downstream analytics workflows that rely on AgentMemory.
# --- End Analytics Function/Class Map ---
from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, Mapping, Optional, List

from analytics.core.session_state import SessionStateSnapshot

from .agent_plan import PlanState, PlanTemplate


class AgentMemory:
    """Persistence helper that stores agent artifacts inside SessionStateSnapshot."""

    _PLAN_STATE_KEY = "plan_state"

    def __init__(self, snapshot: Optional[SessionStateSnapshot]) -> None:
        self._snapshot = snapshot
        if snapshot is None:
            self._agent_cache: Dict[str, Any] = {}
            return
        tool_cache = snapshot.tool_cache
        if not isinstance(tool_cache, dict):
            snapshot.tool_cache = {}
            tool_cache = snapshot.tool_cache
        agent_cache = tool_cache.get("agent")
        if not isinstance(agent_cache, dict):
            agent_cache = {}
            tool_cache["agent"] = agent_cache
        self._agent_cache = agent_cache

    @property
    def snapshot(self) -> Optional[SessionStateSnapshot]:
        return self._snapshot

    @property
    def agent_cache(self) -> Dict[str, Any]:
        return self._agent_cache

    def load_plan_state(self, template: PlanTemplate) -> PlanState:
        """Rehydrate plan state using the stored snapshot when available."""
        persisted = self._agent_cache.get(self._PLAN_STATE_KEY)
        if isinstance(persisted, Mapping):
            return PlanState.from_template(template, previous_state=persisted)
        return PlanState.from_template(template)

    def persist_plan_state(self, state: PlanState) -> None:
        """Persist the latest plan state into the session snapshot."""
        if self._snapshot is None:
            return
        payload = state.to_dict()
        self._agent_cache[self._PLAN_STATE_KEY] = deepcopy(payload)
        self._snapshot.touch()

    def record_tool_receipt(self, tool_name: str, payload: Mapping[str, Any]) -> None:
        """Append tool receipt metadata to the underlying SessionStateSnapshot."""
        if self._snapshot is None:
            return
        self._snapshot.record_tool_receipt(tool_name, dict(payload))
        receipts = self._agent_cache.setdefault("tool_receipts", {})
        sanitized = dict(payload)
        receipts[str(tool_name)] = sanitized
        self._snapshot.touch()

    def get_tool_receipt(self, tool_name: str) -> Optional[Dict[str, Any]]:
        """Fetch the last recorded receipt for a tool if available."""
        receipts = self._agent_cache.get("tool_receipts")
        if not isinstance(receipts, Mapping):
            return None
        payload = receipts.get(str(tool_name))
        if isinstance(payload, Mapping):
            return dict(payload)
        return None

    def record_clarification(self, payload: Mapping[str, Any]) -> None:
        """Persist clarification outcomes for agent reuse."""
        if self._snapshot is None:
            return
        clarifications = self._agent_cache.setdefault("clarifications", [])
        if isinstance(clarifications, list):
            clarifications.append(dict(payload))
        else:  # pragma: no cover - defensive reset
            self._agent_cache["clarifications"] = [dict(payload)]
        self._snapshot.touch()

    def record_agent_run(
        self,
        *,
        run_id: Optional[str],
        trace_id: Optional[str],
        manager_trace_id: Optional[str] = None,
        model: Optional[str],
        tool_attempts: Mapping[str, int],
        retry_counts: Mapping[str, int],
        receipts: Mapping[str, Any],
        parallel_groups: Optional[Mapping[str, Any]] = None,
        delegation_policy_version: Optional[str] = None,
        decisions: Optional[Any] = None,
    ) -> None:
        """Delegate to SessionStateSnapshot.record_agent_run when available."""
        if self._snapshot is None:
            return
        self._snapshot.record_agent_run(
            run_id=run_id,
            trace_id=trace_id,
            manager_trace_id=manager_trace_id,
            model=model,
            tool_attempts=dict(tool_attempts),
            retry_counts=dict(retry_counts),
            receipts=dict(receipts),
            parallel_groups=dict(parallel_groups) if parallel_groups else None,
            delegation_policy_version=delegation_policy_version,
            decisions=list(decisions) if decisions is not None else None,
        )

    def record_revision_questions(self, bundle: Mapping[str, Any]) -> None:
        """Persist the latest revision questions bundle for reuse."""
        payload = dict(bundle)
        self._agent_cache["revision_questions"] = payload
        if self._snapshot is not None:
            try:
                self._snapshot.record_revision_questions(payload)
            except Exception:
                pass

    def get_revision_questions(self) -> Optional[Dict[str, Any]]:
        """Return the cached revision question bundle if available."""
        payload = self._agent_cache.get("revision_questions")
        if isinstance(payload, Mapping):
            return dict(payload)
        return None

    def record_lane_decision(self, payload: Mapping[str, Any]) -> None:
        """Persist the agent-selected lane decision for auditing."""
        entry = dict(payload)
        decisions = self._agent_cache.get("revision_lane_decisions")
        if isinstance(decisions, list):
            decisions.append(entry)
            if len(decisions) > 10:
                del decisions[:-10]
        else:
            self._agent_cache["revision_lane_decisions"] = [entry]
        snapshot = self._snapshot
        if snapshot is not None:
            lane_value = str(entry.get("lane") or "").strip().lower() or "narrative"
            rationale = str(entry.get("rationale") or "").strip() or "agent_lane_decision"
            bundle = entry.get("questions")
            try:
                snapshot.record_revision_lane_decision(
                    lane=lane_value,
                    rationale=rationale,
                    bundle=bundle,
                    decision_source=entry.get("source"),
                )
            except Exception:
                pass

    def get_lane_decision(self) -> Optional[Dict[str, Any]]:
        """Return the last recorded lane decision if present."""
        decisions = self._agent_cache.get("revision_lane_decisions")
        if isinstance(decisions, list) and decisions:
            return dict(decisions[-1])
        return None

    def to_dict(self) -> Dict[str, Any]:
        """Expose a copy of the agent cache for diagnostics or testing."""
        return deepcopy(self._agent_cache)
