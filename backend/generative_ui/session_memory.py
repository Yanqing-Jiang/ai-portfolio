# --- Session Memory Function/Class Map ---
# Function: _session_key — build Redis key for per-session explanation memory.
#   Called from: load_explanation_memory, store_explanation_memory.
#   Invokes: n/a.
#   Why: Centralizes key structure for session memory storage.
# Function: load_explanation_memory — fetch cached explanation payload from Redis.
#   Called from: backend.generative_ui.routes.dashboard.stream_dashboard, backend.generative_ui.runtime.A2UIRuntime.stream_dashboard.
#   Invokes: redis_pool.get, json.loads.
#   Why: Allows cached replay to skip re-animating streamed explanations.
# Function: store_explanation_memory — persist explanation payload to Redis.
#   Called from: backend.generative_ui.runtime.A2UIRuntime.stream_dashboard.
#   Invokes: redis_pool.setex, json.dumps.
#   Why: Stores streamed explanation content for fast replay.
# --- End Session Memory Function/Class Map ---
"""
Session memory storage for streamed explanation content.

Provides lightweight Redis-backed storage for explanation text + metadata
so cached replays can skip re-animating streaming text.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

try:
    from rate_limiter import redis_pool
except ImportError:  # pragma: no cover - support module execution
    from ..rate_limiter import redis_pool  # type: ignore

logger = logging.getLogger(__name__)

SESSION_TTL_SECONDS = 6 * 60 * 60


def _session_key(session_id: str, dashboard_id: str) -> str:
    """
    Build a Redis key for explanation session memory.
    
    Function: _session_key — session key builder for explanation memory.
    Called from: load_explanation_memory, store_explanation_memory.
    Invokes: n/a.
    Why: Keeps key format consistent across read/write paths.
    """
    return f"a2ui:session:{session_id}:dashboard:{dashboard_id}:explanation"


async def load_explanation_memory(
    session_id: str,
    dashboard_id: str,
) -> Optional[Dict[str, Any]]:
    """
    Load cached explanation payload for a dashboard session.
    
    Function: load_explanation_memory — read explanation payload from Redis.
    Called from: backend.generative_ui.routes.dashboard.stream_dashboard,
                backend.generative_ui.runtime.A2UIRuntime.stream_dashboard.
    Invokes: redis_pool.get, json.loads.
    Why: Skips streaming replay when cached explanation exists.
    """
    if not session_id or not dashboard_id or redis_pool is None:
        return None

    key = _session_key(session_id, dashboard_id)
    try:
        payload = await redis_pool.get(key)
        if not payload:
            return None
        return json.loads(payload)
    except Exception as exc:
        logger.warning("[SESSION] Failed to load explanation memory: %s", exc)
        return None


async def store_explanation_memory(
    session_id: str,
    dashboard_id: str,
    explanation: Dict[str, Any],
) -> bool:
    """
    Store explanation payload for a dashboard session.
    
    Function: store_explanation_memory — persist explanation payload in Redis.
    Called from: backend.generative_ui.runtime.A2UIRuntime.stream_dashboard.
    Invokes: redis_pool.setex, json.dumps.
    Why: Enables cached replays to skip streaming animations.
    """
    if not session_id or not dashboard_id or redis_pool is None:
        return False

    key = _session_key(session_id, dashboard_id)
    payload = dict(explanation)
    payload.setdefault("cached_at", datetime.now(timezone.utc).isoformat())

    try:
        await redis_pool.setex(
            key,
            SESSION_TTL_SECONDS,
            json.dumps(payload, default=str),
        )
        return True
    except Exception as exc:
        logger.warning("[SESSION] Failed to store explanation memory: %s", exc)
        return False
