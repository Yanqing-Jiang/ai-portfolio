from __future__ import annotations
from typing import Any, Dict, List, Optional

import os
import uuid
import json
import asyncpg

from langchain_openai import OpenAIEmbeddings


DATABASE_URL = os.getenv("DATABASE_URL")


async def _ensure_schema(conn: asyncpg.Connection) -> None:
    """Ensure pgvector extension and sql_templates table/indexes exist."""
    # Enable pgvector
    try:
        await conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
    except Exception:
        # Supabase usually has it enabled; ignore failures
        pass

    # Table
    await conn.execute(
        """
        CREATE TABLE IF NOT EXISTS sql_templates (
            id UUID PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT,
            intent_key TEXT,
            sql_template TEXT NOT NULL,
            parameters JSONB DEFAULT '{}'::jsonb,
            tags TEXT[] DEFAULT '{}',
            example_utterances TEXT[] DEFAULT '{}',
            embedding vector(1536),
            created_at TIMESTAMPTZ DEFAULT NOW()
        )
        """
    )

    # Indexes
    await conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_sql_templates_intent
        ON sql_templates(intent_key)
        """
    )
    await conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_sql_templates_tags
        ON sql_templates USING GIN(tags)
        """
    )

    # Vector index (cosine). Requires pgvector >= 0.5.0
    try:
        await conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_sql_templates_embedding
            ON sql_templates USING ivfflat (embedding vector_cosine_ops)
            WITH (lists = 100)
            """
        )
    except Exception:
        # Index creation may fail if permissions differ; continue without it
        pass


def _get_embeddings() -> Optional[OpenAIEmbeddings]:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return None
    # text-embedding-3-small: 1536 dims, cost-effective
    return OpenAIEmbeddings(model="text-embedding-3-small", api_key=api_key)


def _to_pgvector_literal(vec: List[float]) -> str:
    # pgvector accepts a string literal like '[0.1,0.2,...]'::vector
    return "[" + ",".join(f"{x:.8f}" for x in vec) + "]"


async def search_templates(query: str, intent_key: Optional[str] = None, top_k: int = 3) -> List[Dict[str, Any]]:
    """Vector search over sql_templates using pgvector cosine distance.

    Returns rows ordered by ascending distance (lower is closer).
    """
    if not DATABASE_URL:
        return []

    embedder = _get_embeddings()
    if not embedder:
        return []

    # Compute query embedding (sync API; run in thread not necessary for short calls)
    q_emb = embedder.embed_query(query)
    q_vec = _to_pgvector_literal(q_emb)

    conn = await asyncpg.connect(DATABASE_URL, statement_cache_size=0, timeout=10.0, command_timeout=20.0)
    try:
        await _ensure_schema(conn)

        params: List[Any] = [q_vec, top_k]
        filter_sql = ""
        if intent_key:
            filter_sql = "WHERE intent_key = $3"
            params.append(intent_key)

        sql = f"""
            SELECT id, name, intent_key, description, sql_template,
                   (embedding <=> $1::vector) AS distance
            FROM sql_templates
            {filter_sql}
            ORDER BY embedding <=> $1::vector ASC
            LIMIT $2
        """
        rows = await conn.fetch(sql, *params)
        return [dict(r) for r in rows]
    finally:
        await conn.close()


async def seed_from_queries_yaml(path: str, overwrite: bool = False) -> int:
    """Seed sql_templates from queries.yaml config.

    Reads query_patterns.* entries and inserts RAG candidates with embeddings.
    Returns the number of rows upserted.
    """
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL not set for seeding sql_templates")

    try:
        import yaml  # type: ignore
    except Exception as e:
        raise RuntimeError("Missing dependency 'pyyaml'. Add it to backend/requirements.txt and install.") from e

    with open(path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f) or {}

    patterns: Dict[str, Any] = (config.get("query_patterns") or {})
    if not patterns:
        return 0

    embedder = _get_embeddings()
    if not embedder:
        raise RuntimeError("OPENAI_API_KEY is required to embed templates for seeding")

    conn = await asyncpg.connect(DATABASE_URL, statement_cache_size=0, timeout=10.0, command_timeout=20.0)
    try:
        await _ensure_schema(conn)

        total = 0
        for intent_key, body in patterns.items():
            name = body.get("name", intent_key)
            description = body.get("description", "")
            sql_template = body.get("sql_template", "")
            tags = body.get("keywords", []) or []
            example_utterances: List[str] = []

            # Build an embedding text block
            embed_text = "\n".join([
                f"intent:{intent_key}",
                f"name:{name}",
                f"desc:{description}",
                f"tags:{','.join(tags)}",
            ])
            emb = embedder.embed_query(embed_text)

            tpl_id = uuid.uuid5(uuid.NAMESPACE_URL, f"{intent_key}:{name}")
            vec = _to_pgvector_literal(emb)

            if overwrite:
                await conn.execute(
                    """
                    INSERT INTO sql_templates (id, name, description, intent_key, sql_template, parameters, tags, example_utterances, embedding)
                    VALUES ($1, $2, $3, $4, $5, '{}'::jsonb, $6, $7, $8::vector)
                    ON CONFLICT (id) DO UPDATE SET
                        name = EXCLUDED.name,
                        description = EXCLUDED.description,
                        intent_key = EXCLUDED.intent_key,
                        sql_template = EXCLUDED.sql_template,
                        tags = EXCLUDED.tags,
                        example_utterances = EXCLUDED.example_utterances,
                        embedding = EXCLUDED.embedding
                    """,
                    str(tpl_id), name, description, intent_key, sql_template, tags, example_utterances, vec
                )
            else:
                await conn.execute(
                    """
                    INSERT INTO sql_templates (id, name, description, intent_key, sql_template, parameters, tags, example_utterances, embedding)
                    VALUES ($1, $2, $3, $4, $5, '{}'::jsonb, $6, $7, $8::vector)
                    ON CONFLICT (id) DO NOTHING
                    """,
                    str(tpl_id), name, description, intent_key, sql_template, tags, example_utterances, vec
                )

            total += 1

        return total
    finally:
        await conn.close()

