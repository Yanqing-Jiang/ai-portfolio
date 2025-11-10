# --- Analytics Function/Class Map ---
# Class: AnalyticsRuntime
#   Role: Handles AnalyticsRuntime logic for analytics.core.context.
#   Called from: Internal to analytics.core.context
#   Collaborators: dataclasses.dataclass
#   Why: Keeps analytics.core.context from duplicating AnalyticsRuntime behavior across flows.
# Function: get_configs
#   Role: Return loaded configuration schemas.
#   Called from: analytics.core.config_store, analytics.flows.planner_executor, analytics.semantic.catalog, analytics.sql.compiler, +6 more
#   Invokes: Internal helpers only
#   Why: Supports downstream analytics workflows that rely on get_configs.
# Function: get_database_url
#   Role: Handles get database url logic for analytics.core.context.
#   Called from: Internal to analytics.core.context
#   Invokes: os.getenv
#   Why: Keeps analytics.core.context from duplicating get database url behavior across flows.
# Function: get_openai_api_key
#   Role: Handles get openai api key logic for analytics.core.context.
#   Called from: Internal to analytics.core.context
#   Invokes: os.getenv
#   Why: Keeps analytics.core.context from duplicating get openai api key behavior across flows.
# Function: get_runtime
#   Role: Handles get runtime logic for analytics.core.context.
#   Called from: Internal to analytics.core.context
#   Invokes: functools.lru_cache, os.getenv, analytics.core.context.AnalyticsRuntime, analytics.core.context.get_database_url, +1 more
#   Why: Keeps analytics.core.context from duplicating get runtime behavior across flows.
# --- End Analytics Function/Class Map ---
from __future__ import annotations
from dataclasses import dataclass
from functools import lru_cache
from typing import Dict, Optional
import os

from .config import Configs, CONFIGS

__all__ = ["AnalyticsRuntime", "get_runtime", "get_configs", "get_database_url", "get_openai_api_key"]


@dataclass(frozen=True)
class AnalyticsRuntime:
    configs: Configs
    database_url: Optional[str]
    openai_api_key: Optional[str]
    environment: str
    telemetry_enabled: bool
    extra: Dict[str, str]


def get_configs() -> Configs:
    """Return loaded configuration schemas."""
    return CONFIGS


def get_database_url() -> Optional[str]:
    return os.getenv("DATABASE_URL")


def get_openai_api_key() -> Optional[str]:
    return os.getenv("OPENAI_API_KEY")


@lru_cache(maxsize=1)
def get_runtime() -> AnalyticsRuntime:
    env = os.getenv("APP_ENV", "development")
    telemetry = os.getenv("ANALYTICS_TELEMETRY", "false").lower() == "true"
    extra = {
        "responses_reasoning_effort": os.getenv("SUPERVISOR_REASONING_EFFORT", "low"),
        "analytics_mode": os.getenv("ANALYTICS_MODE", "flow"),
        "delegation_policy_version": os.getenv("AGENTS_DELEGATION_POLICY_VERSION", "baseline"),
    }
    return AnalyticsRuntime(
        configs=CONFIGS,
        database_url=get_database_url(),
        openai_api_key=get_openai_api_key(),
        environment=env,
        telemetry_enabled=telemetry,
        extra=extra,
    )
