# --- Analytics Function/Class Map ---
# Class: AgentTaskStep
#   Role: Represents a single task decision produced by the planner.
#   Called from: analytics.flows.multi_agent
#   Collaborators: dataclasses.field
#   Why: Supports downstream analytics workflows that rely on AgentTaskStep.
# Class: AgentTaskPlan
#   Role: Collection of task steps emitted by the planner.
#   Called from: analytics.flows.multi_agent
#   Collaborators: dataclasses.field, analytics.flows.task_plan.AgentTaskStep
#   Why: Supports downstream analytics workflows that rely on AgentTaskPlan.
# --- End Analytics Function/Class Map ---
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence


@dataclass
class AgentTaskStep:
    """Represents a single task decision produced by the planner."""

    name: str
    status: str
    reason: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    retry_count: int = 0
    continuable: bool = True

    def to_dict(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {"name": self.name, "status": self.status}
        if self.reason:
            payload["reason"] = self.reason
        if self.metadata:
            payload.update(self.metadata)
        return payload

    def apply_guardrails(
        self,
        *,
        schema: Optional[Mapping[str, Any]] = None,
        allow_retry: bool = True,
    ) -> None:
        """
        Apply simple guardrail validation rules against the step metadata.

        Guardrail schema example::

            {
                "required": ["tickers"],
                "disallow_status": ["skip"],
            }
        """
        if not schema:
            return
        errors: List[str] = []
        required_fields = schema.get("required") if isinstance(schema, Mapping) else None
        disallow_status = schema.get("disallow_status") if isinstance(schema, Mapping) else None
        if isinstance(required_fields, Sequence):
            for field_name in required_fields:
                if field_name is None:
                    continue
                key = str(field_name)
                if key not in self.metadata or self.metadata.get(key) in (None, "", [], {}):
                    errors.append(f"{key}_missing")
        if (
            isinstance(disallow_status, Sequence)
            and self.status in {str(entry).strip().lower() for entry in disallow_status if entry is not None}
        ):
            errors.append(f"status_{self.status}_disallowed")
        if not errors:
            return
        self.retry_count += 1
        self.metadata.setdefault("guardrail_errors", []).extend(errors)  # type: ignore[assignment]
        if allow_retry:
            self.status = "retry"
            self.continuable = True
        else:
            self.status = "skip"
            self.continuable = False
            self.reason = (self.reason or "guardrail_blocked")


@dataclass
class AgentTaskPlan:
    """Collection of task steps emitted by the planner."""

    steps: List[AgentTaskStep] = field(default_factory=list)

    def add_step(
        self,
        name: str,
        status: str,
        *,
        reason: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> AgentTaskStep:
        step = AgentTaskStep(name=name, status=status, reason=reason, metadata=metadata or {})
        self.steps.append(step)
        return step

    def extend(self, entries: Iterable[AgentTaskStep]) -> None:
        for entry in entries:
            self.steps.append(entry)

    def to_dicts(self) -> List[Dict[str, Any]]:
        return [step.to_dict() for step in self.steps]

    def __iter__(self):
        return iter(self.steps)

    @classmethod
    def build_from_context(
        cls,
        steps: Optional[Iterable[Mapping[str, Any]]],
        *,
        guardrails: Optional[Mapping[str, Mapping[str, Any]]] = None,
    ) -> "AgentTaskPlan":
        plan = cls()
        if not steps:
            return plan
        for raw in steps:
            if not isinstance(raw, Mapping):
                continue
            name = str(raw.get("name") or "").strip()
            if not name:
                continue
            status_value = str(raw.get("status") or "skip").strip().lower() or "skip"
            reason = raw.get("reason")
            metadata = {
                key: value
                for key, value in raw.items()
                if key not in {"name", "status", "reason"} and not key.startswith("_")
            }
            step = plan.add_step(name=name, status=status_value, reason=reason, metadata=metadata)
            if guardrails:
                schema = guardrails.get(name)
                if schema:
                    step.apply_guardrails(schema=schema)
        return plan
