# --- Analytics Function/Class Map ---
# Class: RevisionContext
#   Role: Hydrates and persists chart/analysis revision state from SessionStateSnapshot.
#   Called from: analytics.core.charting.revision_emitters, analytics.flows.chart_revision facade
#   Invokes: analytics.core.session_state.get_session_state_repository, SessionStateSnapshot methods
#   Why: Centralizes revision snapshot access so chart/analysis revisions share a single context.
# Classes: RevisionContextError, MissingRevisionSnapshot, MissingChartSpec, MissingAnalysis
#   Role: Typed errors for revision workflows; surfaced to flow facade and emitters.
# --- End Analytics Function/Class Map ---
from __future__ import annotations

import copy
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, List, Optional, Dict

from analytics.core.session_state import (
    SessionStateRepository,
    SessionStateSnapshot,
    get_session_state_repository,
)


class RevisionContextError(Exception):
    """Base error for revision workflow failures."""


class MissingRevisionSnapshot(RevisionContextError):
    def __init__(self, session_id: str) -> None:
        super().__init__(f"No revision snapshot available for session '{session_id}'")
        self.session_id = session_id


class MissingChartSpec(RevisionContextError):
    def __init__(self, session_id: str) -> None:
        super().__init__(f"No prior chart specification stored for session '{session_id}'")
        self.session_id = session_id


class MissingAnalysis(RevisionContextError):
    def __init__(self, session_id: str) -> None:
        super().__init__(f"No prior analysis stored for session '{session_id}'")
        self.session_id = session_id


ChartPatch = Dict[str, Any]


@dataclass
class RevisionContext:
    session_id: str
    snapshot: SessionStateSnapshot
    last_query: Optional[str]
    last_sql: Optional[str]
    last_chart_spec: Optional[Dict[str, Any]]
    last_analysis: Optional[str]
    sql_attempts: List[Dict[str, Any]]
    analysis_history: List[Dict[str, Any]]
    dataset_preview: List[Dict[str, Any]] = field(default_factory=list)
    analysis_inputs_manifest: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    async def load(
        cls,
        session_id: str,
        *,
        repository: Optional[SessionStateRepository] = None,
    ) -> "RevisionContext":
        repo = repository or get_session_state_repository()
        snapshot = await repo.load(session_id)
        if snapshot is None:
            raise MissingRevisionSnapshot(session_id)
        tool_cache = snapshot.tool_cache if isinstance(snapshot.tool_cache, dict) else {}
        attempts = tool_cache.get("planner_sql_attempts", [])
        if not isinstance(attempts, list):
            attempts = []
        analysis_history = tool_cache.get("analysis_revision_history", [])
        if not isinstance(analysis_history, list):
            analysis_history = []
        dataset_preview_payload = tool_cache.get("planner_dataset_preview", {})
        preview_rows: List[Dict[str, Any]] = []
        if isinstance(dataset_preview_payload, dict):
            rows = dataset_preview_payload.get("rows")
            if isinstance(rows, list):
                preview_rows = [row for row in rows if isinstance(row, dict)]
        return cls(
            session_id=session_id,
            snapshot=snapshot,
            last_query=snapshot.last_query,
            last_sql=snapshot.last_sql,
            last_chart_spec=copy.deepcopy(snapshot.last_chart_spec),
            last_analysis=snapshot.last_analysis,
            sql_attempts=copy.deepcopy(attempts),
            analysis_history=copy.deepcopy(analysis_history),
            dataset_preview=preview_rows,
            analysis_inputs_manifest=copy.deepcopy(snapshot.analysis_inputs_manifest)
            if isinstance(snapshot.analysis_inputs_manifest, dict)
            else {},
        )

    def require_chart_spec(self) -> Dict[str, Any]:
        if not isinstance(self.last_chart_spec, dict) or not self.last_chart_spec:
            raise MissingChartSpec(self.session_id)
        return copy.deepcopy(self.last_chart_spec)

    def require_analysis(self) -> str:
        if not isinstance(self.last_analysis, str) or not self.last_analysis.strip():
            raise MissingAnalysis(self.session_id)
        return self.last_analysis

    def has_analysis_text(self) -> bool:
        return isinstance(self.last_analysis, str) and bool(self.last_analysis.strip())

    def analysis_inputs_ready(self) -> bool:
        manifest = self.analysis_inputs_manifest if isinstance(self.analysis_inputs_manifest, dict) else {}
        if manifest.get("status") == "sealed":
            return True
        return bool(manifest.get("complete"))

    def analysis_inputs_missing(self) -> List[str]:
        manifest = self.analysis_inputs_manifest if isinstance(self.analysis_inputs_manifest, dict) else {}
        blocking = manifest.get("blocking_components")
        if isinstance(blocking, list) and blocking:
            return [str(component) for component in blocking if component]
        missing = manifest.get("missing_components")
        if isinstance(missing, list):
            return [str(component) for component in missing if component]
        return []

    def record_chart_spec(self, updated_spec: Dict[str, Any], *, patch: Dict[str, Any]) -> None:
        self.snapshot.record_outputs(chart_spec=updated_spec)
        history_bucket = self.snapshot.tool_cache.setdefault("chart_revision_history", [])
        if isinstance(history_bucket, list):
            history_bucket.append(
                {
                    "patch": copy.deepcopy(patch),
                    "ts": datetime.utcnow().isoformat(),
                }
            )
        self.last_chart_spec = copy.deepcopy(updated_spec)

    def record_analysis(self, updated_analysis: str, *, reason: Optional[str] = None) -> None:
        self.snapshot.record_outputs(analysis=updated_analysis)
        history_bucket = self.snapshot.tool_cache.setdefault("analysis_revision_history", [])
        if isinstance(history_bucket, list):
            history_bucket.append({
                "analysis": updated_analysis,
                "reason": reason,
                "ts": datetime.utcnow().isoformat(),
            })
        self.last_analysis = updated_analysis

    async def persist(self, *, repository: Optional[SessionStateRepository] = None) -> None:
        repo = repository or get_session_state_repository()
        await repo.save(self.snapshot)

