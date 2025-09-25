from __future__ import annotations
from typing import AsyncGenerator, Dict, Any, Optional, List
import time
import uuid
import asyncio
from datetime import datetime
from .types import WorkflowState, SQLResultModel, ChartSpecModel, ValidationError, IntentModel, QueryPlanModel, ClarifyAnswerModel, ClarifyRequestModel
from .config import CONFIGS
from analytics_shared.streaming.events import EventEmitter, TimedEventEmitter
from analytics_shared.intent import intent_to_sql_criteria
from .intent import detect_intent, detect_intent_llm, detect_intent_with_clarifications
from .sql_planner import compile_sql_from_plan, plan_sql_rule_based, choose_template
from .db import execute
from .charting import build_chart_spec, plan_chart_rule_based
from .analysis import summarize, stream_insights_llm
from .sql_validate import validate_sql
from .clarify import detect_missing_slots, merge_answers, wait_for_answer_blocking, compute_required_clarifications, validate_clarification_answer, get_validation_error_message


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



class AnalyticsMemoryWorkflow:
    """Phase 2 workflow that emits SSE-friendly events for the memory pipeline."""

    def _looks_financial(self, query: str) -> bool:
        q = (query or "").lower()
        keywords = ("market share", "margin", "profit", "earnings", "revenue", "growth", "cash flow", "guidance", "quarter", "qoq", "yoy", "opex", "capex", "gross", "net income")
        return any(keyword in q for keyword in keywords)


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
        workflow_start = time.time()
        timed_emitter = TimedEventEmitter()

        # Ensure session context exists
        if not session_id:
            session_id = str(uuid.uuid4())

        # Emit session start for frontend tracking
        yield EventEmitter.session_started(session_id)

        # 0) Lightweight classification phase before intent detection
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

        looks_financial = self._looks_financial(query)
        reasoning_message = ("Detected financial analytics keywords" if looks_financial else "No financial analytics keywords detected")
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


# 1) Intent Detection Phase with structured events
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
            query,
            CONFIGS.__dict__,
            session_id=session_id,
        )
        intent.slots_detected["original_query"] = query
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

        # 2) Provisional Plan Generation (lightweight)
        provisional_plan: QueryPlanModel = QueryPlanModel(
            **plan_sql_rule_based(intent, CONFIGS.__dict__)
        )

        # 3) Provisional Template Selection
        template = choose_template(intent, provisional_plan, CONFIGS.__dict__)

        # 4) Clarification computation (deduplicated)
        official_clarifications = compute_required_clarifications(
            intent, provisional_plan, template, CONFIGS.__dict__
        )
        deduped_requests: list[ClarifyRequestModel] = []
        seen_slots: set[str] = set()
        for request in official_clarifications:
            if request.slot in seen_slots:
                continue
            seen_slots.add(request.slot)
            deduped_requests.append(request)
        official_clarifications = deduped_requests

        all_answered_slots: set[str] = set()
        assumptions: list[str] = []
        rounds = 0

        clarifications_needed = bool(official_clarifications)
        confidence_sufficient = (intent.confidence or 0.0) >= 0.8

        intent_status_event = (
            EventEmitter.intent_draft(
                confidence=intent.confidence,
                clarifications_needed=True,
                clarifications_count=len(official_clarifications),
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

        # 5) Clarification Phase (if needed)
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
                        from .types import ClarifyAnswerModel

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

                        combined_requests: list[ClarifyRequestModel] = []
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

        plan = provisional_plan

        intent_finalized_event = {
            "event": "intent_finalized",
            "data": {
                "intent_key": intent.intent_key,
                "confidence": intent.confidence,
                "assumptions": assumptions,
                "ts": datetime.utcnow().isoformat(),
            },
        }
        if rounds:
            intent_finalized_event["data"]["clarification_rounds"] = rounds
        yield intent_finalized_event

        criteria_model = intent_to_sql_criteria(intent, CONFIGS.__dict__)
        criteria_payload = criteria_model.dict()
        criteria_payload["ts"] = datetime.utcnow().isoformat()
        yield {
            "event": "criteria_ready",
            "data": criteria_payload,
        }

        # 6) Emit Final Plan and Template Events
        elapsed_ms = int((time.time() - workflow_start) * 1000)
        plan_event = EventEmitter.result(
            "plan_built",
            {
                "granularity": plan.granularity,
                "comparison": plan.comparison,
                "metrics_count": len(plan.metrics),
            },
        )
        plan_event["event"] = "plan_built"
        plan_event["data"].update(
            {
                "ts": datetime.utcnow().isoformat(),
                "elapsed_ms": elapsed_ms,
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

        # 7) SQL Compilation Phase
        sql_progress = EventEmitter.progress("sql_compilation", "Compiling SQL...")
        sql_progress["data"]["ts"] = datetime.utcnow().isoformat()
        yield sql_progress

        compile_start = time.time()
        try:
            sql = compile_sql_from_plan(plan, intent, CONFIGS.__dict__, template)
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
                            plan, intent, CONFIGS.__dict__, template
                        )
                    else:
                        yield EventEmitter.error("clarification", "No company selected")
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
                yield EventEmitter.error("sql_compilation", str(ve))
                return

        compile_elapsed = int((time.time() - compile_start) * 1000)
        sql_compiled_event = EventEmitter.result(
            "sql_compiled",
            {
                "sql_length": len(sql),
                "template_used": template is not None,
            },
        )
        sql_compiled_event["event"] = "sql_compiled"
        sql_compiled_event["data"].update(
            {
                "ts": datetime.utcnow().isoformat(),
                "elapsed_ms": compile_elapsed,
            }
        )
        yield sql_compiled_event

        sql_generated_event = EventEmitter.sql_generated(sql)
        sql_generated_event["data"].update(
            {
                "ts": datetime.utcnow().isoformat(),
                "elapsed_ms": compile_elapsed,
            }
        )
        yield sql_generated_event

        # 8) SQL Validation Phase
        validation_progress = EventEmitter.progress(
            "sql_validation", "Validating SQL..."
        )
        validation_progress["data"]["ts"] = datetime.utcnow().isoformat()
        yield validation_progress

        validate_start = time.time()
        ok, issues = validate_sql(
            sql,
            allowed_tables=["comp_financials"],
            max_limit=CONFIGS.database.get("query_defaults", {}).get(
                "max_limit", 10000
            ),
            granularity=plan.granularity,
        )
        validate_elapsed = int((time.time() - validate_start) * 1000)
        validation_event = EventEmitter.result(
            "sql_validated",
            {
                "ok": ok,
                "issues_count": len(issues) if issues else 0,
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
            yield EventEmitter.error("sql_validation", "; ".join(issues))
            return


        # 9) SQL Execution Phase
        execution_progress = EventEmitter.progress(
            "sql_execution", "Executing query..."
        )
        execution_progress["data"]["ts"] = datetime.utcnow().isoformat()
        yield execution_progress

        exec_start = time.time()
        try:
            data = await execute(sql)
        except Exception as exec_exc:
            error_event = EventEmitter.error("sql_execution", str(exec_exc))
            error_event["data"]["ts"] = datetime.utcnow().isoformat()
            yield error_event
            return
        exec_elapsed = int((time.time() - exec_start) * 1000)

        try:
            SQLResultModel(query=sql, data=data)
        except ValidationError as ve:
            yield EventEmitter.error("sql_execution", str(ve))
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
        from .clarify import get_session_store

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
async def analytics_memory_workflow(query: str, session_id: str = None, session_store=None):
    """Wrapper function that instantiates and runs the AnalyticsMemoryWorkflow"""
    workflow_instance = AnalyticsMemoryWorkflow()
    async for event in workflow_instance.events(query, session_id):
        yield event

