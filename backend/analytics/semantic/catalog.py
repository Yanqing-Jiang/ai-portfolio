from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Dict, List, Optional

from ..core.context import get_configs


@dataclass(frozen=True)
class TimeGrainSpec:
    name: str
    group_by: List[str]
    filter: Optional[str] = None


@dataclass(frozen=True)
class MetricSpec:
    key: str
    source: str
    is_derived: bool
    dependencies: List[str]
    default_granularity: str
    allowed_granularities: List[str]
    comparisons: List[str]
    dimensions: List[str]


@dataclass(frozen=True)
class IntentSpec:
    key: str
    metrics: List[str]
    derived_metrics: List[str]
    comparison: Optional[str]
    default_granularity: str
    allowed_granularities: List[str]
    default_years_back: Optional[int]
    default_limit: Optional[int]
    group_by: List[str]
    filters: Dict[str, Any]
    description: Optional[str] = None


class SemanticCatalog:
    """In-memory view over metrics.yaml semantic section."""

    def __init__(self, configs: Any) -> None:
        if isinstance(configs, dict):
            metrics_cfg = configs.get("metrics", {})
        else:
            metrics_cfg = getattr(configs, "metrics", {})

        if isinstance(metrics_cfg, dict):
            semantic_cfg = metrics_cfg.get("semantic", {})
        else:
            semantic_cfg = getattr(metrics_cfg, "semantic", {})

        semantic_cfg = semantic_cfg or {}

        self._raw = semantic_cfg
        self._tables = semantic_cfg.get("tables", {}) if isinstance(semantic_cfg, dict) else {}
        self._query_defaults = semantic_cfg.get("query_defaults", {}) if isinstance(semantic_cfg, dict) else {}
        self._defaults = semantic_cfg.get("defaults", {}) if isinstance(semantic_cfg, dict) else {}
        self._time_grains = semantic_cfg.get("time_grains", {}) if isinstance(semantic_cfg, dict) else {}
        self._dimensions = semantic_cfg.get("dimensions", {}) if isinstance(semantic_cfg, dict) else {}
        self._metric_specs = semantic_cfg.get("metrics", {}) if isinstance(semantic_cfg, dict) else {}
        self._derived_specs = semantic_cfg.get("derived_metrics", {}) if isinstance(semantic_cfg, dict) else {}
        self._intent_specs = semantic_cfg.get("intents", {}) if isinstance(semantic_cfg, dict) else {}

    # ---------- Storage helpers ----------
    def tables(self) -> Dict[str, Any]:
        return self._tables

    def query_defaults(self) -> Dict[str, Any]:
        return self._query_defaults

    def default_years_back(self) -> Optional[int]:
        defaults = self._defaults or {}
        if isinstance(defaults, dict):
            return defaults.get("years_back")
        return None

    def default_granularity(self) -> str:
        defaults = self._defaults or {}
        granularity = defaults.get("granularity") if isinstance(defaults, dict) else None
        return granularity or "annual"

    def default_limit(self) -> Optional[int]:
        defaults = self._defaults or {}
        return defaults.get("limit") if isinstance(defaults, dict) else None

    # ---------- Time grain helpers ----------
    def get_time_grain(self, key: str) -> TimeGrainSpec:
        spec = self._time_grains.get(key, {}) if isinstance(self._time_grains, dict) else {}
        group_by = spec.get("group_by") if isinstance(spec, dict) else None
        if not isinstance(group_by, list):
            group_by = ["calendar_year"] if key == "annual" else ["calendar_year", "calendar_quarter_num", "calendar_quarter"]
        filter_clause = spec.get("filter") if isinstance(spec, dict) else None
        label = spec.get("label") if isinstance(spec, dict) else key
        return TimeGrainSpec(name=label or key, group_by=group_by, filter=filter_clause)

    def resolve_granularity(self, requested: Optional[str], allowed: List[str], default_key: str) -> str:
        candidate = (requested or "").lower().strip() if isinstance(requested, str) else None
        allowed_normalised = [g.lower() for g in (allowed or [])]
        if candidate and candidate in allowed_normalised:
            return candidate
        if candidate and "quarter" in candidate and "quarterly" in allowed_normalised:
            return "quarterly"
        if candidate and "annual" in candidate and "annual" in allowed_normalised:
            return "annual"
        if default_key in allowed_normalised:
            return default_key
        return allowed_normalised[0] if allowed_normalised else default_key

    # ---------- Metric helpers ----------
    def get_metric(self, key: str) -> Optional[MetricSpec]:
        clean_key = key.lower() if isinstance(key, str) else key
        raw = self._metric_specs.get(clean_key, {}) if isinstance(self._metric_specs, dict) else {}
        if raw:
            return MetricSpec(
                key=clean_key,
                source=raw.get("source", key),
                is_derived=False,
                dependencies=[],
                default_granularity=raw.get("default_granularity", "annual"),
                allowed_granularities=list(raw.get("allowed_granularities", ["annual"])),
                comparisons=list(raw.get("comparisons", [])),
                dimensions=list(raw.get("dimensions", [])),
            )
        derived_raw = self._derived_specs.get(clean_key, {}) if isinstance(self._derived_specs, dict) else {}
        if derived_raw:
            return MetricSpec(
                key=clean_key,
                source=derived_raw.get("source", key),
                is_derived=True,
                dependencies=list(derived_raw.get("dependencies", [])),
                default_granularity=derived_raw.get("default_granularity", "annual"),
                allowed_granularities=list(derived_raw.get("allowed_granularities", ["annual"])),
                comparisons=list(derived_raw.get("comparisons", [])),
                dimensions=list(derived_raw.get("dimensions", [])),
            )
        return None

    def list_metric_specs(self, keys: List[str]) -> List[MetricSpec]:
        result: List[MetricSpec] = []
        for key in keys or []:
            spec = self.get_metric(key)
            if spec:
                result.append(spec)
        return result

    # ---------- Intent helpers ----------
    def get_intent_spec(self, intent_key: Optional[str]) -> Optional[IntentSpec]:
        if not intent_key:
            return None
        raw = self._intent_specs.get(intent_key, {}) if isinstance(self._intent_specs, dict) else {}
        if not raw:
            return None
        metrics = list(raw.get("metrics", []))
        derived = list(raw.get("derived_metrics", []))
        comparison = raw.get("comparison")
        default_grain = raw.get("default_granularity", self.default_granularity())
        allowed = list(raw.get("allowed_granularities", [default_grain]))
        default_years = raw.get("default_years_back", self._query_defaults.get("default_years_back"))
        if default_years is None:
            default_years = self.default_years_back()
        default_limit = raw.get("default_limit", self._query_defaults.get("default_limit"))
        group_by = list(raw.get("group_by", []))
        filters = raw.get("filters", {}) if isinstance(raw.get("filters"), dict) else {}
        description = raw.get("label")
        return IntentSpec(
            key=intent_key,
            metrics=metrics,
            derived_metrics=derived,
            comparison=comparison,
            default_granularity=default_grain,
            allowed_granularities=allowed,
            default_years_back=default_years,
            default_limit=default_limit,
            group_by=group_by,
            filters=filters,
            description=description,
        )

    # ---------- Convenience ----------
    def allowed_tables(self) -> List[str]:
        if isinstance(self._tables, dict):
            return list(self._tables.keys())
        return []


@lru_cache(maxsize=1)
def get_semantic_catalog() -> SemanticCatalog:
    configs = get_configs()
    return SemanticCatalog(configs)
