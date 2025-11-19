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
from analytics.validators import sanitize_for_json

from .agent_plan import PlanState, PlanTemplate


class AgentMemory:
    """Persistence helper that stores agent artifacts inside SessionStateSnapshot."""

    _PLAN_STATE_KEY = "plan_state"

    def __init__(self, snapshot: Optional[SessionStateSnapshot]) -> None:
        self._snapshot = snapshot
        self._plan_state: Dict[str, Any] = {}
        self._tool_receipts: Dict[str, Any] = {}
        self._clarifications: List[Dict[str, Any]] = []
        self._guardrails: Dict[str, Any] = {}
        self._revision_questions: Optional[Dict[str, Any]] = None
        self._lane_decisions: List[Dict[str, Any]] = []
        if snapshot is None:
            return
        if isinstance(snapshot.agents_plan_state, Mapping):
            self._plan_state = dict(snapshot.agents_plan_state)
        if isinstance(snapshot.agents_tool_receipts, Mapping):
            self._tool_receipts = dict(snapshot.agents_tool_receipts)
        if isinstance(snapshot.agents_clarifications, list):
            self._clarifications = list(snapshot.agents_clarifications)
        if isinstance(snapshot.agents_guardrails, Mapping):
            self._guardrails = dict(snapshot.agents_guardrails)
        store = snapshot.agents_revision_question_store
        if isinstance(store, Mapping):
            latest = store.get("latest")
            if isinstance(latest, Mapping):
                bundle = latest.get("bundle")
                if isinstance(bundle, Mapping):
                    self._revision_questions = dict(bundle)
        if isinstance(snapshot.agent_lane_decisions, list):
            self._lane_decisions = list(snapshot.agent_lane_decisions)

    @property
    def snapshot(self) -> Optional[SessionStateSnapshot]:
        return self._snapshot

    def load_plan_state(self, template: PlanTemplate) -> PlanState:
        """Rehydrate plan state using the stored snapshot when available."""
        persisted = self._plan_state
        if isinstance(persisted, Mapping) and persisted:
            return PlanState.from_template(template, previous_state=persisted)
        return PlanState.from_template(template)

    def persist_plan_state(self, state: PlanState) -> None:
        """Persist the latest plan state into the session snapshot."""
        if self._snapshot is None:
            return
        payload = state.to_dict()
        self._plan_state = deepcopy(payload)
        self._snapshot.agents_plan_state = deepcopy(payload)
        self._snapshot.touch()

    def record_tool_receipt(self, tool_name: str, payload: Mapping[str, Any]) -> None:
        """Append tool receipt metadata to the underlying SessionStateSnapshot."""
        if self._snapshot is None:
            return
        self._snapshot.record_tool_receipt(tool_name, dict(payload))
        receipts = dict(self._tool_receipts)
        sanitized = dict(payload)
        receipts[str(tool_name)] = sanitized
        self._tool_receipts = receipts
        self._snapshot.touch()

    def get_tool_receipt(self, tool_name: str) -> Optional[Dict[str, Any]]:
        """Fetch the last recorded receipt for a tool if available."""
        receipts = self._tool_receipts
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
        clarifications = list(self._clarifications)
        clarifications.append(dict(payload))
        self._clarifications = clarifications
        self._snapshot.agents_clarifications = list(clarifications)
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
        self._revision_questions = payload
        if self._snapshot is not None:
            try:
                self._snapshot.record_revision_questions(payload)
            except Exception:
                pass

    def record_guardrail(self, guardrail_id: str, payload: Mapping[str, Any]) -> None:
        """Persist guardrail verdicts so follow-up routing decisions remain auditable."""
        if not guardrail_id:
            return
        entry = sanitize_for_json(dict(payload))
        guardrail_cache = dict(self._guardrails)
        guardrail_cache[str(guardrail_id)] = entry
        self._guardrails = guardrail_cache
        if self._snapshot is None:
            return
        try:
            self._snapshot.record_agent_guardrail(guardrail_id, entry)
        except Exception:
            pass

    def get_revision_questions(self) -> Optional[Dict[str, Any]]:
        """Return the cached revision question bundle if available."""
        if isinstance(self._revision_questions, Mapping):
            return dict(self._revision_questions)
        return None

    def record_lane_decision(self, payload: Mapping[str, Any]) -> None:
        """Persist the agent-selected lane decision for auditing."""
        entry = dict(payload)
        decisions = list(self._lane_decisions)
        decisions.append(entry)
        if len(decisions) > 10:
            del decisions[:-10]
        self._lane_decisions = decisions
        snapshot = self._snapshot
        if snapshot is not None:
            snapshot.agent_lane_decisions = list(decisions)
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
        if isinstance(self._lane_decisions, list) and self._lane_decisions:
            return dict(self._lane_decisions[-1])
        return None

    def to_dict(self) -> Dict[str, Any]:
        """Expose a copy of the agent cache for diagnostics or testing."""
        return {
            "plan_state": deepcopy(self._plan_state),
            "tool_receipts": deepcopy(self._tool_receipts),
            "clarifications": deepcopy(self._clarifications),
            "guardrails": deepcopy(self._guardrails),
            "revision_questions": deepcopy(self._revision_questions)
            if isinstance(self._revision_questions, Mapping)
            else None,
            "revision_lane_decisions": deepcopy(self._lane_decisions),
        }
