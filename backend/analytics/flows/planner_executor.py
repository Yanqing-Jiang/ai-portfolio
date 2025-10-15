from __future__ import annotations
import json
import hashlib
from typing import AsyncGenerator, Dict, Any, Optional, List, Sequence, Tuple, Set, Mapping
from dataclasses import dataclass, field
import asyncio
import contextlib
from asyncio import QueueEmpty, Task
import re
import os
import logging
import time
import uuid
import copy
from datetime import datetime, date
from types import SimpleNamespace
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
from analytics.core.session_state import SessionStateSnapshot, get_session_state_repository
from analytics.core.revision_snapshot import (
    build_intent_signature,
    extract_revision_snapshot,
    signatures_equal,
)
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
from analytics.routing import FollowUpRoute
from analytics.validators import sanitize_for_json
from .hooks import AnalyticsFlowHooks, NullFlowHooks
from .tooling import run_tool_parallelism, get_default_tool_adapters
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
from .schedulers import FlowMode, get_mode_config, apply_mode_metadata
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
    if getattr(plan, "statistic", None) == "ranking_latest":
        primary_metric = (plan.metrics or [None])[0]
        design.update({
            'chart_type': 'ranking_bar',
            'grouping': 'ticker',
            'y_axis': {'type': 'single'},
            'measure': primary_metric,
            'statistic': plan.statistic,
        })
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
class ToolInvocationReceipt:
    tool: str
    status: str
    attempts: int = 0
    elapsed_ms: Optional[int] = None
    input_hash: Optional[str] = None
    output_hash: Optional[str] = None
    reused: bool = False
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "tool": self.tool,
            "status": self.status,
            "attempts": self.attempts,
            "elapsed_ms": self.elapsed_ms,
            "input_hash": self.input_hash,
            "output_hash": self.output_hash,
            "reused": self.reused,
            "error": self.error,
            "timestamp": self.timestamp,
        }
        if self.metadata:
            payload["metadata"] = sanitize_for_json(self.metadata)
        return {key: value for key, value in payload.items() if value is not None}

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "ToolInvocationReceipt":
        metadata = payload.get("metadata") or {}
        return cls(
            tool=str(payload.get("tool") or ""),
            status=str(payload.get("status") or "unknown"),
            attempts=int(payload.get("attempts") or 0),
            elapsed_ms=payload.get("elapsed_ms"),
            input_hash=payload.get("input_hash"),
            output_hash=payload.get("output_hash"),
            reused=bool(payload.get("reused", False)),
            error=payload.get("error"),
            metadata=dict(metadata) if isinstance(metadata, Mapping) else {},
            timestamp=str(payload.get("timestamp") or datetime.utcnow().isoformat()),
        )


def _hash_payload(payload: Any) -> str:
    try:
        normalized = sanitize_for_json(payload)
    except Exception:
        normalized = payload
    try:
        encoded = json.dumps(
            normalized,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
    except TypeError:
        encoded = json.dumps(str(normalized), sort_keys=True).encode("utf-8")
    return hashlib.sha1(encoded).hexdigest()

@dataclass
class PlannerPhaseContext:
    query: str
    session_id: str
    workflow_start: float
    timed_emitter: TimedEventEmitter
    flow_mode: FlowMode = FlowMode.DIRECT
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
    web_search: Optional[ResponseSearchResult] = None
    web_search_seeded: bool = False
    stock_widget_seeded: bool = False
    parallelism_enabled: bool = False
    follow_up_route: FollowUpRoute = FollowUpRoute.FULL_PIPELINE
    reuse_sql: bool = False
    stock_only: bool = False
    artifacts: PipelineArtifacts = field(default_factory=PipelineArtifacts)
    snapshot_artifacts: Optional[PipelineArtifacts] = None
    revision_snapshot: Optional[Dict[str, Any]] = None
    prior_intent_signature: Optional[Dict[str, Any]] = None
    intent_signature: Optional[Dict[str, Any]] = None
    criteria_changed: bool = False
    reuse_snapshot_active: bool = False
    reused_sql: bool = False
    reused_chart: bool = False
    reused_stock: bool = False
    reused_web: bool = False
    reused_analysis: bool = False
    snapshot_age_seconds: Optional[float] = None
    snapshot_stale: bool = False
    tool_receipts: Dict[str, ToolInvocationReceipt] = field(default_factory=dict)
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

SQL_DATASET_PREVIEW_LIMIT = 200
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")
_DEFAULT_GUARDRAIL_P50 = int(os.getenv("WEB_SEARCH_GUARDRAIL_P50_MS", "1200"))
_DEFAULT_GUARDRAIL_P95 = int(os.getenv("WEB_SEARCH_GUARDRAIL_P95_MS", "2500"))
_RISK_TERMS = (
    "risk",
    "headwind",
    "concern",
    "pressure",
    "downside",
    "volatility",
    "slowdown",
    "uncertain",
    "watchlist",
    "caution",
)
_ACTION_TERMS = (
    "consider",
    "monitor",
    "focus",
    "plan to",
    "plan for",
    "watch",
    "track",
    "follow up",
    "prepare",
    "should",
    "next step",
    "next steps",
    "keep an eye",
)
_NUMERIC_HINTS = ("%", "bps", "basis point", "million", "billion", "m$", "bn")
SNAPSHOT_MAX_AGE_SECONDS = int(os.getenv("ANALYTICS_SNAPSHOT_MAX_AGE_SECONDS", "600"))

FOLLOW_UP_BANNERS: Dict[FollowUpRoute, Dict[str, str]] = {
    FollowUpRoute.FULL_PIPELINE: {
        "title": "Fresh Run Scheduled",
        "message": "Running SQL, charts, and narrative again to deliver a fully refreshed answer.",
    },
    FollowUpRoute.REUSE_SQL: {
        "title": "Reusing Last Dataset",
        "message": "Skipping the SQL rerun�updating visuals and narrative on top of the validated table.",
    },
    FollowUpRoute.STOCK_ONLY: {
        "title": "Market Snapshot Only",
        "message": "Pulling fresh price data while charts and analysis stay pinned to the prior run.",
    },
}


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
    dataset: List[Dict[str, Any]] = list(data or [])
    summary = _summarize_sql_rows(dataset)
    row_count = len(dataset) if dataset else None
    dataset_preview = dataset[:SQL_DATASET_PREVIEW_LIMIT] if dataset else []
    ctx.artifacts.sql_execution = SQLExecutionArtifact(
        query=ctx.query,
        row_count=row_count,
        columns=summary["columns"],
        tickers=summary["tickers"],
        metrics=summary["metrics"],
        timeframe=summary["timeframe"],
        sample_rows=summary["sample_rows"],
        dataset_preview=dataset_preview,
        dataset=dataset,
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


def _get_sql_dataset(ctx: PlannerPhaseContext) -> List[Dict[str, Any]]:
    execution_artifact = getattr(ctx.artifacts, "sql_execution", None)
    if execution_artifact is None:
        return []
    dataset = getattr(execution_artifact, "dataset", None) or []
    if dataset:
        return list(dataset)
    preview = getattr(execution_artifact, "dataset_preview", None) or []
    if preview:
        return list(preview)
    return list(execution_artifact.sample_rows)


def _extract_tldr(text: str) -> Optional[str]:
    stripped = (text or "").strip()
    if not stripped:
        return None
    first_paragraph = stripped.split("\n\n", 1)[0].strip()
    first_sentence = first_paragraph.split(". ", 1)[0].strip()
    return first_sentence[:240] if first_sentence else None


def _extract_bullets(text: str, limit: int = 3) -> List[str]:
    bullets: List[str] = []
    for line in (text or "").splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped[0] in {"-", "*", "\u2022"}:
            content = stripped.lstrip("-* \u2022").strip()
            if content:
                bullets.append(content)
        if len(bullets) >= limit:
            break
    return bullets


def _split_line(line: str) -> List[str]:
    stripped = line.strip()
    if not stripped:
        return []
    if stripped[0] in {"-", "*", "\u2022"}:
        cleaned = stripped.lstrip("-*\u2022 ").strip()
        return [cleaned] if cleaned else []
    return _SENTENCE_SPLIT.split(stripped)


def _normalize_sentence(sentence: str) -> Optional[str]:
    cleaned = re.sub(r"\s+", " ", sentence or "").strip()
    return cleaned or None


def _collect_sentences(text: str) -> List[str]:
    sentences: List[str] = []
    seen: set[str] = set()
    for raw_line in (text or "").splitlines():
        for fragment in _split_line(raw_line):
            normalized = _normalize_sentence(fragment)
            if not normalized:
                continue
            lowered = normalized.lower()
            if lowered in seen:
                continue
            seen.add(lowered)
            sentences.append(normalized)
    return sentences


def _extract_key_numbers(text: str, limit: int = 3) -> List[str]:
    sentences = _collect_sentences(text)
    key_numbers: List[str] = []
    for sentence in sentences:
        lowered = sentence.lower()
        has_numeric = any(char.isdigit() for char in sentence)
        if not has_numeric and not any(hint in lowered for hint in _NUMERIC_HINTS):
            continue
        key_numbers.append(sentence[:240])
        if len(key_numbers) >= limit:
            break
    return key_numbers


def _extract_risk_watch(text: str, limit: int = 2) -> List[str]:
    sentences = _collect_sentences(text)
    risks: List[str] = []
    for sentence in sentences:
        lowered = sentence.lower()
        if any(term in lowered for term in _RISK_TERMS):
            risks.append(sentence[:240])
        if len(risks) >= limit:
            break
    return risks


def _extract_next_steps(text: str, limit: int = 2) -> List[str]:
    sentences = _collect_sentences(text)
    next_steps: List[str] = []
    for sentence in sentences:
        lowered = sentence.lower()
        if any(term in lowered for term in _ACTION_TERMS):
            next_steps.append(sentence[:240])
        if len(next_steps) >= limit:
            break
    return next_steps


def _build_evidence_entries(
    *,
    web_context: Optional[Dict[str, Any]],
    highlights: Optional[List[str]],
    summary: Optional[str],
    max_items: int = 5,
) -> List[Dict[str, Any]]:
    if not web_context or not isinstance(web_context, dict):
        return []

    snippets = web_context.get("snippets") or []
    if not isinstance(snippets, list):
        return []

    claims: List[str] = []
    if summary:
        claims.append(summary)
    if highlights:
        claims.extend(highlights)

    evidence: List[Dict[str, Any]] = []
    seen_urls: set[str] = set()

    for index, raw_snippet in enumerate(snippets):
        if not isinstance(raw_snippet, dict):
            continue
        url = raw_snippet.get("url") or raw_snippet.get("source_url")
        if not isinstance(url, str) or not url.strip():
            continue
        normalized_url = url.strip()
        if normalized_url in seen_urls:
            continue
        title = raw_snippet.get("title") or raw_snippet.get("display_url")
        snippet_text = raw_snippet.get("snippet") or raw_snippet.get("summary")

        entry: Dict[str, Any] = {
            "source_url": normalized_url,
        }
        if isinstance(title, str) and title.strip():
            entry["title"] = title.strip()
        display_url = raw_snippet.get("display_url")
        if isinstance(display_url, str) and display_url.strip():
            entry["display_url"] = display_url.strip()
        if isinstance(snippet_text, str) and snippet_text.strip():
            excerpt = snippet_text.strip()
            if len(excerpt) > 260:
                excerpt = excerpt[:257].rstrip() + "..."
            entry["snippet"] = excerpt
        published_at = raw_snippet.get("published_at")
        if isinstance(published_at, str) and published_at.strip():
            entry["published_at"] = published_at.strip()
        if claims:
            claim_idx = index if index < len(claims) else -1
            if claim_idx >= 0:
                entry["claim"] = claims[claim_idx]
        annotation = raw_snippet.get("annotation") or {}
        confidence = annotation.get("confidence")
        if not isinstance(confidence, (int, float)):
            derived = 1.0 - (0.15 * index)
            confidence = max(0.1, round(derived, 2))
        else:
            confidence = round(max(0.0, min(float(confidence), 1.0)), 2)
        entry["confidence"] = confidence
        evidence.append(entry)
        seen_urls.add(normalized_url)
        if len(evidence) >= max_items:
            break

    return evidence


def _evaluate_latency_guardrail(
    stats: Optional[Dict[str, Any]],
    *,
    p50_threshold: Optional[int] = None,
    p95_threshold: Optional[int] = None,
) -> Optional[Dict[str, Any]]:
    if not stats or not isinstance(stats, dict):
        return None

    observed_p50 = stats.get("p50_ms")
    observed_p95 = stats.get("p95_ms") or stats.get("max_ms")
    observed_total = stats.get("total_ms")
    thresholds = {
        "p50_ms": p50_threshold if p50_threshold is not None else _DEFAULT_GUARDRAIL_P50,
        "p95_ms": p95_threshold if p95_threshold is not None else _DEFAULT_GUARDRAIL_P95,
    }

    violations: List[str] = []
    if isinstance(observed_p50, (int, float)) and observed_p50 > thresholds["p50_ms"]:
        violations.append("p50_ms")
    if isinstance(observed_p95, (int, float)) and observed_p95 > thresholds["p95_ms"]:
        violations.append("p95_ms")

    status = "ok"
    if violations:
        status = "violation"

    guardrail_payload: Dict[str, Any] = {
        "status": status,
        "violations": violations,
        "observed": {
            key: stats.get(key)
            for key in ("total_ms", "p50_ms", "p95_ms", "max_ms", "samples")
            if stats.get(key) is not None
        },
        "thresholds": thresholds,
    }
    if observed_total is not None and guardrail_payload["observed"].get("total_ms") is None:
        guardrail_payload["observed"]["total_ms"] = observed_total
    return guardrail_payload


def _derive_scope_banner(ctx: PlannerPhaseContext, spec: Dict[str, Any]) -> Optional[str]:
    tickers: List[str] = []
    market_artifact = getattr(ctx.artifacts, "market", None)
    if market_artifact and market_artifact.tickers:
        tickers.extend(market_artifact.tickers)
    datasets = spec.get("datasets")
    if not tickers and isinstance(datasets, list):
        for dataset in datasets:
            if isinstance(dataset, dict):
                symbol = dataset.get("ticker") or dataset.get("symbol")
                if isinstance(symbol, str):
                    tickers.append(symbol)
    if not tickers:
        dataset_rows = _get_sql_dataset(ctx)
        for row in dataset_rows:
            symbol = row.get("ticker")
            if isinstance(symbol, str):
                tickers.append(symbol)
    deduped: List[str] = []
    for symbol in tickers:
        upper = symbol.strip().upper()
        if upper and upper not in deduped:
            deduped.append(upper)
    if not deduped:
        return None
    basis = ", ".join(deduped[:7])
    return f"Basis: Revenue share across {basis}"


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
    scope_banner = _derive_scope_banner(ctx, spec)
    if scope_banner:
        spec.setdefault("meta", {})["scopeBanner"] = scope_banner
    ctx.artifacts.chart = ChartArtifact(
        query=ctx.query,
        spec=spec,
        spec_id=spec_id,
        design=chart_design or {},
        datasets_summary=series_summary,
        series_count=len(series_summary) if series_summary else None,
        chart_type=chart_type,
        scope_banner=scope_banner,
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
        latency_stats=payload.get("latency_stats"),
    )


class _PayloadSearchResultProxy:
    """Minimal wrapper so seeded payloads satisfy the ResponseSearchResult interface."""

    def __init__(self, payload: Dict[str, Any]) -> None:
        self._payload = copy.deepcopy(payload)
        self.summary = self._payload.get("summary")
        self.latency_ms = self._payload.get("latency_ms")

    def to_payload(self) -> Dict[str, Any]:
        return copy.deepcopy(self._payload)


def _seed_web_search_from_payload(ctx: PlannerPhaseContext, payload: Dict[str, Any]) -> None:
    if not isinstance(payload, dict):
        return
    sanitized_payload = sanitize_for_json(payload)
    ctx.web_search = _PayloadSearchResultProxy(sanitized_payload)
    ctx.web_search_seeded = True
    if sanitized_payload.get("from_cache"):
        ctx.reused_web = True
    topic = sanitized_payload.get("topic") or sanitized_payload.get("search_topic")
    _set_web_artifact(ctx, payload=sanitized_payload, topic=topic, search_result=None)


def _seed_stock_widget_from_payload(ctx: PlannerPhaseContext, payload: Dict[str, Any]) -> None:
    if not isinstance(payload, dict):
        return
    widget_payload = payload.get("stock_widget")
    if not isinstance(widget_payload, dict):
        if not payload.get("ready"):
            return
        return
    sanitized_widget = sanitize_for_json(widget_payload)
    ctx.stock_widget_seeded = True
    ctx.reused_stock = ctx.reused_stock or bool(payload.get("from_cache"))
    _set_market_artifact(
        ctx,
        widget=sanitized_widget,
        error=payload.get("error"),
        error_code=payload.get("error_code"),
    )


def _set_analysis_artifact(
    ctx: PlannerPhaseContext,
    *,
    analysis_text: str,
    fragments: List[str],
    tool_bundle: Optional[Dict[str, Any]],
    summary: Optional[str],
    bullets: Optional[List[str]],
    key_numbers: Optional[List[str]],
    risk_watch: Optional[List[str]],
    next_steps: Optional[List[str]],
) -> None:
    stock_widget = None
    if tool_bundle:
        stock_widget = tool_bundle.get("stock_widget")
    web_context = None
    if ctx.artifacts.web:
        web_context = ctx.artifacts.web.to_dict()
    elif ctx.web_search is not None:
        web_context = ctx.web_search.to_payload()
    elif ctx.snapshot_artifacts and ctx.snapshot_artifacts.web:
        web_context = ctx.snapshot_artifacts.web.to_dict()
    evidence_entries = _build_evidence_entries(
        web_context=web_context,
        highlights=bullets,
        summary=summary,
    )
    ctx.artifacts.analysis = AnalysisArtifact(
        query=ctx.query,
        analysis_text=analysis_text or None,
        fragments=fragments,
        length=len(analysis_text),
        summary=summary,
        highlights=bullets or [],
        key_numbers=key_numbers or [],
        risk_watch=risk_watch or [],
        next_steps=next_steps or [],
        evidence=evidence_entries,
        stock_widget=stock_widget,
        web_context=web_context,
        tool_bundle=tool_bundle or None,
    )


def _build_planner_result_payload(ctx: PlannerPhaseContext) -> Dict[str, Any]:
    intent_model = ctx.intent
    if intent_model is not None and not isinstance(intent_model, IntentModel):
        intent_payload: Optional[Dict[str, Any]] = None
        if hasattr(intent_model, "model_dump"):
            intent_payload = intent_model.model_dump()
        elif hasattr(intent_model, "__dict__"):
            intent_payload = dict(intent_model.__dict__)
        if isinstance(intent_payload, dict):
            try:
                intent_model = IntentModel(**intent_payload)
            except Exception:
                intent_model = None

    clarification_requests_raw = list(ctx.clarifications)
    clarification_requests: List[ClarifyRequestModel] = []
    for request in clarification_requests_raw:
        if isinstance(request, ClarifyRequestModel):
            clarification_requests.append(request)
            continue
        request_payload: Optional[Dict[str, Any]] = None
        if hasattr(request, "model_dump"):
            request_payload = request.model_dump()
        elif isinstance(request, dict):
            request_payload = request
        elif hasattr(request, "__dict__"):
            request_payload = dict(request.__dict__)
        if isinstance(request_payload, dict):
            try:
                clarification_requests.append(ClarifyRequestModel(**request_payload))
            except Exception:
                continue

    sql_attempts: List[Dict[str, Any]] = []
    sql_text: Optional[str] = None
    if ctx.artifacts.sql_generation:
        sql_attempts = list(ctx.artifacts.sql_generation.attempts or [])
        sql_text = ctx.artifacts.sql_generation.sql

    row_count: Optional[int] = None
    if ctx.artifacts.sql_execution:
        row_count = ctx.artifacts.sql_execution.row_count

    chart_summary: Optional[Dict[str, Any]] = None
    if ctx.artifacts.chart:
        chart_summary = {
            "chart_type": ctx.artifacts.chart.chart_type,
            "series_count": ctx.artifacts.chart.series_count,
            "design": copy.deepcopy(ctx.artifacts.chart.design),
        }
        if ctx.artifacts.chart.scope_banner:
            chart_summary["scope_banner"] = ctx.artifacts.chart.scope_banner

    analysis_text = ctx.artifacts.analysis.analysis_text if ctx.artifacts.analysis else None

    metadata: Dict[str, Any] = {}
    if ctx.classification is not None:
        metadata["classification"] = copy.deepcopy(ctx.classification.model_dump())

    web_payload: Optional[Dict[str, Any]] = None
    if ctx.artifacts.web:
        web_payload = ctx.artifacts.web.to_dict()
    elif ctx.web_search is not None:
        web_payload = ctx.web_search.to_payload()
    elif ctx.snapshot_artifacts and ctx.snapshot_artifacts.web:
        web_payload = ctx.snapshot_artifacts.web.to_dict()
    web_latency: Optional[Dict[str, Any]] = None
    if web_payload:
        metadata["web_search"] = copy.deepcopy(web_payload)
        stats = web_payload.get("latency_stats")
        if isinstance(stats, dict):
            web_latency = {
                "total_ms": stats.get("total_ms") or stats.get("totalMs"),
                "p50_ms": stats.get("p50_ms") or stats.get("p50Ms"),
                "max_ms": stats.get("max_ms") or stats.get("maxMs"),
                "min_ms": stats.get("min_ms") or stats.get("minMs"),
                "samples": stats.get("samples") or stats.get("latency_samples") or stats.get("sample_count"),
            }
    elif ctx.web_search is not None and ctx.web_search.latency_ms is not None:
        web_latency = {
            "total_ms": ctx.web_search.latency_ms,
        }

    if web_latency:
        cleaned_latency = {key: value for key, value in web_latency.items() if value is not None}
        if cleaned_latency:
            metadata["web_search_latency"] = cleaned_latency
        guardrail_payload = _evaluate_latency_guardrail(web_latency)
        if guardrail_payload:
            metadata["web_search_guardrail"] = guardrail_payload

    if ctx.artifacts.analysis:
        overview: Dict[str, Any] = {}
        if ctx.artifacts.analysis.summary:
            overview["tldr"] = ctx.artifacts.analysis.summary
        if ctx.artifacts.analysis.highlights:
            overview["highlights"] = list(ctx.artifacts.analysis.highlights)
        if ctx.artifacts.analysis.key_numbers:
            overview["key_numbers"] = list(ctx.artifacts.analysis.key_numbers)
        if ctx.artifacts.analysis.risk_watch:
            overview["risk_watch"] = list(ctx.artifacts.analysis.risk_watch)
        if ctx.artifacts.analysis.next_steps:
            overview["next_steps"] = list(ctx.artifacts.analysis.next_steps)
        evidence_entries = list(ctx.artifacts.analysis.evidence or [])
        if not evidence_entries:
            web_source: Optional[Dict[str, Any]] = None
            if metadata.get("web_search"):
                web_candidate = metadata.get("web_search")
                if isinstance(web_candidate, dict):
                    web_source = web_candidate
            elif ctx.artifacts.web:
                web_source = ctx.artifacts.web.to_dict()
            evidence_entries = _build_evidence_entries(
                web_context=web_source,
                highlights=ctx.artifacts.analysis.highlights,
                summary=ctx.artifacts.analysis.summary or ctx.artifacts.analysis.analysis_text,
            )
            if evidence_entries:
                ctx.artifacts.analysis.evidence = evidence_entries
        if evidence_entries:
            overview["evidence"] = evidence_entries
        if overview:
            metadata["analysis_overview"] = overview

    if SCHEMA_CLARIFIER_ENABLED:
        decision = ctx.schema_clarifier_decision
        metadata["schema_clarifier"] = {
            "enabled": True,
            "action": decision.action if decision else "disabled",
            "missing_slots": list(decision.missing_slots) if decision and decision.missing_slots else [],
            "slot": decision.slot if decision else None,
        }

    metadata["follow_up_route"] = ctx.follow_up_route.value
    metadata["snapshot_reuse"] = {
        "reused_sql": ctx.reused_sql,
        "reused_chart": ctx.reused_chart,
        "reused_stock": ctx.reused_stock,
        "reused_web": ctx.reused_web,
        "reused_analysis": ctx.reused_analysis,
        "criteria_changed": ctx.criteria_changed,
        "follow_up_route": ctx.follow_up_route.value,
        "source": "snapshot" if ctx.reuse_snapshot_active else None,
        "snapshot_age_seconds": ctx.snapshot_age_seconds,
        "snapshot_stale": ctx.snapshot_stale,
    }
    metadata["reuse_snapshot"] = metadata["snapshot_reuse"]

    planner_result_model = PlannerResultModel(
        intent=intent_model,
        clarification_requests=clarification_requests,
        sql_attempts=sql_attempts,
        sql_text=sql_text,
        data_row_count=row_count,
        chart_summary=chart_summary,
        analysis=analysis_text,
        metadata=metadata,
    )
    return planner_result_model.model_dump()


def _artifacts_from_snapshot(snapshot: Optional[SessionStateSnapshot]) -> Optional[PipelineArtifacts]:
    if snapshot is None:
        return None
    analytics_cache = snapshot.tool_cache.get("analytics", {}) if hasattr(snapshot, "tool_cache") else {}
    artifacts_payload = analytics_cache.get("artifacts")
    if isinstance(artifacts_payload, dict):
        try:
            return PipelineArtifacts.from_dict(artifacts_payload)
        except Exception:
            return None
    return None


def _dataset_preview_from_snapshot(snapshot: Optional[SessionStateSnapshot]) -> Optional[Dict[str, Any]]:
    if snapshot is None or not hasattr(snapshot, "tool_cache"):
        return None
    preview_payload = snapshot.tool_cache.get("planner_dataset_preview")
    if isinstance(preview_payload, dict):
        rows = preview_payload.get("rows")
        if isinstance(rows, list):
            return preview_payload
    return None


def _limit_sample_rows(rows: Optional[Sequence[Dict[str, Any]]], *, limit: int = 50) -> List[Dict[str, Any]]:
    if not isinstance(rows, Sequence):
        return []
    limited: List[Dict[str, Any]] = []
    for row in rows[:limit]:
        if isinstance(row, dict):
            limited.append(copy.deepcopy(row))
    return limited


def _snapshot_age_seconds_from_snapshot(snapshot: Dict[str, Any]) -> Optional[float]:
    updated_at = snapshot.get("updated_at")
    if not isinstance(updated_at, str):
        return None
    try:
        stamp = datetime.fromisoformat(updated_at)
    except ValueError:
        return None
    if stamp.tzinfo is None:
        delta = datetime.utcnow() - stamp
    else:
        delta = datetime.now(stamp.tzinfo) - stamp
    return max(delta.total_seconds(), 0.0)


def _is_snapshot_fresh(snapshot: Optional[Dict[str, Any]]) -> bool:
    if not isinstance(snapshot, dict):
        return False
    age_seconds = _snapshot_age_seconds_from_snapshot(snapshot)
    if age_seconds is None:
        return False
    return age_seconds <= SNAPSHOT_MAX_AGE_SECONDS


def _build_revision_snapshot_payload(ctx: PlannerPhaseContext) -> Optional[Dict[str, Any]]:
    signature = ctx.intent_signature or build_intent_signature(ctx.intent, ctx.plan or ctx.provisional_plan)
    if signature is None:
        return None

    payload: Dict[str, Any] = {"intent_signature": signature}

    sql_generation = ctx.artifacts.sql_generation
    if sql_generation and sql_generation.sql:
        payload["sql"] = sql_generation.sql

    sql_execution = ctx.artifacts.sql_execution
    if sql_execution:
        if sql_execution.row_count is not None:
            payload["sql_row_count"] = sql_execution.row_count
        if sql_execution.columns:
            payload["columns"] = list(sql_execution.columns)
        sample_source = sql_execution.sample_rows or sql_execution.dataset_preview
        samples = _limit_sample_rows(sample_source)
        if samples:
            payload["data_sample"] = samples

    chart_artifact = ctx.artifacts.chart
    if chart_artifact:
        if chart_artifact.spec:
            payload["chart_spec"] = copy.deepcopy(chart_artifact.spec)
        if chart_artifact.spec_id:
            payload["chart_spec_id"] = chart_artifact.spec_id

    analysis_artifact = ctx.artifacts.analysis
    if analysis_artifact:
        if analysis_artifact.analysis_text:
            payload["analysis"] = analysis_artifact.analysis_text
            if analysis_artifact.length is not None:
                payload["analysis_length"] = analysis_artifact.length
        if analysis_artifact.stock_widget and analysis_artifact.stock_widget not in ({}, None):
            payload["stock_widget"] = copy.deepcopy(analysis_artifact.stock_widget)
        if analysis_artifact.web_context and analysis_artifact.web_context not in ({}, None):
            payload["web_context"] = copy.deepcopy(analysis_artifact.web_context)

    if ctx.web_search is not None and not payload.get("web_context"):
        try:
            payload["web_context"] = ctx.web_search.to_payload()
        except Exception:
            pass

    if ctx.artifacts.market and ctx.artifacts.market.snapshot and not payload.get("stock_widget"):
        payload["stock_widget"] = copy.deepcopy(ctx.artifacts.market.snapshot)

    payload["updated_at"] = datetime.utcnow().isoformat()
    sanitized = sanitize_for_json(payload)
    return sanitized if isinstance(sanitized, dict) else None


def _compose_sql_ready_payload(ctx: PlannerPhaseContext) -> Optional[Dict[str, Any]]:
    generation = getattr(ctx.artifacts, "sql_generation", None)
    execution = getattr(ctx.artifacts, "sql_execution", None)
    snapshot = ctx.revision_snapshot if isinstance(ctx.revision_snapshot, dict) else None
    if not generation and snapshot and snapshot.get("sql"):
        generation = SimpleNamespace(sql=snapshot.get("sql"))
    if not execution and snapshot and (
        snapshot.get("sql_row_count") is not None
        or snapshot.get("columns")
        or snapshot.get("data_sample")
    ):
        execution = SimpleNamespace(
            row_count=snapshot.get("sql_row_count"),
            columns=list(snapshot.get("columns") or []),
            sample_rows=_limit_sample_rows(snapshot.get("data_sample") or []),
            dataset_preview=_limit_sample_rows(snapshot.get("data_sample") or []),
        )
    if not generation and not execution:
        return None
    payload: Dict[str, Any] = {
        "reused": bool(ctx.reused_sql),
        "schedule_stage": "sql",
    }
    if generation and generation.sql:
        payload["sql"] = generation.sql
    if execution:
        if execution.row_count is not None:
            payload["row_count"] = execution.row_count
        if execution.columns:
            payload["columns"] = list(execution.columns)
        samples = execution.sample_rows or execution.dataset_preview
        sample_rows = _limit_sample_rows(samples)
        if sample_rows:
            payload["sample_data"] = sample_rows
    if ctx.snapshot_age_seconds is not None:
        payload["snapshot_age_seconds"] = ctx.snapshot_age_seconds
    elif ctx.reused_sql:
        payload["snapshot_age_seconds"] = 0.0
    return payload


def _compose_chart_ready_payload(ctx: PlannerPhaseContext) -> Optional[Dict[str, Any]]:
    chart_artifact = getattr(ctx.artifacts, "chart", None)
    if not chart_artifact or not chart_artifact.spec:
        return None
    summary: Dict[str, Any] = {}
    if chart_artifact.chart_type:
        summary["chart_type"] = chart_artifact.chart_type
    if chart_artifact.series_count is not None:
        summary["series_count"] = chart_artifact.series_count
    if chart_artifact.design:
        summary["design"] = copy.deepcopy(chart_artifact.design)
    payload: Dict[str, Any] = {
        "chart_spec": copy.deepcopy(chart_artifact.spec),
        "chart_spec_id": chart_artifact.spec_id,
        "chart_summary": summary or None,
        "reused": True,
        "schedule_stage": "chart",
    }
    if ctx.snapshot_age_seconds is not None:
        payload["snapshot_age_seconds"] = ctx.snapshot_age_seconds
    return payload




def _compose_stock_ready_payload(ctx: PlannerPhaseContext) -> Optional[Dict[str, Any]]:
    stock_widget: Optional[Dict[str, Any]] = None
    if ctx.artifacts.analysis and ctx.artifacts.analysis.stock_widget:
        stock_widget = copy.deepcopy(ctx.artifacts.analysis.stock_widget)
    elif ctx.revision_snapshot and ctx.revision_snapshot.get('stock_widget'):
        stock_widget = copy.deepcopy(ctx.revision_snapshot['stock_widget'])
    elif ctx.artifacts.market and ctx.artifacts.market.snapshot:
        stock_widget = copy.deepcopy(ctx.artifacts.market.snapshot)
    if not stock_widget:
        return None
    payload: Dict[str, Any] = {
        'stock_widget': stock_widget,
        'reused': True,
        'schedule_stage': 'hedged_accessories',
    }
    if ctx.snapshot_age_seconds is not None:
        payload['snapshot_age_seconds'] = ctx.snapshot_age_seconds
    return payload

def _compose_web_ready_payload(ctx: PlannerPhaseContext) -> Optional[Dict[str, Any]]:
    web_payload: Optional[Dict[str, Any]] = None
    if ctx.artifacts.analysis and ctx.artifacts.analysis.web_context:
        web_payload = copy.deepcopy(ctx.artifacts.analysis.web_context)
    elif ctx.revision_snapshot and ctx.revision_snapshot.get("web_context"):
        web_payload = copy.deepcopy(ctx.revision_snapshot["web_context"])
    elif ctx.artifacts.web and ctx.artifacts.web.to_dict():
        web_payload = ctx.artifacts.web.to_dict()
    if not web_payload:
        return None
    payload = sanitize_for_json(web_payload) or {}
    if not isinstance(payload, dict):
        return None
    payload["reused"] = True
    payload.setdefault("schedule_stage", "hedged_accessories")
    if ctx.snapshot_age_seconds is not None:
        payload["snapshot_age_seconds"] = ctx.snapshot_age_seconds
    return payload

def _cached_event(
    name: str,
    payload: Dict[str, Any],
    *,
    schedule_stage: str,
    flow_mode: FlowMode,
    parallel_group: Optional[str] = None,
) -> Dict[str, Any]:
    sanitized = sanitize_for_json(payload) if isinstance(payload, dict) else {"payload": sanitize_for_json(payload)}
    if not isinstance(sanitized, dict):
        sanitized = {"payload": sanitized}
    sanitized.setdefault("schedule_stage", schedule_stage)
    if parallel_group:
        sanitized.setdefault("parallel_group", parallel_group)
    sanitized.setdefault("flow_mode", flow_mode.value)
    sanitized.setdefault("reused", True)
    sanitized.setdefault("ts", datetime.utcnow().isoformat())
    return {
        "event": name,
        "data": sanitized,
    }

def _hydrate_context_from_snapshot(
    ctx: PlannerPhaseContext,
    snapshot: Optional[SessionStateSnapshot],
    artifacts: Optional[PipelineArtifacts],
) -> None:
    revision_snapshot = extract_revision_snapshot(snapshot)
    if revision_snapshot:
        ctx.revision_snapshot = copy.deepcopy(revision_snapshot)
        ctx.prior_intent_signature = revision_snapshot.get("intent_signature")
    else:
        ctx.revision_snapshot = None
        ctx.prior_intent_signature = None

    if artifacts is None:
        if ctx.revision_snapshot:
            artifacts = PipelineArtifacts()
        else:
            return

    if ctx.revision_snapshot:
        chart_spec = ctx.revision_snapshot.get("chart_spec")
        if chart_spec and artifacts.chart is None:
            artifacts.chart = ChartArtifact(
                query=ctx.query,
                spec=copy.deepcopy(chart_spec),
                spec_id=ctx.revision_snapshot.get("chart_spec_id"),
            )
        if ctx.revision_snapshot.get("sql") and artifacts.sql_generation is None:
            artifacts.sql_generation = SQLGenerationArtifact(
                query=ctx.query,
                sql=ctx.revision_snapshot.get("sql"),
                status="completed",
            )
        if artifacts.sql_execution is None:
            if ctx.revision_snapshot.get("sql_row_count") is not None or ctx.revision_snapshot.get("data_sample"):
                artifacts.sql_execution = SQLExecutionArtifact(
                    query=ctx.query,
                    row_count=ctx.revision_snapshot.get("sql_row_count"),
                    columns=list(ctx.revision_snapshot.get("columns") or []),
                    sample_rows=_limit_sample_rows(ctx.revision_snapshot.get("data_sample") or []),
                    dataset_preview=_limit_sample_rows(ctx.revision_snapshot.get("data_sample") or []),
                    status="completed",
                )
        if artifacts.analysis is None and (
            ctx.revision_snapshot.get("analysis")
            or ctx.revision_snapshot.get("stock_widget")
            or ctx.revision_snapshot.get("web_context")
        ):
            artifacts.analysis = AnalysisArtifact(
                query=ctx.query,
                analysis_text=ctx.revision_snapshot.get("analysis"),
                length=ctx.revision_snapshot.get("analysis_length"),
                stock_widget=copy.deepcopy(ctx.revision_snapshot.get("stock_widget")) if ctx.revision_snapshot.get("stock_widget") else None,
                web_context=copy.deepcopy(ctx.revision_snapshot.get("web_context")) if ctx.revision_snapshot.get("web_context") else None,
            )
        if artifacts.web is None and isinstance(ctx.revision_snapshot.get("web_context"), dict):
            web_payload = copy.deepcopy(ctx.revision_snapshot["web_context"])
            artifacts.web = WebContextArtifact(
                query=ctx.query,
                summary=web_payload.get("summary"),
                snippets=list(web_payload.get("snippets") or []),
                search_id=web_payload.get("search_id"),
                from_cache=web_payload.get("from_cache"),
                metadata=copy.deepcopy(web_payload.get("metadata") or {}),
                topic=web_payload.get("topic"),
                latency_stats=web_payload.get("latency_stats"),
            )

    cached_tool_results: List[Dict[str, Any]] = []
    if ctx.revision_snapshot:
        stock_snapshot = ctx.revision_snapshot.get("stock_widget")
        if stock_snapshot:
            cached_tool_results.append(
                {
                    "tool": "stock_tracker",
                    "status": "completed",
                    "payload": {"stock_widget": copy.deepcopy(stock_snapshot)},
                    "reused": True,
                }
            )
        web_snapshot = ctx.revision_snapshot.get("web_context")
        if isinstance(web_snapshot, dict) and web_snapshot:
            cached_tool_results.append(
                {
                    "tool": "web_retriever",
                    "status": "completed",
                    "payload": copy.deepcopy(web_snapshot),
                    "reused": True,
                }
            )
    if cached_tool_results:
        ctx.tool_parallel_results = cached_tool_results
    if ctx.revision_snapshot and ctx.revision_snapshot.get("web_context") and getattr(ctx, "web_search", None) is None:
        web_ctx_payload = copy.deepcopy(ctx.revision_snapshot["web_context"])
        ctx.web_search = SimpleNamespace(
            to_payload=lambda payload=web_ctx_payload: copy.deepcopy(payload),
            summary=web_ctx_payload.get("summary"),
            latency_ms=web_ctx_payload.get("latency_ms"),
        )
    if ctx.revision_snapshot and ctx.revision_snapshot.get("stock_widget"):
        ctx.stock_widget_seeded = True
    if ctx.revision_snapshot and ctx.revision_snapshot.get("web_context"):
        ctx.web_search_seeded = True
    ctx.artifacts = artifacts
    ctx.snapshot_artifacts = artifacts
    execution_artifact = getattr(ctx.artifacts, "sql_execution", None)
    preview_payload = _dataset_preview_from_snapshot(snapshot)
    if execution_artifact and preview_payload:
        rows = list(preview_payload.get("rows") or [])
        if rows:
            execution_artifact.dataset_preview = rows
            if not getattr(execution_artifact, "dataset", None):
                execution_artifact.dataset = list(rows)
            if execution_artifact.row_count is None:
                row_count = preview_payload.get("row_count")
                if isinstance(row_count, int):
                    execution_artifact.row_count = row_count
    receipts_payload = {}
    if snapshot and isinstance(snapshot.tool_cache, dict):
        receipts_payload = snapshot.tool_cache.get("tool_receipts") or {}
    for tool_name, payload in (receipts_payload or {}).items():
        try:
            ctx.tool_receipts[tool_name] = ToolInvocationReceipt.from_dict(payload)
        except Exception as exc:  # pragma: no cover - defensive
            logger.debug("Unable to hydrate tool receipt for %s: %s", tool_name, exc)

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

    def __init__(
        self,
        *,
        flow_mode: FlowMode = FlowMode.DIRECT,
        parallelism_enabled: Optional[bool] = None,
    ) -> None:
        self.unified_client = get_unified_client()
        self.config_store = CONFIG_STORE
        self.flow_label = "planner-executor"
        self.flow_mode = flow_mode
        self.follow_up_route = FollowUpRoute.FULL_PIPELINE
        self._prefetched_snapshot: Optional[SessionStateSnapshot] = None
        mode_config = get_mode_config(flow_mode)
        # Tool fan-out defaults to the scheduler mode unless explicitly overridden.
        self.parallelism_enabled = mode_config.parallelism_enabled if parallelism_enabled is None else parallelism_enabled
        self.hooks: AnalyticsFlowHooks = NullFlowHooks()
        self._latest_artifacts: Optional[PipelineArtifacts] = None

    async def _persist_session_state(
        self,
        ctx: PlannerPhaseContext,
        *,
        record_sql: bool = False,
        record_chart: bool = False,
        record_analysis: bool = False,
        tool_bundle: Optional[Dict[str, Any]] = None,
        record_artifacts: bool = True,
    ) -> None:
        session_id = getattr(ctx, "session_id", None)
        if not session_id:
            return
        repository = get_session_state_repository()
        snapshot = await repository.load(session_id)
        if snapshot is None:
            snapshot = SessionStateSnapshot(session_id=session_id)
        updated = False
        sql_artifact = ctx.artifacts.sql_generation if record_sql else None
        if sql_artifact and sql_artifact.sql:
            snapshot.record_outputs(sql=sql_artifact.sql)
            updated = True
            execution_artifact = ctx.artifacts.sql_execution
            if execution_artifact and execution_artifact.dataset_preview:
                sanitized_preview = sanitize_for_json(
                    {
                        "rows": execution_artifact.dataset_preview,
                        "row_count": execution_artifact.row_count,
                    }
                )
                snapshot.record_tool_result("planner_dataset_preview", sanitized_preview)
                updated = True
        chart_artifact = ctx.artifacts.chart if record_chart else None
        if chart_artifact and chart_artifact.spec:
            snapshot.record_outputs(chart_spec=chart_artifact.spec)
            updated = True
        market_artifact = getattr(ctx.artifacts, "market", None)
        if market_artifact and getattr(market_artifact, "snapshot", None):
            snapshot.record_tool_result(
                "planner_stock_widget",
                sanitize_for_json(market_artifact.snapshot),
            )
            updated = True
        analysis_artifact = ctx.artifacts.analysis if record_analysis else None
        if analysis_artifact and analysis_artifact.analysis_text:
            snapshot.record_outputs(analysis=analysis_artifact.analysis_text)
            updated = True
        if tool_bundle:
            sanitized_bundle = sanitize_for_json(tool_bundle)
            snapshot.record_tool_result("planner_bundle", sanitized_bundle)
            updated = True
        if record_artifacts:
            artifacts_payload = ctx.artifacts.to_dict()
            if artifacts_payload:
                snapshot.record_artifacts(artifacts_payload)
                updated = True
        revision_payload = _build_revision_snapshot_payload(ctx)
        if revision_payload:
            snapshot.record_revision_snapshot(revision_payload)
            ctx.revision_snapshot = revision_payload
            updated = True
        planner_meta = snapshot.tool_cache.setdefault("planner_metadata", {})
        route_value = getattr(ctx, "follow_up_route", FollowUpRoute.FULL_PIPELINE).value
        if planner_meta.get("follow_up_route") != route_value:
            planner_meta["follow_up_route"] = route_value
            snapshot.tool_cache["planner_metadata"] = planner_meta
            updated = True
        receipts = getattr(ctx, "tool_receipts", None)
        if receipts:
            for tool_name, receipt in receipts.items():
                if isinstance(receipt, ToolInvocationReceipt):
                    snapshot.record_tool_receipt(tool_name, receipt.to_dict())
                elif isinstance(receipt, dict):
                    snapshot.record_tool_receipt(tool_name, sanitize_for_json(receipt))
            updated = True
        if updated:
            await repository.save(snapshot)

    async def initialize_context(self, query: str, session_id: Optional[str] = None) -> PlannerPhaseContext:
        return await _initialize_context(self, query, session_id)

    def _capture_artifacts(self, ctx: PlannerPhaseContext) -> None:
        self._latest_artifacts = ctx.artifacts

    def latest_artifacts(self) -> Optional[PipelineArtifacts]:
        return self._latest_artifacts

    def prime_with_snapshot(self, snapshot: Optional[SessionStateSnapshot]) -> None:
        self._prefetched_snapshot = snapshot

    def set_follow_up_route(self, route: FollowUpRoute) -> None:
        self.follow_up_route = route

    def _mark_delta_event(self, event: Dict[str, Any]) -> Dict[str, Any]:
        data = event.setdefault("data", {})
        data["delta"] = True
        data.setdefault("parallel_group", "accessory_delta")
        return event

    def _ingest_tool_event(self, ctx: PlannerPhaseContext, event: Dict[str, Any]) -> None:
        if not isinstance(event, dict):
            return
        if event.get("event") != "tool_parallel_result":
            return
        data = event.get("data") or {}
        tool_name = str(data.get("tool") or "").strip().lower()
        status = str(data.get("status") or "").strip().lower()
        payload = data.get("payload") or {}
        if tool_name == "web_retriever" and status in {"completed", "complete", "success"}:
            if isinstance(payload, dict) and payload.get("ready"):
                _seed_web_search_from_payload(ctx, payload)
        elif tool_name == "stock_tracker" and status in {"completed", "complete", "success"}:
            if isinstance(payload, dict):
                _seed_stock_widget_from_payload(ctx, payload)

    def _start_tool_parallelism(
        self,
        ctx: PlannerPhaseContext,
        *,
        adapters: Optional[Sequence[Any]] = None,
        concurrency_override: Optional[int] = None,
    ) -> Tuple[Task, asyncio.Queue]:
        queue: asyncio.Queue = asyncio.Queue()

        async def runner() -> None:
            async for event in run_tool_parallelism(
                ctx,
                adapters=adapters,
                concurrency_override=concurrency_override,
            ):
                self._ingest_tool_event(ctx, event)
                await queue.put(event)

        task = asyncio.create_task(runner())
        return task, queue

    @staticmethod
    def _flush_tool_events(queue: Optional[asyncio.Queue]) -> List[Dict[str, Any]]:
        flushed: List[Dict[str, Any]] = []
        if queue is None:
            return flushed
        while True:
            try:
                flushed.append(queue.get_nowait())
            except QueueEmpty:
                break
        return flushed

    async def _emit_post_analysis_accessories(self, ctx: PlannerPhaseContext) -> AsyncGenerator[Dict[str, Any], None]:
        mode_config = get_mode_config(ctx.flow_mode)
        if mode_config.accessories_in_critical_path:
            return

        accessory_tools = {"web_retriever", "stock_tracker"}
        existing_results = getattr(ctx, "tool_parallel_results", []) or []
        completed_tools = {result.get("tool") for result in existing_results}
        pending_tools = [tool for tool in accessory_tools if tool not in completed_tools]
        if pending_tools:
            adapter_lookup = {adapter.name: adapter for adapter in get_default_tool_adapters()}
            adapters = [adapter_lookup[name] for name in pending_tools if name in adapter_lookup]
            if adapters:
                async for event in run_tool_parallelism(
                    ctx,
                    adapters=tuple(adapters),
                    concurrency_override=len(adapters),
                ):
                    self._ingest_tool_event(ctx, event)
                    yield self._mark_delta_event(event)

        if ctx.web_search is None and not getattr(ctx, "web_search_seeded", False):
            async for event in self._web_search_phase(ctx):
                yield self._mark_delta_event(event)
        await self._persist_session_state(ctx, record_artifacts=True)

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

        plan_payload: Optional[Dict[str, Any]] = None
        if hasattr(plan, "model_dump"):
            plan_payload = plan.model_dump()
        elif hasattr(plan, "dict"):
            plan_payload = plan.dict()
        input_payload = {
            "query": query,
            "intent": getattr(intent, "intent_key", None),
            "plan": plan_payload,
            "selected_template_id": selected_template_id,
        }
        receipt = ctx.tool_receipts.get("sql_chain")
        if receipt:
            receipt.status = "running"
            receipt.reused = False
            if not receipt.input_hash:
                receipt.input_hash = _hash_payload(input_payload)
            receipt.attempts = 0
            receipt.error = None
            receipt.output_hash = None
        else:
            receipt = ToolInvocationReceipt(
                tool="sql_chain",
                status="running",
                attempts=0,
                input_hash=_hash_payload(input_payload),
            )
        start_time = time.time()
        ctx.tool_receipts["sql_chain"] = receipt

        sql_progress = EventEmitter.progress("sql_compilation", "Generating SQL with Responses API...")
        sql_progress["data"]["ts"] = datetime.utcnow().isoformat()
        yield sql_progress
        timed_emitter.start_step("sql_generation")
        MAX_SQL_ATTEMPTS = 3
        sql = ""
        llm_used = False
        attempt_logs: List[Dict[str, Any]] = []
        validated_attempt: Optional[int] = None
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
            receipt.attempts += 1
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
                    if ok:
                        sql = candidate_sql
                        llm_used = True
                        validated_attempt = attempt
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

        generation_status = "generated" if sql else "failed"
        _set_sql_generation_artifact(
            ctx,
            sql=sql if sql else None,
            template_id=selected_template_id,
            attempts=attempt_logs,
            llm_used=llm_used,
            last_error_code=last_error_code,
            last_error_detail=last_error_detail,
            status=generation_status,
        )
        self._capture_artifacts(ctx)
        if sql:
            await self._persist_session_state(ctx, record_sql=True)
        if not sql:
            failure_event = EventEmitter.error(
                "sql_compilation",
                "Unable to generate valid SQL after 3 attempts",
                details={"attempts": attempt_logs, "last_error": last_error_code, "last_detail": last_error_detail},
                code=last_error_code or "SQL_RETRY_EXHAUSTED",
            )
            failure_event["data"]["ts"] = datetime.utcnow().isoformat()
            yield failure_event
            receipt.status = "failed"
            receipt.error = last_error_detail or last_error_code or "SQL_RETRY_EXHAUSTED"
            receipt.elapsed_ms = int((time.time() - start_time) * 1000)
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
        latest_attempt = validated_attempt
        if latest_attempt is None:
            for entry in reversed(attempt_logs):
                if isinstance(entry, dict) and "attempt" in entry:
                    latest_attempt = entry.get("attempt")
                    break
        validation_event = EventEmitter.result(
            "sql_validated",
            {
                "ok": ok,
                "issues_count": len(issues),
                "attempt": latest_attempt,
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
                llm_used=llm_used,
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
            receipt.status = "failed"
            receipt.error = "; ".join(issues) if issues else "SQL validation failed"
            receipt.elapsed_ms = int((time.time() - start_time) * 1000)
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
                llm_used=llm_used,
                last_error_code=None,
                last_error_detail=None,
                status="validated",
            )
            self._capture_artifacts(ctx)
        if not ctx.halted:
            receipt.status = "completed"
            receipt.elapsed_ms = int((time.time() - start_time) * 1000)
            receipt.error = None
            if sql:
                receipt.output_hash = _hash_payload({"sql": sql})
        execution_progress = EventEmitter.progress(
            "sql_execution", "Executing query..."
        )
        execution_progress["data"]["ts"] = datetime.utcnow().isoformat()
        yield execution_progress
        exec_start = time.time()
        try:
            data = await execute_sql(sql)
            exec_elapsed = int((time.time() - exec_start) * 1000)
            _set_sql_execution_artifact(
                ctx,
                data=data,
                elapsed_ms=exec_elapsed,
                status="success",
            )
            self._capture_artifacts(ctx)
        except Exception as exec_exc:
            exec_elapsed = int((time.time() - exec_start) * 1000)
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
            receipt.status = "failed"
            receipt.error = str(exec_exc)
            receipt.elapsed_ms = int((time.time() - start_time) * 1000)
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

    async def run_chart_phase(self, ctx: PlannerPhaseContext, *, intent: IntentModel, plan: QueryPlanModel) -> AsyncGenerator[Dict[str, Any], None]:
        plan_payload: Optional[Dict[str, Any]] = None
        if hasattr(plan, "model_dump"):
            plan_payload = plan.model_dump()
        elif hasattr(plan, "dict"):
            plan_payload = plan.dict()
        input_payload = {
            "query": ctx.query,
            "intent": getattr(intent, "intent_key", None),
            "plan": plan_payload,
        }
        receipt = ctx.tool_receipts.get("chart_builder")
        if ctx.reused_chart:
            if receipt:
                receipt.status = "reused"
                receipt.reused = True
                receipt.error = None
            else:
                receipt = ToolInvocationReceipt(
                    tool="chart_builder",
                    status="reused",
                    attempts=0,
                    input_hash=_hash_payload(input_payload),
                    reused=True,
                )
            ctx.tool_receipts["chart_builder"] = receipt
            cached_payload = _compose_chart_ready_payload(ctx)
            if cached_payload:
                yield _cached_event(
                    "chart_ready",
                    cached_payload,
                    schedule_stage="chart",
                    flow_mode=self.flow_mode,
                    parallel_group="core_sequential",
                )
            return
        if receipt:
            receipt.status = "running"
            receipt.reused = False
            receipt.error = None
            if not receipt.input_hash:
                receipt.input_hash = _hash_payload(input_payload)
        else:
            receipt = ToolInvocationReceipt(
                tool="chart_builder",
                status="running",
                attempts=0,
                input_hash=_hash_payload(input_payload),
            )
        chart_start = time.time()
        ctx.tool_receipts["chart_builder"] = receipt
        data = _get_sql_dataset(ctx)
        if not data:
            receipt.status = "skipped"
            receipt.elapsed_ms = int((time.time() - chart_start) * 1000)
            return
        query = ctx.query
        chart_progress = EventEmitter.progress(
            "chart_generation", "Planning chart..."
        )
        chart_progress["data"]["ts"] = datetime.utcnow().isoformat()
        yield chart_progress
        chart_plan = plan_chart_rule_based(
            data,
            query,
            intent.intent_key,
            statistic=getattr(plan, "statistic", None),
        )
        spec = build_chart_spec(
            data,
            chart_plan.dict(),
            CONFIGS.charts,
            intent_key=intent.intent_key,
            comparison=plan.comparison,
            statistic=getattr(plan, "statistic", None),
        )
        chart_design = _generate_chart_design(intent.intent_key, plan, data, spec)
        spec.setdefault("meta", {}).setdefault("chartDesign", chart_design)
        _set_chart_artifact(
            ctx,
            spec=spec,
            chart_plan=chart_plan,
            chart_design=chart_design,
        )
        self._capture_artifacts(ctx)
        await self._persist_session_state(ctx, record_chart=True)
        chart_elapsed = int((time.time() - chart_start) * 1000)
        receipt.status = "completed"
        receipt.elapsed_ms = chart_elapsed
        receipt.output_hash = _hash_payload(spec)
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
            receipt.metadata["validation_warning"] = str(ve)
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
        ready_payload = _compose_chart_ready_payload(ctx)
        if ready_payload:
            ready_payload["reused"] = False
            ready_payload.setdefault("schedule_stage", "chart")
            ready_payload.setdefault("parallel_group", "core_sequential")
            ready_payload.setdefault("flow_mode", self.flow_mode.value)
            ready_payload.setdefault("ts", datetime.utcnow().isoformat())
            yield {
                "event": "chart_ready",
                "data": sanitize_for_json(ready_payload),
            }

    async def _ensure_analysis_dependencies(self, ctx: PlannerPhaseContext) -> AsyncGenerator[Dict[str, Any], None]:
        if getattr(ctx, "accessories_prefetched", False):
            return
        required_tools: List[str] = []
        mode_config = get_mode_config(ctx.flow_mode)
        has_cached_stock = bool(ctx.artifacts.analysis and ctx.artifacts.analysis.stock_widget)
        if not has_cached_stock:
            market_artifact = getattr(ctx.artifacts, "market", None)
            has_cached_stock = bool(market_artifact and getattr(market_artifact, "snapshot", None))
        if not has_cached_stock and getattr(ctx, "stock_widget_seeded", False):
            has_cached_stock = True
        has_cached_web = bool(ctx.artifacts.analysis and ctx.artifacts.analysis.web_context)
        if ctx.parallelism_enabled:
            existing = getattr(ctx, "tool_parallel_results", []) or []

            def _has_completed(tool_name: str) -> bool:
                return any(
                    result.get("tool") == tool_name and result.get("status") == "completed"
                    for result in existing
                )

            if not _has_completed("stock_tracker") and not has_cached_stock:
                required_tools.append("stock_tracker")
            if not _has_completed("web_retriever") and not has_cached_web:
                required_tools.append("web_retriever")

        if required_tools:
            adapter_lookup = {adapter.name: adapter for adapter in get_default_tool_adapters()}
            subset = [adapter_lookup[name] for name in required_tools if name in adapter_lookup]
            if subset:
                async for event in run_tool_parallelism(ctx, adapters=subset, concurrency_override=len(subset)):
                    self._ingest_tool_event(ctx, event)
                    yield event

        has_web_context = (
            ctx.web_search is not None
            or has_cached_web
            or getattr(ctx, "web_search_seeded", False)
        )
        if not has_web_context and mode_config.accessories_in_critical_path:
            async for event in self._web_search_phase(ctx):
                yield event
        ctx.accessories_prefetched = True

    async def run_analysis_phase(self, ctx: PlannerPhaseContext) -> AsyncGenerator[Dict[str, Any], None]:
        receipt = ctx.tool_receipts.get("analysis_synthesis")
        if ctx.reused_analysis:
            if receipt:
                receipt.status = "reused"
                receipt.reused = True
                receipt.error = None
            else:
                receipt = ToolInvocationReceipt(
                    tool="analysis_synthesis",
                    status="reused",
                    attempts=0,
                    reused=True,
                )
            ctx.tool_receipts["analysis_synthesis"] = receipt
            return
        if receipt:
            receipt.status = "running"
            receipt.reused = False
            receipt.error = None
            receipt.output_hash = None
        else:
            receipt = ToolInvocationReceipt(
                tool="analysis_synthesis",
                status="running",
                attempts=0,
            )
        ctx.tool_receipts["analysis_synthesis"] = receipt
        data = _get_sql_dataset(ctx)
        if not data:
            receipt.status = "skipped"
            return
        async for dependency_event in self._ensure_analysis_dependencies(ctx):
            yield dependency_event
        session_id = ctx.session_id
        query = ctx.query
        sql_artifact = ctx.artifacts.sql_generation
        sql = sql_artifact.sql if sql_artifact and sql_artifact.sql else ""
        chart_artifact = ctx.artifacts.chart
        chart_spec = chart_artifact.spec if chart_artifact and chart_artifact.spec else None
        input_payload = {
            "query": query,
            "sql_hash": _hash_payload(sql) if sql else None,
            "chart_present": bool(chart_spec),
            "web_present": bool(ctx.web_search or ctx.artifacts.web),
        }
        if not receipt.input_hash:
            receipt.input_hash = _hash_payload(input_payload)
        receipt.attempts += 1
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
            chart_spec=chart_spec,
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
        analysis_payload = {
            "analysis_length": len(full_analysis),
            "analysis": full_analysis,
        }
        receipt.elapsed_ms = analysis_elapsed
        tldr_summary = _extract_tldr(full_analysis)
        if tldr_summary:
            analysis_payload["tldr"] = tldr_summary
        bullets = _extract_bullets(full_analysis)
        if bullets:
            analysis_payload["bullets"] = bullets
        key_numbers = _extract_key_numbers(full_analysis)
        if key_numbers:
            analysis_payload["key_numbers"] = key_numbers
        risk_watch = _extract_risk_watch(full_analysis)
        if risk_watch:
            analysis_payload["risk_watch"] = risk_watch
        next_steps = _extract_next_steps(full_analysis)
        if next_steps:
            analysis_payload["next_steps"] = next_steps
        tool_bundle = collect_tool_bundle(
            manifest=getattr(ctx, "tool_parallel_manifest", None),
            results=getattr(ctx, "tool_parallel_results", None),
        )
        stock_widget = None
        if tool_bundle:
            stock_widget = tool_bundle.get("stock_widget")
            sources = tool_bundle.get("sources") or {}
            if sources:
                if any(
                    sources.get(alias) == "cached"
                    for alias in ("web_retriever", "web_retriever_cached", "web_retriever_live")
                ):
                    ctx.reused_web = True
                if sources.get("stock_tracker") == "cached":
                    ctx.reused_stock = True
            analysis_payload.update(tool_bundle)
        guardrail_payload = None
        if ctx.web_search:
            web_payload = ctx.web_search.to_payload()
            analysis_payload['web_context'] = web_payload
            guardrail_payload = _evaluate_latency_guardrail(web_payload.get("latency_stats"))
        elif ctx.artifacts.web:
            guardrail_payload = _evaluate_latency_guardrail(ctx.artifacts.web.latency_stats)
        if stock_widget:
            _set_market_artifact(ctx, widget=stock_widget)
            self._capture_artifacts(ctx)
        _set_analysis_artifact(
            ctx,
            analysis_text=full_analysis,
            fragments=fragments,
            tool_bundle=tool_bundle or None,
            summary=tldr_summary,
            bullets=bullets,
            key_numbers=key_numbers,
            risk_watch=risk_watch,
            next_steps=next_steps,
        )
        if ctx.artifacts.analysis and ctx.artifacts.analysis.evidence:
            analysis_payload["evidence"] = list(ctx.artifacts.analysis.evidence)
        if guardrail_payload:
            analysis_payload["latency_guardrail"] = guardrail_payload
        self._capture_artifacts(ctx)
        await self._persist_session_state(ctx, record_analysis=True, tool_bundle=tool_bundle or None)
        receipt.status = "completed"
        receipt.error = None
        receipt.output_hash = _hash_payload(analysis_payload)
        receipt.metadata["fragment_count"] = len(fragments)
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
        banner_config = FOLLOW_UP_BANNERS.get(ctx.follow_up_route, FOLLOW_UP_BANNERS[FollowUpRoute.FULL_PIPELINE])
        banner_event = EventEmitter.progress("follow_up_route", banner_config["message"])
        banner_event["data"]["ts"] = datetime.utcnow().isoformat()
        banner_event["data"]["schedule_stage"] = "analysis"
        banner_event["data"]["banner"] = {
            "title": banner_config["title"],
            "message": banner_config["message"],
            "route": ctx.follow_up_route.value,
        }
        yield banner_event
        async for accessory_event in self._emit_post_analysis_accessories(ctx):
            yield accessory_event
        from analytics.core.clarify import get_session_store
        session_store = await get_session_store()
        await session_store.cleanup_expired()
        total_elapsed = int((time.time() - ctx.workflow_start) * 1000)
        planner_payload = _build_planner_result_payload(ctx)
        result_event = EventEmitter.result(
            "planner_result", planner_payload
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
            card = {
                "type": "web_context",
                "state": "error",
                "message": summary,
            }
            _set_web_artifact(ctx, payload=payload, topic=None, search_result=None)
            self._capture_artifacts(ctx)
            result_event = EventEmitter.result("web_search", {"web_context": payload, "specialist_card": card})
            result_event["data"]["ts"] = datetime.utcnow().isoformat()
            result_event["data"]["specialist_card"] = card
            result_event["data"]["schedule_stage"] = "accessories_post"
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
        card = {
            "type": "web_context",
            "state": "ready",
            "topic": payload.get("search_topic") or topic,
            "summary": payload.get("summary"),
            "snippets": payload.get("snippets", []),
        }
        event_payload = {"web_context": payload, "specialist_card": card}
        result_event = EventEmitter.result("web_search", event_payload)
        result_event["data"]["ts"] = datetime.utcnow().isoformat()
        result_event["data"]["specialist_card"] = card
        result_event["data"]["schedule_stage"] = "accessories_post"
        yield result_event
    
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
        "Enhanced workflow with structured decision events and timing."
        ctx = await _initialize_context(self, query, session_id)
        session_id = ctx.session_id
        timed_emitter = ctx.timed_emitter
        yield EventEmitter.session_started(session_id)

        from .pipeline_tools import get_planner_tool_registry  # Local import to avoid circular dependency

        registry = get_planner_tool_registry()
        executed: Set[str] = set()
        mode_config = get_mode_config(self.flow_mode)
        tool_task: Optional[Task] = None
        tool_queue: Optional[asyncio.Queue] = None

        def pending_tool_events() -> List[Dict[str, Any]]:
            return self._flush_tool_events(tool_queue)

        try:
            async for event in registry.invoke("classification", self, ctx, executed=executed):
                yield event
            await self._persist_session_state(ctx, record_artifacts=True)
            if not ctx.is_financial_query:
                return

            for tool_name in ("intent_detection", "clarification", "plan_generation"):
                async for event in registry.invoke(tool_name, self, ctx, executed=executed):
                    yield event
                await self._persist_session_state(ctx, record_artifacts=True)

            if ctx.intent is None or (ctx.plan or ctx.provisional_plan) is None:
                return

            should_run_parallel = ctx.parallelism_enabled and not (ctx.reuse_sql and ctx.reuse_snapshot_active)
            if should_run_parallel:
                tool_task, tool_queue = self._start_tool_parallelism(ctx)
                for tool_event in pending_tool_events():
                    yield tool_event

            reuse_sql = ctx.reuse_sql and ctx.revision_snapshot is not None
            if not reuse_sql and ctx.snapshot_stale and ctx.revision_snapshot:
                stale_progress = EventEmitter.progress("sql_generation", "Cached SQL snapshot expired - rerunning dataset")
                stale_progress["data"]["ts"] = datetime.utcnow().isoformat()
                stale_progress["data"]["schedule_stage"] = "sql"
                stale_progress["data"]["parallel_group"] = "core_sequential"
                stale_progress["data"]["flow_mode"] = self.flow_mode.value
                stale_progress["data"]["reused"] = False
                yield stale_progress
                for tool_event in pending_tool_events():
                    yield tool_event

            if not reuse_sql:
                async for event in registry.invoke("sql_generation", self, ctx, executed=executed):
                    yield event
                    for tool_event in pending_tool_events():
                        yield tool_event
            else:
                ctx.reused_sql = True
                reuse_status = EventEmitter.progress("sql_generation", "Reusing cached SQL dataset")
                reuse_status["data"]["ts"] = datetime.utcnow().isoformat()
                reuse_status["data"]["schedule_stage"] = "sql"
                reuse_status["data"]["parallel_group"] = "core_sequential"
                reuse_status["data"]["flow_mode"] = self.flow_mode.value
                reuse_status["data"]["reused"] = True
                yield reuse_status
                for tool_event in pending_tool_events():
                    yield tool_event
                receipt = ctx.tool_receipts.get("sql_chain")
                if receipt:
                    receipt.status = "reused"
                    receipt.reused = True
                    receipt.error = None
                sql_payload = _compose_sql_ready_payload(ctx)
                if sql_payload:
                    yield _cached_event(
                        "sql_ready",
                        sql_payload,
                        schedule_stage="sql",
                        flow_mode=self.flow_mode,
                        parallel_group="core_sequential",
                    )
                    for tool_event in pending_tool_events():
                        yield tool_event

            await self._persist_session_state(
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
                    sql_payload["reused"] = False
                    yield {
                        "event": "sql_ready",
                        "data": sanitize_for_json(sql_payload),
                    }
            for tool_event in pending_tool_events():
                yield tool_event

            if tool_task:
                await tool_task
                for tool_event in pending_tool_events():
                    yield tool_event
                tool_task = None
                tool_queue = None

            if reuse_sql:
                stock_payload = _compose_stock_ready_payload(ctx)
                if stock_payload:
                    ctx.reused_stock = True
                    yield _cached_event(
                        "stock_ready",
                        stock_payload,
                        schedule_stage="hedged_accessories",
                        flow_mode=self.flow_mode,
                        parallel_group="tool_fanout",
                    )
                web_payload = _compose_web_ready_payload(ctx)
                if web_payload:
                    ctx.reused_web = True
                    yield _cached_event(
                        "web_ready",
                        web_payload,
                        schedule_stage="hedged_accessories",
                        flow_mode=self.flow_mode,
                        parallel_group="tool_fanout",
                    )
                ctx.accessories_prefetched = True
            else:
                async for event in self._ensure_analysis_dependencies(ctx):
                    yield event
                    for tool_event in pending_tool_events():
                        yield tool_event

            if ctx.halted:
                return

            async for event in registry.invoke("chart_generation", self, ctx, executed=executed):
                yield event
            await self._persist_session_state(
                ctx,
                record_chart=bool(ctx.artifacts.chart and ctx.artifacts.chart.spec),
                record_artifacts=True,
            )

            if mode_config.accessories_in_critical_path:
                async for event in self._web_search_phase(ctx):
                    yield event
                await self._persist_session_state(ctx, record_artifacts=True)

            async for event in registry.invoke("analysis_generation", self, ctx, executed=executed):
                yield event
            await self._persist_session_state(
                ctx,
                record_analysis=bool(
                    ctx.artifacts.analysis and ctx.artifacts.analysis.analysis_text
                ),
                record_artifacts=True,
            )
        finally:
            if tool_task:
                tool_task.cancel()
                with contextlib.suppress(Exception):
                    await tool_task


async def _initialize_context(self, query: str, session_id: Optional[str]) -> PlannerPhaseContext:
    workflow_start = time.time()
    resolved_session = session_id or str(uuid.uuid4())
    timed_emitter = TimedEventEmitter(session_id=resolved_session, flow=self.flow_label)
    ctx = PlannerPhaseContext(
        query=query,
        session_id=resolved_session,
        workflow_start=workflow_start,
        timed_emitter=timed_emitter,
        flow_mode=self.flow_mode,
        configs=CONFIGS.__dict__,
        parallelism_enabled=self.parallelism_enabled,
        follow_up_route=self.follow_up_route,
        reuse_sql=self.follow_up_route == FollowUpRoute.REUSE_SQL,
        stock_only=self.follow_up_route == FollowUpRoute.STOCK_ONLY,
    )
    snapshot = getattr(self, "_prefetched_snapshot", None)
    snapshot_artifacts = _artifacts_from_snapshot(snapshot)
    revision_snapshot = extract_revision_snapshot(snapshot)
    if snapshot_artifacts or revision_snapshot:
        _hydrate_context_from_snapshot(ctx, snapshot, snapshot_artifacts)
    else:
        ctx.revision_snapshot = None
        ctx.prior_intent_signature = None
    if (
        not snapshot_artifacts
        and not revision_snapshot
        and self.follow_up_route == FollowUpRoute.REUSE_SQL
        and self._latest_artifacts is not None
    ):
        cloned_artifacts = copy.deepcopy(self._latest_artifacts)
        ctx.artifacts = copy.deepcopy(cloned_artifacts)
        ctx.snapshot_artifacts = copy.deepcopy(cloned_artifacts)
    return ctx


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
        planner_payload = _build_planner_result_payload(ctx)
        result_event = EventEmitter.result("planner_result", planner_payload)
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
    ctx.reused_sql = False
    ctx.reused_chart = False
    ctx.reused_stock = False
    ctx.reused_web = False
    ctx.reused_analysis = False
    ctx.web_search_seeded = False
    ctx.stock_widget_seeded = False
    current_signature = build_intent_signature(intent, ctx.plan)
    ctx.intent_signature = current_signature
    prior_signature = ctx.prior_intent_signature
    if prior_signature and current_signature:
        ctx.criteria_changed = not signatures_equal(prior_signature, current_signature)
    elif prior_signature and current_signature is None:
        ctx.criteria_changed = True
    else:
        ctx.criteria_changed = False
    ctx.snapshot_age_seconds = (
        _snapshot_age_seconds_from_snapshot(ctx.revision_snapshot) if ctx.revision_snapshot else None
    )
    snapshot_fresh = _is_snapshot_fresh(ctx.revision_snapshot)
    ctx.snapshot_stale = bool(ctx.revision_snapshot) and not snapshot_fresh
    ctx.reuse_snapshot_active = snapshot_fresh and not ctx.criteria_changed
    if ctx.follow_up_route == FollowUpRoute.REUSE_SQL and ctx.reuse_snapshot_active:
        ctx.reuse_sql = current_signature is not None
    else:
        ctx.reuse_sql = False
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

    def __init__(
        self,
        *,
        flow_mode: FlowMode = FlowMode.DIRECT,
        parallelism_enabled: Optional[bool] = None,
    ) -> None:
        self._pipeline = PlannerPipeline(flow_mode=flow_mode, parallelism_enabled=parallelism_enabled)
        self.flow_mode = flow_mode
        self.follow_up_route = FollowUpRoute.FULL_PIPELINE

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

    def prime_with_snapshot(self, snapshot: Optional[SessionStateSnapshot]) -> None:
        self._pipeline.prime_with_snapshot(snapshot)

    def set_follow_up_route(self, route: FollowUpRoute) -> None:
        self.follow_up_route = route
        self._pipeline.set_follow_up_route(route)

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

    def _annotate(self, event: Dict[str, Any]) -> Dict[str, Any]:
        annotated = apply_mode_metadata(event, self.flow_mode)
        data = annotated.setdefault("data", {})
        data.setdefault("follow_up_route", self.follow_up_route.value)
        return annotated

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
                yield self._annotate(event)
            return

        hook_ctx: Dict[str, Any] = {"query": query, "session_id": session_id}
        try:
            async for start_event in hooks.on_flow_start(hook_ctx):
                yield self._annotate(start_event)
            async for event in stream:
                async for pre_event in hooks.before_event(hook_ctx, event):
                    yield self._annotate(pre_event)
                annotated = self._annotate(event)
                yield annotated
                if event.get("event") == "session_started":
                    data = event.get("data") or {}
                    hook_ctx["session_id"] = data.get("session_id", hook_ctx.get("session_id"))
                async for post_event in hooks.after_event(hook_ctx, event):
                    yield self._annotate(post_event)
        except BaseException as exc:
            async for end_event in hooks.on_flow_end(hook_ctx, error=exc):
                yield self._annotate(end_event)
            raise
        else:
            async for end_event in hooks.on_flow_end(hook_ctx):
                yield self._annotate(end_event)
# Standalone wrapper function for main.py
async def run_planner_executor(query: str, session_id: Optional[str] = None) -> AsyncGenerator[Dict[str, Any], None]:
    """Helper to stream planner-executor events without referencing the registry."""
    workflow_instance = PlannerExecutorFlow()
    async for event in workflow_instance.events(query, session_id):
        yield event








