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
        "supervisor_beta_enabled": os.getenv("ANALYTICS_SUPERVISOR_BETA_ENABLED", "false").lower() in {"1", "true", "yes", "on"},
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
