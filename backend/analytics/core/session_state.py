from __future__ import annotations

import logging
import time
import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from copy import deepcopy

from pydantic import BaseModel, Field, field_validator

try:
    import redis.asyncio as redis  # type: ignore
except ImportError:  # pragma: no cover - redis optional in some test envs
    redis = None

logger = logging.getLogger(__name__)

__all__ = [
    "SessionStateSnapshot",
    "SessionStateRepository",
    "get_session_state_repository",
    "close_session_state_repository",
]


DEFAULT_TTL_MINUTES = 30
MIN_TTL_MINUTES = 1
MAX_TTL_MINUTES = 60
MAX_ARTIFACT_HISTORY = 5


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
    schedule_history: List[Dict[str, Any]] = Field(default_factory=list)

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

    def record_tool_receipt(self, tool: str, payload: Dict[str, Any]) -> None:
        receipts = self.tool_cache.setdefault("tool_receipts", {})
        receipts[tool] = deepcopy(payload)
        self.touch()

    def get_tool_receipt(self, tool: str) -> Optional[Dict[str, Any]]:
        receipts = self.tool_cache.get("tool_receipts") or {}
        receipt = receipts.get(tool)
        return deepcopy(receipt) if receipt is not None else None

    def record_revision_snapshot(self, payload: Dict[str, Any]) -> None:
        analytics_cache = self.tool_cache.setdefault("analytics", {})
        analytics_cache["revision_snapshot"] = payload
        self.touch()

    def record_artifacts(self, artifacts: Dict[str, Any]) -> None:
        analytics_cache = self.tool_cache.setdefault("analytics", {})
        history = analytics_cache.setdefault("artifacts_history", [])
        version = int(analytics_cache.get("artifact_version", 0)) + 1
        history.append(
            {
                "version": version,
                "recorded_at": datetime.now(timezone.utc).isoformat(),
                "artifacts": artifacts,
            }
        )
        if len(history) > MAX_ARTIFACT_HISTORY:
            analytics_cache["artifacts_history"] = history[-MAX_ARTIFACT_HISTORY:]
        analytics_cache["artifacts"] = artifacts
        analytics_cache["artifact_version"] = version
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

    def record_schedule_stage(
        self,
        *,
        stage: Optional[str],
        parallel_group: Optional[str],
        event: Optional[str] = None,
        ts: Optional[str] = None,
        flow_mode: Optional[str] = None,
    ) -> None:
        if not stage:
            return
        entry = {
            "stage": stage,
            "parallel_group": parallel_group,
            "event": event,
            "ts": ts,
            "flow_mode": flow_mode,
        }
        history = self.schedule_history
        history.append(entry)
        if len(history) > 50:
            self.schedule_history = history[-50:]
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
    """Session state storage with Redis and in-memory fallback."""

    def __init__(
        self,
        redis_client: Optional["redis.Redis"] = None,
        *,
        ttl_minutes: Optional[int] = None,
        redis_url: Optional[str] = None,
    ) -> None:
        self._redis_url = redis_url or os.getenv("REDIS_URL", "redis://localhost:6379/0")
        self._redis_retry_backoff = 30.0
        self._last_failure_ts = 0.0
        self._fallback_store: Dict[str, Tuple[float, str]] = {}

        ttl_env = ttl_minutes or _read_ttl_from_env()
        self._ttl_seconds = max(MIN_TTL_MINUTES, min(MAX_TTL_MINUTES, ttl_env)) * 60

        if redis_client is not None:
            self._redis = redis_client
        elif redis is None:
            self._redis = None
            logger.info(
                "Redis client unavailable for session state storage; using in-memory fallback."
            )
        else:
            try:
                self._redis = redis.from_url(  # type: ignore[call-arg]
                    self._redis_url,
                    encoding="utf-8",
                    decode_responses=True,
                    socket_timeout=0.5,
                    socket_connect_timeout=0.5,
                    health_check_interval=30,
                )
            except Exception as exc:  # pragma: no cover - network failure
                logger.warning(
                    "Failed to configure Redis client for session state: %s",
                    exc,
                )
                self._redis = None
                self._record_failure()

    @property
    def ttl_seconds(self) -> int:
        return self._ttl_seconds

    async def load(self, session_id: str) -> Optional[SessionStateSnapshot]:
        self._cleanup_fallback()
        key = self._key(session_id)

        payload: Optional[str] = None
        client = await self._ensure_redis()
        if client:
            try:
                payload = await client.get(key)
            except Exception as exc:  # pragma: no cover - network failure
                logger.warning("Redis load failed for %s: %s", session_id, exc)
                self._record_failure()

        if not payload:
            payload = self._fallback_get(key)
            if not payload:
                return None
        else:
            self._fallback_set(key, payload)

        try:
            data = json.loads(payload)
            return SessionStateSnapshot(**data)
        except Exception as exc:  # pragma: no cover - defensive logging
            raise ValueError(
                f"Failed to deserialize session state for {session_id}: {exc}"
            ) from exc

    async def save(self, snapshot: SessionStateSnapshot) -> SessionStateSnapshot:
        snapshot.touch()
        serialized = json.dumps(snapshot.snapshot(), default=str)
        key = self._key(snapshot.session_id)

        client = await self._ensure_redis()
        if client:
            try:
                await client.setex(key, self._ttl_seconds, serialized)
            except Exception as exc:  # pragma: no cover - network failure
                logger.warning("Redis save failed for %s: %s", snapshot.session_id, exc)
                self._record_failure()

        self._fallback_set(key, serialized)
        return snapshot

    async def delete(self, session_id: str) -> None:
        key = self._key(session_id)
        client = await self._ensure_redis()
        if client:
            try:
                await client.delete(key)
            except Exception as exc:  # pragma: no cover - network failure
                logger.warning("Redis delete failed for %s: %s", session_id, exc)
                self._record_failure()
        self._fallback_delete(key)

    async def touch(self, session_id: str) -> None:
        key = self._key(session_id)
        client = await self._ensure_redis()
        if client:
            try:
                await client.expire(key, self._ttl_seconds)
                return
            except Exception as exc:  # pragma: no cover - network failure
                logger.warning("Redis touch failed for %s: %s", session_id, exc)
                self._record_failure()
        self._fallback_touch(key)

    async def close(self) -> None:
        if self._redis:
            try:
                await self._redis.close()
            except Exception:  # pragma: no cover - defensive close
                pass
            self._redis = None

    async def _ensure_redis(self) -> Optional["redis.Redis"]:
        if redis is None:
            return None
        if self._redis is None:
            if time.time() - self._last_failure_ts < self._redis_retry_backoff:
                return None
            try:
                client = redis.from_url(  # type: ignore[call-arg]
                    self._redis_url,
                    encoding="utf-8",
                    decode_responses=True,
                    socket_timeout=0.5,
                    socket_connect_timeout=0.5,
                    health_check_interval=30,
                )
                await client.ping()
                self._redis = client
                logger.info("Session state Redis connection established")
            except Exception as exc:  # pragma: no cover - network failure
                logger.warning("Session state Redis connection failed: %s", exc)
                self._record_failure()
                return None
        return self._redis

    def _record_failure(self) -> None:
        self._redis = None
        self._last_failure_ts = time.time()

    def _cleanup_fallback(self) -> None:
        now = time.time()
        expired = [
            key
            for key, (expires_at, _) in self._fallback_store.items()
            if expires_at <= now
        ]
        for key in expired:
            self._fallback_store.pop(key, None)

    def _fallback_get(self, key: str) -> Optional[str]:
        entry = self._fallback_store.get(key)
        if not entry:
            return None
        expires_at, payload = entry
        if expires_at <= time.time():
            self._fallback_store.pop(key, None)
            return None
        return payload

    def _fallback_set(self, key: str, payload: str) -> None:
        self._cleanup_fallback()
        self._fallback_store[key] = (time.time() + self._ttl_seconds, payload)

    def _fallback_touch(self, key: str) -> None:
        entry = self._fallback_store.get(key)
        if entry:
            _, payload = entry
            self._fallback_store[key] = (time.time() + self._ttl_seconds, payload)

    def _fallback_delete(self, key: str) -> None:
        self._fallback_store.pop(key, None)

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
