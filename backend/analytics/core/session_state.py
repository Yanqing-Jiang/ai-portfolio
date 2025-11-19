# --- Analytics Function/Class Map ---
# Function: _hash_arguments
#   Role: Handles hash arguments logic for analytics.core.session_state.
#   Called from: Internal to analytics.core.session_state
#   Invokes: json.dumps, hashlib.sha256
#   Why: Keeps analytics.core.session_state from duplicating hash arguments behavior across flows.
# Class: SessionStateSnapshot
#   Role: Representation of analytics session state persisted in Redis.
#   Called from: analytics.agent_orchestrator.memory, analytics.core.lane_refresh, analytics.core.revision_snapshot, analytics.flows.chart_revision, +23 more
#   Collaborators: pydantic.Field, pydantic.field_validator, copy.deepcopy, analytics.core.session_state._normalize_tool_name, +2 more
#   Why: Supports downstream analytics workflows that rely on SessionStateSnapshot.
# Class: SnapshotRevisionContext
#   Role: Handles SnapshotRevisionContext logic for analytics.core.session_state.
#   Called from: analytics.flows.planner_executor
#   Collaborators: dataclasses.field
#   Why: Keeps analytics.core.session_state from duplicating SnapshotRevisionContext behavior across flows.
# Class: SessionStateRepository
#   Role: Session state storage with Redis and in-memory fallback.
#   Called from: analytics.flows.chart_revision, tests.analytics.conftest, tests.analytics.test_instrumentation_schedule, tests.analytics.test_session_state_fallback
#   Collaborators: json.dumps, time.time, os.getenv, analytics.core.session_state._read_ttl_from_env, +2 more
#   Why: Supports downstream analytics workflows that rely on SessionStateRepository.
# Function: get_session_state_repository
#   Role: Handles get session state repository logic for analytics.core.session_state.
#   Called from: _inspect_session, analytics.flows.chart_revision, analytics.flows.instrumentation, analytics.flows.multi_agent, +12 more
#   Invokes: analytics.core.session_state.SessionStateRepository
#   Why: Keeps analytics.core.session_state from duplicating get session state repository behavior across flows.
# Function: close_session_state_repository
#   Role: Handles close session state repository logic for analytics.core.session_state.
#   Called from: scripts.seed_agentic_staging, temp_run, tests.analytics.test_analysis_revision, tests.analytics.test_revision_routing
#   Invokes: Internal helpers only
#   Why: Keeps analytics.core.session_state from duplicating close session state repository behavior across flows.
# Function: _read_ttl_from_env
#   Role: Handles read ttl from env logic for analytics.core.session_state.
#   Called from: Internal to analytics.core.session_state
#   Invokes: os.getenv
#   Why: Keeps analytics.core.session_state from duplicating read ttl from env behavior across flows.
# Function: _string_similarity
#   Role: Handles string similarity logic for analytics.core.session_state.
#   Called from: Internal to analytics.core.session_state
#   Invokes: difflib.SequenceMatcher
#   Why: Keeps analytics.core.session_state from duplicating string similarity behavior across flows.
# Function: _normalize_tool_name
#   Role: Handles normalize tool name logic for analytics.core.session_state.
#   Called from: Internal to analytics.core.session_state
#   Invokes: Internal helpers only
#   Why: Keeps analytics.core.session_state from duplicating normalize tool name behavior across flows.
# Function: chart_spec_has_numeric_payload
#   Role: Detects whether a chart spec payload contains at least one numeric data point.
#   Called from: analytics.core.session_state.SessionStateSnapshot.record_outputs, analytics.flows.workflow
#   Invokes: collections.deque
#   Why: Prevents empty chart specs from marking the chart lane ready across workflows.
# Function: normalize_row_count
#   Role: Convert loosely-typed row_count payloads into canonical integers.
#   Called from: analytics.core.session_state.SessionStateSnapshot, analytics.flows.planner_executor
#   Invokes: Built-in int parsing helpers only
#   Why: Keeps downstream manifest logic tolerant of serialized row_count strings without duplicating coercion.
# Function: ensure_analysis_outputs_from_revision
#   Role: Rehydrates last_analysis/last_chart_spec plus lane timestamps from cached revision snapshots or artifacts.
#   Called from: analytics.flows.workflow
#   Invokes: analytics.validators.sanitize_for_json, analytics.core.session_state.chart_spec_has_numeric_payload
#   Why: Prevents revision-only flows from running before baseline narratives/charts exist.
# Function: ensure_dataset_preview_from_revision
#   Role: Rehydrates planner_dataset_preview / planner_stock_widget when cached revision snapshots or artifacts contain usable data but receipts went missing.
#   Called from: analytics.flows.workflow
#   Invokes: analytics.core.session_state.SessionStateSnapshot.record_tool_result, analytics.core.session_state.normalize_row_count
#   Why: Prevents analysis revisions from regressing when SQL + market artifacts exist but tool receipts were lost.
# Function: SessionStateSnapshot.record_revision_questions
#   Role: Persists Gemini revision keyword bundles for telemetry and ledger exports.
#   Called from: analytics.services.revision_focus, analytics.flows.workflow, analytics.flows.single_agent_tools
#   Invokes: datetime.now, analytics.services.revision_focus.cache_revision_questions
#   Why: Keeps downstream controllers and inspectors aligned on the prompts agents actually received.
# Function: SessionStateSnapshot.record_web_topics_ready
#   Role: Captures the final `web_topics_ready` payload for audit trails and replay.
#   Called from: analytics.flows.workflow
#   Invokes: datetime.now
#   Why: Lets future revisions or UI replays recover the exact topic branches and prompts that shipped.
# Function: SessionStateSnapshot.record_revision_lane_decision
#   Role: Captures the selected revision lane plus rationale for auditing agent decisions.
#   Called from: analytics.flows.single_agent_tools, analytics.flows.multi_agent
#   Invokes: datetime.now
#   Why: Ensures ledgers and SSE surface the final lane decision and supporting Gemini hints.
# --- End Analytics Function/Class Map ---
from __future__ import annotations

import hashlib
import logging
import time
import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Mapping, Optional, Tuple, TYPE_CHECKING, Literal
from copy import deepcopy
from collections import deque
import uuid
from decimal import Decimal

from pydantic import BaseModel, Field, field_validator

from analytics.validators import sanitize_for_json
from analytics.core.telemetry import (
    analysis_inputs_manifest_sealed,
    analysis_inputs_missing,
    analysis_lane_missing_artifact,
)

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
    "chart_spec_has_numeric_payload",
    "normalize_row_count",
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

ANALYSIS_INPUT_COMPONENTS: Tuple[str, ...] = ("sql", "dataset_preview", "market", "web")
ANALYSIS_INPUT_BLOCKING: Tuple[str, ...] = ("sql", "dataset_preview")
ANALYSIS_INPUT_SOURCES: Dict[str, str] = {
    "sql": "snapshot.last_sql",
    "dataset_preview": "tool_cache.planner_dataset_preview",
    "market": "tool_cache.planner_stock_widget",
    "web": "tool_cache.web_search",
}
ANALYSIS_INPUT_LANES: Dict[str, str] = {
    "sql": "sql",
    "dataset_preview": "sql",
    "market": "market",
    "web": "web",
}
ANALYSIS_INPUT_TOOL_COMPONENT: Dict[str, str] = {
    "planner_dataset_preview": "dataset_preview",
    "planner_stock_widget": "market",
    "web_search": "web",
}


def _hash_arguments(payload: Any) -> str:
    try:
        serialized = json.dumps(payload, sort_keys=True, default=str)
    except TypeError:
        serialized = repr(payload)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()[:16]


def digest_tool_payload(payload: Any, *, limit: int = 512) -> Optional[str]:
    if payload is None:
        return None
    try:
        serialized = json.dumps(payload, sort_keys=True, default=str, ensure_ascii=True)
    except TypeError:
        serialized = repr(payload)
    digest = serialized.strip()
    if not digest:
        return None
    if len(digest) > limit:
        digest = digest[:limit]
    return digest


def chart_spec_has_numeric_payload(chart_spec: Optional[Any], *, max_nodes: int = 4096) -> bool:
    """Return True when a chart spec contains at least one numeric data point."""
    if not isinstance(chart_spec, Mapping):
        return False
    queue = deque([chart_spec])
    inspected = 0
    while queue and inspected < max_nodes:
        inspected += 1
        current = queue.popleft()
        if current is None or isinstance(current, bool):
            continue
        if isinstance(current, (int, float)):
            return True
        if isinstance(current, Mapping):
            for value in current.values():
                if isinstance(value, (str, bytes)):
                    continue
                queue.append(value)
        elif isinstance(current, (list, tuple, set)):
            for value in current:
                if isinstance(value, (str, bytes)):
                    continue
                queue.append(value)
    return False


def normalize_row_count(value: Any) -> Optional[int]:
    """Return canonical integer row counts when the payload is numeric-like."""
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if value.is_integer():
            return int(value)
        return None
    if isinstance(value, Decimal):
        try:
            int_value = int(value)
        except (ValueError, OverflowError):
            return None
        return int_value
    if isinstance(value, str):
        candidate = value.strip()
        if not candidate:
            return None
        candidate = candidate.replace(",", "")
        try:
            return int(candidate)
        except ValueError:
            return None
    return None


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
    analysis_inputs_manifest: Dict[str, Any] = Field(default_factory=dict)
    revision_inputs_plan: Optional[Dict[str, Any]] = None
    revision_inputs_outcome: Optional[Dict[str, Any]] = None
    agent_coordination_events: List[Dict[str, Any]] = Field(default_factory=list)
    agent_revision_questions: List[Dict[str, Any]] = Field(default_factory=list)
    web_research_questions: List[Dict[str, Any]] = Field(default_factory=list)
    web_topics_ready: Optional[Dict[str, Any]] = None
    agent_lane_decisions: List[Dict[str, Any]] = Field(default_factory=list)

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

    def record_revision_inputs_plan(
        self,
        plan: Optional[Mapping[str, Any]],
        *,
        metadata: Optional[Mapping[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        if not plan:
            self.revision_inputs_plan = None
            self.touch()
            return None
        normalized = self._normalize_revision_inputs_payload(plan, metadata=metadata)
        self.revision_inputs_plan = normalized
        self.touch()
        return normalized

    def record_revision_inputs_outcome(
        self,
        outcome: Optional[Mapping[str, Any]],
        *,
        metadata: Optional[Mapping[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        if not outcome:
            self.revision_inputs_outcome = None
            self.touch()
            return None
        normalized = self._normalize_revision_inputs_payload(
            outcome,
            metadata=metadata,
            include_questions=False,
        )
        self.revision_inputs_outcome = normalized
        self.touch()
        return normalized

    def record_web_topics_ready(
        self,
        payload: Optional[Mapping[str, Any]],
        *,
        metadata: Optional[Mapping[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        if not payload:
            self.web_topics_ready = None
            self.touch()
            return None

        def _coerce_int(value: Any) -> Optional[int]:
            try:
                return int(value)
            except (TypeError, ValueError):
                return None

        normalized: Dict[str, Any] = {
            "total": _coerce_int(payload.get("total")),
            "completed": _coerce_int(payload.get("completed")),
            "pending": _coerce_int(payload.get("pending")),
            "recorded_at": datetime.now(timezone.utc).isoformat(),
        }
        branches_payload: List[Dict[str, Any]] = []
        branches = payload.get("branches")
        if isinstance(branches, Iterable):
            for idx, branch in enumerate(branches):
                if not isinstance(branch, Mapping):
                    continue
                branch_id = str(branch.get("id") or branch.get("branch") or f"branch_{idx}")
                status_value = str(branch.get("status") or "").strip() or "ready"
                branch_entry: Dict[str, Any] = {
                    "id": branch_id,
                    "status": status_value,
                }
                summary_value = branch.get("summary")
                if isinstance(summary_value, str) and summary_value.strip():
                    branch_entry["summary"] = summary_value.strip()
                question_kind = branch.get("question_kind")
                if isinstance(question_kind, str) and question_kind.strip():
                    branch_entry["question_kind"] = question_kind.strip()
                branches_payload.append(branch_entry)
        if branches_payload:
            normalized["branches"] = branches_payload

        questions = payload.get("questions")
        if isinstance(questions, Mapping):
            normalized["questions"] = dict(questions)
        if metadata:
            normalized["metadata"] = {key: value for key, value in metadata.items() if value is not None}

        self.web_topics_ready = normalized
        self.touch()
        return normalized

    def record_agent_coordination(self, payload: Mapping[str, Any]) -> Optional[Dict[str, Any]]:
        if not isinstance(payload, Mapping):
            return None
        normalized: Dict[str, Any] = {}
        lane = str(payload.get("lane") or "").strip().lower()
        if lane:
            normalized["lane"] = lane
        web_value = str(payload.get("web") or "").strip().lower()
        if web_value:
            normalized["web"] = web_value
        reason = payload.get("reason") or payload.get("message")
        if isinstance(reason, str) and reason.strip():
            normalized["reason"] = reason.strip()
        source = payload.get("source")
        if isinstance(source, str) and source.strip():
            normalized["source"] = source.strip()
        questions = self._normalize_revision_questions_payload(payload.get("questions"))
        if questions:
            normalized["questions"] = questions
        normalized["revision"] = bool(payload.get("revision", True))
        ts_value = payload.get("ts") or payload.get("timestamp")
        normalized["ts"] = (
            ts_value if isinstance(ts_value, str) and ts_value.strip() else datetime.now(timezone.utc).isoformat()
        )
        session_id = payload.get("session_id")
        if isinstance(session_id, str) and session_id.strip():
            normalized["session_id"] = session_id.strip()
        events = list(self.agent_coordination_events)
        events.append(normalized)
        if len(events) > 20:
            events = events[-20:]
        self.agent_coordination_events = events
        self.touch()
        return normalized

    def record_revision_questions(self, bundle: Any) -> Dict[str, Any]:
        """Persist the Gemini keyword bundle for ledger hydration."""
        if hasattr(bundle, "to_dict"):
            try:
                payload = dict(bundle.to_dict())  # type: ignore[arg-type]
            except Exception:
                payload = {}
        elif isinstance(bundle, Mapping):
            payload = dict(bundle)
        else:
            payload = {
                "keyword_focus": getattr(bundle, "keyword_focus", None),
                "user_question": getattr(bundle, "user_question", None),
                "industry_question": getattr(bundle, "industry_question", None),
                "model": getattr(bundle, "model", None),
                "latency_ms": getattr(bundle, "latency_ms", None),
                "follow_up_query": getattr(bundle, "follow_up_query", None),
                "fingerprint": getattr(bundle, "fingerprint", None),
                "source": getattr(bundle, "source", None),
                "fallback_reason": getattr(bundle, "fallback_reason", None),
            }
        entry = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "keyword_focus": (str(payload.get("keyword_focus") or "").strip()),
            "user_question": (str(payload.get("user_question") or "").strip()),
            "industry_question": (str(payload.get("industry_question") or "").strip()),
            "model": (str(payload.get("model") or "").strip() or None),
            "latency_ms": payload.get("latency_ms"),
            "follow_up_query": (str(payload.get("follow_up_query") or "").strip() or None),
            "fingerprint": (str(payload.get("fingerprint") or "").strip() or None),
            "source": (str(payload.get("source") or "").strip() or None),
            "fallback_reason": (str(payload.get("fallback_reason") or "").strip() or None),
        }
        questions = self.agent_revision_questions
        if not isinstance(questions, list):
            self.agent_revision_questions = []
            questions = self.agent_revision_questions
        questions.append(entry)
        if len(questions) > 25:
            del questions[:-25]
        self.touch()
        try:  # pragma: no cover - lazy import
            from analytics.services.revision_focus import cache_revision_questions, RevisionQuestionBundle  # type: ignore
        except Exception:
            return entry
        try:
            if isinstance(bundle, RevisionQuestionBundle):
                cache_revision_questions(self, bundle)
            else:
                cached_bundle = RevisionQuestionBundle.from_dict(payload)  # type: ignore[arg-type]
                cache_revision_questions(self, cached_bundle)
        except Exception:
            logger.debug("Failed to cache revision questions", exc_info=True)
        return entry

    def record_web_research_questions(self, bundle: Mapping[str, Any]) -> Dict[str, Any]:
        """Persist the Gemini-powered web question bundle for reuse and ledgers."""
        payload = dict(bundle)
        entry = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "keyword_focus": (str(payload.get("keyword_focus") or "").strip() or None),
            "user_question": (str(payload.get("user_question") or "").strip() or None),
            "industry_question": (str(payload.get("industry_question") or "").strip() or None),
            "model": (str(payload.get("model") or "").strip() or None),
            "latency_ms": payload.get("latency_ms"),
            "source": (str(payload.get("source") or "").strip() or None),
            "fallback_reason": (str(payload.get("fallback_reason") or "").strip() or None),
        }
        questions = self.web_research_questions
        if not isinstance(questions, list):
            self.web_research_questions = []
            questions = self.web_research_questions
        questions.append(entry)
        if len(questions) > 25:
            del questions[:-25]
        try:
            cache = self.tool_cache.setdefault("web_research_questions", {})
            if isinstance(cache, dict):
                cache.update(entry)
        except Exception:
            logger.debug("Failed to mirror web research questions in tool cache", exc_info=True)
        self.touch()
        return entry

    def _normalize_revision_inputs_payload(
        self,
        payload: Mapping[str, Any],
        *,
        metadata: Optional[Mapping[str, Any]] = None,
        include_questions: bool = True,
    ) -> Dict[str, Any]:
        normalized: Dict[str, Any] = {
            "recorded_at": datetime.now(timezone.utc).isoformat(),
        }
        lane_value = str(payload.get("lane") or "").strip().lower()
        if lane_value:
            normalized["lane"] = lane_value
        web_value = str(payload.get("web") or "").strip().lower()
        if web_value:
            normalized["web"] = web_value
        if include_questions:
            questions = self._normalize_revision_questions_payload(payload.get("questions"))
            if questions:
                normalized["questions"] = questions
        if metadata:
            for key, value in metadata.items():
                if value is not None:
                    normalized[key] = value
        return normalized

    def _normalize_revision_questions_payload(self, payload: Any) -> Optional[Dict[str, Any]]:
        if payload is None:
            return None
        if hasattr(payload, "to_dict"):
            try:
                payload = payload.to_dict()
            except Exception:
                payload = {}
        if not isinstance(payload, Mapping):
            return None
        sanitized: Dict[str, Any] = {}
        for key in ("keyword_focus", "user_question", "industry_question"):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                sanitized[key] = value.strip()
        model = payload.get("model")
        if isinstance(model, str) and model.strip():
            sanitized["model"] = model.strip()
        latency = payload.get("latency_ms")
        if isinstance(latency, (int, float)):
            sanitized["latency_ms"] = int(latency)
        source = payload.get("source")
        if isinstance(source, str) and source.strip():
            sanitized["source"] = source.strip()
        return sanitized or None

    def record_revision_lane_decision(
        self,
        *,
        lane: Literal["chart", "narrative"],
        rationale: str,
        bundle: Optional[Any] = None,
        decision_source: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Record the lane chosen by the agent runtime."""
        normalized_lane = str(lane or "").strip().lower() or lane
        entry: Dict[str, Any] = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "lane": normalized_lane,
            "rationale": rationale.strip(),
            "source": decision_source,
        }
        if bundle is not None:
            if hasattr(bundle, "to_dict"):
                try:
                    payload = dict(bundle.to_dict())  # type: ignore[arg-type]
                except Exception:
                    payload = {}
            elif isinstance(bundle, Mapping):
                payload = dict(bundle)
            else:
                payload = {
                    "keyword_focus": getattr(bundle, "keyword_focus", None),
                    "user_question": getattr(bundle, "user_question", None),
                    "industry_question": getattr(bundle, "industry_question", None),
                }
            entry["keyword_focus"] = (str(payload.get("keyword_focus") or "").strip() or None)
            entry["user_question"] = (str(payload.get("user_question") or "").strip() or None)
            entry["industry_question"] = (str(payload.get("industry_question") or "").strip() or None)
        decisions = self.agent_lane_decisions
        if not isinstance(decisions, list):
            self.agent_lane_decisions = []
            decisions = self.agent_lane_decisions
        decisions.append(entry)
        if len(decisions) > 25:
            del decisions[:-25]
        self.touch()
        return entry

    def record_tool_result(self, tool: str, payload: Dict[str, Any]) -> None:
        if not isinstance(self.tool_cache, dict):
            self.tool_cache = {}
        self.tool_cache[tool] = payload
        normalized_tool = _normalize_tool_name(tool)
        component = ANALYSIS_INPUT_TOOL_COMPONENT.get(normalized_tool)
        if component:
            lane_hint = ANALYSIS_INPUT_LANES.get(component)
            if lane_hint:
                self.touch_lane(lane_hint)
            self._persist_analysis_lane_receipt(
                component,
                payload,
                source="record_tool_result",
                tool=normalized_tool,
            )
            self.refresh_analysis_inputs_manifest(persist=False)
        self.touch()

    def ensure_dataset_preview_from_revision(self) -> bool:
        """
        Function: ensure_dataset_preview_from_revision -- seeds planner_dataset_preview / planner_stock_widget from
        cached revision snapshots or artifacts so manifest hydration can seal receipts. Called from analytics.flows.workflow.
        """
        tool_cache = self.tool_cache if isinstance(self.tool_cache, dict) else {}
        analytics_cache = tool_cache.get("analytics") if isinstance(tool_cache, Mapping) else None
        revision_snapshot = (
            analytics_cache.get("revision_snapshot")
            if isinstance(analytics_cache, Mapping)
            else None
        )
        artifacts_snapshot = (
            analytics_cache.get("artifacts")
            if isinstance(analytics_cache, Mapping)
            else None
        )

        dataset_ready = self._analysis_component_ready(
            "dataset_preview", tool_cache.get("planner_dataset_preview")
        )
        market_ready = self._analysis_component_ready(
            "market", tool_cache.get("planner_stock_widget")
        )
        seeded = False

        def _coerce_rows(raw: Any) -> List[Dict[str, Any]]:
            rows: List[Dict[str, Any]] = []
            if isinstance(raw, (list, tuple)):
                for entry in raw:
                    if isinstance(entry, Mapping) and entry:
                        rows.append(dict(entry))
            return rows

        def _seed_dataset(rows_payload: Any, row_count_hint: Any) -> bool:
            normalized_rows = _coerce_rows(rows_payload)
            if not normalized_rows:
                return False
            normalized_count = normalize_row_count(row_count_hint)
            payload: Dict[str, Any] = {"rows": normalized_rows}
            if normalized_count is not None:
                payload["row_count"] = normalized_count
            self.record_tool_result("planner_dataset_preview", sanitize_for_json(payload))
            return True

        def _seed_market(snapshot_payload: Any) -> bool:
            if not isinstance(snapshot_payload, Mapping) or not snapshot_payload:
                return False
            sanitized = sanitize_for_json(snapshot_payload)
            self.record_tool_result("planner_stock_widget", sanitized)
            return True

        if not dataset_ready:
            rows_candidate = None
            row_count_candidate = None
            if isinstance(revision_snapshot, Mapping):
                rows_candidate = revision_snapshot.get("data_sample")
                row_count_candidate = revision_snapshot.get("sql_row_count")
            if not rows_candidate and isinstance(artifacts_snapshot, Mapping):
                sql_exec = artifacts_snapshot.get("sql_execution")
                if isinstance(sql_exec, Mapping):
                    rows_candidate = (
                        sql_exec.get("dataset_preview") or sql_exec.get("sample_rows")
                    )
                    row_count_candidate = sql_exec.get("row_count")
            if rows_candidate and _seed_dataset(rows_candidate, row_count_candidate):
                dataset_ready = True
                seeded = True

        if not market_ready:
            market_payload = None
            if isinstance(revision_snapshot, Mapping):
                market_payload = revision_snapshot.get("stock_widget")
            if not isinstance(market_payload, Mapping) and isinstance(artifacts_snapshot, Mapping):
                market_artifact = artifacts_snapshot.get("market")
                if isinstance(market_artifact, Mapping):
                    market_payload = market_artifact.get("snapshot")
            if market_payload and _seed_market(market_payload):
                market_ready = True
                seeded = True

        return seeded

    def ensure_analysis_outputs_from_revision(self) -> bool:
        """
        Function: ensure_analysis_outputs_from_revision -- rehydrates missing analysis/chart outputs and lane
        timestamps from cached revision snapshots or persisted artifacts so revision-only requests never run
        without a baseline narrative. Called from analytics.flows.workflow.
        """
        tool_cache = self.tool_cache if isinstance(self.tool_cache, dict) else {}
        analytics_cache = tool_cache.get("analytics") if isinstance(tool_cache, Mapping) else None
        revision_snapshot = (
            analytics_cache.get("revision_snapshot")
            if isinstance(analytics_cache, Mapping)
            else None
        )
        artifacts_snapshot = (
            analytics_cache.get("artifacts")
            if isinstance(analytics_cache, Mapping)
            else None
        )
        analysis_present = isinstance(self.last_analysis, str) and bool(self.last_analysis.strip())
        chart_present = isinstance(self.last_chart_spec, Mapping) and bool(self.last_chart_spec)
        seeded = False

        def _parse_timestamp(value: Any) -> Optional[datetime]:
            if isinstance(value, str):
                candidate = value.strip()
                if not candidate:
                    return None
                normalized = candidate[:-1] + "+00:00" if candidate.endswith("Z") else candidate
                try:
                    parsed = datetime.fromisoformat(normalized)
                except ValueError:
                    return None
                if parsed.tzinfo is None:
                    parsed = parsed.replace(tzinfo=timezone.utc)
                return parsed.astimezone(timezone.utc)
            return None

        def _coerce_analysis(payload: Any) -> Optional[str]:
            if isinstance(payload, str):
                stripped = payload.strip()
                return stripped or None
            if isinstance(payload, Mapping):
                for key in ("analysis", "analysis_text", "final", "summary"):
                    candidate = payload.get(key)
                    if isinstance(candidate, str) and candidate.strip():
                        return candidate.strip()
            return None

        def _coerce_chart_spec(payload: Any) -> Optional[Dict[str, Any]]:
            if not isinstance(payload, Mapping):
                return None
            if "spec" in payload and isinstance(payload["spec"], Mapping):
                payload = payload["spec"]
            sanitized = sanitize_for_json(payload)
            if isinstance(sanitized, Mapping) and chart_spec_has_numeric_payload(sanitized):
                return dict(sanitized)
            return None

        timestamp_hint = None
        if isinstance(revision_snapshot, Mapping):
            timestamp_hint = _parse_timestamp(revision_snapshot.get("updated_at"))
        if timestamp_hint is None:
            timestamp_hint = self.updated_at if isinstance(self.updated_at, datetime) else None
        timestamp_hint = timestamp_hint or datetime.now(timezone.utc)

        if not analysis_present:
            analysis_candidate = None
            if isinstance(revision_snapshot, Mapping):
                analysis_candidate = revision_snapshot.get("analysis")
            if analysis_candidate is None and isinstance(artifacts_snapshot, Mapping):
                analysis_artifact = artifacts_snapshot.get("analysis")
                analysis_candidate = (
                    analysis_artifact.get("analysis_text")
                    if isinstance(analysis_artifact, Mapping)
                    else None
                )
                if analysis_candidate is None and isinstance(analysis_artifact, Mapping):
                    analysis_candidate = (
                        analysis_artifact.get("analysis")
                        or analysis_artifact.get("final")
                        or analysis_artifact.get("summary")
                    )
            normalized_analysis = _coerce_analysis(analysis_candidate)
            if normalized_analysis:
                self.last_analysis = normalized_analysis
                self.touch_lane("analysis", at=timestamp_hint)
                seeded = True

        if not chart_present:
            chart_candidate = None
            if isinstance(revision_snapshot, Mapping):
                chart_candidate = revision_snapshot.get("chart_spec")
            if chart_candidate is None and isinstance(artifacts_snapshot, Mapping):
                chart_artifact = artifacts_snapshot.get("chart")
                if isinstance(chart_artifact, Mapping):
                    chart_candidate = chart_artifact.get("spec") or chart_artifact.get("chart_spec")
            normalized_chart = _coerce_chart_spec(chart_candidate)
            if normalized_chart:
                self.last_chart_spec = normalized_chart
                self.touch_lane("chart", at=timestamp_hint)
                seeded = True

        return seeded

    def record_tool_receipt(self, tool: str, payload: Dict[str, Any]) -> None:
        receipts = self.tool_cache.setdefault("tool_receipts", {})
        enhanced = deepcopy(payload)
        enhanced.setdefault("tool", tool)
        enhanced.setdefault("recorded_at", datetime.now(timezone.utc).isoformat())
        tool_call_meta = enhanced.get("tool_call")
        arguments_payload = enhanced.get("arguments")
        if arguments_payload is None and isinstance(tool_call_meta, Mapping):
            arguments_payload = tool_call_meta.get("arguments") or tool_call_meta.get("arguments_delta")
        if "arguments_hash" not in enhanced and arguments_payload is not None:
            enhanced["arguments_hash"] = _hash_arguments(arguments_payload)
        argument_digest = digest_tool_payload(arguments_payload)
        if argument_digest and not enhanced.get("arguments_digest"):
            enhanced["arguments_digest"] = argument_digest
        if "attempts" not in enhanced and "attempt" in enhanced:
            try:
                enhanced["attempts"] = int(enhanced.get("attempt", 0))
            except (TypeError, ValueError):
                enhanced["attempts"] = 0
        output_payload = enhanced.get("payload") or enhanced.get("result")
        if output_payload is None and isinstance(tool_call_meta, Mapping):
            output_payload = tool_call_meta.get("result")
        output_digest = digest_tool_payload(output_payload)
        if output_digest and not enhanced.get("output_digest"):
            enhanced["output_digest"] = output_digest
        metadata_payload = enhanced.get("metadata") if isinstance(enhanced.get("metadata"), Mapping) else None
        guardrail_payload = (
            enhanced.get("latency_guardrail")
            or enhanced.get("guardrail")
            or (metadata_payload.get("guardrail") if metadata_payload else None)
            or (metadata_payload.get("latency_guardrail") if metadata_payload else None)
        )
        if guardrail_payload:
            sanitized_guardrail = sanitize_for_json(guardrail_payload)
            enhanced.setdefault("latency_guardrail", sanitized_guardrail)
            enhanced.setdefault("guardrail", sanitized_guardrail)
            if metadata_payload is not None:
                merged_metadata = dict(metadata_payload)
                merged_metadata.setdefault("guardrail", sanitized_guardrail)
                enhanced["metadata"] = merged_metadata
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
        lane_ttls: Dict[str, int] = {}
        try:
            from analytics.core import lane_refresh as _lane_refresh_mod  # type: ignore
        except Exception:  # pragma: no cover - defensive import
            _lane_refresh_mod = None
        resolver = getattr(_lane_refresh_mod, "resolve_lane_ttls", None)
        if callable(resolver):
            try:
                lane_ttls = dict(resolver())
            except Exception:  # pragma: no cover - defensive fallback
                lane_ttls = {}
        chart_spec = deepcopy(self.last_chart_spec) if isinstance(self.last_chart_spec, dict) else None
        manifest = deepcopy(self.analysis_inputs_manifest) if isinstance(self.analysis_inputs_manifest, dict) else {}
        return SnapshotRevisionContext(
            session_id=self.session_id,
            tool_receipts=receipts_payload,
            agent_reasoning=reasoning_cache,
            revision_snapshot=revision_snapshot,
            lane_timestamps=lane_timestamps,
            lane_ttls=lane_ttls,
            last_analysis=self.last_analysis,
            last_chart_spec=chart_spec,
            analysis_inputs_manifest=manifest,
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
        analysis_inputs_changed = False
        if sql is not None:
            self.last_sql = sql
            self.touch_lane("sql")
            self._persist_analysis_lane_receipt(
                "sql",
                sql,
                source="record_outputs",
                tool="sql_generation",
            )
            analysis_inputs_changed = True
        if chart_spec is not None:
            self.last_chart_spec = chart_spec
            if chart_spec_has_numeric_payload(chart_spec):
                self.touch_lane("chart")
        if analysis is not None:
            self.last_analysis = analysis
            self.touch_lane("analysis")
        if analysis_inputs_changed:
            self.refresh_analysis_inputs_manifest(persist=False)
        self.touch()

    def refresh_analysis_inputs_manifest(self, *, persist: bool = True) -> None:
        timestamp_hint = None if persist else self._manifest_timestamp_hint()
        previous_manifest = self.analysis_inputs_manifest if isinstance(self.analysis_inputs_manifest, dict) else {}
        manifest, changed = self._build_analysis_inputs_manifest(timestamp_hint)
        self.analysis_inputs_manifest = manifest
        if changed:
            self._emit_manifest_metrics(previous_manifest, manifest)
        if changed and persist:
            self.touch()

    def _emit_manifest_metrics(self, previous_manifest: Mapping[str, Any], manifest: Mapping[str, Any]) -> None:
        new_missing = manifest.get("missing_components") or []
        prev_missing = previous_manifest.get("missing_components") or []
        if new_missing and new_missing != prev_missing:
            analysis_inputs_missing(
                session_id=getattr(self, "session_id", None),
                missing_components=new_missing,
                metadata={"source": "manifest_builder"},
            )
        prev_status = previous_manifest.get("status")
        if prev_status is None and previous_manifest.get("complete"):
            prev_status = "sealed"
        new_status = manifest.get("status")
        if new_status == "sealed" and prev_status != "sealed":
            analysis_inputs_manifest_sealed(
                session_id=getattr(self, "session_id", None),
                version=manifest.get("version"),
                ready_components=manifest.get("ready_components") or [],
                captured_at=manifest.get("sealed_at"),
                receipts=manifest.get("receipts"),
                metadata={"source": "manifest_builder"},
            )

    def ensure_analysis_inputs_manifest(self) -> None:
        timestamp_hint = self._manifest_timestamp_hint()
        manifest, _ = self._build_analysis_inputs_manifest(timestamp_hint)
        self.analysis_inputs_manifest = manifest

    def _manifest_timestamp_hint(self) -> str:
        existing = self.analysis_inputs_manifest if isinstance(self.analysis_inputs_manifest, dict) else {}
        updated = existing.get("updated_at") if isinstance(existing, dict) else None
        if isinstance(updated, str):
            return updated
        baseline = self.updated_at if isinstance(self.updated_at, datetime) else datetime.now(timezone.utc)
        return baseline.astimezone(timezone.utc).isoformat()

    def _analysis_input_payloads(self) -> Dict[str, Any]:
        tool_cache = self.tool_cache if isinstance(self.tool_cache, dict) else {}
        dataset_preview = tool_cache.get("planner_dataset_preview")
        if not isinstance(dataset_preview, Mapping):
            dataset_preview = None
        market_payload = tool_cache.get("planner_stock_widget")
        if not isinstance(market_payload, Mapping):
            market_payload = None
        web_payload = tool_cache.get("web_search")
        if not isinstance(web_payload, Mapping):
            web_payload = None
        return {
            "sql": self.last_sql if isinstance(self.last_sql, str) else None,
            "dataset_preview": dataset_preview,
            "market": market_payload,
            "web": web_payload,
        }

    def _analysis_component_ready(self, component: str, payload: Any) -> bool:
        if component == "sql":
            return isinstance(payload, str) and bool(payload.strip())
        if component == "dataset_preview":
            if not isinstance(payload, Mapping):
                return False
            rows = payload.get("rows")
            row_count = payload.get("row_count")
            normalized_row_count = normalize_row_count(row_count)
            return bool(rows) or normalized_row_count is not None
        if component == "market":
            if isinstance(payload, Mapping):
                if payload.get("snapshot") or payload.get("widget") or payload.get("series"):
                    return True
                return bool(payload)
            return False
        if component == "web":
            if isinstance(payload, Mapping):
                summary = payload.get("summary")
                if isinstance(summary, str) and summary.strip():
                    return True
                snippets = payload.get("snippets") or payload.get("documents") or payload.get("articles")
                if isinstance(snippets, Mapping):
                    snippets = list(snippets.values())
                if isinstance(snippets, (list, tuple)) and any(snippets):
                    return True
            return False
        return False

    def _lane_receipts_cache(self) -> Dict[str, Dict[str, Any]]:
        if not isinstance(self.tool_cache, dict):
            self.tool_cache = {}
        cache = self.tool_cache.get("analysis_lane_receipts")
        if not isinstance(cache, dict):
            cache = {}
            self.tool_cache["analysis_lane_receipts"] = cache
        return cache

    def _next_lane_receipt_version(self) -> int:
        if not isinstance(self.tool_cache, dict):
            self.tool_cache = {}
        meta = self.tool_cache.get("analysis_lane_receipts_meta")
        if not isinstance(meta, dict):
            meta = {}
            self.tool_cache["analysis_lane_receipts_meta"] = meta
        version = int(meta.get("version") or 0) + 1
        meta["version"] = version
        return version

    def _persist_analysis_lane_receipt(
        self,
        component: str,
        payload: Any,
        *,
        source: str,
        tool: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        normalized_component = str(component or "").strip().lower()
        if normalized_component not in ANALYSIS_INPUT_COMPONENTS:
            return None
        lane = ANALYSIS_INPUT_LANES.get(normalized_component, normalized_component)
        if not self._analysis_component_ready(normalized_component, payload):
            analysis_lane_missing_artifact(
                session_id=getattr(self, "session_id", None),
                lane=lane,
                component=normalized_component,
                reason="payload_incomplete",
                metadata={"source": source, "tool": tool},
            )
            return None
        cache = self._lane_receipts_cache()
        version = self._next_lane_receipt_version()
        receipt_id = f"{normalized_component}-{version}-{uuid.uuid4().hex[:6]}"
        entry = {
            "component": normalized_component,
            "lane": lane,
            "receipt_id": receipt_id,
            "capture_version": version,
            "captured_at": datetime.now(timezone.utc).isoformat(),
            "source": source,
        }
        if tool:
            entry["tool"] = tool
        digest = digest_tool_payload(payload)
        if digest:
            entry["digest"] = digest
        cache[normalized_component] = entry
        return entry

    def ensure_analysis_lane_receipts(self) -> None:
        payloads = self._analysis_input_payloads()
        receipts = self._lane_receipts_cache()
        updated = False
        for component in ANALYSIS_INPUT_COMPONENTS:
            if receipts.get(component):
                continue
            payload = payloads.get(component)
            if not self._analysis_component_ready(component, payload):
                continue
            entry = self._persist_analysis_lane_receipt(
                component,
                payload,
                source="backfill",
                tool=ANALYSIS_INPUT_SOURCES.get(component),
            )
            updated = updated or bool(entry)
        if updated:
            self.touch()

    def reset_agent_session(self) -> None:
        """
        Function: reset_agent_session -- clears cached agent metadata, manifest receipts, and manifest state
        so fresh chats do not inherit stale planner context. Called from analytics.flows.workflow.
        """
        cache = self.tool_cache
        if isinstance(cache, dict):
            cache.pop("agent", None)
            cache.pop("analysis_lane_receipts", None)
            cache.pop("analysis_lane_receipts_meta", None)
        self.analysis_inputs_manifest = {}
        self.touch()

    def _build_analysis_inputs_manifest(self, timestamp_override: Optional[str]) -> Tuple[Dict[str, Any], bool]:
        payloads = self._analysis_input_payloads()
        previous_manifest = self.analysis_inputs_manifest if isinstance(self.analysis_inputs_manifest, dict) else {}
        previous_components = previous_manifest.get("components")
        if not isinstance(previous_components, dict):
            previous_components = {}
        timestamp_value = timestamp_override or datetime.now(timezone.utc).isoformat()

        receipts_cache = self.tool_cache.get("analysis_lane_receipts") if isinstance(self.tool_cache, dict) else {}
        if not isinstance(receipts_cache, dict):
            receipts_cache = {}

        components: Dict[str, Dict[str, Any]] = {}
        ready_components: List[str] = []
        missing_components: List[str] = []

        for component in ANALYSIS_INPUT_COMPONENTS:
            lane = ANALYSIS_INPUT_LANES.get(component)
            payload = payloads.get(component)
            previous_entry = previous_components.get(component, {})
            entry: Dict[str, Any] = {
                "lane": lane,
                "source": ANALYSIS_INPUT_SOURCES[component],
            }
            reuse_metadata = self._lane_reuse_metadata(lane) if lane else None
            if reuse_metadata:
                entry["reuse_metadata"] = reuse_metadata
            if self._analysis_component_ready(component, payload):
                state = "ready"
                ready_components.append(component)
                if reuse_metadata:
                    entry["reused"] = True
            else:
                lane_timestamp = self.get_lane_timestamp(lane) if lane else None
                if lane_timestamp:
                    state = "missing"
                    missing_components.append(component)
                else:
                    state = "pending"
            entry["state"] = state
            payload_digest = digest_tool_payload(payload)
            if payload_digest:
                entry["digest"] = payload_digest
            receipt_entry = receipts_cache.get(component)
            if isinstance(receipt_entry, Mapping):
                entry["receipt_id"] = receipt_entry.get("receipt_id")
                entry["captured_at"] = receipt_entry.get("captured_at")
                entry["capture_version"] = receipt_entry.get("capture_version")
            component_changed = (
                previous_entry.get("state") != state
                or previous_entry.get("digest") != entry.get("digest")
                or previous_entry.get("receipt_id") != entry.get("receipt_id")
            )
            entry["updated_at"] = (
                previous_entry.get("updated_at")
                if not component_changed and previous_entry.get("updated_at")
                else timestamp_value
            )
            components[component] = entry

        blocking_components = [
            name for name in ANALYSIS_INPUT_BLOCKING if components.get(name, {}).get("state") != "ready"
        ]
        complete = not blocking_components

        prev_ready = previous_manifest.get("ready_components") or []
        prev_missing = previous_manifest.get("missing_components") or []
        prev_blocking = previous_manifest.get("blocking_components") or []
        prev_complete = previous_manifest.get("complete")
        prev_version = int(previous_manifest.get("version") or 0)

        structure_changed = (
            components != previous_components
            or ready_components != prev_ready
            or missing_components != prev_missing
            or blocking_components != prev_blocking
            or complete != prev_complete
            or prev_version == 0
        )

        if prev_version <= 0:
            version = 1
        else:
            version = prev_version + 1 if structure_changed else prev_version

        manifest_updated_at = (
            timestamp_value
            if structure_changed or not isinstance(previous_manifest.get("updated_at"), str)
            else previous_manifest["updated_at"]
        )

        manifest_payload = {
            "components": components,
            "ready_components": ready_components,
            "missing_components": missing_components,
            "blocking_components": blocking_components,
            "complete": complete,
            "version": version,
            "updated_at": manifest_updated_at,
            "status": "sealed" if complete else "pending",
            "receipts": {
                component: (receipts_cache.get(component) or {}).get("receipt_id")
                for component in ANALYSIS_INPUT_COMPONENTS
            },
        }
        if complete:
            manifest_payload["sealed_at"] = manifest_updated_at
        return manifest_payload, structure_changed

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
    lane_ttls: Dict[str, int] = field(default_factory=dict)
    last_analysis: Optional[str] = None
    last_chart_spec: Optional[Dict[str, Any]] = None
    analysis_inputs_manifest: Dict[str, Any] = field(default_factory=dict)

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

    def should_refresh(self, lane: str, *, now: Optional[datetime] = None) -> bool:
        normalized = self._normalize_lane(lane)
        if not normalized:
            return True
        ttl = int(self.lane_ttls.get(normalized, 0))
        if ttl <= 0:
            return True
        age = self.lane_age_seconds(normalized, now=now)
        if age is None:
            return True
        return age > ttl


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
            snapshot.ensure_analysis_inputs_manifest()
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
