from __future__ import annotations

from dataclasses import MISSING, asdict, dataclass, field, fields
from typing import Any, Dict, List, Optional, Sequence, Type, TypeVar


def _clone_dict(source: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not isinstance(source, dict):
        return {}
    return {key: value for key, value in source.items()}


def _clone_list(source: Optional[Sequence[Any]]) -> List[Any]:
    if source is None:
        return []
    return list(source)


T = TypeVar("T", bound="BaseArtifact")


class BaseArtifact:
    """Shared helpers for artifact dataclasses."""

    def to_dict(self) -> Dict[str, Any]:
        payload = asdict(self)
        # Remove None values for cleaner wire payloads
        return {key: value for key, value in payload.items() if value is not None}

    @classmethod
    def from_dict(cls: Type[T], payload: Optional[Dict[str, Any]]) -> T:
        data = payload or {}
        kwargs: Dict[str, Any] = {}
        for field_info in fields(cls):
            if field_info.name in data:
                kwargs[field_info.name] = data[field_info.name]
            elif field_info.default is not MISSING:
                kwargs[field_info.name] = field_info.default
            elif field_info.default_factory is not MISSING:  # type: ignore[attr-defined]
                kwargs[field_info.name] = field_info.default_factory()  # type: ignore[attr-defined]
        return cls(**kwargs)  # type: ignore[arg-type]


@dataclass
class ClassificationArtifact(BaseArtifact):
    query: str
    category: Optional[str] = None
    confidence: Optional[float] = None
    is_financial: Optional[bool] = None
    model: Optional[str] = None
    raw: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ClarificationArtifact(BaseArtifact):
    query: str
    clarifier_action: Optional[str] = None
    clarifier_missing_slots: List[str] = field(default_factory=list)
    clarifier_slot: Optional[str] = None
    pending: List[Dict[str, Any]] = field(default_factory=list)
    assumptions: List[str] = field(default_factory=list)
    resolved: bool = False
    rounds: int = 0
    answered_slots: List[str] = field(default_factory=list)
    history: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class IntentArtifact(BaseArtifact):
    query: str
    intent_key: Optional[str] = None
    confidence: Optional[float] = None
    slots: Dict[str, Any] = field(default_factory=dict)
    clarifications_needed: Optional[bool] = None
    low_confidence: Optional[bool] = None
    raw: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PlanArtifact(BaseArtifact):
    query: str
    plan: Optional[Dict[str, Any]] = None
    candidate_templates: List[Dict[str, Any]] = field(default_factory=list)
    selected_template_id: Optional[str] = None
    comparison: Optional[str] = None
    granularity: Optional[str] = None
    metrics_count: Optional[int] = None
    template: Optional[Dict[str, Any]] = None
    parallelism_enabled: Optional[bool] = None
    criteria: Optional[Dict[str, Any]] = None
    catalog_elapsed_ms: Optional[int] = None


@dataclass
class SQLGenerationArtifact(BaseArtifact):
    query: str
    sql: Optional[str] = None
    llm_used: Optional[bool] = None
    template_id: Optional[str] = None
    attempts: List[Dict[str, Any]] = field(default_factory=list)
    last_error: Optional[str] = None
    last_error_code: Optional[str] = None
    last_error_detail: Optional[str] = None
    status: str = "pending"


@dataclass
class SQLExecutionArtifact(BaseArtifact):
    query: str
    row_count: Optional[int] = None
    columns: List[str] = field(default_factory=list)
    tickers: List[str] = field(default_factory=list)
    metrics: List[str] = field(default_factory=list)
    timeframe: Dict[str, Any] = field(default_factory=dict)
    sample_rows: List[Dict[str, Any]] = field(default_factory=list)
    elapsed_ms: Optional[int] = None
    status: str = "pending"
    error: Optional[str] = None
    error_code: Optional[str] = None


@dataclass
class WebContextArtifact(BaseArtifact):
    query: str
    summary: Optional[str] = None
    snippets: List[Dict[str, Any]] = field(default_factory=list)
    search_id: Optional[str] = None
    from_cache: Optional[bool] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    topic: Optional[str] = None


@dataclass
class ChartArtifact(BaseArtifact):
    query: str
    spec: Optional[Dict[str, Any]] = None
    spec_id: Optional[str] = None
    design: Dict[str, Any] = field(default_factory=dict)
    datasets_summary: List[Dict[str, Any]] = field(default_factory=list)
    series_count: Optional[int] = None
    chart_type: Optional[str] = None
    scope_banner: Optional[str] = None


@dataclass
class AnalysisArtifact(BaseArtifact):
    query: str
    analysis_text: Optional[str] = None
    fragments: List[str] = field(default_factory=list)
    length: Optional[int] = None
    summary: Optional[str] = None
    stock_widget: Optional[Dict[str, Any]] = None
    web_context: Optional[Dict[str, Any]] = None
    tool_bundle: Optional[Dict[str, Any]] = None


@dataclass
class MarketArtifact(BaseArtifact):
    query: str
    tickers: List[str] = field(default_factory=list)
    snapshot: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    error_code: Optional[str] = None


@dataclass
class RevisionArtifact(BaseArtifact):
    query: str
    revision_type: str
    patch: Dict[str, Any] = field(default_factory=dict)
    reason: Optional[str] = None
    source: Optional[str] = None


@dataclass
class PipelineArtifacts(BaseArtifact):
    """Container aggregating all phase artifacts for a run."""

    classification: Optional[ClassificationArtifact] = None
    intent: Optional[IntentArtifact] = None
    clarification: Optional[ClarificationArtifact] = None
    plan: Optional[PlanArtifact] = None
    sql_generation: Optional[SQLGenerationArtifact] = None
    sql_execution: Optional[SQLExecutionArtifact] = None
    chart: Optional[ChartArtifact] = None
    analysis: Optional[AnalysisArtifact] = None
    web: Optional[WebContextArtifact] = None
    market: Optional[MarketArtifact] = None
    revision: Optional[RevisionArtifact] = None

    def to_dict(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {}
        for name, value in self.__dict__.items():
            if value is None:
                continue
            payload[name] = value.to_dict()
        return payload

    @classmethod
    def from_dict(cls, payload: Optional[Dict[str, Any]]) -> "PipelineArtifacts":
        data = payload or {}
        return cls(
            classification=_maybe_from_dict(ClassificationArtifact, data.get("classification")),
            intent=_maybe_from_dict(IntentArtifact, data.get("intent")),
            clarification=_maybe_from_dict(ClarificationArtifact, data.get("clarification")),
            plan=_maybe_from_dict(PlanArtifact, data.get("plan")),
            sql_generation=_maybe_from_dict(SQLGenerationArtifact, data.get("sql_generation")),
            sql_execution=_maybe_from_dict(SQLExecutionArtifact, data.get("sql_execution")),
            chart=_maybe_from_dict(ChartArtifact, data.get("chart")),
            analysis=_maybe_from_dict(AnalysisArtifact, data.get("analysis")),
            web=_maybe_from_dict(WebContextArtifact, data.get("web")),
            market=_maybe_from_dict(MarketArtifact, data.get("market")),
            revision=_maybe_from_dict(RevisionArtifact, data.get("revision")),
        )


def _maybe_from_dict(cls: Type[T], payload: Optional[Dict[str, Any]]) -> Optional[T]:
    if payload is None:
        return None
    return cls.from_dict(payload)


__all__ = [
    "AnalysisArtifact",
    "ChartArtifact",
    "ClassificationArtifact",
    "ClarificationArtifact",
    "IntentArtifact",
    "MarketArtifact",
    "PipelineArtifacts",
    "PlanArtifact",
    "RevisionArtifact",
    "SQLExecutionArtifact",
    "SQLGenerationArtifact",
    "WebContextArtifact",
]
