from __future__ import annotations
from typing import AsyncGenerator, Dict, Any, Optional, List
import time
import uuid
import asyncio
from datetime import datetime
from .types import WorkflowState, SQLResultModel, ChartSpecModel, ValidationError, IntentModel, QueryPlanModel, ClarifyAnswerModel, ClarifyRequestModel
from .config import CONFIGS
from analytics_shared.streaming.events import EventEmitter, TimedEventEmitter
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
        now = datetime.utcnow().isoformat()
        
        # Generate session ID if not provided
        if not session_id:
            session_id = str(uuid.uuid4())
        
        
        # Emit session ID for frontend tracking (lightweight)
        yield EventEmitter.session_started(session_id)
        
        # 1) Enhanced Intent Detection Phase with Early Clarification
        yield EventEmitter.progress("intent_detection", "Detecting intent...")
        
        intent_start = time.time()
        intent: IntentModel = await asyncio.to_thread(detect_intent_with_clarifications, query, CONFIGS.__dict__, session_id=session_id)
        # Store original query for clarification engine
        intent.slots_detected['original_query'] = query
        intent_elapsed = int((time.time() - intent_start) * 1000)

        # 2) Provisional Plan Generation (lightweight)
        provisional_plan: QueryPlanModel = QueryPlanModel(**plan_sql_rule_based(intent, CONFIGS.__dict__))
        
        # 3) Provisional Template Selection
        template = choose_template(intent, provisional_plan, CONFIGS.__dict__)
        
        # 4) Early Clarification Computation
        clarify_start = time.time()
        official_clarifications = compute_required_clarifications(intent, provisional_plan, template, CONFIGS.__dict__)
        
        # Track answered slots throughout the session to prevent duplicates
        all_answered_slots = set()

        # Decision point: emit intent_draft or intent_decided
        clarifications_needed = len(official_clarifications) > 0
        confidence_sufficient = (intent.confidence or 0.0) >= 0.8
        
        if clarifications_needed or not confidence_sufficient:
            # Emit intent_draft - clarifications are needed (lightweight)
            yield EventEmitter.intent_draft(
                confidence=intent.confidence,
                clarifications_needed=True,
                clarifications_count=len(official_clarifications)
            )
        else:
            # Emit intent_decided - high confidence, no clarifications needed (lightweight)
            yield EventEmitter.intent_decided(
                key=intent.intent_key,
                confidence=intent.confidence,
                clarifications_needed=False
            )

        # 5) Clarification Phase (if needed)
        if official_clarifications:
            yield EventEmitter.progress("clarification", "Clarifying requirements...")
            assumptions: list[str] = []
            rounds = 0

            while official_clarifications and rounds < 3:
                # Process one clarification at a time
                slot_request = official_clarifications[0]  # Take the first (most important) clarification
                
                
                # Send single clarification request
                yield EventEmitter.clarification_request(session_id, {
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
                    "round": rounds + 1
                })
                
                # Wait for single answer with timeout
                try:
                    answer = await asyncio.wait_for(
                        wait_for_answer_blocking(session_id, slot_request.request_id),
                        timeout=60.0  # 60 second timeout
                    )
                except asyncio.TimeoutError:
                    # Emit timeout event
                    yield EventEmitter.progress("clarification_timeout", f"Timeout waiting for {slot_request.slot} clarification. Using default value.")
                    # Use default value if available, otherwise skip this clarification
                    if slot_request.default:
                        from .types import ClarifyAnswerModel
                        answer = ClarifyAnswerModel(
                            session_id=session_id,
                            request_id=slot_request.request_id,
                            slot=slot_request.slot,
                            value=slot_request.default,
                            ts=datetime.utcnow().isoformat()
                        )
                    else:
                        # Skip this clarification
                        official_clarifications.pop(0)
                        continue
                
                if answer:
                    # Validate answer using the new validation function (bool)
                    is_valid = validate_clarification_answer(answer, slot_request)
                    if is_valid:
                        
                        # Emit acknowledgment for the received answer
                        yield EventEmitter.result("clarification_ack", {
                            "slot": slot_request.slot,
                            "answer": answer.value
                        })
                        
                        # Merge single answer back into intent and plan
                        intent, provisional_plan, merge_assumptions = await merge_answers(intent, provisional_plan, [answer], CONFIGS.__dict__)
                        assumptions.extend(merge_assumptions)
                        
                        # Re-select template after this answer
                        template = choose_template(intent, provisional_plan, CONFIGS.__dict__)

                        # Re-compute clarifications after intent/plan changes
                        new_clarifications = compute_required_clarifications(intent, provisional_plan, template, CONFIGS.__dict__)
                        
                        # Remove the answered clarification from original list
                        remaining_original = official_clarifications[1:]
                        
                        # Track this answer in session history
                        all_answered_slots.add(answer.slot)
                        
                        # Combine new clarifications with remaining original ones (avoid duplicates)
                        combined_requests = []
                        
                        # Add new clarifications first (higher priority), skip already answered in session
                        for new_req in new_clarifications:
                            if new_req.slot not in all_answered_slots:
                                combined_requests.append(new_req)
                        
                        # Add remaining original clarifications (skip answered and duplicates)
                        for orig_req in remaining_original:
                            if (orig_req.slot not in all_answered_slots and 
                                not any(c.slot == orig_req.slot for c in combined_requests)):
                                combined_requests.append(orig_req)
                        
                        official_clarifications = combined_requests
                        rounds += 1
                        
                    else:
                        # Invalid answer, emit detailed error message
                        error_message = get_validation_error_message(answer, slot_request)
                        yield EventEmitter.progress("clarification_error", error_message or f"Invalid value for {slot_request.slot}: {answer.value}")
                        # Remove this clarification from the list and continue
                        official_clarifications = official_clarifications[1:]
                else:
                    # No answer received, skip this clarification
                    official_clarifications = official_clarifications[1:]

            # Emit intent_resolved after clarifications complete
            yield EventEmitter.intent_resolved(
                key=intent.intent_key,
                confidence=intent.confidence,
                rounds=rounds
            )

        # Now use the finalized intent and provisional plan as the real plan
        plan = provisional_plan
        
        # 6) Emit Final Plan and Template Events
        current_time = time.time()
        elapsed_ms = int((current_time - workflow_start) * 1000)
        
        yield EventEmitter.result("plan_built", {
            "granularity": plan.granularity,
            "comparison": plan.comparison,
            "metrics_count": len(plan.metrics)
        })

        # Get template metadata from queries config
        template_info = None
        if template and intent.intent_key:
            queries_config = CONFIGS.__dict__.get('queries', {})
            patterns = queries_config.get('query_patterns', {})
            if intent.intent_key in patterns:
                pattern = patterns[intent.intent_key]
                template_info = {
                    "id": intent.intent_key,
                    "name": pattern.get('name', intent.intent_key),
                    "description": pattern.get('description', 'No description available')
                }
        
        yield EventEmitter.result("template_selected", {
            "template_id": intent.intent_key if template else None,
            "has_template": template is not None
        })

        # 7) SQL Compilation Phase
        yield EventEmitter.progress("sql_compilation", "Compiling SQL...")
        
        compile_start = time.time()
        try:
            sql = compile_sql_from_plan(plan, intent, CONFIGS.__dict__, template)
        except ValueError as ve:
            # Handle company requirement validation errors by requesting clarification
            error_msg = str(ve)
            if "This query requires specifying a company" in error_msg:
                # Create company clarification request (schema-friendly)
                companies_list = CONFIGS.companies.get('companies', {}).get('semiconductor', [])
                # Build display options like "NVDA (Nvidia)"
                display_options: list[str] = []
                for comp in companies_list[:7]:
                    try:
                        t = comp.get('ticker')
                        n = comp.get('short_name', comp.get('name', t))
                        if t:
                            display_options.append(f"{t} ({n})")
                    except Exception:
                        continue

                # Fallback options if config missing
                if not display_options:
                    display_options = ['NVDA (Nvidia)', 'AMD (AMD)', 'INTC (Intel)', 'MU (Micron)']

                clarification_request = ClarifyRequestModel(
                    request_id=f"company_req_{int(time.time() * 1000)}",
                    slot="company",
                    question="Which company would you like to analyze?",
                    type="single",
                    options=display_options,
                    default=display_options[0],
                    required=True,
                    reason="Market share analysis requires specifying a company"
                )

                # Emit clarification request
                yield EventEmitter.clarification_request(session_id, {
                    "request_id": clarification_request.request_id,
                    "slot": clarification_request.slot,
                    "question": clarification_request.question,
                    "type": clarification_request.type,
                    "options": clarification_request.options,
                    "required": clarification_request.required,
                    "reason": clarification_request.reason
                })

                # Wait for clarification response
                try:
                    answer = await asyncio.wait_for(
                        wait_for_answer_blocking(session_id, clarification_request.request_id),
                        timeout=60.0
                    )

                    if answer and answer.value:
                        # Emit acknowledgment
                        yield EventEmitter.result("clarification_ack", {
                            "slot": clarification_request.slot,
                            "answer": answer.value
                        })

                        # Update intent with selected company
                        intent.slots_detected["company"] = answer.value

                        # Retry SQL compilation with selected company
                        try:
                            sql = compile_sql_from_plan(plan, intent, CONFIGS.__dict__, template)
                        except ValueError as retry_ve:
                            yield EventEmitter.errors([str(retry_ve)])
                            return
                    else:
                        yield EventEmitter.errors(["No company selected"])
                        return

                except asyncio.TimeoutError:
                    yield EventEmitter.progress("clarification_timeout", "Timeout waiting for company selection")
                    return
            else:
                # Non-company related ValueError, emit as error
                yield EventEmitter.errors([str(ve)])
                return
        compile_elapsed = int((time.time() - compile_start) * 1000)
        
        yield EventEmitter.result("sql_compiled", {
            "sql_length": len(sql),
            "template_used": template is not None
        })

        # 8) SQL Validation Phase
        yield EventEmitter.progress("sql_validation", "Validating SQL...")
        
        validate_start = time.time()
        ok, issues = validate_sql(sql, allowed_tables=["comp_financials"], max_limit=CONFIGS.database.get('query_defaults', {}).get('max_limit', 10000), granularity=plan.granularity)
        validate_elapsed = int((time.time() - validate_start) * 1000)
        
        yield EventEmitter.result("sql_validated", {
            "ok": ok,
            "issues_count": len(issues) if issues else 0
        })
        
        if not ok:
            yield EventEmitter.errors(issues)
            return

        yield EventEmitter.sql_generated(sql)

        # 9) SQL Execution Phase
        yield EventEmitter.progress("sql_execution", "Executing query...")
        
        exec_start = time.time()
        try:
            data = await execute(sql)
        except Exception as e:
            # Emit a clear error event on DB failures/timeouts
            yield EventEmitter.errors([str(e)], step="sql_execution")
            return
        exec_elapsed = int((time.time() - exec_start) * 1000)
        
        try:
            SQLResultModel(query=sql, data=data)
        except ValidationError as ve:
            yield EventEmitter.errors([str(ve)])
            return
        
        # Emit execution statistics
        yield EventEmitter.result("execution_stats", {
            "row_count": len(data),
            "columns_count": len(data[0].keys()) if data else 0
        })
        
        yield EventEmitter.result("data_retrieved", {"row_count": len(data)})

        # 10) Chart Planning Phase
        yield EventEmitter.progress("chart_generation", "Planning chart...")
        
        chart_start = time.time()
        chart_plan = plan_chart_rule_based(data, query, intent.intent_key)
        # Pass intent and comparison to the chart builder for intent-specific layouts
        spec = build_chart_spec(
            data,
            chart_plan.dict(),
            CONFIGS.charts,
            intent_key=intent.intent_key,
            comparison=plan.comparison,
        )
        
        # Generate smart chart design metadata
        chart_design = _generate_chart_design(intent.intent_key, plan, data, spec)
        spec['meta']['chartDesign'] = chart_design
        
        chart_elapsed = int((time.time() - chart_start) * 1000)
        
        yield EventEmitter.result("chart_planned", {
            "chart_type": chart_plan.chart_type,
            "series_count": len(chart_plan.series)
        })
        
        try:
            ChartSpecModel(**spec)
            yield EventEmitter.result("chart_generated", {"chart_type": spec.get('meta', {}).get('chartDesign', {}).get('chart_type', 'unknown')}, key="chart_spec")
        except ValidationError as ve:
            # Send warning but continue with raw spec - frontend can handle it
            yield EventEmitter.progress("warning", f"Chart spec validation warning: {str(ve)}")
            yield EventEmitter.result("chart_generated", {"chart_type": spec.get('meta', {}).get('chartDesign', {}).get('chart_type', 'unknown')}, key="chart_spec")

        # 11) Analysis Generation Phase
        yield EventEmitter.progress("analysis_generation", "Generating insights...")
        
        analysis_start = time.time()
        full_analysis = ""
        async for text in stream_insights_llm(data, sql, query, session_id=session_id):
            if text:
                full_analysis += text
                yield EventEmitter.result("analysis_streaming", {"chunk_length": len(text)}, key="partial_analysis")
        
        analysis_elapsed = int((time.time() - analysis_start) * 1000)
        
        # Emit complete buffered analysis
        yield EventEmitter.result("analysis_complete", {"analysis_length": len(full_analysis)}, key="analysis")
        
        # Cleanup expired sessions
        from .clarify import get_session_store
        session_store = await get_session_store()
        await session_store.cleanup_expired()
        
        # Final workflow completion with total timing
        total_elapsed = int((time.time() - workflow_start) * 1000)
        yield EventEmitter.result("workflow_complete", {
            "total_elapsed_ms": total_elapsed
        })


# Standalone wrapper function for main.py
async def analytics_memory_workflow(query: str, session_id: str = None, session_store=None):
    """Wrapper function that instantiates and runs the AnalyticsMemoryWorkflow"""
    workflow_instance = AnalyticsMemoryWorkflow()
    async for event in workflow_instance.events(query, session_id):
        yield event
