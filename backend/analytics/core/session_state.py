from __future__ import annotations

import hashlib
import logging
import time
import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Mapping, Optional, Tuple, TYPE_CHECKING
from copy import deepcopy

from pydantic import BaseModel, Field, field_validator

from analytics.validators import sanitize_for_json

try:
    import redis.asyncio as redis  # type: ignore
except ImportError:  # pragma: no cover - redis optional in some test envs
    redis = None

logger = logging.getLogger(__name__)

if TYPE_CHECKING:  # pragma: no cover - typing only
    from analytics.flows.revision_directive import RevisionDirective

__all__ = [
    "SessionStateSnapshot",
    "SessionStateRepository",
    "get_session_state_repository",
    "close_session_state_repository",
    "SnapshotRevisionContext",
]


DEFAULT_TTL_MINUTES = 10
MIN_TTL_MINUTES = 1
MAX_TTL_MINUTES = 60
MAX_ARTIFACT_HISTORY = 5

TOOL_LANE_HINTS: Dict[str, str] = {
    "web_retriever": "web",
    "market_question_a": "market",
    "market_question_b": "market",
    "stock_tracker": "market",
}


def _hash_arguments(payload: Any) -> str:
    try:
        serialized = json.dumps(payload, sort_keys=True, default=str)
    except TypeError:
        serialized = repr(payload)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()[:16]


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
    last_revision_directive: Optional[Dict[str, Any]] = None
    tool_cache: Dict[str, Any] = Field(default_factory=dict)
    routing: Dict[str, Any] = Field(default_factory=dict)
    messages: List[Dict[str, Any]] = Field(default_factory=list)
    schedule_history: List[Dict[str, Any]] = Field(default_factory=list)
    lane_timestamps: Dict[str, datetime] = Field(default_factory=dict)
    agents_run_id: Optional[str] = None
    agents_trace_id: Optional[str] = None
    agents_manager_trace_id: Optional[str] = None
    agents_model: Optional[str] = None
    agents_tool_attempts: Dict[str, int] = Field(default_factory=dict)
    agents_retry_counts: Dict[str, int] = Field(default_factory=dict)
    agents_tool_receipts: Dict[str, Any] = Field(default_factory=dict)
    agents_recorded_at: Optional[str] = None
    agents_parallel_groups: Dict[str, Any] = Field(default_factory=dict)
    agents_delegation_policy_version: Optional[str] = None
    agents_delegation_decisions: List[Dict[str, Any]] = Field(default_factory=list)

    model_config = {
        "extra": "allow",
        "json_encoders": {datetime: lambda dt: dt.astimezone(timezone.utc).isoformat()},
    }

    def touch(self) -> None:
        """Refresh the updated_at marker."""
        self.updated_at = datetime.now(timezone.utc)

    def touch_lane(self, lane: str, *, at: Optional[datetime] = None) -> None:
        """Record the last-updated timestamp for a revision lane."""
        if not lane:
            return
        normalized = lane.strip().lower()
        if not normalized:
            return
        timestamp = at or datetime.now(timezone.utc)
        self.lane_timestamps[normalized] = timestamp
        self.touch()

    def get_lane_timestamp(self, lane: str) -> Optional[datetime]:
        if not lane:
            return None
        normalized = lane.strip().lower()
        if not normalized:
            return None
        timestamp = self.lane_timestamps.get(normalized)
        if timestamp is None:
            return None
        if isinstance(timestamp, datetime):
            return timestamp
        if isinstance(timestamp, str):
            try:
                return datetime.fromisoformat(timestamp)
            except ValueError:
                return None
        return None

    def lane_age_seconds(self, lane: str, *, now: Optional[datetime] = None) -> Optional[float]:
        timestamp = self.get_lane_timestamp(lane)
        if timestamp is None:
            return None
        now_dt = now or datetime.now(timezone.utc)
        delta = now_dt - timestamp
        try:
            return max(delta.total_seconds(), 0.0)
        except Exception:
            return None

    def record_query(self, query: str, intent_key: Optional[str]) -> None:
        self.last_query = query
        self.last_intent_key = intent_key
        self.touch()

    def record_revision_directive(
        self, directive: Optional["RevisionDirective"], *, metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        if directive is None:
            self.last_revision_directive = None
            self.touch()
            return

        payload = directive.to_dict()
        payload["recorded_at"] = datetime.now(timezone.utc).isoformat()
        if metadata:
            payload.update({key: value for key, value in metadata.items() if value is not None})
        self.last_revision_directive = payload
        self.touch()

    def record_tool_result(self, tool: str, payload: Dict[str, Any]) -> None:
        self.tool_cache[tool] = payload
        self.touch()

    def record_tool_receipt(self, tool: str, payload: Dict[str, Any]) -> None:
        receipts = self.tool_cache.setdefault("tool_receipts", {})
        enhanced = deepcopy(payload)
        enhanced.setdefault("tool", tool)
        enhanced.setdefault("recorded_at", datetime.now(timezone.utc).isoformat())
        if "arguments_hash" not in enhanced and "arguments" in enhanced:
            enhanced["arguments_hash"] = _hash_arguments(enhanced.get("arguments"))
        if "attempts" not in enhanced and "attempt" in enhanced:
            try:
                enhanced["attempts"] = int(enhanced.get("attempt", 0))
            except (TypeError, ValueError):
                enhanced["attempts"] = 0
        normalized_tool = _normalize_tool_name(enhanced.get("tool"))
        lane = (enhanced.get("lane") or "").strip().lower()
        source_lane = lane
        if not source_lane and normalized_tool:
            source_lane = TOOL_LANE_HINTS.get(normalized_tool)
        if source_lane:
            enhanced.setdefault("source_lane", source_lane)
        if lane:
            reuse_metadata = self._lane_reuse_metadata(lane)
            if reuse_metadata:
                enhanced.setdefault("reuse_metadata", reuse_metadata)
                if enhanced.get("reused_at_ms") is None:
                    fast_path_latency = reuse_metadata.get("fast_path_latency_ms")
                    if isinstance(fast_path_latency, (int, float)):
                        enhanced["reused_at_ms"] = int(fast_path_latency)
        if enhanced.get("latency_ms") is None:
            latency_candidate = enhanced.get("elapsed_ms")
            if latency_candidate is None:
                latency_candidate = enhanced.get("fast_path_latency_ms")
            try:
                if latency_candidate is not None:
                    enhanced["latency_ms"] = int(latency_candidate)
            except (TypeError, ValueError):
                pass
        if enhanced.get("reused_at_ms") is None:
            fast_path_latency = enhanced.get("fast_path_latency_ms")
            try:
                if fast_path_latency is not None:
                    enhanced["reused_at_ms"] = int(fast_path_latency)
            except (TypeError, ValueError):
                pass
        receipts[tool] = enhanced
        self.touch()

    def record_lane_reuse(
        self,
        lane: str,
        metadata: Mapping[str, Any],
    ) -> None:
        normalized = str(lane or "").strip().lower()
        if not normalized:
            return
        cache = self.tool_cache.setdefault("lane_reuse", {})
        cache[normalized] = sanitize_for_json(dict(metadata))
        self.touch_lane(normalized)

    def _lane_reuse_metadata(self, lane: str) -> Optional[Dict[str, Any]]:
        cache = self.tool_cache.get("lane_reuse") or {}
        normalized = str(lane or "").strip().lower()
        if not normalized:
            return None
        payload = cache.get(normalized)
        if isinstance(payload, Mapping):
            return sanitize_for_json(dict(payload))
        return None

    def get_lane_reuse_metadata(self, lane: str) -> Optional[Dict[str, Any]]:
        metadata = self._lane_reuse_metadata(lane)
        if metadata:
            return sanitize_for_json(dict(metadata))
        return None

    def record_lane_fast_path_marker(self, marker: str, *, at: Optional[datetime] = None) -> None:
        key = str(marker or "").strip()
        if not key:
            return
        cache = self.tool_cache.setdefault("lane_fast_path", {})
        timestamp = (at or datetime.now(timezone.utc)).astimezone(timezone.utc).isoformat()
        cache[key] = timestamp
        self.touch()

    def lane_fast_path_latency_ms(self, marker: str, *, now: Optional[datetime] = None) -> Optional[int]:
        cache = self.tool_cache.get("lane_fast_path") or {}
        timestamp = cache.get(str(marker or ""))
        if not timestamp:
            return None
        try:
            start = datetime.fromisoformat(timestamp)
        except ValueError:
            return None
        end = now or datetime.now(timezone.utc)
        delta = end - start
        try:
            return max(int(delta.total_seconds() * 1000), 0)
        except Exception:
            return None

    def record_agent_reasoning(
        self,
        key: str,
        summary: str,
        *,
        lane: Optional[str] = None,
        metadata: Optional[Mapping[str, Any]] = None,
    ) -> None:
        normalized_key = str(key or "").strip()
        normalized_summary = str(summary or "").strip()
        if not normalized_key or not normalized_summary:
            return
        reasoning_cache = self.tool_cache.setdefault("agent_reasoning", {})
        payload: Dict[str, Any] = {
            "summary": normalized_summary,
            "ts": datetime.now(timezone.utc).isoformat(),
        }
        normalized_lane = str(lane or "").strip().lower()
        if normalized_lane:
            payload["lane"] = normalized_lane
        if metadata:
            try:
                payload["metadata"] = sanitize_for_json(dict(metadata))
            except Exception:
                payload["metadata"] = json.loads(json.dumps(metadata, default=str))
        reasoning_cache[normalized_key] = payload
        self.touch()

    def record_agent_run(
        self,
        *,
        run_id: Optional[str],
        trace_id: Optional[str],
        manager_trace_id: Optional[str] = None,
        model: Optional[str],
        tool_attempts: Dict[str, int],
        retry_counts: Dict[str, int],
        receipts: Dict[str, Any],
        parallel_groups: Optional[Dict[str, Any]] = None,
        delegation_policy_version: Optional[str] = None,
        decisions: Optional[Iterable[Dict[str, Any]]] = None,
    ) -> None:
        agent_cache = self.tool_cache.setdefault("agent", {})
        previous_run_id = agent_cache.get("last_run_id")
        if run_id:
            normalized_run_id = str(run_id)
            agent_cache["last_run_id"] = normalized_run_id
            self.agents_run_id = normalized_run_id
        if trace_id:
            normalized_trace_id = str(trace_id)
            agent_cache["trace_id"] = normalized_trace_id
            self.agents_trace_id = normalized_trace_id
        if manager_trace_id:
            normalized_manager_trace_id = str(manager_trace_id)
            agent_cache["manager_trace_id"] = normalized_manager_trace_id
            self.agents_manager_trace_id = normalized_manager_trace_id
        elif previous_run_id and self.agents_run_id and self.agents_run_id != previous_run_id:
            agent_cache.pop("manager_trace_id", None)
            self.agents_manager_trace_id = None
        if model:
            normalized_model = str(model)
            agent_cache["model"] = normalized_model
            self.agents_model = normalized_model
        if previous_run_id and self.agents_run_id and self.agents_run_id != previous_run_id:
            agent_cache.pop("tool_attempts", None)
            agent_cache.pop("retry_counts", None)
            agent_cache.pop("receipts", None)
            self.agents_tool_attempts = {}
            self.agents_retry_counts = {}
            self.agents_tool_receipts = {}
        recorded_at = datetime.now(timezone.utc).isoformat()
        agent_cache["recorded_at"] = recorded_at
        self.agents_recorded_at = recorded_at
        if tool_attempts:
            attempts_payload = {
                str(key): int(value)
                for key, value in tool_attempts.items()
                if key is not None
            }
            agent_cache["tool_attempts"] = attempts_payload
            self.agents_tool_attempts = dict(attempts_payload)
        else:
            agent_cache.pop("tool_attempts", None)
            self.agents_tool_attempts = {}
        if retry_counts:
            retry_payload = {
                str(key): int(value)
                for key, value in retry_counts.items()
                if key is not None
            }
            agent_cache["retry_counts"] = retry_payload
            self.agents_retry_counts = dict(retry_payload)
        else:
            agent_cache.pop("retry_counts", None)
            self.agents_retry_counts = {}
        if receipts:
            try:
                sanitized_receipts = sanitize_for_json(receipts)
            except Exception:
                sanitized_receipts = json.loads(json.dumps(receipts, default=str))
            if not isinstance(sanitized_receipts, dict):
                sanitized_receipts = {"receipt": sanitized_receipts}
            agent_cache["receipts"] = sanitized_receipts
            self.agents_tool_receipts = dict(sanitized_receipts)
        else:
            agent_cache.pop("receipts", None)
            self.agents_tool_receipts = {}
        if parallel_groups:
            try:
                sanitized_groups = sanitize_for_json(parallel_groups)
            except Exception:
                sanitized_groups = json.loads(json.dumps(parallel_groups, default=str))
            if not isinstance(sanitized_groups, dict):
                sanitized_groups = {"groups": sanitized_groups}
            agent_cache["parallel_groups"] = sanitized_groups
            self.agents_parallel_groups = dict(sanitized_groups)
        else:
            agent_cache.pop("parallel_groups", None)
            self.agents_parallel_groups = {}
        if delegation_policy_version:
            normalized_version = str(delegation_policy_version)
            agent_cache["delegation_policy_version"] = normalized_version
            self.agents_delegation_policy_version = normalized_version
        else:
            agent_cache.pop("delegation_policy_version", None)
            self.agents_delegation_policy_version = None
        if decisions:
            decisions_list = []
            for entry in decisions:
                try:
                    sanitized_entry = sanitize_for_json(entry)
                except Exception:
                    sanitized_entry = json.loads(json.dumps(entry, default=str))
                decisions_list.append(sanitized_entry)
            agent_cache["delegation_decisions"] = decisions_list
            normalized_decisions: List[Dict[str, Any]] = []
            for item in decisions_list:
                if isinstance(item, dict):
                    normalized_decisions.append(item)
                else:
                    normalized_decisions.append({"value": item})
            self.agents_delegation_decisions = normalized_decisions
        else:
            agent_cache.pop("delegation_decisions", None)
            self.agents_delegation_decisions = []
        self.touch()

    def agent_run_metadata(self) -> Dict[str, Any]:
        metadata: Dict[str, Any] = {}
        if self.agents_run_id:
            metadata["runId"] = self.agents_run_id
        if self.agents_trace_id:
            metadata["traceId"] = self.agents_trace_id
        if self.agents_manager_trace_id:
            metadata["managerTraceId"] = self.agents_manager_trace_id
        if self.agents_model:
            metadata["model"] = self.agents_model
        if self.agents_recorded_at:
            metadata["recordedAt"] = self.agents_recorded_at
        if self.agents_tool_attempts:
            metadata["toolAttempts"] = dict(self.agents_tool_attempts)
        if self.agents_retry_counts:
            metadata["retryCounts"] = dict(self.agents_retry_counts)
        if self.agents_tool_receipts:
            metadata["toolReceipts"] = sanitize_for_json(self.agents_tool_receipts)
        if self.agents_parallel_groups:
            metadata["parallelGroups"] = dict(self.agents_parallel_groups)
        if self.agents_delegation_policy_version:
            metadata["delegationPolicyVersion"] = self.agents_delegation_policy_version
        if self.agents_delegation_decisions:
            metadata["delegationDecisions"] = [dict(entry) for entry in self.agents_delegation_decisions]
        return metadata

    def get_tool_receipt(self, tool: str) -> Optional[Dict[str, Any]]:
        receipts = self.tool_cache.get("tool_receipts") or {}
        receipt = receipts.get(tool)
        return deepcopy(receipt) if receipt is not None else None

    def revision_context(self) -> "SnapshotRevisionContext":
        receipts_payload: Dict[str, Dict[str, Any]] = {}
        raw_receipts = (self.tool_cache or {}).get("tool_receipts") or {}
        if isinstance(raw_receipts, Mapping):
            for tool_name, payload in raw_receipts.items():
                if not isinstance(payload, Mapping):
                    continue
                receipts_payload[str(tool_name)] = deepcopy(payload)
        reasoning_cache: Dict[str, Dict[str, Any]] = {}
        raw_reasoning = (self.tool_cache or {}).get("agent_reasoning") or {}
        if isinstance(raw_reasoning, Mapping):
            for key, value in raw_reasoning.items():
                if isinstance(value, Mapping):
                    reasoning_cache[str(key)] = deepcopy(value)
                elif isinstance(value, str):
                    reasoning_cache[str(key)] = {"summary": value}
        revision_snapshot: Optional[Dict[str, Any]] = None
        analytics_cache = (self.tool_cache or {}).get("analytics")
        if isinstance(analytics_cache, Mapping):
            snapshot_payload = analytics_cache.get("revision_snapshot")
            if isinstance(snapshot_payload, Mapping):
                revision_snapshot = deepcopy(snapshot_payload)
        lane_timestamps: Dict[str, datetime] = {}
        for lane_key in (self.lane_timestamps or {}).keys():
            normalized = str(lane_key or "").strip().lower()
            if not normalized:
                continue
            lane_ts = self.get_lane_timestamp(normalized)
            if lane_ts:
                lane_timestamps[normalized] = lane_ts
        chart_spec = deepcopy(self.last_chart_spec) if isinstance(self.last_chart_spec, dict) else None
        return SnapshotRevisionContext(
            session_id=self.session_id,
            tool_receipts=receipts_payload,
            agent_reasoning=reasoning_cache,
            revision_snapshot=revision_snapshot,
            lane_timestamps=lane_timestamps,
            last_analysis=self.last_analysis,
            last_chart_spec=chart_spec,
        )
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
            self.touch_lane("sql")
        if chart_spec is not None:
            self.last_chart_spec = chart_spec
            self.touch_lane("chart")
        if analysis is not None:
            self.last_analysis = analysis
            self.touch_lane("analysis")
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


@dataclass
class SnapshotRevisionContext:
    session_id: str
    tool_receipts: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    agent_reasoning: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    revision_snapshot: Optional[Dict[str, Any]] = None
    lane_timestamps: Dict[str, datetime] = field(default_factory=dict)
    last_analysis: Optional[str] = None
    last_chart_spec: Optional[Dict[str, Any]] = None

    @staticmethod
    def _normalize_lane(lane: Optional[str]) -> Optional[str]:
        if lane is None:
            return None
        normalized = str(lane).strip().lower()
        return normalized or None

    def lane_age_seconds(self, lane: str, *, now: Optional[datetime] = None) -> Optional[float]:
        normalized = self._normalize_lane(lane)
        if not normalized:
            return None
        timestamp = self.lane_timestamps.get(normalized)
        if timestamp is None:
            return None
        now_dt = now or datetime.now(timezone.utc)
        try:
            delta = now_dt - timestamp
            return max(delta.total_seconds(), 0.0)
        except Exception:
            return None


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

    def _deserialize_snapshot(self, payload: str, session_id: str) -> Optional[SessionStateSnapshot]:
        try:
            data = json.loads(payload)
            snapshot = SessionStateSnapshot(**data)
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.warning("Failed to deserialize session state for %s: %s", session_id, exc)
            return None
        return snapshot

    def _snapshot_expired(self, snapshot: SessionStateSnapshot) -> bool:
        try:
            age = datetime.now(timezone.utc) - snapshot.updated_at
        except Exception:
            return False
        return age.total_seconds() >= self._ttl_seconds

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

        snapshot = self._deserialize_snapshot(payload, session_id)
        if snapshot is None:
            await self.delete(session_id)
            return None
        if self._snapshot_expired(snapshot):
            await self.delete(session_id)
            return None
        return snapshot

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
    candidates = [
        os.getenv("AGENTS_SESSION_TTL_MINUTES"),
        os.getenv("ANALYTICS_SESSION_TTL_MINUTES"),
    ]
    for raw in candidates:
        if not raw:
            continue
        try:
            value = int(raw)
        except ValueError:
            continue
        if value > 0:
            return value
    return DEFAULT_TTL_MINUTES


def _string_similarity(a: str, b: str) -> float:
    try:
        from difflib import SequenceMatcher

        return SequenceMatcher(None, a.lower(), b.lower()).ratio()
    except Exception:  # pragma: no cover - extremely rare
        return 0.0


def _normalize_tool_name(tool: Optional[str]) -> Optional[str]:
    if tool is None:
        return None
    normalized = str(tool).strip().lower()
    return normalized or None
