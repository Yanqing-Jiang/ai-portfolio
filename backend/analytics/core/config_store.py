from __future__ import annotations

import os
from dataclasses import dataclass, field
from enum import Enum
import logging
import time
from typing import Any, Dict, List, Optional

from .cache import get_cache_service
from .context import get_configs

logger = logging.getLogger(__name__)
CONFIGS = get_configs()


class ConfigSource(Enum):
    """Configuration data sources."""

    YAML_CONFIG = "yaml_config"
    EMPTY_FALLBACK = "empty_fallback"


class QueryType(Enum):
    """Supported configuration lookups."""

    TEMPLATES = "templates"
    METRICS = "metrics"
    COMPANIES = "companies"
    CHARTS = "charts"
    ANALYTICS_CONTEXT = "analytics_context"


@dataclass
class ConfigResult:
    """Result wrapper for configuration queries."""

    data: List[Dict[str, Any]]
    source: ConfigSource
    query_time_ms: float
    error: Optional[str] = None
    fallback_attempted: List[ConfigSource] = field(default_factory=list)
    cache_hit: bool = False

    @property
    def success(self) -> bool:
        return self.error is None and len(self.data) > 0


class ConfigStore:
    """YAML-backed configuration store with optional caching."""

    def __init__(self) -> None:
        self.yaml_configs = CONFIGS.__dict__
        self.cache_service = get_cache_service()

    async def _load_from_cache(self, query_type: QueryType, query: str, **kwargs: Any) -> Optional[ConfigResult]:
        if not self.cache_service:
            return None
        cached = await self.cache_service.get("config", query, query_type=query_type.value, **kwargs)
        if not cached:
            return None
        try:
            return self._deserialize_config_result(cached, cache_hit=True)
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("Failed to hydrate cached config result: %s", exc)
            return None

    async def _store_in_cache(
        self,
        query_type: QueryType,
        query: str,
        result: ConfigResult,
        **kwargs: Any,
    ) -> None:
        if not self.cache_service or not result.success:
            return
        payload = self._serialize_config_result(result)
        try:
            await self.cache_service.set("config", query, payload, query_type=query_type.value, **kwargs)
        except Exception as exc:  # pragma: no cover - cache failures should not bubble
            logger.debug("Config cache set failed for query '%s': %s", query, exc)

    @staticmethod
    def _serialize_config_result(result: ConfigResult) -> Dict[str, Any]:
        return {
            "data": result.data,
            "source": result.source.value,
            "query_time_ms": result.query_time_ms,
            "error": result.error,
            "fallback_attempted": [entry.value for entry in result.fallback_attempted],
            "cache_hit": result.cache_hit,
        }

    @staticmethod
    def _deserialize_config_result(payload: Dict[str, Any], cache_hit: bool = False) -> ConfigResult:
        fallback_attempted = [ConfigSource(entry) for entry in payload.get("fallback_attempted", [])]
        source = ConfigSource(payload.get("source", ConfigSource.YAML_CONFIG.value))
        return ConfigResult(
            data=payload.get("data", []),
            source=source,
            query_time_ms=float(payload.get("query_time_ms", 0.0)),
            error=payload.get("error"),
            fallback_attempted=fallback_attempted,
            cache_hit=cache_hit or bool(payload.get("cache_hit")),
        )

    async def _search_with_yaml(self, query_type: QueryType, query: str, **kwargs: Any) -> List[Dict[str, Any]]:
        if query_type == QueryType.TEMPLATES:
            return await self._yaml_templates_search(query, **kwargs)
        if query_type == QueryType.METRICS:
            return await self._yaml_metrics_search(query, **kwargs)
        if query_type == QueryType.COMPANIES:
            return await self._yaml_companies_search(query, **kwargs)
        if query_type == QueryType.CHARTS:
            return await self._yaml_charts_search(query, **kwargs)
        if query_type == QueryType.ANALYTICS_CONTEXT:
            return await self._yaml_analytics_context(query, **kwargs)
        return []

    async def _search_configs(self, query_type: QueryType, query: str, **kwargs: Any) -> ConfigResult:
        start = time.time()

        cached = await self._load_from_cache(query_type, query, **kwargs)
        if cached:
            return cached

        data = await self._search_with_yaml(query_type, query, **kwargs)
        elapsed_ms = (time.time() - start) * 1000

        if data:
            result = ConfigResult(
                data=data,
                source=ConfigSource.YAML_CONFIG,
                query_time_ms=elapsed_ms,
            )
        else:
            result = ConfigResult(
                data=[],
                source=ConfigSource.EMPTY_FALLBACK,
                query_time_ms=elapsed_ms,
                error="no_matches_found",
            )

        await self._store_in_cache(query_type, query, result, **kwargs)
        return result

    # =============== PUBLIC LOOKUPS ===============

    async def get_templates(
        self,
        query: str,
        intent_key: Optional[str] = None,
        top_k: int = 3,
    ) -> ConfigResult:
        return await self._search_configs(
            QueryType.TEMPLATES,
            query,
            intent_key=intent_key,
            top_k=top_k,
        )

    async def get_metrics(
        self,
        query: str,
        category: Optional[str] = None,
        top_k: int = 5,
        include_derived: bool = True,
    ) -> ConfigResult:
        return await self._search_configs(
            QueryType.METRICS,
            query,
            category=category,
            top_k=top_k,
            include_derived=include_derived,
        )

    async def get_companies(
        self,
        query: str,
        sector: Optional[str] = None,
        top_k: int = 5,
    ) -> ConfigResult:
        return await self._search_configs(
            QueryType.COMPANIES,
            query,
            sector=sector,
            top_k=top_k,
        )

    async def get_charts(
        self,
        query: str,
        chart_type: Optional[str] = None,
        top_k: int = 3,
    ) -> ConfigResult:
        return await self._search_configs(
            QueryType.CHARTS,
            query,
            chart_type=chart_type,
            top_k=top_k,
        )

    async def get_analytics_context(
        self,
        query: str = "",
        top_k: int = 5,
        include: Optional[List[str]] = None,
    ) -> ConfigResult:
        return await self._search_configs(
            QueryType.ANALYTICS_CONTEXT,
            query,
            top_k=top_k,
            include=include,
        )

    @staticmethod
    def _merge_nested(base: Dict[str, Any], extra: Dict[str, Any]) -> Dict[str, Any]:
        merged = dict(base)
        for key, value in extra.items():
            if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
                merged[key] = ConfigStore._merge_nested(merged[key], value)
            else:
                merged[key] = value
        return merged

    def get_agent_mode_config(self, mode: str) -> Dict[str, Any]:
        agents_section = self.yaml_configs.get("agents", {})
        if not isinstance(agents_section, dict):
            return {}
        key = str(mode or "").strip()
        defaults = agents_section.get("defaults", {})
        resolved: Dict[str, Any] = {}
        if isinstance(defaults, dict):
            resolved = self._merge_nested(resolved, defaults)
        payload = agents_section.get(key, {})
        if isinstance(payload, dict):
            resolved = self._merge_nested(resolved, payload)
        return resolved

    def get_agent_feature_flags(self) -> Dict[str, Any]:
        flags_section = self.yaml_configs.get("agent_feature_flags", {})
        if not isinstance(flags_section, dict):
            return {}

        resolved: Dict[str, Any] = {}
        for key, meta in flags_section.items():
            if not isinstance(meta, dict):
                continue
            env_name = str(meta.get("env") or "").strip()
            default_value = meta.get("default")
            raw = os.getenv(env_name) if env_name else None

            if isinstance(default_value, bool):
                if raw is None:
                    resolved_value = bool(default_value)
                else:
                    normalized = raw.strip().lower()
                    resolved_value = normalized in {"1", "true", "yes", "on"}
            else:
                resolved_value = raw if raw is not None else default_value

            resolved[key] = {
                "value": resolved_value,
                "env": env_name or None,
                "default": default_value,
                "description": meta.get("description"),
            }

        return resolved

    # =============== YAML LOOKUPS ===============

    async def _yaml_templates_search(self, query: str, **kwargs: Any) -> List[Dict[str, Any]]:
        queries_section = self.yaml_configs.get("queries", {}) or {}
        patterns = queries_section.get("query_patterns", {}) or queries_section

        matches: List[Dict[str, Any]] = []
        intent_key = kwargs.get("intent_key")
        top_k = kwargs.get("top_k", 3)
        q_lower = query.lower()

        for key, pattern in patterns.items():
            if intent_key and key != intent_key:
                continue

            keywords = pattern.get("keywords", []) or [pattern.get("name", ""), pattern.get("description", "")]
            haystacks = [str(kw).lower() for kw in keywords if isinstance(kw, (str, bytes))]
            if q_lower:
                normalized_query_tokens = {
                    token for token in q_lower.replace("?", " " ).replace(",", " " ).split() if token
                }
                match_found = any(
                    hay in q_lower or any(token in hay for token in normalized_query_tokens)
                    for hay in haystacks
                )
                if not match_found:
                    continue

            matches.append(
                {
                    "id": pattern.get("id", key),
                    "name": pattern.get("name", key.replace("_", " ").title()),
                    "description": pattern.get("description", ""),
                    "sql_template": pattern.get("sql_template"),
                    "intent_key": pattern.get("intent_key", key),
                    "source": "yaml",
                }
            )
            if len(matches) >= top_k:
                break

        return matches

    async def _yaml_metrics_search(self, query: str, **kwargs: Any) -> List[Dict[str, Any]]:
        metrics_config = self.yaml_configs.get("metrics", {}) or {}
        base_metrics: List[Dict[str, Any]] = []

        metrics_section = metrics_config.get("metrics")
        if isinstance(metrics_section, dict):
            base_metrics.extend(metrics_section.values())
        elif isinstance(metrics_section, list):
            base_metrics.extend(metrics_section)

        include_derived = kwargs.get("include_derived", True)
        if include_derived:
            derived_metrics = metrics_config.get("derived_metrics", [])
            if isinstance(derived_metrics, dict):
                base_metrics.extend(derived_metrics.values())
            elif isinstance(derived_metrics, list):
                base_metrics.extend(derived_metrics)

        matches: List[Dict[str, Any]] = []
        category_filter = kwargs.get("category")
        top_k = kwargs.get("top_k", 5)
        q_lower = query.lower()

        for metric in base_metrics:
            names = [metric.get("name", ""), metric.get("metric_id", ""), metric.get("short_name", "")]
            aliases = metric.get("aliases", [])
            description = metric.get("description", "")

            tokens = [*(str(name).lower() for name in names if isinstance(name, (str, bytes))),
                      *(str(alias).lower() for alias in aliases if isinstance(alias, (str, bytes)))]
            if q_lower:
                haystack = tokens + [str(description).lower()]
                if not any(q_lower in token for token in haystack):
                    continue

            if category_filter and metric.get("category") != category_filter:
                continue

            matches.append(metric)
            if len(matches) >= top_k:
                break

        return matches

    async def _yaml_companies_search(self, query: str, **kwargs: Any) -> List[Dict[str, Any]]:
        companies_config = self.yaml_configs.get("companies", {}) or {}
        sector_filter = kwargs.get("sector")
        top_k = kwargs.get("top_k", 5)
        q_lower = query.lower()

        matches: List[Dict[str, Any]] = []

        sectors = companies_config.get("sectors") if isinstance(companies_config.get("sectors"), dict) else companies_config
        iterable = sectors.items() if isinstance(sectors, dict) else []

        for sector, companies in iterable:
            if sector_filter and sector != sector_filter:
                continue

            records = companies.get("companies", []) if isinstance(companies, dict) else []
            for company in records:
                aliases = company.get("aliases", [])
                tokens = [company.get("name", ""), company.get("ticker", ""), *(aliases or [])]
                if q_lower and not any(q_lower in str(token).lower() for token in tokens):
                    continue

                entry = {**company, "sector": sector}
                matches.append(entry)
                if len(matches) >= top_k:
                    break
            if len(matches) >= top_k:
                break

        return matches

    async def _yaml_charts_search(self, query: str, **kwargs: Any) -> List[Dict[str, Any]]:
        charts_config = self.yaml_configs.get("charts", {}) or {}
        chart_types = charts_config.get("chart_types", [])
        top_k = kwargs.get("top_k", 3)
        chart_type_filter = kwargs.get("chart_type")
        q_lower = query.lower()

        matches: List[Dict[str, Any]] = []
        for chart in chart_types:
            chart_type = chart.get("type", "")
            description = chart.get("description", "")
            name = chart.get("name", "")

            if chart_type_filter and chart_type != chart_type_filter:
                continue

            haystack = " ".join([str(name), str(description), str(chart_type)]).lower()
            if q_lower and q_lower not in haystack:
                continue

            matches.append(
                {
                    "type": chart_type,
                    "name": name,
                    "description": description,
                    "config": chart.get("config", {}),
                }
            )
            if len(matches) >= top_k:
                break

        return matches

    async def _yaml_analytics_context(self, query: str, **kwargs: Any) -> List[Dict[str, Any]]:
        include = kwargs.get("include") or ["queries", "metrics", "charts", "companies"]
        top_k = kwargs.get("top_k", 5)
        q_lower = query.lower()

        context: List[Dict[str, Any]] = []

        if "queries" in include:
            queries_section = self.yaml_configs.get("queries", {}) or {}
            patterns = queries_section.get("query_patterns", {}) or queries_section
            intents = list(patterns.keys())[:top_k]
            if not q_lower or any(q_lower in key.lower() for key in intents):
                context.append({
                    "type": "query_patterns",
                    "count": len(patterns),
                    "examples": intents,
                })

        if "metrics" in include:
            metrics_section = self.yaml_configs.get("metrics", {}) or {}
            metrics = metrics_section.get("metrics")
            metric_count = len(metrics) if isinstance(metrics, (list, dict)) else 0
            if not q_lower or "metric" in q_lower:
                context.append({
                    "type": "metrics_catalogue",
                    "count": metric_count,
                    "derived": bool(metrics_section.get("derived_metrics")),
                })

        if "charts" in include:
            charts_section = self.yaml_configs.get("charts", {}) or {}
            chart_types = charts_section.get("chart_types", [])
            if not q_lower or "chart" in q_lower:
                context.append({
                    "type": "chart_library",
                    "count": len(chart_types),
                    "supported_types": [chart.get("type") for chart in chart_types[:top_k]],
                })

        if "companies" in include:
            companies_section = self.yaml_configs.get("companies", {}) or {}
            sectors = companies_section.get("sectors", {})
            sector_count = len(sectors) if isinstance(sectors, dict) else 0
            if not q_lower or "company" in q_lower or "sector" in q_lower:
                context.append({
                    "type": "company_index",
                    "sectors": sector_count,
                    "examples": list(sectors.keys())[:top_k] if isinstance(sectors, dict) else [],
                })

        return context

    # =============== MAINTENANCE ===============

    async def clear_cache(self) -> None:
        if self.cache_service:
            await self.cache_service.clear_all()

    async def close(self) -> None:
        if self.cache_service:
            await self.cache_service.close()


_config_store: Optional[ConfigStore] = None


def get_config_store() -> ConfigStore:
    global _config_store
    if _config_store is None:
        _config_store = ConfigStore()
    return _config_store


if __name__ == "__main__":
    import asyncio

    async def _debug():
        store = get_config_store()
        print(await store.get_templates("revenue analysis"))
        print(await store.get_metrics("revenue"))
        print(await store.get_companies("nvidia"))
        print(await store.get_charts("line"))
        print(await store.get_analytics_context("overview"))

    asyncio.run(_debug())
