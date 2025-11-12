# --- Analytics Function/Class Map ---
# Function: _build_tool_metadata
#   Role: Handles build tool metadata logic for analytics.flows.multi_agent.
#   Called from: Internal to analytics.flows.multi_agent
#   Invokes: Internal helpers only
#   Why: Keeps analytics.flows.multi_agent from duplicating build tool metadata behavior across flows.
# Class: _MultiAgentHooks
#   Role: Handles MultiAgentHooks logic for analytics.flows.multi_agent.
#   Called from: tests.analytics.test_multi_agent_flow
#   Collaborators: Internal helpers only
#   Why: Keeps analytics.flows.multi_agent from duplicating MultiAgentHooks behavior across flows.
# Function: _make_identifier
#   Role: Handles make identifier logic for analytics.flows.multi_agent.
#   Called from: Internal to analytics.flows.multi_agent
#   Invokes: hashlib.sha1
#   Why: Keeps analytics.flows.multi_agent from duplicating make identifier behavior across flows.
# Function: _canonical_tool_name
#   Role: Handles canonical tool name logic for analytics.flows.multi_agent.
#   Called from: Internal to analytics.flows.multi_agent
#   Invokes: Internal helpers only
#   Why: Keeps analytics.flows.multi_agent from duplicating canonical tool name behavior across flows.
# Function: _infer_tickers
#   Role: Handles infer tickers logic for analytics.flows.multi_agent.
#   Called from: Internal to analytics.flows.multi_agent
#   Invokes: re.findall
#   Why: Keeps analytics.flows.multi_agent from duplicating infer tickers behavior across flows.
# Function: _normalize_chart_spec_payload
#   Role: Unwrap common chart payload wrappers down to the ECharts option dict.
#   Called from: Internal to analytics.flows.multi_agent
#   Invokes: analytics.flows.multi_agent._normalize_chart_spec_payload
#   Why: Supports downstream analytics workflows that rely on _normalize_chart_spec_payload.
# Function: _needs_web_refresh
#   Role: Handles needs web refresh logic for analytics.flows.multi_agent.
#   Called from: Internal to analytics.flows.multi_agent
#   Invokes: Internal helpers only
#   Why: Keeps analytics.flows.multi_agent from duplicating needs web refresh behavior across flows.
# Function: _derive_tasks
#   Role: Handles derive tasks logic for analytics.flows.multi_agent.
#   Called from: tests.analytics.test_multi_agent_flow, tests.analytics.test_revision_followups
#   Invokes: analytics.flows.task_plan.AgentTaskPlan, analytics.flows.chart_revision.is_chart_revision_query, analytics.flows.chart_revision.infer_chart_patch_from_query, analytics.flows.multi_agent._needs_web_refresh
#   Why: Keeps analytics.flows.multi_agent from duplicating derive tasks behavior across flows.
# Function: _task_status
#   Role: Return the status for a task by name regardless of container type.
#   Called from: Internal to analytics.flows.multi_agent
#   Invokes: Internal helpers only
#   Why: Supports downstream analytics workflows that rely on _task_status.
# Function: _create_planner_bundle
#   Role: Handles create planner bundle logic for analytics.flows.multi_agent.
#   Called from: tests.analytics.test_multi_agent_bundle
#   Invokes: analytics.validators.sanitize_for_json, json.dumps, analytics.flows.multi_agent._make_identifier, copy.deepcopy
#   Why: Keeps analytics.flows.multi_agent from duplicating create planner bundle behavior across flows.
# Function: _planner_agent
#   Role: Handles planner agent logic for analytics.flows.multi_agent.
#   Called from: tests.analytics.test_multi_agent_flow
#   Invokes: analytics.flows.multi_agent._derive_tasks, analytics.flows.multi_agent._create_planner_bundle, analytics.core.telemetry.agent_handoff, analytics.flows.orchestrator.AgentResult
#   Why: Keeps analytics.flows.multi_agent from duplicating planner agent behavior across flows.
# Function: _query_agent
#   Role: Handles query agent logic for analytics.flows.multi_agent.
#   Called from: tests.analytics.test_multi_agent_flow
#   Invokes: analytics.flows.multi_agent._task_status, analytics.flows.orchestrator.AgentResult
#   Why: Keeps analytics.flows.multi_agent from duplicating query agent behavior across flows.
# Function: _analyst_agent
#   Role: Handles analyst agent logic for analytics.flows.multi_agent.
#   Called from: Internal to analytics.flows.multi_agent
#   Invokes: analytics.flows.multi_agent._task_status, analytics.flows.orchestrator.AgentResult
#   Why: Keeps analytics.flows.multi_agent from duplicating analyst agent behavior across flows.
# Function: _chart_agent
#   Role: Handles chart agent logic for analytics.flows.multi_agent.
#   Called from: Internal to analytics.flows.multi_agent
#   Invokes: analytics.flows.multi_agent._task_status, analytics.flows.orchestrator.AgentResult
#   Why: Keeps analytics.flows.multi_agent from duplicating chart agent behavior across flows.
# Function: _market_agent
#   Role: Handles market agent logic for analytics.flows.multi_agent.
#   Called from: tests.analytics.test_multi_agent_flow
#   Invokes: analytics.flows.multi_agent._task_status, analytics.flows.orchestrator.AgentResult, analytics.core.telemetry.policy_decision, asyncio.wait_for
#   Why: Keeps analytics.flows.multi_agent from duplicating market agent behavior across flows.
# Function: _web_research_agent
#   Role: Handles web research agent logic for analytics.flows.multi_agent.
#   Called from: tests.analytics.test_multi_agent_flow, tests.analytics.test_web_research
#   Invokes: analytics.flows.multi_agent._task_status, analytics.core.session_state.get_session_state_repository, analytics.flows.orchestrator.AgentResult, analytics.flows.planner_executor._evaluate_latency_guardrail, +2 more
#   Why: Keeps analytics.flows.multi_agent from duplicating web research agent behavior across flows.
# Function: _build_default_agent_registry
#   Role: Handles build default agent registry logic for analytics.flows.multi_agent.
#   Called from: Internal to analytics.flows.multi_agent
#   Invokes: analytics.flows.orchestrator.AgentSpec
#   Why: Keeps analytics.flows.multi_agent from duplicating build default agent registry behavior across flows.
# Function: _build_default_plan
#   Role: Handles build default plan logic for analytics.flows.multi_agent.
#   Called from: Internal to analytics.flows.multi_agent
#   Invokes: analytics.flows.orchestrator.AgentTask
#   Why: Keeps analytics.flows.multi_agent from duplicating build default plan behavior across flows.
# Class: _SupervisorSequencerState
#   Role: Handles SupervisorSequencerState logic for analytics.flows.multi_agent.
#   Called from: Internal to analytics.flows.multi_agent
#   Collaborators: Internal helpers only
#   Why: Keeps analytics.flows.multi_agent from duplicating SupervisorSequencerState behavior across flows.
# Class: MultiAgentFlow
#   Role: Coordinates specialist agents while reusing the planner-executor core.
#   Called from: analytics.flows.workflow, tests.analytics.test_multi_agent_flow, tests.analytics.test_multi_agent_rerun_policy, tests.analytics.test_prompt_contracts, +3 more
#   Collaborators: analytics.core.config_store.get_config_store, os.getenv, analytics.flows.supervisor_retry_manager.SupervisorRetryManager, analytics.flows.planner_executor.PlannerExecutorFlow, +2 more
#   Why: Supports downstream analytics workflows that rely on MultiAgentFlow.
# --- End Analytics Function/Class Map ---
from __future__ import annotations

import hashlib
import json
import re
import time
import copy
import os
import asyncio
import contextlib
import statistics
import logging
import uuid
from datetime import datetime, date, timezone
from dataclasses import dataclass, field
from typing import Any, AsyncGenerator, Dict, Iterable, List, Mapping, Optional, Sequence, Set, Tuple, TYPE_CHECKING

from analytics.core.session_state import SessionStateSnapshot, get_session_state_repository
from analytics.core.cache import get_cache_service
from analytics.core.events import EventEmitter
from analytics.core.revision_snapshot import extract_revision_snapshot
from analytics.core.telemetry import (
    analysis_chunk as log_analysis_chunk,
    agent_handoff,
    agent_run as log_agent_run,
    backpressure_event,
    tool_iteration as log_tool_iteration,
    policy_decision,
)
from analytics.accessory_receipts import (
    enrich_accessory_payload,
    build_lane_reuse_event,
)
from analytics.core.config_store import get_config_store
from analytics.policies.delegation_policy import DelegationPolicy
from analytics.services.polygon import PolygonMarketDataClient, PolygonError, fetch_daily_snapshot
from analytics.services.response_search import ResponseSearchError, perform_response_search
from analytics.routing import FollowUpRoute
from analytics.validators import CohesiveResultValidationError, CohesiveResultValidator, sanitize_for_json
from .planner_executor import (
    PlannerExecutorFlow,
    PlannerPhaseContext,
    run_planner_executor,
    FOLLOW_UP_BANNERS,
    _build_planner_result_payload,
    _build_reused_analysis_event,
    _evaluate_latency_guardrail,
    _hash_payload,
    _reset_revision_accessories,
    _INTENT_LANE_HINTS,
)
from .hooks import AnalyticsFlowHooks
from .tool_bundle import collect_tool_bundle
from .pipeline_tools import (
    PlannerToolRegistry,
    get_planner_tool_registry,
)
from .orchestrator_adapter import PlannerOrchestratorAdapter, LaneCompleteCallback
from .schedulers import FlowMode, apply_mode_metadata, get_mode_config
from .sequencer import (
    PlannerEventBus,
    PlannerSequencer,
    LANE_STATUS_RUNNING,
    LANE_STATUS_COMPLETED,
    LANE_STATUS_FAILED,
    LANE_STATUS_PENDING,
    LANE_STATUS_SKIPPED,
)
from .supervisor_orchestrator import (
    SupervisorSpecialistConfig,
    build_supervisor_bundle,
)
from .planner import (
    annotate_revision_event,
    apply_revision_plan,
    build_revision_plan,
    build_revision_request_event,
    derive_revision_targets,
    ensure_analysis_dependencies,
    stream_analysis_lane,
    stream_chart_lane,
    stream_sql_lane,
    ToolParallelRuntime,
)
from .tooling import StockTrackerAdapter
from .supervisor_retry_manager import SupervisorRetryManager

logger = logging.getLogger(__name__)


if TYPE_CHECKING:  # pragma: no cover - typing only
    from .revision_directive import RevisionDirective


REVISION_INTENT_CONFIDENCE_THRESHOLD: float = 0.6


def _build_tool_metadata(manifest: Any) -> Dict[str, Dict[str, Any]]:
    metadata: Dict[str, Dict[str, Any]] = {}
    try:
        iterable = list(manifest)
    except TypeError:
        return metadata
    for entry in iterable:
        if not isinstance(entry, dict):
            continue
        name = entry.get("name")
        if not isinstance(name, str):
            continue
        metadata[name] = {
            "latency_budget_ms": entry.get("latency_budget_ms"),
            "output_artifacts": entry.get("output_artifacts"),
            "concurrency_limit": entry.get("concurrency_limit"),
        }
    return metadata


from .chart_revision import (
    infer_analysis_revision_from_query,
    infer_chart_patch_from_query,
    is_analysis_revision_query,
    is_chart_revision_query,
)
from .task_plan import AgentTaskPlan, AgentTaskStep
from .orchestrator import (
    AgentExecutionOrchestrator,
    AgentRunContext,
    AgentResult,
    AgentSpec,
    AgentTask,
    OrchestratorContext,
)

_HASH_PREFIX = "analytics"
_MAX_FRAGMENT_COUNT = 5
_MAX_ANALYSIS_STORED = 1200
HEDGED_WEB_TOOLS = ("web_retriever_cached", "web_retriever_live")

SUPERVISOR_AGENT_SYSTEM_PROMPTS: Dict[str, str] = {
    "planner": (
        "Plan the analytics workflow into specialist-ready tasks while keeping payloads light.\n"
        "- Emit rerun directives that list lanes needing fresh execution in `rerun_directive.rerun` and cached lanes in `rerun_directive.reuse`.\n"
        "- Reference cached receipts and planner context so reused lanes do not schedule redundant work."
    ),
    "query": (
        "Summarize SQL attempt history and highlight retry outcomes.\n"
        "- Call out which attempts reused cached receipts versus introduced fresh execution.\n"
        "- Flag stale receipts so the supervisor can queue reruns in the rerun directive."
    ),
    "analyst": (
        "Summarize findings using planner context and cached notes without re-querying data.\n"
        "- When required lanes are missing or declined, emit `final_answer_only` guidance that specifies which lanes to rerun and which receipts stay valid.\n"
        "- Acknowledge reused receipts so analysts know which insights came from cache."
    ),
    "chart": (
        "Convert planner data into chart metadata summaries only when required.\n"
        "- If `cached_receipts.chart` is fresh, respond with reuse status and concise rationale instead of generating a new spec.\n"
        "- Explain what changed when a rerun occurs so downstream reviewers can compare versions."
    ),
    "market": (
        "Surface market context for planner tickers while honoring cached receipts.\n"
        "- Prefer cached snapshots when present; emit status `reuse` and include the receipt timestamp.\n"
        "- Request reruns only when tickers change or data freshness fails guardrails."
    ),
    "web_research": (
        "Retrieve external signals and citations for the active query.\n"
        "- Use cached receipts when available to avoid duplicate fetches and mark responses with `reused` metadata.\n"
        "- When live reruns are required, emit citations that distinguish fresh versus reused sources."
    ),
}


class _MultiAgentHooks(AnalyticsFlowHooks):
    def __init__(self, flow: "MultiAgentFlow", query: str, session_id: Optional[str] = None) -> None:
        self._flow = flow
        self._query = query
        self._active_session: Optional[str] = session_id
        self._flow._chart_revision_missing_session = False
        self._started: bool = False

    async def on_flow_start(self, ctx: Dict[str, Any]) -> AsyncGenerator[Dict[str, Any], None]:
        if self._started:
            if False:
                yield {}
            return
        self._started = True
        self._flow._prepare_context(self._query)
        if ctx.get("session_id") and not self._active_session:
            session = ctx.get("session_id")
            if isinstance(session, str) and session:
                self._active_session = session
        if False:
            yield {}

    async def before_event(self, ctx: Dict[str, Any], event: Dict[str, Any]) -> AsyncGenerator[Dict[str, Any], None]:
        if False:
            yield {}
        name = event.get("event")
        if name == "session_started":
            data = event.get("data") or {}
            self._active_session = data.get("session_id") or ctx.get("session_id")
            ctx["session_id"] = self._active_session
        self._flow._capture_event(event)
        if self._flow._artifact_flush_pending:
            for artifact_event in self._flow._drain_artifact_events():
                yield self._flow._annotate(artifact_event)
            self._flow._artifact_flush_pending = False
        start_event = self._flow._maybe_agent_turn_start(event)
        if start_event:
            yield start_event
            tool_event = self._flow._agent_tool_event_from_turn(start_event, status="start")
            if tool_event:
                yield tool_event
        if name == "analysis_streaming":
            reasoning = self._flow._agent_reasoning(event, self._active_session)
            if reasoning:
                yield reasoning

    async def after_event(self, ctx: Dict[str, Any], event: Dict[str, Any]) -> AsyncGenerator[Dict[str, Any], None]:
        if False:
            yield {}
        if event.get("event") == "error":
            data = event.get("data") or {}
            code = str(data.get("code") or "").upper()
            if code == "CHART_REVISION_MISSING_SESSION":
                self._flow._chart_revision_missing_session = True
                self._flow.set_follow_up_route(FollowUpRoute.FULL_PIPELINE)
            return
        end_event = self._flow._maybe_agent_turn_end(event)
        if end_event:
            yield end_event
            tool_complete = self._flow._agent_tool_event_from_turn(end_event, status="completed")
            if tool_complete:
                yield tool_complete
        if (
            not self._flow._orchestrated
            and event.get("event") == "analysis_complete"
            and self._flow._active_sequencer is None
        ):
            async for orchestrated_event in self._flow._run_agent_orchestration(
                self._query,
                self._active_session,
            ):
                yield orchestrated_event
            self._flow._orchestrated = True
        for artifact_event in self._flow._drain_artifact_events():
            yield self._flow._annotate(artifact_event)
        self._flow._artifact_flush_pending = False

    async def on_flow_end(
        self,
        ctx: Dict[str, Any],
        *,
        error: Optional[BaseException] = None,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        if False:
            yield {}


def _make_identifier(session_id: Optional[str], prefix: str, payload: str) -> str:
    base = session_id or "sessionless"
    digest = hashlib.sha1(f"{base}:{prefix}:{payload}".encode("utf-8")).hexdigest()[:12]
    return f"{_HASH_PREFIX}:{prefix}:{digest}"


def _canonical_tool_name(name: Optional[str]) -> Optional[str]:
    if not isinstance(name, str):
        return name
    stripped = name.strip()
    if not stripped:
        return stripped
    if stripped.startswith("web_retriever"):
        return "web_retriever"
    return stripped

def _infer_tickers(query: Optional[str]) -> List[str]:
    if not query:
        return []
    tokens = set(re.findall(r"[A-Z]{2,5}", query))
    blacklist = {"WITH", "FROM", "AND", "THE"}
    return sorted(token for token in tokens if token not in blacklist)[:5]


def _normalize_chart_spec_payload(payload: Any) -> Optional[Dict[str, Any]]:
    """Unwrap common chart payload wrappers down to the ECharts option dict."""
    if payload is None:
        return None
    if isinstance(payload, dict):
        if any(
            key in payload
            for key in ("series", "dataset", "datasets", "xAxis", "yAxis", "legend", "tooltip")
        ):
            return payload
        for nested_key in ("chart_spec", "chart", "option", "chartOption", "spec"):
            nested = payload.get(nested_key)
            normalized = _normalize_chart_spec_payload(nested)
            if normalized is not None:
                return normalized
        return None
    return None


# Web search is now owned by a specialist agent step in the plan.
# Legacy env flag removed; agent plan controls whether to run web search.


RECENCY_KEYWORDS = (
    "today",
    "latest",
    "recent",
    "news",
    "headline",
    "update",
    "guidance",
    "current",
    "filing",
    "quarter",
    "earnings",
)


WEB_SEARCH_MAX_ATTEMPTS = 2
WEB_SEARCH_BACKOFF_SECONDS = 0.6


def _needs_web_refresh(query: str, web_ctx: Dict[str, Any]) -> bool:
    normalized = (query or "").strip().lower()
    if any(keyword in normalized for keyword in RECENCY_KEYWORDS):
        return True
    cached_query = str(web_ctx.get('query') or web_ctx.get('query_terms') or '').strip().lower()
    if cached_query and cached_query != normalized:
        return True
    snippets = web_ctx.get('snippets') or []
    return not bool(snippets)


def _derive_tasks(
    planner_ctx: Dict[str, Any],
    sql_ctx: Dict[str, Any],
    analysis_ctx: Dict[str, Any],
    chart_ctx: Dict[str, Any],
    market_ctx: Dict[str, Any],
    query: str,
    *,
    web_ctx: Optional[Dict[str, Any]] = None,
    revision_completed: Optional[Sequence[str]] = None,
    lane_refresh_required: Optional[Mapping[str, Any]] = None,
) -> AgentTaskPlan:
    plan = AgentTaskPlan()
    lane_refresh_raw: Dict[str, Any] = {}
    force_run_lanes: Set[str] = set()
    force_skip_lanes: Set[str] = set()
    if lane_refresh_required:
        for lane, required in lane_refresh_required.items():
            if lane is None:
                continue
            key = str(lane).strip().lower()
            if not key:
                continue
            lane_refresh_raw[key] = required
            if required is False:
                force_skip_lanes.add(key)
            elif bool(required):
                force_run_lanes.add(key)
    if lane_refresh_raw:
        planner_ctx.setdefault("lane_refresh_required", dict(lane_refresh_raw))

    attempts = sql_ctx.get("attempts") or []
    last_attempt = attempts[-1] if attempts else None
    reuse_sql = bool(sql_ctx.get("status") in {"reused", "success"} and (sql_ctx.get("row_count") or 0) > 0)
    completed_lanes = {
        str(lane).strip().lower()
        for lane in (revision_completed or [])
        if lane
    }
    if "market" in completed_lanes:
        completed_lanes.add("stock")
    if "stock" in completed_lanes:
        completed_lanes.add("market")
    if "web" in completed_lanes:
        completed_lanes.add("web")
    if force_run_lanes:
        for lane in force_run_lanes:
            completed_lanes.discard(lane)
            if lane == "market":
                completed_lanes.discard("stock")
            elif lane == "stock":
                completed_lanes.discard("market")
    if force_skip_lanes:
        for lane in force_skip_lanes:
            completed_lanes.add(lane)
            if lane == "market":
                completed_lanes.add("stock")
            elif lane == "stock":
                completed_lanes.add("market")
    analysis_revision_text = None
    if isinstance(analysis_ctx, Mapping):
        analysis_revision_text = analysis_ctx.get("revision_text")
    planner_revision = planner_ctx.get("analysis_revision")
    if analysis_revision_text is None and isinstance(planner_revision, Mapping):
        candidate = planner_revision.get("text") or planner_revision.get("analysis")
        if isinstance(candidate, str) and candidate.strip():
            analysis_revision_text = candidate
    analysis_revision = bool(analysis_revision_text and isinstance(analysis_revision_text, str) and analysis_revision_text.strip())
    if reuse_sql:
        plan.add_step("query", "skip", reason="sql_cached")
    elif attempts:
        plan.add_step(
            "query",
            "run",
            reason="sql_attempt_summary",
            metadata={"outcome": last_attempt.get("status") if last_attempt else None},
        )
    else:
        plan.add_step("query", "skip", reason="no_sql_attempts")

    chart_revision = is_chart_revision_query(query)
    revision_patch = infer_chart_patch_from_query(query) if chart_revision else None

    web_ctx = web_ctx or {}
    analysis_ready = bool(analysis_ctx.get("final"))
    chart_ready = bool(chart_ctx.get("spec_summary")) and (sql_ctx.get("row_count", 0) > 0)
    tickers = planner_ctx.get("tickers", []) or market_ctx.get("tickers", []) or []
    market_ctx["tickers"] = tickers

    if analysis_revision:
        if analysis_revision_text:
            analysis_ctx["revision_text"] = analysis_revision_text
        plan.add_step("analyst", "run", reason="analysis_revision")
        plan.add_step("chart", "reuse", reason="analysis_revision")

        market_reason = "analysis_revision"
        plan.add_step(
            "market",
            "skip",
            reason=market_reason,
            metadata={"tickers": tickers},
        )

        web_skipped = "web" in force_skip_lanes
        web_required = not web_skipped
        if web_required:
            plan.add_step(
                "web_research",
                "run",
                reason="forced_refresh" if "web" in force_run_lanes else "analysis_revision",
                metadata={"source": web_ctx.get("source") if isinstance(web_ctx, Mapping) else None},
            )
        else:
            plan.add_step(
                "web_research",
                "skip",
                reason="lane_skipped" if web_skipped else "analysis_revision",
                metadata={"source": web_ctx.get("source") if isinstance(web_ctx, Mapping) else None},
            )
        return plan

    if chart_revision:
        if revision_patch:
            chart_ctx["revision_patch"] = revision_patch
        chart_status = "reuse" if "chart" in completed_lanes else "run"
        chart_reason = "revision_completed" if chart_status == "reuse" else "chart_revision"
        plan.add_step("chart", chart_status, reason=chart_reason)
        plan.add_step("analyst", "skip", reason="chart_revision")
        if "market" in force_skip_lanes:
            market_status = "skip"
            market_reason = "lane_skipped"
        elif "market" in force_run_lanes:
            market_status = "run"
            market_reason = "forced_refresh"
        else:
            market_status = "reuse" if "stock" in completed_lanes else "skip"
            market_reason = "revision_completed" if market_status == "reuse" else "chart_revision"
        plan.add_step(
            "market",
            market_status,
            reason=market_reason,
            metadata={"tickers": tickers},
        )
        if "web" in force_skip_lanes:
            web_status = "skip"
            web_reason = "lane_skipped"
        elif "web" in force_run_lanes:
            web_status = "run"
            web_reason = "forced_refresh"
        else:
            web_status = "reuse" if "web" in completed_lanes else "skip"
            web_reason = "revision_completed" if web_status == "reuse" else "chart_revision"
        plan.add_step(
            "web_research",
            web_status,
            reason=web_reason,
            metadata={"source": web_ctx.get("source") if isinstance(web_ctx, Mapping) else None},
        )
        return plan

    analyst_status = "reuse" if "analysis" in completed_lanes else (
        "reuse" if (analysis_ready and reuse_sql) else ("run" if analysis_ready else "skip")
    )
    analyst_reason = "revision_completed" if "analysis" in completed_lanes else (
        "analysis_cached" if (analysis_ready and reuse_sql) else ("analysis_ready" if analysis_ready else "analysis_not_available")
    )
    plan.add_step("analyst", analyst_status, reason=analyst_reason)

    chart_status = "reuse" if "chart" in completed_lanes else (
        "reuse" if (chart_ready and reuse_sql) else ("run" if chart_ready else "skip")
    )
    chart_reason = "revision_completed" if "chart" in completed_lanes else (
        "chart_cached" if (chart_ready and reuse_sql) else ("chart_ready" if chart_ready else "chart_not_available")
    )
    plan.add_step("chart", chart_status, reason=chart_reason)

    if "market" in force_skip_lanes:
        market_status = "skip"
        market_reason = "lane_skipped"
    elif "market" in force_run_lanes:
        market_status = "run"
        market_reason = "forced_refresh"
    else:
        stock_cached = bool(market_ctx.get("snapshot") or market_ctx.get("stock_widget")) or ("stock" in completed_lanes)
        if stock_cached:
            market_status = "reuse"
            market_reason = "revision_completed" if "stock" in completed_lanes else "market_cached"
        elif bool(tickers) and chart_ready:
            market_status = "run"
            market_reason = "tickers_detected"
        else:
            market_status = "skip"
            market_reason = "no_tickers"
    plan.add_step(
        "market",
        market_status,
        reason=market_reason,
        metadata={"tickers": tickers, "source": market_ctx.get("source")},
    )

    web_context = web_ctx if isinstance(web_ctx, Mapping) else {}
    if "web" in force_skip_lanes:
        web_status = "skip"
        web_reason = "lane_skipped"
    else:
        web_should_run = _needs_web_refresh(query, web_context) and ("web" not in completed_lanes)
        if "web" in force_run_lanes:
            web_status = "run"
            web_reason = "forced_refresh"
        elif "web" in completed_lanes:
            web_status = "reuse"
            web_reason = "revision_completed"
        elif web_should_run:
            web_status = "run"
            web_reason = "recency_requested"
        else:
            web_status = "skip"
            web_reason = "cached_web_context"
    plan.add_step("web_research", web_status, reason=web_reason)

    if revision_completed:
        guard_map = {
            "analyst": {"analysis"},
            "chart": {"chart"},
            "market": {"market", "stock"},
            "web_research": {"web"},
        }
        completed_set = {str(l).strip().lower() for l in revision_completed if l}
        for step in plan.steps:
            lanes = guard_map.get(step.name)
            if lanes and completed_set.intersection(lanes) and step.status == "run":
                step.status = "reuse"
                step.reason = "revision_guardrail"

    return plan



    tasks.append(
        {
            'name': 'chart',
            'status': 'run' if chart_ready else 'skip',
            'reason': 'chart_ready' if chart_ready else 'chart_not_available',
        }
    )

    market_ready = bool(tickers) and chart_ready
    tasks.append(
        {
            'name': 'market',
            'status': 'run' if market_ready else 'skip',
            'reason': 'tickers_detected' if market_ready else 'no_tickers',
            'tickers': tickers,
        }
    )

    return tasks


def _task_status(tasks, name: str) -> str:
    """Return the status for a task by name regardless of container type."""
    if isinstance(tasks, AgentTaskPlan):
        iterable = tasks.steps
    else:
        iterable = tasks or []
    for task in iterable:
        if isinstance(task, AgentTaskStep):
            if task.name == name:
                return task.status
        elif task.get("name") == name:
            return str(task.get("status", "skip"))
    return "skip"


def _create_planner_bundle(
    session_id: Optional[str],
    query: str,
    planner_ctx: Dict[str, Any],
    sql_ctx: Dict[str, Any],
    chart_ctx: Dict[str, Any],
    analysis_ctx: Dict[str, Any],
    tasks: List[Dict[str, Any]],
    *,
    tool_manifest: Optional[List[Dict[str, Any]]] = None,
    tool_results: Optional[List[Dict[str, Any]]] = None,
    stock_widget: Optional[Dict[str, Any]] = None,
    web_context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    attempts = sql_ctx.get('attempts') or []
    bundle = {
        'query': query,
        'intent': {
            'key': planner_ctx.get('intent_key'),
            'confidence': planner_ctx.get('confidence'),
        },
        'sql': {
            'row_count': sql_ctx.get('row_count'),
            'attempts': attempts,
            'status': sql_ctx.get('status'),
        },
        'analysis': {
            'available': bool(analysis_ctx.get('final')),
            'id': analysis_ctx.get('id'),
        },
        'chart': {
            'spec_id': chart_ctx.get('spec_id'),
            'summary': chart_ctx.get('spec_summary'),
        },
        'assets': {
            'sql_id': sql_ctx.get('id'),
            'chart_id': chart_ctx.get('spec_id'),
            'analysis_id': analysis_ctx.get('id'),
        },
        'tasks': tasks,
    }
    tickers = planner_ctx.get('tickers') or []
    if tickers:
        bundle['tickers'] = tickers
    if attempts:
        bundle['sql']['last_attempt'] = attempts[-1]
    if tool_manifest:
        bundle['tool_manifest'] = copy.deepcopy(tool_manifest)
    if tool_results:
        bundle['tool_results'] = copy.deepcopy(tool_results)
    visuals: Dict[str, Any] = {}
    if stock_widget:
        visuals['stock_widget'] = copy.deepcopy(stock_widget)
    if web_context:
        visuals['web_context'] = copy.deepcopy(web_context)
    if visuals:
        bundle['visuals'] = visuals
    sanitized_bundle = sanitize_for_json(bundle)
    serialized = json.dumps(sanitized_bundle, sort_keys=True, default=str)
    sanitized_bundle['id'] = _make_identifier(session_id, 'bundle', serialized)
    return sanitized_bundle





async def _planner_agent(context: AgentRunContext) -> AgentResult:
    shared = context.shared
    planner_ctx = shared.setdefault('planner', {})
    sql_ctx = shared.setdefault('sql', {})
    chart_ctx = shared.setdefault('chart', {})
    analysis_ctx = shared.setdefault('analysis', {})
    market_ctx = shared.setdefault('market', {})

    shared.setdefault('query', context.query)

    plan = _derive_tasks(
        planner_ctx,
        sql_ctx,
        analysis_ctx,
        chart_ctx,
        market_ctx,
        shared.get('query', context.query),
        web_ctx=shared.setdefault('web', {}),
        revision_completed=shared.get('revision_completed_lanes'),
        lane_refresh_required=shared.get('lane_refresh_required'),
    )
    tasks = plan.to_dicts()
    bundle = _create_planner_bundle(
        context.session_id,
        context.query,
        planner_ctx,
        sql_ctx,
        chart_ctx,
        analysis_ctx,
        tasks,
        tool_manifest=shared.get('tool_manifest'),
        tool_results=shared.get('tool_results'),
        stock_widget=shared.get('stock_widget'),
        web_context=shared.get('web'),
    )
    agent_handoff(
        role='planner_agent',
        status='planned',
        metadata={'tasks': tasks},
        session_id=context.session_id,
        flow=shared.get('_meta', {}).get('flow_label'),
    )
    planner_ctx['tasks'] = tasks
    planner_ctx['task_plan'] = tasks
    planner_ctx['bundle'] = bundle
    return AgentResult(
        name='planner',
        output={
            'status': 'planned',
            'tasks': tasks,
            'task_plan': tasks,
            'bundle_id': bundle['id'],
            'bundle': bundle,
            'planner_result': planner_ctx.get('result'),
        },
    )



async def _query_agent(context: AgentRunContext) -> AgentResult:
    planner_output = context.dependencies.get('planner_phase')
    tasks = planner_output.output.get('tasks', []) if planner_output else []
    status = _task_status(tasks, 'query')
    sql_ctx = context.shared.get('sql', {})
    attempts = sql_ctx.get('attempts') or []
    last_attempt = attempts[-1] if attempts else None
    summary_attempts: List[Dict[str, Any]] = []
    for attempt in attempts[-3:]:
        summary_attempts.append(
            {
                'attempt': attempt.get('attempt'),
                'source': attempt.get('source'),
                'status': attempt.get('status'),
                'error_code': attempt.get('error_code'),
                'error_detail': attempt.get('error_detail'),
            }
        )
    output = {
        'status': status,
        'attempt_count': len(attempts),
        'summary': summary_attempts,
    }
    if last_attempt:
        output['last_status'] = last_attempt.get('status')
        output['last_error_code'] = last_attempt.get('error_code')
    return AgentResult(name='query', output=output)


async def _analyst_agent(context: AgentRunContext) -> AgentResult:
    planner_output = context.dependencies.get("planner_phase")
    tasks = planner_output.output.get("tasks", []) if planner_output else []
    status = _task_status(tasks, "analyst")
    analysis_ctx = context.shared.get("analysis", {})
    final_text: Optional[str] = analysis_ctx.get("final")
    summary = None
    if status in {"run", "reuse"} and final_text:
        summary = final_text
        if len(summary) > 280:
            summary = summary[:277].rstrip() + "..."
    return AgentResult(
        name="analyst",
        output={
            "status": status,
            "summary": summary,
            "word_count": len(final_text.split()) if final_text else 0,
        },
    )


async def _chart_agent(context: AgentRunContext) -> AgentResult:
    planner_output = context.dependencies.get("planner_phase")
    tasks = planner_output.output.get("tasks", []) if planner_output else []
    status = _task_status(tasks, "chart")
    chart_ctx = context.shared.get("chart", {})
    summary = chart_ctx.get("spec_summary") or {}
    spec_id = chart_ctx.get("spec_id")
    payload: Dict[str, Any] = {"status": status}
    if summary or spec_id:
        payload["chart"] = {
            "chart_type": summary.get("chart_type"),
            "series_count": summary.get("series_count"),
            "spec_id": spec_id,
        }
    return AgentResult(name="chart", output=payload)


async def _market_agent(context: AgentRunContext) -> AgentResult:
    lane_flags: Dict[str, bool] = {}
    shared_flags = context.shared.get('lane_refresh_required')
    if isinstance(shared_flags, Mapping):
        lane_flags.update({str(k).strip().lower(): bool(v) for k, v in shared_flags.items()})
    ctx_flags = getattr(context, 'lane_refresh_required', None)
    if isinstance(ctx_flags, Mapping):
        lane_flags.update({str(k).strip().lower(): bool(v) for k, v in ctx_flags.items()})
    if lane_flags.get('market') is False:
        tickers = context.shared.get('planner', {}).get('tickers', [])
        return AgentResult(
            name='market',
            output={
                'status': 'skip',
                'tickers': tickers,
                'refresh': False,
            },
        )

    gate = context.shared.get('_runtime', {}).get('accessories_ready')
    if isinstance(gate, asyncio.Event) and not gate.is_set():
        try:
            await asyncio.wait_for(gate.wait(), 1.5)
        except asyncio.TimeoutError:
            logger.debug("Market agent proceeding without accessories_ready signal after timeout.")
    planner_output = context.dependencies.get('planner_phase')
    tasks = planner_output.output.get('tasks', []) if planner_output else []
    status = _task_status(tasks, 'market')
    tickers = context.shared.get('planner', {}).get('tickers', [])
    market_ctx = context.shared.setdefault('market', {})
    runtime = context.shared.get('_runtime', {})
    snapshot_payload: Optional[Dict[str, Any]] = market_ctx.get('snapshot')
    error_reason: Optional[str] = None
    error_code: Optional[str] = None
    receipts = context.shared.get('tool_receipts') or {}
    receipt_candidates = [
        receipts.get('market_question_a'),
        receipts.get('market_question_b'),
        receipts.get('stock_tracker'),
    ]
    if status == 'run' and any(
        MultiAgentFlow._receipt_is_fresh(receipt, MultiAgentFlow.RECEIPT_TTL_SECONDS)
        for receipt in receipt_candidates
    ):
        status = 'reuse'
        market_ctx.setdefault('source', market_ctx.get('source') or 'cached')

    if status == 'run' and tickers:
        fetcher = runtime.get('market_fetcher')
        client = runtime.get('market_client')
        retries = market_ctx.get('retry_count', 0)
        planner_confidence = float(context.shared.get('planner', {}).get('confidence') or 0.0)
        flow_label = context.shared.get('_meta', {}).get('flow_label')
        if retries:
            threshold = 0.55 if retries == 1 else 0.7
            allowed = planner_confidence >= threshold
            policy_decision(
                policy='market_refresh_retry',
                score=planner_confidence,
                threshold=threshold,
                action='allow_retry' if allowed else 'skip_retry',
                reason=f'{retries} prior retries',
                session_id=context.session_id,
                flow=flow_label,
                metadata={'retries': retries, 'tickers': tickers},
            )
            if not allowed:
                status = 'skip'
                error_reason = 'market refresh blocked by policy'
                error_code = 'POLICY_BLOCKED'
                market_ctx['error'] = error_reason
                market_ctx['error_code'] = error_code
                market_ctx['policy_blocked'] = True
                output = {
                    'status': status,
                    'tickers': tickers,
                    'refresh': False,
                    'error': error_reason,
                    'error_code': error_code,
                    'policy_score': planner_confidence,
                    'policy_threshold': threshold,
                }
                return AgentResult(name='market', output=output)
        if fetcher and client and getattr(client, 'is_configured', False):
            try:
                snapshot = await fetcher(tickers[0], client=client)
                bars = snapshot.bars[-30:]
                snapshot_payload = {
                    'symbol': snapshot.symbol,
                    'latest_close': snapshot.latest_close,
                    'change_percent': snapshot.change_percent,
                    'bars': [{'time': bar.time, 'close': bar.close} for bar in bars],
                }
                market_ctx['snapshot'] = snapshot_payload
                market_ctx['source'] = 'market_agent'
                market_ctx['retry_count'] = 0
                market_ctx.pop('error', None)
                market_ctx.pop('error_code', None)
            except Exception as exc:
                error_reason = str(exc)
                error_code = 'POLYGON_API_ERROR' if isinstance(exc, PolygonError) else 'MARKET_FETCH_ERROR'
                market_ctx['error'] = error_reason
                market_ctx['error_code'] = error_code
                market_ctx['retry_count'] = retries + 1
        else:
            error_reason = 'polygon_client_unconfigured'
            error_code = 'POLYGON_CLIENT_UNCONFIGURED'
            market_ctx['error'] = error_reason
            market_ctx['error_code'] = error_code
            market_ctx['retry_count'] = retries + 1
    elif status == 'reuse':
        snapshot_payload = market_ctx.get('snapshot')
        error_code = market_ctx.get('error_code')
        error_reason = market_ctx.get('error')
    else:
        market_ctx.pop('snapshot', None)
        market_ctx.pop('error', None)
        market_ctx.pop('error_code', None)
        market_ctx.pop('source', None)
        snapshot_payload = None
    market_ctx['status'] = status

    output: Dict[str, Any] = {
        'status': status,
        'tickers': tickers,
        'refresh': status == 'run',
    }
    if snapshot_payload:
        output['insights'] = snapshot_payload
    if market_ctx.get('source'):
        output['source'] = market_ctx.get('source')
    if error_reason:
        output['error'] = error_reason
        output['error_code'] = error_code or 'UNKNOWN_MARKET_ERROR'
    return AgentResult(name='market', output=output)






async def _web_research_agent(context: AgentRunContext) -> AgentResult:
    gate = context.shared.get('_runtime', {}).get('accessories_ready')
    if isinstance(gate, asyncio.Event) and not gate.is_set():
        try:
            await asyncio.wait_for(gate.wait(), 1.5)
        except asyncio.TimeoutError:
            logger.debug("Web research agent proceeding without accessories_ready signal after timeout.")
    web_ctx = context.shared.setdefault('web', {})
    query = context.shared.get('query', context.query)
    session_id = context.session_id

    planner_output = context.dependencies.get('planner_phase')
    tasks = planner_output.output.get('tasks', []) if planner_output else []
    status_hint = _task_status(tasks, 'web_research')
    receipts = context.shared.get('tool_receipts') or {}
    receipt = receipts.get('web_retriever')
    if status_hint == 'skip':
        web_ctx['status'] = 'skip'
        web_ctx.pop('error', None)
        web_ctx['attempts'] = []
        return AgentResult(
            name='web_research',
            output={
                'status': 'skip',
                'from_cache': False,
                'attempts': [],
                'attempt_count': 0,
            },
        )

    attempts_meta: List[Dict[str, Any]] = []

    repository = get_session_state_repository()
    snapshot = await repository.load(session_id) if session_id else None
    cached_payload = None
    if snapshot:
        cache = snapshot.tool_cache.get('web_search')
        if cache and str(cache.get('query') or '').strip().lower() == query.strip().lower():
            cached_payload = cache

    receipt_fresh = MultiAgentFlow._receipt_is_fresh(receipt, MultiAgentFlow.RECEIPT_TTL_SECONDS)
    should_reuse = status_hint != 'run' or receipt_fresh
    if cached_payload and not _needs_web_refresh(query, web_ctx):
        should_reuse = True

    if should_reuse:
        reuse_source: Dict[str, Any] = {}
        if isinstance(cached_payload, dict):
            reuse_source = copy.deepcopy(cached_payload)
        elif web_ctx:
            reuse_source = dict(web_ctx)
        if reuse_source:
            web_ctx.update(reuse_source)
            web_ctx['ready'] = True
            web_ctx['from_cache'] = True
            attempts_meta = list(reuse_source.get('attempts', []))
            web_ctx['attempts'] = attempts_meta
            web_ctx.setdefault('source', web_ctx.get('source') or 'cached')
            web_ctx['status'] = 'reuse'
            return AgentResult(
                name='web_research',
                output={
                    'status': 'reuse',
                    'summary': web_ctx.get('summary'),
                    'snippets': web_ctx.get('snippets'),
                    'from_cache': True,
                    'attempts': attempts_meta,
                    'attempt_count': len(attempts_meta),
                },
            )

    last_error: Optional[Exception] = None
    search_result = None
    for attempt in range(1, WEB_SEARCH_MAX_ATTEMPTS + 1):
        try:
            search_result = await perform_response_search(
                query,
                session_id=session_id,
            )
            attempts_meta.append({
                'attempt': attempt,
                'status': 'success',
                'latency_ms': search_result.latency_ms,
            })
            break
        except ResponseSearchError as exc:
            last_error = exc
            attempts_meta.append({
                'attempt': attempt,
                'status': 'error',
                'error': str(exc),
            })
            if attempt >= WEB_SEARCH_MAX_ATTEMPTS:
                web_ctx['error'] = str(exc)
                web_ctx['attempts'] = attempts_meta
                return AgentResult(
                    name='web_research',
                    output={
                        'status': 'error',
                        'error': str(exc),
                        'attempts': attempts_meta,
                        'attempt_count': len(attempts_meta),
                    },
                )
            await asyncio.sleep(min(WEB_SEARCH_BACKOFF_SECONDS * attempt, 2.0))

    if not search_result:
        error_message = str(last_error) if last_error else 'web_search_failed'
        web_ctx['error'] = error_message
        web_ctx['attempts'] = attempts_meta
        return AgentResult(
            name='web_research',
            output={
                'status': 'error',
                'error': error_message,
                'attempts': attempts_meta,
                'attempt_count': len(attempts_meta),
            },
        )

    payload = search_result.to_payload()
    payload['query'] = query
    payload['ready'] = True
    payload['from_cache'] = False
    payload['attempts'] = attempts_meta
    web_ctx.update(payload)
    web_ctx['status'] = 'run'

    topic_latencies = [
        topic.latency_ms
        for topic in (search_result.topics or [])
        if topic.latency_ms is not None
    ]

    latency_stats: Optional[Dict[str, Any]] = None
    if search_result.latency_ms is not None or topic_latencies:
        latency_stats = {
            'total_ms': search_result.latency_ms,
            'per_topic_ms': topic_latencies,
            'samples': len(topic_latencies) or None,
        }
        if topic_latencies:
            p50 = statistics.median(topic_latencies)
            latency_stats.update(
                {
                    'p50_ms': int(round(p50)),
                    'max_ms': max(topic_latencies),
                    'min_ms': min(topic_latencies),
                }
            )

    guardrail_payload: Optional[Dict[str, Any]] = None
    if latency_stats:
        payload['latency_stats'] = latency_stats
        guardrail_payload = _evaluate_latency_guardrail(
            {
                "total_ms": latency_stats.get("total_ms"),
                "p50_ms": latency_stats.get("p50_ms"),
                "p95_ms": latency_stats.get("p95_ms") or latency_stats.get("max_ms"),
                "max_ms": latency_stats.get("max_ms"),
                "min_ms": latency_stats.get("min_ms"),
                "samples": latency_stats.get("samples"),
            }
        )
        if guardrail_payload:
            payload['latency_guardrail'] = guardrail_payload

    if snapshot:
        snapshot.record_tool_result('web_search', payload)
        await repository.save(snapshot)

    web_ctx['attempts'] = attempts_meta
    if latency_stats:
        web_ctx['latency_stats'] = latency_stats
    if guardrail_payload:
        web_ctx['latency_guardrail'] = guardrail_payload

    metrics: Dict[str, Any] = {'latency_ms': search_result.latency_ms}
    if topic_latencies:
        median_latency = statistics.median(topic_latencies)
        metrics.update(
            {
                'latency_p50_ms': int(round(median_latency)),
                'latency_max_ms': max(topic_latencies),
                'latency_min_ms': min(topic_latencies),
                'latency_samples': len(topic_latencies),
            }
        )
    if guardrail_payload:
        metrics['latency_guardrail_status'] = guardrail_payload['status']

    return AgentResult(
        name='web_research',
        output={
            'status': 'run',
            'summary': payload.get('summary'),
            'snippets': payload.get('snippets'),
            'search_id': payload.get('search_id'),
            'from_cache': False,
            'attempts': attempts_meta,
            'attempt_count': len(attempts_meta),
            'latency_guardrail': guardrail_payload,
        },
        metrics=metrics,
    )



def _build_default_agent_registry() -> Dict[str, AgentSpec]:
    return {
        'planner': AgentSpec(
            name='planner',
            system_prompt=SUPERVISOR_AGENT_SYSTEM_PROMPTS['planner'],
            capabilities=('task_planning', 'sql_routing'),
            latency_budget_ms=400,
            entrypoint=_planner_agent,
        ),
        'query': AgentSpec(
            name='query',
            system_prompt=SUPERVISOR_AGENT_SYSTEM_PROMPTS['query'],
            capabilities=('sql_diagnostics',),
            latency_budget_ms=300,
            entrypoint=_query_agent,
        ),
        'analyst': AgentSpec(
            name='analyst',
            system_prompt=SUPERVISOR_AGENT_SYSTEM_PROMPTS['analyst'],
            capabilities=('narrative', 'context_blending'),
            latency_budget_ms=500,
            entrypoint=_analyst_agent,
        ),
        'chart': AgentSpec(
            name='chart',
            system_prompt=SUPERVISOR_AGENT_SYSTEM_PROMPTS['chart'],
            capabilities=('visualization', 'vega_lite'),
            latency_budget_ms=400,
            entrypoint=_chart_agent,
        ),
        'market': AgentSpec(
            name='market',
            system_prompt=SUPERVISOR_AGENT_SYSTEM_PROMPTS['market'],
            capabilities=('market_data', 'ticker_updates'),
            latency_budget_ms=1500,
            entrypoint=_market_agent,
        ),
        'web_research': AgentSpec(
            name='web_research',
            system_prompt=SUPERVISOR_AGENT_SYSTEM_PROMPTS['web_research'],
            capabilities=('web_search', 'context_enrichment'),
            latency_budget_ms=2000,
            entrypoint=_web_research_agent,
        ),
    }





def _build_default_plan() -> List[AgentTask]:
    return [
        AgentTask(name='planner_phase', agent='planner'),
        AgentTask(name='query_phase', agent='query', depends_on=('planner_phase',)),
        AgentTask(name='market_phase', agent='market', depends_on=('planner_phase',)),
        AgentTask(name='web_research_phase', agent='web_research', depends_on=('planner_phase',)),
        AgentTask(name='chart_phase', agent='chart', depends_on=('query_phase',)),
        AgentTask(
            name='analyst_phase',
            agent='analyst',
            depends_on=('chart_phase', 'market_phase', 'web_research_phase'),
        ),
    ]




@dataclass
class _SupervisorSequencerState:
    ctx: PlannerPhaseContext
    registry: PlannerToolRegistry
    executed: Set[str]
    mode_config: Any
    query: str
    session_id: Optional[str]
    hooks: "_MultiAgentHooks"
    tool_runtime: Optional[ToolParallelRuntime] = None
    tool_state: Optional[Dict[str, Any]] = None
    revision_plan: Optional[Any] = None
    derived_targets: Optional[Set[str]] = None
    lane_states: Optional[Dict[str, str]] = None
    run_sql_lane: bool = True
    run_chart_lane: bool = True
    run_analysis_lane: bool = True
    stock_only_run: bool = False
    is_revision_follow_up: bool = False


class MultiAgentFlow:
    """Coordinates specialist agents while reusing the planner-executor core."""

    _PROMPT_VERSIONS: Dict[str, str] = {
        "schema_clarifier": "2025-10-16",
        "multi_agent.supervisor": "2025-10-16",
    }
    SESSION_AWARE_EVENTS: Set[str] = {
        "follow_up_route",
        "analysis_ready",
        "analysis_revision_ready",
        "analysis_complete",
        "workflow_complete",
    }

    AGENT_START_STEPS = {
        "intent_detection": "intent_analyst",
        "clarification": "user_liaison",
        "sql_compilation": "sql_specialist",
        "sql_validation": "risk_controller",
        "sql_execution": "data_engineer",
        "chart_generation": "viz_designer",
        "chart_revision": "viz_designer",
        "analysis_generation": "insight_reviewer",
        "analysis_revision": "insight_reviewer",
        "web_refresh": "insight_reviewer",
        "market_refresh": "market_agent",
    }

    AGENT_END_EVENTS = {
        "intent_detection_complete": "intent_analyst",
        "clarification_resolved": "user_liaison",
        "clarification_skipped": "user_liaison",
        "clarification_timeout": "user_liaison",
        "sql_generated": "sql_specialist",
        "sql_validated": "risk_controller",
        "execution_stats": "data_engineer",
        "sql_attempts": "query_agent",
        "chart_generated": "viz_designer",
        "chart_patch": "viz_designer",
        "analysis_revision": "insight_reviewer",
        "analysis_complete": "insight_reviewer",
        "web_ready": "insight_reviewer",
        "stock_ready": "market_agent",
    }

    TOOL_METADATA_STEP_MAP = {
        "intent_detection": "intent_detection",
        "clarification": "clarification",
        "sql_compilation": "sql_generation",
        "sql_validation": "sql_generation",
        "sql_execution": "sql_generation",
        "chart_generation": "chart_generation",
        "chart_revision": "chart_revision",
        "analysis_generation": "analysis_generation",
        "analysis_revision": "analysis_revision",
        "web_refresh": "web_refresh",
        "market_refresh": "market_refresh",
    }

    TOOL_METADATA_EVENT_MAP = {
        "intent_detection_complete": "intent_detection",
        "clarification_resolved": "clarification",
        "clarification_skipped": "clarification",
        "clarification_timeout": "clarification",
        "sql_generated": "sql_generation",
        "sql_validated": "sql_generation",
        "execution_stats": "sql_generation",
        "sql_attempts": "sql_generation",
        "chart_generated": "chart_generation",
        "chart_patch": "chart_revision",
        "analysis_revision": "analysis_revision",
        "analysis_complete": "analysis_generation",
        "web_ready": "web_refresh",
        "stock_ready": "market_refresh",
    }

    TOOL_METADATA_ROLE_MAP = {
        "planner_agent": "plan_generation",
        "intent_analyst": "intent_detection",
        "user_liaison": "clarification",
        "sql_specialist": "sql_generation",
        "risk_controller": "sql_generation",
        "data_engineer": "sql_generation",
        "viz_designer": "chart_generation",
        "analyst_agent": "analysis_generation",
        "insight_reviewer": "analysis_generation",
        "query_agent": "sql_generation",
        "market_agent": "chart_generation",
    }

    ORCHESTRATION_ROLES: Dict[str, str] = {
        "planner_phase": "planner_agent",
        "query_phase": "sql_specialist",
        "chart_phase": "viz_designer",
        "market_phase": "market_agent",
        "web_research_phase": "web_research_agent",
        "analyst_phase": "insight_reviewer",
    }
    ROLE_PARALLEL_GROUPS: Dict[str, str] = {
        "planner_agent": "supervisor_intent",
        "sql_specialist": "sql_web",
        "viz_designer": "chart_parallel",
        "market_agent": "sql_web",
        "web_research_agent": "sql_web",
        "insight_reviewer": "supervisor_summary",
    }
    ROLE_LANES: Dict[str, str] = {
        "planner_agent": "intent",
        "sql_specialist": "sql",
        "viz_designer": "chart",
        "market_agent": "market",
        "web_research_agent": "web",
        "insight_reviewer": "analysis",
    }
    ROLE_TOOL_ALIAS: Dict[str, str] = {
        "planner_agent": "planner",
        "intent_analyst": "intent_classifier",
        "user_liaison": "clarification_manager",
        "sql_specialist": "sql_generator",
        "risk_controller": "sql_validator",
        "data_engineer": "sql_executor",
        "viz_designer": "chart_designer",
        "insight_reviewer": "analysis_writer",
        "analyst_agent": "analysis_writer",
        "market_agent": "stock_tracker",
        "web_research_agent": "web_retriever",
    }
    ARTIFACT_LANE_MAP: Dict[str, str] = {
        "sql_ready": "sql",
        "chart_ready": "chart",
        "stock_ready": "market",
        "web_ready": "web",
        "analysis_ready": "analysis",
    }
    ARTIFACT_PARALLEL_GROUPS: Dict[str, str] = {
        "sql_ready": "sql_web",
        "chart_ready": "chart_parallel",
        "stock_ready": "sql_web",
        "web_ready": "sql_web",
        "analysis_ready": "supervisor_summary",
    }
    DEFAULT_PARALLEL_GROUP = "sql_web"
    SUPERVISOR_PARALLEL_LIMITS: Dict[str, int] = {
        "supervisor_intent": 1,
        "sql_web": 2,
        "chart_parallel": 1,
        "supervisor_summary": 1,
    }
    RECEIPT_TTL_SECONDS: int = 600

    @classmethod
    def get_prompt_versions(cls) -> Dict[str, str]:
        return dict(cls._PROMPT_VERSIONS)

    @staticmethod
    def _receipt_is_fresh(receipt: Optional[Mapping[str, Any]], ttl_seconds: int) -> bool:
        if not receipt:
            return False
        status = str(receipt.get("status") or "").strip().lower()
        if status not in {"completed", "complete", "success", "reused"}:
            return False
        timestamp = receipt.get("timestamp") or receipt.get("completed_at")
        if not timestamp:
            return False
        try:
            recorded = datetime.fromisoformat(str(timestamp))
        except ValueError:
            logger.warning("[SUPERVISOR] invalid receipt timestamp: %s", timestamp)
            return False
        if recorded.tzinfo is None:
            recorded = recorded.replace(tzinfo=timezone.utc)
        else:
            recorded = recorded.astimezone(timezone.utc)
        age_seconds = (datetime.now(timezone.utc) - recorded).total_seconds()
        return age_seconds <= ttl_seconds

    def __init__(self) -> None:
        self._config_store = get_config_store()
        self._supervisor_settings = self._config_store.get_agent_mode_config("supervisor")
        policy_version = os.getenv("AGENTS_DELEGATION_POLICY_VERSION", "baseline")
        agents_yaml = getattr(self._config_store, "yaml_configs", {})
        self._delegation_policy = DelegationPolicy.load(
            version=policy_version,
            config=agents_yaml,
        )
        self._retry_manager = SupervisorRetryManager(
            self._delegation_policy,
            task_roles=self.ORCHESTRATION_ROLES,
            role_lanes=self.ROLE_LANES,
        )
        self._max_tool_retries = int(self._supervisor_settings.get("max_tool_retries") or 2)
        supervisor_name = str(self._supervisor_settings.get("name") or "analytics_supervisor")
        supervisor_instructions = str(self._supervisor_settings.get("instructions") or "")
        supervisor_model = str(self._supervisor_settings.get("model") or "gpt-5-mini-2025-08-07")
        supervisor_reasoning = self._supervisor_settings.get("reasoning_effort")
        supervisor_max_turns = self._supervisor_settings.get("max_turns")

        specialist_configs: List[SupervisorSpecialistConfig] = []
        for entry in self._supervisor_settings.get("specialists", []) or []:
            lane = str(entry.get("lane") or "").strip()
            if not lane:
                continue
            specialist_configs.append(
                SupervisorSpecialistConfig(
                    lane=lane,
                    name=str(entry.get("name") or f"{lane}_specialist"),
                    instructions=str(entry.get("instructions") or supervisor_instructions),
                    description=entry.get("description"),
                    model=entry.get("model"),
                    reasoning_effort=entry.get("reasoning_effort"),
                    max_turns=entry.get("max_turns"),
                )
            )

        self._supervisor_bundle = (
            build_supervisor_bundle(
                supervisor_name=supervisor_name,
                supervisor_instructions=supervisor_instructions,
                model=supervisor_model,
                reasoning_effort=supervisor_reasoning,
                max_turns=supervisor_max_turns,
                specialist_configs=specialist_configs,
            )
            if specialist_configs
            else None
        )
        self._supervisor_agent = self._supervisor_bundle.supervisor if self._supervisor_bundle else None
        self._specialist_tools = (
            {binding.lane: binding.tool for binding in self._supervisor_bundle.bindings}
            if self._supervisor_bundle
            else {}
        )

        self._planner = PlannerExecutorFlow(flow_mode=FlowMode.MULTI_AGENT)
        self.follow_up_route = FollowUpRoute.FULL_PIPELINE
        self._planner.set_follow_up_route(self.follow_up_route)
        self.flow_mode = FlowMode.MULTI_AGENT
        self.flow_label = "multi-agent"
        self._cohesive_validator = CohesiveResultValidator()
        self._prompt_versions = dict(self._PROMPT_VERSIONS)
        registry = get_planner_tool_registry()
        self._planner_tool_manifest = registry.describe_tools()
        self._tool_metadata_by_registry = _build_tool_metadata(self._planner_tool_manifest)
        self._tool_metadata_by_role = {
            role: self._tool_metadata_by_registry.get(registry_name)
            for role, registry_name in self.TOOL_METADATA_ROLE_MAP.items()
            if registry_name in self._tool_metadata_by_registry
        }
        self._timers: Dict[str, float] = {}
        self._latest_lane_states: Dict[str, str] = {}
        self._agent_registry = _build_default_agent_registry()
        # Analyst orchestration traverses supervisor -> specialists -> reviewer which requires a deeper DAG budget.
        self._orchestrator = AgentExecutionOrchestrator(
            self._agent_registry,
            max_depth=4,
            max_retries=self._max_tool_retries,
            retry_decider=self._retry_manager.should_retry,
        )
        self._base_plan = _build_default_plan()
        self._market_client = PolygonMarketDataClient()
        self._market_fetcher = fetch_daily_snapshot
        self._session_snapshot: Optional[SessionStateSnapshot] = None
        self._prefetched_snapshot: Optional[SessionStateSnapshot] = None
        self._shared_context: Dict[str, Any] = {}
        if self._supervisor_agent:
            supervisor_meta = self._shared_context.setdefault("_meta", {}).setdefault("supervisor", {})
            supervisor_meta["agent_name"] = self._supervisor_agent.name
            supervisor_meta["specialists"] = [binding.lane for binding in self._supervisor_bundle.bindings]
        self._orchestrated = False
        self._hedged_completion: Dict[str, bool] = {}
        self._pending_artifact_events: List[Dict[str, Any]] = []
        self._artifact_flush_pending: bool = False
        self._chart_revision_missing_session: bool = False
        self._revision_directive: Optional["RevisionDirective"] = None
        self._agentic_revision_mode: bool = False
        self._lane_refresh_required: Dict[str, bool] = {}
        self._agent_retry_counts: Dict[str, int] = {}
        self._agent_cache_ttl: int = 600
        self._planner_event_bus: Optional[PlannerEventBus] = None
        self._sequencer_state: Optional[_SupervisorSequencerState] = None
        self._active_sequencer: Optional["PlannerSequencer"] = None  # type: ignore[name-defined]
        self._lane_retry_counts: Dict[str, int] = {}
        self._session_follow_up = False
        self._agent_tool_counters: Dict[str, int] = {}
        self._agent_tool_active_ids: Dict[str, str] = {}

    def _abort_stale_sequencer(self, *, reason: str = "restart") -> None:
        sequencer = self._active_sequencer
        if sequencer is None:
            return
        try:
            sequencer.abort_pending_lanes(reason=reason)
        except Exception:  # pragma: no cover - defensive logging
            logger.exception("Failed to abort pending lanes for reason=%s", reason)
        finally:
            if self._active_sequencer is sequencer:
                self._active_sequencer = None

    def set_session_follow_up(self, follow_up: bool) -> None:
        self._session_follow_up = bool(follow_up)
        self._planner.set_session_follow_up(follow_up)

    def _hedged_tool_aliases(self) -> List[str]:
        manifest = self._shared_context.get("tool_manifest")
        aliases: List[str] = []
        if manifest is not None:
            try:
                iterable = list(manifest)
            except TypeError:
                iterable = []
        else:
            iterable = []
        for entry in iterable:
            if not isinstance(entry, dict):
                continue
            name = str(entry.get("name") or "").strip()
            if not name:
                continue
            lowered = name.lower()
            if lowered in HEDGED_WEB_TOOLS or lowered.startswith("web_retriever"):
                aliases.append(lowered)
        if aliases:
            return sorted(set(aliases))
        if iterable:
            return []
        return list(HEDGED_WEB_TOOLS)

    def _hedged_accessories_ready(self) -> bool:
        results = self._shared_context.get("tool_results") or []
        if not isinstance(results, list):
            return False
        aliases = self._hedged_tool_aliases()
        if not aliases:
            self._hedged_completion = {}
            self._shared_context["hedged_accessories_status"] = {}
            return True
        seen: Dict[str, bool] = {alias: False for alias in aliases}
        planner_tickers = self._shared_context.get("planner", {}).get("tickers") or []
        stock_required = bool(planner_tickers)
        if stock_required:
            seen.setdefault("stock_tracker", False)

        def mark_ready(alias_key: str) -> None:
            if alias_key in seen:
                seen[alias_key] = True

        for entry in results:
            tool = str(entry.get("tool") or "").strip().lower()
            status = str(entry.get("status") or "").lower()
            ready_payload = bool(entry.get("payload")) or status in {"complete", "completed", "success", "ok"}
            if not ready_payload or status in {"error", "cancelled"}:
                continue
            if tool in seen:
                mark_ready(tool)
                continue
            if tool.startswith("web_retriever"):
                for alias in seen:
                    if alias.startswith("web_retriever"):
                        mark_ready(alias)
                continue
            if tool == "stock_tracker" and stock_required:
                mark_ready("stock_tracker")

        web_ctx = self._shared_context.get("web") or {}
        if isinstance(web_ctx, dict) and web_ctx.get("ready"):
            for alias in seen:
                if alias.startswith("web_retriever"):
                    mark_ready(alias)
        if stock_required and self._shared_context.get("stock_widget"):
            mark_ready("stock_tracker")
        elif not stock_required:
            seen["stock_tracker"] = True

        missing = [alias for alias, ready in seen.items() if not ready]
        self._hedged_completion = seen
        self._shared_context["hedged_accessories_status"] = seen
        return not missing

    def _build_specialist_card(self, event_name: str, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if event_name == "sql_ready":
            row_count = payload.get("row_count")
            columns = payload.get("columns") or []
            message_parts: List[str] = ["SQL dataset ready"]
            if isinstance(row_count, int):
                message_parts.append(f"rows: {row_count}")
            if columns:
                message_parts.append(f"columns: {min(len(columns), 6)}")
            return {
                "type": "sql_executor",
                "state": "ready",
                "title": "Generated SQL",
                "message": " | ".join(message_parts),
                "metadata": {
                    "row_count": row_count,
                    "columns": columns[:10] if isinstance(columns, list) else columns,
                },
            }
        if event_name == "chart_ready":
            chart_summary = payload.get("chart_summary") or {}
            chart_type = chart_summary.get("chart_type") if isinstance(chart_summary, dict) else None
            series_count = chart_summary.get("series_count") if isinstance(chart_summary, dict) else None
            parts = ["Chart specification ready"]
            if chart_type:
                parts.append(f"type: {chart_type}")
            if isinstance(series_count, int):
                parts.append(f"series: {series_count}")
            return {
                "type": "chart_builder",
                "state": "ready",
                "title": "Visualization Ready",
                "message": " | ".join(parts),
            }
        if event_name == "stock_ready":
            widget = payload.get("stock_widget") or {}
            raw_symbols = widget.get("symbols") if isinstance(widget, dict) else None
            symbols: List[str] = []
            if isinstance(raw_symbols, list):
                for item in raw_symbols:
                    if isinstance(item, (list, tuple)) and item:
                        candidate = item[0]
                    else:
                        candidate = item
                    if isinstance(candidate, str) and candidate.strip():
                        symbols.append(candidate.strip().upper())
            message = "Stock widget ready"
            if symbols:
                message = f"{message} | symbols: {', '.join(symbols[:3])}"
            return {
                "type": "stock_widget",
                "state": "ready",
                "title": "Market Tracker",
                "message": message,
                "symbols": symbols,
            }
        if event_name == "web_ready":
            web_ctx = payload.get("web_context") or {}
            if not isinstance(web_ctx, dict):
                web_ctx = {}
            snippets = web_ctx.get("snippets")
            summary = web_ctx.get("summary")
            topic = web_ctx.get("search_topic") or web_ctx.get("searchTopic") or web_ctx.get("query")
            normalized_snippets: List[Dict[str, Any]] = []
            if isinstance(snippets, list):
                for entry in snippets[:6]:
                    if not isinstance(entry, dict):
                        continue
                    normalized_snippets.append(
                        {
                            "title": entry.get("title"),
                            "snippet": entry.get("snippet"),
                            "url": entry.get("url"),
                            "display_url": entry.get("display_url") or entry.get("displayUrl"),
                            "published_at": entry.get("published_at") or entry.get("publishedAt"),
                        }
                    )
            return {
                "type": "web_context",
                "state": "ready",
                "title": "Online Research",
                "message": summary or "Web context collected",
                "topic": topic,
                "snippets": normalized_snippets,
            }
        return None

    def _get_accessories_gate(self) -> Optional[asyncio.Event]:
        runtime_state = self._shared_context.get("_runtime", {})
        event = runtime_state.get("accessories_ready")
        return event if isinstance(event, asyncio.Event) else None

    def _mark_accessories_ready(self) -> None:
        gate = self._get_accessories_gate()
        if gate and not gate.is_set():
            gate.set()

    async def _await_accessories_ready(self, timeout: float = 1.5) -> None:
        gate = self._get_accessories_gate()
        if not gate or gate.is_set():
            return
        try:
            await asyncio.wait_for(gate.wait(), timeout)
        except asyncio.TimeoutError:
            logger.debug(
                "Accessory gate wait timed out; continuing execution without ready signal.",
            )

    def _queue_artifact_event(self, event_name: str, payload: Dict[str, Any]) -> None:
        sanitized_payload = sanitize_for_json(payload)
        if not isinstance(sanitized_payload, dict):
            sanitized_payload = {"value": sanitized_payload}

        lane = self.ARTIFACT_LANE_MAP.get(event_name)
        fingerprint_seed = {
            "event": event_name,
            "lane": lane,
            "payload": sanitized_payload,
        }
        artifact_meta = self._shared_context.setdefault("_artifact_meta", {})
        hashes: Dict[str, str] = artifact_meta.setdefault("artifact_hashes", {})
        fingerprint = _hash_payload(fingerprint_seed)
        if hashes.get(event_name) == fingerprint:
            return
        hashes[event_name] = fingerprint

        enriched_payload = dict(sanitized_payload)
        specialist_card = self._build_specialist_card(event_name, enriched_payload)
        if specialist_card:
            enriched_payload["specialist_card"] = specialist_card
        if lane:
            enriched_payload.setdefault("lane", lane)
            enriched_payload.setdefault(
                "parallel_group",
                self.ARTIFACT_PARALLEL_GROUPS.get(event_name, self.DEFAULT_PARALLEL_GROUP),
            )
        else:
            enriched_payload.setdefault("parallel_group", self.DEFAULT_PARALLEL_GROUP)
        if "reused" not in enriched_payload:
            enriched_payload["reused"] = False
        enriched_payload.setdefault("flow_mode", self.flow_mode.value)
        enriched_payload.setdefault("ts", datetime.utcnow().isoformat())
        receipts_map = self._shared_context.setdefault("tool_receipts", {})
        if lane:
            enrich_accessory_payload(lane, enriched_payload, receipts=receipts_map)
        artifact_meta.setdefault("latest_payloads", {})[event_name] = enriched_payload
        if lane:
            artifact_meta.setdefault("latest_sources", {})[lane] = enriched_payload.get("source")
            if enriched_payload.get("reused"):
                reuse_event = build_lane_reuse_event(lane, enriched_payload, receipts=receipts_map)
                if reuse_event:
                    self._pending_artifact_events.append(reuse_event)
        event = {"event": event_name, "data": enriched_payload}
        self._pending_artifact_events.append(event)
        self._artifact_flush_pending = True
        try:
            logger.debug(
                "multi_agent.artifact_enqueued",
                extra={
                    "event": event_name,
                    "lane": lane,
                    "parallel_group": enriched_payload.get("parallel_group"),
                    "flow_mode": getattr(self, "flow_mode", FlowMode.MULTI_AGENT).value,
                },
            )
        except Exception:
            pass

    def _queue_supervisor_event(self, event_name: str, payload: Dict[str, Any]) -> None:
        event = apply_mode_metadata({"event": event_name, "data": payload}, self.flow_mode)
        self._pending_artifact_events.append(event)
        self._artifact_flush_pending = True

    def _drain_artifact_events(self) -> List[Dict[str, Any]]:
        pending = self._pending_artifact_events
        self._pending_artifact_events = []
        return pending

    def _sql_preview(self, sql_ctx: Dict[str, Any]) -> Dict[str, Any]:
        sample = sql_ctx.get("sample_data")
        if isinstance(sample, list):
            sample_preview = sample[:20]
        else:
            sample_preview = sample
        return {
            "sql": sql_ctx.get("sql"),
            "sql_id": sql_ctx.get("id"),
            "row_count": sql_ctx.get("row_count"),
            "columns": sql_ctx.get("columns"),
            "sample_data": sample_preview,
        }

    def _analysis_sources_snapshot(
        self,
        *,
        sql_ctx: Mapping[str, Any],
        stock_widget: Optional[Mapping[str, Any]],
        web_context: Optional[Mapping[str, Any]],
        bundle_sources: Mapping[str, Any],
    ) -> Dict[str, Any]:
        def _compact(entry: Dict[str, Any]) -> Dict[str, Any]:
            cleaned: Dict[str, Any] = {}
            for key, value in entry.items():
                if value is None:
                    continue
                if isinstance(value, (list, dict)) and not value:
                    continue
                if isinstance(value, str) and not value.strip():
                    continue
                cleaned[key] = value
            return cleaned

        def _lane_reused(*, lane: str, context: Mapping[str, Any], source_keys: Iterable[str]) -> bool:
            status = str(context.get("status") or "").lower()
            if status in {"reused", "cached"}:
                return True
            source_hint = str(context.get("source") or "").lower()
            if source_hint == "cached":
                return True
            for key in source_keys:
                tag = str(bundle_sources.get(key) or "").lower()
                if tag in {"cached", "reused"}:
                    return True
            return bool(context.get("reused"))

        sources: Dict[str, Dict[str, Any]] = {}

        if sql_ctx.get("sql") or sql_ctx.get("row_count") is not None:
            columns = list(sql_ctx.get("columns") or [])[:6]
            entry = _compact(
                {
                    "lane": "sql",
                    "label": "SQL data",
                    "row_count": sql_ctx.get("row_count"),
                    "columns": columns,
                    "reused": _lane_reused(
                        lane="sql",
                        context=sql_ctx,
                        source_keys=("sql_executor", "sql_execution", "sql_compilation"),
                    ),
                }
            )
            if entry:
                sources["sql"] = entry

        widget = stock_widget if isinstance(stock_widget, Mapping) else None
        if widget:
            raw_symbols = widget.get("symbols")
            symbols: List[str] = []
            if isinstance(raw_symbols, list):
                for item in raw_symbols:
                    candidate = None
                    if isinstance(item, (list, tuple)) and item:
                        candidate = item[0] if isinstance(item[0], str) else item[1] if len(item) > 1 else None
                    elif isinstance(item, str):
                        candidate = item
                    if isinstance(candidate, str) and candidate.strip():
                        symbols.append(candidate.strip().upper())
            entry = _compact(
                {
                    "lane": "stock",
                    "label": "Stock data",
                    "symbols": symbols[:6],
                    "reused": _lane_reused(
                        lane="stock",
                        context=self._shared_context.get("market", {}),
                        source_keys=("stock_tracker",),
                    ),
                }
            )
            if entry:
                sources["stock"] = entry

        web_ctx = web_context if isinstance(web_context, Mapping) else None
        if web_ctx:
            snippets = []
            raw_snippets = web_ctx.get("snippets")
            if isinstance(raw_snippets, list):
                for snippet in raw_snippets[:5]:
                    if isinstance(snippet, Mapping):
                        snippets.append(
                            {
                                "title": snippet.get("title"),
                                "url": snippet.get("url"),
                            }
                        )
            entry = _compact(
                {
                    "lane": "web",
                    "label": "Online research",
                    "summary": web_ctx.get("summary"),
                    "snippets": snippets,
                    "reused": _lane_reused(
                        lane="web",
                        context=web_ctx,
                        source_keys=("web_retriever", "web_search"),
                    ),
                }
            )
            if entry:
                sources["web"] = entry

        return sources

    def _analysis_bundle_snapshot(
        self,
        *,
        analysis_ctx: Mapping[str, Any],
        sql_ctx: Mapping[str, Any],
        stock_widget: Optional[Mapping[str, Any]],
        web_context: Optional[Mapping[str, Any]],
    ) -> Optional[Dict[str, Any]]:
        bundle: Dict[str, Any] = {}

        narrative = ""
        if isinstance(analysis_ctx, Mapping):
            narrative = str(analysis_ctx.get("final") or "").strip()
        if narrative:
            bundle["narrative"] = narrative

        if isinstance(sql_ctx, Mapping) and (sql_ctx.get("sql") or sql_ctx.get("row_count") is not None):
            sql_entry: Dict[str, Any] = {}
            sql_text = sql_ctx.get("sql")
            if isinstance(sql_text, str) and sql_text.strip():
                sql_entry["query"] = sql_text.strip()
            row_count = sql_ctx.get("row_count")
            if isinstance(row_count, int):
                sql_entry["row_count"] = row_count
            columns = sql_ctx.get("columns")
            if isinstance(columns, Sequence):
                preview_cols = [str(col) for col in columns if isinstance(col, str)][:6]
                if preview_cols:
                    sql_entry["columns"] = preview_cols
            sample_data = sql_ctx.get("sample_data")
            if isinstance(sample_data, Sequence):
                samples: List[Any] = []
                for row in sample_data[:3]:
                    if isinstance(row, Mapping):
                        samples.append({str(k): v for k, v in row.items()})
                    else:
                        samples.append(row)
                if samples:
                    sql_entry["sample_rows"] = samples
            if sql_entry:
                bundle["sql"] = sql_entry

        if isinstance(web_context, Mapping):
            web_entry: Dict[str, Any] = {}
            summary = web_context.get("summary")
            if isinstance(summary, str) and summary.strip():
                web_entry["summary"] = summary.strip()
            topic = (
                web_context.get("search_topic")
                or web_context.get("searchTopic")
                or web_context.get("query")
            )
            if isinstance(topic, str) and topic.strip():
                web_entry["topic"] = topic.strip()
            snippets = web_context.get("snippets")
            if isinstance(snippets, Sequence):
                normalized_snippets: List[Dict[str, Any]] = []
                for snippet in snippets[:3]:
                    if not isinstance(snippet, Mapping):
                        continue
                    normalized_snippets.append(
                        {
                            "title": snippet.get("title"),
                            "snippet": snippet.get("snippet"),
                            "url": snippet.get("url"),
                            "display_url": snippet.get("display_url") or snippet.get("displayUrl"),
                        }
                    )
                if normalized_snippets:
                    web_entry["snippets"] = normalized_snippets
            if web_entry:
                bundle["web"] = web_entry

        if isinstance(stock_widget, Mapping):
            stock_entry: Dict[str, Any] = {}
            raw_symbols = stock_widget.get("symbols")
            symbols: List[str] = []
            if isinstance(raw_symbols, Sequence):
                for item in raw_symbols:
                    candidate = None
                    if isinstance(item, (list, tuple)) and item:
                        candidate = item[0]
                    elif isinstance(item, str):
                        candidate = item
                    if isinstance(candidate, str) and candidate.strip():
                        symbols.append(candidate.strip().upper())
            if symbols:
                stock_entry["symbols"] = symbols[:3]
            chart_type = stock_widget.get("chartType") or stock_widget.get("chart_type")
            if isinstance(chart_type, str) and chart_type.strip():
                stock_entry["chart_type"] = chart_type.strip()
            generated_at = stock_widget.get("generated_at") or stock_widget.get("generatedAt")
            if isinstance(generated_at, str) and generated_at.strip():
                stock_entry["generated_at"] = generated_at.strip()
            change_pct = stock_widget.get("change_percent")
            if isinstance(change_pct, (int, float)):
                stock_entry["change_percent"] = change_pct
            latest_close = stock_widget.get("latest_close")
            if isinstance(latest_close, (int, float)):
                stock_entry["latest_close"] = latest_close
            if stock_entry:
                bundle["stock"] = stock_entry

        if not bundle:
            return None

        sanitized = sanitize_for_json(bundle)
        if isinstance(sanitized, dict) and sanitized:
            return sanitized
        return None

    def _lane_state_snapshot(self) -> Dict[str, str]:
        if getattr(self, "_latest_lane_states", None):
            return dict(self._latest_lane_states)
        bundle_sources = self._shared_context.get("_meta", {}).get("bundle_sources", {})

        def classify(ctx: Mapping[str, Any], *, has_payload: bool, source_keys: Iterable[str]) -> str:
            status = str(ctx.get("status") or "").lower()
            if status in {"reused", "cached"}:
                return "reused"
            source_hint = str(ctx.get("source") or "").lower()
            if source_hint == "cached":
                return "reused"
            for key in source_keys:
                tag = str(bundle_sources.get(key) or "").lower()
                if tag in {"cached", "reused"}:
                    return "reused"
            if has_payload:
                return "fresh"
            return "missing"

        sql_ctx = self._shared_context.get("sql", {})
        chart_ctx = self._shared_context.get("chart", {})
        analysis_ctx = self._shared_context.get("analysis", {})
        market_ctx = self._shared_context.get("market", {})
        web_ctx = self._shared_context.get("web", {})
        planner_ctx = self._shared_context.get("planner", {})
        intent_state = "missing"
        if planner_ctx.get("intent_reused"):
            intent_state = "reused"
        elif planner_ctx.get("intent_key") or planner_ctx.get("slots"):
            intent_state = "fresh"

        lane_states = {
            "intent": intent_state,
            "sql": classify(
                sql_ctx,
                has_payload=bool(sql_ctx.get("sql") or sql_ctx.get("row_count") is not None),
                source_keys=("sql_executor", "sql_execution", "sql_compilation"),
            ),
            "chart": classify(
                chart_ctx,
                has_payload=bool(chart_ctx.get("spec")),
                source_keys=("chart_builder",),
            ),
            "analysis": classify(
                analysis_ctx,
                has_payload=bool(analysis_ctx.get("final") or analysis_ctx.get("summary")),
                source_keys=("analysis_generation", "analysis_agent", "insight_reviewer", "supervisor_summary"),
            ),
            "market": classify(
                market_ctx,
                has_payload=bool(self._shared_context.get("stock_widget")),
                source_keys=("stock_tracker",),
            ),
            "web": classify(
                web_ctx,
                has_payload=bool(web_ctx.get("summary") or web_ctx.get("snippets")),
                source_keys=("web_retriever", "web_search"),
            ),
        }
        return lane_states

    def _select_follow_up_route(self, lane_states: Mapping[str, str]) -> FollowUpRoute:
        if (
            lane_states.get("market") == "fresh"
            and all(lane_states.get(lane) == "reused" for lane in ("sql", "chart", "analysis", "web") if lane in lane_states)
        ):
            return FollowUpRoute.STOCK_ONLY
        if (
            lane_states.get("sql") == "reused"
            and any(lane_states.get(lane) == "fresh" for lane in ("chart", "analysis"))
        ):
            return FollowUpRoute.REUSE_SQL
        if any(lane_states.get(lane) == "fresh" for lane in ("sql", "chart", "analysis", "web")):
            return FollowUpRoute.FULL_PIPELINE
        return self.follow_up_route

    def _initial_lane_states(self) -> Dict[str, str]:
        route = getattr(self, "follow_up_route", FollowUpRoute.FULL_PIPELINE)
        if route == FollowUpRoute.REUSE_SQL:
            return {
                "intent": "pending",
                "sql": "reused",
                "chart": "reused",
                "analysis": "reused",
                "market": "skipped",
                "web": "skipped",
            }
        if route == FollowUpRoute.STOCK_ONLY:
            return {
                "intent": "pending",
                "sql": "reused",
                "chart": "reused",
                "analysis": "reused",
                "market": "pending",
                "web": "reused",
            }
        return {
            "intent": "pending",
            "sql": "pending",
            "chart": "queued",
            "analysis": "queued",
            "market": "pending",
            "web": "pending",
        }

    def _sync_lane_states_from_sequencer(
        self,
        lane_states: Dict[str, str],
        sequencer: PlannerSequencer,
    ) -> None:
        lane_states.clear()
        lane_states.update(sequencer.lane_presentations())

    def _emit_lane_summary(self, lane_states: Mapping[str, str]) -> Optional[Dict[str, Any]]:
        meta = self._shared_context.setdefault("_meta", {})
        if meta.get("lane_summary_emitted"):
            return None

        normalized_states = dict(lane_states)
        if self.follow_up_route == FollowUpRoute.REUSE_SQL:
            for lane in ("sql", "analysis", "market", "web"):
                state = normalized_states.get(lane)
                if state in {"fresh", "missing", "pending", "running", "queued"}:
                    normalized_states[lane] = "reused"

        rerun_lanes = [lane for lane, status in normalized_states.items() if status in {"fresh", "missing", "pending"}]
        reuse_lanes = [lane for lane, status in normalized_states.items() if status in {"reused", "cached"}]

        route = self._select_follow_up_route(lane_states)
        if route != self.follow_up_route:
            self.follow_up_route = route

        payload = {
            "lane_summary": dict(normalized_states),
            "parallel_group": "supervisor_summary",
            "ts": datetime.utcnow().isoformat(),
            "flow_mode": self.flow_mode.value,
            "rerun_scope": {
                "rerun": rerun_lanes,
                "reuse": reuse_lanes,
                "route": self.follow_up_route.value,
            },
        }

        if "chart" in rerun_lanes and "sql" in reuse_lanes:
            payload["decision"] = "chart_revision"
        elif rerun_lanes:
            payload["decision"] = "fresh_execution"
        else:
            payload["decision"] = "reuse_snapshot"

        meta["lane_summary_emitted"] = True
        return {"event": "agent_decision", "data": payload}

    def _chart_preview(self, chart_ctx: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "chart_spec": chart_ctx.get("spec"),
            "chart_spec_id": chart_ctx.get("spec_id"),
            "chart_summary": chart_ctx.get("spec_summary"),
        }

    def _maybe_queue_sql_ready(self) -> None:
        sql_ctx = self._shared_context.get("sql", {})
        if sql_ctx.get("_emitted_ready"):
            return
        if sql_ctx.get("sql") and sql_ctx.get("row_count") is not None:
            payload = self._sql_preview(sql_ctx)
            payload["schedule_stage"] = "sql"
            status = str(sql_ctx.get("status") or "").lower()
            if status in {"reused", "cached"}:
                payload["reused"] = True
                payload["source"] = "cached"
            else:
                payload.setdefault("source", "fanout")
            self._queue_artifact_event("sql_ready", payload)
            sql_ctx["_emitted_ready"] = True

    def _maybe_queue_chart_ready(self) -> None:
        chart_ctx = self._shared_context.get("chart", {})
        if chart_ctx.get("_emitted_ready"):
            return
        if chart_ctx.get("spec"):
            payload = self._chart_preview(chart_ctx)
            payload["schedule_stage"] = "chart"
            status = str(chart_ctx.get("status") or "").lower()
            if status in {"reused", "cached"}:
                payload["reused"] = True
                payload["source"] = "cached"
            else:
                payload.setdefault("source", "fanout")
            self._queue_artifact_event("chart_ready", payload)
            chart_ctx["_emitted_ready"] = True

    def _maybe_queue_stock_ready(self) -> None:
        widget = self._shared_context.get("stock_widget")
        if not widget:
            return
        meta = self._shared_context.setdefault("_artifact_meta", {})
        if meta.get("stock_ready"):
            return
        payload = {"stock_widget": widget, "schedule_stage": "hedged_accessories"}
        market_ctx = self._shared_context.get('market', {})
        if isinstance(market_ctx, dict):
            source = market_ctx.get('source')
            if source:
                payload["source"] = source
                if source in {"revision_snapshot", "cached"}:
                    payload["reused"] = True
            elif market_ctx.get('snapshot') and not market_ctx.get('refresh', False):
                payload.setdefault("source", "fanout")
        self._queue_artifact_event("stock_ready", payload)
        meta["stock_ready"] = True
        self._maybe_emit_hedged_accessories_complete()

    def _maybe_queue_web_ready(self) -> None:
        web_ctx = self._shared_context.get("web")
        if not web_ctx:
            return
        meta = self._shared_context.setdefault("_artifact_meta", {})
        if meta.get("web_ready"):
            return
        payload = {"web_context": web_ctx, "schedule_stage": "hedged_accessories"}
        source = None
        if isinstance(web_ctx, dict):
            if web_ctx.get("from_cache"):
                source = "cached"
                payload["reused"] = True
            else:
                source = web_ctx.get("source")
        if source:
            payload["source"] = source
        else:
            payload.setdefault("source", "fanout")
        self._queue_artifact_event("web_ready", payload)
        meta["web_ready"] = True
        self._maybe_emit_hedged_accessories_complete()

    def _emit_hedged_accessories_complete(self, *, queue_only: bool = False) -> Optional[Dict[str, Any]]:
        if self._shared_context.get("hedged_accessories_emitted"):
            return None
        tools = list(self._hedged_completion.keys())
        event = {
            "event": "hedged_accessories_complete",
            "data": {
                "tools": tools,
                "schedule_stage": "hedged_accessories",
                "parallel_group": "specialist_fanout",
                "ts": datetime.utcnow().isoformat(),
            },
        }
        self._shared_context["hedged_accessories_emitted"] = True
        if queue_only:
            self._pending_artifact_events.append(event)
            self._artifact_flush_pending = True
            return None
        return self._annotate(event)

    def _maybe_emit_hedged_accessories_complete(self) -> None:
        if self._shared_context.get("hedged_accessories_emitted"):
            return
        if not self._hedged_accessories_ready():
            return
        self._emit_hedged_accessories_complete(queue_only=True)

    def _maybe_queue_analysis_ready(self) -> None:
        analysis_ctx = self._shared_context.get("analysis", {})
        if analysis_ctx.get("_emitted_ready"):
            return
        if analysis_ctx.get("final"):
            analysis_length_value = analysis_ctx.get("length")
            if analysis_length_value is None:
                analysis_length_value = analysis_ctx.get("analysis_length")
            payload = {
                "analysis": analysis_ctx.get("final"),
                "analysis_length": analysis_length_value,
                "schedule_stage": "analysis",
            }
            self._queue_artifact_event("analysis_ready", payload)
            analysis_ctx["_emitted_ready"] = True

    def _component_status(self) -> Dict[str, bool]:
        sql_ctx = self._shared_context.get("sql", {}) or {}
        has_sql = bool(sql_ctx.get("sql"))
        if not has_sql and sql_ctx.get("sample_data"):
            has_sql = True
        if not has_sql:
            row_count = sql_ctx.get("row_count")
            has_sql = row_count is not None and row_count != 0
        if not has_sql and sql_ctx.get("columns"):
            has_sql = True

        stock_widget = self._shared_context.get("stock_widget")
        has_stock = bool(stock_widget)
        if not has_stock:
            market_ctx = self._shared_context.get("market", {}) or {}
            if isinstance(market_ctx, dict):
                has_stock = bool(market_ctx.get("snapshot"))
        analysis_ctx = self._shared_context.get("analysis", {}) or {}
        if not has_stock and isinstance(analysis_ctx, dict):
            bundle = analysis_ctx.get("bundle")
            if isinstance(bundle, dict) and bundle.get("stock_widget"):
                has_stock = True

        web_ctx = self._shared_context.get("web") or {}
        has_web = False
        if isinstance(web_ctx, dict):
            if web_ctx.get("summary"):
                has_web = True
            else:
                snippets = web_ctx.get("snippets") or web_ctx.get("articles")
                if isinstance(snippets, list) and snippets:
                    has_web = True
        if not has_web and isinstance(analysis_ctx, dict):
            bundle = analysis_ctx.get("bundle")
            if isinstance(bundle, dict):
                web_bundle = bundle.get("web_context")
                if isinstance(web_bundle, dict):
                    if web_bundle.get("summary"):
                        has_web = True
                    else:
                        snippets = web_bundle.get("snippets") or web_bundle.get("articles")
                        if isinstance(snippets, list) and snippets:
                            has_web = True
        return {"sql": has_sql, "stock": has_stock, "web": has_web}

    def _build_final_answer_payload(self, analysis_text: Optional[str]) -> Optional[Dict[str, Any]]:
        status = self._component_status()
        missing = [component for component in ("sql", "stock", "web") if not status.get(component, False)]
        text_value: Optional[str]
        if isinstance(analysis_text, str):
            stripped = analysis_text.strip()
            text_value = stripped or None
        else:
            text_value = None
        human_labels = {
            "sql": "SQL data",
            "stock": "stock data",
            "web": "online research data",
        }
        note: Optional[str] = None
        reuse_scope = (
            self.follow_up_route == FollowUpRoute.REUSE_SQL
            and not self._chart_revision_missing_session
        )
        if self._chart_revision_missing_session:
            missing = ["sql", "stock", "web"]
            note = (
                "I couldn't apply the chart update because the saved session expired. "
                "Ask me to rerun the full analysis so I can rebuild fresh data and charts."
            )
        elif reuse_scope:
            missing = []
            note = "Chart revision applied. Reused cached datasets for consistency."
        elif missing:
            # Suppress redundant "Pending lanes" note to avoid noisy cards.
            note = None
        parts: List[str] = []
        if text_value:
            parts.append(text_value)
        if note:
            parts.append(note)
        message = "\n\n".join(part for part in parts if part).strip()
        if not message:
            if note:
                message = note
            else:
                return None
        return {
            "message": message,
            "missing_components": missing,
            "analysis_available": bool(text_value),
        }

    def prime_with_snapshot(self, snapshot: Optional[SessionStateSnapshot]) -> None:
        self._prefetched_snapshot = snapshot
        self._session_snapshot = snapshot
        self._planner.prime_with_snapshot(snapshot)

    def set_revision_directive(self, directive: Optional["RevisionDirective"]) -> None:
        self._revision_directive = directive
        self._agentic_revision_mode = bool(directive.agentic if directive else False)
        self._planner.set_revision_directive(directive)

    def set_follow_up_route(self, route: FollowUpRoute) -> None:
        self.follow_up_route = route
        self._planner.set_follow_up_route(route)

    def set_revision_targets(self, targets: Iterable[str]) -> None:
        self._planner.set_revision_targets(targets)

    def set_lane_refresh_requirements(self, requirements: Optional[Mapping[str, Any]]) -> None:
        normalized: Dict[str, bool] = {}
        if requirements:
            for lane, required in requirements.items():
                if lane is None:
                    continue
                key = str(lane).strip().lower()
                if not key:
                    continue
                normalized[key] = bool(required)
                if required is False:
                    normalized[key] = False
        self._lane_refresh_required = normalized
        if self._shared_context is not None:
            self._shared_context.setdefault("lane_refresh_required", {})
            self._shared_context["lane_refresh_required"] = dict(normalized)
        self._planner.set_lane_refresh_requirements(requirements)

    def set_analysis_refresh_mode(self, mode: Optional[str]) -> None:
        self._planner.set_analysis_refresh_mode(mode)

    def set_planner_event_bus(self, event_bus: Optional[PlannerEventBus]) -> None:
        self._planner_event_bus = event_bus

    def build_planner_orchestrator(
        self,
        *,
        metadata: Optional[Dict[str, Any]] = None,
        lane_complete_callback: Optional[LaneCompleteCallback] = None,
    ) -> PlannerOrchestratorAdapter:
        base_metadata = {
            "flow": self.flow_label,
            "flow_mode": self.flow_mode.value,
        }
        if metadata:
            base_metadata.update(metadata)
        callback = lane_complete_callback or self._handle_lane_complete
        return PlannerOrchestratorAdapter(
            intent_runner=self._intent_stage,
            sql_runner=self._sql_stage,
            web_runner=self._web_stage,
            market_runner=self._market_stage,
            analysis_runner=self._analysis_stage,
            metadata=base_metadata,
            optional_lanes=("web", "market"),
            lane_complete_callback=callback,
        )

    def _handle_lane_complete(
        self,
        lane: str,
        success: bool,
        reused: bool,
        reason: Optional[str],
    ) -> None:
        state = self._sequencer_state
        if state is None:
            return
        ctx = getattr(state, "ctx", None)
        if ctx is None:
            return
        if lane == "web":
            setattr(ctx, "reused_web", bool(reused))
        elif lane == "market":
            setattr(ctx, "reused_stock", bool(reused))

    def _handle_retry(
        self,
        lane: str,
        attempt: int,
        reason: Optional[str],
        error: Optional[str],
        metadata: Optional[Mapping[str, Any]],
    ) -> None:
        retry_count = max(int(attempt) - 1, 0)
        if retry_count <= 0:
            return
        self._lane_retry_counts[lane] = retry_count

    def _annotate(self, event: Dict[str, Any]) -> Dict[str, Any]:
        annotated = apply_mode_metadata(event, self.flow_mode)
        data = annotated.setdefault("data", {})
        if isinstance(data, Mapping):
            mutable = dict(data)
            mutable.setdefault("follow_up_route", self.follow_up_route.value)
            mutable.setdefault("prompt_versions", dict(self._prompt_versions))
            if self._agentic_revision_mode:
                mutable.setdefault("agentic_revision", True)
            annotated["data"] = sanitize_for_json(mutable)
        else:
            annotated["data"] = data
        return annotated

    def _maybe_tag_session_metadata(
        self,
        event: Dict[str, Any],
        session_id: Optional[str],
    ) -> Dict[str, Any]:
        if not session_id:
            return event
        name = event.get("event")
        if name not in self.SESSION_AWARE_EVENTS:
            return event
        data = event.setdefault("data", {})
        if isinstance(data, dict) and not data.get("session_id"):
            data["session_id"] = session_id
        return event

    def _emit_lane_transition(
        self,
        lane: Optional[str],
        *,
        status: str,
        success: Optional[bool] = None,
        reused: Optional[bool] = None,
        error: Optional[str] = None,
        reason: Optional[str] = None,
    ) -> None:
        if not lane:
            return
        payload: Dict[str, Any] = {
            "lane": lane,
            "status": status,
            "ts": datetime.utcnow().isoformat(),
        }
        if success is not None:
            payload["success"] = success
        if reused is not None:
            payload["reused"] = reused
        if error:
            payload["error"] = error
        if reason:
            payload["reason"] = reason
        event = apply_mode_metadata({"event": "planner_lane_transition", "data": payload}, self.flow_mode)
        self._pending_artifact_events.append(event)
        self._artifact_flush_pending = True
        if self._planner_event_bus:
            self._planner_event_bus.emit_lane_transition(
                lane=lane,
                status=status,
                success=success,
                error=error,
                reused=reused,
                reason=reason,
            )

    def _get_tool_metadata_for_step(self, step: Optional[str]) -> Optional[Dict[str, Any]]:
        if not step:
            return None
        registry_name = self.TOOL_METADATA_STEP_MAP.get(step)
        if not registry_name:
            return None
        return self._tool_metadata_by_registry.get(registry_name)

    def _get_tool_metadata_for_event(self, event_name: Optional[str]) -> Optional[Dict[str, Any]]:
        if not event_name:
            return None
        registry_name = self.TOOL_METADATA_EVENT_MAP.get(event_name)
        if not registry_name:
            return None
        return self._tool_metadata_by_registry.get(registry_name)

    def _get_tool_metadata_for_role(self, role: Optional[str]) -> Optional[Dict[str, Any]]:
        if not role:
            return None
        metadata = self._tool_metadata_by_role.get(role)
        if metadata:
            return metadata
        registry_name = self.TOOL_METADATA_ROLE_MAP.get(role)
        if registry_name:
            return self._tool_metadata_by_registry.get(registry_name)
        return None

    def latest_artifacts(self):
        return self._planner.latest_artifacts()

    async def _forward_with_hooks(
        self,
        stream: AsyncGenerator[Dict[str, Any], None],
        hooks: _MultiAgentHooks,
        query: str,
        session_id: Optional[str],
        *,
        ensure_session_event: bool = True,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        hook_ctx: Dict[str, Any] = {"query": query, "session_id": session_id}
        session_emitted = False

        async def _maybe_emit_session_event() -> AsyncGenerator[Dict[str, Any], None]:
            nonlocal session_emitted
            if session_emitted or not ensure_session_event:
                if False:
                    yield {}
                return
            session_identifier = hook_ctx.get("session_id")
            if not session_identifier:
                if False:
                    yield {}
                return
            raw_event = EventEmitter.session_started(session_identifier)
            async for pre_event in hooks.before_event(hook_ctx, raw_event):
                yield self._maybe_tag_session_metadata(
                    self._annotate(pre_event),
                    hook_ctx.get("session_id"),
                )
            annotated = self._maybe_tag_session_metadata(self._annotate(raw_event), session_identifier)
            yield annotated
            async for post_event in hooks.after_event(hook_ctx, raw_event):
                yield self._maybe_tag_session_metadata(
                    self._annotate(post_event),
                    hook_ctx.get("session_id"),
                )
            session_emitted = True

        try:
            async for start_event in hooks.on_flow_start(hook_ctx):
                yield self._maybe_tag_session_metadata(self._annotate(start_event), hook_ctx.get("session_id"))
            async for session_event in _maybe_emit_session_event():
                yield session_event
            async for event in stream:
                async for pre_event in hooks.before_event(hook_ctx, event):
                    yield self._maybe_tag_session_metadata(
                        self._annotate(pre_event),
                        hook_ctx.get("session_id"),
                    )
                annotated_event = self._maybe_tag_session_metadata(
                    self._annotate(event),
                    hook_ctx.get("session_id"),
                )
                yield annotated_event
                if event.get("event") == "session_started":
                    data = event.get("data") or {}
                    hook_ctx["session_id"] = data.get("session_id", hook_ctx.get("session_id"))
                    session_emitted = True
                else:
                    data = annotated_event.get("data") or {}
                    fallback_session = data.get("session_id")
                    if fallback_session and not hook_ctx.get("session_id"):
                        hook_ctx["session_id"] = fallback_session
                async for session_event in _maybe_emit_session_event():
                    yield session_event
                async for post_event in hooks.after_event(hook_ctx, event):
                    yield self._maybe_tag_session_metadata(
                        self._annotate(post_event),
                        hook_ctx.get("session_id"),
                    )
        except BaseException as exc:
            async for end_event in hooks.on_flow_end(hook_ctx, error=exc):
                yield self._maybe_tag_session_metadata(
                    self._annotate(end_event),
                    hook_ctx.get("session_id"),
                )
            raise
        else:
            async for end_event in hooks.on_flow_end(hook_ctx):
                yield self._maybe_tag_session_metadata(
                    self._annotate(end_event),
                    hook_ctx.get("session_id"),
                )
        if ensure_session_event and not session_emitted:
            session_identifier = hook_ctx.get("session_id") or "unknown_session"
            raise RuntimeError(f"session_started event missing for {session_identifier}")

    async def _intent_stage(self) -> AsyncGenerator[Dict[str, Any], None]:
        state = self._sequencer_state
        if state is None:
            raise RuntimeError("Sequencer state not initialized")
        ctx = state.ctx
        registry = state.registry
        executed = state.executed
        hooks = state.hooks

        if (not state.is_revision_follow_up) or ("classification" not in executed):
            async for event in self._forward_with_hooks(
                registry.invoke("classification", self._planner, ctx, executed=executed),
                hooks,
                state.query,
                state.session_id,
            ):
                yield event
            await self._planner._persist_session_state(ctx, record_artifacts=True)
            if not getattr(ctx, "is_financial_query", True):
                ctx.halted = True
                return
        elif state.is_revision_follow_up and "classification" in executed:
            await self._planner._persist_session_state(ctx, record_artifacts=True)

        tool_sequence: Tuple[str, ...]
        if state.is_revision_follow_up:
            needs_intent = ctx.intent is None
            needs_plan = (ctx.plan or ctx.provisional_plan) is None
            sequence_parts: List[str] = []
            if needs_intent:
                sequence_parts.append("intent_detection")
            else:
                executed.add("intent_detection")
            if needs_plan:
                sequence_parts.append("plan_generation")
            else:
                executed.add("plan_generation")
            tool_sequence = tuple(sequence_parts)
        else:
            tool_sequence = ("intent_detection", "clarification", "plan_generation")

        for tool_name in tool_sequence:
            async for event in self._forward_with_hooks(
                registry.invoke(tool_name, self._planner, ctx, executed=executed),
                hooks,
                state.query,
                state.session_id,
            ):
                yield event
            await self._planner._persist_session_state(ctx, record_artifacts=True)
            executed.add(tool_name)

        if ctx.intent is None or (ctx.plan or ctx.provisional_plan) is None:
            ctx.halted = True
            return

        fanout_adapters: Tuple[Any, ...] = self._planner._fanout_adapters_for_context(ctx)
        should_run_parallel = (
            ctx.parallelism_enabled
            and bool(fanout_adapters)
            and not (ctx.reuse_sql and ctx.reuse_snapshot_active)
        )
        if should_run_parallel:
            runtime = self._planner._start_tool_parallelism(
                ctx,
                adapters=fanout_adapters,
            )
            state.tool_runtime = runtime
            state.tool_state = {"queue": runtime.queue, "active": True, "runtime": runtime}

            async def _drain_tool_deltas() -> AsyncGenerator[Dict[str, Any], None]:
                for tool_event in self._planner._collect_tool_deltas_now(state.tool_state, ctx):
                    yield tool_event

            async for event in self._forward_with_hooks(
                _drain_tool_deltas(),
                hooks,
                state.query,
                state.session_id,
            ):
                yield event

        state.derived_targets = set(derive_revision_targets(ctx, intent_lane_map=_INTENT_LANE_HINTS) or set())
        revision_plan = build_revision_plan(ctx, targets=state.derived_targets)
        apply_revision_plan(ctx, revision_plan)
        state.revision_plan = revision_plan
        state.run_sql_lane = revision_plan.run_sql_lane
        state.run_chart_lane = revision_plan.run_chart_lane
        state.run_analysis_lane = revision_plan.run_analysis_lane
        state.stock_only_run = revision_plan.stock_only

    async def _sql_stage(self) -> AsyncGenerator[Dict[str, Any], None]:
        state = self._sequencer_state
        if state is None:
            raise RuntimeError("Sequencer state not initialized")
        ctx = state.ctx
        if getattr(ctx, "halted", False):
            return
        hooks = state.hooks

        revision_plan = state.revision_plan
        revision_targets: Set[str] = set(revision_plan.targets) if revision_plan else set()
        if revision_targets:
            follow_up_route = getattr(self, "follow_up_route", None)
            revision_event = annotate_revision_event(
                build_revision_request_event(
                    ctx,
                    flow_mode_value=self.flow_mode.value,
                    follow_up_route_value=follow_up_route.value if follow_up_route is not None else None,
                ),
                ctx,
            )

            async def _revision_stream() -> AsyncGenerator[Dict[str, Any], None]:
                yield revision_event

            async for event in self._forward_with_hooks(
                _revision_stream(),
                hooks,
                state.query,
                state.session_id,
            ):
                yield event

        async for event in self._forward_with_hooks(
            stream_sql_lane(
                self._planner,
                ctx=ctx,
                registry=state.registry,
                executed=state.executed,
                tool_state=state.tool_state,
                run_sql_lane=state.run_sql_lane,
            ),
            hooks,
            state.query,
            state.session_id,
        ):
            yield event

        async for event in self._forward_with_hooks(
            self._planner._stream_with_tool_state(
                ensure_analysis_dependencies(self._planner, ctx, mode_config=state.mode_config),
                state.tool_state,
                ctx,
            ),
            hooks,
            state.query,
            state.session_id,
        ):
            yield event

    async def _web_stage(self) -> AsyncGenerator[Dict[str, Any], None]:
        state = self._sequencer_state
        if state is None:
            raise RuntimeError("Sequencer state not initialized")
        ctx = state.ctx
        if getattr(ctx, "halted", False):
            return
        async for event in self._forward_with_hooks(
            self._planner.refresh_web_lane(
                ctx,
                reason="sequencer_web_refresh",
                source="multi_agent_sequencer",
            ),
            state.hooks,
            state.query,
            state.session_id,
        ):
            yield event

    async def _market_stage(self) -> AsyncGenerator[Dict[str, Any], None]:
        state = self._sequencer_state
        if state is None:
            raise RuntimeError("Sequencer state not initialized")
        ctx = state.ctx
        if getattr(ctx, "halted", False):
            return
        async for event in self._forward_with_hooks(
            self._planner.refresh_market_lane(
                ctx,
                reason="sequencer_market_refresh",
                source="multi_agent_sequencer",
            ),
            state.hooks,
            state.query,
            state.session_id,
        ):
            yield event

    async def _analysis_stage(self) -> AsyncGenerator[Dict[str, Any], None]:
        state = self._sequencer_state
        if state is None:
            raise RuntimeError("Sequencer state not initialized")
        ctx = state.ctx
        hooks = state.hooks
        try:
            if state.stock_only_run:
                ctx.reused_stock = False
                if state.tool_state and state.tool_state.get("active", False):
                    async for event in self._forward_with_hooks(
                        self._planner._drain_tool_state_async(state.tool_state, ctx),
                        hooks,
                        state.query,
                        state.session_id,
                    ):
                        yield event
                else:
                    runtime = self._planner._start_tool_parallelism(
                        ctx,
                        adapters=(StockTrackerAdapter(),),
                        concurrency_override=1,
                    )
                    ad_hoc_state = {"queue": runtime.queue, "active": True, "runtime": runtime}
                    try:
                        async for event in self._forward_with_hooks(
                            self._planner._drain_tool_state_async(ad_hoc_state, ctx),
                            hooks,
                            state.query,
                            state.session_id,
                        ):
                            yield event
                    finally:
                        await runtime.close()
                await self._planner._persist_session_state(ctx, record_artifacts=True)

                analysis_event = _build_reused_analysis_event(self.flow_mode, ctx)

                async def _analysis_reuse_stream() -> AsyncGenerator[Dict[str, Any], None]:
                    if analysis_event:
                        yield analysis_event

                async for event in self._forward_with_hooks(
                    _analysis_reuse_stream(),
                    hooks,
                    state.query,
                    state.session_id,
                ):
                    yield event

                banner_config = FOLLOW_UP_BANNERS.get(
                    ctx.follow_up_route,
                    FOLLOW_UP_BANNERS[FollowUpRoute.FULL_PIPELINE],
                )
                banner_event = EventEmitter.progress("follow_up_route", banner_config["message"])
                banner_event["data"]["route"] = ctx.follow_up_route.value
                banner_event["data"]["ts"] = datetime.utcnow().isoformat()
                session_identifier = getattr(ctx, "session_id", None)
                if session_identifier:
                    banner_event["data"]["session_id"] = session_identifier

                async def _banner_stream() -> AsyncGenerator[Dict[str, Any], None]:
                    yield banner_event

                async for event in self._forward_with_hooks(
                    _banner_stream(),
                    hooks,
                    state.query,
                    state.session_id,
                ):
                    yield event

                planner_payload = _build_planner_result_payload(ctx)
                result_event = EventEmitter.result("planner_result", planner_payload)
                result_event["event"] = "planner_result"
                result_event["data"]["ts"] = datetime.utcnow().isoformat()
                if session_identifier:
                    result_event["data"]["session_id"] = session_identifier

                async def _planner_result_stream() -> AsyncGenerator[Dict[str, Any], None]:
                    yield result_event

                async for event in self._forward_with_hooks(
                    _planner_result_stream(),
                    hooks,
                    state.query,
                    state.session_id,
                ):
                    yield event
            else:
                if getattr(ctx, "halted", False):
                    return

                async for event in self._forward_with_hooks(
                    stream_chart_lane(
                        self._planner,
                        ctx=ctx,
                        registry=state.registry,
                        executed=state.executed,
                        tool_state=state.tool_state,
                        run_chart_lane=state.run_chart_lane,
                    ),
                    hooks,
                    state.query,
                    state.session_id,
                ):
                    yield event

                async for event in self._forward_with_hooks(
                    stream_analysis_lane(
                        self._planner,
                        ctx=ctx,
                        registry=state.registry,
                        executed=state.executed,
                        tool_state=state.tool_state,
                        mode_config=state.mode_config,
                    ),
                    hooks,
                    state.query,
                    state.session_id,
                ):
                    yield event
        finally:
            if state.tool_runtime:
                await state.tool_runtime.close()
                state.tool_runtime = None

        ctx_session = ctx.session_id or state.session_id
        async for event in self._run_agent_orchestration(
            state.query,
            ctx_session,
        ):
            yield event
        self._orchestrated = True

    async def sequencer_stream(
        self,
        query: str,
        *,
        session_id: Optional[str],
        sequencer: PlannerSequencer,
        state: Optional[_SupervisorSequencerState] = None,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        if state is None:
            state = await self._prepare_sequencer_state(query, session_id=session_id)
        else:
            self._sequencer_state = state
        revision_targets: Set[str] = set()
        if state.revision_plan:
            revision_targets = set(getattr(state.revision_plan, "targets", []) or [])
        elif state.derived_targets:
            revision_targets = set(state.derived_targets)
        working_lane_states = dict(state.lane_states or self._initial_lane_states())
        state.lane_states = working_lane_states
        self._latest_lane_states = dict(working_lane_states)

        session_identifier = session_id or getattr(state.ctx, "session_id", None)
        if session_identifier:
            synthetic = EventEmitter.session_started(session_identifier)
            annotated_session = self._maybe_tag_session_metadata(
                self._annotate(synthetic),
                session_identifier,
            )
            yield annotated_session

        def _on_lane_transition(event: Dict[str, Any]) -> None:
            self._sync_lane_states_from_sequencer(working_lane_states, sequencer)
            self._latest_lane_states = dict(working_lane_states)

        sequencer.event_bus.subscribe(_on_lane_transition)
        self._planner_event_bus = sequencer.event_bus
        self._active_sequencer = sequencer
        sequencer.on_retry(self._handle_retry)
        sequencer.prefill_lane_states(working_lane_states)
        sequencer.set_revision_targets(revision_targets)
        self._sync_lane_states_from_sequencer(working_lane_states, sequencer)
        self._latest_lane_states = dict(working_lane_states)

        try:
            async for event in sequencer.run():
                annotated_event = self._maybe_tag_session_metadata(
                    self._annotate(event),
                    session_identifier,
                )
                yield annotated_event
                self._sync_lane_states_from_sequencer(working_lane_states, sequencer)
                self._latest_lane_states = dict(working_lane_states)
        except Exception:
            raise
        finally:
            sequencer.remove_retry_callback(self._handle_retry)
            sequencer.event_bus.unsubscribe(_on_lane_transition)
            if self._active_sequencer is sequencer:
                self._active_sequencer = None
            self._sequencer_state = None
            self._sync_lane_states_from_sequencer(working_lane_states, sequencer)
            self._latest_lane_states = dict(working_lane_states)

        state.lane_states = dict(working_lane_states)
        self._latest_lane_states = dict(working_lane_states)
        summary_event = self._emit_lane_summary(working_lane_states)
        if summary_event:
            yield self._maybe_tag_session_metadata(
                self._annotate(summary_event),
                session_identifier,
            )

    async def events(
        self,
        query: str,
        session_id: Optional[str] = None,
        *,
        sequencer: Optional[PlannerSequencer] = None,
        sequencer_state: Optional[_SupervisorSequencerState] = None,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        self._abort_stale_sequencer(reason="restart")
        if self._agentic_revision_mode:
            sequencer = None
            sequencer_state = None
        if sequencer is not None:
            async for event in self.sequencer_stream(
                query,
                session_id=session_id,
                sequencer=sequencer,
                state=sequencer_state,
            ):
                yield event
            return

        planner_events = getattr(self._planner, "events", None)
        hooks = _MultiAgentHooks(self, query, session_id=session_id)
        if callable(planner_events):
            try:
                async for event in planner_events(query, session_id=session_id, hooks=hooks):
                    yield event
                return
            except TypeError:
                planner_stream = planner_events(query, session_id=session_id)
                async for event in self._forward_with_hooks(
                    planner_stream,
                    hooks,
                    query,
                    session_id,
                    ensure_session_event=True,
                ):
                    yield event
                return

        planner_stream = run_planner_executor(query, session_id=session_id)
        async for event in self._forward_with_hooks(
            planner_stream,
            hooks,
            query,
            session_id,
            ensure_session_event=True,
        ):
            yield event

    async def chart_revision(
        self,
        query: str,
        *,
        session_id: Optional[str],
        patch: Dict[str, Any],
        reason: Optional[str] = None,
        source: Optional[str] = None,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        if session_id is None:
            raise ValueError("chart_revision requires an existing session_id")
        self._chart_revision_missing_session = False
        self.set_follow_up_route(FollowUpRoute.REUSE_SQL)
        hooks = _MultiAgentHooks(self, query, session_id=session_id)
        ctx = await self._planner.initialize_context(query, session_id=session_id)
        registry = get_planner_tool_registry()
        tool_stream = registry.invoke(
            "chart_revision",
            self._planner._pipeline,
            ctx,
            patch=patch,
            reason=reason,
            source=source,
        )
        async for event in self._forward_with_hooks(
            tool_stream,
            hooks,
            query,
            session_id,
            ensure_session_event=True,
        ):
            yield event

    async def apply_chart_revision(
        self,
        query: str,
        *,
        session_id: Optional[str],
        patch: Dict[str, Any],
        reason: Optional[str] = None,
        source: Optional[str] = None,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        async for event in self.chart_revision(
            query,
            session_id=session_id,
            patch=patch,
            reason=reason,
            source=source,
        ):
            yield event

    async def run_web_refresh(
        self,
        query: str,
        *,
        session_id: Optional[str],
        reason: Optional[str] = None,
        source: Optional[str] = None,
        revision_directive: Optional["RevisionDirective"] = None,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        if session_id is None:
            raise ValueError("run_web_refresh requires an existing session_id")
        hooks = _MultiAgentHooks(self, query, session_id=session_id)
        ctx = await self._planner.initialize_context(query, session_id=session_id)
        if revision_directive is not None:
            ctx.revision_directive = revision_directive
            ctx.agentic_revision_mode = bool(getattr(revision_directive, "agentic", False))
            ctx.revision_targets = set(getattr(revision_directive, "targets", []))
        directive_topics = getattr(getattr(ctx, "revision_directive", None), "search_topics", None)
        if directive_topics:
            ctx.revision_search_topics = list(directive_topics)
        _reset_revision_accessories(ctx, {"web"})

        async def _stream() -> AsyncGenerator[Dict[str, Any], None]:
            async for event in self._planner.invoke_tool(
                "web_refresh",
                ctx,
                reason=reason,
                source=source,
            ):
                yield event

        async for event in self._forward_with_hooks(
            _stream(),
            hooks,
            query,
            session_id,
            ensure_session_event=True,
        ):
            yield self._annotate(event)

    async def refresh_market_lane(
        self,
        query: str,
        *,
        session_id: Optional[str],
        reason: Optional[str] = None,
        source: Optional[str] = None,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        if session_id is None:
            raise ValueError("refresh_market_lane requires an existing session_id")
        hooks = _MultiAgentHooks(self, query, session_id=session_id)
        ctx = await self._planner.initialize_context(query, session_id=session_id)
        _reset_revision_accessories(ctx, {"market"})

        async def _stream() -> AsyncGenerator[Dict[str, Any], None]:
            async for event in self._planner.invoke_tool(
                "market_refresh",
                ctx,
                reason=reason,
                source=source,
            ):
                yield event

        async for event in self._forward_with_hooks(
            _stream(),
            hooks,
            query,
            session_id,
            ensure_session_event=True,
        ):
            yield self._annotate(event)

    async def run_analysis_refresh(
        self,
        query: str,
        *,
        session_id: Optional[str],
        requested_focus: Optional[str] = None,
        revision_directive: Optional["RevisionDirective"] = None,
        reason: Optional[str] = None,
        source: Optional[str] = None,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        if session_id is None:
            raise ValueError("run_analysis_refresh requires an existing session_id")
        hooks = _MultiAgentHooks(self, query, session_id=session_id)

        def _apply_revision_context(ctx_obj: Any) -> None:
            if revision_directive is not None:
                ctx_obj.revision_directive = revision_directive
                ctx_obj.agentic_revision_mode = bool(getattr(revision_directive, "agentic", False))
                ctx_obj.revision_targets = set(getattr(revision_directive, "targets", []))
            if requested_focus:
                setattr(ctx_obj, "revision_focus", requested_focus)
            directive_topics = getattr(getattr(ctx_obj, "revision_directive", None), "search_topics", None)
            if directive_topics:
                ctx_obj.revision_search_topics = list(directive_topics)

        ctx = await self._planner.initialize_context(query, session_id=session_id)
        _apply_revision_context(ctx)
        ctx.reused_analysis = False
        ctx.web_ready_emitted = False
        _reset_revision_accessories(ctx, {"web", "market"})
        sql_artifact = getattr(ctx.artifacts, "sql_generation", None)
        analysis_artifact = getattr(ctx.artifacts, "analysis", None)
        missing_sql = not sql_artifact or not getattr(sql_artifact, "sql", None)
        missing_analysis = analysis_artifact is None or not getattr(analysis_artifact, "analysis_text", None)
        if missing_sql or missing_analysis:
            logger.warning(
                "snapshot_missing",
                extra={
                    "lane": "analysis",
                    "session_id": session_id,
                    "reason": "missing_sql_snapshot" if missing_sql else "missing_analysis_snapshot",
                },
            )
            ctx.analysis_refresh_mode = "full"
            refresh_flags = dict(getattr(ctx, "lane_refresh_required", {}) or {})
            refresh_flags["analysis"] = True
            refresh_flags["web"] = True
            ctx.lane_refresh_required = refresh_flags

        web_ready_seen = False
        web_failure_reason: Optional[str] = None
        async for event in self.run_web_refresh(
            query,
            session_id=session_id,
            reason=reason,
            source="fresh_revision",
            revision_directive=revision_directive,
        ):
            name = str(event.get("event") or "")
            data = event.setdefault("data", {})
            data.setdefault("lane", "web")
            if data.get("source") != "fresh_revision":
                data["source"] = "fresh_revision"
            reused_flag = bool(data.get("reused"))
            data["from_cache"] = reused_flag
            if not reused_flag:
                data["reason"] = "fresh_revision"
            if name in {"web_ready", "web_revision_ready"}:
                web_ready_seen = True
                data.setdefault("reason", "fresh_revision")
                data["from_cache"] = reused_flag
            elif name == "error":
                web_failure_reason = data.get("error") or web_failure_reason or "web_refresh_error"
            elif name == "status":
                phase = str(data.get("phase") or "").lower()
                if phase == "skipped":
                    web_failure_reason = data.get("message") or web_failure_reason or "web_refresh_skipped"
            yield event

        if web_ready_seen:
            ready_event = EventEmitter.status(
                "web_revision_ready",
                "Web context refreshed for analysis revision",
            )
            ready_event.setdefault("data", {})
            ready_event["data"].update(
                {
                    "lane": "web",
                    "revision": True,
                    "source": "fresh_revision",
                    "from_cache": False,
                    "reason": "fresh_revision",
                }
            )
            if session_id:
                ready_event["data"]["session_id"] = session_id
            yield self._annotate(ready_event)

        if not web_ready_seen:
            warning_event = EventEmitter.status(
                "web_refresh",
                "Web research unavailable - analysis reused previous context",
            )
            warning_event.setdefault("data", {})
            warning_event["data"].update(
                {
                    "lane": "web",
                    "level": "warning",
                    "revision": True,
                    "source": "fresh_revision",
                    "reason": web_failure_reason or "web_refresh_unavailable",
                    "from_cache": True,
                    "banner": {
                        "title": "Web Research Unavailable",
                        "message": "Web research unavailable - analysis reused previous context.",
                        "route": "analysis_only",
                    },
                }
            )
            if session_id:
                warning_event["data"]["session_id"] = session_id
            yield self._annotate(warning_event)

        ctx = await self._planner.initialize_context(query, session_id=session_id)
        _apply_revision_context(ctx)
        ctx.reused_analysis = False
        ctx.web_ready_emitted = web_ready_seen
        _reset_revision_accessories(ctx, {"market"})
        refresh_flags = dict(getattr(ctx, "lane_refresh_required", {}) or {})
        refresh_flags.setdefault("analysis", True)
        refresh_flags["web"] = False
        refresh_flags["market"] = False
        ctx.lane_refresh_required = refresh_flags

        async for _ in self._planner._pipeline.run_analysis_phase(ctx):  # type: ignore[attr-defined]
            pass
        async for _ in self._planner._pipeline._emit_post_analysis_accessories(ctx):  # type: ignore[attr-defined]
            pass
        await self._planner._pipeline._persist_session_state(  # type: ignore[attr-defined]
            ctx,
            record_analysis=True,
            record_artifacts=True,
        )

        refreshed_analysis = getattr(ctx.artifacts, "analysis", None)
        refreshed_text = getattr(refreshed_analysis, "analysis_text", None)
        analysis_payload = refreshed_text or requested_focus or ""

        async for event in self._forward_with_hooks(
            self.analysis_revision(  # type: ignore[misc]
                query,
                session_id=session_id,
                analysis=analysis_payload,
                reason=reason,
                source=source or "fresh_revision",
                revision_directive=revision_directive,
            ),
            hooks,
            query,
            session_id,
        ):
            yield self._annotate(event)

    async def analysis_revision(
        self,
        query: str,
        *,
        session_id: Optional[str],
        analysis: Optional[str] = None,
        reason: Optional[str] = None,
        source: Optional[str] = None,
        revision_directive: Optional["RevisionDirective"] = None,
        refresh_web: bool = False,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        if session_id is None:
            raise ValueError("analysis_revision requires an existing session_id")
        hooks = _MultiAgentHooks(self, query, session_id=session_id)
        ctx = await self._planner.initialize_context(query, session_id=session_id)
        registry = get_planner_tool_registry()
        if revision_directive is not None:
            ctx.revision_directive = revision_directive
            ctx.agentic_revision_mode = bool(getattr(revision_directive, "agentic", False))
            ctx.revision_targets = set(getattr(revision_directive, "targets", []))
            focus_hint = (
                getattr(revision_directive, "requested_focus", None)
                or getattr(revision_directive, "raw_text", None)
            )
            if focus_hint:
                ctx.revision_focus = focus_hint
            if getattr(revision_directive, "search_topics", None):
                ctx.revision_search_topics = list(revision_directive.search_topics)
        if refresh_web:
            async for event in self.run_web_refresh(
                query,
                session_id=session_id,
                reason=reason,
                source=source or "fresh_revision",
                revision_directive=revision_directive,
            ):
                yield event
        tool_stream = registry.invoke(
            "analysis_revision",
            self._planner._pipeline,
            ctx,
            analysis=analysis or "",
            reason=reason,
            source=source,
        )
        async for event in self._forward_with_hooks(
            tool_stream,
            hooks,
            query,
            session_id,
            ensure_session_event=True,
        ):
            yield event

    def _prepare_context(self, query: str) -> None:
        preserved_market = self._shared_context.get('market', {})
        preserved_web = self._shared_context.get('web', {})
        self._shared_context = {
            'query': query,
            'planner': {'tickers': _infer_tickers(query)},
            'sql': {'attempts': []},
            'chart': {},
            'analysis': {'fragments': [], 'final': None},
            'market': preserved_market or {},
            'web': preserved_web or {},
            'tool_manifest': self._planner_tool_manifest,
            'tool_results': [],
            'stock_widget': None,
            'agents': {},
            'revision_completed_lanes': set(),
            '_runtime': {
                'market_fetcher': self._market_fetcher,
                'market_client': self._market_client,
            },
            '_meta': {
                'flow_label': getattr(self, 'flow_label', None),
                'prompt_versions': dict(self._prompt_versions),
            },
        }
        self._shared_context['lane_refresh_required'] = dict(self._lane_refresh_required)
        if self._revision_directive is not None:
            self._shared_context['revision_directive'] = self._revision_directive.to_dict()
            self._shared_context.setdefault('_meta', {}).setdefault(
                'revision_mode', 'agentic' if self._agentic_revision_mode else 'manual'
            )
        runtime_state = self._shared_context.setdefault('_runtime', {})
        runtime_state['accessories_ready'] = asyncio.Event()
        receipts_cache: Dict[str, Any] = {}
        if self._prefetched_snapshot and isinstance(self._prefetched_snapshot.tool_cache, dict):
            receipts_cache = copy.deepcopy(self._prefetched_snapshot.tool_cache.get("tool_receipts") or {})
        self._shared_context["tool_receipts"] = receipts_cache
        revision_snapshot = extract_revision_snapshot(self._prefetched_snapshot)
        if isinstance(revision_snapshot, dict):
            self._shared_context['revision_snapshot'] = copy.deepcopy(revision_snapshot)
            sql_ctx = self._shared_context.setdefault('sql', {'attempts': []})
            if revision_snapshot.get('sql'):
                sql_ctx['sql'] = revision_snapshot['sql']
                sql_ctx['status'] = 'reused'
            if revision_snapshot.get('sql_row_count') is not None:
                sql_ctx['row_count'] = revision_snapshot['sql_row_count']
            if revision_snapshot.get('columns'):
                sql_ctx['columns'] = list(revision_snapshot.get('columns') or [])
            if revision_snapshot.get('data_sample'):
                sql_ctx['sample_data'] = copy.deepcopy(revision_snapshot['data_sample'])
            chart_ctx = self._shared_context.setdefault('chart', {})
            if revision_snapshot.get('chart_spec'):
                chart_ctx['spec'] = copy.deepcopy(revision_snapshot['chart_spec'])
                chart_ctx['spec_id'] = revision_snapshot.get('chart_spec_id')
                chart_ctx['status'] = 'reused'
            analysis_ctx = self._shared_context.setdefault('analysis', {'fragments': [], 'final': None})
            if revision_snapshot.get('analysis'):
                analysis_ctx['final'] = revision_snapshot['analysis']
                length_value = revision_snapshot.get('analysis_length')
                if length_value is None and isinstance(revision_snapshot.get('analysis'), str):
                    length_value = len(revision_snapshot['analysis'])
                if length_value is not None:
                    try:
                        length_int = int(length_value)
                    except (TypeError, ValueError):
                        length_int = None
                    else:
                        analysis_ctx['length'] = length_int
                        analysis_ctx['analysis_length'] = length_int
                else:
                    analysis_ctx['analysis_length'] = length_value
            if revision_snapshot.get('stock_widget'):
                stock_widget_copy = copy.deepcopy(revision_snapshot['stock_widget'])
                self._shared_context['stock_widget'] = stock_widget_copy
                market_ctx = self._shared_context.setdefault('market', {})
                market_ctx['snapshot'] = copy.deepcopy(stock_widget_copy)
                original_symbols = stock_widget_copy.get('original')
                if isinstance(original_symbols, list) and original_symbols:
                    market_ctx['tickers'] = list(original_symbols)
                market_ctx.setdefault('source', 'revision_snapshot')
            web_payload = revision_snapshot.get('web_context') or {}
            if isinstance(web_payload, dict) and web_payload:
                web_ctx = self._shared_context.setdefault('web', {})
                web_ctx.update(copy.deepcopy(web_payload))
                web_ctx.setdefault('ready', True)
                web_ctx.setdefault('source', 'revision_snapshot')
            tool_results = self._shared_context.setdefault('tool_results', [])
            if revision_snapshot.get('stock_widget') and not any(res.get('tool') == 'stock_tracker' for res in tool_results):
                tool_results.append(
                    {
                        'tool': 'stock_tracker',
                        'status': 'completed',
                        'payload': {'ready': True, 'widget': copy.deepcopy(revision_snapshot['stock_widget'])},
                        'metadata': {'name': 'stock_tracker'},
                        'elapsed_ms': 0,
                    }
                )
            if isinstance(web_payload, dict) and web_payload and not any(res.get('tool', '').startswith('web_retriever') for res in tool_results):
                tool_results.append(
                    {
                        'tool': 'web_retriever',
                        'status': 'completed',
                        'payload': copy.deepcopy(web_payload),
                        'metadata': {'name': 'web_retriever'},
                        'elapsed_ms': 0,
                    }
                )
            meta = self._shared_context.setdefault('_meta', {})
            meta['prior_intent_signature'] = revision_snapshot.get('intent_signature')
        else:
            self._shared_context.pop('revision_snapshot', None)
        self._orchestrated = False

    async def _prepare_sequencer_state(
        self,
        query: str,
        *,
        session_id: Optional[str],
    ) -> _SupervisorSequencerState:
        self._prepare_context(query)
        ctx = await self._planner.initialize_context(query, session_id=session_id)
        registry: PlannerToolRegistry = get_planner_tool_registry()
        executed: Set[str] = set()
        mode_config = get_mode_config(self.flow_mode)
        hooks = _MultiAgentHooks(self, query, session_id=ctx.session_id or session_id)
        classification_artifact = getattr(ctx.artifacts, "classification", None)
        cached_classification: Optional[Mapping[str, Any]] = getattr(ctx, "classification", None)
        if classification_artifact is not None:
            is_financial = getattr(classification_artifact, "is_financial", None)
            if is_financial is not None:
                ctx.is_financial_query = bool(is_financial)
            if cached_classification is None:
                raw_payload = getattr(classification_artifact, "raw", None)
                if isinstance(raw_payload, Mapping):
                    cached_classification = dict(raw_payload)
                    ctx.classification = cached_classification
        elif getattr(ctx, "is_financial_query", None) is None:
            ctx.is_financial_query = True
        session_follow_up = bool(getattr(ctx, "session_follow_up", False) or self._session_follow_up)
        state = _SupervisorSequencerState(
            ctx=ctx,
            registry=registry,
            executed=executed,
            mode_config=mode_config,
            query=query,
            session_id=ctx.session_id or session_id,
            hooks=hooks,
        )
        if state.lane_states is None:
            state.lane_states = dict(self._initial_lane_states())
        revision_directive_active = bool(self._revision_directive or getattr(ctx, "revision_directive", None))
        has_revision_targets = bool(getattr(ctx, "revision_targets", None))
        agentic_revision_mode = bool(getattr(ctx, "agentic_revision_mode", False) or self._agentic_revision_mode)
        is_revision_follow_up = (
            session_follow_up
            or ctx.follow_up_route != FollowUpRoute.FULL_PIPELINE
            or revision_directive_active
            or has_revision_targets
            or agentic_revision_mode
        )
        state.is_revision_follow_up = is_revision_follow_up
        setattr(ctx, "is_revision_follow_up", is_revision_follow_up)
        if is_revision_follow_up:
            confidence = 0.0
            if isinstance(cached_classification, Mapping):
                confidence_value = cached_classification.get("confidence")
                try:
                    confidence = float(confidence_value or 0.0)
                except (TypeError, ValueError):
                    confidence = 0.0
            cached_intent_ready = bool(getattr(ctx, "intent", None))
            cached_plan_ready = bool(getattr(ctx, "plan", None) or getattr(ctx, "provisional_plan", None))
            pending_followups = 0
            intent_resolution = getattr(ctx, "intent_resolution", None)
            if intent_resolution is not None:
                followups = getattr(intent_resolution, "followups", None) or []
                try:
                    pending_followups = len(followups)
                except TypeError:
                    pending_followups = 0
            cached_revision_ready = cached_intent_ready and cached_plan_ready and pending_followups == 0
            hydrated_intent_ready = bool(getattr(ctx, "intent", None))
            hydrated_plan_ready = bool(getattr(ctx, "plan", None) or getattr(ctx, "provisional_plan", None))
            no_pending_followups = pending_followups == 0
            if not hydrated_intent_ready and cached_intent_ready:
                hydrated_intent_ready = True
            if not hydrated_plan_ready and cached_plan_ready:
                hydrated_plan_ready = True
            skip_reason = "session_follow_up" if session_follow_up else "revision_follow_up"
            if cached_classification is not None and confidence >= REVISION_INTENT_CONFIDENCE_THRESHOLD:
                skip_reason = "cached_intent"
            elif cached_revision_ready:
                skip_reason = "revision_context"
            skip_classification = True
            reuse_intent = hydrated_intent_ready and hydrated_plan_ready and no_pending_followups
            if skip_classification:
                executed.add("classification")
                if classification_artifact is None and getattr(ctx, "is_financial_query", None) is None:
                    ctx.is_financial_query = True
                log_tool_iteration(
                    tool="intent_classifier",
                    status="skipped",
                    step="classification",
                    session_id=ctx.session_id,
                    flow=self.flow_label,
                    details={
                        "reason": skip_reason,
                        "confidence": confidence,
                        "pending_followups": pending_followups,
                    },
                )
            lane_states = state.lane_states or {}
            lane_states["intent"] = "reused" if reuse_intent else "pending"
            state.lane_states = lane_states
            if reuse_intent:
                executed.update({"intent_detection", "clarification", "plan_generation"})
                if skip_reason == "cached_intent":
                    intent_skip_reason = "cached_intent"
                elif cached_revision_ready:
                    intent_skip_reason = "revision_context"
                else:
                    intent_skip_reason = "session_follow_up" if session_follow_up else "revision_follow_up"
                log_tool_iteration(
                    tool="intent_classifier",
                    status="skipped",
                    step="intent_detection",
                    session_id=ctx.session_id,
                    flow=self.flow_label,
                    details={
                        "reason": intent_skip_reason,
                        "confidence": confidence,
                    },
                )
                log_tool_iteration(
                    tool="clarification_manager",
                    status="skipped",
                    step="clarification",
                    session_id=ctx.session_id,
                    flow=self.flow_label,
                    details={"reason": intent_skip_reason},
                )
                log_tool_iteration(
                    tool="planner",
                    status="skipped",
                    step="plan_generation",
                    session_id=ctx.session_id,
                    flow=self.flow_label,
                    details={"reason": intent_skip_reason},
                )
                self._emit_lane_transition(
                    "intent",
                    status=LANE_STATUS_COMPLETED,
                    success=True,
                    reused=True,
                    reason=intent_skip_reason,
                )
            ctx.intent_reused = reuse_intent
            planner_snapshot = self._shared_context.setdefault("planner", {})
            planner_snapshot["intent_reused"] = bool(reuse_intent)

            await self._planner._persist_session_state(ctx, record_artifacts=True)
        self._sequencer_state = state
        return state

    def _capture_event(self, event: Dict[str, Any]) -> None:
        name = event.get("event")
        data = event.get("data") or {}
        if name == "criteria_ready":
            self._mark_accessories_ready()
        elif name == "clarification_skipped":
            self._mark_accessories_ready()
        elif name == "clarification_resolved":
            self._mark_accessories_ready()
        if name == "session_started":
            session_identifier = data.get("session_id")
            if session_identifier:
                if (
                    self._session_snapshot is not None
                    and self._session_snapshot.session_id == session_identifier
                ):
                    pass
                elif (
                    self._prefetched_snapshot is not None
                    and self._prefetched_snapshot.session_id == session_identifier
                ):
                    self._session_snapshot = self._prefetched_snapshot
                else:
                    self._session_snapshot = SessionStateSnapshot(session_id=session_identifier)
            return

        if isinstance(data, Mapping) and data.get("revision"):
            lane_name = data.get("lane")
            if lane_name:
                completed = self._shared_context.setdefault("revision_completed_lanes", set())
                if isinstance(completed, set):
                    completed.add(str(lane_name))
                else:
                    updated = set(completed) if isinstance(completed, Iterable) else set()
                    updated.add(str(lane_name))
                    self._shared_context["revision_completed_lanes"] = updated

        planner_ctx = self._shared_context.setdefault("planner", {})
        sql_ctx = self._shared_context.setdefault("sql", {})
        analysis_ctx = self._shared_context.setdefault("analysis", {"fragments": [], "final": None})
        chart_ctx = self._shared_context.setdefault("chart", {})

        if name == "intent_detection_complete":
            planner_ctx["intent_key"] = data.get("intent_key")
            planner_ctx["confidence"] = data.get("confidence")
            if self._session_snapshot:
                self._session_snapshot.record_query(
                    self._shared_context.get("query", ""),
                    planner_ctx.get("intent_key"),
                )
            slots = data.get("slots_detected") or {}
            planner_ctx["slots"] = {k: v for k, v in slots.items() if k in {"company", "metric", "ticker"}}
            slot_status_payload = data.get("slot_statuses") or {}
            if isinstance(slot_status_payload, Mapping):
                planner_ctx["slot_statuses"] = slot_status_payload
            slot_followups_payload = data.get("slot_followups") or []
            if isinstance(slot_followups_payload, Sequence):
                planner_ctx["slot_followups"] = list(slot_followups_payload)
            companies = slots.get("company")
            if isinstance(companies, str):
                companies = [companies]
            if isinstance(companies, list):
                planner_ctx["tickers"] = sorted(set(planner_ctx.get("tickers", [])).union({str(item) for item in companies}))[:5]
        elif name == "planner_result":
            planner_ctx["result"] = data

        elif name == "sql_generated":
            sql_text = data.get("sql") or ""
            sql_ctx["llm_used"] = data.get("llm_used")
            sql_ctx["template_fallback"] = data.get("template_fallback")
            sql_ctx["generated"] = True
            if sql_text:
                sql_ctx["sql"] = sql_text
                sql_ctx["id"] = _make_identifier(self._session_id, "sql", sql_text)
                self._record_snapshot(sql=sql_text)
        elif name == "sql_validated":
            sql_ctx["validated"] = data.get("ok", False)
            sql_ctx["issues"] = data.get("issues_count", 0)
        elif name == "sql_attempts":
            attempts = sanitize_for_json(data.get("attempts") or [])
            sql_ctx["attempts"] = attempts
            if attempts:
                sql_ctx["status"] = attempts[-1].get("status")
        elif name == "execution_stats":
            sql_ctx["row_count"] = data.get("row_count")
            sql_ctx["status"] = 'success'
        elif name == "data_retrieved":
            sample = data.get("sample_data")
            if isinstance(sample, Sequence) and not isinstance(sample, (str, bytes)):
                sql_ctx["sample_data"] = list(sample)
            columns = data.get("columns")
            if isinstance(columns, Sequence) and not isinstance(columns, (str, bytes)):
                sql_ctx["columns"] = list(columns)
        elif name == "chart_generated":
            raw_spec = data.get("chart_spec")
            normalized_spec = _normalize_chart_spec_payload(raw_spec) if raw_spec is not None else None
            if normalized_spec is None and isinstance(raw_spec, dict):
                normalized_spec = raw_spec
            chart_type = data.get("chart_type")
            if isinstance(raw_spec, dict) and not chart_type:
                chart_type = raw_spec.get("chart_type")
            if normalized_spec is not None:
                sanitized_spec = sanitize_for_json(normalized_spec)
                identifier_source = json.dumps(sanitized_spec, sort_keys=True, default=str)
                identifier = _make_identifier(self._session_id, "chart", identifier_source)
                chart_ctx["spec_id"] = identifier
                chart_ctx["spec"] = sanitized_spec
                chart_ctx["status"] = "fresh"
                series_count: Optional[int] = None
                if isinstance(sanitized_spec, dict):
                    if isinstance(sanitized_spec.get("series"), list):
                        series_count = len(sanitized_spec["series"])
                    elif isinstance(sanitized_spec.get("datasets"), list):
                        series_count = len(sanitized_spec["datasets"])
                    elif isinstance(sanitized_spec.get("dataset"), list):
                        series_count = len(sanitized_spec["dataset"])
                inferred_type = None
                if isinstance(sanitized_spec, dict):
                    inferred_type = sanitized_spec.get("chart_type")
                    if not inferred_type:
                        meta = sanitized_spec.get("meta")
                        if isinstance(meta, dict):
                            chart_design = meta.get("chartDesign") or meta.get("chart_design")
                            if isinstance(chart_design, dict):
                                inferred_type = chart_design.get("chart_type")
                chart_ctx["spec_summary"] = {
                    "chart_type": chart_type or inferred_type,
                    "series_count": series_count,
                }
                data["chart_spec"] = sanitized_spec
                data["chart_spec_id"] = identifier
                self._record_snapshot(chart_spec=sanitized_spec)
            else:
                chart_ctx["spec_summary"] = {"chart_type": chart_type}
                chart_ctx.setdefault("status", "fresh")
        elif name == "analysis_streaming":
            fragment = data.get("partial_analysis")
            if fragment:
                fragments: List[str] = analysis_ctx.setdefault("fragments", [])
                if len(fragments) < _MAX_FRAGMENT_COUNT:
                    fragments.append(fragment[:200])
        elif name == "analysis_complete":
            raw_analysis = data.get("analysis")
            final_text: str = ""
            if isinstance(raw_analysis, str):
                final_text = raw_analysis
            elif isinstance(raw_analysis, Mapping):
                # Gemini responses may embed the prose under nested keys; inspect common fields before fallback.
                for candidate in ("analysis", "text", "content", "message", "markdown"):
                    candidate_value = raw_analysis.get(candidate)
                    if isinstance(candidate_value, str) and candidate_value.strip():
                        final_text = candidate_value
                        break
                if not final_text:
                    final_text = json.dumps(raw_analysis, ensure_ascii=False)
            elif raw_analysis is not None:
                final_text = str(raw_analysis)
            if final_text:
                truncated = final_text[:_MAX_ANALYSIS_STORED]
                analysis_ctx["final"] = truncated
                analysis_ctx["id"] = _make_identifier(self._session_id, "analysis", final_text)
                length_value = data.get("analysis_length", len(final_text))
                try:
                    length_int = int(length_value)
                except (TypeError, ValueError):
                    length_int = len(final_text)
                analysis_ctx["length"] = length_int
                analysis_ctx["analysis_length"] = length_int
                self._record_snapshot(analysis=final_text)
            tool_bundle = collect_tool_bundle(
                manifest=self._shared_context.get("tool_manifest"),
                results=self._shared_context.get("tool_results"),
                stock_widget=data.get("stock_widget"),
                web_context=data.get("web_context"),
            )
            if tool_bundle.get("stock_widget"):
                self._shared_context["stock_widget"] = tool_bundle["stock_widget"]
                sources = tool_bundle.get("sources") or {}
                if sources.get("stock_tracker") == "cached":
                    market_ctx = self._shared_context.setdefault("market", {})
                    market_ctx['source'] = 'cached'
            if tool_bundle.get("web_context"):
                web_ctx = self._shared_context.setdefault("web", {})
                web_ctx.update(tool_bundle["web_context"])
                sources = tool_bundle.get("sources") or {}
                if sources.get("web_retriever") == "cached":
                    web_ctx['source'] = 'cached'
            if tool_bundle and self._session_snapshot:
                self._session_snapshot.record_tool_result("visual_bundle", tool_bundle)
            self._maybe_queue_analysis_ready()

        elif name == "web_search":
            payload = data.get("web_context") or {}
            if payload:
                web_ctx = self._shared_context.setdefault('web', {})
                web_ctx.update(payload)
                if self._session_snapshot:
                    try:
                        self._session_snapshot.record_tool_result('web_search', payload)
                    except Exception:
                        pass
            return

        elif name == "tool_parallel_start":
            manifest = data.get("tools") or data.get("tool_manifest")
            if manifest:
                self._shared_context["tool_manifest"] = sanitize_for_json(manifest)
                self._shared_context["tool_results"] = []

        elif name == "tool_parallel_result":
            results_list = self._shared_context.setdefault("tool_results", [])
            sanitized_result = sanitize_for_json(data)
            canonical_tool = _canonical_tool_name(sanitized_result.get("tool"))
            if canonical_tool:
                sanitized_result["tool"] = canonical_tool
            tool_key = sanitized_result.get("tool") or canonical_tool
            artifact_meta = self._shared_context.setdefault("_artifact_meta", {})
            tool_hashes: Dict[str, str] = artifact_meta.setdefault("tool_result_hashes", {})
            fingerprint = _hash_payload(
                {
                    "tool": tool_key,
                    "status": sanitized_result.get("status"),
                    "reused": sanitized_result.get("reused"),
                    "payload": sanitized_result.get("payload"),
                    "metadata": sanitized_result.get("metadata"),
                }
            )
            if tool_key and tool_hashes.get(tool_key) == fingerprint:
                return
            if tool_key:
                tool_hashes[tool_key] = fingerprint
            results_list.append(sanitized_result)
            deduped: List[Dict[str, Any]] = []
            seen_tools: set[str] = set()
            for entry in reversed(results_list):
                tool_alias = entry.get("tool")
                if tool_alias in seen_tools:
                    continue
                seen_tools.add(tool_alias)
                deduped.append(entry)
            deduped.reverse()
            if len(deduped) > 10:
                deduped = deduped[-10:]
            results_list[:] = deduped

            tool_name = (canonical_tool or "").strip()
            receipts_map = self._shared_context.setdefault("tool_receipts", {})
            receipt_key = tool_name or sanitized_result.get("tool")
            if receipt_key:
                receipt_payload = {
                    "status": sanitized_result.get("status"),
                    "reused": bool(sanitized_result.get("reused")),
                    "elapsed_ms": sanitized_result.get("elapsed_ms"),
                    "timestamp": sanitized_result.get("completed_at")
                    or sanitized_result.get("ts")
                    or datetime.utcnow().isoformat(),
                }
                receipts_map[receipt_key] = receipt_payload
            if tool_name.startswith("web_retriever"):
                web_ctx = self._shared_context.setdefault('web', {})
                payload = sanitized_result.get("payload") or {}
                metadata = sanitized_result.get("metadata") or {}
                if payload:
                    web_ctx.update(payload)
                    web_ctx['ready'] = payload.get('ready', False)
                    web_ctx.setdefault('query', payload.get('query_terms'))
                    if payload.get('from_cache'):
                        web_ctx['source'] = 'cached'
                    else:
                        web_ctx.setdefault('source', 'planner_fanout')
                elif metadata.get('summary'):
                    web_ctx.setdefault('summary', metadata.get('summary'))
                if metadata.get('cache_hit') is not None:
                    if metadata.get('cache_hit'):
                        web_ctx['source'] = 'cached'
                    web_ctx['cache_hit'] = metadata.get('cache_hit')
                if sanitized_result.get("reused"):
                    web_ctx['source'] = 'cached'
                if metadata.get('summary') and not web_ctx.get('summary'):
                    web_ctx['summary'] = metadata.get('summary')
            elif tool_name == "stock_tracker":
                payload = sanitized_result.get("payload") or {}
                if isinstance(payload, dict) and (payload.get('ready') or payload.get('stock_widget')):
                    widget = collect_tool_bundle(results=[sanitized_result]).get('stock_widget')
                    if widget:
                        self._shared_context['stock_widget'] = widget
                        market_ctx = self._shared_context.setdefault('market', {})
                        market_ctx['snapshot'] = copy.deepcopy(widget)
                        if isinstance(payload.get('tickers'), list) and payload.get('tickers'):
                            market_ctx['tickers'] = list(payload['tickers'])
                        elif isinstance(widget.get('original'), list) and widget.get('original'):
                            market_ctx.setdefault('tickers', list(widget['original']))
                        if sanitized_result.get("reused"):
                            market_ctx['source'] = 'cached'
                        else:
                            market_ctx.setdefault('source', 'planner_fanout')
            bundle_update = collect_tool_bundle(
                manifest=self._shared_context.get('tool_manifest'),
                results=self._shared_context.get('tool_results'),
            )
            if bundle_update.get('stock_widget'):
                widget = bundle_update['stock_widget']
                self._shared_context['stock_widget'] = widget
                market_ctx = self._shared_context.setdefault('market', {})
                market_ctx['snapshot'] = copy.deepcopy(widget)
                if isinstance(widget.get('original'), list) and widget.get('original'):
                    market_ctx.setdefault('tickers', list(widget['original']))
                sources_meta = bundle_update.get('sources') or {}
                if sources_meta.get('stock_tracker') == 'cached':
                    market_ctx['source'] = 'cached'
                else:
                    market_ctx.setdefault('source', market_ctx.get('source') or 'planner_fanout')
            if bundle_update.get('web_context'):
                web_ctx = self._shared_context.setdefault('web', {})
                web_ctx.update(bundle_update['web_context'])
                if bundle_update['web_context'].get('from_cache'):
                    web_ctx['source'] = 'cached'
                else:
                    web_ctx.setdefault('source', web_ctx.get('source') or 'planner_fanout')
            self._maybe_queue_stock_ready()
            self._maybe_queue_web_ready()
        self._maybe_queue_sql_ready()
        self._maybe_queue_chart_ready()
        self._maybe_queue_stock_ready()
        self._maybe_queue_web_ready()

    async def _run_agent_orchestration(
        self,
        query: str,
        session_id: Optional[str],
    ) -> AsyncGenerator[Dict[str, Any], None]:
        sql_ctx = self._shared_context.get("sql", {})
        chart_ctx = self._shared_context.get("chart", {})
        analysis_ctx = self._shared_context.get("analysis", {})
        stock_widget = self._shared_context.get("stock_widget")
        web_context = self._shared_context.get("web")
        tool_manifest = self._shared_context.get("tool_manifest")
        tool_results = self._shared_context.get("tool_results")
        self._agent_retry_counts = {lane: 0 for lane in self.ROLE_LANES.values()}
        supervisor_run_id = f"{self.flow_label}-run-{uuid.uuid4().hex}"
        supervisor_trace_id = f"{self.flow_label}-trace-{uuid.uuid4().hex}"
        supervisor_meta = self._shared_context.setdefault("_meta", {}).setdefault("supervisor", {})
        supervisor_meta["run_id"] = supervisor_run_id
        supervisor_meta["trace_id"] = supervisor_trace_id
        supervisor_meta["delegation_policy_version"] = self._delegation_policy.version
        tool_attempts: Dict[str, int] = {}
        retry_counts: Dict[str, int] = {}
        failure_markers: Dict[str, str] = {}
        self._retry_manager.reset()

        for task in self._base_plan:
            role = self.ORCHESTRATION_ROLES.get(task.name)
            if role:
                yield self._format_agent_turn(role, "start")

        context = OrchestratorContext(
            query=query,
            session_id=session_id,
            shared=self._shared_context,
        )
        task_groups = {
            task_name: self.ROLE_PARALLEL_GROUPS.get(role)
            for task_name, role in self.ORCHESTRATION_ROLES.items()
            if self.ROLE_PARALLEL_GROUPS.get(role)
        }
        backpressure_queue: asyncio.Queue[Dict[str, Any]] = asyncio.Queue()

        def _handle_backpressure(task_name: str, payload: Mapping[str, Any]) -> None:
            event = self._format_backpressure_event(task_name, payload)
            if event:
                backpressure_queue.put_nowait(event)

        run_task = asyncio.create_task(
            self._orchestrator.run(
                self._base_plan,
                context,
                task_groups=task_groups,
                group_limits=self.SUPERVISOR_PARALLEL_LIMITS,
                on_backpressure=_handle_backpressure,
            )
        )

        pending_get: Optional[asyncio.Task] = None
        try:
            while True:
                wait_set = {run_task}
                if pending_get is None:
                    pending_get = asyncio.create_task(backpressure_queue.get())
                wait_set.add(pending_get)
                done, _ = await asyncio.wait(wait_set, return_when=asyncio.FIRST_COMPLETED)
                if pending_get in done:
                    event = pending_get.result()
                    yield event
                    backpressure_queue.task_done()
                    pending_get = None
                if run_task in done:
                    break
        finally:
            if pending_get and not pending_get.done():
                pending_get.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await pending_get
        while True:
            try:
                pending_event = backpressure_queue.get_nowait()
            except asyncio.QueueEmpty:
                break
            else:
                yield pending_event
                backpressure_queue.task_done()

        results = run_task.result()

        decision_payloads = list(self._retry_manager.decisions())
        for decision in decision_payloads:
            payload = dict(decision)
            payload.setdefault("ts", datetime.utcnow().isoformat())
            self._queue_supervisor_event("delegation_decision", payload)
            metadata = payload.get("metadata") if isinstance(payload.get("metadata"), Mapping) else None
            policy_decision(
                policy=f"delegation:{self._delegation_policy.version}",
                score=float(metadata.get("attempt", 0)) if metadata else 0.0,
                threshold=float(metadata.get("window", {}).get("limit", 0) if metadata else 0),
                action=str(payload.get("decision") or "allow"),
                reason=payload.get("reason"),
                session_id=session_id,
                flow=self.flow_label,
                metadata=metadata,
            )

        planner_result = results.get("planner_phase")
        bundle = planner_result.output.get("bundle") if planner_result else None
        analysis_text = analysis_ctx.get("final")

        def _final_answer_event(analysis_text_value: Optional[str]) -> Optional[Dict[str, Any]]:
            fallback = self._build_final_answer_payload(analysis_text_value)
            if not fallback:
                return None
            payload = {
                "message": fallback["message"],
                "missing_components": fallback["missing_components"],
                "analysis_available": fallback["analysis_available"],
                "final_answer_only": True,
                "mode": getattr(self, "flow_mode", FlowMode.MULTI_AGENT).value,
                "flow_mode": getattr(self, "flow_mode", FlowMode.MULTI_AGENT).value,
                "ts": datetime.utcnow().isoformat(),
            }
            return self._annotate({"event": "final_answer", "data": payload})

        for task in self._base_plan:
            role = self.ORCHESTRATION_ROLES.get(task.name)
            result = results.get(task.name)
            if not role or not result:
                continue
            lane = self.ROLE_LANES.get(role)
            lane_key = lane or role
            reasoning = self._format_reasoning(role, result)
            if reasoning:
                yield reasoning
            output_payload = result.output or {}
            status_value_normalized: Optional[str] = None
            error_detail: Optional[str] = None
            reused_lane = False
            transition_status = LANE_STATUS_COMPLETED
            success_value: Optional[bool] = True if lane else None
            if isinstance(output_payload, Mapping):
                attempt_count = output_payload.get("attempts")
                if isinstance(attempt_count, int) and lane_key:
                    tool_attempts[lane_key] = attempt_count
                status_value = output_payload.get("status")
                if isinstance(status_value, str):
                    status_value_normalized = status_value.lower()
                    if lane_key and status_value_normalized in {"failed", "error"}:
                        failure_markers[lane_key] = status_value_normalized
                    if status_value_normalized in {"reuse", "reused"}:
                        reused_lane = True
                    elif status_value_normalized in {"skip", "skipped"}:
                        transition_status = LANE_STATUS_SKIPPED
                        success_value = True
                error_detail = output_payload.get("error") or output_payload.get("error_code")
            retry_trace = output_payload.get("retry_trace") if isinstance(output_payload, Mapping) else None
            if retry_trace:
                yield self._agent_retry_event(role, retry_trace)
                if lane_key:
                    retry_counts[lane_key] = len(retry_trace)
            if result.events:
                extra_context: Dict[str, Any] = {"flow_mode": getattr(self, "flow_mode", FlowMode.MULTI_AGENT).value}
                if lane:
                    extra_context["lane"] = lane
                parallel_group = self.ROLE_PARALLEL_GROUPS.get(role)
                if parallel_group:
                    extra_context["parallel_group"] = parallel_group
                for agent_event in result.to_events(
                    role=role,
                    run_id=supervisor_run_id,
                    retry_count=self._agent_retry_counts.get(lane, 0) if lane else None,
                    extra=extra_context,
                ):
                    yield self._annotate(agent_event)
            if lane:
                if lane_key and lane_key in failure_markers:
                    transition_status = LANE_STATUS_FAILED
                    success_value = False
                    error_detail = error_detail or failure_markers[lane_key]
                elif transition_status != LANE_STATUS_SKIPPED and status_value_normalized in {"failed", "error"}:
                    transition_status = LANE_STATUS_FAILED
                    success_value = False
                self._emit_lane_transition(
                    lane,
                    status=transition_status,
                    success=success_value,
                    reused=reused_lane if transition_status != LANE_STATUS_FAILED else None,
                    error=error_detail,
                )
            yield self._format_agent_turn(
                role,
                "complete",
                summary=self._result_summary(result),
                elapsed=result.elapsed_ms,
            )
            agent_output = result.output or {}
            agent_handoff(
                role=role,
                status=str(agent_output.get('status') or 'unknown'),
                elapsed_ms=result.elapsed_ms,
                handoff=','.join(task.depends_on) if getattr(task, 'depends_on', None) else None,
                retries=len(agent_output.get('attempts') or []),
                session_id=session_id,
                flow=getattr(self, 'flow_label', None),
                metadata={
                    'summary': agent_output.get('summary'),
                    'tickers': agent_output.get('tickers'),
                    'parallel_group': self.ROLE_PARALLEL_GROUPS.get(role),
                },
            )

        for lane_name, count in self._agent_retry_counts.items():
            if count and lane_name not in retry_counts:
                retry_counts[lane_name] = count

        parallel_groups: Dict[str, List[str]] = {}
        for task_name in results.keys():
            role = self.ORCHESTRATION_ROLES.get(task_name)
            lane = self.ROLE_LANES.get(role or "")
            group = self.ROLE_PARALLEL_GROUPS.get(role or "")
            if not lane or not group:
                continue
            attempt_index = retry_counts.get(lane, 0)
            identifier = f"{lane}_lane_{attempt_index}"
            bucket = parallel_groups.setdefault(group, [])
            if identifier not in bucket:
                bucket.append(identifier)

        receipts_map: Dict[str, Any] = {}
        if isinstance(tool_results, list):
            for entry in tool_results:
                if isinstance(entry, Mapping):
                    tool_name = entry.get("tool")
                    if isinstance(tool_name, str):
                        receipts_map[tool_name] = entry

        repository = get_session_state_repository()
        if repository and session_id:
            snapshot = await repository.load(session_id)
            if snapshot is None:
                snapshot = SessionStateSnapshot(session_id=session_id)
            snapshot.record_agent_run(
                run_id=supervisor_run_id,
                trace_id=supervisor_trace_id,
                manager_trace_id=supervisor_trace_id,
                model=getattr(self._supervisor_agent, "model", None),
                tool_attempts=tool_attempts,
                retry_counts=retry_counts,
                receipts=receipts_map,
                parallel_groups=parallel_groups,
                delegation_policy_version=self._delegation_policy.version,
                decisions=decision_payloads,
            )
            await repository.save(snapshot)

        log_agent_run(
            session_id=session_id,
            flow=self.flow_label,
            run_id=supervisor_run_id,
            trace_id=supervisor_trace_id,
            manager_trace_id=supervisor_trace_id,
            model=getattr(self._supervisor_agent, "model", None),
            tool_attempts=tool_attempts,
            retry_counts=retry_counts,
            parallel_groups=parallel_groups,
            delegation_policy_version=self._delegation_policy.version,
            decisions=decision_payloads,
        )
        try:
            cache_service = get_cache_service()
            if cache_service and session_id:
                await cache_service.set_agent_metadata(
                    session_id,
                    {
                        "run_id": supervisor_run_id,
                        "trace_id": supervisor_trace_id,
                        "manager_trace_id": supervisor_trace_id,
                        "model": getattr(self._supervisor_agent, "model", None),
                        "tool_attempts": tool_attempts,
                        "retry_counts": retry_counts,
                        "failures": failure_markers,
                        "parallel_groups": parallel_groups,
                        "delegation_policy_version": self._delegation_policy.version,
                        "delegation_decisions": decision_payloads,
                        "recorded_at": datetime.utcnow().isoformat(),
                    },
                    ttl=self._agent_cache_ttl,
                )
        except Exception:  # pragma: no cover - defensive logging
            logger.exception("Failed to cache supervisor run metadata for session %s", session_id)

        analysis_length_value = analysis_ctx.get("length")
        if analysis_length_value is None:
            analysis_length_value = analysis_ctx.get("analysis_length")
        final_payload = {
            "analysis": analysis_ctx.get("final"),
            "analysis_length": analysis_length_value,
            "chart_spec": chart_ctx.get("spec"),
            "chart_spec_id": chart_ctx.get("spec_id"),
            "sql": sql_ctx.get("sql"),
            "sql_row_count": sql_ctx.get("row_count"),
            "data_sample": sql_ctx.get("sample_data"),
            "columns": sql_ctx.get("columns"),
            "stock_widget": stock_widget,
            "web_context": web_context,
            "tool_manifest": tool_manifest,
            "tool_results": tool_results,
            "bundle": bundle,
            "query": query,
        }
        bundle_sources: Dict[str, Any] = {}
        if isinstance(bundle, Mapping):
            sanitized_bundle = sanitize_for_json(bundle)
            bundle_sources = sanitized_bundle.get("sources") or {}
            final_payload["bundle"] = sanitized_bundle
        elif bundle is not None:
            final_payload["bundle"] = sanitize_for_json(bundle)
        meta = self._shared_context.setdefault("_meta", {})
        if isinstance(bundle_sources, Mapping):
            meta["bundle_sources"] = dict(bundle_sources)
        analysis_sources = self._analysis_sources_snapshot(
            sql_ctx=sql_ctx,
            stock_widget=stock_widget if isinstance(stock_widget, Mapping) else None,
            web_context=web_context if isinstance(web_context, Mapping) else None,
            bundle_sources=bundle_sources if isinstance(bundle_sources, Mapping) else {},
        )
        if bundle_sources:
            final_payload["sources"] = bundle_sources
        if analysis_sources:
            final_payload["analysis_sources"] = analysis_sources
        analysis_bundle = self._analysis_bundle_snapshot(
            analysis_ctx=analysis_ctx,
            sql_ctx=sql_ctx,
            stock_widget=stock_widget if isinstance(stock_widget, Mapping) else None,
            web_context=web_context if isinstance(web_context, Mapping) else None,
        )
        if analysis_bundle:
            final_payload["analysis_bundle"] = analysis_bundle
        sanitized_cohesive_payload = sanitize_for_json(final_payload)
        if isinstance(sanitized_cohesive_payload, Mapping):
            sanitized_cohesive_payload = dict(sanitized_cohesive_payload)
        validator_debug = {
            "payload_keys": sorted(sanitized_cohesive_payload.keys()) if isinstance(sanitized_cohesive_payload, Mapping) else [],
            "analysis_sources": sanitized_cohesive_payload.get("analysis_sources") if isinstance(sanitized_cohesive_payload, Mapping) else None,
            "sources": sanitized_cohesive_payload.get("sources") if isinstance(sanitized_cohesive_payload, Mapping) else None,
        }
        hedged_ready = self._hedged_accessories_ready()
        if hedged_ready:
            completion_event = self._emit_hedged_accessories_complete(queue_only=False)
            if completion_event is not None:
                yield completion_event
        else:
            pending = [tool for tool, ready in self._hedged_completion.items() if not ready]
            logger.info(
                "Cohesive result delayed until accessories finish",
                extra={
                    "missing_tools": pending,
                    "session_id": self._session_id,
                    "flow": getattr(self, "flow_label", None),
                },
            )
            warning = {
                "event": "cohesive_result_error",
                "data": {
                    "message": "hedged_accessories incomplete; delaying cohesive_result",
                    "missing_tools": [tool for tool, ready in self._hedged_completion.items() if not ready],
                },
            }
            yield self._annotate(warning)
            final_event = _final_answer_event(analysis_text)
            if final_event:
                yield final_event
            return
        if isinstance(sanitized_cohesive_payload, Mapping) and any(
            value is not None for key, value in sanitized_cohesive_payload.items() if key not in {"query", "bundle"}
        ):
            try:
                validated_payload = self._cohesive_validator.ensure(sanitized_cohesive_payload)
                self._shared_context.setdefault("_meta", {}).setdefault("cohesive_payload", validated_payload)
            except CohesiveResultValidationError as exc:
                logger.warning(
                    "Cohesive result validation failed",
                    extra={
                        "session_id": self._session_id,
                        "flow": getattr(self, "flow_label", None),
                        "missing": list(self._cohesive_validator.required_keys),
                        "payload_keys": validator_debug.get("payload_keys"),
                        "analysis_sources": validator_debug.get("analysis_sources"),
                        "sources": validator_debug.get("sources"),
                        "error": str(exc),
                    },
                )
                error_event = {
                    "event": "cohesive_result_error",
                    "data": {
                        "message": str(exc),
                        "missing": list(self._cohesive_validator.required_keys),
                    },
                }
                yield self._annotate(error_event)
                final_event = _final_answer_event(analysis_text)
                if final_event:
                    yield final_event
                return
            yield self._annotate({"event": "cohesive_result", "data": validated_payload})
            lane_event = self._emit_lane_summary(self._lane_state_snapshot())
            if lane_event:
                yield self._annotate(lane_event)
        else:
            lane_event = self._emit_lane_summary(self._lane_state_snapshot())
            if lane_event:
                yield self._annotate(lane_event)

        await self._persist_bundle(bundle)

    def _maybe_agent_turn_start(self, event: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if event.get("event") != "progress":
            return None
        step = (event.get("data") or {}).get("step")
        role = self.AGENT_START_STEPS.get(step)
        if not role:
            return None
        self._timers[role] = time.time()
        lane = self.ROLE_LANES.get(role)
        retry_count = self._agent_retry_counts.get(lane, 0) if lane else 0
        payload: Dict[str, Any] = {
            "role": role,
            "status": "start",
            "step": step,
            "ts": datetime.utcnow().isoformat(),
            "retry_count": retry_count,
        }
        if lane:
            payload["lane"] = lane
        parallel_group = self.ROLE_PARALLEL_GROUPS.get(role)
        if parallel_group:
            payload["parallel_group"] = parallel_group
        metadata = self._get_tool_metadata_for_step(step)
        if metadata:
            payload["latency_budget_ms"] = metadata.get("latency_budget_ms")
            payload["output_artifacts"] = metadata.get("output_artifacts")
            payload["concurrency_limit"] = metadata.get("concurrency_limit")
        return self._annotate({"event": "agent_turn_start", "data": payload})

    def _maybe_agent_turn_end(self, event: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        role = self.AGENT_END_EVENTS.get(event.get("event"))
        if not role:
            return None
        start = self._timers.pop(role, None)
        elapsed = int((time.time() - start) * 1000) if start else None
        lane = self.ROLE_LANES.get(role)
        retry_count = self._agent_retry_counts.get(lane, 0) if lane else 0
        payload: Dict[str, Any] = {
            "role": role,
            "status": "complete",
            "ts": datetime.utcnow().isoformat(),
            "retry_count": retry_count,
        }
        if lane:
            payload["lane"] = lane
        summary = self._agent_summary(role, event)
        if summary:
            payload["summary"] = summary
        if elapsed is not None:
            payload["elapsed_ms"] = elapsed
        parallel_group = self.ROLE_PARALLEL_GROUPS.get(role)
        if parallel_group:
            payload["parallel_group"] = parallel_group
        metadata = self._get_tool_metadata_for_event(event.get("event")) or self._get_tool_metadata_for_role(role)
        if metadata:
            payload["latency_budget_ms"] = metadata.get("latency_budget_ms")
            payload["output_artifacts"] = metadata.get("output_artifacts")
            payload["concurrency_limit"] = metadata.get("concurrency_limit")
        return self._annotate({"event": "agent_turn_end", "data": payload})

    def _agent_tool_event_from_turn(
        self,
        turn_event: Dict[str, Any],
        *,
        status: str,
    ) -> Optional[Dict[str, Any]]:
        data = dict(turn_event.get("data") or {})
        role = data.get("role")
        if not role:
            return None
        tool_alias = self.ROLE_TOOL_ALIAS.get(str(role))
        if not tool_alias:
            return None
        lane = data.get("lane") or self.ROLE_LANES.get(role)
        if status == "start":
            counter = self._agent_tool_counters.get(tool_alias, 0) + 1
            self._agent_tool_counters[tool_alias] = counter
            call_id = f"{tool_alias}-{counter}"
            self._agent_tool_active_ids[tool_alias] = call_id
        else:
            call_id = self._agent_tool_active_ids.get(tool_alias)
            if not call_id:
                counter = self._agent_tool_counters.get(tool_alias, 0) + 1
                self._agent_tool_counters[tool_alias] = counter
                call_id = f"{tool_alias}-{counter}"
            if status == "completed":
                self._agent_tool_active_ids.pop(tool_alias, None)
        sequence_number = self._agent_tool_counters.get(tool_alias, 1)
        tool_call = {
            "id": call_id,
            "name": tool_alias,
            "lane": lane,
            "status": status,
            "sequence_number": sequence_number,
            "parallel_group": data.get("parallel_group"),
            "role": role,
        }
        payload: Dict[str, Any] = {
            "tool_call": {key: value for key, value in tool_call.items() if value is not None},
            "tool": tool_alias,
            "lane": lane,
            "role": role,
            "status": status,
            "parallel_group": data.get("parallel_group"),
            "retry_count": data.get("retry_count"),
            "ts": datetime.utcnow().isoformat(),
        }
        step = data.get("step")
        if step:
            payload["step"] = step
        if status == "completed":
            if "summary" in data:
                payload["summary"] = data.get("summary")
            if "elapsed_ms" in data:
                payload["elapsed_ms"] = data.get("elapsed_ms")
        event_name = "agent_tool_call" if status == "start" else "agent_tool_complete"
        return self._annotate({"event": event_name, "data": payload})

    def _agent_retry_event(self, role: str, trace: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
        last = trace[-1] if trace else {}
        lane = self.ROLE_LANES.get(role)
        retry_count = len(trace)
        if lane:
            self._agent_retry_counts[lane] = retry_count
        payload: Dict[str, Any] = {
            "role": role,
            "lane": lane,
            "status": "retry",
            "retry_count": retry_count,
            "ts": datetime.utcnow().isoformat(),
            "retry_trace": [dict(entry) for entry in trace],
        }
        if "error_code" in last:
            payload["error_code"] = last.get("error_code")
        error_message = last.get("error") or last.get("message")
        if error_message:
            payload["error"] = error_message
        parallel_group = self.ROLE_PARALLEL_GROUPS.get(role)
        if parallel_group:
            payload["parallel_group"] = parallel_group
        return self._annotate({"event": "tool_retry", "data": payload})

    def _agent_reasoning(self, event: Dict[str, Any], session_id: Optional[str]) -> Optional[Dict[str, Any]]:
        delta = (event.get("data") or {}).get("partial_analysis")
        if not delta:
            return None
        log_analysis_chunk(
            chunk=delta,
            step="analysis_generation",
            role="insight_reviewer",
            session_id=session_id,
            flow=getattr(self, "flow_label", None),
        )
        return {
            "event": "agent_reasoning",
            "data": {
                "role": "insight_reviewer",
                "thought": delta,
                "ts": datetime.utcnow().isoformat(),
            },
        }

    def _agent_summary(self, role: str, event: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        data = event.get("data") or {}
        if role == "intent_analyst":
            return {"intent_key": data.get("intent_key"), "confidence": data.get("confidence")}
        if role == "sql_specialist":
            return {"llm_used": data.get("llm_used"), "template_fallback": data.get("template_fallback")}
        if role == "risk_controller":
            return {"ok": data.get("ok"), "issues": data.get("issues_count")}
        if role == "data_engineer":
            return {"rows": data.get("row_count")}
        if role == "viz_designer":
            payload = {"chart_type": data.get("chart_type")}
            if "chart_spec_id" in data:
                payload["chart_spec_id"] = data.get("chart_spec_id")
            return payload
        if role == "insight_reviewer":
            return {"analysis_length": data.get("analysis_length")}
        return None

    def _format_backpressure_event(
        self,
        task_name: str,
        payload: Mapping[str, Any],
    ) -> Optional[Dict[str, Any]]:
        role = self.ORCHESTRATION_ROLES.get(task_name)
        lane = self.ROLE_LANES.get(role) if role else None
        parallel_group = payload.get("group") or (self.ROLE_PARALLEL_GROUPS.get(role) if role else None)
        if not parallel_group and not lane:
            return None
        data: Dict[str, Any] = {
            "ts": datetime.utcnow().isoformat(),
            "parallel_group": parallel_group or self.DEFAULT_PARALLEL_GROUP,
            "pending": int(payload.get("queue_size", 0) or 0),
            "running": int(payload.get("running", 0) or 0),
            "task": task_name,
        }
        limit = payload.get("limit")
        if isinstance(limit, (int, float)):
            data["limit"] = int(limit)
        position = payload.get("position")
        if isinstance(position, int):
            data["position"] = position
        if role:
            data["role"] = role
        if lane:
            data["lane"] = lane
            data["retry_count"] = self._agent_retry_counts.get(lane, 0)
        event = {"event": "agent_turn_backpressure", "data": data}
        annotated = self._annotate(event)
        try:
            backpressure_event(
                lane=lane,
                group=parallel_group or data.get("parallel_group"),
                pending=int(data.get("pending", 0) or 0),
                running=int(data.get("running", 0) or 0),
                limit=data.get("limit"),
                session_id=self._shared_context.get("session_id") if isinstance(self._shared_context, Mapping) else None,
                flow=self.flow_label,
            )
        except Exception:  # pragma: no cover - defensive
            pass
        return annotated

    def _format_agent_turn(
        self,
        role: str,
        status: str,
        *,
        summary: Optional[Dict[str, Any]] = None,
        elapsed: Optional[int] = None,
    ) -> Dict[str, Any]:
        lane = self.ROLE_LANES.get(role)
        retry_count = self._agent_retry_counts.get(lane, 0) if lane else 0
        payload: Dict[str, Any] = {
            "role": role,
            "status": status,
            "ts": datetime.utcnow().isoformat(),
            "retry_count": retry_count,
        }
        parallel_group = self.ROLE_PARALLEL_GROUPS.get(role)
        if parallel_group:
            payload["parallel_group"] = parallel_group
        if lane:
            payload["lane"] = lane
            tool_obj = self._specialist_tools.get(lane)
            if tool_obj:
                payload["tool"] = getattr(tool_obj, "name", f"{lane}_specialist")
                payload.setdefault("specialist", getattr(tool_obj, "name", f"{lane}_specialist"))
        if summary:
            payload["summary"] = summary
        if elapsed is not None:
            payload["elapsed_ms"] = elapsed
        event_name = "agent_turn_start" if status == "start" else "agent_turn_end"
        annotated = self._annotate({"event": event_name, "data": payload})
        if lane and status == "start":
            self._emit_lane_transition(
                lane,
                status=LANE_STATUS_RUNNING,
            )
        return annotated

    def _format_reasoning(self, role: str, result: AgentResult) -> Optional[Dict[str, Any]]:
        output = result.output or {}
        thought: Optional[str] = None
        if role == "planner_agent":
            tasks = output.get("tasks") or []
            bundle_id = output.get("bundle_id")
            descriptors = [f"{item['name']}={item['status']}" for item in tasks if isinstance(item, dict)]
            pieces = ["Planner tasks"]
            if bundle_id:
                pieces.append(f"bundle={bundle_id}")
            if descriptors:
                pieces.append(", ".join(descriptors))
            thought = " | ".join(pieces)
        elif role == "query_agent":
            attempts = output.get('attempt_count')
            last_status = output.get('last_status')
            last_error = output.get('last_error_code')
            parts = []
            if attempts is not None:
                parts.append(f"attempts={attempts}")
            if last_status:
                parts.append(f"last={last_status}")
            if last_error:
                parts.append(f"error={last_error}")
            thought = " | ".join(parts) if parts else None
        elif role == "analyst_agent":
            status = output.get("status")
            summary = output.get("summary")
            thought = f"Analyst status: {status}"
            if summary:
                thought = f"Analyst ({status}) summary: {summary[:120]}"
        elif role == "chart_agent":
            status = output.get("status")
            chart = output.get("chart") or {}
            if chart.get("chart_type"):
                thought = f"Chart agent ({status}) prepared {chart['chart_type']}"
            else:
                thought = f"Chart agent status: {status}"
        elif role == "market_agent":
            status = output.get("status")
            tickers = output.get("tickers") or []
            insights = output.get("insights") or {}
            change = insights.get("change_percent")
            if change is not None and tickers:
                thought = f"Market agent ({status}) {tickers[0]} change {change:.2f}%"
            elif tickers:
                thought = f"Market agent ({status}) monitoring {', '.join(tickers[:3])}"
            else:
                thought = f"Market agent status: {status}"
        if not thought:
            return None
        return {
            "event": "agent_reasoning",
            "data": {
                "role": role,
                "thought": thought,
                "ts": datetime.utcnow().isoformat(),
            },
        }

    def _result_summary(self, result: AgentResult) -> Dict[str, Any]:
        output = result.output or {}
        summary: Dict[str, Any] = {}
        if "status" in output:
            summary["status"] = output["status"]
        if "bundle_id" in output:
            summary["bundle_id"] = output["bundle_id"]
        if "tasks" in output:
            summary["tasks"] = output["tasks"]
        if "attempt_count" in output:
            summary["attempt_count"] = output["attempt_count"]
        if "last_status" in output and output.get("last_status") is not None:
            summary["last_status"] = output["last_status"]
        if "last_error_code" in output and output.get("last_error_code") is not None:
            summary["last_error_code"] = output["last_error_code"]
        if "summary" in output and output["summary"]:
            summary["attempts"] = output["summary"]
        if "chart" in output and output["chart"]:
            summary["chart"] = output["chart"]
        if "tickers" in output and output["tickers"]:
            summary["tickers"] = output["tickers"]
        if "snippets" in output and output["snippets"]:
            summary["snippets"] = len(output["snippets"])
        if "from_cache" in output:
            summary["from_cache"] = output["from_cache"]
        insights = output.get("insights")
        if insights:
            summary["insights"] = {
                "symbol": insights.get("symbol"),
                "change_percent": insights.get("change_percent"),
                "latest_close": insights.get("latest_close"),
            }
        if output.get("error"):
            summary["error"] = output["error"]
        return summary

    async def _persist_bundle(self, bundle: Optional[Dict[str, Any]]) -> None:
        if not bundle or not self._session_snapshot:
            return
        try:
            sanitized_bundle = sanitize_for_json(bundle)
            self._session_snapshot.record_tool_result("planner_bundle", sanitized_bundle)
            repository = get_session_state_repository()
            await repository.save(self._session_snapshot)
        except Exception:
            pass

    def _record_snapshot(
        self,
        *,
        sql: Optional[str] = None,
        chart_spec: Optional[Dict[str, Any]] = None,
        analysis: Optional[str] = None,
    ) -> None:
        if not self._session_snapshot:
            return
        self._session_snapshot.record_outputs(
            sql=sql,
            chart_spec=chart_spec,
            analysis=analysis,
        )

        return {
        }

    @property
    def _session_id(self) -> Optional[str]:
        return getattr(self._session_snapshot, "session_id", None)


__all__ = ["MultiAgentFlow"]

