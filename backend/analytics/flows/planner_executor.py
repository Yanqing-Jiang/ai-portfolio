from __future__ import annotations
import json
from typing import AsyncGenerator, Dict, Any, Optional, List, Sequence, Tuple
from dataclasses import dataclass, field
import asyncio
import re
import os
import logging
import time
import uuid
from datetime import datetime, date
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
from analytics.artifacts import (
    ClassificationArtifact as ClassificationArtifactModel,
    ClarificationArtifact,
    IntentArtifact as IntentArtifactModel,
    PipelineArtifacts,
    PlanArtifact,
    SQLExecutionArtifact,
    SQLGenerationArtifact,
    ChartArtifact,
    WebContextArtifact,
    AnalysisArtifact,
    MarketArtifact,
)
from .hooks import AnalyticsFlowHooks, NullFlowHooks
from .tooling import run_tool_parallelism
from ..core.intent import intent_to_sql_criteria
from analytics.core.intent import (
    detect_intent,
    detect_intent_llm,
    detect_intent_with_clarifications,
    classify_query_async,
    OffTopicClassifierSchema,
)
from analytics.sql.sql_planner import build_query_plan, choose_template
from analytics.sql.executor import execute_sql
from analytics.sql.validator import validate_sql
from analytics.sql.templates import fetch_templates_for_intent
from analytics.sql.prompt_builder import build_sql_messages, build_sql_retry_messages, extract_sql_from_response
from analytics.agents.schema_clarifier import ClarifierDecision, decide_schema_clarification
from analytics.core.charting import build_chart_spec, plan_chart_rule_based
from .tool_bundle import collect_tool_bundle
from .chart_revision import emit_chart_patch as _chart_revision_emit, emit_analysis_revision as _analysis_revision_emit
from analytics.core.telemetry import analysis_chunk as log_analysis_chunk
try:
    from analytics.services.response_search import (
        ResponseSearchError,
        perform_response_search,
        has_search_api_key,
        generate_search_topic,
    )
except (ModuleNotFoundError, ImportError):  # pragma: no cover - optional dependency for tests
    ResponseSearchError = RuntimeError  # type: ignore[assignment]

    async def perform_response_search(*args, **kwargs):  # type: ignore[no-redef]
        raise ResponseSearchError("response_search dependency not available")

    def has_search_api_key() -> bool:  # type: ignore[no-redef]
        return False

    def generate_search_topic(query: str) -> str:  # type: ignore[no-redef]
        return query
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
    # Legacy env flag helper retained for backwards compatibility in logs only.
    # Behavioural flags have been removed; flows use built-in defaults.
    value = os.getenv(name)
    if value is None:
        return default
    normalized = value.strip().lower()
    if normalized in {'1', 'true', 'yes', 'on'}:
        return True
    if normalized in {'0', 'false', 'no', 'off'}:
        return False
    return default

# Schema clarifier is now always enabled (legacy env flag removed)
SCHEMA_CLARIFIER_ENABLED = True

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

def _validate_sql(sql: str) -> Tuple[bool, List[str], int]:
    start = time.time()
    ok, issues = validate_sql(sql)
    elapsed = int((time.time() - start) * 1000)
    return ok, issues, elapsed

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
    clarifier_agent_invoked: bool = False
    schema_clarifier_decision: Optional[ClarifierDecision] = None
    plan: Optional[QueryPlanModel] = None
    candidate_templates: List[Dict[str, Any]] = field(default_factory=list)
    selected_template_id: Optional[str] = None
    sql: str = ""
    llm_used: bool = False
    sql_attempt: int = 1
    sql_attempts: List[Dict[str, Any]] = field(default_factory=list)
    validation_attempt: int = 1
    data: List[Dict[str, Any]] = field(default_factory=list)
    exec_elapsed_ms: Optional[int] = None
    chart_spec: Optional[Dict[str, Any]] = None
    web_search: Optional[ResponseSearchResult] = None
    analysis: str = ""
    parallelism_enabled: bool = False
    planner_result: PlannerResultModel = field(default_factory=PlannerResultModel)
    artifacts: PipelineArtifacts = field(default_factory=PipelineArtifacts)
    halted: bool = False
    halt_reason: Optional[str] = None

AGGREGATE_METRIC_MARKERS = (
    "'r&d expense'",
    "'revenue'",
    "'operating cash flow'",
    "'capex'",
    "'capital expenditures'",
    "'operating income'",
    "'net income'",
)


def _normalize_calendar_filters(sql: str) -> str:
    if not sql:
        return sql
    lower_sql = sql.lower()
    if "calendar_quarter_num is null" not in lower_sql:
        return sql
    if "sum(" not in lower_sql:
        return sql
    if not any(marker in lower_sql for marker in AGGREGATE_METRIC_MARKERS):
        return sql
    return re.sub(r"calendar_quarter_num\s+IS\s+NULL", "calendar_quarter_num IS NOT NULL", sql, flags=re.IGNORECASE)


def _safe_year(value: Any) -> Optional[int]:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return int(value)
    if isinstance(value, str):
        stripped = value.strip()
        if stripped.isdigit() and len(stripped) <= 4:
            return int(stripped)
    return None


def _safe_date(value: Any) -> Optional[date]:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return None
        cleaned = stripped.rstrip("Z")
        try:
            return datetime.fromisoformat(cleaned).date()
        except ValueError:
            return None
    return None


def _summarize_sql_rows(data: Optional[List[Dict[str, Any]]]) -> Dict[str, Any]:
    if not isinstance(data, list):
        data = []
    columns: List[str] = sorted({key for row in data if isinstance(row, dict) for key in row.keys()})
    sample_rows: List[Dict[str, Any]] = []
    for row in data[:5]:
        if isinstance(row, dict):
            sample_rows.append({column: row.get(column) for column in columns})
    tickers = sorted(
        {
            str(row.get("ticker")).strip()
            for row in data
            if isinstance(row, dict) and row.get("ticker")
        }
    )
    metric_keys = ("metric", "metric_name", "series", "measure", "line_item")
    metrics = sorted(
        {
            str(row.get(key)).strip()
            for row in data
            if isinstance(row, dict)
            for key in metric_keys
            if row.get(key)
        }
    )
    years: List[int] = []
    dates: List[date] = []
    for row in data:
        if not isinstance(row, dict):
            continue
        for key, value in row.items():
            lower = key.lower()
            if "year" in lower:
                maybe_year = _safe_year(value)
                if maybe_year is not None:
                    years.append(maybe_year)
            if "date" in lower or "period" in lower:
                maybe_date = _safe_date(value)
                if maybe_date is not None:
                    dates.append(maybe_date)
    timeframe: Dict[str, Any] = {}
    if years:
        timeframe["years"] = {"min": min(years), "max": max(years)}
    if dates:
        timeframe["dates"] = {
            "start": min(dates).isoformat(),
            "end": max(dates).isoformat(),
        }
    return {
        "columns": columns,
        "sample_rows": sample_rows,
        "tickers": tickers,
        "metrics": metrics,
        "timeframe": timeframe,
    }


def _set_sql_generation_artifact(
    ctx: PlannerPhaseContext,
    *,
    sql: Optional[str],
    template_id: Optional[str],
    attempts: Sequence[Dict[str, Any]],
    llm_used: bool,
    last_error_code: Optional[str],
    last_error_detail: Optional[str],
    status: str,
) -> None:
    ctx.artifacts.sql_generation = SQLGenerationArtifact(
        query=ctx.query,
        sql=sql,
        template_id=template_id,
        attempts=list(attempts),
        llm_used=llm_used,
        last_error=last_error_detail,
        last_error_code=last_error_code,
        last_error_detail=last_error_detail,
        status=status,
    )


def _set_sql_execution_artifact(
    ctx: PlannerPhaseContext,
    *,
    data: Optional[List[Dict[str, Any]]],
    elapsed_ms: Optional[int],
    status: str,
    error: Optional[str] = None,
    error_code: Optional[str] = None,
) -> None:
    summary = _summarize_sql_rows(data)
    row_count = None if data is None else len(data)
    ctx.artifacts.sql_execution = SQLExecutionArtifact(
        query=ctx.query,
        row_count=row_count,
        columns=summary["columns"],
        tickers=summary["tickers"],
        metrics=summary["metrics"],
        timeframe=summary["timeframe"],
        sample_rows=summary["sample_rows"],
        elapsed_ms=elapsed_ms,
        status=status,
        error=error,
        error_code=error_code,
    )


def _summarize_chart_series(plan: Any, spec: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    series_summary: List[Dict[str, Any]] = []
    plan_dict: Dict[str, Any] = {}
    if hasattr(plan, "dict"):
        try:
            plan_dict = plan.dict()
        except Exception:
            plan_dict = {}
    elif isinstance(plan, dict):
        plan_dict = dict(plan)
    for entry in plan_dict.get("series", []) or []:
        if isinstance(entry, dict):
            summary = {
                key: entry.get(key)
                for key in ("id", "metric", "measure", "comparison", "axis")
                if entry.get(key) is not None
            }
            if summary:
                series_summary.append(summary)
    # Fallback to spec datasets if series empty
    if not series_summary and isinstance(spec, dict):
        datasets = spec.get("datasets")
        if isinstance(datasets, list):
            for dataset in datasets:
                if isinstance(dataset, dict):
                    label = dataset.get("label") or dataset.get("name")
                    series_summary.append(
                        {
                            "label": label,
                            "id": dataset.get("id"),
                            "metric": dataset.get("metric"),
                        }
                    )
    return series_summary


def _set_chart_artifact(
    ctx: PlannerPhaseContext,
    *,
    spec: Dict[str, Any],
    chart_plan: Any,
    chart_design: Dict[str, Any],
) -> None:
    series_summary = _summarize_chart_series(chart_plan, spec)
    chart_type = getattr(chart_plan, "chart_type", None)
    try:
        serialized_spec = json.dumps(spec, sort_keys=True)
    except Exception:
        serialized_spec = repr(spec)
    spec_id = None
    try:
        spec_id = _make_identifier(ctx.session_id, "chart", serialized_spec)
        spec.setdefault("meta", {})["artifactSpecId"] = spec_id
    except Exception:
        spec_id = None
    ctx.artifacts.chart = ChartArtifact(
        query=ctx.query,
        spec=spec,
        spec_id=spec_id,
        design=chart_design or {},
        datasets_summary=series_summary,
        series_count=len(series_summary) if series_summary else None,
        chart_type=chart_type,
    )


def _set_market_artifact(
    ctx: PlannerPhaseContext,
    *,
    widget: Optional[Dict[str, Any]] = None,
    error: Optional[str] = None,
    error_code: Optional[str] = None,
) -> None:
    tickers: List[str] = []
    snapshot: Optional[Dict[str, Any]] = None
    if isinstance(widget, dict):
        snapshot = widget
        symbols = widget.get("symbols")
        if isinstance(symbols, list):
            tickers = [
                str(symbol).strip()
                for symbol in symbols
                if isinstance(symbol, str) and symbol.strip()
            ]
    ctx.artifacts.market = MarketArtifact(
        query=ctx.query,
        tickers=tickers,
        snapshot=snapshot,
        error=error,
        error_code=error_code,
    )


def _set_web_artifact(
    ctx: PlannerPhaseContext,
    *,
    payload: Dict[str, Any],
    topic: Optional[str],
    search_result: Optional[Any],
) -> None:
    metadata = {}
    if search_result is not None:
        metadata = dict(getattr(search_result, "metadata", {}) or {})
    ctx.artifacts.web = WebContextArtifact(
        query=ctx.query,
        summary=payload.get("summary"),
        snippets=list(payload.get("snippets") or []),
        search_id=payload.get("search_id"),
        from_cache=payload.get("from_cache"),
        metadata=metadata,
        topic=topic,
    )


def _set_analysis_artifact(
    ctx: PlannerPhaseContext,
    *,
    analysis_text: str,
    fragments: List[str],
    tool_bundle: Optional[Dict[str, Any]],
) -> None:
    stock_widget = None
    if tool_bundle:
        stock_widget = tool_bundle.get("stock_widget")
    web_context = None
    if ctx.artifacts.web:
        web_context = ctx.artifacts.web.to_dict()
    else:
        # Fall back to latest payload stored on ctx.planner_result
        web_context = ctx.planner_result.metadata.get("web_search")
    ctx.artifacts.analysis = AnalysisArtifact(
        query=ctx.query,
        analysis_text=analysis_text or None,
        fragments=fragments,
        length=len(analysis_text),
        stock_widget=stock_widget,
        web_context=web_context,
        tool_bundle=tool_bundle or None,
    )




def _build_schema_clarifier_request(decision: ClarifierDecision, session_id: str) -> Optional[ClarifyRequestModel]:
    if not decision.slot or not decision.question:
        return None
    options = decision.options or []
    default_option = options[0] if options else None
    input_type = "single" if options else "free"
    return ClarifyRequestModel(
        slot=decision.slot,
        question=decision.question,
        type=input_type,
        options=options,
        default=default_option,
        reason=decision.reason or "Required by the schema clarifier.",
        required=True,
        request_id=str(uuid.uuid4()),
        proposed=None,
        proposed_confidence=None,
        session_id=session_id,
    )


class PlannerPipeline:
    """Phase 2 workflow that emits SSE-friendly events for the memory pipeline."""

    def __init__(self) -> None:
        self.unified_client = get_unified_client()
        self.config_store = CONFIG_STORE
        self.flow_label = "planner-executor"
        # Tool fan-out is now the default; legacy ANALYTICS_TOOL_PARALLELISM flag removed
        self.parallelism_enabled = True
        self.hooks: AnalyticsFlowHooks = NullFlowHooks()
        self._latest_artifacts: Optional[PipelineArtifacts] = None

    async def initialize_context(self, query: str, session_id: Optional[str] = None) -> PlannerPhaseContext:
        return await _initialize_context(self, query, session_id)

    def _capture_artifacts(self, ctx: PlannerPhaseContext) -> None:
        self._latest_artifacts = ctx.artifacts

    def latest_artifacts(self) -> Optional[PipelineArtifacts]:
        return self._latest_artifacts

    async def emit_chart_patch(
        self,
        *,
        session_id: str,
        patch: Dict[str, Any],
        reason: Optional[str] = None,
        source: Optional[str] = None,
        repository: Optional[Any] = None,
        hooks: Optional[AnalyticsFlowHooks] = None,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        stream = _chart_revision_emit(
            session_id=session_id,
            patch=patch,
            reason=reason,
            source=source,
            repository=repository,
        )
        if hooks is None:
            async for event in stream:
                yield event
            return

        hook_ctx: Dict[str, Any] = {"session_id": session_id}
        try:
            async for start_event in hooks.on_flow_start(hook_ctx):
                yield start_event
            async for event in stream:
                async for pre_event in hooks.before_event(hook_ctx, event):
                    yield pre_event
                yield event
                async for post_event in hooks.after_event(hook_ctx, event):
                    yield post_event
        except BaseException as exc:
            async for end_event in hooks.on_flow_end(hook_ctx, error=exc):
                yield end_event
            raise
        else:
            async for end_event in hooks.on_flow_end(hook_ctx):
                yield end_event






    async def run_classification(self, ctx: PlannerPhaseContext) -> AsyncGenerator[Dict[str, Any], None]:
        async for event in _classification_phase(self, ctx):
            yield event

    async def run_intent(self, ctx: PlannerPhaseContext) -> AsyncGenerator[Dict[str, Any], None]:
        async for event in _intent_phase(self, ctx):
            yield event

    async def run_clarification(self, ctx: PlannerPhaseContext) -> AsyncGenerator[Dict[str, Any], None]:
        async for event in _clarification_phase(self, ctx):
            yield event

    async def run_plan(self, ctx: PlannerPhaseContext) -> AsyncGenerator[Dict[str, Any], None]:
        async for event in _plan_phase(self, ctx):
            yield event

    async def run_sql_pipeline(
        self,
        ctx: PlannerPhaseContext,
        *,
        intent: IntentModel,
        plan: QueryPlanModel,
        candidate_templates: List[Dict[str, Any]],
        selected_template_id: Optional[str],
    ) -> AsyncGenerator[Dict[str, Any], None]:
        timed_emitter = ctx.timed_emitter
        workflow_start = ctx.workflow_start
        session_id = ctx.session_id
        query = ctx.query
        template = ctx.template

        sql_progress = EventEmitter.progress("sql_compilation", "Generating SQL with Responses API...")
        sql_progress["data"]["ts"] = datetime.utcnow().isoformat()
        yield sql_progress
        timed_emitter.start_step("sql_generation")
        MAX_SQL_ATTEMPTS = 3
        sql = ""
        llm_used = False
        attempt_logs: List[Dict[str, Any]] = []
        last_error_code: Optional[str] = None
        last_error_detail: Optional[str] = None
        previous_sql: Optional[str] = None

        messages = await build_sql_messages(
            original_query=query,
            intent=intent,
            plan=plan,
            config_store=self.config_store,
            templates=candidate_templates,
        )

        for attempt in range(1, MAX_SQL_ATTEMPTS + 1):
            attempt_start = time.time()
            attempt_record: Dict[str, Any] = {"attempt": attempt, "status": "started"}
            candidate_sql = ""
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
                candidate_sql = _normalize_calendar_filters(candidate_sql)
            except Exception as exc:
                last_error_code = "SQL_GENERATION_ERROR"
                last_error_detail = str(exc)
                attempt_record.update(
                    status="error",
                    error_code=last_error_code,
                    error_detail=last_error_detail,
                    elapsed_ms=int((time.time() - attempt_start) * 1000),
                )
                attempt_logs.append(attempt_record)
                ctx.sql_attempts = attempt_logs
                ctx.planner_result.sql_attempts = list(attempt_logs)
                error_event = EventEmitter.error(
                    "sql_compilation",
                    "SQL generation failed",
                    details={"attempt": attempt, "error": last_error_detail},
                    code=last_error_code,
                )
                error_event["data"]["ts"] = datetime.utcnow().isoformat()
                yield error_event
            else:
                if not candidate_sql:
                    last_error_code = "SQL_EMPTY"
                    last_error_detail = "Responses API returned no SQL content."
                    attempt_record.update(
                        status="empty",
                        error_code=last_error_code,
                        error_detail=last_error_detail,
                        elapsed_ms=int((time.time() - attempt_start) * 1000),
                    )
                    attempt_logs.append(attempt_record)
                    ctx.sql_attempts = attempt_logs
                    ctx.planner_result.sql_attempts = list(attempt_logs)
                    empty_notice = EventEmitter.progress(
                        "sql_compilation",
                        "SQL attempt returned no content; retrying with additional guidance.",
                    )
                    empty_notice["data"].update(
                        {"ts": datetime.utcnow().isoformat(), "attempt": attempt}
                    )
                    yield empty_notice
                else:
                    ok, issues, validate_elapsed = _validate_sql(candidate_sql)
                    attempt_record.update(
                        status="valid" if ok else "invalid",
                        elapsed_ms=int((time.time() - attempt_start) * 1000),
                        validation_elapsed_ms=validate_elapsed,
                        issues=issues,
                    )
                    if not ok:
                        last_error_code = "SQL_VALIDATION_FAILED"
                        last_error_detail = "; ".join(issues) if issues else "Validation failed"
                    attempt_logs.append(attempt_record)
                    ctx.sql_attempts = attempt_logs
                    ctx.planner_result.sql_attempts = list(attempt_logs)
                    if ok:
                        sql = candidate_sql
                        ctx.sql = sql
                        llm_used = True
                        ctx.llm_used = True
                        ctx.sql_attempt = attempt
                        ctx.planner_result.sql_text = sql
                        compiled_event = EventEmitter.result(
                            "sql_compiled",
                            {
                                "sql_length": len(sql),
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
                                "elapsed_ms": attempt_record.get("elapsed_ms"),
                            }
                        )
                        yield compiled_event
                        generated_event = EventEmitter.sql_generated(sql)
                        generated_event["data"].update(
                            {
                                "ts": datetime.utcnow().isoformat(),
                                "elapsed_ms": attempt_record.get("elapsed_ms"),
                                "llm_used": True,
                                "attempt": attempt,
                            }
                        )
                        yield generated_event
                        break
                    validation_event = EventEmitter.error(
                        "sql_validation",
                        "Generated SQL failed validation",
                        details={"attempt": attempt, "issues": issues},
                        code=last_error_code,
                    )
                    validation_event["data"]["ts"] = datetime.utcnow().isoformat()
                    yield validation_event
                    previous_sql = candidate_sql
            if sql:
                break
            if attempt < MAX_SQL_ATTEMPTS:
                retry_notice = EventEmitter.progress(
                    "sql_compilation",
                    f"Retrying SQL generation (attempt {attempt + 1}/{MAX_SQL_ATTEMPTS})",
                )
                retry_notice["data"].update(
                    {"ts": datetime.utcnow().isoformat(), "last_error": last_error_code}
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

        ctx.sql_attempts = attempt_logs
        ctx.planner_result.sql_attempts = list(attempt_logs)
        generation_status = "generated" if sql else "failed"
        _set_sql_generation_artifact(
            ctx,
            sql=sql if sql else None,
            template_id=selected_template_id,
            attempts=attempt_logs,
            llm_used=llm_used or ctx.llm_used,
            last_error_code=last_error_code,
            last_error_detail=last_error_detail,
            status=generation_status,
        )
        self._capture_artifacts(ctx)
        if not sql:
            failure_event = EventEmitter.error(
                "sql_compilation",
                "Unable to generate valid SQL after 3 attempts",
                details={"attempts": attempt_logs, "last_error": last_error_code, "last_detail": last_error_detail},
                code=last_error_code or "SQL_RETRY_EXHAUSTED",
            )
            failure_event["data"]["ts"] = datetime.utcnow().isoformat()
            yield failure_event
            workflow_abort = EventEmitter.result(
                "workflow_complete",
                {
                    "status": "sql_generation_failed",
                    "total_elapsed_ms": int((time.time() - workflow_start) * 1000),
                },
            )
            workflow_abort["event"] = "workflow_complete"
            workflow_abort["data"]["ts"] = datetime.utcnow().isoformat()
            yield workflow_abort
            ctx.halted = True
            ctx.halt_reason = "sql_generation_failed"
            return

        validation_progress = EventEmitter.progress(
            "sql_validation", "Validating SQL..."
        )
        validation_progress["data"]["ts"] = datetime.utcnow().isoformat()
        yield validation_progress
        ok, issues, validate_elapsed = _validate_sql(sql)
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
        if not ok:
            _set_sql_generation_artifact(
                ctx,
                sql=sql,
                template_id=selected_template_id,
                attempts=attempt_logs,
                llm_used=llm_used or ctx.llm_used,
                last_error_code="SQL_VALIDATION_FINAL",
                last_error_detail="; ".join(issues) if issues else None,
                status="validation_failed",
            )
            self._capture_artifacts(ctx)
            error_event = EventEmitter.error(
                "sql_validation",
                "SQL failed validation after retries",
                details={"attempts": attempt_logs, "issues": issues},
                code="SQL_VALIDATION_FINAL",
            )
            error_event["data"]["ts"] = datetime.utcnow().isoformat()
            yield error_event
            workflow_abort = EventEmitter.result(
                "workflow_complete",
                {
                    "status": "sql_validation_failed",
                    "total_elapsed_ms": int((time.time() - workflow_start) * 1000),
                },
            )
            workflow_abort["event"] = "workflow_complete"
            workflow_abort["data"]["ts"] = datetime.utcnow().isoformat()
            yield workflow_abort
            ctx.halted = True
            ctx.halt_reason = "sql_validation_failed"
            return
        else:
            _set_sql_generation_artifact(
                ctx,
                sql=sql,
                template_id=selected_template_id,
                attempts=attempt_logs,
                llm_used=llm_used or ctx.llm_used,
                last_error_code=None,
                last_error_detail=None,
                status="validated",
            )
            self._capture_artifacts(ctx)

        execution_progress = EventEmitter.progress(
            "sql_execution", "Executing query..."
        )
        execution_progress["data"]["ts"] = datetime.utcnow().isoformat()
        yield execution_progress
        exec_start = time.time()
        try:
            data = await execute_sql(sql)
            exec_elapsed = int((time.time() - exec_start) * 1000)
            ctx.exec_elapsed_ms = exec_elapsed
            ctx.planner_result.data_row_count = len(data)
            _set_sql_execution_artifact(
                ctx,
                data=data,
                elapsed_ms=exec_elapsed,
                status="success",
            )
            self._capture_artifacts(ctx)
        except Exception as exec_exc:
            exec_elapsed = int((time.time() - exec_start) * 1000)
            ctx.exec_elapsed_ms = exec_elapsed
            _set_sql_execution_artifact(
                ctx,
                data=None,
                elapsed_ms=exec_elapsed,
                status="error",
                error=str(exec_exc),
                error_code="SQL_EXECUTION_ERROR",
            )
            self._capture_artifacts(ctx)
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
            workflow_abort = EventEmitter.result(
                "workflow_complete",
                {
                    "status": "sql_execution_failed",
                    "total_elapsed_ms": int((time.time() - workflow_start) * 1000),
                },
            )
            workflow_abort["event"] = "workflow_complete"
            workflow_abort["data"]["ts"] = datetime.utcnow().isoformat()
            yield workflow_abort
            ctx.halted = True
            ctx.halt_reason = "sql_execution_failed"
            return

        ctx.llm_used = llm_used or ctx.llm_used
        ctx.sql = sql
        ctx.data = data

    async def run_chart_phase(self, ctx: PlannerPhaseContext, *, intent: IntentModel, plan: QueryPlanModel) -> AsyncGenerator[Dict[str, Any], None]:
        data = ctx.data or []
        if not data:
            return
        query = ctx.query
        chart_progress = EventEmitter.progress(
            "chart_generation", "Planning chart..."
        )
        chart_progress["data"]["ts"] = datetime.utcnow().isoformat()
        yield chart_progress
        chart_start = time.time()
        chart_plan = plan_chart_rule_based(data, query, intent.intent_key)
        spec = build_chart_spec(
            data,
            chart_plan.dict(),
            CONFIGS.charts,
            intent_key=intent.intent_key,
            comparison=plan.comparison,
        )
        ctx.chart_spec = spec
        chart_design = _generate_chart_design(intent.intent_key, plan, data, spec)
        spec.setdefault("meta", {}).setdefault("chartDesign", chart_design)
        _set_chart_artifact(
        ctx,
        spec=spec,
        chart_plan=chart_plan,
        chart_design=chart_design,
    )
        self._capture_artifacts(ctx)
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

    async def run_analysis_phase(self, ctx: PlannerPhaseContext) -> AsyncGenerator[Dict[str, Any], None]:
        data = ctx.data or []
        if not data:
            return
        session_id = ctx.session_id
        query = ctx.query
        sql = ctx.sql
        analysis_progress = EventEmitter.progress(
            "analysis_generation", "Generating insights..."
        )
        analysis_progress["data"]["ts"] = datetime.utcnow().isoformat()
        yield analysis_progress
        analysis_start = time.time()
        full_analysis = ""
        fragments: List[str] = []
        async for text_chunk in stream_insights_llm(
            data,
            sql,
            query,
            chart_spec=ctx.chart_spec,
            search_result=ctx.web_search,
            session_id=session_id,
        ):
            if text_chunk:
                full_analysis += text_chunk
                fragments.append(text_chunk)
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
        ctx.analysis = full_analysis
        ctx.planner_result.analysis = full_analysis
        analysis_payload = {
            "analysis_length": len(full_analysis),
            "analysis": full_analysis,
        }
        tool_bundle = collect_tool_bundle(
            manifest=getattr(ctx, "tool_parallel_manifest", None),
            results=getattr(ctx, "tool_parallel_results", None),
        )
        stock_widget = None
        if tool_bundle:
            stock_widget = tool_bundle.get("stock_widget")
            analysis_payload.update(tool_bundle)
        if ctx.web_search:
            web_payload = ctx.web_search.to_payload()
            analysis_payload['web_context'] = web_payload
            ctx.planner_result.metadata['web_search'] = web_payload
        if stock_widget:
            _set_market_artifact(ctx, widget=stock_widget)
            self._capture_artifacts(ctx)
        _set_analysis_artifact(
            ctx,
            analysis_text=full_analysis,
            fragments=fragments,
            tool_bundle=tool_bundle or None,
        )
        self._capture_artifacts(ctx)
        analysis_complete = EventEmitter.result(
            "analysis_complete",
            analysis_payload,
            key="analysis",
        )
        analysis_complete["event"] = "analysis_complete"
        analysis_complete["data"].update(
            {
                "ts": datetime.utcnow().isoformat(),
                "elapsed_ms": analysis_elapsed,
            }
        )
        yield analysis_complete
        from analytics.core.clarify import get_session_store
        session_store = await get_session_store()
        await session_store.cleanup_expired()
        total_elapsed = int((time.time() - ctx.workflow_start) * 1000)
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


    async def _web_search_phase(self, ctx: PlannerPhaseContext) -> AsyncGenerator[Dict[str, Any], None]:
        if not ctx.query or not ctx.query.strip():
            return
    
        progress = EventEmitter.progress("web_search", "Gathering latest market headlines...")
        progress["data"]["ts"] = datetime.utcnow().isoformat()
        yield progress

        if not has_search_api_key():
            summary = "Web search disabled until GOOGLE_API_KEY or GEMINI_API_KEY is configured."
            payload = {
                "ready": False,
                "error": "search_api_missing",
                "summary": summary,
            }
            _set_web_artifact(ctx, payload=payload, topic=None, search_result=None)
            self._capture_artifacts(ctx)
            result_event = EventEmitter.result("web_search", {"web_context": payload})
            result_event["data"]["ts"] = datetime.utcnow().isoformat()
            yield result_event
            return
    
        context_parts: List[str] = []
        intent = ctx.intent
        if intent and getattr(intent, "intent_key", None):
            context_parts.append(f"intent={intent.intent_key}")
        slots = getattr(intent, "slots_detected", {}) or {}
        company_slot = slots.get("company") if isinstance(slots, dict) else None
        tickers: List[str] = []
        if isinstance(company_slot, str) and company_slot.strip():
            tickers.append(company_slot.strip().upper())
        elif isinstance(company_slot, (list, tuple, set)):
            for value in company_slot:
                if isinstance(value, str) and value.strip():
                    tickers.append(value.strip().upper())
        if tickers:
            context_parts.append("tickers=" + ", ".join(tickers[:3]))
        plan = ctx.plan or ctx.provisional_plan
        if plan and getattr(plan, "metrics", None):
            metrics = list(getattr(plan, "metrics", []) or [])
            if metrics:
                context_parts.append("metrics=" + ", ".join(metrics[:3]))
        if ctx.assumptions:
            context_parts.append("assumptions=" + "; ".join(str(item) for item in ctx.assumptions[:2]))
    
        context_hint = " | ".join(context_parts) if context_parts else None
    
        topic: Optional[str] = None
        try:
            # First, compute and surface the rewritten search topic
            try:
                topic = await generate_search_topic(ctx.query, session_id=ctx.session_id)
            except Exception:
                topic = None
            if topic:
                topic_event = EventEmitter.progress("web_search", f"Search topic: {topic}")
                topic_event["data"]["ts"] = datetime.utcnow().isoformat()
                yield topic_event

            # Then, perform the actual web search using that topic
            search_result = await perform_response_search(
                ctx.query,
                session_id=ctx.session_id,
                context=context_hint,
                search_topic=topic,
            )
        except ResponseSearchError as exc:
            error_event = EventEmitter.error(
                "web_search",
                "Latest news search failed",
                details={"error": str(exc)},
                code="WEB_SEARCH_ERROR",
            )
            error_event["data"]["ts"] = datetime.utcnow().isoformat()
            yield error_event
            error_payload = {
                "ready": False,
                "error": "WEB_SEARCH_ERROR",
                "summary": str(exc),
            }
            _set_web_artifact(ctx, payload=error_payload, topic=None, search_result=None)
            self._capture_artifacts(ctx)
            return
    
        ctx.web_search = search_result
        payload = search_result.to_payload()
        payload["ready"] = True
        payload["ts"] = datetime.utcnow().isoformat()
        _set_web_artifact(ctx, payload=payload, topic=topic, search_result=search_result)
        self._capture_artifacts(ctx)
        yield EventEmitter.result("web_search", {"web_context": payload})
    
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

    async def emit_analysis_revision(
        self,
        *,
        session_id: str,
        analysis: str,
        reason: Optional[str] = None,
        source: Optional[str] = None,
        repository: Optional[Any] = None,
        hooks: Optional[AnalyticsFlowHooks] = None,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        stream = _analysis_revision_emit(
            session_id=session_id,
            analysis=analysis,
            reason=reason,
            source=source,
            repository=repository,
        )
        if hooks is None:
            async for event in stream:
                yield event
            return

        hook_ctx: Dict[str, Any] = {"session_id": session_id}
        try:
            async for start_event in hooks.on_flow_start(hook_ctx):
                yield start_event
            async for event in stream:
                async for pre_event in hooks.before_event(hook_ctx, event):
                    yield pre_event
                yield event
                async for post_event in hooks.after_event(hook_ctx, event):
                    yield post_event
        except BaseException as exc:
            async for end_event in hooks.on_flow_end(hook_ctx, error=exc):
                yield end_event
            raise
        else:
            async for end_event in hooks.on_flow_end(hook_ctx):
                yield end_event

    async def events(self, query: str, session_id: Optional[str] = None) -> AsyncGenerator[Dict[str, Any], None]:
        """Enhanced workflow with structured decision events and timing."""
        ctx = await _initialize_context(self, query, session_id)
        session_id = ctx.session_id
        timed_emitter = ctx.timed_emitter
        workflow_start = ctx.workflow_start
        yield EventEmitter.session_started(session_id)
        async for event in self.run_classification(ctx):
            yield event
        if not ctx.is_financial_query:
            return
        async for event in self.run_intent(ctx):
            yield event
        async for event in self.run_clarification(ctx):
            yield event
        async for event in self.run_plan(ctx):
            yield event
        intent = ctx.intent
        provisional_plan = ctx.plan or ctx.provisional_plan
        template = ctx.template
        candidate_templates = ctx.candidate_templates
        selected_template_id = ctx.selected_template_id



        if not intent or not provisional_plan:
            return
        active_plan = ctx.plan or ctx.provisional_plan
        async for event in self.run_sql_pipeline(
            ctx,
            intent=ctx.intent,
            plan=active_plan,
            candidate_templates=ctx.candidate_templates,
            selected_template_id=ctx.selected_template_id,
        ):
            yield event
        if ctx.halted:
            return
        async for event in self.run_chart_phase(ctx, intent=ctx.intent, plan=active_plan):
            yield event
        async for event in self._web_search_phase(ctx):
            yield event
        async for event in self.run_analysis_phase(ctx):
            yield event


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
    ctx.artifacts.classification = ClassificationArtifactModel(
        query=ctx.query,
        category=getattr(classification, "topic_category", None),
        confidence=getattr(classification, "confidence", None),
        is_financial=getattr(classification, "is_financial_query", None),
        model=model_name,
        raw=classification.model_dump(),
    )
    self._capture_artifacts(ctx)
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

    schema_decision: Optional[ClarifierDecision] = None
    if SCHEMA_CLARIFIER_ENABLED and ctx.template is not None:
        try:
            schema_decision = await asyncio.to_thread(
                decide_schema_clarification,
                intent,
                ctx.provisional_plan,
                session_id=ctx.session_id,
                template_id=intent.intent_key or (ctx.template.get("name") if isinstance(ctx.template, dict) else None),
            )
        except Exception as exc:
            logger.exception("[SCHEMA_CLARIFIER] decision failed: %s", exc)
            schema_decision = ClarifierDecision(action="fallback", missing_slots=[])
    elif SCHEMA_CLARIFIER_ENABLED:
        schema_decision = ClarifierDecision(action="fallback", missing_slots=[])

    ctx.clarifier_agent_invoked = bool(schema_decision)
    ctx.schema_clarifier_decision = schema_decision
    ctx.planner_result.metadata["schema_clarifier"] = {
        "enabled": SCHEMA_CLARIFIER_ENABLED,
        "action": schema_decision.action if schema_decision else "disabled",
        "missing_slots": schema_decision.missing_slots if schema_decision else [],
        "slot": schema_decision.slot if schema_decision else None,
    }
    ctx.artifacts.intent = IntentArtifactModel(
        query=ctx.query,
        intent_key=getattr(intent, "intent_key", None),
        confidence=getattr(intent, "confidence", None),
        slots=dict(getattr(intent, "slots_detected", {}) or {}),
        clarifications_needed=bool(schema_decision and getattr(schema_decision, "action", None) == "request"),
        low_confidence=getattr(intent, "low_confidence", None),
        raw=intent.model_dump(),
    )
    self._capture_artifacts(ctx)

    if SCHEMA_CLARIFIER_ENABLED:
        clarifier_event = EventEmitter.progress(
            "schema_clarifier",
            f"Schema clarifier decision: {(schema_decision.action if schema_decision else 'disabled')}",
        )
        clarifier_event["data"].update(
            {
                "action": schema_decision.action if schema_decision else "disabled",
                "missing_slots": schema_decision.missing_slots if schema_decision else [],
                "enabled": True,
                "ts": datetime.utcnow().isoformat(),
            }
        )
        if schema_decision and schema_decision.slot:
            clarifier_event["data"]["slot"] = schema_decision.slot
        yield clarifier_event

    clarifier_request: Optional[ClarifyRequestModel] = None
    if schema_decision and schema_decision.action == "skip":
        official_clarifications: List[ClarifyRequestModel] = []
    else:
        official_clarifications = compute_required_clarifications(
            intent, ctx.provisional_plan, ctx.template, CONFIGS.__dict__
        )
        if schema_decision and schema_decision.action == "clarify":
            clarifier_request = _build_schema_clarifier_request(schema_decision, ctx.session_id)
            if clarifier_request:
                official_clarifications = [clarifier_request] + [
                    request for request in official_clarifications if request.slot != clarifier_request.slot
                ]
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

    if clarifications_needed:
        intent_status_event = EventEmitter.intent_draft(
            confidence=intent.confidence,
            clarifications_needed=True,
            clarifications_count=len(deduped_requests),
        )
    else:
        intent_status_event = EventEmitter.intent_decided(
            key=intent.intent_key,
            confidence=intent.confidence,
            clarifications_needed=False,
        )
        if not confidence_sufficient:
            intent_status_event["data"]["low_confidence"] = True
        if schema_decision:
            intent_status_event["data"]["schema_clarifier_action"] = schema_decision.action
            if schema_decision.missing_slots:
                intent_status_event["data"]["schema_clarifier_missing"] = schema_decision.missing_slots

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
    history_entries: List[Dict[str, Any]] = []
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
            history_entry: Dict[str, Any] = {"request": dict(request_payload)}
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
                    history_entry["response"] = {
                        "status": "timeout_no_value",
                        "slot": slot_request.slot,
                    }
                    history_entries.append(history_entry)
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
                    history_entry["response"] = {
                        "status": "accepted",
                        "slot": answer.slot,
                        "value": answer.value,
                    }
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
                    history_entry["response"] = {
                        "status": "rejected",
                        "slot": answer.slot,
                        "value": answer.value,
                        "error": error_message,
                    }
            else:
                official_clarifications = official_clarifications[1:]
                history_entry["response"] = {
                    "status": "no_answer",
                    "slot": slot_request.slot,
                }
            if history_entry not in history_entries:
                history_entries.append(history_entry)
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
    decision = ctx.schema_clarifier_decision
    clarifier_action = None
    clarifier_missing = []
    clarifier_slot = None
    if decision is not None:
        clarifier_action = getattr(decision, "action", None)
        clarifier_missing = list(getattr(decision, "missing_slots", []) or [])
        clarifier_slot = getattr(decision, "slot", None)
    elif official_clarifications:
        clarifier_action = "request"
    else:
        clarifier_action = "not_required"
    ctx.artifacts.clarification = ClarificationArtifact(
        query=ctx.query,
        clarifier_action=clarifier_action,
        clarifier_missing_slots=clarifier_missing,
        clarifier_slot=clarifier_slot,
        pending=[req.model_dump() for req in official_clarifications],
        assumptions=list(assumptions),
        resolved=not official_clarifications,
        rounds=rounds,
        answered_slots=sorted(all_answered_slots),
        history=history_entries,
    )
    self._capture_artifacts(ctx)

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
    criteria_payload = criteria_model.model_dump()
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
    plan_payload = provisional_plan.model_dump()
    candidate_payload = [dict(template) for template in candidate_templates]
    template_payload = template_info or (template if isinstance(template, dict) else None)
    ctx.artifacts.plan = PlanArtifact(
        query=ctx.query,
        plan=plan_payload,
        candidate_templates=candidate_payload,
        selected_template_id=selected_template_id,
        comparison=provisional_plan.comparison,
        granularity=provisional_plan.granularity,
        metrics_count=len(provisional_plan.metrics),
        template=template_payload,
        parallelism_enabled=ctx.parallelism_enabled,
        criteria={k: v for k, v in criteria_payload.items() if k != "ts"},
        catalog_elapsed_ms=catalog_elapsed,
    )
    self._capture_artifacts(ctx)

class PlannerExecutorFlow:
    """Backward-compatible wrapper around :class:`PlannerPipeline`."""

    def __init__(self) -> None:
        self._pipeline = PlannerPipeline()

    def __getattr__(self, name: str):
        try:
            return getattr(self._pipeline, name)
        except AttributeError:
            raise AttributeError(name) from None

    def __setattr__(self, name: str, value):
        if name == '_pipeline':
            super().__setattr__(name, value)
        elif hasattr(self, '_pipeline') and hasattr(self._pipeline, name):
            setattr(self._pipeline, name, value)
        else:
            super().__setattr__(name, value)

    def latest_artifacts(self) -> Optional[PipelineArtifacts]:
        return self._pipeline.latest_artifacts()

    async def initialize_context(self, query: str, session_id: Optional[str] = None) -> PlannerPhaseContext:
        return await self._pipeline.initialize_context(query, session_id)

    async def emit_chart_patch(
        self,
        *,
        session_id: str,
        patch: Dict[str, Any],
        reason: Optional[str] = None,
        source: Optional[str] = None,
        repository: Optional[Any] = None,
        hooks: Optional[AnalyticsFlowHooks] = None,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        stream = self._pipeline.emit_chart_patch(
            session_id=session_id,
            patch=patch,
            reason=reason,
            source=source,
            repository=repository,
            hooks=hooks,
        )
        async for event in stream:
            yield event

    async def emit_analysis_revision(
        self,
        *,
        session_id: str,
        analysis: str,
        reason: Optional[str] = None,
        source: Optional[str] = None,
        repository: Optional[Any] = None,
        hooks: Optional[AnalyticsFlowHooks] = None,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        stream = self._pipeline.emit_analysis_revision(
            session_id=session_id,
            analysis=analysis,
            reason=reason,
            source=source,
            repository=repository,
            hooks=hooks,
        )
        async for event in stream:
            yield event

    async def events(
        self,
        query: str,
        session_id: Optional[str] = None,
        *,
        hooks: Optional[AnalyticsFlowHooks] = None,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        stream = self._pipeline.events(query, session_id)
        if hooks is None:
            async for event in stream:
                yield event
            return

        hook_ctx: Dict[str, Any] = {"query": query, "session_id": session_id}
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
# Standalone wrapper function for main.py
async def run_planner_executor(query: str, session_id: Optional[str] = None) -> AsyncGenerator[Dict[str, Any], None]:
    """Helper to stream planner-executor events without referencing the registry."""
    workflow_instance = PlannerExecutorFlow()
    async for event in workflow_instance.events(query, session_id):
        yield event




















