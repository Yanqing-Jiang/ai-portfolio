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
│  2. YAML configs (File-based)           │  ← Secondary: Static configuration
│  3. Empty results (Graceful failure)    │  ← Final: Prevent crashes
└─────────────────────────────────────────┘

Fallback Chain: RAG Service → YAML Configs → Empty Results

Features:
- Unified interface for all config types (templates, metrics, companies, charts)
- Streamlined 2-layer fallback with graceful degradation
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
    from analytics_supervisor.cache_service import get_cache_service
    from analytics_memory.config import CONFIGS
except ImportError:
    logger = logging.getLogger(__name__)
    logger.warning("Could not import dependencies - using fallback implementations")

    def get_rag_service():
        return None
    def get_cache_service():
        return None

    class MockConfigs:
        def __init__(self):
            self.__dict__ = {}
    CONFIGS = MockConfigs()

    class SearchMode:
        HYBRID = "hybrid"

logger = logging.getLogger(__name__)

T = TypeVar('T')


class ConfigSource(Enum):
    """Configuration data sources in order of preference"""
    RAG_SERVICE = "rag_service"
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
class ConfigResult:
    """Simplified result format for config operations"""
    data: List[Dict[str, Any]]
    source: ConfigSource
    query_time_ms: float
    error: Optional[str] = None

    @property
    def success(self) -> bool:
        return self.error is None and len(self.data) > 0


@dataclass
class FallbackConfig:
    """Configuration for fallback behavior"""
    enable_rag: bool = True
    enable_yaml_config: bool = True
    timeout_rag_ms: int = 5000
    timeout_yaml_ms: int = 1000
    max_fallback_attempts: int = 2


class ConfigStore:
    """Unified configuration store with deterministic fallback coverage"""

    def __init__(self, fallback_config: Optional[FallbackConfig] = None):
        self.fallback_config = fallback_config or FallbackConfig()
        self.rag_service = None
        self.yaml_configs = CONFIGS.__dict__
        self.cache_service = get_cache_service()  # Centralized cache service

    async def _get_rag_service(self):
        """Lazy initialization of RAG service"""
        if self.rag_service is None:
            try:
                self.rag_service = get_rag_service()
            except Exception as e:
                logger.warning(f"Failed to initialize RAG service: {e}")
                self.rag_service = False  # Mark as failed to avoid retry
        return self.rag_service if self.rag_service is not False else None


    async def _search_with_fallback(self, query_type: QueryType, query: str, **kwargs) -> ConfigResult:
        """Simplified fallback search"""
        start_time = time.time()

        # Check cache first
        if self.cache_service:
            cached = await self.cache_service.get("config", query, query_type=query_type.value, **kwargs)
            if cached:
                return ConfigResult(**cached)

        # Try RAG service first
        if self.fallback_config.enable_rag:
            try:
                rag_service = await self._get_rag_service()
                if rag_service:
                    data = await self._rag_search(rag_service, query_type, query, **kwargs)
                    if data:
                        result = ConfigResult(
                            data=data,
                            source=ConfigSource.RAG_SERVICE,
                            query_time_ms=(time.time() - start_time) * 1000
                        )
                        if self.cache_service:
                            await self.cache_service.set("config", query, result.__dict__,
                                                       query_type=query_type.value, **kwargs)
                        return result
            except Exception as e:
                logger.warning(f"RAG search failed: {e}")

        # Fallback to YAML
        try:
            data = await self._yaml_search(query_type, query, **kwargs)
            result = ConfigResult(
                data=data,
                source=ConfigSource.YAML_CONFIG,
                query_time_ms=(time.time() - start_time) * 1000
            )
            if self.cache_service:
                await self.cache_service.set("config", query, result.__dict__,
                                           query_type=query_type.value, **kwargs)
            return result
        except Exception as e:
            return ConfigResult(
                data=[],
                source=ConfigSource.EMPTY_FALLBACK,
                query_time_ms=(time.time() - start_time) * 1000,
                error=str(e)
            )

    async def _rag_search(self, rag_service, query_type: QueryType, query: str, **kwargs):
        """Generic RAG search dispatcher"""
        if query_type == QueryType.TEMPLATES:
            results = await rag_service.search_templates(query, kwargs.get('intent_key'), kwargs.get('top_k', 3))
        elif query_type == QueryType.METRICS:
            results = await rag_service.search_metrics(query, kwargs.get('category'), kwargs.get('top_k', 5), kwargs.get('include_derived', True))
        elif query_type == QueryType.COMPANIES:
            results = await rag_service.search_companies(query, kwargs.get('sector'), kwargs.get('top_k', 5), kwargs.get('include_aliases', True))
        else:
            return []

        return [self._convert_search_result_to_dict(result) for result in results]

    async def _yaml_search(self, query_type: QueryType, query: str, **kwargs):
        """Generic YAML search dispatcher"""
        if query_type == QueryType.TEMPLATES:
            return await self._yaml_templates_search(query, **kwargs)
        elif query_type == QueryType.METRICS:
            return await self._yaml_metrics_search(query, **kwargs)
        elif query_type == QueryType.COMPANIES:
            return await self._yaml_companies_search(query, **kwargs)
        elif query_type == QueryType.CHARTS:
            return await self._yaml_charts_search(query, **kwargs)
        return []

    # =============== TEMPLATES ===============

    async def get_templates(self, query: str, intent_key: Optional[str] = None, top_k: int = 3, mode: str = "hybrid") -> ConfigResult:
        """Get SQL templates with fallback chain"""
        return await self._search_with_fallback(QueryType.TEMPLATES, query, intent_key=intent_key, top_k=top_k, mode=mode)

    async def _yaml_templates_search(self, query: str, **kwargs):
        """YAML templates search"""
        try:
            queries_section = self.yaml_configs.get('queries', {})
            patterns = queries_section.get('query_patterns', {}) or self.yaml_configs.get('query_patterns', {})

            matches = []
            intent_key = kwargs.get('intent_key')
            top_k = kwargs.get('top_k', 3)

            for key, pattern in patterns.items():
                if intent_key and key != intent_key:
                    continue

                keywords = pattern.get('keywords', []) or [pattern.get('name', ''), pattern.get('description', '')]
                if any(keyword and keyword.lower() in query.lower() for keyword in keywords):
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

    # =============== METRICS ===============

    async def get_metrics(self, query: str, category: Optional[str] = None, top_k: int = 5, include_derived: bool = True) -> ConfigResult:
        """Get metrics with fallback chain"""
        return await self._search_with_fallback(QueryType.METRICS, query, category=category, top_k=top_k, include_derived=include_derived)

    async def _yaml_metrics_search(self, query: str, **kwargs):
        """YAML metrics search"""
        try:
            metrics_config = self.yaml_configs.get('metrics', {})
            base_metrics = []

            # Get base metrics
            metrics_section = metrics_config.get('metrics')
            if isinstance(metrics_section, dict):
                base_metrics.extend(metrics_section.values())
            elif isinstance(metrics_section, list):
                base_metrics.extend(metrics_section)

            # Add derived metrics if requested
            include_derived = kwargs.get('include_derived', True)
            if include_derived:
                derived_metrics = metrics_config.get('derived_metrics', [])
                if isinstance(derived_metrics, dict):
                    base_metrics.extend(derived_metrics.values())
                else:
                    base_metrics.extend(derived_metrics)

            matches = []
            category = kwargs.get('category')
            top_k = kwargs.get('top_k', 5)

            for metric in base_metrics:
                aliases = metric.get('aliases', [])
                description = metric.get('description', '')
                names = [metric.get('name', ''), metric.get('metric_id', ''), metric.get('short_name', '')]

                if (any(alias and alias.lower() in query.lower() for alias in aliases) or
                    any(name and name.lower() in query.lower() for name in names) or
                    (description and query.lower() in description.lower())):

                    if category and metric.get('category') != category:
                        continue
                    matches.append(metric)
                    if len(matches) >= top_k:
                        break

            return matches
        except Exception:
            return []

    # =============== COMPANIES ===============

    async def get_companies(self, query: str, sector: Optional[str] = None, top_k: int = 5, include_aliases: bool = True) -> ConfigResult:
        """Get companies with fallback chain"""
        return await self._search_with_fallback(QueryType.COMPANIES, query, sector=sector, top_k=top_k, include_aliases=include_aliases)

    async def _yaml_companies_search(self, query: str, **kwargs):
        """YAML companies search"""
        try:
            companies_section = self.yaml_configs.get('companies', {})
            companies_config = companies_section.get('companies', {}) if isinstance(companies_section.get('companies'), dict) else companies_section

            matches = []
            sector_filter = kwargs.get('sector')
            top_k = kwargs.get('top_k', 5)

            for sector, companies in companies_config.items():
                if sector_filter and sector != sector_filter:
                    continue

                records = companies.get('companies', []) if isinstance(companies, dict) and 'companies' in companies else (companies if isinstance(companies, list) else [])

                for company in records:
                    aliases = company.get('aliases', []) + [company.get('name', ''), company.get('ticker', ''), sector]
                    if any(alias and alias.lower() in query.lower() for alias in aliases):
                        entry = company.copy()
                        entry.setdefault('sector', sector)
                        matches.append(entry)
                        if len(matches) >= top_k:
                            break

            return matches
        except Exception:
            return []

    # =============== CHARTS ===============

    async def get_charts(self, query: str, chart_type: Optional[str] = None, top_k: int = 3) -> ConfigResult:
        """Get chart configurations with fallback to YAML"""
        return await self._search_with_fallback(QueryType.CHARTS, query, chart_type=chart_type, top_k=top_k)

    async def _yaml_charts_search(self, query: str, **kwargs):
        """YAML charts search"""
        try:
            charts_config = self.yaml_configs.get('charts', {})
            chart_types = charts_config.get('chart_types', [])

            matches = []
            chart_type_filter = kwargs.get('chart_type')
            top_k = kwargs.get('top_k', 3)

            for chart in chart_types:
                name = chart.get('name', '')
                description = chart.get('description', '')
                chart_type_name = chart.get('type', '')

                if (query.lower() in name.lower() or query.lower() in description.lower() or query.lower() in chart_type_name.lower()):
                    if chart_type_filter and chart_type_name != chart_type_filter:
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

    async def clear_cache(self) -> None:
        """Clear configuration cache"""
        if self.cache_service:
            await self.cache_service.clear_all()

    async def close(self) -> None:
        """Close resources and cleanup"""
        if self.rag_service and self.rag_service is not False:
            await self.rag_service.close()
        if self.cache_service:
            await self.cache_service.close()


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
