from __future__ import annotations

import asyncio
import contextlib
from datetime import datetime
import copy
import time
import logging
from typing import Any, AsyncGenerator, Dict, Iterable, List, Optional, Set, Tuple, Mapping

from analytics.artifacts.models import PipelineArtifacts
from analytics.core.events import EventEmitter
from analytics.core.telemetry import tool_iteration as log_tool_iteration
from analytics.core.session_state import SessionStateSnapshot, get_session_state_repository
from analytics.validators import sanitize_for_json
from analytics.routing import FollowUpRoute
from .hooks import AnalyticsFlowHooks
from .planner_executor import (
    _cached_event,
    _compose_sql_ready_payload,
    _compose_stock_ready_payload,
    _compose_web_ready_payload,
    _build_analysis_source_summaries,
    ToolInvocationReceipt,
    _hash_payload,
    PlannerPhaseContext,
    PlannerExecutorFlow,
)
from .pipeline_tools import get_planner_tool_registry
from .schedulers import FlowMode, apply_mode_metadata, get_mode_config
from .tooling import StockTrackerAdapter, WebRetrieverAdapter


logger = logging.getLogger(__name__)


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


class MarketQuestionAdapter(StockTrackerAdapter):
    """Stock tracker wrapper that tags outputs for specific market questions."""

    def __init__(self, alias: str, label: str) -> None:
        super().__init__()
        self.name = alias
        self.display_name = label
        self._question_id = alias

    async def execute(self, context):  # type: ignore[override]
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


class _SingleAgentToolHooks(AnalyticsFlowHooks):
    def __init__(self, flow: "SingleAgentController", session_id: Optional[str] = None) -> None:
        self._flow = flow
        self._timers: Dict[str, float] = {}
        self._sql_compile_details: Dict[str, Any] = {}
        self._session_id: Optional[str] = session_id
        self._emitted_cohesive = False
        self._last_analysis_payload: Optional[Dict[str, Any]] = None
        self._final_answer_emitted = False

    async def on_flow_start(self, ctx: Dict[str, Any]) -> AsyncGenerator[Dict[str, Any], None]:
        self._emitted_cohesive = False
        self._last_analysis_payload = None
        self._final_answer_emitted = False
        if ctx.get("session_id") and not self._session_id:
            session = ctx.get("session_id")
            if isinstance(session, str) and session:
                self._session_id = session
        if False:
            yield {}

    async def before_event(self, ctx: Dict[str, Any], event: Dict[str, Any]) -> AsyncGenerator[Dict[str, Any], None]:
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
        reuse_scope = self._flow.follow_up_route == FollowUpRoute.REUSE_SQL
        if reuse_scope:
            # For chart-only revisions we intentionally reuse the existing SQL, stock, and web context,
            # so suppress the generic "Pending lanes" warning and surface a reuse hint instead.
            missing = []
            note = "Chart revision applied. SQL tables, stock telemetry, and market research were reused."
        elif missing:
            readable = ", ".join(human_labels[name] for name in missing)
            note = f"Pending lanes: {readable}. Ask me to rerun those tools when you're ready."
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
    }

    CONCURRENT_LANES: Tuple[str, ...] = ("market", "web")
    LANE_CACHE_TTL_SECONDS: int = 600
    LANE_PARALLEL_GROUPS: Dict[str, str] = {
        "market": "single_agent_market",
        "web": "single_agent_web",
    }
    LANE_CONCURRENCY_LIMITS: Dict[str, int] = {
        # Allow both market research questions plus the stock tracker to execute without serialising.
        "market": 3,
        "web": 1,
    }
    LANE_TOOL_MAP: Dict[str, Tuple[str, ...]] = {
        "market": ("market_question_a", "market_question_b", "stock_tracker"),
        "web": ("web_retriever",),
    }
    LANE_TOOL_LOOKUP: Dict[str, str] = {
        tool.lower(): lane for lane, tools in LANE_TOOL_MAP.items() for tool in tools
    }

    def __init__(self) -> None:
        self._planner = PlannerExecutorFlow(flow_mode=FlowMode.SINGLE_AGENT)
        self.follow_up_route = FollowUpRoute.FULL_PIPELINE
        self._planner.set_follow_up_route(self.follow_up_route)
        self.flow_mode = FlowMode.SINGLE_AGENT
        self.flow_label = "single-agent"
        registry = get_planner_tool_registry()
        self.planner_tool_manifest = registry.describe_tools()
        self._tool_metadata_by_registry = _build_tool_metadata(self.planner_tool_manifest)
        self.tool_metadata: Dict[str, Dict[str, Any]] = {}
        for alias, registry_name in self.TOOL_METADATA_ALIAS_MAP.items():
            metadata = self._tool_metadata_by_registry.get(registry_name)
            if metadata:
                self.tool_metadata[alias] = metadata

    def prime_with_snapshot(self, snapshot: Optional[SessionStateSnapshot]) -> None:
        self._planner.prime_with_snapshot(snapshot)

    @classmethod
    def _lane_for_tool(cls, tool_name: Optional[str]) -> Optional[str]:
        if not tool_name:
            return None
        return cls.LANE_TOOL_LOOKUP.get(str(tool_name).strip().lower())

    @classmethod
    def _lane_tool_names(cls, lane: str) -> Tuple[str, ...]:
        return cls.LANE_TOOL_MAP.get(lane, tuple())

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

    def _mark_lane_reused(self, ctx: PlannerPhaseContext, lane: str) -> None:
        if lane == "market":
            ctx.reused_stock = True
        elif lane == "web":
            ctx.reused_web = True
        for tool_name in self._lane_tool_names(lane):
            receipt = ctx.tool_receipts.get(tool_name)
            if not receipt:
                continue
            receipt.status = "reused"
            receipt.reused = True
            receipt.error = None
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
            data.setdefault("parallel_group", self.LANE_PARALLEL_GROUPS.get(lane, "single_agent_fanout"))
            data.setdefault("reused", False)
        self._finalize_receipt(ctx, lane, tool_name, data)

    def _lane_adapters(self, lane: str) -> Tuple[Any, ...]:
        if lane == "market":
            return (
                MarketQuestionAdapter("market_question_a", "Market Research Question A"),
                MarketQuestionAdapter("market_question_b", "Market Research Question B"),
                StockTrackerAdapter(),
            )
        if lane == "web":
            return (WebRetrieverAdapter(),)
        return tuple()

    def _should_reuse_market(self, ctx: PlannerPhaseContext) -> bool:
        market_artifact = getattr(ctx.artifacts, "market", None)
        has_snapshot = bool(market_artifact and getattr(market_artifact, "snapshot", None))
        if not has_snapshot:
            return False
        receipts = [
            ctx.tool_receipts.get(tool_name)
            for tool_name in self._lane_tool_names("market")
        ]
        if any(self._receipt_is_fresh(receipt) for receipt in receipts):
            return True
        age = ctx.snapshot_age_seconds
        if age is None:
            return self.follow_up_route == FollowUpRoute.REUSE_SQL
        return age <= self.LANE_CACHE_TTL_SECONDS

    def _should_reuse_web(self, ctx: PlannerPhaseContext) -> bool:
        web_artifact = getattr(ctx.artifacts, "web", None)
        has_web = bool(web_artifact and getattr(web_artifact, "summary", None))
        if not has_web:
            analysis_art = getattr(ctx.artifacts, "analysis", None)
            has_web = bool(analysis_art and getattr(analysis_art, "web_context", None))
        if not has_web:
            return False
        receipt = ctx.tool_receipts.get("web_retriever")
        if self._receipt_is_fresh(receipt):
            return True
        age = ctx.snapshot_age_seconds
        if age is None:
            return self.follow_up_route == FollowUpRoute.REUSE_SQL
        return age <= self.LANE_CACHE_TTL_SECONDS

    def _start_fanout_lanes(
        self,
        ctx: PlannerPhaseContext,
        lanes: Iterable[str],
    ) -> Dict[str, Tuple[asyncio.Task, Optional[asyncio.Queue]]]:
        active: Dict[str, Tuple[asyncio.Task, Optional[asyncio.Queue]]] = {}
        for lane in lanes:
            adapters = self._lane_adapters(lane)
            if not adapters:
                continue
            concurrency_limit = self.LANE_CONCURRENCY_LIMITS.get(lane)
            if concurrency_limit is None:
                concurrency_limit = len(adapters)
            else:
                concurrency_limit = max(1, min(concurrency_limit, len(adapters)))
            task, queue = self._planner._start_tool_parallelism(
                ctx,
                adapters=adapters,
                concurrency_override=concurrency_limit,
            )
            active[lane] = (task, queue)
        return active

    def _iter_fresh_accessory_events(
        self,
        ctx: PlannerPhaseContext,
        lane_states: Mapping[str, str],
    ) -> Iterable[Dict[str, Any]]:
        if lane_states.get("market") == "fresh" and not getattr(ctx, "stock_widget_announced", False):
            stock_payload = _compose_stock_ready_payload(ctx)
            if stock_payload:
                payload = dict(stock_payload)
                payload["reused"] = False
                payload.setdefault("schedule_stage", "hedged_accessories")
                payload.setdefault("parallel_group", self.LANE_PARALLEL_GROUPS.get("market", "single_agent_market"))
                payload.setdefault("lane", "market")
                payload.setdefault("flow_mode", self.flow_mode.value)
                payload.setdefault("ts", datetime.utcnow().isoformat())
                sanitized = sanitize_for_json(payload)
                if not isinstance(sanitized, dict):
                    sanitized = {"payload": sanitized}
                ctx.stock_widget_announced = True  # type: ignore[attr-defined]
                yield self._planner._annotate(
                    {
                        "event": "stock_ready",
                        "data": sanitized,
                    }
                )
        if lane_states.get("web") == "fresh" and not getattr(ctx, "web_context_announced", False):
            web_payload = _compose_web_ready_payload(ctx)
            if web_payload:
                payload = dict(web_payload)
                payload["reused"] = False
                payload.setdefault("schedule_stage", "hedged_accessories")
                payload.setdefault("parallel_group", self.LANE_PARALLEL_GROUPS.get("web", "single_agent_web"))
                payload.setdefault("lane", "web")
                payload.setdefault("flow_mode", self.flow_mode.value)
                payload.setdefault("ts", datetime.utcnow().isoformat())
                sanitized = sanitize_for_json(payload)
                if not isinstance(sanitized, dict):
                    sanitized = {"payload": sanitized}
                ctx.web_context_announced = True  # type: ignore[attr-defined]
                yield self._planner._annotate(
                    {
                        "event": "web_ready",
                        "data": sanitized,
                    }
                )

    def _drain_fanout_events(
        self,
        ctx: PlannerPhaseContext,
        fanout_tasks: Dict[str, Tuple[asyncio.Task, Optional[asyncio.Queue]]],
    ) -> AsyncGenerator[Dict[str, Any], None]:
        for lane, (_, queue) in fanout_tasks.items():
            if not queue:
                continue
            lane_events = self._planner._flush_tool_events(queue)
            for event in lane_events:
                data = event.setdefault("data", {})
                parallel_group = self.LANE_PARALLEL_GROUPS.get(lane, "single_agent_fanout")
                data.setdefault("parallel_group", parallel_group)
                data.setdefault("lane", lane)
                data.setdefault("reused", False)
                self._process_tool_parallel_event(ctx, event, lane_hint=lane)
                yield self._planner._annotate(event)

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

    def set_follow_up_route(self, route: FollowUpRoute) -> None:
        self.follow_up_route = route
        self._planner.set_follow_up_route(route)

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
        **kwargs: Any,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        resolved_query = query if query is not None else await self._resolve_session_query(session_id)
        ctx = await self._planner.initialize_context(resolved_query or "", session_id=session_id)
        registry = get_planner_tool_registry()
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
        ctx = await self._planner.initialize_context(query, session_id=session_id)
        session_identifier = ctx.session_id
        yield self._planner._annotate(EventEmitter.session_started(session_identifier))

        registry = get_planner_tool_registry()
        executed: Set[str] = set()
        mode_config = get_mode_config(self.flow_mode)
        fanout_tasks: Dict[str, Tuple[asyncio.Task, Optional[asyncio.Queue]]] = {}
        started_lanes: Set[str] = set()
        lane_states: Dict[str, str] = {
            "sql": "pending",
            "chart": "queued",
            "analysis": "queued",
            "market": "skipped",
            "web": "skipped",
        }

        try:
            async for event in registry.invoke("classification", self._planner, ctx, executed=executed):
                yield self._planner._annotate(event)
            await self._planner._persist_session_state(ctx, record_artifacts=True)
            if not ctx.is_financial_query:
                return

            for tool_name in ("intent_detection", "clarification", "plan_generation"):
                async for event in registry.invoke(tool_name, self._planner, ctx, executed=executed):
                    yield self._planner._annotate(event)
                await self._planner._persist_session_state(ctx, record_artifacts=True)

            if ctx.intent is None or (ctx.plan or ctx.provisional_plan) is None:
                return

            reuse_sql = ctx.reuse_sql and ctx.revision_snapshot is not None
            should_run_parallel = ctx.parallelism_enabled and not (ctx.reuse_sql and ctx.reuse_snapshot_active)
            market_reuse = self._should_reuse_market(ctx)
            web_reuse = self._should_reuse_web(ctx)
            if market_reuse:
                lane_states["market"] = "reused"
                self._mark_lane_reused(ctx, "market")
            if web_reuse:
                lane_states["web"] = "reused"
                self._mark_lane_reused(ctx, "web")

            lanes_to_start: Tuple[str, ...] = tuple(
                lane
                for lane in self.CONCURRENT_LANES
                if not (
                    (lane == "market" and market_reuse)
                    or (lane == "web" and web_reuse)
                )
            )

            if should_run_parallel and not reuse_sql and lanes_to_start:
                fanout_tasks = self._start_fanout_lanes(ctx, lanes_to_start)
                started_lanes = set(fanout_tasks.keys())
                if "market" in started_lanes:
                    lane_states["market"] = "running"
                if "web" in started_lanes:
                    lane_states["web"] = "running"
                for fanout_event in self._drain_fanout_events(ctx, fanout_tasks):
                    yield fanout_event
            elif should_run_parallel and not reuse_sql and (market_reuse or web_reuse):
                ctx.accessories_prefetched = True

            if not reuse_sql and ctx.snapshot_stale and ctx.revision_snapshot:
                stale_progress = EventEmitter.progress("sql_generation", "Cached SQL snapshot expired - rerunning dataset")
                stale_progress["data"]["ts"] = datetime.utcnow().isoformat()
                stale_progress["data"]["schedule_stage"] = "sql"
                stale_progress["data"]["parallel_group"] = "core_sequential"
                stale_progress["data"]["flow_mode"] = self.flow_mode.value
                stale_progress["data"]["reused"] = False
                yield self._planner._annotate(stale_progress)
                if fanout_tasks:
                    for fanout_event in self._drain_fanout_events(fanout_tasks):
                        yield fanout_event

            if not reuse_sql:
                lane_states["sql"] = "running"
                async for event in registry.invoke("sql_generation", self._planner, ctx, executed=executed):
                    yield self._planner._annotate(event)
                    if fanout_tasks:
                        for fanout_event in self._drain_fanout_events(ctx, fanout_tasks):
                            yield fanout_event
                lane_states["sql"] = "fresh"
            else:
                ctx.reused_sql = True
                lane_states["sql"] = "reused"
                reuse_status = EventEmitter.progress("sql_generation", "Reusing cached SQL dataset")
                reuse_status["data"]["ts"] = datetime.utcnow().isoformat()
                reuse_status["data"]["schedule_stage"] = "sql"
                reuse_status["data"]["parallel_group"] = "core_sequential"
                reuse_status["data"]["flow_mode"] = self.flow_mode.value
                reuse_status["data"]["reused"] = True
                yield self._planner._annotate(reuse_status)
                receipt = ctx.tool_receipts.get("sql_chain")
                if receipt:
                    receipt.status = "reused"
                    receipt.reused = True
                    receipt.error = None
                sql_payload = _compose_sql_ready_payload(ctx)
                if sql_payload:
                    cached_sql_event = _cached_event(
                        "sql_ready",
                        sql_payload,
                        schedule_stage="sql",
                        flow_mode=self.flow_mode,
                        parallel_group="core_sequential",
                        lane="sql",
                    )
                    yield self._planner._annotate(cached_sql_event)
                    if fanout_tasks:
                        for fanout_event in self._drain_fanout_events(ctx, fanout_tasks):
                            yield fanout_event

            await self._planner._persist_session_state(
                ctx,
                record_sql=(not reuse_sql) and bool(ctx.artifacts.sql_generation and ctx.artifacts.sql_generation.sql),
                record_artifacts=True,
            )
            if not reuse_sql:
                sql_payload = _compose_sql_ready_payload(ctx)
                if sql_payload:
                    sql_payload.setdefault("parallel_group", "core_sequential")
                    sql_payload.setdefault("flow_mode", self.flow_mode.value)
                    sql_payload.setdefault("ts", datetime.utcnow().isoformat())
                    sql_payload.setdefault("lane", "sql")
                    sql_payload["reused"] = False
                    yield self._planner._annotate(
                        {
                            "event": "sql_ready",
                            "data": sanitize_for_json(sql_payload),
                        }
                    )

            if fanout_tasks:
                for fanout_event in self._drain_fanout_events(ctx, fanout_tasks):
                    yield fanout_event

                for lane in list(fanout_tasks.keys()):
                    task, queue = fanout_tasks[lane]
                    if not task:
                        continue
                    try:
                        await task
                        if lane_states.get(lane) == "running":
                            lane_states[lane] = "fresh"
                    except Exception:
                        lane_states[lane] = "error"
                        raise
                    finally:
                        lane_entry = {lane: (task, queue)}
                        for fanout_event in self._drain_fanout_events(ctx, lane_entry):
                            yield fanout_event
                        fanout_tasks.pop(lane, None)
                ctx.accessories_prefetched = bool(started_lanes)
                for accessory_event in self._iter_fresh_accessory_events(ctx, lane_states):
                    yield accessory_event

            if reuse_sql:
                stock_payload = _compose_stock_ready_payload(ctx)
                if stock_payload:
                    self._mark_lane_reused(ctx, "market")
                    lane_states["market"] = "reused"
                    cached_stock_event = _cached_event(
                        "stock_ready",
                        stock_payload,
                        schedule_stage="hedged_accessories",
                        flow_mode=self.flow_mode,
                        parallel_group=self.LANE_PARALLEL_GROUPS.get("market", "tool_fanout"),
                        lane="market",
                    )
                    yield self._planner._annotate(cached_stock_event)
                web_payload = _compose_web_ready_payload(ctx)
                if web_payload:
                    self._mark_lane_reused(ctx, "web")
                    lane_states["web"] = "reused"
                    cached_web_event = _cached_event(
                        "web_ready",
                        web_payload,
                        schedule_stage="hedged_accessories",
                        flow_mode=self.flow_mode,
                        parallel_group=self.LANE_PARALLEL_GROUPS.get("web", "tool_fanout"),
                        lane="web",
                    )
                    yield self._planner._annotate(cached_web_event)
                ctx.accessories_prefetched = True
            elif not started_lanes:
                logger.debug(
                    "Ensuring analysis dependencies for single-agent flow",
                    extra={
                        "session_id": ctx.session_id,
                        "market_lane": lane_states.get("market"),
                        "web_lane": lane_states.get("web"),
                        "flow_mode": self.flow_mode.value,
                    },
                )
                async for event in self._planner._ensure_analysis_dependencies(ctx):
                    data = event.setdefault("data", {})
                    lane_hint = None
                    tool_name = data.get("tool")
                    if tool_name:
                        lane_hint = self._lane_for_tool(tool_name)
                    self._process_tool_parallel_event(ctx, event, lane_hint=lane_hint)
                    lane = data.get("lane") or lane_hint
                    if not lane:
                        tools_meta = data.get("tools") or []
                        for tool_meta in tools_meta:
                            if not isinstance(tool_meta, Mapping):
                                continue
                            candidate = self._lane_for_tool(tool_meta.get("name") or tool_meta.get("tool"))
                            if candidate:
                                lane = candidate
                                break
                    if lane:
                        data.setdefault("lane", lane)
                        data.setdefault("parallel_group", self.LANE_PARALLEL_GROUPS.get(lane, "single_agent_fanout"))
                        data.setdefault("reused", False)
                    yield self._planner._annotate(event)
                ctx.accessories_prefetched = True
                if lane_states["market"] == "reused":
                    stock_payload = _compose_stock_ready_payload(ctx)
                    if stock_payload:
                        self._mark_lane_reused(ctx, "market")
                        yield self._planner._annotate(
                            _cached_event(
                                "stock_ready",
                                stock_payload,
                                schedule_stage="hedged_accessories",
                                flow_mode=self.flow_mode,
                                parallel_group=self.LANE_PARALLEL_GROUPS.get("market", "tool_fanout"),
                                lane="market",
                            )
                        )
                elif ctx.artifacts.market and lane_states["market"] == "skipped":
                    lane_states["market"] = "fresh"
                if lane_states["web"] == "reused":
                    web_payload = _compose_web_ready_payload(ctx)
                    if web_payload:
                        self._mark_lane_reused(ctx, "web")
                        yield self._planner._annotate(
                            _cached_event(
                                "web_ready",
                                web_payload,
                                schedule_stage="hedged_accessories",
                                flow_mode=self.flow_mode,
                                parallel_group=self.LANE_PARALLEL_GROUPS.get("web", "tool_fanout"),
                                lane="web",
                            )
                        )
                elif ctx.artifacts.web and lane_states["web"] == "skipped":
                    lane_states["web"] = "fresh"
                for accessory_event in self._iter_fresh_accessory_events(ctx, lane_states):
                    yield accessory_event
            else:
                if ctx.artifacts.market and lane_states["market"] in {"running", "pending"}:
                    lane_states["market"] = "fresh"
                if ctx.artifacts.web and lane_states["web"] in {"running", "pending"}:
                    lane_states["web"] = "fresh"
                for accessory_event in self._iter_fresh_accessory_events(ctx, lane_states):
                    yield accessory_event

            lane_summary_event = self._emit_lane_summary(lane_states)
            if lane_summary_event:
                yield lane_summary_event
            else:
                logger.debug(
                    "Single-agent lane summary emitted no payload",
                    extra={
                        "session_id": ctx.session_id,
                        "lane_states": dict(lane_states),
                        "flow_mode": self.flow_mode.value,
                    },
                )

            if ctx.halted:
                logger.warning(
                    "Single-agent flow halted after lane summary",
                    extra={
                        "session_id": ctx.session_id,
                        "halt_reason": getattr(ctx, "halt_reason", None),
                        "lane_states": dict(lane_states),
                        "flow_mode": self.flow_mode.value,
                    },
                )
                return

            lane_states["chart"] = "running"
            async for event in registry.invoke("chart_generation", self._planner, ctx, executed=executed):
                yield self._planner._annotate(event)
            lane_states["chart"] = "reused" if getattr(ctx, "reused_chart", False) else "fresh"
            await self._planner._persist_session_state(
                ctx,
                record_chart=bool(ctx.artifacts.chart and ctx.artifacts.chart.spec),
                record_artifacts=True,
            )

            if mode_config.accessories_in_critical_path:
                async for event in self._planner._web_search_phase(ctx):
                    yield self._planner._annotate(event)
                await self._planner._persist_session_state(ctx, record_artifacts=True)

            lane_states["analysis"] = "running" if not getattr(ctx, "reused_analysis", False) else "reused"
            async for event in registry.invoke("analysis_generation", self._planner, ctx, executed=executed):
                yield self._planner._annotate(event)
            if getattr(ctx, "reused_analysis", False):
                lane_states["analysis"] = "reused"
            else:
                lane_states["analysis"] = "fresh"
            await self._planner._persist_session_state(
                ctx,
                record_analysis=bool(
                    ctx.artifacts.analysis and ctx.artifacts.analysis.analysis_text
                ),
                record_artifacts=True,
            )
        finally:
            for task, _ in fanout_tasks.values():
                if task and not task.done():
                    task.cancel()
                    with contextlib.suppress(Exception):
                        await task

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

    async def analysis_revision(
        self,
        *,
        session_id: str,
        analysis: str,
        reason: Optional[str] = None,
        source: Optional[str] = None,
        query: Optional[str] = None,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        hooks = _SingleAgentToolHooks(self, session_id=session_id)
        async for event in self._invoke_planner_tool(
            "analysis_revision",
            session_id=session_id,
            query=query,
            hooks=hooks,
            analysis=analysis,
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




    def latest_artifacts(self):
        return self._planner.latest_artifacts()


