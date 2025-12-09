# --- Analytics Function/Class Map ---
# Function: _normalize_topic_key
#   Role: Handles normalize topic key logic for analytics.flows.tooling.
#   Called from: Internal to analytics.flows.tooling
#   Invokes: re.sub
#   Why: Keeps analytics.flows.tooling from duplicating normalize topic key behavior across flows.
# Function: _merge_web_payloads
#   Role: Combine multiple per-topic web payloads into a single context blob.
#   Called from: Internal to analytics.flows.tooling
#   Invokes: json.dumps
#   Why: Supports downstream analytics workflows that rely on _merge_web_payloads.
# Class: ToolExecutionContext
#   Role: Context exposed to tool adapters during fan-out.
#   Called from: tests.analytics.test_web_retriever_adapter
#   Collaborators: dataclasses.dataclass, dataclasses.field
#   Why: Supports downstream analytics workflows that rely on ToolExecutionContext.
# Class: ToolAdapterResult
#   Role: Normalized result emitted by a tool adapter.
#   Called from: tests.analytics.test_planner_executor_sql
#   Collaborators: dataclasses.field
#   Why: Supports downstream analytics workflows that rely on ToolAdapterResult.
# Class: BaseToolAdapter
#   Role: Minimal async interface each adapter must implement.
#   Called from: tests.analytics.test_planner_executor_sql
#   Collaborators: Internal helpers only
#   Why: Supports downstream analytics workflows that rely on BaseToolAdapter.
# Class: _FatalAdapterException
#   Role: Signal used to cancel sibling adapters when a fatal error occurs.
#   Called from: Internal to analytics.flows.tooling
#   Collaborators: Internal helpers only
#   Why: Supports downstream analytics workflows that rely on _FatalAdapterException.
# Class: ToolTaskGroup
#   Role: Coordinate tool adapters with bounded concurrency.
#   Called from: Internal to analytics.flows.tooling
#   Collaborators: asyncio.Semaphore, inspect.isawaitable, asyncio.TaskGroup, analytics.flows.tooling._FatalAdapterException, +1 more
#   Why: Supports downstream analytics workflows that rely on ToolTaskGroup.
# Class: SQLPlannerAdapter
#   Role: Handles SQLPlannerAdapter logic for analytics.flows.tooling.
#   Called from: Internal to analytics.flows.tooling
#   Collaborators: analytics.flows.tooling.ToolAdapterResult
#   Why: Keeps analytics.flows.tooling from duplicating SQLPlannerAdapter behavior across flows.
# Class: ChartBuilderAdapter
#   Role: Handles ChartBuilderAdapter logic for analytics.flows.tooling.
#   Called from: Internal to analytics.flows.tooling
#   Collaborators: analytics.flows.tooling.ToolAdapterResult
#   Why: Keeps analytics.flows.tooling from duplicating ChartBuilderAdapter behavior across flows.
# Class: WebRetrieverAdapter
#   Role: Handles WebRetrieverAdapter logic for analytics.flows.tooling.
#   Called from: analytics.flows.planner_executor, tests.analytics.test_web_retriever_adapter
#   Collaborators: collections.Counter, collections.defaultdict, analytics.core.session_state.get_session_state_repository, analytics.flows.tooling.ToolAdapterResult, +2 more
#   Why: Keeps analytics.flows.tooling from duplicating WebRetrieverAdapter behavior across flows.
# Class: StockTrackerAdapter
#   Role: Handles StockTrackerAdapter logic for analytics.flows.tooling.
#   Called from: analytics.flows.multi_agent, analytics.flows.planner_executor, analytics.flows.single_agent_tools
#   Collaborators: analytics.services.polygon.PolygonMarketDataClient, time.perf_counter, analytics.flows.tooling.ToolAdapterResult, re.finditer, +1 more
#   Why: Keeps analytics.flows.tooling from duplicating StockTrackerAdapter behavior across flows.
# Class: MarketQuestionAdapter
#   Role: Stock tracker wrapper that tags outputs for specific market questions.
#   Called from: analytics.flows.planner_executor
#   Collaborators: Internal helpers only
#   Why: Supports downstream analytics workflows that rely on MarketQuestionAdapter.
# Class: NarrativeSynthesizerAdapter
#   Role: Handles NarrativeSynthesizerAdapter logic for analytics.flows.tooling.
#   Called from: Internal to analytics.flows.tooling
#   Collaborators: analytics.flows.tooling.ToolAdapterResult
#   Why: Keeps analytics.flows.tooling from duplicating NarrativeSynthesizerAdapter behavior across flows.
# Function: get_default_tool_adapters
#   Role: Handles get default tool adapters logic for analytics.flows.tooling.
#   Called from: analytics.flows.planner.analysis_lane, analytics.flows.planner_executor
#   Invokes: Internal helpers only
#   Why: Keeps analytics.flows.tooling from duplicating get default tool adapters behavior across flows.
# Function: _resolve_concurrency_limit
#   Role: Handles resolve concurrency limit logic for analytics.flows.tooling.
#   Called from: Internal to analytics.flows.tooling
#   Invokes: os.getenv
#   Why: Keeps analytics.flows.tooling from duplicating resolve concurrency limit behavior across flows.
# Function: run_tool_parallelism
#   Role: Execute the registered tool adapters with concurrency pinned to the adapter count and yield telemetry events.
#   Called from: analytics.flows.planner.analysis_lane, analytics.flows.planner.fanout, analytics.flows.planner_executor, tests.analytics.test_planner_executor_sql
#   Invokes: analytics.flows.tooling.ToolExecutionContext, analytics.core.telemetry.tool_parallelism, analytics.flows.tooling.ToolTaskGroup, asyncio.Queue, +2 more
#   Why: Supports downstream analytics workflows that rely on run_tool_parallelism.
# --- End Analytics Function/Class Map ---
from __future__ import annotations

import logging
import asyncio
import contextlib
import copy
import json
import os
import re
import time
from collections import Counter, defaultdict
from collections.abc import Mapping as MappingABC
from dataclasses import dataclass, field
from datetime import datetime
from typing import (
    Any,
    Awaitable,
    Callable,
    Dict,
    List,
    Mapping,
    Optional,
    Sequence,
    Set,
    Tuple,
    TYPE_CHECKING,
    AsyncGenerator,
)
import inspect

from analytics.artifacts.models import MarketArtifact, PipelineArtifacts, WebContextArtifact
from analytics.core import telemetry
from analytics.core.events import EventEmitter
from analytics.core.intent_impl.models import IntentModel
from analytics.core.session_state import SessionStateSnapshot, get_session_state_repository
from analytics.core.lane_refresh import resolve_lane_ttls
from analytics.core.state import QueryPlanModel
from analytics.services.response_search import (
    ResponseSearchError,
    SearchTopicPlan,
    WebResearchQuestionBundle,
    build_web_research_questions,
    generate_search_topics,
    has_search_api_key,
    perform_response_search,
)
from analytics.services.polygon import PolygonMarketDataClient, PolygonError, fetch_daily_snapshot

logger = logging.getLogger(__name__)

_WEB_SNIPPET_LIMIT = 5


def _normalize_topic_key(value: str) -> str:
    if not value:
        return ""
    return re.sub(r"\s+", " ", value.strip().lower())


def _merge_web_payloads(
    payloads: Sequence[Dict[str, Any]],
    *,
    base_query: Optional[str] = None,
) -> Dict[str, Any]:
    """Combine multiple per-topic web payloads into a single context blob."""
    entries: List[Dict[str, Any]] = [dict(payload) for payload in payloads if isinstance(payload, dict)]
    if not entries:
        return {}

    summaries: List[str] = []
    annotations: List[Dict[str, Any]] = []
    topics: List[Dict[str, Any]] = []
    snippets: List[Dict[str, Any]] = []
    search_topics: List[str] = []
    ready_any = False
    from_cache_all = True
    model: Optional[str] = None
    usage: Optional[Dict[str, Any]] = None
    fetched_at: Optional[str] = None
    search_id: Optional[str] = None
    latency_total = 0
    query_value = base_query

    for entry in entries:
        ready_any = ready_any or bool(entry.get("ready"))
        if not entry.get("from_cache"):
            from_cache_all = False
        model = entry.get("model") or model
        usage = entry.get("usage") or usage
        fetched_at = entry.get("fetched_at") or fetched_at
        if not search_id:
            search_id = entry.get("search_id")
        if not query_value:
            query_value = entry.get("query") or entry.get("query_terms")

        summary = entry.get("summary")
        if isinstance(summary, str) and summary.strip():
            summaries.append(summary.strip())

        entry_topics = entry.get("topics")
        if isinstance(entry_topics, list):
            topics.extend(entry_topics)

        entry_snippets = entry.get("snippets")
        if isinstance(entry_snippets, list):
            snippets.extend(entry_snippets)

        entry_annotations = entry.get("annotations")
        if isinstance(entry_annotations, list):
            annotations.extend(entry_annotations)

        entry_search_topics = entry.get("search_topics")
        if isinstance(entry_search_topics, list):
            for topic in entry_search_topics:
                if isinstance(topic, str) and topic.strip() and topic not in search_topics:
                    search_topics.append(topic)
        else:
            topic_value = entry.get("search_topic")
            if isinstance(topic_value, str) and topic_value.strip() and topic_value not in search_topics:
                search_topics.append(topic_value)

        latency = entry.get("latency_ms")
        if isinstance(latency, (int, float)):
            latency_total += int(latency)

    deduped_snippets: List[Dict[str, Any]] = []
    seen_snippet_keys: Set[str] = set()
    for snippet in snippets:
        if not isinstance(snippet, dict):
            continue
        key = snippet.get("url") or snippet.get("display_url") or snippet.get("snippet") or json.dumps(snippet, sort_keys=True)
        key_lower = key.lower() if isinstance(key, str) else str(key)
        if key_lower in seen_snippet_keys:
            continue
        seen_snippet_keys.add(key_lower)
        deduped_snippets.append(snippet)
        if len(deduped_snippets) >= _WEB_SNIPPET_LIMIT:
            break

    combined_summary = None
    if summaries:
        combined_summary = "\n\n".join(dict.fromkeys(summaries))

    merged = {
        "query": query_value,
        "query_terms": query_value,
        "search_topic": search_topics[0] if search_topics else None,
        "search_topics": search_topics,
        "summary": combined_summary,
        "snippets": deduped_snippets,
        "annotations": annotations,
        "topics": topics,
        "usage": usage,
        "fetched_at": fetched_at,
        "latency_ms": latency_total or None,
        "model": model,
        "from_cache": from_cache_all,
        "ready": ready_any,
        "search_id": search_id,
        "topic_count": len(entries),
    }
    return merged


def _lane_ttl_remaining(
    snapshot: Optional[SessionStateSnapshot],
    lane: str,
    *,
    now: Optional[datetime] = None,
) -> Optional[int]:
    ttl_map = resolve_lane_ttls()
    ttl = int(ttl_map.get(lane, 0))
    if ttl <= 0 or snapshot is None:
        return None
    age = snapshot.lane_age_seconds(lane, now=now)
    if age is None:
        return None
    remaining = ttl - age
    return int(remaining) if remaining > 0 else None


if TYPE_CHECKING:  # pragma: no cover - import guard for typing only
    from analytics.flows.planner.context import PlannerPhaseContext


@dataclass(frozen=True)
class ToolExecutionContext:
    """Context exposed to tool adapters during fan-out."""

    session_id: str
    query: str
    intent: Any
    plan: Any
    template: Optional[Any]
    configs: Dict[str, Any]
    revision_directive: Optional[Any] = None
    revision_focus: Optional[str] = None
    revision_search_topics: Tuple[Dict[str, Any], ...] = field(default_factory=tuple)
    artifacts: Optional[PipelineArtifacts] = None
    snapshot_artifacts: Optional[PipelineArtifacts] = None


@dataclass
class ToolAdapterResult:
    """Normalized result emitted by a tool adapter."""

    name: str
    status: str
    payload: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    elapsed_ms: Optional[int] = None
    fatal: bool = False


class BaseToolAdapter:
    """Minimal async interface each adapter must implement."""

    name: str = "tool"
    display_name: str = "Tool"
    description: str = ""
    preview_only: bool = True
    capabilities: Tuple[str, ...] = ()
    fatal_on_exception: bool = False
    outputs: Tuple[str, ...] = ()

    def get_metadata(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "display_name": self.display_name,
            "description": self.description,
            "preview_only": self.preview_only,
            "capabilities": list(self.capabilities),
            "outputs": list(self.outputs),
        }

    async def expand(self, context: ToolExecutionContext) -> Sequence["BaseToolAdapter"]:
        """Return concrete adapters to execute for the given context.

        Most tools run once and therefore return ``self``. Adapters that need
        to fan out into multiple specialized executions can override this method
        to return additional adapter instances.
        """
        return (self,)

    async def execute(self, context: ToolExecutionContext) -> ToolAdapterResult:  # pragma: no cover - interface
        raise NotImplementedError


class _FatalAdapterException(Exception):
    """Signal used to cancel sibling adapters when a fatal error occurs."""

    def __init__(self, result: ToolAdapterResult) -> None:
        super().__init__(result.error or "fatal tool adapter error")
        self.result = result


class ToolTaskGroup:
    """Coordinate tool adapters with bounded concurrency."""

    def __init__(self, adapters: Sequence[BaseToolAdapter], *, concurrency_limit: int = 5) -> None:
        self._adapters: Sequence[BaseToolAdapter] = adapters
        self._semaphore = asyncio.Semaphore(max(1, concurrency_limit))

    async def run(
        self,
        context: ToolExecutionContext,
        *,
        on_result: Optional[Callable[[ToolAdapterResult], Optional[Awaitable[None]]]] = None,
    ) -> List[ToolAdapterResult]:
        results: Dict[int, ToolAdapterResult] = {}

        def _record(index: int, result: ToolAdapterResult) -> None:
            results.setdefault(index, result)

        async def _dispatch_result(index: int, result: ToolAdapterResult) -> None:
            if on_result is None:
                return
            try:
                maybe = on_result(result)
                if inspect.isawaitable(maybe):
                    await maybe
            except Exception:
                logger.exception(
                    "tool_parallelism.result_callback_failed",
                    extra={"adapter_index": index, "adapter": getattr(result, "name", None)},
                )

        async def _runner(index: int, adapter: BaseToolAdapter) -> None:
            adapter_meta = adapter.get_metadata()
            started = datetime.utcnow()
            await self._semaphore.acquire()
            try:
                try:
                    result = await adapter.execute(context)
                except asyncio.CancelledError:
                    cancelled_at = datetime.utcnow()
                    cancel_result = ToolAdapterResult(
                        name=getattr(adapter, "name", f"adapter_{index}"),
                        status="cancelled",
                        payload={},
                        metadata=dict(adapter_meta),
                        error="cancelled due to fatal sibling",
                        started_at=started.isoformat(),
                        completed_at=cancelled_at.isoformat(),
                        elapsed_ms=int((cancelled_at - started).total_seconds() * 1000),
                        fatal=False,
                    )
                    await _dispatch_result(index, cancel_result)
                    _record(index, cancel_result)
                    raise
                except Exception as exc:  # pragma: no cover - defensive fan-out guard
                    fatal = getattr(adapter, 'fatal_on_exception', False)
                    result = ToolAdapterResult(
                        name=getattr(adapter, "name", f"adapter_{index}"),
                        status="error",
                        payload={},
                        metadata=dict(adapter_meta),
                        error=str(exc),
                        fatal=fatal,
                    )
                else:
                    if result.metadata:
                        merged = dict(adapter_meta)
                        merged.update(result.metadata)
                        result.metadata = merged
                    else:
                        result.metadata = dict(adapter_meta)
                    if result.payload is None:
                        result.payload = {}
                completed = datetime.utcnow()
                if result.started_at is None:
                    result.started_at = started.isoformat()
                if result.completed_at is None:
                    result.completed_at = completed.isoformat()
                if result.elapsed_ms is None:
                    result.elapsed_ms = int((completed - started).total_seconds() * 1000)
                await _dispatch_result(index, result)
                _record(index, result)
                if result.status == "error" and result.fatal:
                    raise _FatalAdapterException(result)
            finally:
                self._semaphore.release()

        fatal_detected = False
        try:
            async with asyncio.TaskGroup() as tg:
                for idx, adapter in enumerate(self._adapters):
                    tg.create_task(_runner(idx, adapter))
        except _FatalAdapterException:
            fatal_detected = True
        except Exception:
            raise

        ordered = [results[idx] for idx in sorted(results.keys())]

        # Ensure adapters that never started (e.g., cancelled before acquiring semaphore) appear as cancelled
        if len(ordered) < len(self._adapters):
            synthetic_results: List[ToolAdapterResult] = []
            for idx, adapter in enumerate(self._adapters):
                if idx not in results:
                    synthetic = ToolAdapterResult(
                        name=getattr(adapter, "name", f"adapter_{idx}"),
                        status="cancelled",
                        payload={},
                        metadata=adapter.get_metadata(),
                        error="cancelled before start",
                        fatal=False,
                    )
                    synthetic_results.append(synthetic)
                    _record(idx, synthetic)
                    await _dispatch_result(idx, synthetic)
            ordered = [results[idx] for idx in sorted(results.keys())]

        if fatal_detected:
            # flag results so downstream callers can surface cancellation reason
            for res in ordered:
                if res.status == "cancelled" and res.error == "cancelled due to fatal sibling":
                    res.payload.setdefault("cancelled", True)
        return ordered


# ----------------------------------------------------------------------------
# Default adapter implementations
# ----------------------------------------------------------------------------


class SQLPlannerAdapter(BaseToolAdapter):
    name = "sql_planner"
    display_name = "SQL Planner"
    description = "Preview metrics and comparisons before execution."
    capabilities = ("plan_summary", "telemetry")
    outputs = ("intent", "metrics_count", "comparison", "granularity")

    async def execute(self, context: ToolExecutionContext) -> ToolAdapterResult:
        plan = context.plan
        metrics = getattr(plan, "metrics", []) or []
        comparison = getattr(plan, "comparison", None)
        granularity = getattr(plan, "granularity", None)
        payload = {
            "intent": getattr(context.intent, "intent_key", None),
            "metrics_count": len(metrics),
            "comparison": comparison,
            "granularity": granularity,
        }
        metadata = self.get_metadata()
        metadata["summary"] = f"{len(metrics)} metric{'s' if len(metrics) != 1 else ''} planned"
        metadata["preview_keys"] = list(payload.keys())
        if metrics:
            metadata["sample_metrics"] = metrics[:3]
        return ToolAdapterResult(name=self.name, status="planned", payload=payload, metadata=metadata)


class ChartBuilderAdapter(BaseToolAdapter):
    name = "chart_builder"
    display_name = "Chart Builder"
    description = "Echo chart scaffolding before data arrives."
    capabilities = ("chart_stub", "telemetry")
    outputs = ("group_by", "timeframe")

    async def execute(self, context: ToolExecutionContext) -> ToolAdapterResult:
        plan = context.plan
        fields = {
            "group_by": getattr(plan, "group_by", []),
            "timeframe": getattr(plan, "timeframe", None),
        }
        group_by = fields.get("group_by") or []
        group_count = len(group_by)
        metadata = self.get_metadata()
        metadata["summary"] = f"{group_count} grouping{'s' if group_count != 1 else ''} staged" if group_count else "Awaiting grouping details"
        if fields.get("timeframe"):
            metadata["timeframe"] = fields["timeframe"]
        if group_by:
            metadata["group_by_preview"] = group_by[:3]
        metadata["preview_keys"] = list(fields.keys())
        return ToolAdapterResult(name=self.name, status="awaiting_data", payload=fields, metadata=metadata)



class WebRetrieverAdapter(BaseToolAdapter):
    base_name = "web_retriever"
    base_display_name = "Web Search"
    description = "Fetch fresh external context using Gemini (Google Search retrieval)."
    capabilities = ("web_context", "telemetry")
    outputs = ("query_terms", "ready", "summary", "snippets", "search_id", "annotations", "from_cache")
    preview_only = False
    _RECENCY_KEYWORDS = (
        "today",
        "latest",
        "recent",
        "news",
        "headline",
        "update",
        "guidance",
        "filing",
        "quarter",
        "earnings",
        "as of",
        "current",
    )

    def __init__(
        self,
        *,
        topic_plan: Optional[SearchTopicPlan] = None,
        topic_index: Optional[int] = None,
        topic_total: Optional[int] = None,
        base_query: Optional[str] = None,
        label_occurrence: Optional[int] = None,
        label_total: Optional[int] = None,
        research_bundle: Optional[WebResearchQuestionBundle] = None,
    ) -> None:
        self._topic_plan = topic_plan
        self._topic_index = topic_index
        self._topic_total = topic_total
        self._base_query = base_query
        self._label_occurrence = label_occurrence
        self._label_total = label_total
        self._topic_key = _normalize_topic_key(topic_plan.query) if topic_plan else None
        self._research_bundle = research_bundle
        self._topic_position: Optional[int] = None
        if isinstance(topic_index, int) and topic_index >= 0:
            self._topic_position = topic_index + 1
        elif isinstance(label_occurrence, int) and label_occurrence > 0:
            self._topic_position = label_occurrence
        if topic_plan is None:
            self.name = self.base_name
            self.display_name = self.base_display_name
        else:
            raw_suffix = topic_plan.label if isinstance(topic_plan.label, str) else ""
            suffix = raw_suffix.strip() if raw_suffix else ""
            label_from_plan = bool(suffix)
            position_value = self._topic_position
            if not suffix:
                suffix = f"Topic {position_value}" if position_value is not None else "Topic"
            slug_source = suffix if label_from_plan else ""
            base_slug = re.sub(r"[^a-z0-9]+", "-", slug_source.lower()).strip("-") if slug_source else ""
            if not base_slug:
                base_slug = f"topic-{position_value}" if position_value is not None else "topic"
            total_dupes = label_total if isinstance(label_total, int) and label_total > 0 else None
            occurrence = label_occurrence if isinstance(label_occurrence, int) and label_occurrence > 0 else None
            if total_dupes and total_dupes > 1:
                occurrence_value = occurrence or position_value or 1
                slug = f"{base_slug}-{occurrence_value}"
            else:
                slug = base_slug
            self.name = f"{self.base_name}_{slug}"[:64]
            if total_dupes and total_dupes > 1 and label_from_plan:
                occurrence_value = occurrence or position_value or 1
                suffix = f"{suffix} (Topic {occurrence_value} of {total_dupes})"
            elif not label_from_plan and position_value is not None:
                suffix = f"Topic {position_value}"
            self.display_name = f"{self.base_display_name} - {suffix}"

    @property
    def is_topic_adapter(self) -> bool:
        return self._topic_plan is not None

    def _cached_web_payload(
        self,
        context: ToolExecutionContext,
        query_terms: str,
    ) -> Optional[Tuple[Dict[str, Any], Dict[str, Any]]]:
        """Return cached web payload sourced from artifacts when Gemini search fails."""
        normalized_query = query_terms.strip().lower()
        sources = tuple(
            source for source in (getattr(context, "artifacts", None), getattr(context, "snapshot_artifacts", None)) if source
        )
        for source in sources:
            web_artifact = getattr(source, "web", None)
            if not isinstance(web_artifact, WebContextArtifact):
                continue
            cached_query = (web_artifact.query or "").strip().lower()
            if cached_query and cached_query != normalized_query:
                continue
            if not (web_artifact.summary or web_artifact.snippets):
                continue
            payload = {
                "query": web_artifact.query or query_terms,
                "query_terms": query_terms,
                "summary": web_artifact.summary,
                "snippets": copy.deepcopy(web_artifact.snippets or []),
                "search_id": web_artifact.search_id,
                "from_cache": True,
                "ready": True,
                "agent_envelope": {
                    "status": "cached",
                    "query": web_artifact.query or query_terms,
                    "summary": web_artifact.summary,
                    "error": None,
                    "retryable": True,
                    "from_cache": True,
                },
            }
            metadata = {
                "summary": "Reused cached web research.",
                "provider": "cache",
                "preview_only": False,
                "snippets_count": len(payload["snippets"]),
                "search_id": web_artifact.search_id,
                "from_cache": True,
            }
            return payload, metadata
        return None

    @staticmethod
    def _bundle_from_topics(
        plans: Sequence[SearchTopicPlan],
        *,
        base_query: str,
    ) -> Tuple[Optional[WebResearchQuestionBundle], List[SearchTopicPlan]]:
        normalized: List[SearchTopicPlan] = []
        for plan in plans:
            if not isinstance(plan, SearchTopicPlan):
                continue
            query_value = (plan.query or "").strip()
            if not query_value:
                continue
            normalized.append(
                SearchTopicPlan(
                    label=(plan.label or "Research focus").strip() or "Research focus",
                    query=query_value,
                    reason=plan.reason,
                    question_kind=plan.question_kind,
                )
            )
        if not normalized:
            fallback_query = base_query or "latest market context"
            normalized = [
                SearchTopicPlan(
                    label="Primary question",
                    query=fallback_query,
                    reason="User focus",
                    question_kind="user",
                )
            ]
        if len(normalized) == 1:
            normalized.append(
                SearchTopicPlan(
                    label="Industry context",
                    query=f"{normalized[0].query} industry outlook",
                    reason="Broader sector context",
                    question_kind="industry",
                )
            )
        if not normalized[0].question_kind:
            normalized[0].question_kind = "user"
        if not normalized[1].question_kind:
            normalized[1].question_kind = "industry"
        bundle = WebResearchQuestionBundle(
            keyword_focus=normalized[0].label or normalized[0].query or base_query,
            user_question=normalized[0].query,
            industry_question=normalized[1].query,
            source="planner_topics",
        )
        return bundle, normalized

    async def expand(self, context: ToolExecutionContext) -> Sequence["BaseToolAdapter"]:
        if self.is_topic_adapter or not has_search_api_key():
            return (self,)
        base_query = self._resolve_query_terms(context)
        if not base_query:
            return (self,)

        revision_topics_raw = tuple(getattr(context, "revision_search_topics", ()) or ())
        filtered: List[SearchTopicPlan] = []

        if revision_topics_raw:
            for raw_topic in revision_topics_raw:
                if not isinstance(raw_topic, dict):
                    continue
                query_value = str(raw_topic.get("query") or raw_topic.get("label") or "").strip()
                if not query_value:
                    continue
                label_value = str(raw_topic.get("label") or query_value).strip() or query_value
                reason_value = raw_topic.get("reason")
                reason = str(reason_value).strip() if isinstance(reason_value, str) and reason_value.strip() else None
                filtered.append(SearchTopicPlan(label=label_value, query=query_value, reason=reason))
        else:
            try:
                bundle, planned_topics = await build_web_research_questions(
                    base_query,
                    snapshot=None,
                    session_id=context.session_id,
                    min_topics=2,
                )
                self._research_bundle = bundle
            except Exception as exc:  # pragma: no cover - defensive planning guard
                logger.debug("WebRetrieverAdapter topic planning failed: %s", exc)
                return (self,)
            filtered = [
                plan for plan in planned_topics if isinstance(plan, SearchTopicPlan) and plan.query and plan.query.strip()
            ]

        allow_single_topic = bool(revision_topics_raw)
        if not filtered:
            return (self,)
        if len(filtered) <= 1 and not allow_single_topic:
            return (self,)

        if revision_topics_raw:
            bundle_for_topics, filtered = self._bundle_from_topics(filtered, base_query=base_query)
        else:
            bundle_for_topics = self._research_bundle
        label_keys: List[str] = []
        for idx, plan in enumerate(filtered):
            label_value = plan.label if isinstance(plan.label, str) else ""
            normalized_label = _normalize_topic_key(label_value) if label_value else ""
            label_keys.append(normalized_label or f"__topic_{idx}")

        label_totals: Counter[str] = Counter(label_keys)
        label_seen: defaultdict[str, int] = defaultdict(int)

        adapters: List[WebRetrieverAdapter] = []
        total = len(filtered)
        for idx, plan in enumerate(filtered):
            label_key = label_keys[idx]
            label_seen[label_key] += 1
            occurrence = label_seen[label_key]
            label_total = label_totals.get(label_key, 1)
            adapters.append(
                WebRetrieverAdapter(
                    topic_plan=plan,
                    topic_index=idx,
                    topic_total=total,
                    base_query=base_query,
                    label_occurrence=occurrence,
                    label_total=label_total,
                    research_bundle=bundle_for_topics,
                )
            )
        return tuple(adapters)

    async def execute(self, context: ToolExecutionContext) -> ToolAdapterResult:
        query_terms = self._resolve_query_terms(context)
        base_query = self._base_query or str(context.query or "").strip() or query_terms
        metadata = self.get_metadata()
        payload: Dict[str, Any] = {"query_terms": query_terms, "ready": False}
        questions_payload: Optional[Dict[str, Any]] = None
        if self._research_bundle:
            try:
                questions_payload = self._research_bundle.to_dict()
            except Exception:
                logger.debug("Failed to serialize stored web research bundle", exc_info=True)
        if self.is_topic_adapter:
            payload["topic_index"] = self._topic_index
            payload["topic_total"] = self._topic_total
            payload["topic_label"] = self._topic_plan.label if self._topic_plan else None
            if self._topic_position is not None:
                payload["topic_position"] = self._topic_position
            metadata.setdefault(
                "summary",
                f"Queued search topic: {self._topic_plan.label}" if self._topic_plan else "Topic search queued.",
            )
            metadata["topic_index"] = self._topic_index
            metadata["topic_total"] = self._topic_total
            metadata["topic_label"] = self._topic_plan.label if self._topic_plan else None
            metadata["base_query"] = base_query
            if self._topic_position is not None:
                metadata["topic_position"] = self._topic_position
        metadata["preview_keys"] = list(payload.keys())
        metadata.setdefault("summary", "Search adapter seeded with query terms.")

        if not query_terms:
            metadata["summary"] = "Waiting for query text before triggering web search."
            metadata["preview_only"] = True
            return ToolAdapterResult(name=self.name, status="queued", payload=payload, metadata=metadata)

        if not has_search_api_key():
            metadata["summary"] = "Web search disabled until GOOGLE_API_KEY or GEMINI_API_KEY is configured."
            metadata["preview_only"] = True
            metadata["error"] = "search_api_missing"
            metadata["retryable"] = False
            metadata["retryable_error_code"] = "missing_credentials"
            payload["error"] = "search_api_missing"
            payload["retryable"] = False
            return ToolAdapterResult(name=self.name, status="skip", payload=payload, metadata=metadata)

        force_revision_refresh = bool(getattr(context, "revision_directive", None)) or bool(
            getattr(context, "revision_search_topics", ())
        ) or bool(getattr(context, "force_revision_refresh", False))

        repository = get_session_state_repository()
        snapshot = await repository.load(context.session_id)
        if snapshot is None:
            snapshot = SessionStateSnapshot(session_id=context.session_id)

        cached_payload = None if force_revision_refresh else self._maybe_get_cached(snapshot, query_terms)
        if cached_payload:
            metadata["summary"] = cached_payload.get("summary") or metadata.get("summary")
            metadata["cache_hit"] = True
            metadata["preview_only"] = False
            metadata["snippets_count"] = len(cached_payload.get("snippets") or [])
            metadata["latency_ms"] = cached_payload.get("latency_ms")
            payload.update(cached_payload)
            payload["query_terms"] = query_terms
            payload["ready"] = True
            payload.setdefault("from_cache", True)
            if "latency_ms" not in payload:
                payload["latency_ms"] = 0
            if "agent_envelope" not in payload:
                payload["agent_envelope"] = {
                    "status": "reused",
                    "query": payload.get("query") or base_query,
                    "summary": payload.get("summary"),
                    "snippets": payload.get("snippets"),
                    "topics": payload.get("topics"),
                    "from_cache": True,
                }
            if self.is_topic_adapter:
                payload.setdefault("topic_index", self._topic_index)
                payload.setdefault("topic_total", self._topic_total)
                payload.setdefault("topic_label", self._topic_plan.label if self._topic_plan else None)
            if self._topic_position is not None:
                payload.setdefault("topic_position", self._topic_position)
                metadata["topic_cached"] = True
                if self._topic_position is not None:
                    metadata["topic_position"] = self._topic_position
            metadata["preview_keys"] = list(payload.keys())
            cached_questions = cached_payload.get("questions")
            if questions_payload is None and isinstance(cached_questions, MappingABC):
                questions_payload = dict(cached_questions)
            if questions_payload:
                payload["questions"] = dict(questions_payload)
                metadata["questions"] = dict(questions_payload)
                metadata["preview_keys"] = list(dict.fromkeys(metadata["preview_keys"] + ["questions"]))
            metadata["agent_envelope"] = payload.get("agent_envelope")
            return ToolAdapterResult(name=self.name, status="completed", payload=payload, metadata=metadata)

        if force_revision_refresh:
            metadata["revision_refresh"] = True

        backpressure_remaining = None if force_revision_refresh else _lane_ttl_remaining(snapshot, "web")
        if backpressure_remaining is not None:
            metadata["summary"] = (
                metadata.get("summary")
                or f"Web search throttled for {backpressure_remaining} seconds to honor TTL."
            )
            metadata["preview_only"] = True
            metadata["cache_hit"] = False
            metadata["backpressure_seconds"] = backpressure_remaining
            payload["backpressure_seconds"] = backpressure_remaining
            return ToolAdapterResult(name=self.name, status="queued", payload=payload, metadata=metadata)

        if not force_revision_refresh and not self._should_refresh(query_terms, snapshot):
            metadata["summary"] = "Web search will run when the user requests the latest context."
            metadata["preview_only"] = True
            metadata["cache_hit"] = False
            return ToolAdapterResult(name=self.name, status="queued", payload=payload, metadata=metadata)

        try:
            start_time = time.perf_counter()
            search_result = await perform_response_search(
                base_query,
                session_id=context.session_id,
                context=self._build_context(context),
                topic_plans=[self._topic_plan] if self._topic_plan else None,
            )
            elapsed_ms = int((time.perf_counter() - start_time) * 1000)
            if getattr(search_result, "latency_ms", None) is None:
                search_result.latency_ms = elapsed_ms

        except ResponseSearchError as exc:
            error_stage = getattr(exc, "stage", "unknown")
            cached_payload = self._cached_web_payload(context, query_terms)
            metadata["error"] = str(exc)
            metadata["error_stage"] = error_stage
            metadata["retryable_error_code"] = getattr(exc, "code", None) or f"search_{error_stage}"
            metadata["retryable"] = bool(getattr(exc, "retryable", True))
            payload["error"] = str(exc)
            payload["error_stage"] = error_stage
            payload["retryable"] = metadata["retryable"]
            if cached_payload:
                cached_result, cached_meta = cached_payload
                payload.update(cached_result)
                metadata.update(cached_meta)
                metadata["preview_keys"] = list(payload.keys())
                metadata["agent_envelope"] = payload.get("agent_envelope")
                logger.warning(
                    "WebRetrieverAdapter search failed during %s; reused cached payload.",
                    error_stage,
                )
                return ToolAdapterResult(
                    name=self.name,
                    status="completed",
                    payload=payload,
                    metadata=metadata,
                )
            metadata["summary"] = "Web search unavailable (Gemini search error)."
            metadata["preview_only"] = True
            payload["agent_envelope"] = {
                "status": "error",
                "query": base_query,
                "summary": None,
                "error": str(exc),
                "error_code": metadata["retryable_error_code"],
                "retryable": metadata["retryable"],
                "from_cache": False,
            }
            existing_keys = metadata.get("preview_keys", list(payload.keys()))
            metadata["preview_keys"] = list(dict.fromkeys(list(existing_keys) + list(payload.keys())))
            metadata["agent_envelope"] = payload["agent_envelope"]
            logger.warning("WebRetrieverAdapter search failed during %s: %s", error_stage, exc)
            return ToolAdapterResult(
                name=self.name,
                status="error",
                payload=payload,
                metadata=metadata,
                error=str(exc),
            )

        result_payload = search_result.to_payload()
        result_payload["query_terms"] = query_terms
        result_payload["ready"] = True
        result_payload["from_cache"] = False
        if search_result.latency_ms is not None:
            result_payload["latency_ms"] = search_result.latency_ms
        existing_questions = getattr(search_result, "questions", None)
        if questions_payload is None and isinstance(existing_questions, MappingABC):
            questions_payload = dict(existing_questions)
        elif questions_payload is not None:
            if not existing_questions:
                setattr(search_result, "questions", dict(questions_payload))
        if self.is_topic_adapter:
            result_payload.setdefault("search_topics", [self._topic_plan.query])
            result_payload["topic_index"] = self._topic_index
            result_payload["topic_total"] = self._topic_total
            result_payload["topic_label"] = self._topic_plan.label if self._topic_plan else None
            result_payload["base_query"] = base_query
            if self._topic_position is not None:
                result_payload["topic_position"] = self._topic_position
        agent_envelope = search_result.to_agent_envelope(cached=False)
        result_payload["agent_envelope"] = agent_envelope
        payload.update(result_payload)
        metadata["summary"] = search_result.summary or "Web search results ready."
        metadata["preview_only"] = False
        metadata["snippets_count"] = len(result_payload.get("snippets") or [])
        metadata["latency_ms"] = search_result.latency_ms
        metadata["search_id"] = search_result.search_id
        metadata["provider"] = "Gemini"
        if getattr(search_result, "model", None):
            metadata["model"] = search_result.model
        if self.is_topic_adapter:
            metadata["topic_index"] = self._topic_index
            metadata["topic_total"] = self._topic_total
            metadata["topic_label"] = self._topic_plan.label if self._topic_plan else None
            metadata["base_query"] = base_query
            metadata["search_query"] = query_terms
            if self._topic_position is not None:
                metadata["topic_position"] = self._topic_position
        if questions_payload:
            payload["questions"] = dict(questions_payload)
            metadata["questions"] = dict(questions_payload)
        metadata["preview_keys"] = list(payload.keys())
        metadata["agent_envelope"] = agent_envelope

        cache_payload = dict(result_payload)
        cache_payload.setdefault("query", base_query)
        cache_payload.setdefault("query_terms", query_terms)
        cache_payload["ready"] = True
        if questions_payload:
            cache_payload["questions"] = dict(questions_payload)

        await self._record_cache(
            repository,
            snapshot,
            cache_payload,
            base_query=base_query,
        )
        if snapshot is not None and questions_payload:
            try:
                snapshot.record_web_research_questions(questions_payload)
            except Exception:
                logger.debug("Failed to persist web research questions on snapshot", exc_info=True)

        return ToolAdapterResult(name=self.name, status="completed", payload=payload, metadata=metadata)

    def _resolve_query_terms(self, context: ToolExecutionContext) -> str:
        if self._topic_plan and isinstance(self._topic_plan.query, str):
            return self._topic_plan.query.strip()
        revision_focus = getattr(context, "revision_focus", None)
        if isinstance(revision_focus, str) and revision_focus.strip():
            return revision_focus.strip()
        slots = getattr(context.intent, "slots_detected", {}) or {}
        return str(slots.get("original_query") or context.query or "").strip()

    def _maybe_get_cached(self, snapshot: SessionStateSnapshot, query_terms: str) -> Optional[Dict[str, Any]]:
        if snapshot is None:
            return None

        normalized = query_terms.strip().lower()
        if self._topic_key:
            topic_cache = (snapshot.tool_cache or {}).get("web_search_topics") or {}
            cached_topic = topic_cache.get(self._topic_key)
            if not isinstance(cached_topic, dict):
                return None
            cached_query = str(cached_topic.get("query_terms") or cached_topic.get("query") or "").strip().lower()
            if cached_query and cached_query != normalized:
                return None
            cached = dict(cached_topic)
            cached["from_cache"] = True
            cached.setdefault("ready", True)
            if self._topic_position is not None:
                cached.setdefault("topic_position", self._topic_position)
            return cached

        cache = (snapshot.tool_cache or {}).get("web_search")
        if not isinstance(cache, dict):
            return None
        cached_query = str(cache.get("query") or cache.get("query_terms") or "").strip().lower()
        if cached_query and cached_query == normalized:
            cached = dict(cache)
            cached["from_cache"] = True
            cached.setdefault("ready", True)
            if self._topic_position is not None:
                cached.setdefault("topic_position", self._topic_position)
            return cached
        return None

    def _should_refresh(self, query_terms: str, snapshot: Optional[SessionStateSnapshot]) -> bool:
        normalized = query_terms.strip().lower()
        if any(keyword in normalized for keyword in self._RECENCY_KEYWORDS):
            return True
        if snapshot is None:
            return True
        if self._topic_key:
            topic_cache = (snapshot.tool_cache or {}).get("web_search_topics") or {}
            cached = topic_cache.get(self._topic_key)
            if not isinstance(cached, dict):
                return True
            cached_query = str(cached.get("query_terms") or cached.get("query") or "").strip().lower()
            return cached_query != normalized
        cache = snapshot.tool_cache.get("web_search") if snapshot.tool_cache else None
        if not cache:
            return True
        cached_query = str(cache.get("query") or cache.get("query_terms") or "").strip().lower()
        if cached_query and cached_query != normalized:
            return True
        return False

    def _build_context(self, context: ToolExecutionContext) -> Optional[str]:
        intent = getattr(context.intent, "intent_key", None)
        plan = context.plan
        metrics = []
        if plan is not None:
            metrics = list(getattr(plan, "metrics", []) or [])
        parts: List[str] = []
        if intent:
            parts.append(f"Intent: {intent}.")
        if metrics:
            parts.append("Focus metrics: " + ", ".join(metrics[:3]))
        if self._topic_plan and self._topic_plan.label:
            parts.append(f"Topic: {self._topic_plan.label}")
        configs = context.configs if isinstance(context.configs, dict) else {}
        assumptions = configs.get("assumptions")
        if isinstance(assumptions, list) and assumptions:
            parts.append("Assumptions: " + "; ".join(str(item) for item in assumptions[:2]))
        return " ".join(parts) if parts else None

    async def _record_cache(
        self,
        repository: Any,
        snapshot: SessionStateSnapshot,
        payload: Dict[str, Any],
        *,
        base_query: str,
    ) -> None:
        payload = dict(payload)
        payload.setdefault("ready", True)
        payload.setdefault("query", base_query)
        if self._topic_position is not None:
            payload.setdefault("topic_position", self._topic_position)

        if self._topic_key:
            topic_cache = snapshot.tool_cache.setdefault("web_search_topics", {})
            topic_cache[self._topic_key] = payload
            merged = _merge_web_payloads(list(topic_cache.values()), base_query=base_query)
            if merged:
                snapshot.record_tool_result("web_search", merged)
        else:
            snapshot.record_tool_result("web_search", payload)
        await repository.save(snapshot)

class StockTrackerAdapter(BaseToolAdapter):
    name = "stock_tracker"
    display_name = "Stock Tracker"
    description = "Fetch live stock snapshots for planner tickers."
    capabilities = ("market_data", "telemetry")
    outputs = ("tickers", "ready", "insights", "bars", "stock_widget")

    _TICKER_BLACKLIST = {"WITH", "FROM", "AND", "THE", "WHERE", "SELECT", "JOIN"}

    def _cached_market_snapshot(
        self,
        context: ToolExecutionContext,
        symbol: str,
    ) -> Optional[Dict[str, Any]]:
        """Reuse a cached market snapshot when live Polygon data is unavailable."""
        symbol_key = symbol.upper()
        sources = tuple(
            source for source in (getattr(context, "artifacts", None), getattr(context, "snapshot_artifacts", None)) if source
        )
        for source in sources:
            market_artifact = getattr(source, "market", None)
            if not isinstance(market_artifact, MarketArtifact):
                continue
            snapshot = getattr(market_artifact, "snapshot", None)
            if not isinstance(snapshot, Mapping):
                continue
            tracked = {ticker.strip().upper() for ticker in (market_artifact.tickers or []) if isinstance(ticker, str)}
            if tracked and symbol_key not in tracked:
                continue
            cached_payload = dict(snapshot)
            cached_payload.setdefault("symbol", symbol_key)
            cached_payload.setdefault("bars", snapshot.get("bars") or [])
            cached_payload["ready"] = True
            cached_payload["from_cache"] = True
            if "fetched_at" not in cached_payload:
                cached_payload["fetched_at"] = datetime.utcnow().isoformat()
            return cached_payload
        return None

    async def execute(self, context: ToolExecutionContext) -> ToolAdapterResult:
        slots = getattr(context.intent, "slots_detected", {}) or {}
        query = (context.query or "").strip()

        def _normalize_candidates(raw: Any) -> List[str]:
            ordered: List[str] = []
            candidates: List[str] = []
            if isinstance(raw, str):
                candidates.append(raw)
            elif isinstance(raw, (list, tuple, set)):
                candidates.extend(str(item) for item in raw)
            deduped: List[str] = []
            for item in candidates:
                symbol = str(item).strip().upper()
                if symbol and symbol not in deduped:
                    deduped.append(symbol)
            if query:
                for match in re.finditer(r"[A-Za-z0-9\.]{2,6}", query):
                    token = match.group(0).strip().upper()
                    if token in deduped and token not in ordered:
                        ordered.append(token)
            for symbol in deduped:
                if symbol not in ordered:
                    ordered.append(symbol)
            return ordered

        company_candidates = _normalize_candidates(slots.get("company"))
        ticker_candidates = _normalize_candidates(slots.get("tickers"))

        tickers: List[str] = []
        if company_candidates or ticker_candidates:
            seen_candidates: Set[str] = set()
            for symbol in company_candidates + ticker_candidates:
                if symbol and symbol not in seen_candidates:
                    tickers.append(symbol)
                    seen_candidates.add(symbol)

        if not tickers and query:
            inferred: List[str] = []
            seen: Set[str] = set()
            for match in re.finditer(r"\b[A-Z]{2,5}\b", query):
                token = match.group(0).upper()
                if token not in self._TICKER_BLACKLIST and token not in seen:
                    inferred.append(token)
                    seen.add(token)
            tickers = inferred[:3]
        payload: Dict[str, Any] = {
            "tickers": tickers,
            "ready": False,
        }
        metadata = self.get_metadata()
        metadata["preview_keys"] = list(payload.keys())

        repository = get_session_state_repository()
        snapshot: Optional[SessionStateSnapshot] = None
        try:
            snapshot = await repository.load(context.session_id)
        except Exception:
            logger.debug("Failed to load session snapshot for market TTL checks", exc_info=True)

        def _snapshot_cached_payload(symbol_key: str) -> Optional[Dict[str, Any]]:
            cache = snapshot.tool_cache if snapshot and isinstance(snapshot.tool_cache, dict) else {}
            cached_widget = cache.get("planner_stock_widget")
            if not isinstance(cached_widget, Mapping):
                return None
            cached_symbol = str(cached_widget.get("symbol") or cached_widget.get("ticker") or "").upper()
            if cached_symbol and cached_symbol != symbol_key:
                return None
            cached = dict(cached_widget)
            cached.setdefault("symbol", symbol_key)
            cached.setdefault("ready", True)
            cached.setdefault("from_cache", True)
            return cached

        widget_symbols: List[List[str]] = []
        for raw in tickers:
            symbol = raw.upper()
            if ":" in symbol:
                base, alias = symbol.split(":", 1)
                widget_symbols.append([symbol, alias or base])
            else:
                widget_symbols.append([f"NASDAQ:{symbol}", symbol])
        widget_config: Optional[Dict[str, Any]] = None
        if widget_symbols:
            locale = "en"
            configs = getattr(context, "configs", {})
            if isinstance(configs, dict):
                locale = configs.get("locale", locale)
            widget_config = {
                "symbols": widget_symbols,
                "original": tickers,
                "chartType": "candlesticks",
                "showVolume": True,
                "showMA": False,
                "autosize": True,
                "height": 440,
                "locale": locale,
            }
            payload["stock_widget"] = widget_config
            metadata["preview_keys"].append("stock_widget")

        if not tickers:
            metadata["summary"] = "No planner tickers detected; market snapshot idle."
            metadata["preview_only"] = True
            return ToolAdapterResult(
                name=self.name,
                status="queued",
                payload=payload,
                metadata=metadata,
            )

        remaining_market_ttl = _lane_ttl_remaining(snapshot, "market")

        client = PolygonMarketDataClient()
        if not getattr(client, "is_configured", False):
            metadata["summary"] = "Polygon client not configured; showing TradingView fallback."
            metadata["preview_only"] = False
            payload["ready"] = False
            metadata["retryable"] = False
            metadata["retryable_error_code"] = "polygon_not_configured"
            payload["retryable"] = False
            return ToolAdapterResult(
                name=self.name,
                status="completed",
                payload=payload,
                metadata=metadata,
            )

        symbol = tickers[0].upper()
        cached_market = _snapshot_cached_payload(symbol)
        if remaining_market_ttl is not None:
            if cached_market:
                payload.update(copy.deepcopy(cached_market))
                metadata["summary"] = metadata.get("summary") or "Reused cached market snapshot inside TTL."
                metadata["from_cache"] = True
                metadata["preview_only"] = False
                metadata["preview_keys"] = sorted(set(metadata.get("preview_keys", [])))
                return ToolAdapterResult(
                    name=self.name,
                    status="completed",
                    payload=payload,
                    metadata=metadata,
                )

            metadata["summary"] = (
                metadata.get("summary")
                or "Market snapshot throttled until TTL expires to avoid hammering Polygon."
            )
            metadata["preview_only"] = True
            metadata["backpressure_seconds"] = remaining_market_ttl
            payload["backpressure_seconds"] = remaining_market_ttl
            return ToolAdapterResult(
                name=self.name,
                status="queued",
                payload=payload,
                metadata=metadata,
            )

        if cached_market and not remaining_market_ttl:
            payload.update(copy.deepcopy(cached_market))
            metadata["summary"] = metadata.get("summary") or "Reused cached market snapshot."
            metadata["from_cache"] = True
            metadata["preview_only"] = False
            metadata["preview_keys"] = sorted(set(metadata.get("preview_keys", [])))
            return ToolAdapterResult(
                name=self.name,
                status="completed",
                payload=payload,
                metadata=metadata,
            )

        start_time = time.perf_counter()
        try:
            snapshot = await fetch_daily_snapshot(symbol, client=client)
        except PolygonError as exc:
            error_message = str(exc)
            cached_snapshot = self._cached_market_snapshot(context, symbol)
            error_code = "polygon_rate_limited" if getattr(exc, "status_code", None) == 429 else "polygon_error"
            metadata["error"] = error_message
            metadata["retryable_error_code"] = error_code
            metadata["retryable"] = True
            payload["error"] = error_message
            payload["retryable"] = True
            if cached_snapshot:
                payload.update({key: copy.deepcopy(value) for key, value in cached_snapshot.items()})
                metadata["summary"] = f"Reused cached market snapshot for {cached_snapshot.get('symbol')} (live fetch unavailable)."
                metadata["from_cache"] = True
                metadata["preview_only"] = False
                metadata["preview_keys"] = sorted(set(metadata.get("preview_keys", [])))
                return ToolAdapterResult(
                    name=self.name,
                    status="completed",
                    payload=payload,
                    metadata=metadata,
                )
            metadata["summary"] = f"Polygon error for {symbol}: {error_message}"
            return ToolAdapterResult(
                name=self.name,
                status="error",
                payload=payload,
                metadata=metadata,
            )

        elapsed_ms = int((time.perf_counter() - start_time) * 1000)
        bars = snapshot.bars[-30:]
        formatted_bars = [
            {
                "time": bar.time,
                "open": round(bar.open, 2),
                "high": round(bar.high, 2),
                "low": round(bar.low, 2),
                "close": round(bar.close, 2),
                "volume": int(bar.volume),
            }
            for bar in bars
        ]
        payload.update(
            {
                "ready": True,
                "symbol": snapshot.symbol,
                "latest_close": snapshot.latest_close,
                "previous_close": snapshot.previous_close,
                "change_percent": snapshot.change_percent,
                "bars": formatted_bars,
                "chartType": payload.get("chartType") or "candlestick",
                "showVolume": payload.get("showVolume", True),
                "showMA": payload.get("showMA", False),
                "autosize": payload.get("autosize", True),
                "fetched_at": datetime.utcnow().isoformat(),
                "insights": {
                    "symbol": snapshot.symbol,
                    "latest_close": snapshot.latest_close,
                    "previous_close": snapshot.previous_close,
                    "change_percent": snapshot.change_percent,
                },
            }
        )
        if widget_config:
            payload["stock_widget"] = {
                **widget_config,
                "chartType": payload.get("chartType"),
                "showVolume": payload.get("showVolume"),
                "showMA": payload.get("showMA"),
                "autosize": payload.get("autosize"),
                "height": widget_config.get("height", 440),
            }

        metadata["summary"] = (
            f"{snapshot.symbol} close {snapshot.latest_close:.2f}"
            + (
                f" ({snapshot.change_percent:+.2f}% vs prior close)"
                if snapshot.change_percent is not None
                else ""
            )
        )
        metadata["preview_only"] = False
        metadata["preview_keys"] = sorted(set(metadata["preview_keys"]))
        metadata["latency_ms"] = elapsed_ms
        payload["latency_ms"] = elapsed_ms

        return ToolAdapterResult(
            name=self.name,
            status="completed",
            payload=payload,
            metadata=metadata,
        )


class MarketQuestionAdapter(StockTrackerAdapter):
    """Stock tracker wrapper that tags outputs for specific market questions."""

    def __init__(self, alias: str, label: str) -> None:
        super().__init__()
        self.name = alias
        self.display_name = label
        self._question_id = alias

    async def execute(self, context: ToolExecutionContext) -> ToolAdapterResult:  # type: ignore[override]
        result = await super().execute(context)
        if isinstance(result.metadata, dict):
            meta = dict(result.metadata)
        else:
            meta = {}
        meta.setdefault("question_id", self._question_id)
        result.metadata = meta
        if isinstance(result.payload, dict):
            payload = dict(result.payload)
            payload.setdefault("question_id", self._question_id)
            result.payload = payload
        return result


class NarrativeSynthesizerAdapter(BaseToolAdapter):
    name = "narrative_synthesizer"
    display_name = "Narrative Synthesizer"
    description = "Draft narrative preview text from planned metrics."
    capabilities = ("analysis_preview", "telemetry")
    outputs = ("preview",)

    async def execute(self, context: ToolExecutionContext) -> ToolAdapterResult:
        plan = context.plan
        metrics = getattr(plan, "metrics", []) or []
        preview = f"Preparing narrative for {', '.join(metrics[:3]) or 'selected metrics'}"
        payload = {
            "preview": preview,
        }
        metadata = self.get_metadata()
        metadata["summary"] = preview
        if metrics:
            metadata["sample_metrics"] = metrics[:3]
        metadata["preview_keys"] = list(payload.keys())
        return ToolAdapterResult(name=self.name, status="drafting", payload=payload, metadata=metadata)


_DEFAULT_ADAPTERS: Tuple[BaseToolAdapter, ...] = (
    SQLPlannerAdapter(),
    ChartBuilderAdapter(),
    WebRetrieverAdapter(),
    StockTrackerAdapter(),
    NarrativeSynthesizerAdapter(),
)


def get_default_tool_adapters() -> Tuple[BaseToolAdapter, ...]:
    return _DEFAULT_ADAPTERS




def _resolve_concurrency_limit(
    ctx: "PlannerPhaseContext",
    default: int = 5,
    *,
    max_size: Optional[int] = None,
) -> int:
    configs = getattr(ctx, "configs", {}) or {}
    limit: Optional[int] = None

    if isinstance(configs, dict):
        tooling_cfg = configs.get("tooling")
        if isinstance(tooling_cfg, dict):
            value = tooling_cfg.get("concurrency_limit")
            if isinstance(value, int):
                limit = value
        if limit is None:
            analytics_cfg = configs.get("analytics")
            if isinstance(analytics_cfg, dict):
                fanout_cfg = analytics_cfg.get("tool_parallelism")
                if isinstance(fanout_cfg, dict):
                    value = fanout_cfg.get("concurrency_limit")
                    if isinstance(value, int):
                        limit = value

    env_value = os.getenv("ANALYTICS_TOOL_CONCURRENCY_LIMIT")
    if env_value is not None:
        try:
            parsed = int(env_value)
            if parsed >= 1:
                limit = parsed
        except ValueError:
            pass

    if limit is None or limit < 1:
        limit = default
    if max_size is not None and max_size >= 1:
        return min(limit, max_size)
    return limit

async def run_tool_parallelism(
    ctx: "PlannerPhaseContext",
    *,
    adapters: Optional[Sequence[BaseToolAdapter]] = None,
    concurrency_override: Optional[int] = None,
) -> AsyncGenerator[Dict[str, Any], None]:
    """Execute the registered tool adapters and yield telemetry events."""

    intent = getattr(ctx, "intent", None)
    plan = getattr(ctx, "plan", None) or getattr(ctx, "provisional_plan", None)
    force_revision_refresh = bool(getattr(ctx, "force_revision_refresh", False))
    forced_refresh_context = force_revision_refresh or bool(getattr(ctx, "revision_search_topics", ()))
    if forced_refresh_context and (intent is None or plan is None):
        query_text = str(getattr(ctx, "query", "") or "").strip()
        if intent is None:
            slots = {"original_query": query_text} if query_text else {}
            intent = IntentModel(intent_key="revision_refresh", slots_detected=slots)
            ctx.intent = intent
        if plan is None:
            plan = QueryPlanModel()
            ctx.plan = plan
            ctx.provisional_plan = plan
        logger.warning(
            "tool_parallelism.forced_refresh_missing_planner_state",
            extra={
                "session_id": getattr(ctx, "session_id", None),
                "reason": "fallback_intent_plan_injected",
            },
        )
    if not intent or not plan:
        return

    selected_adapters: Tuple[BaseToolAdapter, ...] = (
        tuple(adapters) if adapters is not None else get_default_tool_adapters()
    )
    if not selected_adapters:
        return

    directive = getattr(ctx, "revision_directive", None)
    revision_focus: Optional[str] = None
    revision_topics: Tuple[Dict[str, Any], ...] = tuple()
    if directive is not None:
        focus_candidate = getattr(directive, "requested_focus", None) or getattr(directive, "raw_text", None)
        if isinstance(focus_candidate, str) and focus_candidate.strip():
            revision_focus = focus_candidate.strip()
        topics_iterable = getattr(directive, "search_topics", None)
        if topics_iterable:
            normalized_topics: List[Dict[str, Any]] = []
            for topic in topics_iterable:
                if not isinstance(topic, dict):
                    continue
                query_value = str(topic.get("query") or topic.get("label") or "").strip()
                if not query_value:
                    continue
                entry: Dict[str, Any] = {
                    "label": str(topic.get("label") or query_value).strip() or query_value,
                    "query": query_value,
                }
                reason_value = topic.get("reason")
                if isinstance(reason_value, str) and reason_value.strip():
                    entry["reason"] = reason_value.strip()
                normalized_topics.append(entry)
            if normalized_topics:
                revision_topics = tuple(normalized_topics)

    execution_context = ToolExecutionContext(
        session_id=ctx.session_id,
        query=ctx.query,
        intent=intent,
        plan=plan,
        template=getattr(ctx, "template", None),
        configs=getattr(ctx, "configs", {}),
        revision_directive=directive,
        revision_focus=revision_focus,
        revision_search_topics=revision_topics,
        artifacts=getattr(ctx, "artifacts", None),
        snapshot_artifacts=getattr(ctx, "snapshot_artifacts", None),
    )

    expanded_adapters: List[BaseToolAdapter] = []
    for adapter in selected_adapters:
        try:
            expanded = await adapter.expand(execution_context)
        except Exception:  # pragma: no cover - defensive expansion guard
            logger.exception(
                "tool_parallelism.expand_failed",
                extra={"adapter": getattr(adapter, "name", None)},
            )
            expanded = (adapter,)
        if not expanded:
            continue
        expanded_adapters.extend(expanded)
    selected_adapters = tuple(expanded_adapters)
    if not selected_adapters:
        return

    tool_manifests = [adapter.get_metadata() for adapter in selected_adapters]

    tool_count = len(selected_adapters)
    default_concurrency = tool_count
    if concurrency_override is not None:
        try:
            concurrency_limit = int(concurrency_override)
        except (TypeError, ValueError):
            concurrency_limit = tool_count
    elif hasattr(ctx, "tool_parallel_concurrency") and isinstance(
        getattr(ctx, "tool_parallel_concurrency", None), (int, float)
    ):
        concurrency_limit = max(1, int(getattr(ctx, "tool_parallel_concurrency")))
    else:
        concurrency_limit = _resolve_concurrency_limit(
            ctx,
            default=default_concurrency,
            max_size=None,
        )
    if concurrency_limit < tool_count:
        concurrency_limit = tool_count
    if adapters is None:
        ctx.tool_parallel_manifest = tool_manifests
        ctx.tool_parallel_results = []
    else:
        existing_manifest = getattr(ctx, "tool_parallel_manifest", []) or []
        ctx.tool_parallel_manifest = [*existing_manifest, *tool_manifests]
        ctx.tool_parallel_results = getattr(ctx, "tool_parallel_results", []) or []
    ctx.tool_parallel_concurrency = concurrency_limit
    telemetry.tool_parallelism(
        stage="start",
        session_id=getattr(ctx, "session_id", None),
        flow=getattr(ctx, "flow_label", None),
        payload={
            "tool_group": "single_agent",
            "parallel_group": "tool_fanout",
            "tool_count": len(selected_adapters),
            "concurrency_limit": concurrency_limit,
            "tools": tool_manifests,
        },
    )
    yield {
        "event": "tool_parallel_start",
        "data": {
            "tool_group": "single_agent",
            "parallel_group": "tool_fanout",
            "tool_count": len(selected_adapters),
            "concurrency_limit": concurrency_limit,
            "tools": tool_manifests,
            "ts": datetime.utcnow().isoformat(),
        },
    }

    task_group = ToolTaskGroup(selected_adapters, concurrency_limit=concurrency_limit)
    result_queue: asyncio.Queue[Dict[str, Any]] = asyncio.Queue()
    total_expected = len(selected_adapters)
    fatal_detected = False

    async def _handle_result(result: ToolAdapterResult) -> None:
        nonlocal fatal_detected
        payload_for_context = (
            copy.deepcopy(result.payload) if result.payload is not None else {}
        )
        metadata_for_context = (
            copy.deepcopy(result.metadata) if result.metadata is not None else {}
        )
        serialized = {
            "tool": result.name,
            "status": result.status,
            "payload": payload_for_context,
            "metadata": metadata_for_context,
            "error": result.error,
            "elapsed_ms": result.elapsed_ms,
            "started_at": result.started_at,
            "completed_at": result.completed_at,
            "fatal": result.fatal,
        }
        ctx.tool_parallel_results.append(serialized)
        if len(ctx.tool_parallel_results) > 10:
            ctx.tool_parallel_results = ctx.tool_parallel_results[-10:]
        telemetry.tool_parallelism(
            stage="result",
            session_id=getattr(ctx, "session_id", None),
            flow=getattr(ctx, "flow_label", None),
            payload={**serialized, "concurrency_limit": concurrency_limit},
        )
        if result.status == "error" and result.fatal:
            fatal_detected = True
        event_payload = {
            "tool": result.name,
            "status": result.status,
            "payload": copy.deepcopy(serialized["payload"]),
            "metadata": copy.deepcopy(serialized["metadata"]),
            "error": result.error,
            "elapsed_ms": result.elapsed_ms,
            "started_at": result.started_at,
            "completed_at": result.completed_at,
            "fatal": result.fatal,
            "parallel_group": "tool_fanout",
            "tool_group": "single_agent",
            "concurrency_limit": concurrency_limit,
            "ts": datetime.utcnow().isoformat(),
        }
        await result_queue.put({"event": "tool_parallel_result", "data": event_payload})

    task = asyncio.create_task(task_group.run(execution_context, on_result=_handle_result))
    results: List[ToolAdapterResult] = []

    try:
        emitted = 0
        while emitted < total_expected:
            event = await result_queue.get()
            emitted += 1
            yield event

        # Drain any remaining events that might have arrived while awaiting completion.
        while not result_queue.empty():
            yield result_queue.get_nowait()

        results = await task
    finally:
        if not task.done():
            task.cancel()
            with contextlib.suppress(Exception):
                await task
    if not fatal_detected:
        fatal_detected = any(result.status == "error" and result.fatal for result in results)

    completion_status = "cancelled" if fatal_detected else "complete"
    telemetry.tool_parallelism(
        stage="complete",
        session_id=getattr(ctx, "session_id", None),
        flow=getattr(ctx, "flow_label", None),
        payload={
            "status": completion_status,
            "concurrency_limit": concurrency_limit,
            "tool_group": "single_agent",
            "parallel_group": "tool_fanout",
        },
    )
    yield {
        "event": "tool_parallel_complete",
        "data": {
            "tool_group": "single_agent",
            "parallel_group": "tool_fanout",
            "status": completion_status,
            "concurrency_limit": concurrency_limit,
            "ts": datetime.utcnow().isoformat(),
        },
    }
