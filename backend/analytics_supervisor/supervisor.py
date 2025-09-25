from __future__ import annotations
from typing import Any, Dict, AsyncGenerator, Optional, List
import time
import json
import uuid
import logging
import os
import sys
from datetime import datetime
import asyncio

logger = logging.getLogger(__name__)

# Debug configuration
SUPERVISOR_DEBUG = os.getenv('SUPERVISOR_DEBUG', 'false').lower() == 'true'

FAST_LANE_SQL_ENABLED = os.getenv('FAST_LANE_SQL', 'true').lower() == 'true'

DEFAULT_OFFTOPIC_MESSAGE = "I'm focused on financial analytics..."

from analytics_memory.config import CONFIGS
from analytics_shared.intent import (
    ClarifyRequestModel,
    IntentModel,
    detect_intent_with_clarifications_async,
    intent_to_sql_criteria,
)

from .tools import SupervisorTools
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from unified_responses_client import get_unified_client, SUPERVISOR_REASONING_EFFORT
from .schemas import FinalSummarySchema, WorkflowState

# Registry of active supervisor workflows keyed by session_id
ACTIVE_WORKFLOWS: Dict[str, "SupervisorWorkflow"] = {}
INTENT_CACHE: Dict[str, Dict[str, Any]] = {}
INTENT_CACHE_TTL = 60  # seconds


class SupervisorWorkflow:
    """
    Claude Code-style single-agent orchestrator with planning and tool execution.
    
    Implements the propose-and-apply pattern with explicit side-effect gating.
    """

    def __init__(self):
        self.tools = SupervisorTools(CONFIGS.__dict__)
        try:
            self.client = get_unified_client()
        except ValueError:
            # For development/testing without OpenAI API key
            self.client = None
        self.workflow_states: Dict[str, WorkflowState] = {}  # Session-based state tracking
        self._clarification_events: Dict[str, asyncio.Event] = {}  # Session-based clarification events
        self._pending_clarifications: Dict[str, ClarifyRequestModel] = {}  # Session-based clarification requests

    async def events(self, query: str, session_id: Optional[str] = None) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Claude Code-style orchestration with planning and execution phases.
        """
        start_ts = time.time()
        now = datetime.utcnow().isoformat()

        # Session bootstrap
        original_session_id = session_id
        if not session_id:
            session_id = str(uuid.uuid4())

        logger.debug(f"SUPERVISOR_WORKFLOW - Query: {query[:50]}..., Session: {session_id}, Original session: {original_session_id}")

        # Initialize workflow state
        state = WorkflowState(
            session_id=session_id,
            current_phase="initializing",
            started_at=now
        )
        self.workflow_states[session_id] = state
        # Register active workflow for this session
        ACTIVE_WORKFLOWS[session_id] = self

        yield {"event": "session_started", "data": {"session_id": session_id, "ts": now}}

        try:
            # Ultra-fast guard for obvious small talk
            if self._is_small_talk(query):
                state.early_exit = True
                state.current_phase = "completed"
                ts_final = datetime.utcnow().isoformat()
                state.completed_at = ts_final
                logger.info(f"[SUPERVISOR] Small-talk detected; early exit for session {session_id}")
                yield {"event": "final_answer", "event_type": "user", "data": {"message": DEFAULT_OFFTOPIC_MESSAGE, "category": "general_conversation", "is_financial": False, "ts": ts_final}}
                yield {"event": "workflow_complete", "event_type": "thinking", "data": {"message": "Workflow completed with early exit (small talk)", "early_exit": True, "ts": ts_final, "total_elapsed_ms": int((time.time() - start_ts) * 1000)}}
                return

            # ====== FAST INTENT DETECTION PHASE (heuristic-first) ======
            state.current_phase = "intent_detection"

            if not self._looks_financial(query):
                state.early_exit = True
                state.current_phase = "completed"
                ts_final = datetime.utcnow().isoformat()
                state.completed_at = ts_final
                yield {"event": "final_answer", "event_type": "user", "data": {
                    "message": DEFAULT_OFFTOPIC_MESSAGE,
                    "category": "other",
                    "is_financial": False,
                    "ts": ts_final
                }}
                yield {"event": "workflow_complete", "event_type": "thinking", "data": {
                    "message": "Workflow completed with early exit (keyword sieve)",
                    "early_exit": True,
                    "ts": ts_final,
                    "total_elapsed_ms": int((time.time() - start_ts) * 1000)
                }}
                return

            cache_key = (query or "").strip().lower()
            cache_entry = INTENT_CACHE.get(cache_key)
            cache_hit = False
            if cache_entry and time.time() - cache_entry["ts"] <= INTENT_CACHE_TTL:
                cache_hit = True

            detection_started_ts = datetime.utcnow().isoformat()
            start_message = "Using cached intent result" if cache_hit else "Detecting user intent and required slots..."
            yield {"event": "intent_detection_started", "data": {
                "message": start_message,
                "cache_hit": cache_hit,
                "ts": detection_started_ts
            }}

            if cache_hit:
                logger.info(f"[SUPERVISOR] Intent cache hit for session {session_id}")
                intent = IntentModel(**cache_entry["payload"])
            else:
                intent = await detect_intent_with_clarifications_async(
                    query,
                    CONFIGS.__dict__,
                    session_id=session_id
                )
                INTENT_CACHE[cache_key] = {"payload": intent.dict(), "ts": time.time()}
                logger.info(f"[SUPERVISOR] Intent detection executed for session {session_id}")

            yield {"event": "intent_detection_complete", "data": {
                "intent_key": intent.intent_key,
                "confidence": intent.confidence,
                "slots_detected": intent.slots_detected,
                "clarifications_needed": len(intent.clarifications_suggested) > 0,
                "cache_hit": cache_hit,
                "ts": datetime.utcnow().isoformat()
            }}

            state.session_metadata["intent_cache_hit"] = cache_hit

            # Schema validation
            state.current_phase = "validation"
            validation_started_ts = datetime.utcnow().isoformat()
            yield {"event": "schema_validation_started", "data": {
                "intent_key": intent.intent_key,
                "ts": validation_started_ts
            }}

            required_fields = self._get_required_fields_for_intent(intent.intent_key or "")
            missing_fields = self._validate_schema(intent.slots_detected, required_fields)
            provided_fields = {field: intent.slots_detected.get(field) for field in required_fields}
            validation_passed = len(missing_fields) == 0

            yield {"event": "schema_validation_complete", "data": {
                "intent_key": intent.intent_key,
                "required_fields": required_fields,
                "provided_fields": provided_fields,
                "missing_fields": missing_fields,
                "validation_passed": validation_passed,
                "ts": datetime.utcnow().isoformat()
            }}

            clarification_requests: List[ClarifyRequestModel] = []

            # Convert LLM suggestions into clarification requests first
            for suggestion in intent.clarifications_suggested or []:
                request = ClarifyRequestModel(
                    slot=suggestion.slot,
                    question=suggestion.question or f"Please provide a value for {suggestion.slot}.",
                    type=suggestion.type or "single",
                    options=suggestion.options or self._get_options_for_slot(suggestion.slot),
                    default=None,
                    reason=suggestion.reason or f"{suggestion.slot} is required for this analysis.",
                    required=True,
                    request_id=str(uuid.uuid4()),
                    proposed=suggestion.proposed,
                    proposed_confidence=suggestion.proposed_confidence or 0.0,
                    session_id=session_id,
                )
                clarification_requests.append(request)

            # Add schema-driven clarifications for any remaining missing fields
            for field in missing_fields:
                if any(req.slot == field for req in clarification_requests):
                    continue
                clarification_requests.append(ClarifyRequestModel(
                    slot=field,
                    question=f"Which {field} should we use for this analysis?",
                    type="single",
                    options=self._get_options_for_slot(field),
                    default=None,
                    reason=f"{field} is required for intent {intent.intent_key}.",
                    required=True,
                    request_id=str(uuid.uuid4()),
                    session_id=session_id,
                ))

            clarification_answers: List[Dict[str, Any]] = []
            if clarification_requests:
                yield {"event": "clarification_loop_start", "data": {
                    "total_clarifications": len(clarification_requests),
                    "session_id": session_id,
                    "ts": datetime.utcnow().isoformat()
                }}

                for idx, request in enumerate(clarification_requests, start=1):
                    self._pending_clarifications[session_id] = request
                    evt = self._clarification_events.setdefault(session_id, asyncio.Event())
                    if evt.is_set():
                        evt.clear()

                    yield {"event": "clarification_request", "data": {
                        **request.model_dump(),
                        "question_number": idx,
                        "total_questions": len(clarification_requests),
                        "progress": f"{idx}/{len(clarification_requests)}"
                    }}

                    await self._wait_for_clarification(session_id)

                    answer_value = getattr(self.workflow_states.get(session_id), 'clarification_answer', None)
                    if answer_value is not None:
                        intent.slots_detected[request.slot] = answer_value
                        clarification_answers.append({"slot": request.slot, "answer": answer_value})
                        yield {"event": "clarification_acknowledged", "data": {
                            "slot": request.slot,
                            "answer": answer_value,
                            "question_number": idx,
                            "remaining": len(clarification_requests) - idx,
                            "ts": datetime.utcnow().isoformat()
                        }}
                    self._pending_clarifications.pop(session_id, None)
                    self._clarification_events.pop(session_id, None)
                    workflow_state = self.workflow_states.get(session_id)
                    if workflow_state:
                        workflow_state.clarification_answer = None

                yield {"event": "clarification_loop_complete", "data": {
                    "total_answered": len(clarification_answers),
                    "clarifications": clarification_answers,
                    "ts": datetime.utcnow().isoformat()
                }}
            else:
                yield {"event": "clarification_skipped", "data": {
                    "reason": "All required fields present",
                    "ts": datetime.utcnow().isoformat()
                }}

            yield {"event": "intent_finalized", "data": {
                "intent_key": intent.intent_key,
                "confidence": intent.confidence,
                "slots_detected": intent.slots_detected,
                "ts": datetime.utcnow().isoformat()
            }}

            final_missing_fields = self._validate_schema(intent.slots_detected, required_fields)
            schema_status = "passed" if not clarification_requests else "clarified"
            if final_missing_fields:
                schema_status = "partial"

            intent_dict = intent.dict()
            logger.info(f"[SUPERVISOR] Intent extracted: {intent_dict.get('intent_key')} for session {session_id}")

            criteria_model = intent_to_sql_criteria(intent, CONFIGS.__dict__)
            criteria_payload = criteria_model.dict()
            criteria_payload["ts"] = datetime.utcnow().isoformat()
            state.session_metadata["criteria"] = criteria_payload
            yield {"event": "criteria_ready", "data": criteria_payload}

            # Store intent data in workflow state for later access
            state.intent_data = intent_dict

            # ====== EXECUTION PIPELINE (FAST LANE OR AGENT) ======
            execution_start = time.time()
            state.current_phase = "executing"
            logger.info(f"[SUPERVISOR] Tool execution phase started for session {session_id}")

            fast_lane_candidate = FAST_LANE_SQL_ENABLED and not final_missing_fields
            fast_lane_result: Dict[str, Any] = {}
            fast_lane_success = False

            data = None
            chart_spec = None
            sql_executed = None

            if fast_lane_candidate:
                yield {"event": "tool_planning_started", "data": {
                    "message": "Running fast-lane SQL pipeline...",
                    "strategy": "fast_lane_sql",
                    "ts": datetime.utcnow().isoformat()
                }}

                yield {"event": "tool_selection_reasoning", "data": {
                    "available_tools": ["plan_and_select_template", "validate_sql", "apply_execute_sql", "plan_chart", "build_chart", "short_financial_analysis"],
                    "strategy": "fast_lane_sql_pipeline",
                    "pre_validated": {
                        "classification": "financial_query",
                        "intent": intent_dict,
                        "schema_validation": schema_status
                    },
                    "ts": datetime.utcnow().isoformat()
                }}

                fast_lane_result = await self._run_fast_lane_sql(query, session_id, intent)
                for fast_event in fast_lane_result.get("events", []):
                    yield fast_event

                if fast_lane_result.get("success"):
                    fast_lane_success = True
                    full_data = fast_lane_result.get("data") or []
                    chart_spec = fast_lane_result.get("chart_spec")
                    sql_executed = fast_lane_result.get("sql")
                    data = full_data[:3]
                    state.data_retrieved = full_data
                    state.chart_spec = chart_spec
                    state.sql_executed = sql_executed
                    state.executed_tools.extend([
                        "plan_and_select_template",
                        "validate_sql",
                        "apply_execute_sql",
                    ])
                    if chart_spec:
                        state.executed_tools.append("build_chart")
                    state.session_metadata["fast_lane_sql"] = {
                        "used": True,
                        "fallback": False,
                        "granularity": fast_lane_result.get("granularity"),
                    }
                    if fast_lane_result.get("plan"):
                        state.session_metadata["fast_lane_plan"] = fast_lane_result["plan"]
                    if fast_lane_result.get("template"):
                        state.session_metadata["fast_lane_template"] = fast_lane_result["template"]
                    state.tool_execution_duration_ms = int((time.time() - execution_start) * 1000)
                else:
                    state.session_metadata["fast_lane_sql"] = {
                        "used": True,
                        "fallback": True,
                        "issues": fast_lane_result.get("issues", []),
                    }
                    yield {"event": "status", "data": {
                        "step": "fast_lane_sql",
                        "message": "Fast lane unavailable; switching to agent workflow.",
                        "ts": datetime.utcnow().isoformat()
                    }}
                    execution_start = time.time()

            if not fast_lane_success:
                yield {"event": "tool_planning_started", "data": {
                    "message": "Agent analyzing query and planning tool execution strategy...",
                    "strategy": "agent_driven_analysis",
                    "ts": datetime.utcnow().isoformat()
                }}

                yield {"event": "tool_selection_reasoning", "data": {
                    "available_tools": ["provisional_plan", "plan_and_select_template", "retrieve_templates_rag", "compile_sql", "validate_sql", "apply_execute_sql", "plan_chart", "build_chart", "short_financial_analysis"],
                    "strategy": "agent_driven_workflow_with_validated_intent",
                    "pre_validated": {
                        "classification": "financial_query",
                        "intent": intent_dict,
                        "schema_validation": schema_status
                    },
                    "ts": datetime.utcnow().isoformat()
                }}

                tool_count = 0
                had_tool_error = False
                async for tool_event in self._execute_tools_direct(query, session_id):
                    tool_count += 1
                    if tool_event.get("event") == "data_retrieved":
                        data = tool_event["data"].get("sample_data", [])
                        sql_executed = tool_event["data"].get("sql_executed")
                        if SUPERVISOR_DEBUG:
                            logger.info(f"[SUPERVISOR] Data retrieved: {len(data)} rows for session {session_id}")
                    elif tool_event.get("event") == "chart_generated":
                        chart_spec = tool_event["data"].get("chart_spec")
                        if SUPERVISOR_DEBUG:
                            logger.info(f"[SUPERVISOR] Chart generated for session {session_id}")
                    elif tool_event.get("event") == "tool_start":
                        if SUPERVISOR_DEBUG:
                            logger.info(f"[SUPERVISOR] Tool started: {tool_event['data'].get('tool')} for session {session_id}")
                    elif tool_event.get("event") == "tool_end":
                        if SUPERVISOR_DEBUG:
                            logger.info(f"[SUPERVISOR] Tool completed: {tool_event['data'].get('tool')} for session {session_id}")
                    elif tool_event.get("event") == "tool_error":
                        logger.error(f"[SUPERVISOR] Tool error: {tool_event['data'].get('tool')} - {tool_event['data'].get('error')} for session {session_id}")
                        had_tool_error = True
                    yield tool_event

                execution_duration = time.time() - execution_start
                logger.info(f"[SUPERVISOR] Tool execution completed in {execution_duration:.2f}s, processed {tool_count} events for session {session_id}")

                state.data_retrieved = data
                state.chart_spec = chart_spec
                state.sql_executed = sql_executed
                state.tool_execution_duration_ms = int(execution_duration * 1000)

                if had_tool_error:
                    ts_final = datetime.utcnow().isoformat()
                    state.current_phase = "completed"
                    state.completed_at = ts_final
                    yield {"event": "workflow_complete", "event_type": "thinking", "data": {"message": "Workflow aborted due to tool error", "early_exit": False, "ts": ts_final, "total_elapsed_ms": int((time.time() - start_ts) * 1000)}}
                    return

            # ====== PHASE 3: ANALYSIS STREAMING ======
            state.current_phase = "analysis"
            yield {"event": "status", "data": {"step": "analysis_generation", "message": "Generating insights...", "ts": datetime.utcnow().isoformat()}}
            
            full_analysis = ""
            if not self.client:
                logger.error(f"[ANALYSIS] No Response API client available for session {session_id}")
                raise ValueError("Response API client required for financial analytics")

            if data:
                try:
                    async for chunk in self.client.stream_analysis(
                        messages=[
                            {"role": "system", "content": f"Analyze this financial data and provide insights.\n\nUser Query: {query}\nSQL: {sql_executed}\nData Preview: {data[:3] if data else 'No data'}"}
                        ],
                        session_id=session_id
                    ):
                        if chunk:
                            full_analysis += chunk
                            yield {"event": "analysis_streaming", "data": {"partial_analysis": chunk}}
                except Exception as e:
                    logger.error(f"[ANALYSIS] Response API failed for session {session_id}: {str(e)}")
                    raise ValueError(f"Response API required for analysis: {str(e)}")

            yield {"event": "analysis_complete", "data": {"analysis": full_analysis}}

            # ====== PHASE 4: FINALIZATION ======
            state.current_phase = "completed"
            state.completed_at = datetime.utcnow().isoformat()
            
            summary = await self._finalization_turn(query, sql_executed, data, chart_spec, full_analysis, session_id)
            
            yield {
                "event": "final_summary",
                "data": summary.dict() if hasattr(summary, 'dict') else summary
            }

            yield {
                "event": "workflow_complete",
                "data": {
                    "message": "Claude Code-style supervisor completed",
                    "ts": state.completed_at,
                    "total_elapsed_ms": int((time.time() - start_ts) * 1000)
                }
            }

        except Exception as e:
            state.errors.append(str(e))
            yield {"event": "tool_error", "data": {"error": str(e), "step": state.current_phase}}
        finally:
            # Cleanup active workflow and clarification events for this session
            ACTIVE_WORKFLOWS.pop(session_id, None)
            self._clarification_events.pop(session_id, None)
            self._pending_clarifications.pop(session_id, None)


    def _is_small_talk(self, query: str) -> bool:
        if not query:
            return False
        q = (query or "").strip().lower()
        if len(q) <= 2:
            return True
        small_phrases = {
            "hi", "hello", "hey", "how are you", "how's it going", "sup", "good morning",
            "good afternoon", "good evening", "thanks", "thank you", "what's up", "yo",
            "are you there", "ping", "help", "test"
        }
        # Normalize punctuation
        norm = "".join(ch for ch in q if ch.isalnum() or ch.isspace()).strip()
        return norm in small_phrases

    def _looks_financial(self, query: str) -> bool:
        if not query:
            return False
        q = query.lower()
        keywords = (
            "market share",
            "margin",
            "profit",
            "earnings",
            "eps",
            "revenue",
            "growth",
            "r&d",
            "rnd",
            "guidance",
            "capex",
            "opex",
            "cash flow",
            "qoq",
            "yoy",
            "quarter",
            "gross",
            "operating",
            "net income",
            "free cash",
        )
        if any(token in q for token in keywords):
            return True
        return any(part.isupper() and 1 < len(part) <= 5 for part in query.split())

    def _get_required_fields_for_intent(self, intent_key: str) -> List[str]:
        """Get required fields for a given intent."""
        intent_requirements = {
            "market_share_single": ["company"],
            "market_share_all": [],
            "margins_vs_peers": ["company"],
            "revenue_growth_analysis": [],
            "revenue_growth_vs_avg": [],
            "rnd_intensity_vs_peers": ["company"],
            "rnd_expense_vs_peers": ["company"],
            "margin_growth_vs_peers": ["company"],
        }
        return intent_requirements.get(intent_key, [])

    def _validate_schema(self, slots_detected: Dict[str, Any], required_fields: List[str]) -> List[str]:
        """Validate if all required fields are present in detected slots."""
        missing_fields = []
        for field in required_fields:
            if field not in slots_detected or not slots_detected[field]:
                missing_fields.append(field)
        return missing_fields


    async def _execute_tools_direct(self, query: str, session_id: str):
        """Direct tool execution without separate planning phase - agent-forward approach"""

        execution_start = time.time()
        logger.info(f"[DIRECT] Starting direct tool execution for session {session_id}")

        if not self.client:
            logger.error(f"[DIRECT] No OpenAI client available for session {session_id} - Response API required")
            raise ValueError("OpenAI client unavailable - Response API required for tool execution")

        # Get tool schemas from SupervisorTools
        tool_schemas = self.tools.get_tool_schemas()
        if SUPERVISOR_DEBUG:
            logger.info(f"[DIRECT] Loaded {len(tool_schemas)} tool schemas: {[t.get('function', {}).get('name') for t in tool_schemas]}")

        # Get current workflow state to pass context
        state = self.workflow_states.get(session_id)
        intent_dict = getattr(state, 'intent_data', {}) if state else {}

        # Prepare initial messages with context and intent
        initial_messages = [
            {
                "role": "system",
                "content": f"""You are a financial analytics agent. You have access to tools for analyzing financial data.

User Query: {query}
Classification: Financial query (passed pre-validation)
Intent Data: {intent_dict}

Your task is to:
1. Create a provisional plan based on the intent
2. Retrieve relevant templates using RAG
3. Compile and validate SQL queries
4. Execute SQL and retrieve data
5. Generate charts if applicable
6. Perform financial analysis

Use tools sequentially and logically. Start with provisional_plan, then proceed based on the analysis type needed."""
            }
        ]

        if SUPERVISOR_DEBUG:
            logger.info(f"[DIRECT] Prepared {len(initial_messages)} initial messages with intent: {intent_dict.get('intent_key', 'unknown')}")

        # Tool loop with agent deciding what to call
        async for event in self._tool_calling_loop(initial_messages, tool_schemas, session_id, query):
            yield event

        execution_duration = time.time() - execution_start
        logger.info(f"[DIRECT] Direct tool execution completed in {execution_duration:.2f}s for session {session_id}")



    async def _execute_single_tool(self, tool_name: str, tool_args: Dict[str, Any], session_id: str):
        """Execute a single tool call"""

        tool_start = time.time()
        if SUPERVISOR_DEBUG:
            logger.info(f"[SINGLE_TOOL] Executing {tool_name} for session {session_id}")

        if SUPERVISOR_DEBUG:
            logger.debug(f"[SINGLE_TOOL] Args for {tool_name}: {tool_args}")
        
        if tool_name == "provisional_plan":
            from analytics_memory.types import IntentModel
            intent = IntentModel(**tool_args["intent"])
            result = self.tools.provisional_plan(intent)
            return result.dict()

        elif tool_name == "plan_and_select_template":
            from analytics_memory.types import IntentModel
            intent = IntentModel(**tool_args["intent"])
            result = self.tools.plan_and_select_template(intent)
            return result

        elif tool_name == "retrieve_templates_rag":
            result = await self.tools.retrieve_templates_rag(
                tool_args["query"],
                tool_args.get("intent_key"),
                tool_args.get("top_k", 3),
                tool_args.get("mode", "hybrid")
            )
            return result

        elif tool_name == "search_metrics_rag":
            result = await self.tools.search_metrics_rag(
                tool_args["query"],
                tool_args.get("category"),
                tool_args.get("top_k", 5),
                tool_args.get("include_derived", True)
            )
            return result

        elif tool_name == "search_companies_rag":
            result = await self.tools.search_companies_rag(
                tool_args["query"],
                tool_args.get("sector"),
                tool_args.get("top_k", 5)
            )
            return result

        elif tool_name == "get_analytics_context_rag":
            result = await self.tools.get_analytics_context_rag(
                tool_args["query"],
                tool_args.get("intent_key"),
                tool_args.get("company_filter"),
                tool_args.get("category_filter")
            )
            return result
            
        elif tool_name == "choose_template_from_config":
            from analytics_memory.types import IntentModel, QueryPlanModel
            intent = IntentModel(**tool_args["intent"])
            plan = QueryPlanModel(**tool_args["plan"])
            result = self.tools.choose_template_from_config(intent, plan)
            return result
            
        elif tool_name == "validate_sql":
            ok, issues = self.tools.validate_sql(
                tool_args["sql"],
                tool_args["granularity"],
                tool_args.get("max_limit")
            )
            return {"ok": ok, "issues": issues}
            
        elif tool_name == "apply_execute_sql":
            # Execute SQL directly after validation
            sql = tool_args["sql"]
            result = await self.tools.apply_execute_sql(sql)
            
            # Track execution in workflow state
            wf_state = self.workflow_states.get(session_id) if hasattr(self, 'workflow_states') else None
            if wf_state:
                wf_state.executed_tools.append("apply_execute_sql")
                if result.get("success"):
                    wf_state.sql_executed = sql
                    wf_state.data_retrieved = result.get("data", [])
            
            return result
            
        elif tool_name == "short_financial_analysis":
            result = self.tools.short_financial_analysis(
                tool_args["data"],
                tool_args["query"],
                tool_args["sql"]
            )
            return result

        elif tool_name == "plan_chart":
            result = self.tools.plan_chart(
                tool_args["data"],
                tool_args["query"],
                tool_args.get("intent_key")
            )
            return result.dict() if hasattr(result, 'dict') else result
            
        elif tool_name == "request_clarification":
            from analytics_memory.types import IntentModel, QueryPlanModel
            intent = IntentModel(**tool_args["intent"])
            plan = QueryPlanModel(**tool_args["plan"])
            template = tool_args.get("template")
            result = await self.tools.request_clarification(intent, plan, template, session_id)
            return result
            
        elif tool_name == "build_chart":
            result = self.tools.build_chart(
                tool_args["data"],
                tool_args["chart_plan"],
                tool_args.get("comparison"),
                tool_args.get("intent_key")
            )
            return result

        elif tool_name == "compile_sql":
            # New SQL compilation step using analytics_shared
            try:
                from analytics_shared.sql.compiler import compile_sql_from_plan
                from analytics_memory.types import IntentModel, QueryPlanModel

                intent = IntentModel(**tool_args["intent"])
                plan = QueryPlanModel(**tool_args["plan"])
                template = tool_args.get("template")

                sql = compile_sql_from_plan(plan.dict(), intent.dict(), self.tools.configs, template)

                result = {
                    "success": True,
                    "sql": sql,
                    "template_used": template.get("name") if template else "generic",
                    "compilation_method": "analytics_shared"
                }

                # Track in workflow state
                wf_state = self.workflow_states.get(session_id) if hasattr(self, 'workflow_states') else None
                if wf_state:
                    wf_state.executed_tools.append("compile_sql")
                    wf_state.compiled_sql = sql

                return result

            except Exception as compile_error:
                logger.error(f"[COMPILE_SQL] SQL compilation failed: {compile_error}")
                return {
                    "success": False,
                    "error": f"SQL compilation failed: {str(compile_error)}",
                    "tool": "compile_sql"
                }

        else:
            logger.error(f"[SINGLE_TOOL] Unknown tool: {tool_name} for session {session_id}")
            raise ValueError(f"Unknown tool: {tool_name}")

        tool_duration = time.time() - tool_start
        if SUPERVISOR_DEBUG:
            logger.info(f"[SINGLE_TOOL] Tool {tool_name} completed in {tool_duration:.3f}s for session {session_id}")

        if 'result' in locals():
            return result
        else:
            logger.warning(f"[SINGLE_TOOL] No result returned from {tool_name} for session {session_id}")
            return None

    async def _run_fast_lane_sql(
        self,
        query: str,
        session_id: str,
        intent: IntentModel,
    ) -> Dict[str, Any]:
        """Run deterministic SQL pipeline without entering the agent loop."""
        events: List[Dict[str, Any]] = []
        issues: List[str] = []
        full_data: List[Dict[str, Any]] = []
        chart_spec: Optional[Dict[str, Any]] = None
        sql: str = ""
        plan_dict: Dict[str, Any] = {}
        template: Optional[Dict[str, Any]] = None
        granularity: Optional[str] = None

        try:
            from analytics_memory.types import IntentModel as MemoryIntentModel, QueryPlanModel as MemoryQueryPlanModel

            memory_intent = MemoryIntentModel(**intent.dict())
            plan_start = time.time()
            plan_result = self.tools.plan_and_select_template(memory_intent)
            template = plan_result.get("template")
            plan_dict = plan_result.get("plan", {}) or {}

            plan_model: Optional[MemoryQueryPlanModel] = None
            try:
                if plan_dict:
                    plan_model = MemoryQueryPlanModel(**plan_dict)
            except Exception as plan_exc:
                logger.warning(f"[FAST_LANE] Unable to hydrate QueryPlanModel: {plan_exc}")

            sql = plan_result.get("sql", "")
            granularity = plan_result.get("granularity") or (getattr(plan_model, "granularity", None) or "annual")

            elapsed_ms = int((time.time() - plan_start) * 1000)
            timestamp = datetime.utcnow().isoformat()

            events.append({
                "event": "plan_built",
                "data": {
                    "plan": plan_dict,
                    "ts": timestamp,
                    "elapsed_ms": elapsed_ms,
                },
            })
            events.append({
                "event": "template_selected",
                "data": {
                    "template": template or {},
                    "ts": timestamp,
                    "elapsed_ms": elapsed_ms,
                },
            })
            events.append({
                "event": "sql_compiled",
                "data": {
                    "sql_length": len(sql),
                    "template_used": (template or {}).get("name", "unknown"),
                    "ts": timestamp,
                    "elapsed_ms": elapsed_ms,
                },
            })
            events.append({
                "event": "sql_generated",
                "data": {
                    "sql": sql,
                    "ts": timestamp,
                    "elapsed_ms": elapsed_ms,
                },
            })

            validation_start = time.time()
            validation_result = self.tools.validate_sql(sql, granularity)
            if isinstance(validation_result, tuple):
                ok, issues = validation_result
            else:
                ok = bool(validation_result.get("ok"))
                issues = validation_result.get("issues", [])
            validation_elapsed = int((time.time() - validation_start) * 1000)
            events.append({
                "event": "sql_validated",
                "data": {
                    "ok": bool(ok),
                    "issues": issues,
                    "granularity": granularity,
                    "ts": datetime.utcnow().isoformat(),
                    "elapsed_ms": validation_elapsed,
                },
            })
            if not ok:
                events.append({
                    "event": "warning",
                    "data": {
                        "message": "Fast lane SQL validation failed; using agent workflow instead.",
                        "issues": issues,
                        "ts": datetime.utcnow().isoformat(),
                    },
                })
                return {
                    "success": False,
                    "events": events,
                    "data": full_data,
                    "chart_spec": chart_spec,
                    "sql": sql,
                    "plan": plan_dict,
                    "template": template,
                    "granularity": granularity,
                    "issues": issues,
                }

            execution_start = time.time()
            execution_result = await self.tools.apply_execute_sql(sql)
            execution_elapsed = int((time.time() - execution_start) * 1000)
            if not execution_result.get("success"):
                error_msg = execution_result.get("error", "Unknown SQL execution error")
                events.append({
                    "event": "sql_executed",
                    "data": {
                        "sql": sql,
                        "success": False,
                        "error": error_msg,
                        "ts": datetime.utcnow().isoformat(),
                        "elapsed_ms": execution_elapsed,
                    },
                })
                events.append({
                    "event": "warning",
                    "data": {
                        "message": "Fast lane SQL execution failed; using agent workflow instead.",
                        "sql": sql,
                        "ts": datetime.utcnow().isoformat(),
                    },
                })
                return {
                    "success": False,
                    "events": events,
                    "data": full_data,
                    "chart_spec": chart_spec,
                    "sql": sql,
                    "plan": plan_dict,
                    "template": template,
                    "granularity": granularity,
                    "issues": [error_msg],
                }

            full_data = execution_result.get("data", []) or []
            row_count = len(full_data)
            events.append({
                "event": "sql_executed",
                "data": {
                    "sql": sql,
                    "row_count": row_count,
                    "success": True,
                    "ts": datetime.utcnow().isoformat(),
                    "elapsed_ms": execution_elapsed,
                },
            })
            events.append({
                "event": "data_retrieved",
                "data": {
                    "row_count": row_count,
                    "sample_data": full_data[:3] if full_data else [],
                    "sql_executed": sql,
                    "ts": datetime.utcnow().isoformat(),
                },
            })
            if row_count == 0:
                events.append({
                    "event": "warning",
                    "data": {
                        "message": "Fast lane produced no rows; using agent workflow instead.",
                        "sql": sql,
                        "ts": datetime.utcnow().isoformat(),
                    },
                })
                return {
                    "success": False,
                    "events": events,
                    "data": full_data,
                    "chart_spec": chart_spec,
                    "sql": sql,
                    "plan": plan_dict,
                    "template": template,
                    "granularity": granularity,
                    "issues": ["no_rows_returned"],
                }

            chart_start = time.time()
            chart_plan = self.tools.plan_chart(full_data, query, intent.intent_key)
            if chart_plan:
                chart_elapsed = int((time.time() - chart_start) * 1000)
                events.append({
                    "event": "chart_planned",
                    "data": {
                        "chart_type": getattr(chart_plan, "chart_type", "unknown"),
                        "series_count": len(getattr(chart_plan, "series", []) or []),
                        "ts": datetime.utcnow().isoformat(),
                        "elapsed_ms": chart_elapsed,
                    },
                })
                comparison = getattr(chart_plan, "comparison", None)
                if comparison is None and 'comparison' in plan_dict:
                    comparison = plan_dict.get("comparison")
                chart_spec = self.tools.build_chart(
                    full_data,
                    chart_plan,
                    comparison,
                    intent.intent_key,
                )
                events.append({
                    "event": "chart_generated",
                    "data": {
                        "chart_spec": chart_spec,
                        "ts": datetime.utcnow().isoformat(),
                    },
                })

            analysis_payload = self.tools.short_financial_analysis(full_data, query, sql)
            events.append({
                "event": "analysis_complete",
                "data": {
                    "analysis": analysis_payload,
                    "insights": analysis_payload.get("insights", []),
                    "summary": analysis_payload.get("summary", ""),
                    "data_points": analysis_payload.get("data_points", 0),
                    "ts": datetime.utcnow().isoformat(),
                },
            })

            return {
                "success": True,
                "events": events,
                "data": full_data,
                "chart_spec": chart_spec,
                "sql": sql,
                "plan": plan_dict,
                "template": template,
                "granularity": granularity,
                "issues": issues,
            }
        except Exception as exc:
            logger.error(f"[FAST_LANE] Exception during fast lane execution for session {session_id}: {exc}")
            events.append({
                "event": "warning",
                "data": {
                    "message": f"Fast lane error: {exc}",
                    "ts": datetime.utcnow().isoformat(),
                },
            })
            return {
                "success": False,
                "events": events,
                "data": full_data,
                "chart_spec": chart_spec,
                "sql": sql,
                "plan": plan_dict,
                "template": template,
                "granularity": granularity,
                "issues": [str(exc)],
            }

    async def _finalization_turn(self, query: str, sql: str, data: List, chart_spec: Dict, analysis: str, session_id: str) -> FinalSummarySchema:
        """Phase 5: Summarize results"""

        if not self.client:
            logger.error(f"[FINALIZATION] No Response API client available for session {session_id}")
            raise ValueError("Response API client required for finalization")

        try:
            messages = [
                {"role": "system", "content": "Summarize the analytics workflow results concisely."},
                {"role": "user", "content": f"Summarize results for query '{query}'. SQL: {sql}. Rows: {len(data) if data else 0}. Analysis: {analysis[:200]}..."}
            ]

            return await self.client.finalization_turn(
                messages=messages,
                response_format=FinalSummarySchema,
                session_id=session_id,
                reasoning_effort="low"
            )
        except Exception as e:
            logger.error(f"[FINALIZATION] Response API failed for session {session_id}: {str(e)}")
            raise ValueError(f"Response API required for finalization: {str(e)}")


    def _is_follow_up_query(self, query: str, cached_artifact: Any) -> bool:
        """Detect if query is a simple follow-up that could use cached context"""
        query_lower = query.lower()

        # Common follow-up patterns
        follow_up_patterns = [
            "make it", "change to", "switch to", "use", "quarterly", "annual",
            "different company", "another company", "instead", "modify"
        ]

        # Check if query contains modification patterns and we have cached context
        has_modification = any(pattern in query_lower for pattern in follow_up_patterns)
        has_cached_context = cached_artifact is not None

        return has_modification and has_cached_context

    async def _smart_patch_artifact(self, query: str, cached_artifact: Any, session_id: str) -> Any:
        """Use agent to intelligently patch the cached artifact based on follow-up query"""
        if not self.client:
            return None

        try:
            # Prepare messages for agent analysis
            messages = [
                {
                    "role": "system",
                    "content": "You are helping to modify a cached financial query artifact based on a follow-up request. Analyze the follow-up query and determine what changes need to be made to the existing artifact. Return the modified artifact as JSON."
                },
                {
                    "role": "user",
                    "content": f"Original artifact: {json.dumps(cached_artifact.dict() if hasattr(cached_artifact, 'dict') else cached_artifact)}\n\nFollow-up query: {query}\n\nPlease modify the artifact to reflect the follow-up request and return the updated JSON."
                }
            ]

            # Use agent to determine the patch
            response = await self.client.finalization_turn(
                messages=messages,
                session_id=session_id,
                reasoning_effort="low"
            )

            if response:
                try:
                    # Try to parse the response as modified artifact
                    if isinstance(response, str):
                        patched_data = json.loads(response)
                    else:
                        patched_data = response

                    logger.info(f"[SMART_PATCH] Successfully patched artifact for session {session_id}")
                    return patched_data
                except (json.JSONDecodeError, Exception) as e:
                    logger.warning(f"[SMART_PATCH] Failed to parse agent response for session {session_id}: {e}")
                    return None

        except Exception as e:
            logger.error(f"[SMART_PATCH] Failed to patch artifact for session {session_id}: {e}")
            return None

        return None

    def _get_tool_phase(self, tool_name: str) -> str:
        """Get the workflow phase for a tool (for animation color coding)"""
        phase_map = {
            'provisional_plan': 'planning',
            'plan_and_select_template': 'planning',
            'retrieve_templates_rag': 'planning',
            'compile_sql': 'planning',               # New SQL compilation step
            'validate_sql': 'planning',
            'apply_execute_sql': 'execution',
            'plan_chart': 'execution',
            'build_chart': 'execution',
            'short_financial_analysis': 'synthesis',
            'request_clarification': 'analysis'
        }
        return phase_map.get(tool_name, 'execution')

    def _estimate_tool_duration(self, tool_name: str) -> int:
        """Estimate tool execution duration in milliseconds for animation timing"""
        duration_map = {
            'provisional_plan': 500,
            'plan_and_select_template': 1000,
            'retrieve_templates_rag': 800,
            'compile_sql': 400,                # New SQL compilation step
            'validate_sql': 300,
            'apply_execute_sql': 2500,
            'plan_chart': 600,
            'build_chart': 800,
            'short_financial_analysis': 1200,
            'request_clarification': 0
        }
        return duration_map.get(tool_name, 1000)

    def _get_options_for_slot(self, slot: str) -> List[str]:
        """Get available options for a clarification slot (backward compatible)"""
        if not slot:
            return []

        slot = str(slot).lower()

        if slot == "company":
            return self.tools.configs.get("companies", {}).get("selection_rules", {}).get("default_companies", {}).get("tickers", ["NVDA", "AMD", "INTC", "MU", "QCOM", "AVGO", "TXN"])
        if slot == "comparison":
            # Derive comparison choices from YAML-defined intents
            try:
                qp = (self.tools.configs.get("queries", {}) or {}).get("query_patterns", {}) or {}
                keys = list(qp.keys()) if isinstance(qp, dict) else []
                opts = []
                if any(str(k).lower().endswith("_single") for k in keys):
                    opts.append("single")
                if any(str(k).lower().endswith("_all") for k in keys):
                    opts.append("all")
                # Fallback to both if not derivable
                return opts or ["single", "all"]
            except Exception:
                return ["single", "all"]
        if slot == "granularity":
            return ["annual", "quarterly"]
        return []

    def _get_options_with_labels(self, slot: str) -> List[dict]:
        """Get available options with enhanced labels for better UX"""
        if not slot:
            return []

        slot = str(slot).lower()

        if slot == "company":
            tickers = self.tools.configs.get("companies", {}).get("selection_rules", {}).get("default_companies", {}).get("tickers", ["NVDA", "AMD", "INTC", "MU", "QCOM", "AVGO", "TXN"])
            # Company name mapping for better UX
            company_names = {
                "NVDA": "NVIDIA Corporation",
                "AMD": "Advanced Micro Devices",
                "INTC": "Intel Corporation",
                "MU": "Micron Technology",
                "QCOM": "Qualcomm Inc.",
                "AVGO": "Broadcom Inc.",
                "TXN": "Texas Instruments"
            }
            return [{"value": ticker, "label": company_names.get(ticker, ticker)} for ticker in tickers]

        if slot == "comparison":
            # Derive comparison choices from YAML-defined intents
            try:
                qp = (self.tools.configs.get("queries", {}) or {}).get("query_patterns", {}) or {}
                keys = list(qp.keys()) if isinstance(qp, dict) else []
                opts = []
                if any(str(k).lower().endswith("_single") for k in keys):
                    opts.append({"value": "single", "label": "Single Company"})
                if any(str(k).lower().endswith("_all") for k in keys):
                    opts.append({"value": "all", "label": "All Companies"})
                # Fallback to both if not derivable
                return opts or [
                    {"value": "single", "label": "Single Company"},
                    {"value": "all", "label": "All Companies"}
                ]
            except Exception:
                return [
                    {"value": "single", "label": "Single Company"},
                    {"value": "all", "label": "All Companies"}
                ]
        if slot == "granularity":
            return [
                {"value": "annual", "label": "Annual Data"},
                {"value": "quarterly", "label": "Quarterly Data"}
            ]
        return []

    async def _wait_for_clarification(self, session_id: str):
        """Block until a clarification answer is received for the session."""
        logger.info(f"[CLARIFY_DEBUG] _wait_for_clarification called for session {session_id}")
        evt = self._clarification_events.get(session_id)
        if not evt:
            evt = asyncio.Event()
            self._clarification_events[session_id] = evt
            logger.info(f"[CLARIFY_DEBUG] Created new event for session {session_id}")
        else:
            logger.info(f"[CLARIFY_DEBUG] Using existing event for session {session_id}, is_set: {evt.is_set()}")

        logger.info(f"[CLARIFY_DEBUG] Waiting for clarification event for session {session_id}...")
        await evt.wait()
        logger.info(f"[CLARIFY_DEBUG] Clarification event received for session {session_id}!")

    def submit_clarification(self, session_id: str, answer: Any) -> bool:
        """Submit clarification answer and signal any waiters for the session."""
        state = self.workflow_states.get(session_id)
        evt = self._clarification_events.get(session_id)

        logger.info(f"[CLARIFY_DEBUG] submit_clarification called - session: {session_id}, answer: {answer}")
        logger.info(f"[CLARIFY_DEBUG] state exists: {state is not None}, pending: {session_id in self._pending_clarifications}, event exists: {evt is not None}")

        if state and session_id in self._pending_clarifications:
            # Store the answer in the workflow state
            state.clarification_answer = answer
            logger.info(f"[CLARIFY_DEBUG] Answer stored in state: {answer}")

            # Signal the waiting clarification process
            if evt and not evt.is_set():
                evt.set()
                logger.info(f"[CLARIFY_DEBUG] Event signaled for session {session_id}")
            else:
                logger.warning(f"[CLARIFY_DEBUG] Event not signaled - evt: {evt is not None}, is_set: {evt.is_set() if evt else 'N/A'}")
            return True
        else:
            logger.warning(f"[CLARIFY_DEBUG] Clarification not processed - state: {state is not None}, pending: {session_id in self._pending_clarifications}")
        return False

    async def _tool_calling_loop(self, messages: List[Dict], tool_schemas: List[Dict], session_id: str, query: str):
        """Execute tool calling loop using Responses API"""

        loop_start = time.time()
        max_iterations = 10  # Prevent infinite loops
        data = None
        chart_spec = None
        sql_executed = None

        logger.info(f"[TOOL_LOOP] Starting tool calling loop for session {session_id}, max iterations: {max_iterations}")
        if SUPERVISOR_DEBUG:
            logger.info(f"[TOOL_LOOP] Available tools: {[tool.get('function', {}).get('name', 'unknown') for tool in tool_schemas]}")
        
        for iteration in range(max_iterations):
            iteration_start = time.time()
            if SUPERVISOR_DEBUG:
                logger.info(f"[TOOL_LOOP] Iteration {iteration + 1}/{max_iterations} for session {session_id}")

            try:
                # Call the model with tools
                api_call_start = time.time()
                if SUPERVISOR_DEBUG:
                    logger.info(f"[TOOL_LOOP] Calling OpenAI tool calling turn for session {session_id}")

                response = await self.client.tool_calling_turn(
                    messages=messages,
                    tools=tool_schemas,
                    tool_choice="auto",
                    session_id=session_id,
                    reasoning_effort="medium"
                )

                api_duration = time.time() - api_call_start
                if SUPERVISOR_DEBUG:
                    logger.info(f"[TOOL_LOOP] OpenAI API call completed in {api_duration:.2f}s for session {session_id}")
                
                # Check if model wants to call tools
                if hasattr(response, 'tool_calls') and response.tool_calls:
                    if SUPERVISOR_DEBUG:
                        logger.info(f"[TOOL_LOOP] Model requested {len(response.tool_calls)} tool calls for session {session_id}")
                    # Execute each tool call
                    tool_results = []
                    tool_execution_results = []  # Store original results for API submission

                    early_exit_triggered = False
                    for tool_call in response.tool_calls:
                        tool_start = time.time()
                        tool_name = tool_call.function.name
                        tool_args = json.loads(tool_call.function.arguments)

                        if SUPERVISOR_DEBUG:
                            logger.info(f"[TOOL_LOOP] Executing tool: {tool_name} for session {session_id}")
                        if SUPERVISOR_DEBUG:
                            logger.debug(f"[TOOL_LOOP] Tool args: {tool_args}")

                        # Emit tool selection event with animation metadata
                        yield {
                            "event": "tool_selected",
                            "data": {
                                "tool": tool_name,
                                "reasoning": f"Agent selected {tool_name} to execute next",
                                "args_preview": str(tool_args)[:100],
                                "ts": datetime.utcnow().isoformat(),
                                "animation": {
                                    "type": "activating",
                                    "intensity": "medium",
                                    "duration": 300,
                                    "phase": self._get_tool_phase(tool_name)
                                }
                            }
                        }

                        yield {
                            "event": "tool_start",
                            "data": {
                                "tool": tool_name,
                                "args_summary": str(tool_args)[:100],
                                "ts": datetime.utcnow().isoformat(),
                                "animation": {
                                    "type": "processing",
                                    "intensity": "high",
                                    "phase": self._get_tool_phase(tool_name),
                                    "estimated_duration": self._estimate_tool_duration(tool_name)
                                }
                            }
                        }

                        # Execute tool normally with enhanced error handling
                        # Note: classify_query_relevance and detect_intent are now handled before agent
                        try:
                            if SUPERVISOR_DEBUG:
                                logger.debug(f"[TOOL_EXECUTION] Executing {tool_name} with args: {json.dumps(tool_args, indent=2)}")
                            result = await self._execute_single_tool(tool_name, tool_args, session_id)
                            if SUPERVISOR_DEBUG:
                                logger.debug(f"[TOOL_EXECUTION] {tool_name} result: success={result.get('success')}, data_size={len(str(result))}")
                        except Exception as tool_exc:
                            logger.error(f"[TOOL_EXECUTION] Error executing {tool_name}: {str(tool_exc)}")
                            if SUPERVISOR_DEBUG:
                                logger.debug(f"[TOOL_EXECUTION] Full error: {repr(tool_exc)}")
                            result = {"success": False, "error": str(tool_exc), "tool": tool_name}

                        # Store original result for API submission
                        tool_execution_results.append(result)

                        # Track important results and emit SQL events
                        if tool_name == "apply_execute_sql":
                            sql_executed = tool_args.get("sql")
                            if result.get("success"):
                                data = result.get("data", [])
                                row_count = len(data)

                                # Always emit SQL executed event for frontend
                                yield {
                                    "event": "sql_executed",
                                    "data": {
                                        "sql": sql_executed,
                                        "row_count": row_count,
                                        "success": True
                                    }
                                }

                                # Emit data retrieved event
                                yield {
                                    "event": "data_retrieved",
                                    "data": {
                                        "row_count": row_count,
                                        "sample_data": data[:3] if data else [],
                                        "sql_executed": sql_executed
                                    }
                                }

                                # Add fallback for empty data
                                if row_count == 0:
                                    logger.warning(f"[TOOL_EXECUTION] SQL returned 0 rows for session {session_id}: {sql_executed}")
                                    yield {
                                        "event": "warning",
                                        "data": {
                                            "message": "No data found for the query. You may want to adjust the time period or company selection.",
                                            "sql": sql_executed
                                        }
                                    }
                            else:
                                # SQL execution failed
                                error_msg = result.get("error", "Unknown SQL error")
                                logger.error(f"[TOOL_EXECUTION] SQL execution failed for session {session_id}: {error_msg}")
                                yield {
                                    "event": "sql_executed",
                                    "data": {
                                        "sql": sql_executed,
                                        "success": False,
                                        "error": error_msg
                                    }
                                }
                        elif tool_name == "compile_sql":
                            # Emit SQL generation event for frontend
                            if result.get("success"):
                                sql_generated = result.get("sql", "")
                                yield {
                                    "event": "sql_generated",
                                    "data": {
                                        "sql": sql_generated,
                                        "sql_length": len(sql_generated),
                                        "template_used": result.get("template_used", "generic"),
                                        "compilation_method": result.get("compilation_method", "analytics_shared"),
                                        "success": True,
                                        "ts": datetime.utcnow().isoformat()
                                    }
                                }
                                # Also emit compiled event for backward compatibility
                                yield {
                                    "event": "sql_compiled",
                                    "data": {
                                        "sql_length": len(sql_generated),
                                        "template_used": result.get("template_used", "generic"),
                                        "compilation_method": result.get("compilation_method", "analytics_shared"),
                                        "ts": datetime.utcnow().isoformat()
                                    }
                                }
                            else:
                                # SQL compilation failed
                                error_msg = result.get("error", "SQL compilation failed")
                                logger.error(f"[TOOL_EXECUTION] SQL compilation failed for session {session_id}: {error_msg}")
                                yield {
                                    "event": "sql_generated",
                                    "data": {
                                        "success": False,
                                        "error": error_msg,
                                        "ts": datetime.utcnow().isoformat()
                                    }
                                }
                        elif tool_name == "short_financial_analysis":
                            # Emit analysis event for frontend
                            yield {
                                "event": "analysis_complete",
                                "data": {
                                    "analysis": result,
                                    "insights": result.get("insights", []),
                                    "summary": result.get("summary", ""),
                                    "data_points": result.get("data_points", 0)
                                }
                            }
                        elif tool_name == "plan_and_select_template":
                            # Emit virtual tool steps for frontend compatibility
                            yield {
                                "event": "plan_built",
                                "data": {
                                    "plan": result.get("plan", {}),
                                    "elapsed_ms": int((time.time() - tool_start) * 1000)
                                }
                            }

                            yield {
                                "event": "template_selected",
                                "data": {
                                    "template": result.get("template", {}),
                                    "elapsed_ms": int((time.time() - tool_start) * 1000)
                                }
                            }

                            # Emit SQL compilation events
                            sql = result.get("sql", "")
                            yield {
                                "event": "sql_compiled",
                                "data": {
                                    "sql_length": len(sql),
                                    "template_used": result.get("template", {}).get("name", "unknown"),
                                    "elapsed_ms": int((time.time() - tool_start) * 1000)
                                }
                            }

                            yield {
                                "event": "sql_generated",
                                "data": {
                                    "sql": sql,
                                    "elapsed_ms": int((time.time() - tool_start) * 1000)
                                }
                            }
                        elif tool_name == "compile_sql":
                            # Emit SQL compilation events for frontend visibility
                            if result.get("success"):
                                sql = result.get("sql", "")
                                yield {
                                    "event": "sql_generated",
                                    "data": {
                                        "sql": sql,
                                        "sql_length": len(sql),
                                        "template_used": result.get("template_used", "generic"),
                                        "compilation_method": result.get("compilation_method", "analytics_shared"),
                                        "elapsed_ms": int((time.time() - tool_start) * 1000)
                                    }
                                }
                                logger.info(f"[SQL_COMPILATION] Generated SQL query ({len(sql)} chars) for session {session_id}")
                            else:
                                logger.error(f"[SQL_COMPILATION] SQL compilation failed for session {session_id}: {result.get('error')}")

                        elif tool_name == "build_chart":
                            chart_spec = result
                            yield {"event": "chart_generated", "data": {"chart_spec": chart_spec}}

                        tool_duration = time.time() - tool_start
                        tool_duration_ms = int(tool_duration * 1000)

                        # Enhanced observability logging with latency tracking
                        logger.info(f"[OBSERVABILITY] Tool execution completed: "
                                   f"session_id={session_id}, "
                                   f"tool={tool_name}, "
                                   f"duration_ms={tool_duration_ms}, "
                                   f"iteration={iteration + 1}, "
                                   f"has_result={result is not None}")

                        # Update workflow state performance tracking
                        wf_state = self.workflow_states.get(session_id)
                        if wf_state:
                            if not wf_state.tool_execution_duration_ms:
                                wf_state.tool_execution_duration_ms = 0
                            wf_state.tool_execution_duration_ms += tool_duration_ms

                        yield {
                            "event": "tool_end",
                            "data": {
                                "tool": tool_name,
                                "output_summary": str(result)[:100] if result else "completed",
                                "duration_ms": tool_duration_ms,
                                "ts": datetime.utcnow().isoformat(),
                                "animation": {
                                    "type": "completed" if result.get("success", True) else "error",
                                    "intensity": "medium",
                                    "phase": self._get_tool_phase(tool_name),
                                    "success_burst": result.get("success", True)
                                }
                            }
                        }

                        # Add tool result to conversation (Responses API format)
                        tool_results.append({
                            "tool_call_id": tool_call.id,
                            "role": "tool",
                            "name": tool_name,
                            "content": [{"type": "input_text", "text": json.dumps(result)}]
                        })

                    # Submit tool outputs to OpenAI API with enhanced observability
                    if hasattr(response, 'response_id') and response.response_id:
                        try:
                            tool_outputs = []
                            tool_call_ids = []
                            for tool_call, execution_result in zip(response.tool_calls, tool_execution_results):
                                tool_call_ids.append(tool_call.id)
                                tool_outputs.append({
                                    "tool_call_id": tool_call.id,
                                    "output": json.dumps(execution_result) if execution_result else "{}"
                                })

                            # Enhanced structured logging for observability
                            logger.info(f"[OBSERVABILITY] Tool submission for session {session_id}: "
                                       f"response_id={response.response_id}, "
                                       f"tool_call_ids={tool_call_ids}, "
                                       f"outputs_count={len(tool_outputs)}, "
                                       f"iteration={iteration + 1}")

                            # Submit the tool outputs to continue the conversation
                            await self.client.client.responses.submit_tool_outputs(
                                response_id=response.response_id,
                                tool_outputs=tool_outputs
                            )

                            logger.info(f"[OBSERVABILITY] Successfully submitted {len(tool_outputs)} tool outputs for session {session_id}")

                            # Track cache hits for performance monitoring
                            wf_state = self.workflow_states.get(session_id)
                            if wf_state:
                                wf_state.total_api_calls += 1

                        except Exception as submit_error:
                            logger.error(f"[OBSERVABILITY] Failed to submit tool outputs for session {session_id}: "
                                        f"response_id={getattr(response, 'response_id', 'None')}, "
                                        f"error={str(submit_error)}, "
                                        f"error_type={type(submit_error).__name__}")

                    # Add assistant message and tool results to conversation (Responses API format)
                    assistant_content = [{"type": "input_text", "text": response.content}] if response.content else []
                    messages.append({
                        "role": "assistant",
                        "content": assistant_content,
                        "tool_calls": [
                            {
                                "id": tc.id,
                                "type": "function",
                                "function": {"name": tc.function.name, "arguments": tc.function.arguments}
                            } for tc in response.tool_calls
                        ]
                    })
                    messages.extend(tool_results)

                    if early_exit_triggered:
                        # Stop processing further iterations after submitting outputs
                        break

                else:
                    # No more tool calls - workflow complete
                    logger.info(f"[TOOL_LOOP] No more tool calls requested, workflow complete for session {session_id}")
                    break

                iteration_duration = time.time() - iteration_start
                if SUPERVISOR_DEBUG:
                    logger.info(f"[TOOL_LOOP] Iteration {iteration + 1} completed in {iteration_duration:.2f}s for session {session_id}")
                    
            except Exception as e:
                iteration_duration = time.time() - iteration_start
                logger.error(f"[TOOL_LOOP] Error in iteration {iteration + 1} after {iteration_duration:.2f}s for session {session_id}: {str(e)}")
                logger.error(f"[TOOL_LOOP] Error type: {type(e).__name__}")

                if SUPERVISOR_DEBUG:
                    logger.debug(f"[TOOL_LOOP] Full error details: {repr(e)}")

                yield {"event": "tool_error", "data": {"tool": "workflow", "error": str(e)}}
                break

        total_duration = time.time() - loop_start
        logger.info(f"[TOOL_LOOP] Tool calling loop completed after {total_duration:.2f}s for session {session_id}")



def get_active_workflow(session_id: str) -> Optional[SupervisorWorkflow]:
    """Lookup the active SupervisorWorkflow instance for a session, if any."""
    return ACTIVE_WORKFLOWS.get(session_id)


async def supervisor_workflow(query: str, session_id: Optional[str] = None):
    """Entry point for supervisor workflow"""
    logger.debug(f"supervisor_workflow called - Query: {query[:50]}..., Session: {session_id}")
    try:
        wf = SupervisorWorkflow()
        logger.debug(f"SupervisorWorkflow created successfully")

        # Ensure the workflow is registered in ACTIVE_WORKFLOWS before events start
        if session_id:
            ACTIVE_WORKFLOWS[session_id] = wf
            logger.debug(f"Registered workflow in ACTIVE_WORKFLOWS for session {session_id}")

        async for ev in wf.events(query, session_id):
            yield ev
    except Exception as e:
        logger.error(f"Exception in supervisor_workflow: {e}")
        import traceback
        traceback.print_exc()
        raise





