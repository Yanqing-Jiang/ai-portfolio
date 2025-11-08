from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Dict, Iterable, Mapping, Optional

from analytics.core.session_state import SessionStateSnapshot

LANE_TTL_DEFAULTS: Dict[str, int] = {
    "analysis": 300,
    "web": 120,
    "chart": 600,
    "market": 300,
}

LANE_TTL_ENV_KEYS: Dict[str, str] = {
    "analysis": "ANALYTICS_ANALYSIS_REFRESH_TTL_SECONDS",
    "web": "ANALYTICS_WEB_REFRESH_TTL_SECONDS",
    "chart": "ANALYTICS_CHART_REFRESH_TTL_SECONDS",
    "market": "ANALYTICS_MARKET_REFRESH_TTL_SECONDS",
}


def normalize_lane_name(lane: Optional[str]) -> Optional[str]:
    if lane is None:
        return None
    normalized = str(lane).strip().lower()
    return normalized or None


def resolve_lane_ttls() -> Dict[str, int]:
    resolved: Dict[str, int] = {}
    for lane, default in LANE_TTL_DEFAULTS.items():
        env_key = LANE_TTL_ENV_KEYS.get(lane)
        ttl = default
        if env_key:
            raw_value = os.getenv(env_key)
            if raw_value:
                try:
                    ttl = int(raw_value)
                except ValueError:
                    ttl = default
        if ttl < 0:
            ttl = 0
        resolved[lane] = ttl
    return resolved


def compute_lane_refresh_requirements(
    snapshot: Optional[SessionStateSnapshot],
    lanes: Iterable[str],
    ttl_map: Mapping[str, int],
    *,
    now: Optional[datetime] = None,
) -> Dict[str, bool]:
    requirements: Dict[str, bool] = {}
    now_dt = now or datetime.now(timezone.utc)
    for lane in lanes:
        normalized = normalize_lane_name(lane)
        if not normalized:
            continue
        ttl = int(ttl_map.get(normalized, 0))
        if snapshot is None:
            requirements[normalized] = True
            continue
        age = snapshot.lane_age_seconds(normalized, now=now_dt)
        if age is None:
            requirements[normalized] = True
            continue
        if ttl <= 0:
            requirements[normalized] = True
            continue
        requirements[normalized] = age > ttl
    return requirements
