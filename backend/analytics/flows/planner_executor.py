from __future__ import annotations
from typing import AsyncGenerator, Dict, Any, Optional, List, Tuple
from dataclasses import dataclass, field
import asyncio
import os
import logging
import time
import uuid
import statistics
import inspect
from datetime import datetime
from analytics.core.types import (
    WorkflowState,
    SQLResultModel,
    ChartSpecModel,
    ValidationError,
    IntentModel,
    QueryPlanModel,
    ClarifyAnswerModel,
    ClarifyRequestModel,
    PlannerResultModel,
)
from analytics.core.context import get_configs
from analytics.core.config_store import get_config_store
from analytics.core.events import EventEmitter, TimedEventEmitter
from .tooling import run_tool_parallelism
from ..core.intent import intent_to_sql_criteria
from analytics.core.intent import detect_intent, detect_intent_llm, detect_intent_with_clarifications, classify_query_async, OffTopicClassifierSchema
from analytics.sql.sql_planner import build_query_plan, choose_template
from analytics.sql.executor import execute_sql
from analytics.sql.validator import validate_sql
from analytics.sql.templates import fetch_templates_for_intent
from analytics.sql.prompt_builder import build_sql_messages, build_sql_retry_messages, extract_sql_from_response
from analytics.core.charting import build_chart_spec, plan_chart_rule_based
from .tool_bundle import collect_tool_bundle
from analytics.core.telemetry import analysis_chunk as log_analysis_chunk, policy_decision as log_policy_decision, retry_summary
from analytics.core.analysis import summarize, stream_insights_llm
from analytics.core.clarify import (
    detect_missing_slots,
    merge_answers,
    wait_for_answer_blocking,
    compute_required_clarifications,
    validate_clarification_answer,
    get_validation_error_message,
)
from unified_responses_client import get_unified_client
CONFIGS = get_configs()
CONFIG_STORE = get_config_store()
logger = logging.getLogger(__name__)
def _env_flag(name: str, *, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    normalized = value.strip().lower()
    if normalized in {'1', 'true', 'yes', 'on'}:
        return True
    if normalized in {'0', 'false', 'no', 'off'}:
        return False
    return default
def _generate_chart_design(intent_key: Optional[str], plan: QueryPlanModel, data: List[Dict[str, Any]], spec: Dict[str, Any]) -> Dict[str, Any]:
    """Generate smart chart design metadata for frontend optimization."""
    if not intent_key or not data:
        return {}
    # Extract available columns from data
    cols = list(data[0].keys()) if data else []
    has_multiple_tickers = len(set(row.get('ticker') for row in data if row.get('ticker'))) > 1
    design = {
        'intent': intent_key,
        'grouping': 'ticker' if has_multiple_tickers else 'metric',
        'chart_type': 'line_multi',
        'y_axis': {'type': 'dual'},
        'legend_order': [],
        'defaultLegendSelection': {},
        'color_by': 'ticker' if has_multiple_tickers else 'metric'
    }
    # Intent-specific configurations
    if intent_key == 'market_share_all':
        design.update({
            'chart_type': 'stacked_area_100',
            'measure': 'market_share_percent',
            'top_n': 3,
            'aggregate_rest': True,
            'rest_label': 'Others',
            'y_axis': {'type': 'percent_only'}
        })
    elif intent_key == 'market_share_single':
        design.update({
            'measure': 'market_share_percent',
            'y_axis': {'type': 'dual'},  # market share + revenue context
            'defaultLegendSelection': {'market_share_percent': True}
        })
    elif intent_key in ['revenue_growth_analysis']:
        design.update({
            'measure': ['qoq_growth_percent', 'yoy_growth_percent'],
            'y_axis': {'type': 'dual'},  # growth on right, revenue context on left
            'defaultLegendSelection': {
                'qoq_growth_percent': True, 
                'yoy_growth_percent': True,
                'quarterly_revenue': False  # context series hidden by default
            }
        })
    elif intent_key in ['margins_vs_peers', 'margin_growth_vs_peers']:
        design.update({
            'measure': ['gross_margin', 'operating_margin', 'net_margin'] if 'margins_vs_peers' in intent_key 
                      else ['company_gross_margin_change_pp', 'company_operating_margin_change_pp', 'company_net_margin_change_pp', 'peer_avg_gross_margin_change_pp', 'peer_avg_operating_margin_change_pp', 'peer_avg_net_margin_change_pp'],
            'y_axis': {'type': 'percent_only'},
            'defaultLegendSelection': {
                'operating_margin': True,
                'net_margin': True
            } if 'margins_vs_peers' in intent_key else {
                'company_operating_margin_change_pp': True,
                'company_net_margin_change_pp': True
            }
        })
    elif intent_key in ['rnd_intensity_vs_peers', 'rnd_expense_vs_peers']:
        design.update({
            'measure': 'company_rnd_intensity' if 'intensity' in intent_key else 'company_rnd_expense',
            'y_axis': {'type': 'percent_only'} if 'intensity' in intent_key else {'type': 'currency_only'},
            'chart_type': 'line_multi'
        })
    return design

@dataclass
class PlannerPhaseContext:
    query: str
    session_id: str
    workflow_start: float
    timed_emitter: TimedEventEmitter
    configs: Dict[str, Any] = field(default_factory=dict)
    classification: Optional[OffTopicClassifierSchema] = None
    is_financial_query: bool = True
    intent: Optional[IntentModel] = None
    provisional_plan: Optional[QueryPlanModel] = None
    template: Optional[Any] = None
    clarifications: List[ClarifyRequestModel] = field(default_factory=list)
    assumptions: List[str] = field(default_factory=list)
    clarification_rounds: int = 0
    plan: Optional[QueryPlanModel] = None
    candidate_templates: List[Dict[str, Any]] = field(default_factory=list)
    selected_template_id: Optional[str] = None
    sql: str = ""
    llm_used: bool = False
    sql_attempt: int = 1
    sql_attempts: List[Dict[str, Any]] = field(default_factory=list)
    sql_phase_status: str = "pending"
    validation_attempt: int = 1
    data: List[Dict[str, Any]] = field(default_factory=list)
    exec_elapsed_ms: Optional[int] = None
    chart_spec: Optional[Dict[str, Any]] = None
    analysis: str = ""
    parallelism_enabled: bool = False
    planner_result: PlannerResultModel = field(default_factory=PlannerResultModel)


class PlannerExecutorFlow:
    """Phase 2 workflow that emits SSE-friendly events for the memory pipeline."""

    def __init__(self) -> None:
        self.unified_client = get_unified_client()
        self.config_store = CONFIG_STORE
        self.flow_label = "planner-executor"
        self.parallelism_enabled = _env_flag("ANALYTICS_TOOL_PARALLELISM", default=False)


    async def _sql_phase(
        self,
        ctx: PlannerPhaseContext,
        *,
        query: str,
        intent: IntentModel,
        plan: QueryPlanModel,
        session_id: str,
        candidate_templates: Optional[List[Dict[str, Any]]] = None,
        selected_template_id: Optional[str] = None,
        timed_emitter: TimedEventEmitter,
        allow_policy_override: bool = False,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        database_cfg = CONFIGS.database or {}
        defaults = database_cfg.get("query_defaults", {}) if isinstance(database_cfg, dict) else {}
        default_limit = int(defaults.get("default_limit", 500))
        max_limit = int(defaults.get("max_limit", default_limit))
        requested_limit = getattr(plan, "limit", None) if plan else None
        effective_limit = default_limit
        if isinstance(requested_limit, int) and requested_limit > 0:
            effective_limit = min(requested_limit, default_limit)
        plan.limit = effective_limit

        sql_policy_meta = ctx.planner_result.metadata.setdefault("sql_policy", {})
        sql_policy_meta.update({
            "default_limit": default_limit,
            "max_limit": max_limit,
            "requested_limit": requested_limit,
            "effective_limit": effective_limit,
        })

        ctx.sql = ""
        ctx.data = []
        ctx.sql_phase_status = "running"
        ctx.sql_attempts = []

        progress_event = EventEmitter.progress("sql_compilation", "Generating SQL with Responses API...")
        progress_event["data"]["ts"] = datetime.utcnow().isoformat()
        yield progress_event
        timed_emitter.start_step("sql_generation")

        fallback_emitted = False

        def _build_fallback_analysis(message: str, *, sources: Optional[Dict[str, bool]] = None) -> Optional[Dict[str, Any]]:
            nonlocal fallback_emitted
            if fallback_emitted:
                return None
            fallback_emitted = True
            resolved_message = message or "Analysis unavailable."
            fallback_sources = sources or {'sql': False, 'web': False, 'market': False, 'llm': False}
            sections = {
                'market_trend': [],
                'web_highlights': [],
                'market_snapshot': [],
                'llm_commentary': resolved_message,
            }
            ctx.planner_result.analysis = resolved_message
            ctx.planner_result.metadata['analysis_sources'] = fallback_sources
            ctx.planner_result.metadata['analysis_sections'] = sections
            ctx.planner_result.metadata['llm_analysis'] = resolved_message
            payload = {
                'analysis_length': len(resolved_message or ''),
                'analysis': resolved_message,
                'analysis_sources': fallback_sources,
                'analysis_sections': sections,
                'llm_analysis': resolved_message,
            }
            event = EventEmitter.result(
                "analysis_complete",
                payload,
                key="analysis",
            )
            event["event"] = "analysis_complete"
            event["data"].update(
                {
                    "ts": datetime.utcnow().isoformat(),
                    "elapsed_ms": 0,
                }
            )
            return event

        candidate_templates = candidate_templates or []
        confidence = float(getattr(intent, "confidence", 0.0) or 0.0)
        policy_threshold = float(os.getenv("ANALYTICS_SQL_CONFIDENCE_THRESHOLD", "0.35"))
        sql_policy_meta["confidence"] = confidence
        sql_policy_meta["policy_threshold"] = policy_threshold

        attempt_logs: List[Dict[str, Any]] = []
        if (not allow_policy_override and confidence < policy_threshold and isinstance(requested_limit, int) and requested_limit > default_limit):
            log_policy_decision(
                policy="sql_retry_confidence",
                score=confidence,
                threshold=policy_threshold,
                action="skip_retry",
                reason="intent confidence below threshold for expanded limit",
                session_id=session_id,
                flow=self.flow_label,
                metadata={
                    "requested_limit": requested_limit,
                    "effective_limit": effective_limit,
                },
            )
            policy_event = EventEmitter.result(
                "sql_policy",
                {
                    "policy": "sql_retry_confidence",
                    "score": confidence,
                    "threshold": policy_threshold,
                    "action": "skip_retry",
                    "reason": "intent confidence below threshold for expanded limit",
                    "requested_limit": requested_limit,
                    "effective_limit": effective_limit,
                },
            )
            policy_event["event"] = "policy_decision"
            policy_event["data"]["ts"] = datetime.utcnow().isoformat()
            yield policy_event
            attempt_logs.append({
                "attempt": 1,
                "source": "policy_guard",
                "status": "policy_blocked",
                "score": confidence,
                "threshold": policy_threshold,
                "requested_limit": requested_limit,
                "effective_limit": effective_limit,
                "elapsed_ms": 0,
                "validation_elapsed_ms": 0,
            })
            ctx.sql_attempts = attempt_logs
            ctx.planner_result.sql_attempts = list(attempt_logs)
            ctx.sql_phase_status = "policy_blocked"
            fallback_text = (
                "Unable to generate SQL because intent confidence "
                f"{confidence:.2f} is below the retry policy threshold {policy_threshold:.2f}."
            )
            fallback_event = _build_fallback_analysis(fallback_text)
            if fallback_event:
                yield fallback_event
            retry_summary(
                stage="sql_generation",
                attempts=attempt_logs,
                final_status=ctx.sql_phase_status,
                session_id=session_id,
                flow=self.flow_label,
            )
            return

        messages = await build_sql_messages(
            original_query=query,
            intent=intent,
            plan=plan,
            config_store=self.config_store,
            templates=candidate_templates,
        )

        MAX_SQL_ATTEMPTS = 3
        last_error_code: Optional[str] = None
        last_error_detail: Optional[str] = None
        previous_sql: Optional[str] = None
        sql_text = ""

        for attempt in range(1, MAX_SQL_ATTEMPTS + 1):
            attempt_start = time.time()
            attempt_record: Dict[str, Any] = {
                "attempt": attempt,
                "source": "responses_sql",
                "status": "started",
                "elapsed_ms": 0,
                "validation_elapsed_ms": 0,
            }
            candidate_sql = ""
            pending_events: List[Dict[str, Any]] = []
            try:
                if not self.unified_client:
                    self.unified_client = get_unified_client()
                if not self.unified_client:
                    raise RuntimeError("Unified Responses client is not configured")
                llm_response, _ = await self.unified_client.simple_completion(
                    messages=messages,
                    reasoning_effort="medium",
                )
                candidate_sql = (extract_sql_from_response(llm_response) or "").strip()
            except Exception as exc:
                last_error_code = "SQL_GENERATION_ERROR"
                last_error_detail = str(exc)
                attempt_record.update(
                    status="error",
                    error_code=last_error_code,
                    error_detail=last_error_detail,
                )
                error_event = EventEmitter.error(
                    "sql_compilation",
                    "SQL generation failed",
                    details={"attempt": attempt, "error": last_error_detail},
                    code=last_error_code,
                )
                error_event["data"]["ts"] = datetime.utcnow().isoformat()
                pending_events.append(error_event)
            else:
                if not candidate_sql:
                    last_error_code = "SQL_EMPTY"
                    last_error_detail = "Responses API returned no SQL content."
                    attempt_record.update(
                        status="empty",
                        error_code=last_error_code,
                        error_detail=last_error_detail,
                    )
                    empty_event = EventEmitter.progress(
                        "sql_compilation",
                        "SQL attempt returned no content; retrying with additional guidance.",
                    )
                    empty_event["data"].update({"ts": datetime.utcnow().isoformat(), "attempt": attempt})
                    pending_events.append(empty_event)
                else:
                    ok, issues, validate_elapsed = self._validate_sql_with_timing(
                        candidate_sql,
                        plan,
                        limit_guard=default_limit,
                    )
                    attempt_record["validation_elapsed_ms"] = validate_elapsed
                    if not ok and allow_policy_override:
                        ok = True
                        issues = []
                    if ok:
                        sql_text = candidate_sql
                        ctx.sql = sql_text
                        ctx.llm_used = True
                        ctx.sql_attempt = attempt
                        ctx.planner_result.sql_text = sql_text
                        attempt_record["status"] = "valid"
                        attempt_record["sql_preview"] = candidate_sql[:160]
                        compiled_event = EventEmitter.result(
                            "sql_compiled",
                            {
                                "sql_length": len(sql_text),
                                "template_fallback": False,
                                "template_used": selected_template_id,
                                "attempt": attempt,
                                "fallback_reason": None,
                                "llm_used": True,
                            },
                        )
                        compiled_event["event"] = "sql_compiled"
                        compiled_event["data"].update(
                            {
                                "ts": datetime.utcnow().isoformat(),
                            }
                        )
                        pending_events.append(compiled_event)
                        generated_event = EventEmitter.sql_generated(sql_text)
                        generated_event["data"].update(
                            {
                                "ts": datetime.utcnow().isoformat(),
                                "llm_used": True,
                                "attempt": attempt,
                            }
                        )
                        pending_events.append(generated_event)
                    else:
                        last_error_code = "SQL_VALIDATION_FAILED"
                        last_error_detail = '; '.join(issues) if issues else "Validation failed"
                        attempt_record.update(
                            status="invalid",
                            error_code=last_error_code,
                            error_detail=last_error_detail,
                            sql_preview=candidate_sql[:160],
                        )
                        validation_event = EventEmitter.error(
                            "sql_validation",
                            "Generated SQL failed validation",
                            details={"attempt": attempt, "issues": issues},
                            code=last_error_code,
                        )
                        validation_event["data"]["ts"] = datetime.utcnow().isoformat()
                        pending_events.append(validation_event)
                        previous_sql = candidate_sql
            attempt_record["elapsed_ms"] = int((time.time() - attempt_start) * 1000)
            attempt_logs.append(attempt_record)
            ctx.sql_attempts = attempt_logs
            ctx.planner_result.sql_attempts = list(attempt_logs)
            for pending in pending_events:
                if pending.get("event") in {"sql_compiled", "sql_generated"}:
                    pending["data"].setdefault("elapsed_ms", attempt_record["elapsed_ms"])
                yield pending
            if sql_text:
                break
            if attempt < MAX_SQL_ATTEMPTS:
                retry_notice = EventEmitter.progress(
                    "sql_compilation",
                    f"Retrying SQL generation (attempt {attempt + 1}/{MAX_SQL_ATTEMPTS})",
                )
                retry_notice["data"].update(
                    {
                        "ts": datetime.utcnow().isoformat(),
                        "last_error": last_error_code,
                    }
                )
                yield retry_notice
                messages = await build_sql_retry_messages(
                    original_query=query,
                    intent=intent,
                    plan=plan,
                    error_code=last_error_code or "unknown_error",
                    error_detail=last_error_detail or "",
                    previous_sql=previous_sql,
                    attempts=attempt_logs,
                    config_store=self.config_store,
                    templates=candidate_templates,
                )

        timed_emitter.end_step("sql_generation")
        if not sql_text:
            ctx.sql_phase_status = "sql_generation_failed"
            fallback_reason = "SQL generation attempts were exhausted."
            if last_error_detail:
                fallback_reason = f"SQL generation failed: {last_error_detail}."
            fallback_event = _build_fallback_analysis(fallback_reason)
            if fallback_event:
                yield fallback_event
            failure_event = EventEmitter.error(
                "sql_compilation",
                "Unable to generate valid SQL after 3 attempts",
                details={"attempts": attempt_logs, "last_error": last_error_code, "last_detail": last_error_detail},
                code=last_error_code or "SQL_RETRY_EXHAUSTED",
            )
            failure_event["data"]["ts"] = datetime.utcnow().isoformat()
            yield failure_event
            retry_summary(
                stage="sql_generation",
                attempts=attempt_logs,
                final_status=ctx.sql_phase_status,
                session_id=session_id,
                flow=self.flow_label,
            )
            return

        timed_emitter.start_step("sql_validation")
        validation_progress = EventEmitter.progress("sql_validation", "Validating SQL...")
        validation_progress["data"]["ts"] = datetime.utcnow().isoformat()
        yield validation_progress
        ok, issues, validate_elapsed = self._validate_sql_with_timing(
            sql_text,
            plan,
            limit_guard=default_limit,
        )
        if not ok and allow_policy_override:
            ok = True
            issues = []
        validation_event = EventEmitter.result(
            "sql_validated",
            {
                "ok": ok,
                "issues_count": len(issues),
                "attempt": ctx.sql_attempt,
                "issues": issues,
            },
        )
        validation_event["event"] = "sql_validated"
        validation_event["data"].update(
            {"ts": datetime.utcnow().isoformat(), "elapsed_ms": validate_elapsed}
        )
        yield validation_event
        timed_emitter.end_step("sql_validation")
        if not ok:
            ctx.sql_phase_status = "sql_validation_failed"
            fallback_reason = "SQL validation failed."
            if issues:
                joined = '; '.join(str(issue) for issue in issues if issue)
                if joined:
                    fallback_reason = f"SQL validation failed: {joined}."
            fallback_event = _build_fallback_analysis(fallback_reason)
            if fallback_event:
                yield fallback_event
            error_event = EventEmitter.error(
                "sql_validation",
                "SQL failed validation after retries",
                details={"attempts": attempt_logs, "issues": issues},
                code="SQL_VALIDATION_FINAL",
            )
            error_event["data"]["ts"] = datetime.utcnow().isoformat()
            yield error_event
            ctx.sql_phase_status = "sql_validation_failed"
            retry_summary(
                stage="sql_generation",
                attempts=attempt_logs,
                final_status=ctx.sql_phase_status,
                session_id=session_id,
                flow=self.flow_label,
            )
            return

        execution_progress = EventEmitter.progress("sql_execution", "Executing query...")
        execution_progress["data"]["ts"] = datetime.utcnow().isoformat()
        yield execution_progress
        timed_emitter.start_step("sql_execution")
        exec_start = time.time()
        try:
            data = await execute_sql(sql_text)
        except Exception as exec_exc:
            logger.error(
                "[SQL_EXECUTION] Execution failed: %s",
                exec_exc,
                extra={
                    "error_code": "SQL_EXECUTION_ERROR",
                    "flow": self.flow_label,
                    "session_id": session_id,
                    "intent_key": intent.intent_key,
                },
            )
            error_event = EventEmitter.error(
                "sql_execution",
                "SQL execution failed",
                details={"error": str(exec_exc)},
                code="SQL_EXECUTION_ERROR",
            )
            error_event["data"]["ts"] = datetime.utcnow().isoformat()
            yield error_event
            fallback_reason = f"SQL execution failed: {exec_exc}."
            fallback_event = _build_fallback_analysis(fallback_reason)
            if fallback_event:
                yield fallback_event
            timed_emitter.end_step("sql_execution")
            ctx.sql_phase_status = "sql_execution_failed"
            retry_summary(
                stage="sql_generation",
                attempts=attempt_logs,
                final_status=ctx.sql_phase_status,
                session_id=session_id,
                flow=self.flow_label,
            )
            return
        exec_elapsed = int((time.time() - exec_start) * 1000)
        timed_emitter.end_step("sql_execution")
        ctx.data = data
        ctx.exec_elapsed_ms = exec_elapsed
        ctx.planner_result.data_row_count = len(data)
        execution_summary = EventEmitter.result(
            "sql_execution",
            {
                "row_count": len(data),
                "elapsed_ms": exec_elapsed,
            },
        )
        execution_summary["event"] = "execution_stats"
        execution_summary["data"]["ts"] = datetime.utcnow().isoformat()
        yield execution_summary
        ctx.sql_phase_status = "ok"
        retry_summary(
            stage="sql_generation",
            attempts=attempt_logs,
            final_status=ctx.sql_phase_status,
            session_id=session_id,
            flow=self.flow_label,
        )

    def _compose_analysis_summary(
        self,
        *,
        ctx: PlannerPhaseContext,
        data: List[Dict[str, Any]],
        analysis_text: str,
        tool_bundle: Dict[str, Any],
    ) -> Tuple[str, Dict[str, bool], Dict[str, Any]]:
        tool_bundle = tool_bundle or {}

        def _scale_percent(value: Any) -> Optional[float]:
            try:
                numeric = float(value)
            except (TypeError, ValueError):
                return None
            if abs(numeric) <= 1:
                return numeric * 100
            return numeric

        def _format_percent(value: Any) -> str:
            scaled = _scale_percent(value)
            if scaled is None:
                return "n/a"
            return f"{scaled:.1f}%"

        def _is_share_field(name: str) -> bool:
            lowered = name.lower()
            if 'market_share' in lowered:
                return True
            if 'share_' in lowered and any(token in lowered for token in ('percent', 'pct', 'percentage')):
                return True
            return lowered.endswith('_share_pct') or lowered.endswith('_share_percent')

        def _detect_share_column(row: Dict[str, Any]) -> Optional[str]:
            preferred = ['market_share_percent', 'market_share_pct']
            for key in preferred:
                if key in row:
                    return key
            for key in row.keys():
                if _is_share_field(key):
                    return key
            return None

        def _extract_share_series(rows: List[Dict[str, Any]], share_key: str) -> Tuple[List[Tuple[str, float]], Optional[str]]:
            timeline: List[Tuple[Tuple[int, int, int], str, float]] = []
            ticker: Optional[str] = None
            for idx, row in enumerate(rows):
                ticker_val = row.get('ticker')
                if isinstance(ticker_val, str) and ticker_val:
                    if ticker is None:
                        ticker = ticker_val
                    elif ticker_val != ticker:
                        continue
                scaled_value = _scale_percent(row.get(share_key))
                if scaled_value is None:
                    continue
                year = row.get('calendar_year')
                quarter_num = row.get('calendar_quarter_num')
                quarter_label = row.get('calendar_quarter')
                if year is not None:
                    try:
                        year_int = int(year)
                    except (TypeError, ValueError):
                        year_int = None
                    if quarter_label:
                        label = f"{year_int} {quarter_label}" if year_int is not None else str(quarter_label)
                        sort_key = (year_int or 0, int(quarter_num or 0), idx)
                    elif quarter_num is not None:
                        label = f"{year} Q{quarter_num}"
                        sort_key = (int(year or 0), int(quarter_num), idx)
                    else:
                        label = str(year)
                        sort_key = (int(year or 0), 0, idx)
                elif row.get('period'):
                    label = str(row['period'])
                    sort_key = (0, 0, idx)
                elif row.get('date'):
                    label = str(row['date'])
                    sort_key = (0, 0, idx)
                else:
                    label = f"row {idx + 1}"
                    sort_key = (0, 0, idx)
                timeline.append((sort_key, label, scaled_value))
            timeline.sort(key=lambda item: item[0])
            return [(label, value) for _, label, value in timeline], ticker

        market_lines: List[str] = []
        share_column = _detect_share_column(data[0]) if data else None
        share_points: List[Tuple[str, float]] = []
        ticker: Optional[str] = None
        if share_column:
            share_points, ticker = _extract_share_series(data, share_column)
        company_label = ctx.intent.slots_detected.get('company') if ctx.intent and ctx.intent.slots_detected else None
        if not company_label and ticker:
            company_label = ticker
        if share_points:
            first_period, first_value = share_points[0]
            last_period, last_value = share_points[-1]
            subject = company_label or 'The company'
            if first_value is not None and last_value is not None:
                delta_pp = last_value - first_value
                delta_text = f" ({delta_pp:+.1f} pp)" if delta_pp is not None else ''
                market_lines.append(
                    f"{subject} share moved from {_format_percent(first_value)} in {first_period} to {_format_percent(last_value)} in {last_period}{delta_text}."
                )
            peak_period, peak_value = max(share_points, key=lambda item: item[1] if item[1] is not None else float('-inf'))
            if peak_value is not None:
                window = min(3, len(share_points))
                window_values = [pt[1] for pt in share_points[-window:] if pt[1] is not None]
                if window_values:
                    avg_value = statistics.mean(window_values)
                    market_lines.append(
                        f"Peak share {_format_percent(peak_value)} in {peak_period}; trailing {window}-period avg {_format_percent(avg_value)}."
                    )
                else:
                    market_lines.append(f"Peak share {_format_percent(peak_value)} in {peak_period}.")

        web_lines: List[str] = []
        web_context = tool_bundle.get('web_context') if isinstance(tool_bundle, dict) else None
        if isinstance(web_context, dict):
            summary = web_context.get('summary')
            if isinstance(summary, str):
                summary = summary.strip()
                if summary:
                    web_lines.append(summary)
            snippets = web_context.get('snippets')
            if isinstance(snippets, list):
                seen = set()
                for snippet in snippets:
                    text = ''
                    title = None
                    if isinstance(snippet, dict):
                        title = snippet.get('title')
                        text = snippet.get('snippet') or snippet.get('summary') or snippet.get('text') or ''
                    else:
                        text = str(snippet)
                    parts = []
                    if title:
                        parts.append(str(title).strip())
                    if text:
                        parts.append(str(text).strip())
                    line = ': '.join(part for part in parts if part)
                    if not line or line in seen:
                        continue
                    seen.add(line)
                    web_lines.append(line)
                    if len(web_lines) >= 4:
                        break

        stock_lines: List[str] = []
        stock_widget = tool_bundle.get('stock_widget') if isinstance(tool_bundle, dict) else None
        if isinstance(stock_widget, dict):
            symbols = stock_widget.get('symbols') or stock_widget.get('original')
            if isinstance(symbols, list) and symbols:
                joined = ', '.join(str(sym).upper() for sym in symbols if sym)
                if joined:
                    stock_lines.append(f"Symbols: {joined}")
            generated_at = stock_widget.get('generated_at')
            if isinstance(generated_at, str) and generated_at:
                stock_lines.append(f"Snapshot generated at {generated_at}.")

        cleaned_llm = (analysis_text or '').strip()
        sections: List[str] = []
        if market_lines:
            sections.append("### Market Share Trend\n" + "\n".join(f"- {line}" for line in market_lines))
        if web_lines:
            sections.append("### Web Highlights\n" + "\n".join(f"- {line}" for line in web_lines))
        if stock_lines:
            sections.append("### Market Snapshot\n" + "\n".join(f"- {line}" for line in stock_lines))
        if cleaned_llm:
            sections.append("### LLM Commentary\n" + cleaned_llm)
        structured_summary = "\n\n".join(section.strip() for section in sections if section).strip()
        if not structured_summary:
            structured_summary = cleaned_llm

        analysis_sources = {
            'sql': bool(market_lines),
            'web': bool(web_lines),
            'market': bool(stock_lines),
            'llm': bool(cleaned_llm),
        }
        section_details = {
            'market_trend': market_lines,
            'web_highlights': web_lines,
            'market_snapshot': stock_lines,
            'llm_commentary': cleaned_llm,
        }
        return structured_summary, analysis_sources, section_details

    def _validate_sql_with_timing(
        self,
        sql: str,
        plan: QueryPlanModel,
        *,
        limit_guard: int,
    ) -> Tuple[bool, List[str], int]:
        start = time.time()
        database_cfg = CONFIGS.database or {}
        tables_cfg = database_cfg.get('tables') if isinstance(database_cfg, dict) else None
        allowed_tables = list(tables_cfg.keys()) if isinstance(tables_cfg, dict) else None
        ok, issues = validate_sql(
            sql,
            allowed_tables=allowed_tables,
            max_limit=limit_guard,
            granularity=getattr(plan, 'granularity', 'annual') or 'annual',
        )
        elapsed = int((time.time() - start) * 1000)
        return ok, issues, elapsed


async def _initialize_context(self, query: str, session_id: Optional[str]) -> PlannerPhaseContext:
    workflow_start = time.time()
    resolved_session = session_id or str(uuid.uuid4())
    timed_emitter = TimedEventEmitter(session_id=resolved_session, flow=self.flow_label)
    return PlannerPhaseContext(
        query=query,
        session_id=resolved_session,
        workflow_start=workflow_start,
        timed_emitter=timed_emitter,
        configs=CONFIGS.__dict__,
        parallelism_enabled=self.parallelism_enabled,
    )


async def _classification_phase(self, ctx: PlannerPhaseContext) -> AsyncGenerator[Dict[str, Any], None]:
    timed_emitter = ctx.timed_emitter
    timed_emitter.start_step("classification")
    classification_started_ts = datetime.utcnow().isoformat()
    model_name = "gpt-5-nano-2025-08-07"
    yield {
        "event": "classification_started",
        "data": {
            "message": "Starting query classification...",
            "model": model_name,
            "ts": classification_started_ts,
        },
    }
    classification: Optional[OffTopicClassifierSchema] = None
    try:
        classification = await classify_query_async(
            ctx.query,
            session_id=ctx.session_id,
            model=model_name,
            reasoning_effort="low",
        )
    except Exception as exc:
        logger.exception("[CLASSIFICATION] LLM classification failed: %s", exc)
        error_event = EventEmitter.error(
            "classification",
            "Classification model unavailable",
            details={"error": str(exc)},
            code="CLASSIFIER_ERROR",
        )
        error_event["data"]["ts"] = datetime.utcnow().isoformat()
        yield error_event
        raise
    if classification is None:
        raise RuntimeError("Classifier returned no response")
    ctx.classification = classification
    ctx.planner_result.metadata['classification'] = classification.model_dump()
    ctx.is_financial_query = bool(getattr(classification, "is_financial_query", False))
    reasoning_message = f"LLM classified topic '{classification.topic_category}'"
    yield {
        "event": "classification_reasoning",
        "data": {
            "thinking": reasoning_message,
            "confidence": classification.confidence,
            "category": classification.topic_category,
            "ts": datetime.utcnow().isoformat(),
        },
    }
    classification_elapsed = timed_emitter.end_step("classification")
    classification_complete = {
        "event": "classification_complete",
        "data": {
            "is_financial": ctx.is_financial_query,
            "category": classification.topic_category,
            "confidence": classification.confidence,
            "ts": datetime.utcnow().isoformat(),
        },
    }
    if classification_elapsed:
        classification_complete["data"]["elapsed_ms"] = classification_elapsed
    yield classification_complete
    if not ctx.is_financial_query:
        decline_message = classification.polite_decline_message or "I am here for financial analytics insights. Try asking about revenue trends or market share."
        if len(decline_message) > 200:
            decline_message = decline_message[:197] + "..."
        final_event = {
            "event": "final_answer",
            "data": {
                "message": decline_message,
                "confidence": classification.confidence,
                "category": classification.topic_category,
                "ts": datetime.utcnow().isoformat(),
            },
        }
        if getattr(classification, "suggested_rephrase", None):
            final_event["data"]["suggested_rephrase"] = classification.suggested_rephrase
        yield final_event
        result_event = EventEmitter.result("planner_result", ctx.planner_result.model_dump())
        result_event["event"] = "planner_result"
        result_event["data"]["ts"] = datetime.utcnow().isoformat()
        yield result_event
        workflow_summary = {
            "status": "off_topic",
            "category": classification.topic_category,
            "total_elapsed_ms": int((time.time() - ctx.workflow_start) * 1000),
        }
        workflow_complete = EventEmitter.result("workflow_complete", workflow_summary)
        workflow_complete["event"] = "workflow_complete"
        workflow_complete["data"]["ts"] = datetime.utcnow().isoformat()
        yield workflow_complete

async def _intent_phase(self, ctx: PlannerPhaseContext) -> AsyncGenerator[Dict[str, Any], None]:
    timed_emitter = ctx.timed_emitter
    intent_progress = EventEmitter.progress("intent_detection", "Detecting intent...")
    intent_progress["data"]["ts"] = datetime.utcnow().isoformat()
    yield intent_progress
    timed_emitter.start_step("intent_detection")
    yield {
        "event": "intent_detection_started",
        "data": {
            "message": "Analyzing query intent...",
            "ts": datetime.utcnow().isoformat(),
        },
    }
    intent_start = time.time()
    intent: IntentModel = await asyncio.to_thread(
        detect_intent_with_clarifications,
        ctx.query,
        CONFIGS.__dict__,
        session_id=ctx.session_id,
    )
    intent.slots_detected["original_query"] = ctx.query
    ctx.intent = intent
    ctx.planner_result.intent = intent
    intent_elapsed = timed_emitter.end_step("intent_detection")
    intent_complete = {
        "event": "intent_detection_complete",
        "data": {
            "intent_key": intent.intent_key,
            "confidence": intent.confidence,
            "slots_detected": intent.slots_detected,
            "ts": datetime.utcnow().isoformat(),
            "elapsed_ms": int((time.time() - intent_start) * 1000),
        },
    }
    if intent_elapsed:
        intent_complete["data"]["elapsed_ms"] = intent_elapsed
    yield intent_complete
    ctx.provisional_plan = build_query_plan(intent, CONFIGS.__dict__)
    ctx.template = choose_template(intent, ctx.provisional_plan, CONFIGS.__dict__)
    official_clarifications = compute_required_clarifications(
        intent, ctx.provisional_plan, ctx.template, CONFIGS.__dict__
    )
    deduped_requests: List[ClarifyRequestModel] = []
    seen_slots: set[str] = set()
    for request in official_clarifications:
        if request.slot in seen_slots:
            continue
        seen_slots.add(request.slot)
        deduped_requests.append(request)
    ctx.clarifications = deduped_requests
    ctx.planner_result.clarification_requests = list(deduped_requests)
    ctx.assumptions = []
    ctx.clarification_rounds = 0
    clarifications_needed = bool(deduped_requests)
    confidence_sufficient = (intent.confidence or 0.0) >= 0.8
    intent_status_event = (
        EventEmitter.intent_draft(
            confidence=intent.confidence,
            clarifications_needed=True,
            clarifications_count=len(deduped_requests),
        )
        if clarifications_needed or not confidence_sufficient
        else EventEmitter.intent_decided(
            key=intent.intent_key,
            confidence=intent.confidence,
            clarifications_needed=False,
        )
    )
    intent_status_event["data"]["ts"] = datetime.utcnow().isoformat()
    if intent_elapsed:
        intent_status_event["data"]["elapsed_ms"] = intent_elapsed
    yield intent_status_event
async def _clarification_phase(self, ctx: PlannerPhaseContext) -> AsyncGenerator[Dict[str, Any], None]:
    intent = ctx.intent
    provisional_plan = ctx.provisional_plan
    template = ctx.template
    if intent is None or provisional_plan is None:
        return
    timed_emitter = ctx.timed_emitter
    session_id = ctx.session_id
    official_clarifications = list(ctx.clarifications)
    assumptions = list(ctx.assumptions)
    rounds = ctx.clarification_rounds
    all_answered_slots: set[str] = set()
    if official_clarifications:
        timed_emitter.start_step("clarification")
        missing_slots = [req.slot for req in official_clarifications]
        yield {
            "event": "clarification_needed",
            "data": {
                "missing_fields": missing_slots,
                "ts": datetime.utcnow().isoformat(),
            },
        }
        clarification_progress = EventEmitter.progress(
            "clarification", "Clarifying requirements..."
        )
        clarification_progress["data"]["ts"] = datetime.utcnow().isoformat()
        yield clarification_progress
        yield {
            "event": "clarification_loop_start",
            "data": {
                "total_clarifications": len(official_clarifications),
                "missing_slots": missing_slots,
                "ts": datetime.utcnow().isoformat(),
            },
        }
        while official_clarifications and rounds < 3:
            slot_request = official_clarifications[0]
            request_payload = {
                "request_id": slot_request.request_id,
                "slot": slot_request.slot,
                "question": slot_request.question,
                "type": slot_request.type,
                "options": slot_request.options,
                "default": slot_request.default,
                "proposed": slot_request.proposed,
                "proposed_confidence": slot_request.proposed_confidence,
                "reason": slot_request.reason,
                "required": slot_request.required,
                "round": rounds + 1,
                "remaining": len(official_clarifications),
            }
            clarification_event = EventEmitter.clarification_request(
                session_id, request_payload
            )
            clarification_event["data"]["ts"] = datetime.utcnow().isoformat()
            yield clarification_event
            try:
                answer = await asyncio.wait_for(
                    wait_for_answer_blocking(session_id, slot_request.request_id),
                    timeout=60.0,
                )
            except asyncio.TimeoutError:
                timeout_event = EventEmitter.progress(
                    "clarification_timeout",
                    f"Timeout waiting for {slot_request.slot} clarification. Using default value.",
                )
                timeout_event["data"]["ts"] = datetime.utcnow().isoformat()
                yield timeout_event
                if slot_request.default:
                    from analytics.core.types import ClarifyAnswerModel
                    answer = ClarifyAnswerModel(
                        session_id=session_id,
                        request_id=slot_request.request_id,
                        slot=slot_request.slot,
                        value=slot_request.default,
                        ts=datetime.utcnow().isoformat(),
                    )
                else:
                    official_clarifications.pop(0)
                    continue
            if answer:
                is_valid = validate_clarification_answer(answer, slot_request)
                if is_valid:
                    ack_event = EventEmitter.clarification_ack(
                        session_id, slot_request.request_id, answer.value
                    )
                    ack_event["data"].update(
                        {
                            "slot": slot_request.slot,
                            "ts": datetime.utcnow().isoformat(),
                        }
                    )
                    yield ack_event
                    intent, provisional_plan, merge_assumptions = await merge_answers(
                        intent, provisional_plan, [answer], CONFIGS.__dict__
                    )
                    assumptions.extend(merge_assumptions)
                    template = choose_template(
                        intent, provisional_plan, CONFIGS.__dict__
                    )
                    new_clarifications = compute_required_clarifications(
                        intent, provisional_plan, template, CONFIGS.__dict__
                    )
                    remaining_original = official_clarifications[1:]
                    all_answered_slots.add(answer.slot)
                    combined_requests: List[ClarifyRequestModel] = []
                    for new_req in new_clarifications:
                        if new_req.slot not in all_answered_slots and all(
                            new_req.slot != existing.slot for existing in combined_requests
                        ):
                            combined_requests.append(new_req)
                    for orig_req in remaining_original:
                        if (
                            orig_req.slot not in all_answered_slots
                            and all(orig_req.slot != existing.slot for existing in combined_requests)
                        ):
                            combined_requests.append(orig_req)
                    official_clarifications = combined_requests
                    rounds += 1
                else:
                    error_message = get_validation_error_message(answer, slot_request)
                    error_event = EventEmitter.progress(
                        "clarification_error",
                        error_message or f"Invalid value for {slot_request.slot}: {answer.value}",
                    )
                    error_event["data"]["ts"] = datetime.utcnow().isoformat()
                    yield error_event
                    official_clarifications = official_clarifications[1:]
            else:
                official_clarifications = official_clarifications[1:]
        clarification_elapsed = timed_emitter.end_step("clarification")
        resolved_event = EventEmitter.intent_resolved(
            key=intent.intent_key,
            confidence=intent.confidence,
            rounds=rounds,
        )
        resolved_event["data"].update(
            {
                "assumptions": assumptions,
                "ts": datetime.utcnow().isoformat(),
            }
        )
        if clarification_elapsed:
            resolved_event["data"]["elapsed_ms"] = clarification_elapsed
        yield resolved_event
    else:
        yield {
            "event": "clarification_skipped",
            "data": {
                "reason": "All required slots satisfied",
                "ts": datetime.utcnow().isoformat(),
            },
        }
    ctx.intent = intent
    ctx.provisional_plan = provisional_plan
    ctx.template = template
    ctx.assumptions = assumptions
    ctx.clarification_rounds = rounds
    ctx.clarifications = official_clarifications
async def _plan_phase(self, ctx: PlannerPhaseContext) -> AsyncGenerator[Dict[str, Any], None]:
    intent = ctx.intent
    provisional_plan = ctx.provisional_plan
    template = ctx.template
    if intent is None or provisional_plan is None:
        return
    ctx.plan = provisional_plan
    intent_finalized_event = {
        "event": "intent_finalized",
        "data": {
            "intent_key": intent.intent_key,
            "confidence": intent.confidence,
            "assumptions": ctx.assumptions,
            "ts": datetime.utcnow().isoformat(),
        },
    }
    if ctx.clarification_rounds:
        intent_finalized_event["data"]["clarification_rounds"] = ctx.clarification_rounds
    yield intent_finalized_event
    criteria_model = intent_to_sql_criteria(intent, CONFIGS.__dict__)
    criteria_payload = criteria_model.dict()
    criteria_payload["ts"] = datetime.utcnow().isoformat()
    yield {
        "event": "criteria_ready",
        "data": criteria_payload,
    }
    elapsed_ms = int((time.time() - ctx.workflow_start) * 1000)
    plan_event = EventEmitter.result(
        "plan_built",
        {
            "granularity": provisional_plan.granularity,
            "comparison": provisional_plan.comparison,
            "metrics_count": len(provisional_plan.metrics),
        },
    )
    plan_event["event"] = "plan_built"
    plan_event["data"].update(
        {
            "ts": datetime.utcnow().isoformat(),
            "elapsed_ms": elapsed_ms,
            "parallelism_enabled": ctx.parallelism_enabled,
        }
    )
    yield plan_event
    if ctx.parallelism_enabled:
        async for tool_event in run_tool_parallelism(ctx):
            yield tool_event

    template_info = None
    if template and intent.intent_key:
        queries_config = CONFIGS.__dict__.get("queries", {})
        patterns = queries_config.get("query_patterns", {})
        if intent.intent_key in patterns:
            pattern = patterns[intent.intent_key]
            template_info = {
                "id": intent.intent_key,
                "name": pattern.get("name", intent.intent_key),
                "description": pattern.get(
                    "description", "No description available"
                ),
            }
    template_event = EventEmitter.result(
        "template_selected",
        {
            "template_id": intent.intent_key if template else None,
            "has_template": template is not None,
        },
    )
    template_event["event"] = "template_selected"
    template_event["data"]["ts"] = datetime.utcnow().isoformat()
    if template_info:
        template_event["data"]["template"] = template_info
    yield template_event
    catalog_lookup_start = time.time()
    candidate_templates: List[Dict[str, Any]] = []
    try:
        candidate_templates = await fetch_templates_for_intent(
            intent,
            query=ctx.query,
            top_k=3,
            store=self.config_store,
        )
    except Exception as catalog_error:
        logger.warning("[SQL_CATALOG] Template lookup failed: %s", catalog_error)
    catalog_elapsed = int((time.time() - catalog_lookup_start) * 1000)
    selected_template_id = None
    if isinstance(template, dict):
        selected_template_id = template.get("id") or template.get("name")
    if candidate_templates:
        catalog_event = EventEmitter.catalog_trace(
            "sql_compilation",
            templates=candidate_templates,
            intent_key=intent.intent_key,
            query=ctx.query,
            selected_template=selected_template_id,
            elapsed_ms=catalog_elapsed,
            session_id=ctx.session_id,
            flow=getattr(self, "flow_label", None),
        )
        catalog_event["data"]["ts"] = datetime.utcnow().isoformat()
        yield catalog_event
    ctx.candidate_templates = candidate_templates
    ctx.selected_template_id = selected_template_id
    def _get_company_display(self, intent: IntentModel, provisional_plan: Optional[QueryPlanModel] = None) -> str:
        """Generate smart company display based on intent and plan context."""
        company = intent.slots_detected.get('company')
        comparison = provisional_plan.comparison if provisional_plan else None
        # Smart display based on context
        if comparison == 'all':
            return 'All Companies'
        elif comparison == 'vs_avg':
            return 'Industry Average'
        elif company:
            return company
        else:
            return 'Unknown'
    async def events(self, query: str, session_id: Optional[str] = None) -> AsyncGenerator[Dict[str, Any], None]:
        """Enhanced workflow with structured decision events and timing."""
        ctx_candidate = _initialize_context(self, query, session_id)
        if inspect.isawaitable(ctx_candidate):
            ctx = await ctx_candidate
        else:
            ctx = ctx_candidate
        session_id = ctx.session_id
        timed_emitter = ctx.timed_emitter
        workflow_start = ctx.workflow_start
        yield EventEmitter.session_started(session_id)
        async for event in _classification_phase(self, ctx):
            yield event
        if not ctx.is_financial_query:
            return
        async for event in _intent_phase(self, ctx):
            yield event
        async for event in _clarification_phase(self, ctx):
            yield event
        async for event in _plan_phase(self, ctx):
            yield event
        intent = ctx.intent
        provisional_plan = ctx.plan or ctx.provisional_plan
        template = ctx.template
        candidate_templates = ctx.candidate_templates
        selected_template_id = ctx.selected_template_id
        if not intent or not provisional_plan:
            return
        plan = provisional_plan
        async for event in self._sql_phase(
            ctx,
            query=query,
            intent=intent,
            plan=plan,
            session_id=session_id,
            candidate_templates=candidate_templates,
            selected_template_id=selected_template_id,
            timed_emitter=timed_emitter,
            allow_policy_override=True,
        ):
            yield event

        if ctx.sql_phase_status != "ok":
            workflow_complete = EventEmitter.result(
                "workflow_complete",
                {
                    "status": ctx.sql_phase_status,
                    "total_elapsed_ms": int((time.time() - workflow_start) * 1000),
                },
            )
            workflow_complete["event"] = "workflow_complete"
            workflow_complete["data"]["ts"] = datetime.utcnow().isoformat()
            yield workflow_complete
            return

        sql = ctx.sql
        data = ctx.data

        # 10) Chart Planning Phase
        # 10) Chart Planning Phase
        chart_progress = EventEmitter.progress(
            "chart_generation", "Planning chart..."
        )
        chart_progress["data"]["ts"] = datetime.utcnow().isoformat()
        yield chart_progress
        chart_start = time.time()
        chart_plan = plan_chart_rule_based(data, query, intent.intent_key)
        logger.info(f"[CHART_DEBUG] Chart plan generated: chart_type={chart_plan.chart_type}, series_count={len(chart_plan.series)}")
        spec = build_chart_spec(
            data,
            chart_plan.dict(),
            CONFIGS.charts,
            intent_key=intent.intent_key,
            comparison=plan.comparison,
        )
        logger.info(f"[CHART_DEBUG] Chart spec built: series_count={len(spec.get('series', []))}, has_xAxis={bool(spec.get('xAxis'))}")
        chart_design = _generate_chart_design(intent.intent_key, plan, data, spec)
        spec.setdefault("meta", {}).setdefault("chartDesign", chart_design)
        ctx.planner_result.chart_summary = {
            "chart_type": chart_plan.chart_type,
            "series_count": len(chart_plan.series),
            "design": chart_design,
        }
        chart_elapsed = int((time.time() - chart_start) * 1000)
        chart_event = EventEmitter.result(
            "chart_planned",
            {
                "chart_type": chart_plan.chart_type,
                "series_count": len(chart_plan.series),
            },
        )
        chart_event["event"] = "chart_planned"
        chart_event["data"].update(
            {
                "ts": datetime.utcnow().isoformat(),
                "elapsed_ms": chart_elapsed,
            }
        )
        yield chart_event
        try:
            ChartSpecModel(**spec)
            logger.info(f"[CHART_DEBUG] ChartSpecModel validation passed, emitting chart_generated event")
            generated_chart = EventEmitter.result(
                "chart_generated",
                {
                    "chart_type": spec.get("meta", {}).get("chartDesign", {}).get(
                        "chart_type", "unknown"
                    ),
                    "chart_spec": spec,
                },
                key="chart_spec",
            )
            generated_chart["event"] = "chart_generated"
            generated_chart["data"]["ts"] = datetime.utcnow().isoformat()
            logger.info(f"[CHART_DEBUG] Chart_generated event payload: series_count={len(generated_chart.get('data', {}).get('chart_spec', {}).get('series', []))}")
            yield generated_chart
        except ValidationError as ve:
            warning_event = EventEmitter.progress(
                "warning", f"Chart spec validation warning: {str(ve)}"
            )
            warning_event["data"]["ts"] = datetime.utcnow().isoformat()
            yield warning_event
            fallback_chart = EventEmitter.result(
                "chart_generated",
                {
                    "chart_type": spec.get("meta", {}).get("chartDesign", {}).get(
                        "chart_type", "unknown"
                    ),
                    "chart_spec": spec,
                },
                key="chart_spec",
            )
            fallback_chart["event"] = "chart_generated"
            fallback_chart["data"]["ts"] = datetime.utcnow().isoformat()
            yield fallback_chart
        # 11) Analysis Generation Phase
        analysis_progress = EventEmitter.progress(
            "analysis_generation", "Generating insights..."
        )
        analysis_progress["data"]["ts"] = datetime.utcnow().isoformat()
        yield analysis_progress
        analysis_start = time.time()
        full_analysis = ""
        async for text_chunk in stream_insights_llm(
            data, sql, query, session_id=session_id
        ):
            if text_chunk:
                full_analysis += text_chunk
                streaming_event = {
                    "event": "analysis_streaming",
                    "data": {
                        "step": "analysis_generation",
                        "partial_analysis": text_chunk,
                        "chunk_length": len(text_chunk),
                        "ts": datetime.utcnow().isoformat(),
                    },
                }
                log_analysis_chunk(
                    chunk=text_chunk,
                    step="analysis_generation",
                    role=None,
                    session_id=session_id,
                    flow=getattr(self, "flow_label", None),
                )
                yield streaming_event
        analysis_elapsed = int((time.time() - analysis_start) * 1000)
        tool_bundle = collect_tool_bundle(
            manifest=getattr(ctx, "tool_parallel_manifest", None),
            results=getattr(ctx, "tool_parallel_results", None),
        ) or {}
        structured_summary, analysis_sources, analysis_sections = self._compose_analysis_summary(
            ctx=ctx,
            data=data,
            analysis_text=full_analysis,
            tool_bundle=tool_bundle,
        )
        ctx.planner_result.analysis = structured_summary
        ctx.planner_result.metadata["analysis_sources"] = analysis_sources
        ctx.planner_result.metadata["analysis_sections"] = analysis_sections
        ctx.planner_result.metadata["llm_analysis"] = full_analysis
        analysis_payload = {
            "analysis_length": len(structured_summary or ''),
            "analysis": structured_summary,
            "analysis_sources": analysis_sources,
            "analysis_sections": analysis_sections,
            "llm_analysis": full_analysis,
        }
        if tool_bundle:
            analysis_payload.update(tool_bundle)
        analysis_complete = EventEmitter.result(
            "analysis_complete",
            analysis_payload,
            key="analysis",
        )
        analysis_complete["event"] = "analysis_complete"
        analysis_data = analysis_complete.get("data", {})
        if isinstance(analysis_data.get("analysis"), dict):
            flattened_analysis = analysis_data.pop("analysis")
            analysis_data.update(flattened_analysis)
        analysis_data.update(
            {
                "ts": datetime.utcnow().isoformat(),
                "elapsed_ms": analysis_elapsed,
            }
        )
        yield analysis_complete
        # Cleanup expired sessions
        from analytics.core.clarify import get_session_store
        session_store = await get_session_store()
        await session_store.cleanup_expired()
        total_elapsed = int((time.time() - workflow_start) * 1000)
        result_event = EventEmitter.result(
            "planner_result", ctx.planner_result.model_dump()
        )
        result_event["event"] = "planner_result"
        result_event["data"]["ts"] = datetime.utcnow().isoformat()
        yield result_event
        workflow_complete = EventEmitter.result(
            "workflow_complete", {"total_elapsed_ms": total_elapsed}
        )
        workflow_complete["event"] = "workflow_complete"
        workflow_complete["data"]["ts"] = datetime.utcnow().isoformat()
        yield workflow_complete
async def _planner_events(
    self,
    query: str,
    session_id: Optional[str] = None,
    *,
    skip_preflight: bool = False,
) -> AsyncGenerator[Dict[str, Any], None]:
    """Enhanced workflow with structured decision events and timing."""
    ctx_candidate = _initialize_context(self, query, session_id)
    if inspect.isawaitable(ctx_candidate):
        ctx = await ctx_candidate
    else:
        ctx = ctx_candidate
    session_id = ctx.session_id
    timed_emitter = ctx.timed_emitter
    workflow_start = ctx.workflow_start
    yield EventEmitter.session_started(session_id)
    if not skip_preflight:
        async for event in _classification_phase(self, ctx):
            yield event
        if not ctx.is_financial_query:
            return
    else:
        classification_meta = ctx.planner_result.metadata.setdefault("classification", {})
        classification_meta.update(
            {
                "status": "skipped",
                "reason": "preflight_disabled",
                "ts": datetime.utcnow().isoformat(),
            }
        )
    async for event in _intent_phase(self, ctx):
        yield event
    async for event in _clarification_phase(self, ctx):
        yield event
    async for event in _plan_phase(self, ctx):
        yield event
    intent = ctx.intent
    provisional_plan = ctx.plan or ctx.provisional_plan
    template = ctx.template
    candidate_templates = ctx.candidate_templates
    selected_template_id = ctx.selected_template_id
    if not intent or not provisional_plan:
        return
    plan = provisional_plan
    async for event in self._sql_phase(
        ctx,
        query=query,
        intent=intent,
        plan=plan,
        session_id=session_id,
        candidate_templates=candidate_templates,
        selected_template_id=selected_template_id,
        timed_emitter=timed_emitter,
        allow_policy_override=True,
    ):
        yield event

    if ctx.sql_phase_status != "ok":
        workflow_complete = EventEmitter.result(
            "workflow_complete",
            {
                "status": ctx.sql_phase_status,
                "total_elapsed_ms": int((time.time() - workflow_start) * 1000),
            },
        )
        workflow_complete["event"] = "workflow_complete"
        workflow_complete["data"]["ts"] = datetime.utcnow().isoformat()
        yield workflow_complete
        return

    sql = ctx.sql
    data = ctx.data

    # 10) Chart Planning Phase
    # 10) Chart Planning Phase
    chart_progress = EventEmitter.progress(
        "chart_generation", "Planning chart..."
    )
    chart_progress["data"]["ts"] = datetime.utcnow().isoformat()
    yield chart_progress
    chart_start = time.time()
    chart_plan = plan_chart_rule_based(data, query, intent.intent_key)
    logger.info(f"[CHART_DEBUG] Chart plan generated: chart_type={chart_plan.chart_type}, series_count={len(chart_plan.series)}")
    spec = build_chart_spec(
        data,
        chart_plan.dict(),
        CONFIGS.charts,
        intent_key=intent.intent_key,
        comparison=plan.comparison,
    )
    logger.info(f"[CHART_DEBUG] Chart spec built: series_count={len(spec.get('series', []))}, has_xAxis={bool(spec.get('xAxis'))}")
    chart_design = _generate_chart_design(intent.intent_key, plan, data, spec)
    spec.setdefault("meta", {}).setdefault("chartDesign", chart_design)
    ctx.planner_result.chart_summary = {
        "chart_type": chart_plan.chart_type,
        "series_count": len(chart_plan.series),
        "design": chart_design,
    }
    chart_elapsed = int((time.time() - chart_start) * 1000)
    chart_event = EventEmitter.result(
        "chart_planned",
        {
            "chart_type": chart_plan.chart_type,
            "series_count": len(chart_plan.series),
        },
    )
    chart_event["event"] = "chart_planned"
    chart_event["data"].update(
        {
            "ts": datetime.utcnow().isoformat(),
            "elapsed_ms": chart_elapsed,
        }
    )
    yield chart_event
    try:
        ChartSpecModel(**spec)
        generated_chart = EventEmitter.result(
            "chart_generated",
            {
                "chart_type": spec.get("meta", {}).get("chartDesign", {}).get(
                    "chart_type", "unknown"
                ),
                "chart_spec": spec,
            },
            key="chart_spec",
        )
        generated_chart["event"] = "chart_generated"
        generated_chart["data"]["ts"] = datetime.utcnow().isoformat()
        yield generated_chart
    except ValidationError as ve:
        warning_event = EventEmitter.progress(
            "warning", f"Chart spec validation warning: {str(ve)}"
        )
        warning_event["data"]["ts"] = datetime.utcnow().isoformat()
        yield warning_event
        fallback_chart = EventEmitter.result(
            "chart_generated",
            {
                "chart_type": spec.get("meta", {}).get("chartDesign", {}).get(
                    "chart_type", "unknown"
                ),
                "chart_spec": spec,
            },
            key="chart_spec",
        )
        fallback_chart["event"] = "chart_generated"
        fallback_chart["data"]["ts"] = datetime.utcnow().isoformat()
        yield fallback_chart
    # 11) Analysis Generation Phase
    analysis_progress = EventEmitter.progress(
        "analysis_generation", "Generating insights..."
    )
    analysis_progress["data"]["ts"] = datetime.utcnow().isoformat()
    yield analysis_progress
    analysis_start = time.time()
    full_analysis = ""
    async for text_chunk in stream_insights_llm(
        data, sql, query, session_id=session_id
    ):
        if text_chunk:
            full_analysis += text_chunk
            streaming_event = {
                "event": "analysis_streaming",
                "data": {
                    "step": "analysis_generation",
                    "partial_analysis": text_chunk,
                    "chunk_length": len(text_chunk),
                    "ts": datetime.utcnow().isoformat(),
                },
            }
            log_analysis_chunk(
                chunk=text_chunk,
                step="analysis_generation",
                role=None,
                session_id=session_id,
                flow=getattr(self, "flow_label", None),
            )
            yield streaming_event
    analysis_elapsed = int((time.time() - analysis_start) * 1000)
    tool_bundle = collect_tool_bundle(
        manifest=getattr(ctx, "tool_parallel_manifest", None),
        results=getattr(ctx, "tool_parallel_results", None),
    ) or {}
    structured_summary, analysis_sources, analysis_sections = self._compose_analysis_summary(
        ctx=ctx,
        data=data,
        analysis_text=full_analysis,
        tool_bundle=tool_bundle,
    )
    ctx.planner_result.analysis = structured_summary
    ctx.planner_result.metadata["analysis_sources"] = analysis_sources
    ctx.planner_result.metadata["analysis_sections"] = analysis_sections
    ctx.planner_result.metadata["llm_analysis"] = full_analysis
    analysis_payload = {
        "analysis_length": len(structured_summary or ''),
        "analysis": structured_summary,
        "analysis_sources": analysis_sources,
        "llm_analysis": full_analysis,
    }
    if tool_bundle:
        analysis_payload.update(tool_bundle)
    analysis_complete = EventEmitter.result(
        "analysis_complete",
        analysis_payload,
        key="analysis",
    )
    analysis_complete["event"] = "analysis_complete"
    analysis_data = analysis_complete.get("data", {})
    if isinstance(analysis_data.get("analysis"), dict):
        flattened_analysis = analysis_data.pop("analysis")
        analysis_data.update(flattened_analysis)
    analysis_data.update(
        {
            "ts": datetime.utcnow().isoformat(),
            "elapsed_ms": analysis_elapsed,
        }
    )
    yield analysis_complete
PlannerExecutorFlow.events = _planner_events

# Standalone wrapper function for main.py

async def run_planner_executor(
    query: str,
    session_id: Optional[str] = None,
    *,
    skip_preflight: bool = False,
) -> AsyncGenerator[Dict[str, Any], None]:
    """Helper to stream planner-executor events without referencing the registry."""
    workflow_instance = PlannerExecutorFlow()
    async for event in workflow_instance.events(query, session_id, skip_preflight=skip_preflight):
        yield event





