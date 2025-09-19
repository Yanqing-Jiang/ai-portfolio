#!/usr/bin/env python3
"""
Config Loaders for migrating YAML configurations to Supabase database.

This module provides comprehensive loaders for:
- metrics.yaml → metric_categories, metrics, derived_metrics, metric_synonyms
- companies.yaml → industries, companies, company_aliases, peer_groups
- charts.yaml → chart_* tables
- database.yaml → table_schemas, table_columns

All loaders support:
- Vector embeddings for semantic search
- Upsert operations with conflict resolution
- Relationship management between entities
- Comprehensive error handling and logging
"""

from __future__ import annotations
from typing import Any, Dict, List, Optional, Union
from pathlib import Path
import os
import uuid
import json
import asyncpg
import yaml
import logging
from datetime import datetime

import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from unified_responses_client import get_unified_client

logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv("DATABASE_URL")


def _get_unified_client():
    """Get unified client for embeddings"""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return None
    return get_unified_client()


def _to_pgvector_literal(vec: List[float]) -> str:
    """Convert vector to pgvector literal format"""
    return "[" + ",".join(f"{x:.8f}" for x in vec) + "]"


async def _ensure_vector_extension(conn: asyncpg.Connection) -> None:
    """Ensure pgvector extension is enabled"""
    try:
        await conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
    except Exception:
        # Supabase usually has it enabled; ignore failures
        pass


class ConfigLoaderError(Exception):
    """Custom exception for config loading errors"""
    pass


class MetricsLoader:
    """Loader for metrics.yaml configuration"""

    @staticmethod
    async def create_schema(conn: asyncpg.Connection) -> None:
        """Create metric-related database tables"""
        await _ensure_vector_extension(conn)

        # Metric categories table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS metric_categories (
                category_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT,
                derived BOOLEAN DEFAULT FALSE,
                embedding vector(1536),
                created_at TIMESTAMPTZ DEFAULT NOW(),
                updated_at TIMESTAMPTZ DEFAULT NOW()
            )
        """)

        # Base metrics table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS metrics (
                metric_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                database_name TEXT,
                aliases TEXT[] DEFAULT '{}',
                category_id TEXT REFERENCES metric_categories(category_id),
                unit TEXT,
                aggregation TEXT,
                description TEXT,
                format TEXT,
                importance TEXT,
                metadata JSONB DEFAULT '{}'::jsonb,
                embedding vector(1536),
                created_at TIMESTAMPTZ DEFAULT NOW(),
                updated_at TIMESTAMPTZ DEFAULT NOW()
            )
        """)

        # Derived metrics table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS derived_metrics (
                metric_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                formula TEXT NOT NULL,
                dependencies TEXT[] NOT NULL,
                unit TEXT,
                description TEXT,
                format TEXT,
                category_id TEXT REFERENCES metric_categories(category_id),
                importance TEXT,
                metadata JSONB DEFAULT '{}'::jsonb,
                embedding vector(1536),
                created_at TIMESTAMPTZ DEFAULT NOW(),
                updated_at TIMESTAMPTZ DEFAULT NOW()
            )
        """)

        # Metric synonyms table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS metric_synonyms (
                alias TEXT PRIMARY KEY,
                target JSONB NOT NULL,
                created_at TIMESTAMPTZ DEFAULT NOW()
            )
        """)

        # Create indexes
        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_metrics_category ON metrics(category_id)",
            "CREATE INDEX IF NOT EXISTS idx_metrics_aliases_gin ON metrics USING GIN(aliases)",
            "CREATE INDEX IF NOT EXISTS idx_metrics_embedding_hnsw ON metrics USING hnsw (embedding vector_cosine_ops) WITH (m=16, ef_construction=64)",
            "CREATE INDEX IF NOT EXISTS idx_derived_metrics_deps_gin ON derived_metrics USING GIN(dependencies)",
            "CREATE INDEX IF NOT EXISTS idx_derived_metrics_embedding_hnsw ON derived_metrics USING hnsw (embedding vector_cosine_ops) WITH (m=16, ef_construction=64)",
            "CREATE INDEX IF NOT EXISTS idx_metric_categories_embedding_hnsw ON metric_categories USING hnsw (embedding vector_cosine_ops) WITH (m=16, ef_construction=64)"
        ]

        for index_sql in indexes:
            try:
                await conn.execute(index_sql)
            except Exception as e:
                logger.warning(f"Failed to create index: {e}")

    @staticmethod
    async def load_from_yaml(yaml_path: str, overwrite: bool = False) -> Dict[str, int]:
        """Load metrics from YAML file into database"""
        if not DATABASE_URL:
            raise ConfigLoaderError("DATABASE_URL not set")

        # Load YAML data
        with open(yaml_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f) or {}

        unified_client = _get_unified_client()
        if not unified_client:
            raise ConfigLoaderError("OpenAI API key required for embeddings")

        conn = await asyncpg.connect(DATABASE_URL, statement_cache_size=0, timeout=10.0)
        try:
            await MetricsLoader.create_schema(conn)

            stats = {"categories": 0, "metrics": 0, "derived_metrics": 0, "synonyms": 0}

            # Load categories
            categories = config.get("categories", {})
            for cat_id, cat_data in categories.items():
                embed_text = f"category:{cat_id}\nname:{cat_data.get('name', '')}\ndesc:{cat_data.get('description', '')}"
                embedding = unified_client.create_embeddings_sync([embed_text])[0]

                await conn.execute("""
                    INSERT INTO metric_categories (category_id, name, description, derived, embedding)
                    VALUES ($1, $2, $3, $4, $5::vector)
                    ON CONFLICT (category_id) DO UPDATE SET
                        name = EXCLUDED.name,
                        description = EXCLUDED.description,
                        derived = EXCLUDED.derived,
                        embedding = EXCLUDED.embedding,
                        updated_at = NOW()
                """, cat_id, cat_data.get('name'), cat_data.get('description'),
                    cat_data.get('derived', False), _to_pgvector_literal(embedding))
                stats["categories"] += 1

            # Load base metrics
            metrics = config.get("metrics", {})
            for metric_id, metric_data in metrics.items():
                aliases = metric_data.get('aliases', [])
                embed_text = f"metric:{metric_id}\nname:{metric_data.get('name', '')}\ndesc:{metric_data.get('description', '')}\naliases:{','.join(aliases)}"
                embedding = unified_client.create_embeddings_sync([embed_text])[0]

                await conn.execute("""
                    INSERT INTO metrics (metric_id, name, database_name, aliases, category_id, unit, aggregation, description, format, importance, embedding)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11::vector)
                    ON CONFLICT (metric_id) DO UPDATE SET
                        name = EXCLUDED.name,
                        database_name = EXCLUDED.database_name,
                        aliases = EXCLUDED.aliases,
                        category_id = EXCLUDED.category_id,
                        unit = EXCLUDED.unit,
                        aggregation = EXCLUDED.aggregation,
                        description = EXCLUDED.description,
                        format = EXCLUDED.format,
                        importance = EXCLUDED.importance,
                        embedding = EXCLUDED.embedding,
                        updated_at = NOW()
                """, metric_id, metric_data.get('name'), metric_data.get('database_name'),
                    aliases, metric_data.get('category'), metric_data.get('unit'),
                    metric_data.get('aggregation'), metric_data.get('description'),
                    metric_data.get('format'), metric_data.get('importance'),
                    _to_pgvector_literal(embedding))
                stats["metrics"] += 1

            # Load derived metrics
            derived_metrics = config.get("derived_metrics", {})
            for metric_id, metric_data in derived_metrics.items():
                embed_text = f"derived:{metric_id}\nname:{metric_data.get('name', '')}\nformula:{metric_data.get('formula', '')}\ndesc:{metric_data.get('description', '')}"
                embedding = unified_client.create_embeddings_sync([embed_text])[0]

                await conn.execute("""
                    INSERT INTO derived_metrics (metric_id, name, formula, dependencies, unit, description, format, category_id, importance, embedding)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10::vector)
                    ON CONFLICT (metric_id) DO UPDATE SET
                        name = EXCLUDED.name,
                        formula = EXCLUDED.formula,
                        dependencies = EXCLUDED.dependencies,
                        unit = EXCLUDED.unit,
                        description = EXCLUDED.description,
                        format = EXCLUDED.format,
                        category_id = EXCLUDED.category_id,
                        importance = EXCLUDED.importance,
                        embedding = EXCLUDED.embedding,
                        updated_at = NOW()
                """, metric_id, metric_data.get('name'), metric_data.get('formula'),
                    metric_data.get('dependencies', []), metric_data.get('unit'),
                    metric_data.get('description'), metric_data.get('format'),
                    metric_data.get('category'), metric_data.get('importance'),
                    _to_pgvector_literal(embedding))
                stats["derived_metrics"] += 1

            # Load synonyms
            synonyms = config.get("synonyms", {})
            for alias, target in synonyms.items():
                # Convert target to JSONB format
                if isinstance(target, list):
                    target_json = json.dumps(target)
                else:
                    target_json = json.dumps([target])

                await conn.execute("""
                    INSERT INTO metric_synonyms (alias, target)
                    VALUES ($1, $2::jsonb)
                    ON CONFLICT (alias) DO UPDATE SET
                        target = EXCLUDED.target
                """, alias, target_json)
                stats["synonyms"] += 1

            return stats

        finally:
            await conn.close()


class CompaniesLoader:
    """Loader for companies.yaml configuration"""

    @staticmethod
    async def create_schema(conn: asyncpg.Connection) -> None:
        """Create company-related database tables"""
        await _ensure_vector_extension(conn)

        # Industries table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS industries (
                industry_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT,
                embedding vector(1536),
                created_at TIMESTAMPTZ DEFAULT NOW(),
                updated_at TIMESTAMPTZ DEFAULT NOW()
            )
        """)

        # Companies table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS companies (
                ticker TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                short_name TEXT,
                sector TEXT,
                industry TEXT,
                description TEXT,
                market_cap_tier TEXT,
                default_selection BOOLEAN DEFAULT FALSE,
                priority INTEGER,
                metadata JSONB DEFAULT '{}'::jsonb,
                embedding vector(1536),
                created_at TIMESTAMPTZ DEFAULT NOW(),
                updated_at TIMESTAMPTZ DEFAULT NOW()
            )
        """)

        # Company aliases table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS company_aliases (
                ticker TEXT REFERENCES companies(ticker) ON DELETE CASCADE,
                alias TEXT NOT NULL,
                PRIMARY KEY (ticker, alias)
            )
        """)

        # Peer groups table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS peer_groups (
                group_id TEXT PRIMARY KEY,
                tickers TEXT[] NOT NULL,
                description TEXT,
                created_at TIMESTAMPTZ DEFAULT NOW(),
                updated_at TIMESTAMPTZ DEFAULT NOW()
            )
        """)

        # Company display colors table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS company_display_colors (
                ticker TEXT PRIMARY KEY REFERENCES companies(ticker) ON DELETE CASCADE,
                hex_color TEXT NOT NULL
            )
        """)

        # Company selection rules table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS company_selection_rules (
                rule_id TEXT PRIMARY KEY,
                tickers TEXT[] NOT NULL,
                reason TEXT,
                created_at TIMESTAMPTZ DEFAULT NOW()
            )
        """)

        # Create indexes
        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_companies_sector ON companies(sector)",
            "CREATE INDEX IF NOT EXISTS idx_companies_industry ON companies(industry)",
            "CREATE INDEX IF NOT EXISTS idx_companies_embedding_hnsw ON companies USING hnsw (embedding vector_cosine_ops) WITH (m=16, ef_construction=64)",
            "CREATE INDEX IF NOT EXISTS idx_industries_embedding_hnsw ON industries USING hnsw (embedding vector_cosine_ops) WITH (m=16, ef_construction=64)",
            "CREATE INDEX IF NOT EXISTS idx_peer_groups_tickers_gin ON peer_groups USING GIN(tickers)"
        ]

        for index_sql in indexes:
            try:
                await conn.execute(index_sql)
            except Exception as e:
                logger.warning(f"Failed to create index: {e}")

    @staticmethod
    async def load_from_yaml(yaml_path: str, overwrite: bool = False) -> Dict[str, int]:
        """Load companies from YAML file into database"""
        if not DATABASE_URL:
            raise ConfigLoaderError("DATABASE_URL not set")

        with open(yaml_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f) or {}

        unified_client = _get_unified_client()
        if not unified_client:
            raise ConfigLoaderError("OpenAI API key required for embeddings")

        conn = await asyncpg.connect(DATABASE_URL, statement_cache_size=0, timeout=10.0)
        try:
            await CompaniesLoader.create_schema(conn)

            stats = {"industries": 0, "companies": 0, "aliases": 0, "peer_groups": 0, "colors": 0, "rules": 0}

            # Load industries
            industries = config.get("industries", {})
            for industry_id, industry_data in industries.items():
                embed_text = f"industry:{industry_id}\nname:{industry_data.get('name', '')}\ndesc:{industry_data.get('description', '')}"
                embedding = unified_client.create_embeddings_sync([embed_text])[0]

                await conn.execute("""
                    INSERT INTO industries (industry_id, name, description, embedding)
                    VALUES ($1, $2, $3, $4::vector)
                    ON CONFLICT (industry_id) DO UPDATE SET
                        name = EXCLUDED.name,
                        description = EXCLUDED.description,
                        embedding = EXCLUDED.embedding,
                        updated_at = NOW()
                """, industry_id, industry_data.get('name'), industry_data.get('description'),
                    _to_pgvector_literal(embedding))
                stats["industries"] += 1

            # Load companies (nested structure: companies.industry[list])
            companies = config.get("companies", {})
            for industry_category, company_list in companies.items():
                if isinstance(company_list, list):
                    for company_data in company_list:
                        ticker = company_data.get('ticker')
                        if not ticker:
                            continue

                        embed_text = f"company:{ticker}\nname:{company_data.get('name', '')}\nshort:{company_data.get('short_name', '')}\nsector:{company_data.get('sector', '')}\nindustry:{company_data.get('industry', '')}\ndesc:{company_data.get('description', '')}"
                        embedding = unified_client.create_embeddings_sync([embed_text])[0]

                        await conn.execute("""
                            INSERT INTO companies (ticker, name, short_name, sector, industry, description, market_cap_tier, default_selection, priority, embedding)
                            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10::vector)
                            ON CONFLICT (ticker) DO UPDATE SET
                                name = EXCLUDED.name,
                                short_name = EXCLUDED.short_name,
                                sector = EXCLUDED.sector,
                                industry = EXCLUDED.industry,
                                description = EXCLUDED.description,
                                market_cap_tier = EXCLUDED.market_cap_tier,
                                default_selection = EXCLUDED.default_selection,
                                priority = EXCLUDED.priority,
                                embedding = EXCLUDED.embedding,
                                updated_at = NOW()
                        """, ticker, company_data.get('name'), company_data.get('short_name'),
                            company_data.get('sector'), company_data.get('industry'),
                            company_data.get('description'), company_data.get('market_cap_tier'),
                            company_data.get('default_selection', False), company_data.get('priority'),
                            _to_pgvector_literal(embedding))
                        stats["companies"] += 1

                        # Load aliases for this company
                        aliases = company_data.get('aliases', [])
                        for alias in aliases:
                            await conn.execute("""
                                INSERT INTO company_aliases (ticker, alias)
                                VALUES ($1, $2)
                                ON CONFLICT (ticker, alias) DO NOTHING
                            """, ticker, alias)
                            stats["aliases"] += 1

            # Load peer groups
            peer_groups = config.get("peer_groups", {})
            for group_id, group_data in peer_groups.items():
                await conn.execute("""
                    INSERT INTO peer_groups (group_id, tickers, description)
                    VALUES ($1, $2, $3)
                    ON CONFLICT (group_id) DO UPDATE SET
                        tickers = EXCLUDED.tickers,
                        description = EXCLUDED.description,
                        updated_at = NOW()
                """, group_id, group_data.get('tickers', []), group_data.get('description'))
                stats["peer_groups"] += 1

            # Load display colors
            colors = config.get("display_colors", {})
            for ticker, color in colors.items():
                await conn.execute("""
                    INSERT INTO company_display_colors (ticker, hex_color)
                    VALUES ($1, $2)
                    ON CONFLICT (ticker) DO UPDATE SET
                        hex_color = EXCLUDED.hex_color
                """, ticker, color)
                stats["colors"] += 1

            # Load selection rules
            selection_rules = config.get("default_companies", {})
            for rule_id, rule_data in selection_rules.items():
                await conn.execute("""
                    INSERT INTO company_selection_rules (rule_id, tickers, reason)
                    VALUES ($1, $2, $3)
                    ON CONFLICT (rule_id) DO UPDATE SET
                        tickers = EXCLUDED.tickers,
                        reason = EXCLUDED.reason
                """, rule_id, rule_data.get('tickers', []), rule_data.get('reason'))
                stats["rules"] += 1

            return stats

        finally:
            await conn.close()


class ChartsLoader:
    """Loader for charts.yaml configuration"""

    @staticmethod
    async def create_schema(conn: asyncpg.Connection) -> None:
        """Create chart-related database tables"""
        await _ensure_vector_extension(conn)

        # Chart themes table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS chart_themes (
                theme_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT,
                colors JSONB NOT NULL,
                chart_colors JSONB,
                created_at TIMESTAMPTZ DEFAULT NOW(),
                updated_at TIMESTAMPTZ DEFAULT NOW()
            )
        """)

        # Chart types table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS chart_types (
                type_id TEXT PRIMARY KEY,
                echarts_type TEXT NOT NULL,
                name TEXT,
                description TEXT,
                default_options JSONB DEFAULT '{}'::jsonb,
                embedding vector(1536),
                created_at TIMESTAMPTZ DEFAULT NOW(),
                updated_at TIMESTAMPTZ DEFAULT NOW()
            )
        """)

        # Chart layouts table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS chart_layouts (
                layout_id TEXT PRIMARY KEY,
                layout JSONB NOT NULL,
                created_at TIMESTAMPTZ DEFAULT NOW(),
                updated_at TIMESTAMPTZ DEFAULT NOW()
            )
        """)

        # Chart formatting table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS chart_formatting (
                format_id TEXT PRIMARY KEY,
                category TEXT NOT NULL,
                axis_formatter TEXT,
                tooltip_formatter TEXT,
                created_at TIMESTAMPTZ DEFAULT NOW(),
                updated_at TIMESTAMPTZ DEFAULT NOW()
            )
        """)

        # Chart title patterns table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS chart_title_patterns (
                pattern_group TEXT,
                pattern_key TEXT,
                template TEXT NOT NULL,
                created_at TIMESTAMPTZ DEFAULT NOW(),
                updated_at TIMESTAMPTZ DEFAULT NOW(),
                PRIMARY KEY (pattern_group, pattern_key)
            )
        """)

        # Chart animations table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS chart_animations (
                animation_id TEXT PRIMARY KEY,
                settings JSONB NOT NULL,
                created_at TIMESTAMPTZ DEFAULT NOW(),
                updated_at TIMESTAMPTZ DEFAULT NOW()
            )
        """)

        # Chart interactivity table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS chart_interactivity (
                feature_id TEXT PRIMARY KEY,
                settings JSONB NOT NULL,
                created_at TIMESTAMPTZ DEFAULT NOW(),
                updated_at TIMESTAMPTZ DEFAULT NOW()
            )
        """)

        # Create indexes
        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_chart_types_embedding_hnsw ON chart_types USING hnsw (embedding vector_cosine_ops) WITH (m=16, ef_construction=64)",
            "CREATE INDEX IF NOT EXISTS idx_chart_formatting_category ON chart_formatting(category)"
        ]

        for index_sql in indexes:
            try:
                await conn.execute(index_sql)
            except Exception as e:
                logger.warning(f"Failed to create index: {e}")

    @staticmethod
    async def load_from_yaml(yaml_path: str, overwrite: bool = False) -> Dict[str, int]:
        """Load charts config from YAML file into database"""
        if not DATABASE_URL:
            raise ConfigLoaderError("DATABASE_URL not set")

        with open(yaml_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f) or {}

        unified_client = _get_unified_client()
        if not unified_client:
            raise ConfigLoaderError("OpenAI API key required for embeddings")

        conn = await asyncpg.connect(DATABASE_URL, statement_cache_size=0, timeout=10.0)
        try:
            await ChartsLoader.create_schema(conn)

            stats = {"themes": 0, "chart_types": 0, "layouts": 0, "formatting": 0, "title_patterns": 0, "animations": 0, "interactivity": 0}

            # Load themes
            themes = config.get("themes", {})
            for theme_id, theme_data in themes.items():
                await conn.execute("""
                    INSERT INTO chart_themes (theme_id, name, description, colors, chart_colors)
                    VALUES ($1, $2, $3, $4::jsonb, $5::jsonb)
                    ON CONFLICT (theme_id) DO UPDATE SET
                        name = EXCLUDED.name,
                        description = EXCLUDED.description,
                        colors = EXCLUDED.colors,
                        chart_colors = EXCLUDED.chart_colors,
                        updated_at = NOW()
                """, theme_id, theme_data.get('name'), theme_data.get('description'),
                    json.dumps(theme_data.get('colors', {})),
                    json.dumps(theme_data.get('chart_colors', {})))
                stats["themes"] += 1

            # Load chart types
            chart_types = config.get("chart_types", {})
            for type_id, type_data in chart_types.items():
                embed_text = f"chart_type:{type_id}\nname:{type_data.get('name', '')}\ndesc:{type_data.get('description', '')}\ntype:{type_data.get('type', '')}"
                embedding = unified_client.create_embeddings_sync([embed_text])[0]

                await conn.execute("""
                    INSERT INTO chart_types (type_id, echarts_type, name, description, default_options, embedding)
                    VALUES ($1, $2, $3, $4, $5::jsonb, $6::vector)
                    ON CONFLICT (type_id) DO UPDATE SET
                        echarts_type = EXCLUDED.echarts_type,
                        name = EXCLUDED.name,
                        description = EXCLUDED.description,
                        default_options = EXCLUDED.default_options,
                        embedding = EXCLUDED.embedding,
                        updated_at = NOW()
                """, type_id, type_data.get('type'), type_data.get('name'),
                    type_data.get('description'), json.dumps(type_data.get('default_options', {})),
                    _to_pgvector_literal(embedding))
                stats["chart_types"] += 1

            # Load formatting rules
            formatting = config.get("formatting", {})
            for category, format_rules in formatting.items():
                for format_id, format_data in format_rules.items():
                    await conn.execute("""
                        INSERT INTO chart_formatting (format_id, category, axis_formatter, tooltip_formatter)
                        VALUES ($1, $2, $3, $4)
                        ON CONFLICT (format_id) DO UPDATE SET
                            category = EXCLUDED.category,
                            axis_formatter = EXCLUDED.axis_formatter,
                            tooltip_formatter = EXCLUDED.tooltip_formatter,
                            updated_at = NOW()
                    """, f"{category}_{format_id}", category,
                        format_data.get('axis_formatter'), format_data.get('tooltip_formatter'))
                    stats["formatting"] += 1

            # Load title patterns
            title_patterns = config.get("title_patterns", {})
            for pattern_group, patterns in title_patterns.items():
                for pattern_key, template in patterns.items():
                    await conn.execute("""
                        INSERT INTO chart_title_patterns (pattern_group, pattern_key, template)
                        VALUES ($1, $2, $3)
                        ON CONFLICT (pattern_group, pattern_key) DO UPDATE SET
                            template = EXCLUDED.template,
                            updated_at = NOW()
                    """, pattern_group, pattern_key, template)
                    stats["title_patterns"] += 1

            return stats

        finally:
            await conn.close()


class DatabaseLoader:
    """Loader for database.yaml configuration"""

    @staticmethod
    async def create_schema(conn: asyncpg.Connection) -> None:
        """Create database schema configuration tables"""
        await _ensure_vector_extension(conn)

        # Table schemas table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS table_schemas (
                table_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT,
                table_type TEXT,
                value_column TEXT,
                entity_column TEXT,
                metric_column TEXT,
                time_columns JSONB,
                metadata JSONB DEFAULT '{}'::jsonb,
                embedding vector(1536),
                created_at TIMESTAMPTZ DEFAULT NOW(),
                updated_at TIMESTAMPTZ DEFAULT NOW()
            )
        """)

        # Table columns table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS table_columns (
                table_id TEXT REFERENCES table_schemas(table_id) ON DELETE CASCADE,
                column_name TEXT NOT NULL,
                data_type TEXT,
                description TEXT,
                required BOOLEAN DEFAULT FALSE,
                nullable BOOLEAN DEFAULT TRUE,
                indexed BOOLEAN DEFAULT FALSE,
                metadata JSONB DEFAULT '{}'::jsonb,
                PRIMARY KEY (table_id, column_name)
            )
        """)

        # Table indexes table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS table_indexes (
                table_id TEXT REFERENCES table_schemas(table_id) ON DELETE CASCADE,
                index_name TEXT NOT NULL,
                columns TEXT[] NOT NULL,
                index_type TEXT,
                PRIMARY KEY (table_id, index_name)
            )
        """)

        # Query defaults table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS query_defaults (
                id SMALLINT PRIMARY KEY DEFAULT 1,
                defaults JSONB NOT NULL,
                data_validation JSONB,
                aggregation JSONB,
                created_at TIMESTAMPTZ DEFAULT NOW(),
                updated_at TIMESTAMPTZ DEFAULT NOW()
            )
        """)

        # Create indexes
        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_table_schemas_embedding_hnsw ON table_schemas USING hnsw (embedding vector_cosine_ops) WITH (m=16, ef_construction=64)",
            "CREATE INDEX IF NOT EXISTS idx_table_columns_data_type ON table_columns(data_type)"
        ]

        for index_sql in indexes:
            try:
                await conn.execute(index_sql)
            except Exception as e:
                logger.warning(f"Failed to create index: {e}")

    @staticmethod
    async def load_from_yaml(yaml_path: str, overwrite: bool = False) -> Dict[str, int]:
        """Load database config from YAML file into database"""
        if not DATABASE_URL:
            raise ConfigLoaderError("DATABASE_URL not set")

        with open(yaml_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f) or {}

        unified_client = _get_unified_client()
        if not unified_client:
            raise ConfigLoaderError("OpenAI API key required for embeddings")

        conn = await asyncpg.connect(DATABASE_URL, statement_cache_size=0, timeout=10.0)
        try:
            await DatabaseLoader.create_schema(conn)

            stats = {"tables": 0, "columns": 0, "indexes": 0, "query_defaults": 0}

            # Load table schemas
            tables = config.get("tables", {})
            for table_id, table_data in tables.items():
                embed_text = f"table:{table_id}\nname:{table_data.get('name', '')}\ndesc:{table_data.get('description', '')}\ntype:{table_data.get('type', '')}"
                embedding = unified_client.create_embeddings_sync([embed_text])[0]

                await conn.execute("""
                    INSERT INTO table_schemas (table_id, name, description, table_type, value_column, entity_column, metric_column, time_columns, embedding)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8::jsonb, $9::vector)
                    ON CONFLICT (table_id) DO UPDATE SET
                        name = EXCLUDED.name,
                        description = EXCLUDED.description,
                        table_type = EXCLUDED.table_type,
                        value_column = EXCLUDED.value_column,
                        entity_column = EXCLUDED.entity_column,
                        metric_column = EXCLUDED.metric_column,
                        time_columns = EXCLUDED.time_columns,
                        embedding = EXCLUDED.embedding,
                        updated_at = NOW()
                """, table_id, table_data.get('name'), table_data.get('description'),
                    table_data.get('type'), table_data.get('value_column'),
                    table_data.get('entity_column'), table_data.get('metric_column'),
                    json.dumps(table_data.get('time_columns', {})), _to_pgvector_literal(embedding))
                stats["tables"] += 1

                # Load columns for this table
                columns = table_data.get('columns', [])
                for column_data in columns:
                    await conn.execute("""
                        INSERT INTO table_columns (table_id, column_name, data_type, description, required, nullable, indexed)
                        VALUES ($1, $2, $3, $4, $5, $6, $7)
                        ON CONFLICT (table_id, column_name) DO UPDATE SET
                            data_type = EXCLUDED.data_type,
                            description = EXCLUDED.description,
                            required = EXCLUDED.required,
                            nullable = EXCLUDED.nullable,
                            indexed = EXCLUDED.indexed
                    """, table_id, column_data.get('name'), column_data.get('type'),
                        column_data.get('description'), column_data.get('required', False),
                        column_data.get('nullable', True), column_data.get('indexed', False))
                    stats["columns"] += 1

                # Load indexes for this table
                indexes = table_data.get('indexes', [])
                for index_data in indexes:
                    await conn.execute("""
                        INSERT INTO table_indexes (table_id, index_name, columns, index_type)
                        VALUES ($1, $2, $3, $4)
                        ON CONFLICT (table_id, index_name) DO UPDATE SET
                            columns = EXCLUDED.columns,
                            index_type = EXCLUDED.index_type
                    """, table_id, index_data.get('name'), index_data.get('columns', []),
                        index_data.get('type'))
                    stats["indexes"] += 1

            # Load query defaults
            query_defaults = config.get("query_defaults", {})
            if query_defaults:
                await conn.execute("""
                    INSERT INTO query_defaults (id, defaults, data_validation, aggregation)
                    VALUES (1, $1::jsonb, $2::jsonb, $3::jsonb)
                    ON CONFLICT (id) DO UPDATE SET
                        defaults = EXCLUDED.defaults,
                        data_validation = EXCLUDED.data_validation,
                        aggregation = EXCLUDED.aggregation,
                        updated_at = NOW()
                """, json.dumps(query_defaults.get('defaults', {})),
                    json.dumps(query_defaults.get('data_validation', {})),
                    json.dumps(query_defaults.get('aggregation', {})))
                stats["query_defaults"] += 1

            return stats

        finally:
            await conn.close()


# Unified interface
async def load_all_configs(overwrite: bool = False) -> Dict[str, Dict[str, int]]:
    """Load all YAML configs into database tables"""
    schemas_dir = Path(__file__).resolve().parents[1] / "config" / "schemas"

    results = {}

    # Load metrics
    metrics_path = schemas_dir / "metrics.yaml"
    if metrics_path.exists():
        results["metrics"] = await MetricsLoader.load_from_yaml(str(metrics_path), overwrite)
        logger.info(f"Loaded metrics: {results['metrics']}")

    # Load companies
    companies_path = schemas_dir / "companies.yaml"
    if companies_path.exists():
        results["companies"] = await CompaniesLoader.load_from_yaml(str(companies_path), overwrite)
        logger.info(f"Loaded companies: {results['companies']}")

    # Load charts
    charts_path = schemas_dir / "charts.yaml"
    if charts_path.exists():
        results["charts"] = await ChartsLoader.load_from_yaml(str(charts_path), overwrite)
        logger.info(f"Loaded charts: {results['charts']}")

    # Load database schemas
    database_path = schemas_dir / "database.yaml"
    if database_path.exists():
        results["database"] = await DatabaseLoader.load_from_yaml(str(database_path), overwrite)
        logger.info(f"Loaded database: {results['database']}")

    return results


if __name__ == "__main__":
    import asyncio
    logging.basicConfig(level=logging.INFO)

    async def main():
        try:
            results = await load_all_configs(overwrite=True)
            print("Config loading completed:")
            for config_name, stats in results.items():
                print(f"  {config_name}: {stats}")
        except Exception as e:
            print(f"Error: {e}")

    asyncio.run(main())