from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional


@dataclass
class AgentTaskStep:
    """Represents a single task decision produced by the planner."""

    name: str
    status: str
    reason: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {"name": self.name, "status": self.status}
        if self.reason:
            payload["reason"] = self.reason
        if self.metadata:
            payload.update(self.metadata)
        return payload


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
