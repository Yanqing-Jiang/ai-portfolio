#!/usr/bin/env python3
"""
Unified Configuration Store for Analytics System

This module provides a unified interface for accessing all configuration data
with deterministic fallback chains and standardized response formats.

ARCHITECTURE OVERVIEW:
┌─────────────────────────────────────────┐
│            config_store.py              │  ← Unified interface layer
│  (Deterministic fallback orchestration) │     with caching & monitoring
└─────────────┬───────────────────────────┘
              ↓ Fallback Chain
┌─────────────────────────────────────────┐
│  1. rag_service.py (Advanced search)    │  ← Primary: Hybrid vector + keyword
│  2. template_store.py (SQL templates)   │  ← Secondary: Vector templates only
│  3. YAML configs (File-based)           │  ← Tertiary: Static configuration
│  4. Empty results (Graceful failure)    │  ← Final: Prevent crashes
└─────────────────────────────────────────┘

Fallback Chain: RAG Service → Template Store → YAML Configs → Empty Results

Features:
- Unified interface for all config types (templates, metrics, companies, charts)
- Deterministic fallback coverage with graceful degradation
- Standardized result format across all sources
- Performance monitoring and caching
- Comprehensive error handling and logging

Usage:
    store = get_config_store()
    templates = await store.get_templates("market share query")
    metrics = await store.get_metrics("revenue growth")
"""

from __future__ import annotations
from typing import Any, Dict, List, Optional, Union, Tuple, TypeVar, Generic
from dataclasses import dataclass, field
from enum import Enum
import logging
import time
import asyncio
from pathlib import Path

# Import existing services
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from analytics_supervisor.rag_service import get_rag_service, SearchContext, SearchMode, SearchResult
    from analytics_supervisor.template_store import search_templates
    from analytics_memory.config import CONFIGS
except ImportError:
    # Fallback - create minimal mock versions for testing
    import logging
    logger = logging.getLogger(__name__)
    logger.warning("Could not import dependencies - using fallback implementations")

    class SearchMode:
        HYBRID = "hybrid"
        VECTOR_ONLY = "vector_only"
        KEYWORD_ONLY = "keyword_only"
        AUTO = "auto"

    class SearchContext:
        def __init__(self, **kwargs):
            for k, v in kwargs.items():
                setattr(self, k, v)

    class SearchResult:
        def __init__(self, **kwargs):
            for k, v in kwargs.items():
                setattr(self, k, v)

    def get_rag_service():
        return None

    async def search_templates(*args, **kwargs):
        return []

    class MockConfigs:
        def __init__(self):
            self.__dict__ = {}

    CONFIGS = MockConfigs()

logger = logging.getLogger(__name__)

T = TypeVar('T')


class ConfigSource(Enum):
    """Configuration data sources in order of preference"""
    RAG_SERVICE = "rag_service"
    TEMPLATE_STORE = "template_store"
    YAML_CONFIG = "yaml_config"
    EMPTY_FALLBACK = "empty_fallback"


class QueryType(Enum):
    """Types of configuration queries"""
    TEMPLATES = "templates"
    METRICS = "metrics"
    COMPANIES = "companies"
    CHARTS = "charts"
    DATABASE = "database"
    CONTEXT = "context"


@dataclass
class ConfigResult(Generic[T]):
    """Standardized result format for all config operations"""
    data: List[T]
    source: ConfigSource
    query_time_ms: float
    total_results: int
    query_info: Dict[str, Any] = field(default_factory=dict)
    fallback_attempted: List[ConfigSource] = field(default_factory=list)
    error: Optional[str] = None
    cache_hit: bool = False

    @property
    def success(self) -> bool:
        """Whether the query was successful"""
        return self.error is None and len(self.data) > 0

    @property
    def is_empty_fallback(self) -> bool:
        """Whether this result is from empty fallback"""
        return self.source == ConfigSource.EMPTY_FALLBACK


@dataclass
class FallbackConfig:
    """Configuration for fallback behavior"""
    enable_rag: bool = True
    enable_template_store: bool = True
    enable_yaml_config: bool = True
    timeout_rag_ms: int = 5000
    timeout_template_store_ms: int = 3000
    timeout_yaml_ms: int = 1000
    max_fallback_attempts: int = 3


class ConfigStore:
    """Unified configuration store with deterministic fallback coverage"""

    def __init__(self, fallback_config: Optional[FallbackConfig] = None):
        self.fallback_config = fallback_config or FallbackConfig()
        self.rag_service = None
        self.yaml_configs = CONFIGS.__dict__
        self._cache = {}
        self._cache_ttl = 300  # 5 minutes for config cache

    async def _get_rag_service(self):
        """Lazy initialization of RAG service"""
        if self.rag_service is None:
            try:
                self.rag_service = get_rag_service()
            except Exception as e:
                logger.warning(f"Failed to initialize RAG service: {e}")
                self.rag_service = False  # Mark as failed to avoid retry
        return self.rag_service if self.rag_service is not False else None

    def _cache_key(self, query_type: QueryType, query: str, **kwargs) -> str:
        """Generate cache key for query"""
        import json
        params = json.dumps(kwargs, sort_keys=True)
        return f"{query_type.value}:{hash(query + params)}"

    def _is_cache_valid(self, timestamp: float) -> bool:
        """Check if cache entry is still valid"""
        return time.time() - timestamp < self._cache_ttl

    async def _retrieve_with_fallback(
        self,
        query_type: QueryType,
        primary_query: callable,
        fallback_queries: List[Tuple[ConfigSource, callable]],
        query: str,
        **kwargs
    ) -> ConfigResult[Dict[str, Any]]:
        """Execute query with deterministic fallback chain"""

        start_time = time.time()
        fallback_attempted = []
        last_error = None

        def _elapsed_ms():
            return max(round((time.time() - start_time) * 1000, 2), 0.01)

        # Check cache first
        cache_key = self._cache_key(query_type, query, **kwargs)
        if cache_key in self._cache:
            cached_time, cached_result = self._cache[cache_key]
            if self._is_cache_valid(cached_time):
                cached_result.cache_hit = True
                return cached_result

        # Try primary source (RAG service)
        if self.fallback_config.enable_rag:
            try:
                timeout = self.fallback_config.timeout_rag_ms / 1000.0
                data = await asyncio.wait_for(primary_query(), timeout=timeout)

                if data:  # Success case
                    result = ConfigResult(
                        data=data,
                        source=ConfigSource.RAG_SERVICE,
                        query_time_ms=_elapsed_ms(),
                        total_results=len(data),
                        query_info={"query": query, "type": query_type.value, **kwargs},
                        fallback_attempted=fallback_attempted
                    )

                    # Cache successful results
                    self._cache[cache_key] = (time.time(), result)
                    return result

            except Exception as e:
                logger.warning(f"RAG service failed for {query_type.value}: {e}")
                fallback_attempted.append(ConfigSource.RAG_SERVICE)
                last_error = str(e)

        # Try fallback sources
        for source, fallback_func in fallback_queries:
            if (source == ConfigSource.TEMPLATE_STORE and not self.fallback_config.enable_template_store) or \
               (source == ConfigSource.YAML_CONFIG and not self.fallback_config.enable_yaml_config):
                continue

            fallback_attempted.append(source)

            try:
                if source == ConfigSource.TEMPLATE_STORE:
                    timeout = self.fallback_config.timeout_template_store_ms / 1000.0
                else:
                    timeout = self.fallback_config.timeout_yaml_ms / 1000.0

                data = await asyncio.wait_for(fallback_func(), timeout=timeout)

                if data:  # Success case
                    result = ConfigResult(
                        data=data,
                        source=source,
                        query_time_ms=_elapsed_ms(),
                        total_results=len(data),
                        query_info={"query": query, "type": query_type.value, **kwargs},
                        fallback_attempted=fallback_attempted
                    )

                    # Cache successful fallback results
                    self._cache[cache_key] = (time.time(), result)
                    return result

            except Exception as e:
                logger.warning(f"Fallback {source.value} failed for {query_type.value}: {e}")
                last_error = str(e)

        # Final fallback: empty result
        fallback_attempted.append(ConfigSource.EMPTY_FALLBACK)
        result = ConfigResult(
            data=[],
            source=ConfigSource.EMPTY_FALLBACK,
            query_time_ms=_elapsed_ms(),
            total_results=0,
            query_info={"query": query, "type": query_type.value, **kwargs},
            fallback_attempted=fallback_attempted,
            error=last_error
        )

        return result

    # =============== TEMPLATES ===============

    async def get_templates(
        self,
        query: str,
        intent_key: Optional[str] = None,
        top_k: int = 3,
        mode: str = "hybrid"
    ) -> ConfigResult[Dict[str, Any]]:
        """Get SQL templates with unified fallback chain"""

        async def rag_query():
            rag_service = await self._get_rag_service()
            if not rag_service:
                return []

            search_mode = getattr(SearchMode, mode.upper(), SearchMode.HYBRID)
            results = await rag_service.search_templates(
                query=query,
                intent_key=intent_key,
                top_k=top_k,
                mode=search_mode
            )

            # Convert SearchResult objects to dictionaries
            return [self._convert_search_result_to_dict(result) for result in results]

        async def template_store_query():
            try:
                results = await search_templates(query, intent_key=intent_key, top_k=top_k)
                return results if results else []
            except Exception:
                return []

        async def yaml_query():
            try:
                # Access YAML query patterns (support both CONFIGS.queries and simplified test fixtures)
                queries_section = self.yaml_configs.get('queries', {})
                patterns = queries_section.get('query_patterns', {})
                if not patterns:
                    patterns = self.yaml_configs.get('query_patterns', {})

                matches = []
                normalized_query = query.lower()

                for key, pattern in patterns.items():
                    if intent_key and key != intent_key:
                        continue

                    keywords = pattern.get('keywords', [])
                    if not keywords:
                        keywords = [pattern.get('name', ''), pattern.get('description', '')]

                    if any(keyword and keyword.lower() in normalized_query for keyword in keywords):
                        matches.append({
                            'id': pattern.get('id', key),
                            'name': pattern.get('name', key.replace('_', ' ').title()),
                            'description': pattern.get('description', ''),
                            'sql_template': pattern.get('sql_template'),
                            'intent_key': pattern.get('intent_key', key),
                            'source': 'yaml_config'
                        })

                        if len(matches) >= top_k:
                            break

                return matches
            except Exception:
                return []

        fallback_queries = [
            (ConfigSource.TEMPLATE_STORE, template_store_query),
            (ConfigSource.YAML_CONFIG, yaml_query)
        ]

        return await self._retrieve_with_fallback(
            QueryType.TEMPLATES, rag_query, fallback_queries, query,
            intent_key=intent_key, top_k=top_k, mode=mode
        )

    # =============== METRICS ===============

    async def get_metrics(
        self,
        query: str,
        category: Optional[str] = None,
        top_k: int = 5,
        include_derived: bool = True
    ) -> ConfigResult[Dict[str, Any]]:
        """Get metrics with unified fallback chain"""

        async def rag_query():
            rag_service = await self._get_rag_service()
            if not rag_service:
                return []

            results = await rag_service.search_metrics(
                query=query,
                category=category,
                top_k=top_k,
                include_derived=include_derived
            )

            return [self._convert_search_result_to_dict(result) for result in results]

        async def yaml_query():
            try:
                metrics_config = self.yaml_configs.get('metrics', {})
                base_metrics = []

                metrics_section = metrics_config.get('metrics')
                if isinstance(metrics_section, dict):
                    base_metrics.extend(metrics_section.values())
                elif isinstance(metrics_section, list):
                    base_metrics.extend(metrics_section)

                extra_base = metrics_config.get('base_metrics')
                if isinstance(extra_base, list):
                    base_metrics.extend(extra_base)

                derived_metrics = metrics_config.get('derived_metrics', []) if include_derived else []
                if isinstance(derived_metrics, dict):
                    derived_values = list(derived_metrics.values())
                else:
                    derived_values = derived_metrics if include_derived else []

                all_metrics = base_metrics + derived_values
                matches = []
                normalized_query = query.lower()

                for metric in all_metrics:
                    aliases = metric.get('aliases', [])
                    description = metric.get('description', '')
                    names = [metric.get('name', ''), metric.get('metric_id', ''), metric.get('short_name', '')]

                    if (
                        any(alias and alias.lower() in normalized_query for alias in aliases)
                        or any(name and name.lower() in normalized_query for name in names)
                        or (description and normalized_query in description.lower())
                    ):
                        if category and metric.get('category') != category:
                            continue
                        matches.append(metric)

                        if len(matches) >= top_k:
                            break

                return matches
            except Exception:
                return []

        fallback_queries = [
            (ConfigSource.YAML_CONFIG, yaml_query)
        ]

        return await self._retrieve_with_fallback(
            QueryType.METRICS, rag_query, fallback_queries, query,
            category=category, top_k=top_k, include_derived=include_derived
        )

    # =============== COMPANIES ===============

    async def get_companies(
        self,
        query: str,
        sector: Optional[str] = None,
        top_k: int = 5,
        include_aliases: bool = True
    ) -> ConfigResult[Dict[str, Any]]:
        """Get companies with unified fallback chain"""

        async def rag_query():
            rag_service = await self._get_rag_service()
            if not rag_service:
                return []

            results = await rag_service.search_companies(
                query=query,
                sector=sector,
                top_k=top_k,
                include_aliases=include_aliases
            )

            return [self._convert_search_result_to_dict(result) for result in results]

        async def yaml_query():
            try:
                companies_section = self.yaml_configs.get('companies', {})
                if isinstance(companies_section.get('companies'), dict):
                    companies_config = companies_section.get('companies', {})
                else:
                    companies_config = companies_section

                matches = []
                normalized_query = query.lower()

                for sector, companies in companies_config.items():
                    if isinstance(companies, dict) and 'companies' in companies:
                        records = companies.get('companies', [])
                    elif isinstance(companies, list):
                        records = companies
                    else:
                        records = []

                    for company in records:
                        aliases = company.get('aliases', []) + [company.get('name', ''), company.get('ticker', ''), sector]
                        if any(alias and alias.lower() in normalized_query for alias in aliases):
                            entry = company.copy()
                            entry.setdefault('sector', sector)
                            matches.append(entry)

                            if len(matches) >= top_k:
                                break

                return matches
            except Exception:
                return []

        fallback_queries = [
            (ConfigSource.YAML_CONFIG, yaml_query)
        ]

        return await self._retrieve_with_fallback(
            QueryType.COMPANIES, rag_query, fallback_queries, query,
            sector=sector, top_k=top_k, include_aliases=include_aliases
        )

    # =============== CHARTS ===============

    async def get_charts(
        self,
        query: str,
        chart_type: Optional[str] = None,
        top_k: int = 3
    ) -> ConfigResult[Dict[str, Any]]:
        """Get chart configurations with fallback to YAML"""

        async def rag_query():
            # RAG service doesn't currently support chart search
            # This would be implemented when chart configs are migrated to Supabase
            return []

        async def yaml_query():
            try:
                # Access YAML charts configuration
                charts_config = self.yaml_configs.get('charts', {})
                chart_types = charts_config.get('chart_types', [])

                matches = []
                query_lower = query.lower()

                for chart in chart_types:
                    name = chart.get('name', '')
                    description = chart.get('description', '')
                    chart_type_name = chart.get('type', '')

                    if (query_lower in name.lower() or
                        query_lower in description.lower() or
                        query_lower in chart_type_name.lower()):

                        if chart_type and chart_type_name != chart_type:
                            continue

                        matches.append({
                            'type': chart_type_name,
                            'name': name,
                            'description': description,
                            'config': chart.get('config', {}),
                            'source_table': 'yaml_config'
                        })

                        if len(matches) >= top_k:
                            break

                return matches

            except Exception:
                return []

        fallback_queries = [
            (ConfigSource.YAML_CONFIG, yaml_query)
        ]

        return await self._retrieve_with_fallback(
            QueryType.CHARTS, rag_query, fallback_queries, query,
            chart_type=chart_type, top_k=top_k
        )

    # =============== CONTEXT-AWARE RETRIEVAL ===============

    async def get_analytics_context(
        self,
        query: str,
        intent_key: Optional[str] = None,
        company_filter: Optional[str] = None,
        category_filter: Optional[str] = None,
        chart_type: Optional[str] = None
    ) -> ConfigResult[Dict[str, Any]]:
        """Get comprehensive analytics context with fallback chain"""

        async def rag_query():
            rag_service = await self._get_rag_service()
            if not rag_service:
                return []

            context = SearchContext(
                query=query,
                intent_key=intent_key,
                company_filter=company_filter,
                category_filter=category_filter,
                chart_type=chart_type
            )

            result = await rag_service.get_analytics_context(context)
            return [result] if result else []

        async def fallback_query():
            # Compose context from individual queries using this ConfigStore
            try:
                templates_result = await self.get_templates(query, intent_key, top_k=3)
                metrics_result = await self.get_metrics(query, category_filter, top_k=5)
                companies_result = await self.get_companies(query, top_k=3)
                charts_result = await self.get_charts(query, chart_type, top_k=2)

                context = {
                    'templates': templates_result.data,
                    'metrics': metrics_result.data,
                    'companies': companies_result.data,
                    'charts': charts_result.data,
                    'query_metadata': {
                        'query': query,
                        'intent_key': intent_key,
                        'filters_applied': {
                            'company': company_filter,
                            'category': category_filter,
                            'chart_type': chart_type
                        },
                        'sources_used': {
                            'templates': templates_result.source.value,
                            'metrics': metrics_result.source.value,
                            'companies': companies_result.source.value,
                            'charts': charts_result.source.value
                        }
                    }
                }

                return [context]

            except Exception:
                return []

        fallback_queries = [
            (ConfigSource.YAML_CONFIG, fallback_query)
        ]

        return await self._retrieve_with_fallback(
            QueryType.CONTEXT, rag_query, fallback_queries, query,
            intent_key=intent_key, company_filter=company_filter,
            category_filter=category_filter, chart_type=chart_type
        )

    # =============== UTILITY METHODS ===============

    def _convert_search_result_to_dict(self, result: SearchResult) -> Dict[str, Any]:
        """Convert SearchResult object to dictionary format"""
        return {
            'id': result.id,
            'title': result.title,
            'description': result.description,
            'score': result.score,
            'distance': result.distance,
            'source_table': result.source_table,
            **result.content
        }

    async def get_system_stats(self) -> Dict[str, Any]:
        """Get configuration system statistics"""
        stats = {
            'cache_size': len(self._cache),
            'fallback_config': {
                'rag_enabled': self.fallback_config.enable_rag,
                'template_store_enabled': self.fallback_config.enable_template_store,
                'yaml_enabled': self.fallback_config.enable_yaml_config
            },
            'sources_available': []
        }

        # Check RAG service availability
        try:
            rag_service = await self._get_rag_service()
            if rag_service:
                rag_stats = await rag_service.get_search_stats()
                stats['rag_service_stats'] = rag_stats
                stats['sources_available'].append('rag_service')
        except Exception:
            pass

        # Template store is available if DATABASE_URL is set
        import os
        if os.getenv("DATABASE_URL"):
            stats['sources_available'].append('template_store')

        # YAML configs are always available
        if self.yaml_configs:
            stats['sources_available'].append('yaml_config')
            stats['yaml_config_keys'] = list(self.yaml_configs.keys())

        return stats

    def clear_cache(self) -> int:
        """Clear configuration cache and return number of entries cleared"""
        cleared_count = len(self._cache)
        self._cache.clear()
        return cleared_count

    async def close(self) -> None:
        """Close resources and cleanup"""
        if self.rag_service and self.rag_service is not False:
            try:
                await self.rag_service.close()
            except Exception:
                pass
        self.clear_cache()


# Global ConfigStore instance
_config_store = None


def get_config_store(fallback_config: Optional[FallbackConfig] = None) -> ConfigStore:
    """Get global ConfigStore instance"""
    global _config_store
    if _config_store is None:
        _config_store = ConfigStore(fallback_config)
    return _config_store


async def close_config_store() -> None:
    """Close global ConfigStore"""
    global _config_store
    if _config_store:
        await _config_store.close()
        _config_store = None


if __name__ == "__main__":
    import asyncio

    async def test_config_store():
        """Test the ConfigStore functionality"""
        from dotenv import load_dotenv
        load_dotenv()

        config_store = get_config_store()

        print("=== Testing ConfigStore ===")

        # Test templates
        print("\n--- Templates ---")
        templates_result = await config_store.get_templates("revenue analysis", top_k=2)
        print(f"Source: {templates_result.source.value}")
        print(f"Results: {len(templates_result.data)}")
        print(f"Query time: {templates_result.query_time_ms}ms")
        print(f"Fallbacks attempted: {[s.value for s in templates_result.fallback_attempted]}")

        # Test metrics
        print("\n--- Metrics ---")
        metrics_result = await config_store.get_metrics("revenue", top_k=3)
        print(f"Source: {metrics_result.source.value}")
        print(f"Results: {len(metrics_result.data)}")
        print(f"Query time: {metrics_result.query_time_ms}ms")

        # Test companies
        print("\n--- Companies ---")
        companies_result = await config_store.get_companies("nvidia", top_k=2)
        print(f"Source: {companies_result.source.value}")
        print(f"Results: {len(companies_result.data)}")
        print(f"Query time: {companies_result.query_time_ms}ms")

        # Test system stats
        print("\n--- System Stats ---")
        stats = await config_store.get_system_stats()
        print(f"Available sources: {stats['sources_available']}")
        print(f"Cache size: {stats['cache_size']}")

        await close_config_store()

    asyncio.run(test_config_store())
