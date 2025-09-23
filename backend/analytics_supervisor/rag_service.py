#!/usr/bin/env python3
"""
Unified RAG Service for Analytics Configuration

This module provides intelligent retrieval across all configuration tables:
- SQL templates with vector similarity search
- Metrics with semantic matching and synonym expansion
- Companies with alias resolution and sector filtering
- Charts with type and theme recommendations
- Database schemas with column and table discovery

Features:
- Hybrid search (vector + keyword matching)
- Context-aware retrieval with related items
- Caching for performance optimization
- Comprehensive error handling and fallbacks
- Telemetry and monitoring integration
"""

from __future__ import annotations
from typing import Any, Dict, List, Optional, Union, Tuple
from dataclasses import dataclass, field
from enum import Enum
import os
import asyncio
import json
import logging
import time
from datetime import datetime, timedelta

import asyncpg

import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from unified_responses_client import get_unified_client

# Import cache service from current directory
try:
    from .cache_service import get_cache_service
except ImportError:
    # Fallback for testing or missing cache service
    def get_cache_service():
        return None

logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv("DATABASE_URL")


class SearchMode(Enum):
    """Search modes for different retrieval strategies"""
    VECTOR_ONLY = "vector_only"
    KEYWORD_ONLY = "keyword_only"
    HYBRID = "hybrid"
    AUTO = "auto"


@dataclass
class SearchResult:
    """Structured search result with metadata"""
    id: str
    title: str
    description: str
    content: Dict[str, Any]
    score: float
    distance: Optional[float] = None
    source_table: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SearchContext:
    """Context for enhanced search with related items"""
    query: str
    intent_key: Optional[str] = None
    company_filter: Optional[str] = None
    category_filter: Optional[str] = None
    time_period: Optional[str] = None
    chart_type: Optional[str] = None


class RAGService:
    """Unified RAG service for analytics configuration retrieval"""

    def __init__(self, connection_pool_size: int = 5):
        self.connection_pool = None
        self.pool_size = connection_pool_size
        self.cache_service = get_cache_service()  # Centralized Redis cache
        self.unified_client = self._get_unified_client()

    def _get_unified_client(self):
        """Get unified client for embeddings"""
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            logger.warning("OPENAI_API_KEY not set - vector search will be disabled")
            return None
        return get_unified_client()

    async def _get_connection(self) -> asyncpg.Connection:
        """Get database connection from pool or create new one"""
        if not DATABASE_URL:
            raise RuntimeError("DATABASE_URL not configured")

        if not self.connection_pool:
            self.connection_pool = await asyncpg.create_pool(
                DATABASE_URL,
                min_size=1,
                max_size=self.pool_size,
                command_timeout=20.0
            )

        return await self.connection_pool.acquire()

    async def _release_connection(self, conn: asyncpg.Connection) -> None:
        """Release connection back to pool"""
        if self.connection_pool:
            await self.connection_pool.release(conn)

    def _to_pgvector_literal(self, vec: List[float]) -> str:
        """Convert vector to pgvector literal format"""
        return "[" + ",".join(f"{x:.8f}" for x in vec) + "]"


    async def _get_query_embedding(self, query: str) -> Optional[List[float]]:
        """Get embedding for query text"""
        if not self.unified_client:
            return None

        try:
            embeddings = self.unified_client.create_embeddings_sync([query])
            return embeddings[0] if embeddings else None
        except Exception as e:
            logger.error(f"Failed to get embedding for query: {e}")
            return None

    # =============== SQL TEMPLATES ===============

    async def search_templates(
        self,
        query: str,
        intent_key: Optional[str] = None,
        top_k: int = 3,
        mode: SearchMode = SearchMode.HYBRID
    ) -> List[SearchResult]:
        """Search SQL templates with enhanced scoring"""

        # Check cache first
        if self.cache_service:
            cached_result = await self.cache_service.get(
                "templates", query,
                intent_key=intent_key, top_k=top_k, mode=mode.value
            )
            if cached_result:
                # Convert back to SearchResult objects
                return [SearchResult(**item) for item in cached_result]

        conn = await self._get_connection()
        try:
            results = []

            if mode in [SearchMode.VECTOR_ONLY, SearchMode.HYBRID, SearchMode.AUTO]:
                # Vector search
                embedding = await self._get_query_embedding(query)
                if embedding:
                    vector_literal = self._to_pgvector_literal(embedding)

                    filter_clause = ""
                    params = [vector_literal, top_k]

                    if intent_key:
                        filter_clause = "WHERE intent_key = $3"
                        params.append(intent_key)

                    sql = f"""
                        SELECT id, name, intent_key, description, sql_template,
                               (embedding <=> $1::vector) AS distance,
                               'sql_templates' as source_table
                        FROM sql_templates
                        {filter_clause}
                        ORDER BY embedding <=> $1::vector ASC
                        LIMIT $2
                    """

                    rows = await conn.fetch(sql, *params)
                    for row in rows:
                        results.append(SearchResult(
                            id=str(row['id']),
                            title=row['name'],
                            description=row['description'] or "",
                            content={
                                'intent_key': row['intent_key'],
                                'sql_template': row['sql_template']
                            },
                            score=1.0 - row['distance'],  # Convert distance to similarity score
                            distance=row['distance'],
                            source_table='sql_templates'
                        ))

            if mode in [SearchMode.KEYWORD_ONLY, SearchMode.HYBRID] and len(results) < top_k:
                # Keyword search fallback
                keyword_results = await self._keyword_search_templates(conn, query, intent_key, top_k - len(results))
                results.extend(keyword_results)

            # Cache results
            final_results = results[:top_k]
            if self.cache_service:
                # Convert SearchResult objects to dictionaries for caching
                cache_data = [result.__dict__ for result in final_results]
                await self.cache_service.set(
                    "templates", query, cache_data,
                    intent_key=intent_key, top_k=top_k, mode=mode.value
                )

            return final_results

        finally:
            await self._release_connection(conn)

    async def _keyword_search_templates(
        self,
        conn: asyncpg.Connection,
        query: str,
        intent_key: Optional[str],
        limit: int
    ) -> List[SearchResult]:
        """Keyword-based template search using PostgreSQL full-text search"""
        query_terms = query.lower().split()

        # Build search conditions
        conditions = []
        params = []
        param_idx = 1

        # Search in name, description, and intent_key
        for term in query_terms:
            conditions.append(f"(LOWER(name) LIKE ${param_idx} OR LOWER(description) LIKE ${param_idx} OR LOWER(intent_key) LIKE ${param_idx})")
            params.append(f"%{term}%")
            param_idx += 1

        where_clause = " AND ".join(conditions) if conditions else "TRUE"

        if intent_key:
            where_clause += f" AND intent_key = ${param_idx}"
            params.append(intent_key)

        sql = f"""
            SELECT id, name, intent_key, description, sql_template,
                   'sql_templates' as source_table
            FROM sql_templates
            WHERE {where_clause}
            ORDER BY
                CASE WHEN LOWER(name) LIKE $1 THEN 1 ELSE 2 END,
                LENGTH(name)
            LIMIT {limit}
        """

        rows = await conn.fetch(sql, *params)
        results = []

        for row in rows:
            # Simple keyword matching score
            score = 0.0
            text_content = f"{row['name']} {row['description'] or ''} {row['intent_key'] or ''}".lower()

            for term in query_terms:
                if term in text_content:
                    score += 0.2

            results.append(SearchResult(
                id=str(row['id']),
                title=row['name'],
                description=row['description'] or "",
                content={
                    'intent_key': row['intent_key'],
                    'sql_template': row['sql_template']
                },
                score=min(score, 1.0),
                source_table='sql_templates'
            ))

        return results

    # =============== METRICS ===============

    async def search_metrics(
        self,
        query: str,
        category: Optional[str] = None,
        top_k: int = 5,
        include_derived: bool = True
    ) -> List[SearchResult]:
        """Search metrics with synonym expansion"""

        # Check cache first
        if self.cache_service:
            cached_result = await self.cache_service.get(
                "metrics", query,
                category=category, top_k=top_k, include_derived=include_derived
            )
            if cached_result:
                return [SearchResult(**item) for item in cached_result]

        conn = await self._get_connection()
        try:
            results = []

            # Check synonyms first to expand query
            expanded_queries = await self._expand_query_with_synonyms(conn, query)

            # Search base metrics
            for search_query in expanded_queries:
                base_results = await self._search_base_metrics(conn, search_query, category, top_k)
                results.extend(base_results)

                # Search derived metrics if requested
                if include_derived:
                    derived_results = await self._search_derived_metrics(conn, search_query, category, top_k)
                    results.extend(derived_results)

            # Remove duplicates and sort by score
            seen_ids = set()
            unique_results = []
            for result in sorted(results, key=lambda x: x.score, reverse=True):
                if result.id not in seen_ids:
                    unique_results.append(result)
                    seen_ids.add(result.id)

            final_results = unique_results[:top_k]

            # Cache results
            if self.cache_service:
                cache_data = [result.__dict__ for result in final_results]
                await self.cache_service.set(
                    "metrics", query, cache_data,
                    category=category, top_k=top_k, include_derived=include_derived
                )

            return final_results

        finally:
            await self._release_connection(conn)

    async def _expand_query_with_synonyms(self, conn: asyncpg.Connection, query: str) -> List[str]:
        """Expand query using metric synonyms"""
        queries = [query]

        # Check if query matches any synonyms
        rows = await conn.fetch("""
            SELECT alias, target
            FROM metric_synonyms
            WHERE LOWER(alias) = LOWER($1)
        """, query)

        for row in rows:
            target = json.loads(row['target'])
            if isinstance(target, list):
                queries.extend(target)
            else:
                queries.append(target)

        return list(set(queries))  # Remove duplicates

    async def _search_base_metrics(
        self,
        conn: asyncpg.Connection,
        query: str,
        category: Optional[str],
        limit: int
    ) -> List[SearchResult]:
        """Search base metrics with vector and keyword matching"""
        results = []

        # Vector search
        embedding = await self._get_query_embedding(query)
        if embedding:
            vector_literal = self._to_pgvector_literal(embedding)

            filter_clause = ""
            params = [vector_literal, limit]

            if category:
                filter_clause = "WHERE category_id = $3"
                params.append(category)

            sql = f"""
                SELECT metric_id, name, description, database_name, aliases, category_id, unit, importance,
                       (embedding <=> $1::vector) AS distance
                FROM metrics
                {filter_clause}
                ORDER BY embedding <=> $1::vector ASC
                LIMIT $2
            """

            rows = await conn.fetch(sql, *params)
            for row in rows:
                results.append(SearchResult(
                    id=row['metric_id'],
                    title=row['name'],
                    description=row['description'] or "",
                    content={
                        'database_name': row['database_name'],
                        'aliases': row['aliases'],
                        'category_id': row['category_id'],
                        'unit': row['unit'],
                        'importance': row['importance']
                    },
                    score=1.0 - row['distance'],
                    distance=row['distance'],
                    source_table='metrics'
                ))

        return results

    async def _search_derived_metrics(
        self,
        conn: asyncpg.Connection,
        query: str,
        category: Optional[str],
        limit: int
    ) -> List[SearchResult]:
        """Search derived metrics"""
        results = []

        embedding = await self._get_query_embedding(query)
        if embedding:
            vector_literal = self._to_pgvector_literal(embedding)

            filter_clause = ""
            params = [vector_literal, limit]

            if category:
                filter_clause = "WHERE category_id = $3"
                params.append(category)

            sql = f"""
                SELECT metric_id, name, description, formula, dependencies, category_id, unit, importance,
                       (embedding <=> $1::vector) AS distance
                FROM derived_metrics
                {filter_clause}
                ORDER BY embedding <=> $1::vector ASC
                LIMIT $2
            """

            rows = await conn.fetch(sql, *params)
            for row in rows:
                results.append(SearchResult(
                    id=row['metric_id'],
                    title=row['name'],
                    description=row['description'] or "",
                    content={
                        'formula': row['formula'],
                        'dependencies': row['dependencies'],
                        'category_id': row['category_id'],
                        'unit': row['unit'],
                        'importance': row['importance']
                    },
                    score=1.0 - row['distance'],
                    distance=row['distance'],
                    source_table='derived_metrics'
                ))

        return results

    # =============== COMPANIES ===============

    async def search_companies(
        self,
        query: str,
        sector: Optional[str] = None,
        top_k: int = 5,
        include_aliases: bool = True
    ) -> List[SearchResult]:
        """Search companies with alias resolution"""

        # Check cache first
        if self.cache_service:
            cached_result = await self.cache_service.get(
                "companies", query,
                sector=sector, top_k=top_k, include_aliases=include_aliases
            )
            if cached_result:
                return [SearchResult(**item) for item in cached_result]

        conn = await self._get_connection()
        try:
            results = []

            # Direct company search
            embedding = await self._get_query_embedding(query)
            if embedding:
                vector_literal = self._to_pgvector_literal(embedding)

                filter_clause = ""
                params = [vector_literal, top_k]

                if sector:
                    filter_clause = "WHERE sector = $3"
                    params.append(sector)

                sql = f"""
                    SELECT ticker, name, short_name, sector, industry, description, market_cap_tier, priority,
                           (embedding <=> $1::vector) AS distance
                    FROM companies
                    {filter_clause}
                    ORDER BY embedding <=> $1::vector ASC
                    LIMIT $2
                """

                rows = await conn.fetch(sql, *params)
                for row in rows:
                    results.append(SearchResult(
                        id=row['ticker'],
                        title=row['name'],
                        description=row['description'] or "",
                        content={
                            'ticker': row['ticker'],
                            'short_name': row['short_name'],
                            'sector': row['sector'],
                            'industry': row['industry'],
                            'market_cap_tier': row['market_cap_tier'],
                            'priority': row['priority']
                        },
                        score=1.0 - row['distance'],
                        distance=row['distance'],
                        source_table='companies'
                    ))

            # Alias search if enabled
            if include_aliases:
                alias_results = await self._search_company_aliases(conn, query, sector, top_k)
                results.extend(alias_results)

            # Remove duplicates and sort
            seen_tickers = set()
            unique_results = []
            for result in sorted(results, key=lambda x: x.score, reverse=True):
                if result.id not in seen_tickers:
                    unique_results.append(result)
                    seen_tickers.add(result.id)

            final_results = unique_results[:top_k]

            # Cache results
            if self.cache_service:
                cache_data = [result.__dict__ for result in final_results]
                await self.cache_service.set(
                    "companies", query, cache_data,
                    sector=sector, top_k=top_k, include_aliases=include_aliases
                )

            return final_results

        finally:
            await self._release_connection(conn)

    async def _search_company_aliases(
        self,
        conn: asyncpg.Connection,
        query: str,
        sector: Optional[str],
        limit: int
    ) -> List[SearchResult]:
        """Search companies by aliases"""
        # Find companies matching aliases
        alias_filter = ""
        params = [f"%{query.lower()}%"]

        if sector:
            alias_filter = "AND c.sector = $2"
            params.append(sector)

        sql = f"""
            SELECT DISTINCT c.ticker, c.name, c.short_name, c.sector, c.industry, c.description, c.market_cap_tier, c.priority
            FROM company_aliases ca
            JOIN companies c ON ca.ticker = c.ticker
            WHERE LOWER(ca.alias) LIKE $1
            {alias_filter}
            ORDER BY c.priority ASC NULLS LAST, c.name
            LIMIT {limit}
        """

        rows = await conn.fetch(sql, *params)
        results = []

        for row in rows:
            # Score based on how well the alias matches
            score = 0.8 if query.lower() in row['name'].lower() else 0.6

            results.append(SearchResult(
                id=row['ticker'],
                title=row['name'],
                description=row['description'] or "",
                content={
                    'ticker': row['ticker'],
                    'short_name': row['short_name'],
                    'sector': row['sector'],
                    'industry': row['industry'],
                    'market_cap_tier': row['market_cap_tier'],
                    'priority': row['priority']
                },
                score=score,
                source_table='companies'
            ))

        return results

    # =============== CONTEXT-AWARE RETRIEVAL ===============

    async def get_analytics_context(self, context: SearchContext) -> Dict[str, Any]:
        """Get comprehensive analytics context for a query"""
        start_time = time.time()

        # Parallel retrieval of all relevant configs
        tasks = [
            self.search_templates(context.query, context.intent_key, top_k=3),
            self.search_metrics(context.query, context.category_filter, top_k=5),
            self.search_companies(context.query, top_k=3) if not context.company_filter else self._get_specific_company(context.company_filter),
        ]

        try:
            templates, metrics, companies = await asyncio.gather(*tasks, return_exceptions=True)

            # Handle any exceptions in the results
            if isinstance(templates, Exception):
                logger.error(f"Template search failed: {templates}")
                templates = []
            if isinstance(metrics, Exception):
                logger.error(f"Metrics search failed: {metrics}")
                metrics = []
            if isinstance(companies, Exception):
                logger.error(f"Companies search failed: {companies}")
                companies = []

            result = {
                'templates': [result.__dict__ for result in templates],
                'metrics': [result.__dict__ for result in metrics],
                'companies': [result.__dict__ for result in companies],
                'query_metadata': {
                    'query': context.query,
                    'intent_key': context.intent_key,
                    'filters_applied': {
                        'company': context.company_filter,
                        'category': context.category_filter,
                        'time_period': context.time_period,
                        'chart_type': context.chart_type
                    },
                    'retrieval_time_ms': round((time.time() - start_time) * 1000, 2)
                }
            }

            return result

        except Exception as e:
            logger.error(f"Failed to get analytics context: {e}")
            return {
                'templates': [],
                'metrics': [],
                'companies': [],
                'error': str(e)
            }

    async def _get_specific_company(self, ticker: str) -> List[SearchResult]:
        """Get specific company by ticker"""
        conn = await self._get_connection()
        try:
            row = await conn.fetchrow("""
                SELECT ticker, name, short_name, sector, industry, description, market_cap_tier, priority
                FROM companies
                WHERE ticker = $1
            """, ticker.upper())

            if row:
                return [SearchResult(
                    id=row['ticker'],
                    title=row['name'],
                    description=row['description'] or "",
                    content=dict(row),
                    score=1.0,
                    source_table='companies'
                )]
            return []

        finally:
            await self._release_connection(conn)


    # =============== TELEMETRY ===============

    async def get_search_stats(self) -> Dict[str, Any]:
        """Get search performance statistics"""
        conn = await self._get_connection()
        try:
            stats = {}

            # Count of different config types
            for table in ['sql_templates', 'metrics', 'derived_metrics', 'companies', 'chart_types']:
                count = await conn.fetchval(f"SELECT COUNT(*) FROM {table}")
                stats[f"{table}_count"] = count

            # Cache statistics
            if self.cache_service:
                cache_stats = await self.cache_service.get_stats()
                stats['cache_stats'] = cache_stats
                stats['cache_hit_ratio'] = cache_stats.get('redis_hit_ratio', 0.0)
            else:
                stats['cache_size'] = 0
                stats['cache_hit_ratio'] = 0.0

            return stats

        finally:
            await self._release_connection(conn)

    def _calculate_cache_hit_ratio(self) -> float:
        """Calculate cache hit ratio (simplified)"""
        # This is a simplified implementation
        # In production, you'd want to track actual hits/misses
        return 0.75 if self.cache_service else 0.0

    async def cleanup_cache(self) -> None:
        """Clean up expired cache entries"""
        if self.cache_service:
            await self.cache_service.cleanup_expired()

    async def close(self) -> None:
        """Close connection pool and cleanup resources"""
        if self.connection_pool:
            await self.connection_pool.close()


# Global RAG service instance
_rag_service = None


def get_rag_service() -> RAGService:
    """Get global RAG service instance"""
    global _rag_service
    if _rag_service is None:
        _rag_service = RAGService()
    return _rag_service


async def close_rag_service() -> None:
    """Close global RAG service"""
    global _rag_service
    if _rag_service:
        await _rag_service.close()
        _rag_service = None


if __name__ == "__main__":
    import asyncio

    async def test_rag_service():
        """Test the RAG service functionality"""
        from dotenv import load_dotenv
        load_dotenv()

        rag = get_rag_service()

        # Test template search
        print("=== Testing Template Search ===")
        templates = await rag.search_templates("market share analysis", top_k=2)
        for t in templates:
            print(f"Template: {t.title} (score: {t.score:.3f})")

        # Test metrics search
        print("\n=== Testing Metrics Search ===")
        metrics = await rag.search_metrics("revenue", top_k=3)
        for m in metrics:
            print(f"Metric: {m.title} (score: {m.score:.3f})")

        # Test companies search
        print("\n=== Testing Companies Search ===")
        companies = await rag.search_companies("nvidia", top_k=2)
        for c in companies:
            print(f"Company: {c.title} (score: {c.score:.3f})")

        # Test context retrieval
        print("\n=== Testing Context Retrieval ===")
        context = SearchContext(
            query="revenue growth analysis",
            intent_key="revenue_growth_analysis"
        )
        analytics_context = await rag.get_analytics_context(context)
        print(f"Context retrieval time: {analytics_context['query_metadata']['retrieval_time_ms']}ms")
        print(f"Found {len(analytics_context['templates'])} templates, {len(analytics_context['metrics'])} metrics, {len(analytics_context['companies'])} companies")

        # Test stats
        print("\n=== Service Statistics ===")
        stats = await rag.get_search_stats()
        for key, value in stats.items():
            print(f"{key}: {value}")

        await close_rag_service()

    asyncio.run(test_rag_service())