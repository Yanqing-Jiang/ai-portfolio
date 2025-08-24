"""Deterministic cache key generation."""
from __future__ import annotations

import hashlib
import json
import re
from typing import Dict


def normalize_sql_ast(sql: str) -> str:
    """Very small SQL normalizer.

    In production this would use `sqlglot` to perform AST-based normalization.
    Here we collapse whitespace for deterministic hashing.
    """
    return re.sub(r"\s+", " ", sql).strip()


def sql_key(sql: str, params: Dict[str, object], schema_fp: str, window: str) -> str:
    """Generate a deterministic cache key for SQL artifacts."""
    normalized_sql = normalize_sql_ast(sql)
    content = json.dumps(
        {
            "sql": normalized_sql,
            "params": sorted(params.items()),
            "schema_fp": schema_fp,
            "window": window,
        },
        sort_keys=True,
    )
    return hashlib.sha256(content.encode()).hexdigest()


__all__ = ["sql_key", "normalize_sql_ast"]
