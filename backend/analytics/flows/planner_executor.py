from __future__ import annotations
from typing import AsyncGenerator, Dict, Any, Optional, List, Tuple
from dataclasses import dataclass, field
import asyncio
import os
import logging
import time
import uuid
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
)
from analytics.core.context import get_configs
from analytics.core.config_store import get_config_store
from analytics.core.events import EventEmitter, TimedEventEmitter
from .tooling import run_tool_parallelism
from ..core.intent import intent_to_sql_criteria
from analytics.core.intent import detect_intent, detect_intent_llm, detect_intent_with_clarifications
from analytics.sql.sql_planner import build_query_plan, choose_template
from analytics.sql.compiler import compile_sql_from_plan
from analytics.sql.executor import execute_sql
from analytics.sql.validator import validate_sql
from analytics.sql.templates import fetch_templates_for_intent
from analytics.sql.prompt_builder import build_sql_messages, extract_sql_from_response
from analytics.core.charting import build_chart_spec, plan_chart_rule_based
from analytics.core.telemetry import analysis_chunk as log_analysis_chunk
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
    looks_financial: bool = False
    configs: Dict[str, Any] = field(default_factory=dict)
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
    fallback_used: bool = False
    fallback_reason: Optional[str] = None
    sql_attempt: int = 1
    validation_attempt: int = 1
    data: List[Dict[str, Any]] = field(default_factory=list)
    exec_elapsed_ms: Optional[int] = None
    chart_spec: Optional[Dict[str, Any]] = None
    analysis: str = ""
    parallelism_enabled: bool = False

class PlannerExecutorFlow:
    """Phase 2 workflow that emits SSE-friendly events for the memory pipeline."""
    def __init__(self) -> None:
        self.unified_client = get_unified_client()
        self.config_store = CONFIG_STORE
        self.flow_label = "planner-executor"
        self.parallelism_enabled = _env_flag("ANALYTICS_TOOL_PARALLELISM", default=False)
    def _looks_financial(self, query: str) -> bool:
        q = (query or "").lower()
        keywords = ("market share", "margin", "profit", "earnings", "revenue", "growth", "cash flow", "guidance", "quarter", "qoq", "yoy", "opex", "capex", "gross", "net income")
        return any(keyword in q for keyword in keywords)
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
    yield {
        "event": "classification_started",
        "data": {
            "message": "Starting query classification...",
            "model": "heuristic-keyword-gate",
            "ts": classification_started_ts,
        },
    }
    looks_financial = self._looks_financial(ctx.query)
    ctx.looks_financial = looks_financial
    reasoning_message = (
        "Detected financial analytics keywords" if looks_financial else "No financial analytics keywords detected"
    )
    yield {
        "event": "classification_reasoning",
        "data": {
            "thinking": reasoning_message,
            "confidence": 0.9 if looks_financial else 0.1,
            "category": "financial_analytics" if looks_financial else "other",
            "ts": datetime.utcnow().isoformat(),
        },
    }
    classification_elapsed = timed_emitter.end_step("classification")
    classification_complete = {
        "event": "classification_complete",
        "data": {
            "is_financial": looks_financial,
            "category": "financial_analytics" if looks_financial else "other",
            "confidence": 0.9 if looks_financial else 0.1,
            "ts": datetime.utcnow().isoformat(),
        },
    }
    if classification_elapsed:
        classification_complete["data"]["elapsed_ms"] = classification_elapsed
    yield classification_complete
    if not looks_financial:
        yield {
            "event": "classification_fallback",
            "data": {
                "method": "keyword_gate",
                "ts": datetime.utcnow().isoformat(),
            },
        }
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
        ctx = await _initialize_context(self, query, session_id)
        session_id = ctx.session_id
        timed_emitter = ctx.timed_emitter
        workflow_start = ctx.workflow_start
        yield EventEmitter.session_started(session_id)
        async for event in _classification_phase(self, ctx):
            yield event
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
        # 7) SQL Generation Phase
        sql_progress = EventEmitter.progress("sql_compilation", "Generating SQL with Responses API...")
        sql_progress["data"]["ts"] = datetime.utcnow().isoformat()
        yield sql_progress
        timed_emitter.start_step("sql_generation")
        sql = ""
        llm_used = False
        fallback_used = False
        fallback_reason: Optional[str] = None
        sql_attempt = 1
        generation_elapsed = 0
        def _emit_sql_events(
            sql_text: str,
            elapsed_ms: int,
            *,
            attempt: int,
            llm_flag: bool,
            fallback_flag: bool,
            reason: Optional[str],
        ) -> List[Dict[str, Any]]:
            compiled_event = EventEmitter.result(
                "sql_compiled",
                {
                    "sql_length": len(sql_text),
                    "template_fallback": fallback_flag or not llm_flag,
                    "template_used": selected_template_id,
                    "attempt": attempt,
                    "fallback_reason": reason,
                    "llm_used": llm_flag,
                },
            )
            compiled_event["event"] = "sql_compiled"
            compiled_event["data"].update(
                {
                    "ts": datetime.utcnow().isoformat(),
                    "elapsed_ms": elapsed_ms,
                }
            )
            generated_event = EventEmitter.sql_generated(sql_text)
            generated_event["data"].update(
                {
                    "ts": datetime.utcnow().isoformat(),
                    "elapsed_ms": elapsed_ms,
                    "llm_used": llm_flag,
                    "attempt": attempt,
                    "fallback_reason": reason,
                }
            )
            return [compiled_event, generated_event]
        try:
            messages = await build_sql_messages(
                original_query=query,
                intent=intent,
                plan=provisional_plan,
                config_store=self.config_store,
                templates=candidate_templates,
            )
            if not self.unified_client:
                self.unified_client = get_unified_client()
            if not self.unified_client:
                raise RuntimeError("Unified Responses client is not configured")
            llm_response, _ = await self.unified_client.simple_completion(
                messages=messages,
                reasoning_effort="medium",
            )
            candidate_sql = extract_sql_from_response(llm_response)
            if candidate_sql and candidate_sql.strip():
                sql = candidate_sql.strip()
                llm_used = True
        except Exception as exc:
            logger.warning("[SQL_GENERATION] LLM SQL generation failed: %s", exc)
        compile_elapsed_ms = 0
        if not sql:
            fallback_used = True
            fallback_reason = "llm_sql_empty"
            logger.info(
                "[SQL_GENERATION] Falling back to template due to empty LLM output",
                extra={
                    "flow": self.flow_label,
                    "session_id": session_id,
                    "intent_key": intent.intent_key,
                },
            )
            fallback_notice = EventEmitter.progress(
                "sql_compilation",
                "Using YAML template fallback for SQL generation",
            )
            fallback_notice["data"].update(
                {
                    "ts": datetime.utcnow().isoformat(),
                    "code": "SQL_COMPILATION_FALLBACK",
                    "attempt": sql_attempt,
                }
            )
            yield fallback_notice
            compile_start = time.time()
            try:
                sql = compile_sql_from_plan(provisional_plan, intent, CONFIGS.__dict__, template)
            except ValueError as ve:
                error_msg = str(ve)
                if "This query requires specifying a company" in error_msg:
                    companies_list = CONFIGS.companies.get("companies", {}).get(
                        "semiconductor", []
                    )
                    display_options: list[str] = []
                    for comp in companies_list[:7]:
                        try:
                            ticker_value = comp.get("ticker")
                            display_name = comp.get(
                                "short_name", comp.get("name", ticker_value)
                            )
                            if ticker_value:
                                display_options.append(f"{ticker_value} ({display_name})")
                        except Exception:
                            continue
                    if not display_options:
                        display_options = [
                            "NVDA (Nvidia)",
                            "AMD (AMD)",
                            "INTC (Intel)",
                            "MU (Micron)",
                        ]
                    clarification_request = ClarifyRequestModel(
                        request_id=f"company_req_{int(time.time() * 1000)}",
                        slot="company",
                        question="Which company would you like to analyze?",
                        type="single",
                        options=display_options,
                        default=display_options[0],
                        required=True,
                        reason="Market share analysis requires specifying a company",
                    )
                    company_request = EventEmitter.clarification_request(
                        session_id,
                        {
                            "request_id": clarification_request.request_id,
                            "slot": clarification_request.slot,
                            "question": clarification_request.question,
                            "type": clarification_request.type,
                            "options": clarification_request.options,
                            "default": clarification_request.default,
                            "required": clarification_request.required,
                            "reason": clarification_request.reason,
                            "round": rounds + 1,
                        },
                    )
                    company_request["data"]["ts"] = datetime.utcnow().isoformat()
                    yield company_request
                    try:
                        answer = await asyncio.wait_for(
                            wait_for_answer_blocking(
                                session_id, clarification_request.request_id
                            ),
                            timeout=60.0,
                        )
                        if answer and answer.value:
                            ack_event = EventEmitter.clarification_ack(
                                session_id,
                                clarification_request.request_id,
                                answer.value,
                            )
                            ack_event["data"].update(
                                {
                                    "slot": clarification_request.slot,
                                    "ts": datetime.utcnow().isoformat(),
                                }
                            )
                            yield ack_event
                            intent.slots_detected["company"] = answer.value
                            sql = compile_sql_from_plan(
                                provisional_plan, intent, CONFIGS.__dict__, template
                            )
                        else:
                            error_event = EventEmitter.error(
                                "clarification",
                                "No company selected",
                                code="CLARIFICATION_NO_SELECTION",
                            )
                            error_event["data"]["ts"] = datetime.utcnow().isoformat()
                            yield error_event
                            return
                    except asyncio.TimeoutError:
                        timeout_event = EventEmitter.progress(
                            "clarification_timeout",
                            "Timeout waiting for company selection",
                        )
                        timeout_event["data"]["ts"] = datetime.utcnow().isoformat()
                        yield timeout_event
                        return
                else:
                    error_event = EventEmitter.error(
                        "sql_compilation",
                        str(ve),
                        code="SQL_COMPILATION_ERROR",
                    )
                    error_event["data"]["ts"] = datetime.utcnow().isoformat()
                    yield error_event
                    return
            compile_elapsed_ms = int((time.time() - compile_start) * 1000)
        generation_elapsed = timed_emitter.end_step("sql_generation") or compile_elapsed_ms
        def _validate_sql(current_sql: str) -> Tuple[bool, List[str], int]:
            validate_start = time.time()
            ok, issues = validate_sql(
                current_sql,
                allowed_tables=["comp_financials"],
                max_limit=CONFIGS.database.get("query_defaults", {}).get(
                    "max_limit", 10000
                ),
                granularity=plan.granularity,
            )
            return ok, issues, int((time.time() - validate_start) * 1000)
        # 8) SQL Validation Phase
        validation_progress = EventEmitter.progress(
            "sql_validation", "Validating SQL..."
        )
        validation_progress["data"]["ts"] = datetime.utcnow().isoformat()
        yield validation_progress
        validation_attempt = 1
        ok, issues, validate_elapsed = _validate_sql(sql)
        while True:
            validation_event = EventEmitter.result(
                "sql_validated",
                {
                    "ok": ok,
                    "issues_count": len(issues),
                    "attempt": validation_attempt,
                    "issues": issues,
                },
            )
            validation_event["event"] = "sql_validated"
            validation_event["data"].update(
                {
                    "ts": datetime.utcnow().isoformat(),
                    "elapsed_ms": validate_elapsed,
                }
            )
            yield validation_event
            if ok:
                break
            logger.error(
                "[SQL_VALIDATION] Validation failed (attempt %s): %s",
                validation_attempt,
                issues,
                extra={
                    "error_code": "SQL_VALIDATION_FAILED",
                    "flow": self.flow_label,
                    "session_id": session_id,
                    "intent_key": intent.intent_key,
                },
            )
            if template and not fallback_used:
                fallback_used = True
                fallback_reason = "sql_validation_failed"
                llm_used = False
                sql_attempt += 1
                logger.info(
                    "[SQL_VALIDATION] Triggering template fallback",
                    extra={
                        "flow": self.flow_label,
                        "session_id": session_id,
                        "intent_key": intent.intent_key,
                        "attempt": validation_attempt,
                    },
                )
                fallback_notice = EventEmitter.progress(
                    "sql_compilation",
                    "Validation failed; regenerating SQL from template",
                )
                fallback_notice["data"].update(
                    {
                        "ts": datetime.utcnow().isoformat(),
                        "code": "SQL_VALIDATION_FAILED",
                        "attempt": validation_attempt,
                    }
                )
                yield fallback_notice
                fallback_start = time.time()
                try:
                    sql = compile_sql_from_plan(provisional_plan, intent, CONFIGS.__dict__, template)
                except ValueError as ve:
                    error_event = EventEmitter.error(
                        "sql_compilation",
                        str(ve),
                        code="SQL_COMPILATION_ERROR",
                        details={"template": selected_template_id},
                    )
                    error_event["data"]["ts"] = datetime.utcnow().isoformat()
                    yield error_event
                    return
                generation_elapsed = int((time.time() - fallback_start) * 1000)
                for event in _emit_sql_events(
                    sql,
                    generation_elapsed,
                    attempt=sql_attempt,
                    llm_flag=llm_used,
                    fallback_flag=True,
                    reason=fallback_reason,
                ):
                    yield event
                validation_attempt += 1
                validation_progress = EventEmitter.progress(
                    "sql_validation",
                    "Validating fallback SQL...",
                )
                validation_progress["data"]["ts"] = datetime.utcnow().isoformat()
                yield validation_progress
                ok, issues, validate_elapsed = _validate_sql(sql)
                continue
            error_event = EventEmitter.error(
                "sql_validation",
                "; ".join(issues) if issues else "SQL validation failed",
                details={"issues": issues, "attempt": validation_attempt},
                code="SQL_VALIDATION_FAILED",
            )
            error_event["data"]["ts"] = datetime.utcnow().isoformat()
            yield error_event
            return
        for event in _emit_sql_events(
            sql,
            generation_elapsed,
            attempt=sql_attempt,
            llm_flag=llm_used,
            fallback_flag=fallback_used,
            reason=fallback_reason,
        ):
            yield event
        # 9) SQL Execution Phase
        execution_progress = EventEmitter.progress(
            "sql_execution", "Executing query..."
        )
        execution_progress["data"]["ts"] = datetime.utcnow().isoformat()
        yield execution_progress
        execution_attempt = 1
        while True:
            exec_start = time.time()
            try:
                data = await execute_sql(sql)
                exec_elapsed = int((time.time() - exec_start) * 1000)
                break
            except Exception as exec_exc:
                logger.error(
                    "[SQL_EXECUTION] Execution failed (attempt %s): %s",
                    execution_attempt,
                    exec_exc,
                    extra={
                        "error_code": "SQL_EXECUTION_ERROR",
                        "flow": self.flow_label,
                        "session_id": session_id,
                        "intent_key": intent.intent_key,
                    },
                )
                if template and llm_used and not fallback_used:
                    fallback_used = True
                    fallback_reason = "sql_execution_error"
                    llm_used = False
                    sql_attempt += 1
                    logger.info(
                        "[SQL_EXECUTION] Triggering template fallback",
                        extra={
                            "flow": self.flow_label,
                            "session_id": session_id,
                            "intent_key": intent.intent_key,
                            "attempt": execution_attempt,
                        },
                    )
                    fallback_notice = EventEmitter.progress(
                        "sql_execution",
                        "Execution error; regenerating SQL from template",
                    )
                    fallback_notice["data"].update(
                        {
                            "ts": datetime.utcnow().isoformat(),
                            "code": "SQL_EXECUTION_ERROR",
                            "attempt": execution_attempt,
                        }
                    )
                    yield fallback_notice
                    fallback_start = time.time()
                    try:
                        sql = compile_sql_from_plan(provisional_plan, intent, CONFIGS.__dict__, template)
                    except ValueError as ve:
                        error_event = EventEmitter.error(
                            "sql_compilation",
                            str(ve),
                            code="SQL_COMPILATION_ERROR",
                        )
                        error_event["data"]["ts"] = datetime.utcnow().isoformat()
                        yield error_event
                        return
                    generation_elapsed = int((time.time() - fallback_start) * 1000)
                    for event in _emit_sql_events(
                        sql,
                        generation_elapsed,
                        attempt=sql_attempt,
                        llm_flag=llm_used,
                        fallback_flag=True,
                        reason=fallback_reason,
                    ):
                        yield event
                    validation_progress = EventEmitter.progress(
                        "sql_validation",
                        "Validating fallback SQL...",
                    )
                    validation_progress["data"]["ts"] = datetime.utcnow().isoformat()
                    yield validation_progress
                    validation_attempt += 1
                    ok, issues, validate_elapsed = _validate_sql(sql)
                    validation_event = EventEmitter.result(
                        "sql_validated",
                        {
                            "ok": ok,
                            "issues_count": len(issues),
                            "attempt": validation_attempt,
                            "issues": issues,
                        },
                    )
                    validation_event["event"] = "sql_validated"
                    validation_event["data"].update(
                        {
                            "ts": datetime.utcnow().isoformat(),
                            "elapsed_ms": validate_elapsed,
                        }
                    )
                    yield validation_event
                    if not ok:
                        error_event = EventEmitter.error(
                            "sql_validation",
                            "; ".join(issues) if issues else "SQL validation failed",
                            details={"issues": issues, "attempt": validation_attempt},
                            code="SQL_VALIDATION_FAILED",
                        )
                        error_event["data"]["ts"] = datetime.utcnow().isoformat()
                        yield error_event
                        return
                    execution_attempt += 1
                    continue
                error_event = EventEmitter.error(
                    "sql_execution",
                    str(exec_exc),
                    details={"exception": str(exec_exc)},
                    code="SQL_EXECUTION_ERROR",
                )
                error_event["data"]["ts"] = datetime.utcnow().isoformat()
                yield error_event
                return
        try:
            SQLResultModel(query=sql, data=data)
        except ValidationError as ve:
            error_event = EventEmitter.error(
                "sql_execution",
                str(ve),
                code="SQL_EXECUTION_ERROR",
            )
            error_event["data"]["ts"] = datetime.utcnow().isoformat()
            yield error_event
            return
        execution_stats = EventEmitter.result(
            "execution_stats",
            {
                "row_count": len(data),
                "columns_count": len(data[0].keys()) if data else 0,
            },
        )
        execution_stats["event"] = "execution_stats"
        execution_stats["data"].update(
            {
                "ts": datetime.utcnow().isoformat(),
                "elapsed_ms": exec_elapsed,
            }
        )
        yield execution_stats
        data_retrieved = EventEmitter.result(
            "data_retrieved", {"row_count": len(data)}
        )
        data_retrieved["event"] = "data_retrieved"
        data_retrieved["data"]["ts"] = datetime.utcnow().isoformat()
        yield data_retrieved
        # 10) Chart Planning Phase
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
        chart_design = _generate_chart_design(intent.intent_key, plan, data, spec)
        spec.setdefault("meta", {}).setdefault("chartDesign", chart_design)
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
        analysis_complete = EventEmitter.result(
            "analysis_complete",
            {
                "analysis_length": len(full_analysis),
                "analysis": full_analysis,
            },
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
        # Cleanup expired sessions
        from analytics.core.clarify import get_session_store
        session_store = await get_session_store()
        await session_store.cleanup_expired()
        total_elapsed = int((time.time() - workflow_start) * 1000)
        workflow_complete = EventEmitter.result(
            "workflow_complete", {"total_elapsed_ms": total_elapsed}
        )
        workflow_complete["event"] = "workflow_complete"
        workflow_complete["data"]["ts"] = datetime.utcnow().isoformat()
        yield workflow_complete
# Standalone wrapper function for main.py
async def run_planner_executor(query: str, session_id: Optional[str] = None) -> AsyncGenerator[Dict[str, Any], None]:
    """Helper to stream planner-executor events without referencing the registry."""
    workflow_instance = PlannerExecutorFlow()
    async for event in workflow_instance.events(query, session_id):
        yield event

