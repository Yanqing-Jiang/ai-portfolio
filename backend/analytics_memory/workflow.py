from __future__ import annotations
from typing import AsyncGenerator, Dict, Any, Optional, List
import time
import uuid
from datetime import datetime
from langgraph.graph import StateGraph, END
from .types import WorkflowState, SQLResultModel, ChartSpecModel, ValidationError, IntentModel, QueryPlanModel, ClarifyAnswerModel, ClarifyRequestModel
from .config import CONFIGS
from .intent import detect_intent, detect_intent_llm, detect_intent_with_clarifications
from .sql_planner import compile_sql_from_plan, plan_sql_rule_based, choose_template
from .db import execute
from .charting import build_chart_spec, plan_chart_rule_based
from .analysis import summarize, stream_insights_llm
from .sql_validate import validate_sql
from .clarify import detect_missing_slots, merge_answers, wait_for_answer_blocking, compute_required_clarifications, validate_clarification_answer


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
                      else ['gross_margin_change_pp', 'operating_margin_change_pp', 'net_margin_change_pp'],
            'y_axis': {'type': 'percent_only'},
            'defaultLegendSelection': {
                'operating_margin': True,
                'net_margin': True
            } if 'margins_vs_peers' in intent_key else {
                'operating_margin_change_pp': True,
                'net_margin_change_pp': True
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
        
        # Emit session ID for frontend tracking
        yield {
            "event": "session_started",
            "data": {
                "session_id": session_id,
                "ts": now
            }
        }
        
        # 1) Enhanced Intent Detection Phase with Early Clarification
        yield {"event": "status", "data": {"step": "intent_detection", "message": "Detecting intent...", "ts": now}}
        
        intent_start = time.time()
        intent: IntentModel = detect_intent_with_clarifications(query, CONFIGS.__dict__)
        # Store original query for clarification engine
        intent.slots_detected['original_query'] = query
        intent_elapsed = int((time.time() - intent_start) * 1000)

        # 2) Provisional Plan Generation (lightweight)
        provisional_plan: QueryPlanModel = plan_sql_rule_based(intent, CONFIGS.__dict__)
        
        # 3) Provisional Template Selection
        template = choose_template(intent, provisional_plan, CONFIGS.__dict__)
        
        # 4) Early Clarification Computation
        clarify_start = time.time()
        official_clarifications = compute_required_clarifications(intent, provisional_plan, template, CONFIGS.__dict__)

        # Decision point: emit intent_draft or intent_decided
        clarifications_needed = len(official_clarifications) > 0
        confidence_sufficient = (intent.confidence or 0.0) >= 0.8
        
        if clarifications_needed or not confidence_sufficient:
            # Emit intent_draft - clarifications are needed
            yield {
                "event": "intent_draft",
                "data": {
                    "step": "intent_detection",
                    "ts": datetime.utcnow().isoformat(),
                    "elapsed_ms": intent_elapsed,
                    "intent": {
                        "key": intent.intent_key,
                        "confidence": intent.confidence,
                        "slots_detected": intent.slots_detected,
                        "assumptions": intent.assumptions,
                        "clarifications_suggested": intent.clarifications_suggested,
                        "possible_intents": intent.possible_intents,
                        "intent_reasoning": intent.intent_reasoning,
                    },
                    "model": "gpt-4o-mini-2024-07-18",
                    "company": self._get_company_display(intent, provisional_plan),
                    "granularity": intent.slots_detected.get('granularity', 'annual'),
                    "years_back": intent.slots_detected.get('timeframe', {}).get('years_back', 4),
                    "clarifications_count": len(official_clarifications),
                },
            }
        else:
            # Emit intent_decided - high confidence, no clarifications needed
            yield {
                "event": "intent_decided", 
                "data": {
                    "step": "intent_detection",
                    "ts": datetime.utcnow().isoformat(),
                    "elapsed_ms": intent_elapsed,
                    "intent": {
                        "key": intent.intent_key,
                        "confidence": intent.confidence,
                        "slots_detected": intent.slots_detected,
                        "assumptions": intent.assumptions,
                    },
                    "model": "gpt-4o-mini-2024-07-18",
                    "company": self._get_company_display(intent, provisional_plan),
                    "granularity": intent.slots_detected.get('granularity', 'annual'),
                    "years_back": intent.slots_detected.get('timeframe', {}).get('years_back', 4),
                },
            }

        # 5) Clarification Phase (if needed)
        if official_clarifications:
            yield {"event": "status", "data": {"step": "clarification", "message": "Clarifying requirements...", "ts": datetime.utcnow().isoformat()}}
            assumptions: list[str] = []
            rounds = 0

            while official_clarifications and rounds < 3:
                answers: list[ClarifyAnswerModel] = []
                
                for slot_request in official_clarifications:
                    # Emit clarification request
                    yield {
                        "event": "clarification_request", 
                        "data": {
                            "session_id": session_id,
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
                            "ts": datetime.utcnow().isoformat()
                        }
                    }
                    
                    # Wait for answer
                    answer = await wait_for_answer_blocking(session_id, slot_request.request_id)
                    
                    if answer:
                        # Validate answer using the new validation function (bool)
                        is_valid = validate_clarification_answer(answer, slot_request)
                        if is_valid:
                            answers.append(answer)
                            yield {
                                "event": "clarification_ack",
                                "data": {
                                    "session_id": session_id,
                                    "request_id": slot_request.request_id,
                                    "slot": slot_request.slot,
                                    "accepted": True,
                                    "value": answer.value,
                                    "ts": datetime.utcnow().isoformat()
                                }
                            }
                        else:
                            # Invalid answer, emit error and continue
                            yield {
                                "event": "clarification_error",
                                "data": {
                                    "request_id": slot_request.request_id,
                                    "slot": slot_request.slot,
                                    "message": f"Invalid value for {slot_request.slot}: {answer.value}",
                                    "ts": datetime.utcnow().isoformat()
                                }
                            }

                # Merge answers back into intent and plan
                if answers:
                    intent, provisional_plan, merge_assumptions = await merge_answers(intent, provisional_plan, answers, CONFIGS.__dict__)
                    assumptions.extend(merge_assumptions)
                
                # Emit clarification complete for this round
                clarify_elapsed = int((time.time() - clarify_start) * 1000)
                yield {
                    "event": "clarification_complete",
                    "data": {
                        "step": "clarification",
                        "ts": datetime.utcnow().isoformat(),
                        "elapsed_ms": clarify_elapsed,
                        "assumptions": assumptions,
                        "clarifications_count": len(answers)
                    }
                }

                # Re-select template after each round
                template = choose_template(intent, provisional_plan, CONFIGS.__dict__)

                # Recompute missing slots for the next round
                official_clarifications = compute_required_clarifications(intent, provisional_plan, template, CONFIGS.__dict__)
                rounds += 1

            # Emit intent_resolved after clarifications complete
            yield {
                "event": "intent_resolved",
                "data": {
                    "step": "clarification",
                    "ts": datetime.utcnow().isoformat(),
                    "elapsed_ms": int((time.time() - clarify_start) * 1000),
                    "intent": {
                        "key": intent.intent_key,
                        "confidence": intent.confidence,
                        "slots_detected": intent.slots_detected,
                        "assumptions": intent.assumptions,
                    },
                    "final_assumptions": assumptions,
                    "rounds": rounds
                },
            }

        # Now use the finalized intent and provisional plan as the real plan
        plan = provisional_plan
        
        # 6) Emit Final Plan and Template Events
        yield {
            "event": "plan_built",
            "data": {
                "step": "plan_generation", 
                "ts": datetime.utcnow().isoformat(),
                "elapsed_ms": 0,  # Already computed during provisional phase
                "plan": {
                    "metrics": plan.metrics,
                    "derived_metrics": plan.derived_metrics,
                    "comparison": plan.comparison,
                    "granularity": plan.granularity,
                    "timeframe": plan.timeframe.dict(),
                    "limit": plan.limit
                }
            }
        }

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
        
        yield {
            "event": "template_selected",
            "data": {
                "step": "template_selection",
                "ts": datetime.utcnow().isoformat(), 
                "elapsed_ms": 0,  # Already computed during provisional phase
                "template": template_info,
                "has_template": template is not None
            }
        }

        # 7) SQL Compilation Phase
        yield {"event": "status", "data": {"step": "sql_compilation", "message": "Compiling SQL...", "ts": datetime.utcnow().isoformat()}}
        
        compile_start = time.time()
        try:
            sql = compile_sql_from_plan(plan, intent, CONFIGS.__dict__, template)
        except ValueError as ve:
            # Handle company requirement validation errors
            yield {"event": "errors", "data": {"errors": [str(ve)]}}
            return
        compile_elapsed = int((time.time() - compile_start) * 1000)
        
        yield {
            "event": "sql_compiled",
            "data": {
                "step": "sql_compilation",
                "ts": datetime.utcnow().isoformat(),
                "elapsed_ms": compile_elapsed,
                "sql_length": len(sql),
                "template_used": template is not None
            }
        }

        # 8) SQL Validation Phase
        yield {"event": "status", "data": {"step": "sql_validation", "message": "Validating SQL...", "ts": datetime.utcnow().isoformat()}}
        
        validate_start = time.time()
        ok, issues = validate_sql(sql, allowed_tables=["comp_financials"], max_limit=CONFIGS.database.get('query_defaults', {}).get('max_limit', 10000), granularity=plan.granularity)
        validate_elapsed = int((time.time() - validate_start) * 1000)
        
        yield {
            "event": "sql_validated", 
            "data": {
                "step": "sql_validation",
                "ts": datetime.utcnow().isoformat(),
                "elapsed_ms": validate_elapsed,
                "validation": {
                    "ok": ok,
                    "issues": issues,
                    "allowed_tables": ["comp_financials"],
                    "max_limit": CONFIGS.database.get('query_defaults', {}).get('max_limit', 10000),
                    "granularity": plan.granularity
                }
            }
        }
        
        if not ok:
            yield {"event": "errors", "data": {"errors": issues}}
            return

        yield {"event": "sql_generated", "data": {"sql": sql}}

        # 9) SQL Execution Phase
        yield {"event": "status", "data": {"step": "sql_execution", "message": "Executing query...", "ts": datetime.utcnow().isoformat()}}
        
        exec_start = time.time()
        data = await execute(sql)
        exec_elapsed = int((time.time() - exec_start) * 1000)
        
        try:
            SQLResultModel(query=sql, data=data)
        except ValidationError as ve:
            yield {"event": "errors", "data": {"errors": [str(ve)]}}
            return
        
        # Emit execution statistics
        yield {
            "event": "execution_stats",
            "data": {
                "step": "sql_execution",
                "ts": datetime.utcnow().isoformat(),
                "elapsed_ms": exec_elapsed,
                "row_count": len(data),
                "columns": list(data[0].keys()) if data else [],
                "sample_data": data[:3]
            }
        }
        
        yield {"event": "data_retrieved", "data": {"row_count": len(data), "sample_data": data[:3]}}

        # 10) Chart Planning Phase
        yield {"event": "status", "data": {"step": "chart_generation", "message": "Planning chart...", "ts": datetime.utcnow().isoformat()}}
        
        chart_start = time.time()
        chart_plan = plan_chart_rule_based(data, query)
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
        
        yield {
            "event": "chart_planned",
            "data": {
                "step": "chart_generation",
                "ts": datetime.utcnow().isoformat(),
                "elapsed_ms": chart_elapsed,
                "chart_type": chart_plan.chart_type,
                "series_count": len(chart_plan.series),
                "x_axis": chart_plan.x_axis.dict() if chart_plan.x_axis else None
            }
        }
        
        try:
            ChartSpecModel(**spec)
            yield {"event": "chart_generated", "data": {"chart_spec": spec}}
        except ValidationError as ve:
            # Send warning but continue with raw spec - frontend can handle it
            yield {"event": "warning", "data": {"message": f"Chart spec validation warning: {str(ve)}"}}
            yield {"event": "chart_generated", "data": {"chart_spec": spec}}

        # 11) Analysis Generation Phase
        yield {"event": "status", "data": {"step": "analysis_generation", "message": "Generating insights...", "ts": datetime.utcnow().isoformat()}}
        
        analysis_start = time.time()
        full_analysis = ""
        async for text in stream_insights_llm(data, sql, query):
            if text:
                full_analysis += text
                yield {"event": "analysis_streaming", "data": {"partial_analysis": text}}
        
        analysis_elapsed = int((time.time() - analysis_start) * 1000)
        
        # Emit complete buffered analysis
        yield {"event": "analysis_complete", "data": {"analysis": full_analysis}}
        
        # Cleanup expired sessions
        from .clarify import get_session_store
        session_store = await get_session_store()
        await session_store.cleanup_expired()
        
        # Final workflow completion with total timing
        total_elapsed = int((time.time() - workflow_start) * 1000)
        yield {
            "event": "workflow_complete", 
            "data": {
                "message": "Analytics memory workflow completed",
                "ts": datetime.utcnow().isoformat(),
                "total_elapsed_ms": total_elapsed
            }
        }


# Standalone wrapper function for main.py
async def analytics_memory_workflow(query: str, session_id: str = None, session_store=None):
    """Wrapper function that instantiates and runs the AnalyticsMemoryWorkflow"""
    workflow_instance = AnalyticsMemoryWorkflow()
    async for event in workflow_instance.events(query, session_id):
        yield event
