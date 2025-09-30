from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator

try:
    import redis.asyncio as redis  # type: ignore
except ImportError:  # pragma: no cover - redis optional in some test envs
    redis = None

__all__ = [
    "SessionStateSnapshot",
    "SessionStateRepository",
    "get_session_state_repository",
    "close_session_state_repository",
]


DEFAULT_TTL_MINUTES = 5
MIN_TTL_MINUTES = 1
MAX_TTL_MINUTES = 15


class SessionStateSnapshot(BaseModel):
    """Representation of analytics session state persisted in Redis."""

    session_id: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    last_query: Optional[str] = None
    last_intent_key: Optional[str] = None
    last_sql: Optional[str] = None
    last_chart_spec: Optional[Dict[str, Any]] = None
    last_analysis: Optional[str] = None
    tool_cache: Dict[str, Any] = Field(default_factory=dict)
    routing: Dict[str, Any] = Field(default_factory=dict)
    messages: List[Dict[str, Any]] = Field(default_factory=list)

    model_config = {
        "extra": "allow",
        "json_encoders": {datetime: lambda dt: dt.astimezone(timezone.utc).isoformat()},
    }

    def touch(self) -> None:
        """Refresh the updated_at marker."""
        self.updated_at = datetime.now(timezone.utc)

    def record_query(self, query: str, intent_key: Optional[str]) -> None:
        self.last_query = query
        self.last_intent_key = intent_key
        self.touch()

    def record_tool_result(self, tool: str, payload: Dict[str, Any]) -> None:
        self.tool_cache[tool] = payload
        self.touch()

    def record_outputs(
        self,
        *,
        sql: Optional[str] = None,
        chart_spec: Optional[Dict[str, Any]] = None,
        analysis: Optional[str] = None,
    ) -> None:
        if sql is not None:
            self.last_sql = sql
        if chart_spec is not None:
            self.last_chart_spec = chart_spec
        if analysis is not None:
            self.last_analysis = analysis
        self.touch()

    def should_trigger_web_refresh(self, new_query: str) -> bool:
        """Simple heuristic to determine if web context should refresh."""
        if not self.last_query:
            return True
        if new_query.strip().lower() == self.last_query.strip().lower():
            return False
        similarity = _string_similarity(new_query, self.last_query)
        return similarity < 0.7

    def snapshot(self) -> Dict[str, Any]:
        """Return serialized representation suitable for persistence."""
        data = self.model_dump()
        # Convert datetimes to ISO strings for Redis storage
        data["created_at"] = self.created_at.astimezone(timezone.utc).isoformat()
        data["updated_at"] = self.updated_at.astimezone(timezone.utc).isoformat()
        return data

    @field_validator("created_at", "updated_at", mode="before")
    def _parse_datetime(cls, value: Any) -> datetime:
        if isinstance(value, datetime):
            return value.astimezone(timezone.utc)
        if isinstance(value, str):
            parsed = datetime.fromisoformat(value)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(timezone.utc)
        raise ValueError("Invalid datetime payload for SessionStateSnapshot")


class SessionStateRepository:
    """Redis-backed repository for analytics session state."""

    def __init__(
        self,
        redis_client: Optional["redis.Redis"] = None,
        *,
        ttl_minutes: Optional[int] = None,
        redis_url: Optional[str] = None,
    ) -> None:
        if redis is None and redis_client is None:
            raise RuntimeError(
                "redis asyncio client not available; install redis package to persist session state"
            )
        if redis_client is None:
            redis_url = redis_url or os.getenv("REDIS_URL", "redis://localhost:6379/0")
            redis_client = redis.from_url(  # type: ignore[call-arg]
                redis_url,
                encoding="utf-8",
                decode_responses=True,
                socket_timeout=5.0,
                socket_connect_timeout=5.0,
                health_check_interval=30,
            )
        self._redis = redis_client

        ttl_env = ttl_minutes or _read_ttl_from_env()
        self._ttl_seconds = max(MIN_TTL_MINUTES, min(MAX_TTL_MINUTES, ttl_env)) * 60

    @property
    def ttl_seconds(self) -> int:
        return self._ttl_seconds

    async def load(self, session_id: str) -> Optional[SessionStateSnapshot]:
        payload = await self._redis.get(self._key(session_id))
        if not payload:
            return None
        try:
            data = json.loads(payload)
            return SessionStateSnapshot(**data)
        except Exception as exc:  # pragma: no cover - defensive logging
            raise ValueError(f"Failed to deserialize session state for {session_id}: {exc}") from exc

    async def save(self, snapshot: SessionStateSnapshot) -> SessionStateSnapshot:
        snapshot.touch()
        serialized = json.dumps(snapshot.snapshot(), default=str)
        await self._redis.setex(self._key(snapshot.session_id), self._ttl_seconds, serialized)
        return snapshot

    async def delete(self, session_id: str) -> None:
        await self._redis.delete(self._key(session_id))

    async def touch(self, session_id: str) -> None:
        await self._redis.expire(self._key(session_id), self._ttl_seconds)

    async def close(self) -> None:
        await self._redis.close()

    def _key(self, session_id: str) -> str:
        return f"analytics:session:{session_id}"


_repository: Optional[SessionStateRepository] = None


def get_session_state_repository() -> SessionStateRepository:
    global _repository
    if _repository is None:
        _repository = SessionStateRepository()
    return _repository


async def close_session_state_repository() -> None:
    global _repository
    if _repository is not None:
        await _repository.close()
        _repository = None


def _read_ttl_from_env() -> int:
    raw = os.getenv("ANALYTICS_SESSION_TTL_MINUTES")
    if not raw:
        return DEFAULT_TTL_MINUTES
    try:
        value = int(raw)
    except ValueError:
        return DEFAULT_TTL_MINUTES
    return value


def _string_similarity(a: str, b: str) -> float:
    try:
        from difflib import SequenceMatcher

        return SequenceMatcher(None, a.lower(), b.lower()).ratio()
    except Exception:  # pragma: no cover - extremely rare
        return 0.0
