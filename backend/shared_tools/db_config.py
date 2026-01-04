"""
Shared database configuration.

Function: DatabaseConfig — provides database connection settings.
Called from: shared_tools.sql_executor
Invokes: os.getenv for DATABASE_URL.
Purpose: Isolate DB config so it can be used by both projects without circular imports.
"""
from __future__ import annotations

import os
from functools import lru_cache
from dataclasses import dataclass


@dataclass(frozen=True)
class DatabaseConfig:
    """Configuration for database connections."""
    database_url: str


@lru_cache(maxsize=1)
def get_db_config() -> DatabaseConfig:
    """
    Function: get_db_config — returns cached database configuration.
    Called from: sql_executor.execute_sql
    Invokes: os.getenv
    Purpose: Single source of truth for database connection string.
    """
    url = os.getenv("DATABASE_URL", "")
    return DatabaseConfig(database_url=url)
