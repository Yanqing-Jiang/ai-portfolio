from __future__ import annotations

import asyncio
import contextlib
from dataclasses import dataclass, field
from datetime import datetime
import copy
import json
import uuid
import os
import time
import logging
from typing import Any, AsyncGenerator, Dict, Iterable, List, Optional, Set, Tuple, Mapping, TYPE_CHECKING

from agents import Agent, Runner
from agents.tool import FunctionTool
from agents.tool_context import ToolContext
from agents.run import RunConfig
from analytics.artifacts.models import PipelineArtifacts
from analytics.core.events import EventEmitter
from analytics.core import telemetry
from analytics.core.telemetry import tool_iteration as log_tool_iteration
from analytics.core.intent import OffTopicClassifierSchema
from analytics.core.session_state import SessionStateSnapshot, get_session_state_repository
from analytics.validators import sanitize_for_json
from analytics.routing import FollowUpRoute
from .hooks import AnalyticsFlowHooks
from .planner_executor import (
    _build_analysis_source_summaries,
    _build_planner_result_payload,
    _build_reused_analysis_event,
    FOLLOW_UP_BANNERS,
    ToolInvocationReceipt,
    _hash_payload,
    PlannerPhaseContext,
    PlannerExecutorFlow,
    _reset_revision_accessories,
    _INTENT_LANE_HINTS,
)
from .orchestrator_adapter import PlannerOrchestratorAdapter
from .pipeline_tools import PlannerToolDefinition, PlannerToolRegistry, get_planner_tool_registry
from .schedulers import FlowMode, apply_mode_metadata, get_mode_config
from .planner import (
    annotate_revision_event,
    apply_revision_plan,
    build_revision_plan,
    build_revision_request_event,
    derive_revision_targets,
    ensure_analysis_dependencies,
    ToolParallelRuntime,
    stream_analysis_lane,
    stream_chart_lane,
    stream_sql_lane,
)
from .sequencer import (
    LANE_STATUS_COMPLETED,
    LANE_STATUS_FAILED,
    LANE_STATUS_RUNNING,
    LANE_STATUS_SKIPPED,
    LANE_TOOL_LOOKUP as SEQUENCER_LANE_TOOL_LOOKUP,
    LANE_TOOL_MAP as SEQUENCER_LANE_TOOL_MAP,
    PlannerSequencer,
)
from .tooling import StockTrackerAdapter
from analytics.core.config_store import get_config_store

logger = logging.getLogger(__name__)


if TYPE_CHECKING:  # pragma: no cover - typing only
    from .revision_directive import RevisionDirective


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


@dataclass
class _SingleAgentRunContext:
    controller: "SingleAgentController"
    session_id: Optional[str]
    query: str
    queue: "asyncio.Queue[Optional[Dict[str, Any]]]"
    revision_directive: Optional["RevisionDirective"]
    tool_attempts: Dict[str, int] = field(default_factory=dict)
    tool_retry_counts: Dict[str, int] = field(default_factory=dict)
    tool_receipts: Dict[str, Any] = field(default_factory=dict)
    run_id: Optional[str] = None
    trace_id: Optional[str] = None


@dataclass
class _SequencerRunState:
    ctx: PlannerPhaseContext
    registry: PlannerToolRegistry
    executed: Set[str]
    mode_config: Any
    query: str
    session_id: Optional[str]
    tool_runtime: Optional[Any] = None
    tool_state: Optional[Dict[str, Any]] = None
    revision_plan: Optional[Any] = None
    derived_targets: Optional[Set[str]] = None
    lane_states: Optional[Dict[str, str]] = None
    run_sql_lane: bool = True
    run_chart_lane: bool = True
    run_analysis_lane: bool = True
    stock_only_run: bool = False
    is_revision_follow_up: bool = False

def _build_single_agent_cohesive_payload(
    analysis_payload: Dict[str, Any],
    artifacts: Optional[PipelineArtifacts],
    *,
    default_manifest: Optional[List[Dict[str, Any]]] = None,
) -> Optional[Dict[str, Any]]:
    if not isinstance(analysis_payload, dict):
        analysis_payload = {}

    payload: Dict[str, Any] = {}

    analysis_text = analysis_payload.get("analysis")
    if isinstance(analysis_text, str) and analysis_text.strip():
        payload["analysis"] = analysis_text

    length_value = analysis_payload.get("analysis_length")
    if isinstance(length_value, (int, float)):
        payload["analysis_length"] = int(length_value)

    passthrough_keys = {
        "tldr",
        "bullets",
        "key_numbers",
        "risk_watch",
        "next_steps",
        "latency_guardrail",
        "analysis_overview",
        "analysis_sources",
        "tool_manifest",
        "tool_results",
        "stock_widget",
        "web_context",
        "bundle",
        "banner",
    }
    for key in passthrough_keys:
        if key in analysis_payload and analysis_payload[key] is not None:
            payload[key] = copy.deepcopy(analysis_payload[key])

    if (not payload.get("tool_manifest")) and default_manifest:
        payload["tool_manifest"] = copy.deepcopy(default_manifest)

    if artifacts:
        chart_art = artifacts.chart
        if chart_art and chart_art.spec:
            payload.setdefault("chart_spec", copy.deepcopy(chart_art.spec))
            if chart_art.spec_id:
                payload.setdefault("chart_spec_id", chart_art.spec_id)

        sql_gen = artifacts.sql_generation
        if sql_gen and sql_gen.sql:
            payload.setdefault("sql", sql_gen.sql)

        sql_exec = artifacts.sql_execution
        if sql_exec:
            if sql_exec.row_count is not None:
                payload.setdefault("sql_row_count", sql_exec.row_count)
            if sql_exec.columns:
                payload.setdefault("columns", list(sql_exec.columns))
            sample = sql_exec.sample_rows or sql_exec.dataset_preview
            if sample:
                payload.setdefault("data_sample", copy.deepcopy(sample))

        analysis_art = artifacts.analysis
        if analysis_art:
            if ("analysis" not in payload or not payload.get("analysis")) and analysis_art.analysis_text:
                payload["analysis"] = analysis_art.analysis_text
                if analysis_art.length is not None and "analysis_length" not in payload:
                    payload["analysis_length"] = analysis_art.length
            if ("stock_widget" not in payload or not payload.get("stock_widget")) and analysis_art.stock_widget:
                payload["stock_widget"] = copy.deepcopy(analysis_art.stock_widget)
            if ("web_context" not in payload or not payload.get("web_context")) and analysis_art.web_context:
                payload["web_context"] = copy.deepcopy(analysis_art.web_context)
            if "analysis_overview" not in payload or not payload.get("analysis_overview"):
                overview: Dict[str, Any] = {}
                if analysis_art.summary:
                    overview["tldr"] = analysis_art.summary
                if analysis_art.highlights:
                    overview["highlights"] = list(analysis_art.highlights)
                if analysis_art.key_numbers:
                    overview["key_numbers"] = list(analysis_art.key_numbers)
                if analysis_art.risk_watch:
                    overview["risk_watch"] = list(analysis_art.risk_watch)
                if analysis_art.next_steps:
                    overview["next_steps"] = list(analysis_art.next_steps)
                if analysis_art.evidence:
                    overview["evidence"] = copy.deepcopy(analysis_art.evidence)
                if overview:
                    payload["analysis_overview"] = overview
            if analysis_art.tool_bundle:
                bundle = analysis_art.tool_bundle
                if bundle.get("tool_manifest") and not payload.get("tool_manifest"):
                    payload["tool_manifest"] = copy.deepcopy(bundle["tool_manifest"])
                if bundle.get("tool_results") and not payload.get("tool_results"):
                    payload["tool_results"] = copy.deepcopy(bundle["tool_results"])
                if bundle.get("stock_widget") and not payload.get("stock_widget"):
                    payload["stock_widget"] = copy.deepcopy(bundle["stock_widget"])
                if bundle.get("web_context") and not payload.get("web_context"):
                    payload["web_context"] = copy.deepcopy(bundle["web_context"])

        market_art = artifacts.market if artifacts else None
        if market_art and market_art.snapshot and not payload.get("stock_widget"):
            payload["stock_widget"] = copy.deepcopy(market_art.snapshot)

        web_art = artifacts.web if artifacts else None
        if web_art and not payload.get("web_context"):
            payload["web_context"] = web_art.to_dict()

    existing_sources = payload.get("analysis_sources")
    if existing_sources:
        sanitized_sources = sanitize_for_json(existing_sources)
        if isinstance(sanitized_sources, dict):
            payload["analysis_sources"] = sanitized_sources
        else:
            payload.pop("analysis_sources", None)
    else:
        snapshot_reuse = analysis_payload.get("snapshot_reuse")
        reuse_flags: Dict[str, bool] = {}
        if isinstance(snapshot_reuse, Mapping):
            reuse_flags = {
                "sql": bool(snapshot_reuse.get("reused_sql")),
                "stock": bool(snapshot_reuse.get("reused_stock")),
                "web": bool(snapshot_reuse.get("reused_web")),
            }
        tool_sources = analysis_payload.get("sources")
        derived_sources = _build_analysis_source_summaries(
            artifacts=artifacts,
            tool_sources=tool_sources if isinstance(tool_sources, Mapping) else None,
            stock_widget=payload.get("stock_widget") or analysis_payload.get("stock_widget"),
            web_context=payload.get("web_context") or analysis_payload.get("web_context"),
            reused_flags=reuse_flags,
        )
        if derived_sources:
            payload["analysis_sources"] = derived_sources

    sanitized = sanitize_for_json(payload)
    if not sanitized:
        return None
    has_sql = bool(sanitized.get("sql")) or bool(sanitized.get("data_sample")) or bool(sanitized.get("columns"))
    stock_widget = sanitized.get("stock_widget")
    has_stock = bool(stock_widget)
    web_context = sanitized.get("web_context")
    if isinstance(web_context, dict):
        has_web = bool(web_context.get("snippets") or web_context.get("summary") or web_context.get("articles"))
    else:
        has_web = bool(web_context)
    if not (has_sql and has_stock and has_web):
        return None
    return sanitized


class _SingleAgentToolHooks(AnalyticsFlowHooks):
    def __init__(self, flow: "SingleAgentController", session_id: Optional[str] = None) -> None:
        self._flow = flow
        self._timers: Dict[str, float] = {}
        self._sql_compile_details: Dict[str, Any] = {}
        self._session_id: Optional[str] = session_id
        self._emitted_cohesive = False
        self._last_analysis_payload: Optional[Dict[str, Any]] = None
        self._final_answer_emitted = False
        self._chart_revision_missing_session = False
        self._agentic_revision_mode: bool = False
        self._agentic_lane_targets: Set[str] = set()
        self._sync_agentic_revision_state()

    def _sync_agentic_revision_state(self) -> None:
        self._agentic_revision_mode = bool(getattr(self._flow, "_agentic_revision_mode", False))
        flow_targets = getattr(self._flow, "_agentic_lane_targets", None)
        if isinstance(flow_targets, set):
            lane_targets = set(flow_targets)
        elif isinstance(flow_targets, Iterable) and not isinstance(flow_targets, (str, bytes)):
            lane_targets = {
                str(target).strip().lower()
                for target in flow_targets
                if target is not None and str(target).strip()
            }
        else:
            lane_targets = set()
        self._agentic_lane_targets = lane_targets

    async def on_flow_start(self, ctx: Dict[str, Any]) -> AsyncGenerator[Dict[str, Any], None]:
        self._emitted_cohesive = False
        self._last_analysis_payload = None
        self._final_answer_emitted = False
        self._chart_revision_missing_session = False
        self._sync_agentic_revision_state()
        if ctx.get("session_id") and not self._session_id:
            session = ctx.get("session_id")
            if isinstance(session, str) and session:
                self._session_id = session
        if False:
            yield {}

    async def before_event(self, ctx: Dict[str, Any], event: Dict[str, Any]) -> AsyncGenerator[Dict[str, Any], None]:
        self._sync_agentic_revision_state()
        if False:
            yield {}
        name = event.get("event")
        if name == "session_started":
            data = event.get("data") or {}
            self._session_id = data.get("session_id") or ctx.get("session_id")
            ctx["session_id"] = self._session_id
            return
        if name != "progress":
            return
        step = (event.get("data") or {}).get("step")
        tool = self._flow.TOOL_START_STEPS.get(step)
        if not tool:
            return
        self._timers[tool] = time.time()
        log_tool_iteration(
            tool=tool,
            status="start",
            step=step,
            session_id=self._session_id,
            flow=self._flow.flow_label,
        )
        payload: Dict[str, Any] = {
            "tool": tool,
            "status": "start",
            "step": step,
            "ts": datetime.utcnow().isoformat(),
        }
        attempt = self._flow.get_tool_attempt(tool)
        if attempt:
            payload["attempt"] = attempt
            payload["retry"] = attempt > 1
            payload["retry_count"] = max(attempt - 1, 0)
        metadata = self._flow.get_tool_metadata_for_step(step)
        if not metadata:
            metadata = self._flow.get_tool_metadata_for_alias(tool)
        if metadata:
            payload["latency_budget_ms"] = metadata.get("latency_budget_ms")
            payload["output_artifacts"] = metadata.get("output_artifacts")
            payload["concurrency_limit"] = metadata.get("concurrency_limit")
        annotated = apply_mode_metadata({"event": "tool_call", "data": payload}, self._flow.flow_mode)
        annotated["data"]["follow_up_route"] = self._flow.follow_up_route.value
        yield annotated

    def _maybe_emit_cohesive_result(self, analysis_payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if self._emitted_cohesive:
            return None
        cohesive_payload = _build_single_agent_cohesive_payload(
            analysis_payload=analysis_payload,
            artifacts=self._flow.latest_artifacts(),
            default_manifest=self._flow.planner_tool_manifest,
        )
        if not cohesive_payload:
            return None
        self._emitted_cohesive = True
        event = {"event": "cohesive_result", "data": cohesive_payload}
        annotated = apply_mode_metadata(event, self._flow.flow_mode)
        annotated["data"]["follow_up_route"] = self._flow.follow_up_route.value
        return annotated

    async def after_event(self, ctx: Dict[str, Any], event: Dict[str, Any]) -> AsyncGenerator[Dict[str, Any], None]:
        if False:
            yield {}
        event_name = event.get("event")
        if event_name == "error":
            data = event.get("data") or {}
            code = str(data.get("code") or "").upper()
            if code == "CHART_REVISION_MISSING_SESSION":
                self._chart_revision_missing_session = True
                self._flow.set_follow_up_route(FollowUpRoute.FULL_PIPELINE)
            return
        if event_name == "final_answer":
            self._final_answer_emitted = True
            return
        if event_name == "sql_compiled":
            self._sql_compile_details = event.get("data", {}) or {}
            return

        tool = self._flow.TOOL_END_EVENTS.get(event_name)
        if tool:
            start = self._timers.pop(tool, None)
            elapsed = int((time.time() - start) * 1000) if start else None
            payload: Dict[str, Any] = {
                "tool": tool,
                "status": "end",
                "ts": datetime.utcnow().isoformat(),
                "details": self._extract_tool_details(tool, event),
            }
            attempt = self._flow.get_tool_attempt(tool)
            if attempt:
                payload["attempt"] = attempt
                payload["retry"] = attempt > 1
                payload["retry_count"] = max(attempt - 1, 0)
            if elapsed is not None:
                payload["elapsed_ms"] = elapsed
            metadata = self._flow.get_tool_metadata_for_event(event_name)
            if not metadata:
                metadata = self._flow.get_tool_metadata_for_alias(tool)
            if metadata:
                payload["latency_budget_ms"] = metadata.get("latency_budget_ms")
                payload["output_artifacts"] = metadata.get("output_artifacts")
                payload["concurrency_limit"] = metadata.get("concurrency_limit")
            log_tool_iteration(
                tool=tool,
                status="end",
                step=event_name,
                session_id=self._session_id,
                flow=self._flow.flow_label,
                elapsed_ms=elapsed,
                details=payload.get("details") or payload,
            )
            annotated_end = apply_mode_metadata({"event": "tool_call", "data": payload}, self._flow.flow_mode)
            annotated_end["data"]["follow_up_route"] = self._flow.follow_up_route.value
            yield annotated_end
            return

        if event_name == "analysis_complete":
            analysis_payload = copy.deepcopy(event.get("data") or {})
            if (not analysis_payload.get("tool_manifest")) and self._flow.planner_tool_manifest:
                analysis_payload["tool_manifest"] = copy.deepcopy(self._flow.planner_tool_manifest)
            self._last_analysis_payload = analysis_payload
            cohesive_event = self._maybe_emit_cohesive_result(analysis_payload)
            if cohesive_event:
                yield cohesive_event
            return

        if event_name == "workflow_complete":
            if self._last_analysis_payload:
                cohesive_event = self._maybe_emit_cohesive_result(copy.deepcopy(self._last_analysis_payload))
                if cohesive_event:
                    yield cohesive_event
            return

    def _analysis_text(self) -> Optional[str]:
        if not self._last_analysis_payload:
            return None
        analysis_field = self._last_analysis_payload.get("analysis")
        if isinstance(analysis_field, str):
            stripped = analysis_field.strip()
            return stripped or None
        if isinstance(analysis_field, Mapping):
            nested = analysis_field.get("analysis")
            if isinstance(nested, str):
                stripped = nested.strip()
                return stripped or None
        return None

    @staticmethod
    def _web_payload_has_content(payload: Any) -> bool:
        if isinstance(payload, Mapping):
            summary = payload.get("summary")
            if isinstance(summary, str) and summary.strip():
                return True
            snippets = payload.get("snippets") or payload.get("articles")
            if isinstance(snippets, list) and len(snippets) > 0:
                return True
        return False

    @staticmethod
    def _payload_has_stock(payload: Any) -> bool:
        if not isinstance(payload, Mapping):
            return False
        widget = payload.get("stock_widget")
        if isinstance(widget, Mapping):
            return bool(widget)
        return False

    def _component_status(self) -> Dict[str, bool]:
        self._sync_agentic_revision_state()
        artifacts = self._flow.latest_artifacts()
        has_sql = False
        has_stock = False
        has_web = False

        if artifacts:
            sql_generation = getattr(artifacts, "sql_generation", None)
            if sql_generation and getattr(sql_generation, "sql", None):
                has_sql = True
            if not has_sql:
                sql_execution = getattr(artifacts, "sql_execution", None)
                if sql_execution:
                    if getattr(sql_execution, "row_count", None) is not None:
                        has_sql = True
                    columns = getattr(sql_execution, "columns", None)
                    if columns:
                        has_sql = True
                    sample_rows = getattr(sql_execution, "sample_rows", None) or getattr(sql_execution, "dataset_preview", None)
                    if sample_rows:
                        has_sql = True
            market_artifact = getattr(artifacts, "market", None)
            if market_artifact and getattr(market_artifact, "snapshot", None):
                has_stock = True
            analysis_artifact = getattr(artifacts, "analysis", None)
            if analysis_artifact:
                if not has_stock and getattr(analysis_artifact, "stock_widget", None):
                    has_stock = True
                if not has_web and self._web_payload_has_content(getattr(analysis_artifact, "web_context", None)):
                    has_web = True
            web_artifact = getattr(artifacts, "web", None)
            if web_artifact:
                summary = getattr(web_artifact, "summary", None)
                if isinstance(summary, str) and summary.strip():
                    has_web = True
                snippets = getattr(web_artifact, "snippets", None)
                if isinstance(snippets, list) and snippets:
                    has_web = True

        analysis_payload = self._last_analysis_payload or {}
        if not has_sql:
            sql_field = analysis_payload.get("sql")
            if isinstance(sql_field, str) and sql_field.strip():
                has_sql = True
            sample = analysis_payload.get("data_sample")
            if not has_sql and sample:
                has_sql = True
            columns_payload = analysis_payload.get("columns")
            if not has_sql and columns_payload:
                has_sql = True
        if not has_stock and self._payload_has_stock(analysis_payload):
            has_stock = True
        if not has_web and self._web_payload_has_content(analysis_payload.get("web_context")):
            has_web = True

        if self._agentic_revision_mode and self._agentic_lane_targets:
            if "sql" not in self._agentic_lane_targets:
                has_sql = True
            if "market" not in self._agentic_lane_targets:
                has_stock = True
            if "web" not in self._agentic_lane_targets:
                has_web = True

        return {
            "sql": has_sql,
            "stock": has_stock,
            "web": has_web,
        }

    def _build_final_answer_payload(self) -> Optional[Dict[str, Any]]:
        status = self._component_status()
        missing = [component for component in ("sql", "stock", "web") if not status.get(component, False)]
        analysis_text = self._analysis_text()
        human_labels = {
            "sql": "SQL data",
            "stock": "stock data",
            "web": "online research data",
        }
        note: Optional[str] = None
        reuse_scope = (
            self._flow.follow_up_route == FollowUpRoute.REUSE_SQL
            and not self._chart_revision_missing_session
        )
        if self._chart_revision_missing_session:
            missing = ["sql", "stock", "web"]
            note = (
                "I couldn't apply the chart update because the saved session expired. "
                "Ask me to rerun the full analysis so I can rebuild fresh data and charts."
            )
        elif reuse_scope:
            # For chart-only revisions we intentionally reuse the existing SQL, stock, and web context,
            # so suppress the generic "Pending lanes" warning and surface a reuse hint instead.
            missing = []
            if self._agentic_revision_mode:
                note = "Revision applied. Reused cached datasets for untouched lanes."
            else:
                note = "Chart revision applied. Reused cached datasets for consistency."
        elif missing:
            # Suppress redundant "Pending lanes" note to avoid noisy cards.
            # We keep the existing analysis text (if any) and omit the extra banner.
            note = None
        parts: List[str] = []
        if analysis_text:
            parts.append(analysis_text.rstrip())
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
            "analysis_available": bool(analysis_text),
        }

    async def on_flow_end(
        self,
        ctx: Dict[str, Any],
        *,
        error: Optional[BaseException] = None,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        if False:
            yield {}
        if error is not None or self._emitted_cohesive or self._final_answer_emitted:
            return
        fallback_payload = self._build_final_answer_payload()
        if not fallback_payload:
            return
        event = {
            "event": "final_answer",
            "data": {
                "message": fallback_payload["message"],
                "missing_components": fallback_payload["missing_components"],
                "analysis_available": fallback_payload["analysis_available"],
                "final_answer_only": True,
                "ts": datetime.utcnow().isoformat(),
                "flow_mode": self._flow.flow_mode.value,
            },
        }
        annotated = apply_mode_metadata(event, self._flow.flow_mode)
        annotated["data"]["follow_up_route"] = self._flow.follow_up_route.value
        self._final_answer_emitted = True
        yield annotated

    def _extract_tool_details(self, tool: str, event: Dict[str, Any]) -> Dict[str, Any]:
        data = event.get("data") or {}
        if tool == "intent_classifier":
            return {
                "intent_key": data.get("intent_key"),
                "confidence": data.get("confidence"),
                "clarifications_needed": data.get("clarifications_needed"),
            }
        if tool == "sql_generator":
            details = {"llm_used": data.get("llm_used")}
            if self._sql_compile_details:
                details["template_used"] = self._sql_compile_details.get("template_used")
                details["sql_length"] = self._sql_compile_details.get("sql_length")
            self._sql_compile_details = {}
            return details
        if tool == "sql_validator":
            return {"ok": data.get("ok"), "issues": data.get("issues_count")}
        if tool == "sql_executor":
            return {"row_count": data.get("row_count")}
        if tool == "chart_designer":
            return {"chart_type": data.get("chart_type")}
        if tool == "analysis_writer":
            return {"analysis_length": data.get("analysis_length")}
        return data


class SingleAgentController:
    """Augments the planner-executor flow with explicit tool-call telemetry."""

    TOOL_START_STEPS = {
        "classification": "intent_classifier",
        "intent_detection": "intent_classifier",
        "clarification": "clarification_manager",
        "plan_generation": "planner",
        "sql_compilation": "sql_generator",
        "sql_validation": "sql_validator",
        "sql_execution": "sql_executor",
        "chart_generation": "chart_designer",
        "chart_revision": "chart_designer",
        "analysis_generation": "analysis_writer",
        "analysis_revision": "analysis_writer",
        "web_refresh": "web_retriever",
        "market_refresh": "stock_tracker",
    }

    TOOL_END_EVENTS = {
        "classification_complete": "intent_classifier",
        "intent_detection_complete": "intent_classifier",
        "clarification_resolved": "clarification_manager",
        "clarification_skipped": "clarification_manager",
        "clarification_timeout": "clarification_manager",
        "sql_generated": "sql_generator",
        "sql_validated": "sql_validator",
        "execution_stats": "sql_executor",
        "chart_generated": "chart_designer",
        "chart_patch": "chart_designer",
        "analysis_revision": "analysis_writer",
        "analysis_complete": "analysis_writer",
        "web_ready": "web_retriever",
        "stock_ready": "stock_tracker",
    }

    TOOL_METADATA_STEP_MAP = {
        "classification": "classification",
        "intent_detection": "intent_detection",
        "clarification": "clarification",
        "plan_generation": "plan_generation",
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
        "classification_complete": "classification",
        "intent_detection_complete": "intent_detection",
        "clarification_resolved": "clarification",
        "clarification_skipped": "clarification",
        "clarification_timeout": "clarification",
        "sql_generated": "sql_generation",
        "sql_compiled": "sql_generation",
        "sql_validated": "sql_generation",
        "execution_stats": "sql_generation",
        "chart_generated": "chart_generation",
        "chart_patch": "chart_revision",
        "analysis_revision": "analysis_revision",
        "analysis_complete": "analysis_generation",
        "web_ready": "web_refresh",
        "stock_ready": "market_refresh",
    }

    TOOL_METADATA_ALIAS_MAP = {
        "intent_classifier": "classification",
        "clarification_manager": "clarification",
        "planner": "plan_generation",
        "sql_generator": "sql_generation",
        "sql_validator": "sql_generation",
        "sql_executor": "sql_generation",
        "chart_designer": "chart_generation",
        "analysis_writer": "analysis_generation",
        "web_retriever": "web_refresh",
        "stock_tracker": "market_refresh",
    }

    LANE_CACHE_TTL_SECONDS: int = 600
    LANE_TOOL_MAP: Dict[str, Tuple[str, ...]] = dict(SEQUENCER_LANE_TOOL_MAP)
    LANE_TOOL_LOOKUP: Dict[str, str] = dict(SEQUENCER_LANE_TOOL_LOOKUP)

    def __init__(self) -> None:
        self._planner = PlannerExecutorFlow(flow_mode=FlowMode.SINGLE_AGENT)
        self.follow_up_route = FollowUpRoute.FULL_PIPELINE
        self._planner.set_follow_up_route(self.follow_up_route)
        self.flow_mode = FlowMode.SINGLE_AGENT
        self.flow_label = "single-agent"
        self._config_store = get_config_store()
        self._agent_settings = self._config_store.get_agent_mode_config("single_agent")
        self._agent_model = str(self._agent_settings.get("model") or "gpt-4.1")
        self._agent_reasoning_effort = str(
            self._agent_settings.get("reasoning_effort") or "medium"
        )
        self._max_turns = int(self._agent_settings.get("max_turns") or 10)
        self._tool_retry_limit = int(self._agent_settings.get("max_tool_retries") or 2)

        self._registry = get_planner_tool_registry()
        self.planner_tool_manifest = self._registry.describe_tools()
        self._tool_metadata_by_registry = _build_tool_metadata(self.planner_tool_manifest)
        self.tool_metadata: Dict[str, Dict[str, Any]] = {}
        for alias, registry_name in self.TOOL_METADATA_ALIAS_MAP.items():
            metadata = self._tool_metadata_by_registry.get(registry_name)
            if metadata:
                self.tool_metadata[alias] = metadata

        flag = str(os.getenv("ANALYTICS_ENABLE_AGENTS", "")).strip().lower()
        self._agents_enabled = flag in {"1", "true", "yes", "on"}
        if self._agents_enabled and not os.getenv("OPENAI_API_KEY"):
            self._agents_enabled = False
        self._function_tools: List[FunctionTool] = []
        self._agent: Optional[Agent[Any]] = None
        if self._agents_enabled:
            self._function_tools = [
                self._build_function_tool(tool_definition)
                for tool_definition in self._registry.list_tools()
            ]
            instructions = self._agent_settings.get(
                "instructions",
                (
                    "You are the Analytics Planner. Execute classification, planning, SQL, chart, "
                    "market, and analysis tools to fulfill the user's analytics request. Respect "
                    "cached receipts when provided, and only call tools necessary to refresh stale lanes."
                ),
            )
            self._agent = Agent(
                name="analytics_single_agent",
                instructions=instructions,
                model=self._agent_model,
                tools=list(self._function_tools),
            )

        self._revision_directive: Optional["RevisionDirective"] = None
        self._agentic_revision_mode: bool = False
        self._agentic_lane_targets: Set[str] = set()
        self._tool_attempts: Dict[str, int] = {}
        self._sequencer_state: Optional[_SequencerRunState] = None

    async def _prepare_sequencer_state(
        self,
        query: str,
        *,
        session_id: Optional[str],
    ) -> _SequencerRunState:
        ctx = await self._planner.initialize_context(query or "", session_id=session_id)
        registry = self._registry
        executed: Set[str] = set()
        mode_config = get_mode_config(self.flow_mode)
        state = _SequencerRunState(
            ctx=ctx,
            registry=registry,
            executed=executed,
            mode_config=mode_config,
            query=query,
            session_id=session_id,
        )
        is_revision_follow_up = (
            ctx.follow_up_route != FollowUpRoute.FULL_PIPELINE
            or bool(getattr(ctx, "revision_targets", None))
        )
        state.is_revision_follow_up = is_revision_follow_up
        setattr(ctx, "is_revision_follow_up", is_revision_follow_up)
        state.session_id = ctx.session_id
        if is_revision_follow_up:
            executed.update({"classification", "clarification"})
            classification_artifact = getattr(ctx.artifacts, "classification", None)
            if classification_artifact is not None:
                is_financial = getattr(classification_artifact, "is_financial", None)
                if is_financial is not None:
                    ctx.is_financial_query = bool(is_financial)
                if getattr(ctx, "classification", None) is None:
                    raw_payload = getattr(classification_artifact, "raw", None)
                    if isinstance(raw_payload, dict):
                        try:
                            ctx.classification = OffTopicClassifierSchema.model_validate(raw_payload)
                        except Exception:
                            pass
            else:
                ctx.is_financial_query = True
            await self._planner._persist_session_state(ctx, record_artifacts=True)
        self._sequencer_state = state
        return state

    async def _intent_stage(self) -> AsyncGenerator[Dict[str, Any], None]:
        state = self._sequencer_state
        if state is None:
            raise RuntimeError("Sequencer state not initialized")
        ctx = state.ctx
        registry = state.registry
        executed = state.executed
        is_revision_follow_up = state.is_revision_follow_up

        if not is_revision_follow_up:
            async for event in registry.invoke("classification", self._planner, ctx, executed=executed):
                yield event
            await self._planner._persist_session_state(ctx, record_artifacts=True)
            if not ctx.is_financial_query:
                ctx.halted = True
                return

        tool_sequence: Tuple[str, ...]
        if is_revision_follow_up:
            needs_intent = ctx.intent is None
            needs_plan = (ctx.plan or ctx.provisional_plan) is None
            if needs_intent:
                tool_sequence = ("intent_detection",)
            else:
                tool_sequence = ()
                executed.add("intent_detection")
            if needs_plan:
                tool_sequence = tool_sequence + ("plan_generation",)
            else:
                executed.add("plan_generation")
        else:
            tool_sequence = ("intent_detection", "clarification", "plan_generation")

        for tool_name in tool_sequence:
            async for event in registry.invoke(tool_name, self._planner, ctx, executed=executed):
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
            for tool_event in self._planner._collect_tool_deltas_now(state.tool_state, ctx):
                yield tool_event

        derived_targets = derive_revision_targets(ctx, intent_lane_map=_INTENT_LANE_HINTS)
        state.derived_targets = set(derived_targets or set())
        revision_plan = build_revision_plan(ctx, targets=state.derived_targets)
        apply_revision_plan(ctx, revision_plan)
        state.revision_plan = revision_plan
        state.run_sql_lane = revision_plan.run_sql_lane
        state.run_chart_lane = revision_plan.run_chart_lane
        state.run_analysis_lane = revision_plan.run_analysis_lane
        state.stock_only_run = revision_plan.stock_only

        telemetry.revision_plan(
            session_id=ctx.session_id,
            flow=self.flow_label,
            targets=sorted(revision_plan.targets),
            run_sql_lane=revision_plan.run_sql_lane,
            run_chart_lane=revision_plan.run_chart_lane,
            run_analysis_lane=revision_plan.run_analysis_lane,
            stock_only=revision_plan.stock_only,
            follow_up_route=(ctx.follow_up_route.value if getattr(ctx, "follow_up_route", None) else None),
            revision_id=getattr(ctx, "revision_id", None),
        )

    async def _sql_stage(self) -> AsyncGenerator[Dict[str, Any], None]:
        state = self._sequencer_state
        if state is None:
            raise RuntimeError("Sequencer state not initialized")
        ctx = state.ctx
        if getattr(ctx, "halted", False):
            return
        registry = state.registry
        executed = state.executed
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
            yield revision_event

        async for event in stream_sql_lane(
            self._planner,
            ctx=ctx,
            registry=registry,
            executed=executed,
            tool_state=state.tool_state,
            run_sql_lane=state.run_sql_lane,
        ):
            yield event

        async for event in self._planner._stream_with_tool_state(
            ensure_analysis_dependencies(self._planner, ctx, mode_config=state.mode_config),
            state.tool_state,
            ctx,
        ):
            yield event

    async def _noop_stage(self) -> AsyncGenerator[Dict[str, Any], None]:
        if False:
            yield {}

    async def _web_stage(self) -> AsyncGenerator[Dict[str, Any], None]:
        state = self._sequencer_state
        if state is None:
            raise RuntimeError("Sequencer state not initialized")
        ctx = state.ctx
        if getattr(ctx, "halted", False):
            return
        async for event in self._planner.refresh_web_lane(
            ctx,
            reason="sequencer_web_refresh",
            source="single_agent_sequencer",
        ):
            yield event

    async def _market_stage(self) -> AsyncGenerator[Dict[str, Any], None]:
        state = self._sequencer_state
        if state is None:
            raise RuntimeError("Sequencer state not initialized")
        ctx = state.ctx
        if getattr(ctx, "halted", False):
            return
        async for event in self._planner.refresh_market_lane(
            ctx,
            reason="sequencer_market_refresh",
            source="single_agent_sequencer",
        ):
            yield event

    async def _analysis_stage(self) -> AsyncGenerator[Dict[str, Any], None]:
        state = self._sequencer_state
        if state is None:
            raise RuntimeError("Sequencer state not initialized")
        ctx = state.ctx
        registry = state.registry
        executed = state.executed
        tool_state = state.tool_state
        try:
            if state.stock_only_run:
                ctx.reused_stock = False
                if tool_state and tool_state.get("active", False):
                    async for tool_event in self._planner._drain_tool_state_async(tool_state, ctx):
                        yield tool_event
                else:
                    ad_hoc_runtime = self._planner._start_tool_parallelism(
                        ctx,
                        adapters=(StockTrackerAdapter(),),
                        concurrency_override=1,
                    )
                    ad_hoc_state = {"queue": ad_hoc_runtime.queue, "active": True, "runtime": ad_hoc_runtime}
                    try:
                        async for tool_event in self._planner._drain_tool_state_async(ad_hoc_state, ctx):
                            yield tool_event
                    finally:
                        await ad_hoc_runtime.close()
                await self._planner._persist_session_state(ctx, record_artifacts=True)
                analysis_event = _build_reused_analysis_event(self.flow_mode, ctx)
                if analysis_event:
                    yield self._planner._annotate_revision(analysis_event, ctx)
                banner_config = FOLLOW_UP_BANNERS.get(ctx.follow_up_route, FOLLOW_UP_BANNERS[FollowUpRoute.FULL_PIPELINE])
                banner_event = EventEmitter.progress("follow_up_route", banner_config["message"])
                banner_event["data"]["route"] = ctx.follow_up_route.value
                banner_event["data"]["ts"] = datetime.utcnow().isoformat()
                yield self._planner._annotate_revision(banner_event, ctx)
                planner_payload = _build_planner_result_payload(ctx)
                result_event = EventEmitter.result("planner_result", planner_payload)
                result_event["event"] = "planner_result"
                result_event["data"]["ts"] = datetime.utcnow().isoformat()
                yield self._planner._annotate_revision(result_event, ctx)
                total_elapsed = int((time.time() - ctx.workflow_start) * 1000)
                workflow_complete = EventEmitter.result("workflow_complete", {"total_elapsed_ms": total_elapsed})
                workflow_complete["event"] = "workflow_complete"
                workflow_complete["data"]["ts"] = datetime.utcnow().isoformat()
                yield self._planner._annotate_revision(workflow_complete, ctx)
                return

            if getattr(ctx, "halted", False):
                return

            async for event in stream_chart_lane(
                self._planner,
                ctx=ctx,
                registry=registry,
                executed=executed,
                tool_state=tool_state,
                run_chart_lane=state.run_chart_lane,
            ):
                yield event

            async for event in stream_analysis_lane(
                self._planner,
                ctx=ctx,
                registry=registry,
                executed=executed,
                tool_state=tool_state,
                mode_config=state.mode_config,
            ):
                yield event
        finally:
            if state.tool_runtime:
                await state.tool_runtime.close()
                state.tool_runtime = None

    async def _agent_run_stage(self) -> AsyncGenerator[Dict[str, Any], None]:
        state = self._sequencer_state
        if state is None:
            raise RuntimeError("Sequencer state not initialized")
        ctx = state.ctx
        session_id = ctx.session_id or state.session_id or str(uuid.uuid4())
        ctx.session_id = session_id
        query = ctx.query or state.query

        lane_states = getattr(state, "lane_states", None)
        if lane_states is None:
            lane_states = {}
            state.lane_states = lane_states

        queue: "asyncio.Queue[Optional[Dict[str, Any]]]" = asyncio.Queue()
        run_context = _SingleAgentRunContext(
            controller=self,
            session_id=session_id,
            query=query,
            queue=queue,
            revision_directive=self._revision_directive if self._agentic_revision_mode else None,
        )
        run_config = RunConfig(
            model=self._agent_model,
            trace_id=str(uuid.uuid4()),
        )
        run_context.trace_id = run_config.trace_id
        agent_task = asyncio.create_task(
            Runner.run(
                self._agent,
                input=query,
                context=run_context,
                max_turns=self._max_turns,
                run_config=run_config,
            )
        )

        async def _drain_queue() -> AsyncGenerator[Dict[str, Any], None]:
            summary_emitted = False
            try:
                while True:
                    if agent_task.done() and queue.empty():
                        break
                    try:
                        event = await asyncio.wait_for(queue.get(), timeout=0.1)
                    except asyncio.TimeoutError:
                        continue
                    if event is None:
                        continue
                    yield event
            finally:
                run_exc: Optional[BaseException] = None
                try:
                    run_result = await asyncio.shield(agent_task)
                except BaseException as exc:  # pragma: no cover - propagate agent failure
                    run_exc = exc
                    run_result = None  # type: ignore[assignment]

                if run_exc is not None:
                    raise run_exc
                try:
                    await self._persist_agent_run_metadata(
                        run_context=run_context,
                        run_config=run_config,
                        run_result=run_result,
                        ctx=ctx,
                    )
                except Exception:  # pragma: no cover - defensive logging
                    logger.exception("Failed to persist agent run metadata")

                artifacts = self._planner.latest_artifacts()
                if artifacts:
                    analysis_payload: Dict[str, Any] = {}
                    if run_result and isinstance(getattr(run_result, "final_output", None), Mapping):
                        analysis_payload = dict(run_result.final_output)  # type: ignore[arg-type]
                    cohesive_payload = _build_single_agent_cohesive_payload(
                        analysis_payload,
                        artifacts,
                        default_manifest=self.planner_tool_manifest,
                    )
                    if cohesive_payload:
                        try:
                            sanitized_payload = sanitize_for_json(cohesive_payload)
                        except Exception:  # pragma: no cover - defensive
                            sanitized_payload = cohesive_payload
                        if isinstance(sanitized_payload, Mapping):
                            sanitized_payload = dict(sanitized_payload)
                        final_event = {
                            "event": "analysis_bundle",
                            "data": {
                                "analysis_bundle": sanitized_payload,
                                "session_id": session_id,
                                "flow": self.flow_label,
                                "query": query,
                            },
                        }
                        yield apply_mode_metadata(final_event, self.flow_mode)

                total_elapsed = int((time.time() - ctx.workflow_start) * 1000)
                workflow_complete = EventEmitter.result(
                    "workflow_complete",
                    {"total_elapsed_ms": total_elapsed},
                )
                workflow_complete["event"] = "workflow_complete"
                workflow_complete["data"]["ts"] = datetime.utcnow().isoformat()
                annotated_complete = self._planner._annotate_revision(workflow_complete, ctx)
                yield apply_mode_metadata(annotated_complete, self.flow_mode)

        async for evt in _drain_queue():
            yield evt
    def prime_with_snapshot(self, snapshot: Optional[SessionStateSnapshot]) -> None:
        self._planner.prime_with_snapshot(snapshot)

    def set_revision_directive(self, directive: Optional["RevisionDirective"]) -> None:
        self._revision_directive = directive
        self._agentic_revision_mode = bool(directive.agentic if directive else False)
        if directive and getattr(directive, "targets", None):
            normalized = {
                target
                for target in (
                    self._normalize_lane_target(entry) for entry in directive.targets
                )
                if target
            }
            self._agentic_lane_targets = normalized
        else:
            self._agentic_lane_targets = set()
        self._planner.set_revision_directive(directive)
        if self._agentic_revision_mode and self._agentic_lane_targets:
            self._planner.set_revision_targets(self._agentic_lane_targets)
        elif not self._agentic_revision_mode:
            self._planner.set_revision_targets(set())
        # Re-evaluate follow-up routing so agentic revisions can opt into reuse plans.
        self.set_follow_up_route(self.follow_up_route)

    def set_lane_refresh_requirements(self, requirements: Optional[Mapping[str, Any]]) -> None:
        self._planner.set_lane_refresh_requirements(requirements)

    def set_analysis_refresh_mode(self, mode: Optional[str]) -> None:
        self._planner.set_analysis_refresh_mode(mode)

    @classmethod
    def _lane_for_tool(cls, tool_name: Optional[str]) -> Optional[str]:
        if not tool_name:
            return None
        return cls.LANE_TOOL_LOOKUP.get(str(tool_name).strip().lower())

    @staticmethod
    def _normalize_tool_key(name: Optional[str]) -> Optional[str]:
        if not name:
            return None
        key = str(name).strip().lower()
        return key or None

    def _resolve_registry_name(self, tool_name: Optional[str]) -> Optional[str]:
        key = self._normalize_tool_key(tool_name)
        if not key:
            return None
        return self.TOOL_METADATA_ALIAS_MAP.get(key, key)

    def _resolve_alias_for_registry(self, registry_name: Optional[str]) -> Optional[str]:
        key = self._normalize_tool_key(registry_name)
        if not key:
            return None
        for alias, registry in self.TOOL_METADATA_ALIAS_MAP.items():
            if registry == key:
                return alias
        return None

    def _record_tool_attempt(self, registry_name: Optional[str]) -> int:
        key = self._normalize_tool_key(registry_name)
        if not key:
            return 1
        attempt = self._tool_attempts.get(key, 0) + 1
        self._tool_attempts[key] = attempt
        return attempt

    def get_tool_attempt(self, tool_name: Optional[str]) -> int:
        registry_name = self._resolve_registry_name(tool_name)
        key = self._normalize_tool_key(registry_name)
        if not key:
            return 0
        return self._tool_attempts.get(key, 0)

    def get_retry_count(self, tool_name: Optional[str]) -> int:
        attempt = self.get_tool_attempt(tool_name)
        return max(attempt - 1, 0)

    def _build_function_tool(self, definition: PlannerToolDefinition) -> FunctionTool:
        params_schema = definition.parameters_schema or {"type": "object", "properties": {}}

        async def _on_invoke(tool_ctx: ToolContext[Any], args_json: str) -> str:
            run_context = tool_ctx.context
            if not isinstance(run_context, _SingleAgentRunContext):
                raise RuntimeError("Single agent run context missing for tool invocation")
            try:
                parsed_args = json.loads(args_json) if args_json else {}
                if not isinstance(parsed_args, dict):
                    raise ValueError("arguments must be an object")
            except Exception as exc:  # pragma: no cover - defensive logging
                logger.error("Failed to parse tool arguments for %s: %s", definition.name, exc)
                parsed_args = {}
                error_payload = {
                    "status": "error",
                    "error_code": "INVALID_TOOL_ARGS",
                    "summary": f"Unable to parse arguments for {definition.name}",
                }
                return json.dumps(error_payload)

            tool_result = await self._execute_planner_tool_for_agent(
                definition=definition,
                run_context=run_context,
                tool_ctx=tool_ctx,
                tool_args=parsed_args,
            )
            return json.dumps(tool_result)

        return FunctionTool(
            name=definition.name,
            description=definition.description,
            params_json_schema=sanitize_for_json(params_schema) if params_schema else {},
            on_invoke_tool=_on_invoke,
            strict_json_schema=True,
        )

    async def _execute_planner_tool_for_agent(
        self,
        *,
        definition: PlannerToolDefinition,
        run_context: _SingleAgentRunContext,
        tool_ctx: ToolContext[Any],
        tool_args: Mapping[str, Any],
    ) -> Dict[str, Any]:
        session_id = run_context.session_id
        if not session_id:
            session_id = str(uuid.uuid4())
            run_context.session_id = session_id

        hooks = _SingleAgentToolHooks(self, session_id=session_id)
        resolved_query = run_context.query or tool_args.get("query") or ""
        ctx = await self._planner.initialize_context(resolved_query, session_id=session_id)
        revision_directive = run_context.revision_directive or self._revision_directive
        if revision_directive is not None:
            ctx.revision_directive = revision_directive  # type: ignore[attr-defined]
            ctx.agentic_revision_mode = bool(getattr(revision_directive, "agentic", False))
            ctx.revision_targets = set(getattr(revision_directive, "targets", []))
            focus_hint = getattr(revision_directive, "requested_focus", None) or getattr(
                revision_directive, "raw_text", None
            )
            if focus_hint:
                ctx.revision_focus = focus_hint
            if getattr(revision_directive, "search_topics", None):
                ctx.revision_search_topics = list(revision_directive.search_topics)

        registry_name = self._resolve_registry_name(definition.name)
        attempt = self._record_tool_attempt(registry_name or definition.name)
        normalized_key = self._normalize_tool_key(registry_name or definition.name) or definition.name
        run_context.tool_attempts[normalized_key] = attempt
        run_context.tool_attempts[definition.name] = attempt

        async def _stream() -> AsyncGenerator[Dict[str, Any], None]:
            async for event in self._registry.invoke(
                definition.name,
                self._planner._pipeline,
                ctx,
                **dict(tool_args),
            ):
                yield event

        last_event: Optional[Dict[str, Any]] = None
        try:
            async for event in self._forward_with_hooks(_stream(), hooks, session_id):
                last_event = event
                annotated = self._attach_retry_metadata(event, registry_name, attempt)
                await run_context.queue.put(annotated)
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.exception("Planner tool %s failed: %s", definition.name, exc)
            return {
                "status": "error",
                "error_code": getattr(exc, "code", "TOOL_FAILURE"),
                "summary": f"{definition.name} failed: {exc}",
            }

        receipt = self._extract_tool_receipt(ctx, definition.name)
        status = "completed"
        error_code = None
        if receipt.get("error"):
            status = "error"
            error_code = receipt.get("error")
        summary = self._summarize_tool_result(definition.name, receipt, last_event)
        result_payload: Dict[str, Any] = {
            "status": status,
            "summary": summary,
            "receipt": receipt,
        }
        if error_code:
            result_payload["error_code"] = error_code
        artifacts = self._collect_artifacts_snapshot(ctx)
        if artifacts:
            result_payload["artifacts"] = artifacts
        if definition.response_schema:
            result_payload["expected_schema"] = definition.response_schema
        result_payload["attempt"] = attempt
        result_payload["retry_count"] = max(attempt - 1, 0)
        if attempt > 1:
            result_payload["retry"] = True
        retry_count = result_payload["retry_count"]
        run_context.tool_retry_counts[normalized_key] = retry_count
        run_context.tool_retry_counts[definition.name] = retry_count
        try:
            serialized_receipt = sanitize_for_json(receipt) if receipt else {}
        except Exception:  # pragma: no cover - defensive
            serialized_receipt = dict(receipt)
        run_context.tool_receipts[normalized_key] = serialized_receipt
        run_context.tool_receipts[definition.name] = serialized_receipt
        return sanitize_for_json(result_payload)

    def _extract_tool_receipt(self, ctx: PlannerPhaseContext, tool_name: str) -> Dict[str, Any]:
        receipts = getattr(ctx, "tool_receipts", {}) or {}
        receipt = receipts.get(tool_name)
        if isinstance(receipt, ToolInvocationReceipt):
            return receipt.to_dict()
        if isinstance(receipt, Mapping):
            try:
                return sanitize_for_json(dict(receipt))
            except Exception:  # pragma: no cover - defensive
                return dict(receipt)
        return {}

    @staticmethod
    def _summarize_tool_result(
        tool_name: str,
        receipt_payload: Mapping[str, Any],
        last_event: Optional[Mapping[str, Any]],
    ) -> str:
        summary = ""
        metadata = receipt_payload.get("metadata") if isinstance(receipt_payload, Mapping) else None
        if isinstance(metadata, Mapping):
            summary = str(metadata.get("summary") or metadata.get("message") or "").strip()
        if not summary:
            if isinstance(last_event, Mapping):
                data = last_event.get("data")
                if isinstance(data, Mapping):
                    summary = str(
                        data.get("summary") or data.get("message") or data.get("status") or ""
                    ).strip()
        if not summary:
            summary = f"{tool_name} completed"
        return summary

    @staticmethod
    def _collect_artifacts_snapshot(ctx: PlannerPhaseContext) -> Dict[str, Any]:
        artifacts = getattr(ctx, "artifacts", None)
        if not artifacts:
            return {}
        if hasattr(artifacts, "to_dict"):
            try:
                return sanitize_for_json(artifacts.to_dict())
            except Exception:  # pragma: no cover - defensive
                pass
        try:
            return sanitize_for_json(dict(artifacts))
        except Exception:  # pragma: no cover - defensive
            return {}

    @staticmethod
    def _normalize_lane_target(lane: Optional[str]) -> Optional[str]:
        if not lane:
            return None
        normalized = str(lane).strip().lower()
        alias_map = {
            "stocks": "market",
            "stock": "market",
            "prices": "market",
            "price": "market",
            "charts": "chart",
            "analysis_revision": "analysis",
            "narrative": "analysis",
        }
        return alias_map.get(normalized, normalized)

    @staticmethod
    def _receipt_age_seconds(receipt: Optional[ToolInvocationReceipt]) -> Optional[float]:
        if not receipt or not getattr(receipt, "timestamp", None):
            return None
        try:
            recorded = datetime.fromisoformat(receipt.timestamp)
        except ValueError:
            return None
        delta = datetime.utcnow() - recorded
        return max(delta.total_seconds(), 0.0)

    def _receipt_is_fresh(self, receipt: Optional[ToolInvocationReceipt]) -> bool:
        if not receipt:
            return False
        if str(getattr(receipt, "status", "")).lower() not in {"completed", "reused"}:
            return False
        if getattr(receipt, "error", None):
            return False
        age_seconds = self._receipt_age_seconds(receipt)
        if age_seconds is None:
            return False
        return age_seconds <= self.LANE_CACHE_TTL_SECONDS

    def _build_receipt_input_payload(
        self,
        ctx: PlannerPhaseContext,
        lane: str,
        tool_name: str,
        metadata: Optional[Mapping[str, Any]],
    ) -> Dict[str, Any]:
        plan = getattr(ctx, "plan", None) or getattr(ctx, "provisional_plan", None)
        if hasattr(plan, "model_dump"):
            plan_payload = plan.model_dump()
        elif hasattr(plan, "dict"):
            plan_payload = plan.dict()
        else:
            plan_payload = None
        payload: Dict[str, Any] = {
            "query": ctx.query,
            "intent_key": getattr(getattr(ctx, "intent", None), "intent_key", None),
            "lane": lane,
            "tool": tool_name,
            "plan": plan_payload,
            "follow_up_route": getattr(getattr(ctx, "follow_up_route", None), "value", None)
            or getattr(self.follow_up_route, "value", FollowUpRoute.FULL_PIPELINE.value),
        }
        if getattr(ctx, "intent_signature", None) is not None:
            payload["intent_signature"] = ctx.intent_signature
        if metadata and isinstance(metadata, Mapping):
            question_id = metadata.get("question_id")
            if question_id:
                payload["question_id"] = question_id
        return payload

    def _ensure_running_receipt(
        self,
        ctx: PlannerPhaseContext,
        lane: str,
        tool_name: str,
        metadata: Optional[Mapping[str, Any]],
    ) -> None:
        fingerprint = self._build_receipt_input_payload(ctx, lane, tool_name, metadata)
        receipt = ctx.tool_receipts.get(tool_name)
        metadata_dict = dict(metadata) if isinstance(metadata, Mapping) else {}
        metadata_dict.setdefault("lane", lane)
        if receipt:
            receipt.status = "running"
            receipt.reused = False
            receipt.error = None
            receipt.output_hash = None
            receipt.attempts = max(receipt.attempts + 1, 1)
            receipt.timestamp = datetime.utcnow().isoformat()
            if not receipt.input_hash:
                receipt.input_hash = _hash_payload(fingerprint)
            existing_meta = dict(receipt.metadata or {})
            existing_meta.update(metadata_dict)
            receipt.metadata = existing_meta
        else:
            receipt = ToolInvocationReceipt(
                tool=tool_name,
                status="running",
                attempts=1,
                input_hash=_hash_payload(fingerprint),
                metadata=metadata_dict,
            )
        ctx.tool_receipts[tool_name] = receipt

    def _finalize_receipt(
        self,
        ctx: PlannerPhaseContext,
        lane: Optional[str],
        tool_name: str,
        event_data: Mapping[str, Any],
    ) -> None:
        metadata = event_data.get("metadata")
        metadata_dict = dict(metadata) if isinstance(metadata, Mapping) else {}
        if lane:
            metadata_dict.setdefault("lane", lane)
        status_value = str(event_data.get("status") or "").strip().lower()
        normalized_status = (
            "completed"
            if status_value in {"completed", "complete", "success"}
            else status_value or "unknown"
        )
        receipt = ctx.tool_receipts.get(tool_name)
        if receipt:
            receipt.status = normalized_status
            receipt.reused = False
            existing_meta = dict(receipt.metadata or {})
            existing_meta.update(metadata_dict)
            receipt.metadata = existing_meta
        else:
            fingerprint = self._build_receipt_input_payload(ctx, lane or "unknown", tool_name, metadata_dict)
            receipt = ToolInvocationReceipt(
                tool=tool_name,
                status=normalized_status,
                attempts=1,
                input_hash=_hash_payload(fingerprint),
                metadata=metadata_dict,
            )
        receipt.elapsed_ms = event_data.get("elapsed_ms")
        receipt.error = event_data.get("error")
        payload = event_data.get("payload")
        if payload:
            receipt.output_hash = _hash_payload(payload)
        ctx.tool_receipts[tool_name] = receipt

    def _process_tool_parallel_event(
        self,
        ctx: PlannerPhaseContext,
        event: Dict[str, Any],
        lane_hint: Optional[str] = None,
    ) -> None:
        if not isinstance(event, dict):
            return
        event_type = event.get("event")
        if event_type not in {"tool_parallel_start", "tool_parallel_result"}:
            return
        data = event.setdefault("data", {})
        if event_type == "tool_parallel_start":
            tools_meta = data.get("tools") or []
            for tool_meta in tools_meta:
                if isinstance(tool_meta, Mapping):
                    tool_name = tool_meta.get("name") or tool_meta.get("tool")
                else:
                    tool_name = None
                if not tool_name:
                    continue
                lane = lane_hint or self._lane_for_tool(tool_name)
                if not lane:
                    continue
                meta = dict(tool_meta) if isinstance(tool_meta, Mapping) else {}
                meta.setdefault("lane", lane)
                self._ensure_running_receipt(ctx, lane, tool_name, meta)
            return

        tool_name = data.get("tool")
        if not tool_name:
            return
        lane = lane_hint or self._lane_for_tool(tool_name)
        if lane:
            data.setdefault("lane", lane)
            parallel_group = "single_agent_fanout"
            if lane == "market":
                parallel_group = "single_agent_market"
            elif lane == "web":
                parallel_group = "single_agent_web"
            data.setdefault("parallel_group", parallel_group)
            data.setdefault("reused", False)
        self._finalize_receipt(ctx, lane, tool_name, data)

    def _apply_lane_transition_event(
        self,
        lane_states: Dict[str, str],
        event: Dict[str, Any],
        *,
        revision_targets: Set[str],
    ) -> None:
        if not isinstance(event, dict) or event.get("event") != "planner_lane_transition":
            return
        data = event.get("data") or {}
        lane = str(data.get("lane") or "").strip().lower()
        if not lane or lane not in lane_states:
            return
        status = str(data.get("status") or "").strip().lower()
        success_flag = bool(data.get("success", True))
        reused_flag = bool(data.get("reused"))
        if status == LANE_STATUS_RUNNING:
            lane_states[lane] = "running"
            return
        if status == LANE_STATUS_SKIPPED:
            lane_states[lane] = "reused"
            return
        if status == LANE_STATUS_FAILED or not success_flag:
            lane_states[lane] = "error"
            return
        if status == LANE_STATUS_COMPLETED:
            if reused_flag or (lane not in revision_targets and lane != "sql"):
                lane_states[lane] = "reused"
            else:
                lane_states[lane] = "fresh"

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
            ctx.reused_web = bool(reused)
        elif lane == "market":
            ctx.reused_stock = bool(reused)

    async def _persist_agent_run_metadata(
        self,
        *,
        run_context: _SingleAgentRunContext,
        run_config: RunConfig,
        run_result: Optional[Any],
        ctx: PlannerPhaseContext,
    ) -> None:
        repository = get_session_state_repository()
        session_id = run_context.session_id or ctx.session_id
        if repository is None or session_id is None:
            return
        snapshot = await repository.load(session_id)
        if snapshot is None:
            snapshot = SessionStateSnapshot(session_id=session_id)
        run_id = (
            getattr(run_result, "id", None)
            or getattr(run_result, "run_id", None)
            or getattr(run_result, "session_id", None)
            or run_context.run_id
            or run_context.trace_id
            or run_config.trace_id
        )
        run_context.run_id = run_id
        snapshot.record_agent_run(
            run_id=run_id,
            trace_id=run_context.trace_id or run_config.trace_id,
            model=self._agent_model,
            tool_attempts=run_context.tool_attempts,
            retry_counts=run_context.tool_retry_counts,
            receipts=run_context.tool_receipts,
        )
        await repository.save(snapshot)
        telemetry.agent_run(
            session_id=session_id,
            flow=self.flow_label,
            run_id=run_id,
            trace_id=run_context.trace_id or run_config.trace_id,
            model=self._agent_model,
            tool_attempts=run_context.tool_attempts,
            retry_counts=run_context.tool_retry_counts,
        )

    def _emit_lane_summary(self, lane_states: Dict[str, str]) -> Dict[str, Any]:
        normalized_states = dict(lane_states)
        if self.follow_up_route == FollowUpRoute.REUSE_SQL:
            for lane in ("sql", "analysis", "market", "web"):
                state = normalized_states.get(lane)
                if state in {"fresh", "running", "pending", "queued", "missing"}:
                    normalized_states[lane] = "reused"

        payload = {
            "lane_summary": normalized_states,
            "parallel_group": "single_agent_fanout",
            "ts": datetime.utcnow().isoformat(),
            "flow_mode": self.flow_mode.value,
        }
        rerun_lanes = [
            lane for lane, status in normalized_states.items() if status in {"fresh", "running", "pending", "queued"}
        ]
        reuse_lanes = [lane for lane, status in normalized_states.items() if status in {"reused", "cached"}]
        payload["rerun_scope"] = {
            "rerun": rerun_lanes,
            "reuse": reuse_lanes,
            "route": self.follow_up_route.value,
        }
        if "chart" in rerun_lanes and "sql" in reuse_lanes:
            payload["decision"] = "chart_revision"
        elif rerun_lanes:
            payload["decision"] = "fresh_execution"
        else:
            payload["decision"] = "reuse_snapshot"
        return self._planner._annotate({"event": "agent_decision", "data": payload})

    def _initial_lane_states(self) -> Dict[str, str]:
        if self._agentic_revision_mode and self._agentic_lane_targets:
            targets = self._agentic_lane_targets
            return {
                "sql": "queued" if "sql" in targets else "reused",
                "chart": "queued" if "chart" in targets else "reused",
                "analysis": "queued" if "analysis" in targets else "reused",
                "market": "queued" if "market" in targets else "reused",
                "web": "queued" if "web" in targets else "reused",
            }
        if self.follow_up_route == FollowUpRoute.REUSE_SQL:
            return {
                "sql": "reused",
                "chart": "reused",
                "analysis": "reused",
                "market": "skipped",
                "web": "skipped",
            }
        if self.follow_up_route == FollowUpRoute.STOCK_ONLY:
            return {
                "sql": "reused",
                "chart": "reused",
                "analysis": "reused",
                "market": "pending",
                "web": "reused",
            }
        return {
            "sql": "pending",
            "chart": "queued",
            "analysis": "queued",
            "market": "skipped",
            "web": "skipped",
        }

    def _update_lane_state_from_event(
        self,
        lane_states: Dict[str, str],
        event: Dict[str, Any],
        *,
        revision_targets: Set[str],
    ) -> None:
        name = event.get("event") or ""
        data = event.get("data") or {}
        lane = data.get("lane")
        reused = bool(data.get("reused"))
        schedule_stage = data.get("schedule_stage")

        if name == "follow_up_route":
            route_value = data.get("route") or data.get("follow_up_route")
            if isinstance(route_value, str):
                try:
                    self.follow_up_route = FollowUpRoute(route_value)
                except ValueError:
                    pass
        elif name == "revision_request":
            lanes = data.get("lanes") or []
            revision_targets.clear()
            revision_targets.update(str(l).strip().lower() for l in lanes if l)
            for tracked_lane in ("sql", "chart", "analysis"):
                if tracked_lane not in revision_targets:
                    lane_states[tracked_lane] = "reused"
        elif name in {"sql_ready", "sql_revision_ready"}:
            lane_states["sql"] = "reused" if reused else "fresh"
        elif name in {"chart_ready", "chart_revision_ready"}:
            lane_states["chart"] = "reused" if reused else "fresh"
        elif name in {"analysis_ready", "analysis_revision_ready", "analysis_complete"}:
            lane_states["analysis"] = "reused" if reused else "fresh"
        elif name in {"stock_ready", "stock_revision_ready"}:
            lane_states["market"] = "reused" if reused else "fresh"
        elif name in {"web_ready", "web_revision_ready"}:
            lane_states["web"] = "reused" if reused else "fresh"
        elif lane in lane_states and name == "tool_parallel_result":
            status = str(data.get("status") or "").lower()
            if status in {"completed", "complete", "success"}:
                lane_states[str(lane)] = "fresh"
            elif status in {"cached", "reused"} or reused:
                lane_states[str(lane)] = "reused"
        elif lane in lane_states and schedule_stage in {"hedged_accessories"}:
            lane_states[str(lane)] = "reused" if reused else "fresh"

        if name == "workflow_complete":
            for tracked_lane in ("sql", "chart", "analysis"):
                lane_states.setdefault(tracked_lane, "reused" if tracked_lane not in revision_targets else "fresh")

    def _should_emit_lane_summary_before(self, event: Dict[str, Any]) -> bool:
        name = event.get("event") or ""
        if name in {
            "chart_progress",
            "chart_generated",
            "chart_ready",
            "chart_revision_ready",
            "analysis_progress",
            "analysis_ready",
            "analysis_revision_ready",
            "analysis_complete",
            "planner_result",
            "workflow_complete",
        }:
            return True
        schedule_stage = (event.get("data") or {}).get("schedule_stage")
        if schedule_stage in {"chart", "analysis"}:
            return True
        return False

    def _resolve_agentic_route(self, candidate: FollowUpRoute) -> FollowUpRoute:
        if not (self._agentic_revision_mode and self._agentic_lane_targets):
            return candidate
        if "sql" in self._agentic_lane_targets:
            return candidate
        if self._agentic_lane_targets == {"market"}:
            return FollowUpRoute.STOCK_ONLY
        return FollowUpRoute.REUSE_SQL

    def set_follow_up_route(self, route: FollowUpRoute) -> None:
        resolved = self._resolve_agentic_route(route)
        self.follow_up_route = resolved
        self._planner.set_follow_up_route(resolved)

    def set_revision_targets(self, targets: Iterable[str]) -> None:
        self._planner.set_revision_targets(targets)

    async def _forward_with_hooks(
        self,
        stream: AsyncGenerator[Dict[str, Any], None],
        hooks: _SingleAgentToolHooks,
        session_id: Optional[str],
    ) -> AsyncGenerator[Dict[str, Any], None]:
        hook_ctx: Dict[str, Any] = {"session_id": session_id}
        try:
            async for start_event in hooks.on_flow_start(hook_ctx):
                yield start_event
            async for event in stream:
                async for pre_event in hooks.before_event(hook_ctx, event):
                    yield pre_event
                yield event
                if event.get("event") == "session_started":
                    data = event.get("data") or {}
                    hook_ctx["session_id"] = data.get("session_id", hook_ctx.get("session_id"))
                async for post_event in hooks.after_event(hook_ctx, event):
                    yield post_event
        except BaseException as exc:
            async for end_event in hooks.on_flow_end(hook_ctx, error=exc):
                yield end_event
            raise
        else:
            async for end_event in hooks.on_flow_end(hook_ctx):
                yield end_event

    async def _resolve_session_query(self, session_id: str) -> str:
        repository = get_session_state_repository()
        snapshot = await repository.load(session_id)
        if snapshot and snapshot.last_query:
            return snapshot.last_query
        return ""

    async def _invoke_planner_tool(
        self,
        tool_name: str,
        *,
        session_id: str,
        query: Optional[str],
        hooks: _SingleAgentToolHooks,
        revision_directive: Optional["RevisionDirective"] = None,
        **kwargs: Any,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        resolved_query = query if query is not None else await self._resolve_session_query(session_id)
        ctx = await self._planner.initialize_context(resolved_query or "", session_id=session_id)
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
        registry = self._registry
        tool_stream = registry.invoke(tool_name, self._planner._pipeline, ctx, **kwargs)
        async for event in self._forward_with_hooks(tool_stream, hooks, session_id):
            yield event

    async def events(
        self,
        query: str,
        session_id: Optional[str] = None,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        hooks = _SingleAgentToolHooks(self, session_id=session_id)
        stream = self._agentic_event_stream(query, session_id=session_id)
        async for event in self._forward_with_hooks(stream, hooks, session_id):
            yield event

    async def _agentic_event_stream(
        self,
        query: str,
        session_id: Optional[str],
    ) -> AsyncGenerator[Dict[str, Any], None]:
        lane_states = self._initial_lane_states()
        revision_targets: Set[str] = (
            set(self._agentic_lane_targets) if self._agentic_revision_mode else set()
        )
        self._tool_attempts.clear()
        summary_emitted = False
        if self._agentic_revision_mode and self._agentic_lane_targets:
            summary_event = self._emit_lane_summary(lane_states)
            if summary_event:
                summary_event.setdefault("data", {})
                summary_event["data"]["mode"] = "agentic_revision"
                yield summary_event
                summary_emitted = True

        state = await self._prepare_sequencer_state(query, session_id=session_id)
        state.lane_states = lane_states  # type: ignore[attr-defined]
        use_agent = self._agents_enabled and self._agent is not None

        intent_runner = self._intent_stage
        sql_runner = self._sql_stage
        web_runner = self._web_stage
        market_runner = self._market_stage
        analysis_runner = self._analysis_stage

        if use_agent:
            sql_runner = self._agent_run_stage
            web_runner = self._noop_stage
            market_runner = self._noop_stage
            analysis_runner = self._noop_stage

        orchestrator = PlannerOrchestratorAdapter(
            intent_runner=intent_runner,
            sql_runner=sql_runner,
            web_runner=web_runner,
            market_runner=market_runner,
            analysis_runner=analysis_runner,
            metadata={
                "flow": self.flow_label,
                "flow_mode": self.flow_mode.value,
            },
            optional_lanes=("web", "market"),
            lane_complete_callback=self._handle_lane_complete,
        )
        sequencer = PlannerSequencer(
            orchestrator,
            lane_refresh_required=dict(getattr(state.ctx, "lane_refresh_required", {}) or {}),
        )

        def _on_lane_transition(event: Dict[str, Any]) -> None:
            self._apply_lane_transition_event(
                lane_states,
                event,
                revision_targets=revision_targets,
            )

        sequencer.event_bus.subscribe(_on_lane_transition)

        try:
            async for event in sequencer.run():
                self._update_lane_state_from_event(
                    lane_states, event, revision_targets=revision_targets
                )
                if not summary_emitted and self._should_emit_lane_summary_before(event):
                    summary_event = self._emit_lane_summary(lane_states)
                    if summary_event:
                        yield summary_event
                    summary_emitted = True
                yield event
        finally:
            self._sequencer_state = None

        if not summary_emitted and any(
            state not in {"pending", "queued", "skipped"} for state in lane_states.values()
        ):
            summary_event = self._emit_lane_summary(lane_states)
            if summary_event:
                yield summary_event

    async def chart_revision(
        self,
        *,
        session_id: str,
        patch: Dict[str, Any],
        reason: Optional[str] = None,
        source: Optional[str] = None,
        query: Optional[str] = None,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        self.set_follow_up_route(FollowUpRoute.REUSE_SQL)
        hooks = _SingleAgentToolHooks(self, session_id=session_id)
        async for event in self._invoke_planner_tool(
            "chart_revision",
            session_id=session_id,
            query=query,
            hooks=hooks,
            patch=patch,
            reason=reason,
            source=source,
        ):
            yield event

    async def apply_chart_revision(
        self,
        *,
        session_id: str,
        patch: Dict[str, Any],
        reason: Optional[str] = None,
        source: Optional[str] = None,
        query: Optional[str] = None,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        async for event in self.chart_revision(
            session_id=session_id,
            patch=patch,
            reason=reason,
            source=source,
            query=query,
        ):
            yield event

    async def run_web_refresh(
        self,
        *,
        session_id: str,
        query: Optional[str] = None,
        reason: Optional[str] = None,
        source: Optional[str] = None,
        revision_directive: Optional["RevisionDirective"] = None,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        hooks = _SingleAgentToolHooks(self, session_id=session_id)
        ctx = await self._planner.initialize_context(query or "", session_id=session_id)
        if revision_directive is not None:
            ctx.revision_directive = revision_directive  # type: ignore[attr-defined]
        directive = getattr(ctx, "revision_directive", None)
        if directive and getattr(directive, "search_topics", None):
            ctx.revision_search_topics = list(directive.search_topics)
        _reset_revision_accessories(ctx, {"web"})

        async def _stream() -> AsyncGenerator[Dict[str, Any], None]:
            async for event in self._planner.invoke_tool(
                "web_refresh",
                ctx,
                reason=reason,
                source=source,
            ):
                yield event

        async for event in self._forward_with_hooks(_stream(), hooks, session_id):
            yield event

    async def run_market_refresh(
        self,
        *,
        session_id: str,
        query: Optional[str] = None,
        reason: Optional[str] = None,
        source: Optional[str] = None,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        hooks = _SingleAgentToolHooks(self, session_id=session_id)
        ctx = await self._planner.initialize_context(query or "", session_id=session_id)
        _reset_revision_accessories(ctx, {"market"})

        async def _stream() -> AsyncGenerator[Dict[str, Any], None]:
            async for event in self._planner.invoke_tool(
                "market_refresh",
                ctx,
                reason=reason,
                source=source,
            ):
                yield event

        async for event in self._forward_with_hooks(_stream(), hooks, session_id):
            yield event

    async def run_analysis_refresh(
        self,
        *,
        session_id: str,
        query: str,
        requested_focus: Optional[str] = None,
        revision_directive: Optional["RevisionDirective"] = None,
        reason: Optional[str] = None,
        source: Optional[str] = None,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        hooks = _SingleAgentToolHooks(self, session_id=session_id)

        def _apply_revision_context(ctx_obj: Any) -> None:
            if revision_directive is not None:
                ctx_obj.revision_directive = revision_directive  # type: ignore[attr-defined]
                ctx_obj.agentic_revision_mode = bool(getattr(revision_directive, "agentic", False))
                ctx_obj.revision_targets = set(getattr(revision_directive, "targets", []))
            if requested_focus:
                setattr(ctx_obj, "revision_focus", requested_focus)
            directive_topics = getattr(getattr(ctx_obj, "revision_directive", None), "search_topics", None)
            if directive_topics:
                ctx_obj.revision_search_topics = list(directive_topics)

        ctx = await self._planner.initialize_context(query or "", session_id=session_id)
        _apply_revision_context(ctx)
        ctx.reused_analysis = False
        ctx.web_ready_emitted = False
        _reset_revision_accessories(ctx, {"web", "market"})
        sql_artifact = getattr(ctx.artifacts, "sql_generation", None)
        analysis_artifact = getattr(ctx.artifacts, "analysis", None)
        if not sql_artifact or not getattr(sql_artifact, "sql", None) or analysis_artifact is None:
            ctx.analysis_refresh_mode = "full"
            refresh_flags = dict(getattr(ctx, "lane_refresh_required", {}) or {})
            refresh_flags["analysis"] = True
            refresh_flags["web"] = True
            ctx.lane_refresh_required = refresh_flags
            async for event in self.analysis_revision(
                session_id=session_id,
                analysis=requested_focus or (analysis_artifact.analysis_text if analysis_artifact else None),
                reason=reason,
                source=source,
                query=query,
                revision_directive=revision_directive,
                refresh_web=True,
            ):
                yield event
            return

        web_ready_seen = False
        web_failure_reason: Optional[str] = None
        async for event in self.run_web_refresh(
            session_id=session_id,
            query=query,
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
            confirmation = EventEmitter.status(
                "web_revision_ready",
                "Web context refreshed for analysis revision",
            )
            confirmation.setdefault("data", {})
            confirmation["data"].update(
                {
                    "lane": "web",
                    "revision": True,
                    "source": "fresh_revision",
                    "from_cache": False,
                    "reason": "fresh_revision",
                }
            )
            annotated_confirmation = apply_mode_metadata(confirmation, self.flow_mode)
            annotated_confirmation["data"]["follow_up_route"] = self.follow_up_route.value
            yield annotated_confirmation

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
            annotated_warning = apply_mode_metadata(warning_event, self.flow_mode)
            annotated_warning["data"]["follow_up_route"] = self.follow_up_route.value
            yield annotated_warning

        ctx = await self._planner.initialize_context(query or "", session_id=session_id)
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

        async for event in self.analysis_revision(
            session_id=session_id,
            analysis=analysis_payload,
            reason=reason,
            source=source or "fresh_revision",
            query=query,
            revision_directive=revision_directive,
        ):
            yield event

    async def analysis_revision(
        self,
        *,
        session_id: str,
        analysis: Optional[str] = None,
        reason: Optional[str] = None,
        source: Optional[str] = None,
        query: Optional[str] = None,
        revision_directive: Optional["RevisionDirective"] = None,
        refresh_web: bool = False,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        hooks = _SingleAgentToolHooks(self, session_id=session_id)
        if refresh_web:
            async for event in self.run_web_refresh(
                session_id=session_id,
                query=query,
                reason=reason,
                source=source or "fresh_revision",
                revision_directive=revision_directive,
            ):
                yield event
        async for event in self._invoke_planner_tool(
            "analysis_revision",
            session_id=session_id,
            query=query,
            hooks=hooks,
            revision_directive=revision_directive,
            analysis=analysis or "",
            reason=reason,
            source=source,
        ):
            yield event

    def get_tool_metadata_for_step(self, step: Optional[str]) -> Optional[Dict[str, Any]]:
        if not step:
            return None
        registry_name = self.TOOL_METADATA_STEP_MAP.get(step)
        if not registry_name:
            return None
        return self._tool_metadata_by_registry.get(registry_name)

    def get_tool_metadata_for_event(self, event_name: Optional[str]) -> Optional[Dict[str, Any]]:
        if not event_name:
            return None
        registry_name = self.TOOL_METADATA_EVENT_MAP.get(event_name)
        if not registry_name:
            return None
        return self._tool_metadata_by_registry.get(registry_name)

    def get_tool_metadata_for_alias(self, alias: Optional[str]) -> Optional[Dict[str, Any]]:
        if not alias:
            return None
        metadata = self.tool_metadata.get(alias)
        if metadata:
            return metadata
        registry_name = self.TOOL_METADATA_ALIAS_MAP.get(alias)
        if registry_name:
            return self._tool_metadata_by_registry.get(registry_name)
        return None



    def _attach_retry_metadata(
        self,
        event: Dict[str, Any],
        tool_name: Optional[str],
        attempt: int,
    ) -> Dict[str, Any]:
        if not isinstance(event, dict):
            return event
        data = event.setdefault("data", {})
        if not isinstance(data, dict):
            return event
        if "attempt" not in data:
            data["attempt"] = attempt
        if "tool_attempt" not in data:
            data["tool_attempt"] = attempt
        retry_count = max(attempt - 1, 0)
        if "retry_count" not in data:
            data["retry_count"] = retry_count
        if "retry" not in data:
            data["retry"] = retry_count > 0
        registry_name = self._resolve_registry_name(tool_name)
        if registry_name and "tool_registry" not in data:
            data["tool_registry"] = registry_name
        alias = self._resolve_alias_for_registry(registry_name)
        if alias and "tool" not in data:
            data["tool"] = alias
        return event

    def latest_artifacts(self):
        return self._planner.latest_artifacts()



