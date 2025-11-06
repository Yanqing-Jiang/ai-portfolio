from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import uuid
from typing import Any, Dict, Iterable, List, Mapping, MutableMapping, Optional, Sequence


class PlanNodeStatus(str, Enum):
    """Lifecycle states tracked for each plan node during an agent run."""

    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    SKIPPED = "skipped"
    CANCELLED = "cancelled"


@dataclass
class PlanNode:
    """
    Runtime representation of a plan step executed by the orchestrator.

    `name` should remain stable across plan template versions so persisted
    snapshots can reconcile prior execution state when resuming revisions.
    """

    name: str
    kind: str
    node_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    status: PlanNodeStatus = PlanNodeStatus.PENDING
    dependencies: Sequence[str] = field(default_factory=tuple)
    metadata: Dict[str, Any] = field(default_factory=dict)
    retries: int = 0
    max_retries: int = 0
    artifacts: Dict[str, Any] = field(default_factory=dict)
    started_at: Optional[str] = None
    finished_at: Optional[str] = None

    def serialize(self) -> Dict[str, Any]:
        """Produce a JSON-friendly representation for session persistence."""
        return {
            "name": self.name,
            "kind": self.kind,
            "node_id": self.node_id,
            "status": self.status.value,
            "dependencies": list(self.dependencies),
            "metadata": self.metadata,
            "retries": self.retries,
            "max_retries": self.max_retries,
            "artifacts": self.artifacts,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
        }

    @classmethod
    def deserialize(cls, payload: Mapping[str, Any]) -> "PlanNode":
        """Rehydrate a PlanNode from persisted state."""
        status_value = payload.get("status", PlanNodeStatus.PENDING.value)
        try:
            status = PlanNodeStatus(status_value)
        except ValueError:
            status = PlanNodeStatus.PENDING
        dependencies = payload.get("dependencies") or []
        if not isinstance(dependencies, (list, tuple)):
            dependencies = []
        return cls(
            name=str(payload.get("name") or payload.get("node") or ""),
            kind=str(payload.get("kind") or "task"),
            node_id=str(payload.get("node_id") or uuid.uuid4().hex),
            status=status,
            dependencies=tuple(str(dep) for dep in dependencies if dep),
            metadata=dict(payload.get("metadata") or {}),
            retries=int(payload.get("retries") or 0),
            max_retries=int(payload.get("max_retries") or 0),
            artifacts=dict(payload.get("artifacts") or {}),
            started_at=payload.get("started_at"),
            finished_at=payload.get("finished_at"),
        )

    def mark_running(self) -> None:
        """Mark node as running, recording a timestamp if not already set."""
        if self.status is PlanNodeStatus.RUNNING:
            return
        self.status = PlanNodeStatus.RUNNING
        if not self.started_at:
            self.started_at = datetime.now(timezone.utc).isoformat()

    def mark_finished(self, status: PlanNodeStatus) -> None:
        """Mark node as finished with the supplied status."""
        if status not in {
            PlanNodeStatus.SUCCEEDED,
            PlanNodeStatus.FAILED,
            PlanNodeStatus.SKIPPED,
            PlanNodeStatus.CANCELLED,
        }:
            raise ValueError(f"Invalid terminal status: {status}")
        self.status = status
        self.finished_at = datetime.now(timezone.utc).isoformat()

    def can_retry(self) -> bool:
        """Return True when the node is eligible for another attempt."""
        if self.max_retries <= 0:
            return False
        return self.retries < self.max_retries

    def increment_retry(self) -> None:
        """Increment retry counters and reset to pending for another attempt."""
        self.retries += 1
        self.status = PlanNodeStatus.PENDING
        self.started_at = None
        self.finished_at = None


@dataclass
class PlanTemplateNode:
    """Static definition of a plan node loaded from configuration."""

    name: str
    kind: str
    depends_on: Sequence[str] = field(default_factory=tuple)
    max_retries: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_config(cls, payload: Mapping[str, Any]) -> "PlanTemplateNode":
        depends_on = payload.get("depends_on") or payload.get("dependencies") or ()
        if not isinstance(depends_on, (list, tuple)):
            depends_on = ()
        return cls(
            name=str(payload.get("name") or payload.get("id") or ""),
            kind=str(payload.get("kind") or payload.get("type") or "task"),
            depends_on=tuple(str(dep) for dep in depends_on if dep),
            max_retries=int(payload.get("max_retries") or payload.get("retries") or 0),
            metadata=dict(payload.get("metadata") or {}),
        )


@dataclass
class PlanTemplate:
    """Collection of plan template nodes with versioned metadata."""

    name: str
    version: str = "v1"
    description: Optional[str] = None
    nodes: Sequence[PlanTemplateNode] = field(default_factory=tuple)

    @classmethod
    def from_config(cls, payload: Mapping[str, Any]) -> "PlanTemplate":
        name = str(payload.get("name") or "default")
        version = str(payload.get("version") or "v1")
        description = payload.get("description")
        nodes_payload = payload.get("nodes") or payload.get("plan") or []
        nodes: List[PlanTemplateNode] = []
        if isinstance(nodes_payload, Mapping):
            # Support dicts keyed by node name.
            nodes_payload = [
                {"name": key, **(value if isinstance(value, Mapping) else {})}
                for key, value in nodes_payload.items()
            ]
        if isinstance(nodes_payload, Iterable):
            for entry in nodes_payload:
                if isinstance(entry, Mapping):
                    node = PlanTemplateNode.from_config(entry)
                    if node.name:
                        nodes.append(node)
        return cls(name=name, version=version, description=description, nodes=tuple(nodes))


class PlanState:
    """Mutable runtime state for agent plans."""

    def __init__(
        self,
        *,
        template: PlanTemplate,
        nodes: MutableMapping[str, PlanNode],
        created_at: Optional[str] = None,
        updated_at: Optional[str] = None,
    ) -> None:
        self.template = template
        self.nodes = nodes
        self.created_at = created_at or datetime.now(timezone.utc).isoformat()
        self.updated_at = updated_at or self.created_at

    @classmethod
    def from_template(
        cls,
        template: PlanTemplate,
        *,
        previous_state: Optional[Mapping[str, Any]] = None,
    ) -> "PlanState":
        """
        Build a PlanState from a PlanTemplate, optionally merging persisted state.

        When previous state is supplied, nodes present in both template and snapshot
        retain their persisted status and metadata. New nodes start in PENDING.
        """
        persisted_nodes: Dict[str, PlanNode] = {}
        if previous_state:
            serialized_nodes = previous_state.get("nodes")
            if isinstance(serialized_nodes, Mapping):
                for name, payload in serialized_nodes.items():
                    if isinstance(payload, Mapping):
                        try:
                            node = PlanNode.deserialize({**payload, "name": name})
                        except Exception:
                            continue
                        persisted_nodes[name] = node
        nodes: Dict[str, PlanNode] = {}
        for node_template in template.nodes:
            existing = persisted_nodes.get(node_template.name)
            if existing:
                # Update template-driven metadata while preserving progress.
                existing.kind = node_template.kind
                existing.dependencies = tuple(node_template.depends_on)
                existing.max_retries = node_template.max_retries
                existing.metadata.update(node_template.metadata)
                nodes[node_template.name] = existing
                continue
            nodes[node_template.name] = PlanNode(
                name=node_template.name,
                kind=node_template.kind,
                dependencies=tuple(node_template.depends_on),
                max_retries=node_template.max_retries,
                metadata=dict(node_template.metadata),
            )
        created_at = None
        updated_at = None
        if previous_state:
            created_at = previous_state.get("created_at")
            updated_at = previous_state.get("updated_at")
        return cls(template=template, nodes=nodes, created_at=created_at, updated_at=updated_at)

    def _touch(self) -> None:
        self.updated_at = datetime.now(timezone.utc).isoformat()

    def ready_nodes(self) -> List[PlanNode]:
        """Return nodes that are pending and have satisfied dependencies."""
        ready: List[PlanNode] = []
        for node in self.nodes.values():
            if node.status is not PlanNodeStatus.PENDING:
                continue
            if all(self.nodes[dep].status is PlanNodeStatus.SUCCEEDED for dep in node.dependencies if dep in self.nodes):
                ready.append(node)
        return ready

    def mark_running(self, name: str) -> PlanNode:
        node = self.nodes[name]
        node.mark_running()
        self._touch()
        return node

    def mark_finished(self, name: str, status: PlanNodeStatus) -> PlanNode:
        node = self.nodes[name]
        node.mark_finished(status)
        self._touch()
        return node

    def record_artifacts(self, name: str, artifacts: Mapping[str, Any]) -> None:
        node = self.nodes[name]
        node.artifacts.update(dict(artifacts))
        self._touch()

    def to_dict(self) -> Dict[str, Any]:
        """Serialize state for persistence."""
        return {
            "template": {
                "name": self.template.name,
                "version": self.template.version,
            },
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "nodes": {name: node.serialize() for name, node in self.nodes.items()},
        }

