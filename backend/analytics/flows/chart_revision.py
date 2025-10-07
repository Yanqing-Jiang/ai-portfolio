from __future__ import annotations

import copy
from dataclasses import dataclass
from datetime import datetime
from typing import Any, AsyncGenerator, Dict, List, Optional

from analytics.core.events import EventEmitter
from analytics.core.session_state import (
    SessionStateRepository,
    SessionStateSnapshot,
    get_session_state_repository,
)

ChartPatch = Dict[str, Any]


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
        return cls(
            session_id=session_id,
            snapshot=snapshot,
            last_query=snapshot.last_query,
            last_sql=snapshot.last_sql,
            last_chart_spec=copy.deepcopy(snapshot.last_chart_spec),
            last_analysis=snapshot.last_analysis,
            sql_attempts=copy.deepcopy(attempts),
            analysis_history=copy.deepcopy(analysis_history),
        )

    def require_chart_spec(self) -> Dict[str, Any]:
        if not isinstance(self.last_chart_spec, dict) or not self.last_chart_spec:
            raise MissingChartSpec(self.session_id)
        return copy.deepcopy(self.last_chart_spec)

    def require_analysis(self) -> str:
        if not isinstance(self.last_analysis, str) or not self.last_analysis.strip():
            raise MissingAnalysis(self.session_id)
        return self.last_analysis

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


def _normalize_chart_patch(
    patch: Dict[str, Any],
    *,
    reason: Optional[str] = None,
    source: Optional[str] = None,
) -> Dict[str, Any]:
    """Ensure downstream consumers receive a consistent chart patch payload."""
    if not isinstance(patch, dict):
        raise ValueError("chart patch payload must be a dictionary")
    ops = patch.get("ops")
    if not isinstance(ops, list) or not all(isinstance(op, dict) for op in ops):
        raise ValueError("chart patch requires a list of operation dictionaries")
    normalized: Dict[str, Any] = {"ops": [dict(op) for op in ops]}
    normalized_reason = reason or patch.get("reason")
    if normalized_reason:
        normalized["reason"] = normalized_reason
    normalized_source = source or patch.get("source")
    if normalized_source:
        normalized["source"] = normalized_source
    chart_id = patch.get("chart_id")
    if isinstance(chart_id, str) and chart_id:
        normalized["chart_id"] = chart_id
    return normalized


def _ensure_legend(option: Dict[str, Any]) -> Dict[str, Any]:
    legend = option.get("legend")
    if isinstance(legend, list):
        legend_obj = legend[0] if legend else {}
        option["legend"] = legend_obj or {}
    elif legend is None or not isinstance(legend, dict):
        option["legend"] = {}
    return option["legend"]


def _axis_as_list(axis_value: Any) -> List[Dict[str, Any]]:
    if isinstance(axis_value, list):
        return [dict(ax or {}) for ax in axis_value]
    if isinstance(axis_value, dict):
        return [dict(axis_value)]
    return []


def _apply_chart_patch_to_spec(spec: Dict[str, Any], patch: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(spec, dict):
        return spec
    ops = patch.get("ops")
    if not isinstance(ops, list) or not ops:
        return copy.deepcopy(spec)

    option = copy.deepcopy(spec)

    for op in ops:
        name = op.get("op")
        if name == "set_chart_type":
            value = op.get("value")
            if not isinstance(value, str):
                continue
            value = value.strip()
            if not value:
                continue
            is_area = "area" in value and "bar" not in value
            is_stacked = value in {"stacked_area", "stacked_bar"}
            target_type = (
                "bar"
                if "bar" in value
                else "line"
                if "line" in value or is_area
                else value
            )
            new_series: List[Dict[str, Any]] = []
            for series in option.get("series", []) or []:
                updated = dict(series)
                updated["type"] = target_type
                if is_area:
                    updated["areaStyle"] = {"opacity": 0.2}
                else:
                    updated.pop("areaStyle", None)
                if is_stacked:
                    updated["stack"] = "total"
                else:
                    updated.pop("stack", None)
                new_series.append(updated)
            if new_series:
                option["series"] = new_series
            meta = option.setdefault("meta", {})
            chart_design = meta.setdefault("chartDesign", {})
            chart_design["chart_type"] = value

        elif name == "set_stack":
            stack_enabled = bool(op.get("stack"))
            stack_mode = op.get("mode")
            new_series = []
            for series in option.get("series", []) or []:
                updated = dict(series)
                if stack_enabled:
                    updated["stack"] = "total"
                else:
                    updated.pop("stack", None)
                new_series.append(updated)
            if new_series:
                option["series"] = new_series
            if stack_mode == "percent":
                meta = option.setdefault("meta", {})
                meta["chartValueType"] = "percent"

        elif name == "toggle_series":
            legend = _ensure_legend(option)
            selected = dict(legend.get("selected") or {})
            visible = bool(op.get("visible"))
            for series_name in op.get("names") or []:
                if isinstance(series_name, str):
                    selected[series_name] = visible
            legend["selected"] = selected

        elif name == "set_y_axis_format":
            value_type = op.get("valueType")
            if isinstance(value_type, str) and value_type:
                meta = option.setdefault("meta", {})
                meta["chartValueType"] = value_type

        elif name == "set_x_axis":
            field = op.get("field")
            if isinstance(field, str) and field:
                axes = _axis_as_list(option.get("xAxis"))
                if not axes:
                    axes = [{}]
                updated_axes: List[Dict[str, Any]] = []
                for axis in axes:
                    axis_copy = dict(axis)
                    axis_copy["name"] = field
                    updated_axes.append(axis_copy)
                option["xAxis"] = updated_axes
                meta = option.setdefault("meta", {})
                chart_design = meta.setdefault("chartDesign", {})
                chart_design["x_field"] = field

        elif name == "filter_companies":
            legend = _ensure_legend(option)
            selected = dict(legend.get("selected") or {})
            whitelist = {
                str(ticker).upper()
                for ticker in (op.get("tickers") or [])
                if isinstance(ticker, (str, int, float))
            }
            for series in option.get("series", []) or []:
                series_name = str(series.get("name") or "")
                prefix = series_name.split(" - ", 1)[0].upper()
                selected[series_name] = True if not whitelist else prefix in whitelist
            legend["selected"] = selected

        elif name == "set_palette":
            palette = op.get("palette")
            if isinstance(palette, list) and palette:
                option["color"] = list(palette)

        elif name == "set_axis_scale":
            axis = op.get("axis") or "y"
            scale = op.get("scale")
            axis_type = "log" if scale == "log" else "value"

            def _normalize_axis(axis_value: Dict[str, Any]) -> Dict[str, Any]:
                updated = dict(axis_value or {})
                updated["type"] = axis_type
                return updated

            if axis == "x":
                axes = _axis_as_list(option.get("xAxis"))
                option["xAxis"] = [_normalize_axis(ax) for ax in axes] or [{"type": axis_type}]
            else:
                axes = _axis_as_list(option.get("yAxis"))
                option["yAxis"] = [_normalize_axis(ax) for ax in axes] or [{"type": axis_type}]

        elif name == "select_metrics":
            legend = _ensure_legend(option)
            selected = dict(legend.get("selected") or {})
            include = op.get("include")
            exclude = op.get("exclude")
            include_all = include == "ALL"
            include_set = {str(item) for item in (include or []) if isinstance(item, str)} if isinstance(include, list) else set()
            exclude_set = {str(item) for item in (exclude or []) if isinstance(item, str)} if isinstance(exclude, list) else set()
            for series in option.get("series", []) or []:
                name_str = str(series.get("name") or "")
                metric = name_str.split(" - ", 1)[1] if " - " in name_str else name_str
                if include_all:
                    selected[name_str] = metric not in exclude_set
                elif include_set:
                    selected[name_str] = metric in include_set and metric not in exclude_set
            legend["selected"] = selected

        elif name == "set_grouping":
            grouping = op.get("grouping")
            if isinstance(grouping, str) and grouping:
                meta = option.setdefault("meta", {})
                meta["groupingType"] = grouping

        else:
            continue

    return option


def _build_analysis_event(
    analysis: str,
    *,
    session_id: str,
    status: str,
    reason: Optional[str] = None,
    source: Optional[str] = None,
    error: Optional[str] = None,
) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "analysis": analysis,
        "status": status,
        "ts": datetime.utcnow().isoformat(),
        "session_id": session_id,
        "analysis_length": len(analysis or ""),
    }
    if reason:
        payload["reason"] = reason
    if source:
        payload["source"] = source
    if error:
        payload["error"] = error
    event = EventEmitter.result("analysis_revision", payload)
    event["event"] = "analysis_revision"
    event_data = event.setdefault("data", {})
    event_data.setdefault("ts", datetime.utcnow().isoformat())
    return event


def _build_patch_event(
    patch: Dict[str, Any],
    *,
    status: str,
    session_id: str,
    error: Optional[str] = None,
) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "ops": patch["ops"],
        "status": status,
        "ts": datetime.utcnow().isoformat(),
        "session_id": session_id,
    }
    if "reason" in patch:
        payload["reason"] = patch["reason"]
    if "source" in patch:
        payload["source"] = patch["source"]
    if "chart_id" in patch:
        payload["chart_id"] = patch["chart_id"]
    if error:
        payload["error"] = error
    event = EventEmitter.result("chart_patch", payload)
    event["event"] = "chart_patch"
    event_data = event.setdefault("data", {})
    event_data.setdefault("ts", datetime.utcnow().isoformat())
    return event

REVISION_KEYWORDS = (
    "revise",
    "revise chart",
    "update",
    "change",
    "modify",
    "tweak",
    "adjust",
)

ANALYSIS_REVISION_KEYWORDS = (
    "analysis",
    "summary",
    "rewrite",
    "revise",
    "update",
)

ANALYSIS_TEXT_MARKERS = (
    "analysis:",
    "analysis ->",
    "summary:",
    "summary ->",
    "rewrite analysis",
    "update analysis to",
    "revise analysis to",
    "replace analysis with",
)

def is_analysis_revision_query(query: Optional[str]) -> bool:
    if not query:
        return False
    normalized = query.strip().lower()
    if "analysis" not in normalized and "summary" not in normalized:
        return False
    return any(marker in normalized for marker in ANALYSIS_REVISION_KEYWORDS)

def infer_analysis_revision_from_query(query: str) -> Optional[str]:
    normalized = query.strip()
    lower = normalized.lower()
    for marker in ANALYSIS_TEXT_MARKERS:
        idx = lower.find(marker)
        if idx != -1:
            start = idx + len(marker)
            candidate = normalized[start:].strip().lstrip(":").strip()
            candidate = candidate.strip('"')
            if candidate:
                return candidate
    if '"' in normalized:
        segments = [segment.strip() for segment in normalized.split('"') if segment.strip()]
        if len(segments) >= 2:
            return segments[-1]
    return None

CHART_TYPE_SYNONYMS: Dict[str, List[str]] = {
    "bar": ["bar chart", "bar", "column chart"],
    "line": ["line chart", "line", "sparkline"],
    "area": ["area chart", "area"],
    "stacked_bar": ["stacked bar", "stacked column"],
    "stacked_area": ["stacked area"],
}


def is_chart_revision_query(query: Optional[str]) -> bool:
    if not query:
        return False
    normalized = query.strip().lower()
    if "chart" not in normalized:
        return False
    return any(keyword in normalized for keyword in REVISION_KEYWORDS)


def infer_chart_patch_from_query(query: str) -> Optional[Dict[str, Any]]:
    normalized = query.lower()
    ops: List[Dict[str, Any]] = []

    def _match_type(chart_type: str) -> bool:
        synonyms = CHART_TYPE_SYNONYMS.get(chart_type, [])
        return any(phrase in normalized for phrase in synonyms)

    if _match_type("stacked_bar"):
        ops.append({"op": "set_chart_type", "value": "stacked_bar"})
    elif _match_type("stacked_area"):
        ops.append({"op": "set_chart_type", "value": "stacked_area"})
    elif _match_type("bar"):
        ops.append({"op": "set_chart_type", "value": "bar"})
    elif _match_type("area"):
        ops.append({"op": "set_chart_type", "value": "area"})
    elif _match_type("line"):
        ops.append({"op": "set_chart_type", "value": "line"})

    if "stack" in normalized:
        mode = "percent" if any(token in normalized for token in ("percent", "percentage", "100%")) else "normal"
        ops.append({"op": "set_stack", "stack": True, "mode": mode})

    if "percent" in normalized and not any(op.get("op") == "set_y_axis_format" for op in ops):
        ops.append({"op": "set_y_axis_format", "valueType": "percent"})

    if not ops:
        return None

    return {"ops": ops}



async def emit_chart_patch(
    *,
    session_id: str,
    patch: Dict[str, Any],
    reason: Optional[str] = None,
    source: Optional[str] = None,
    repository: Optional[SessionStateRepository] = None,
) -> AsyncGenerator[Dict[str, Any], None]:
    """Apply a chart patch and emit progress + patch events."""
    normalized = _normalize_chart_patch(patch, reason=reason, source=source)
    repo = repository or get_session_state_repository()

    progress = EventEmitter.progress("chart_revision", "Applying chart revision patch...")
    progress["data"]["ts"] = datetime.utcnow().isoformat()
    yield progress

    try:
        revision = await RevisionContext.load(session_id, repository=repo)
        base_spec = revision.require_chart_spec()
    except MissingRevisionSnapshot as exc:
        error_event = EventEmitter.error(
            "chart_revision",
            str(exc),
            details={"session_id": session_id},
            code="CHART_REVISION_MISSING_SESSION",
        )
        error_event["data"]["ts"] = datetime.utcnow().isoformat()
        yield error_event
        yield _build_patch_event(
            normalized,
            status="skipped",
            session_id=session_id,
            error="missing_session",
        )
        return
    except MissingChartSpec as exc:
        error_event = EventEmitter.error(
            "chart_revision",
            str(exc),
            details={"session_id": session_id},
            code="CHART_REVISION_MISSING_SPEC",
        )
        error_event["data"]["ts"] = datetime.utcnow().isoformat()
        yield error_event
        yield _build_patch_event(
            normalized,
            status="skipped",
            session_id=session_id,
            error="missing_chart_spec",
        )
        return

    next_spec = _apply_chart_patch_to_spec(base_spec, normalized)
    revision.record_chart_spec(next_spec, patch=normalized)
    await revision.persist(repository=repo)

    yield _build_patch_event(
        normalized,
        status="applied",
        session_id=session_id,
    )


async def emit_analysis_revision(
    *,
    session_id: str,
    analysis: str,
    reason: Optional[str] = None,
    source: Optional[str] = None,
    repository: Optional[SessionStateRepository] = None,
) -> AsyncGenerator[Dict[str, Any], None]:
    progress = EventEmitter.progress("analysis_revision", "Applying analysis revision...")
    progress["data"]["ts"] = datetime.utcnow().isoformat()
    yield progress

    repo = repository or get_session_state_repository()
    try:
        revision = await RevisionContext.load(session_id, repository=repo)
        base_analysis = revision.require_analysis()
    except MissingRevisionSnapshot as exc:
        error_event = EventEmitter.error(
            "analysis_revision",
            str(exc),
            details={"session_id": session_id},
            code="ANALYSIS_REVISION_MISSING_SESSION",
        )
        error_event["data"]["ts"] = datetime.utcnow().isoformat()
        yield error_event
        yield _build_analysis_event(
            analysis,
            session_id=session_id,
            status="skipped",
            reason=reason,
            source=source,
            error="missing_session",
        )
        return
    except MissingAnalysis as exc:
        error_event = EventEmitter.error(
            "analysis_revision",
            str(exc),
            details={"session_id": session_id},
            code="ANALYSIS_REVISION_MISSING_ANALYSIS",
        )
        error_event["data"]["ts"] = datetime.utcnow().isoformat()
        yield error_event
        yield _build_analysis_event(
            analysis,
            session_id=session_id,
            status="skipped",
            reason=reason,
            source=source,
            error="missing_analysis",
        )
        return

    updated_analysis = analysis.strip() or base_analysis
    revision.record_analysis(updated_analysis, reason=reason)
    await revision.persist(repository=repo)

    yield _build_analysis_event(
        updated_analysis,
        session_id=session_id,
        status="applied",
        reason=reason,
        source=source,
    )

__all__ = [
    "ChartPatch",
    "RevisionContext",
    "emit_chart_patch",
    "emit_analysis_revision",
    "_normalize_chart_patch",
    "_apply_chart_patch_to_spec",
    "is_chart_revision_query",
    "infer_chart_patch_from_query",
    "is_analysis_revision_query",
    "infer_analysis_revision_from_query",
]






