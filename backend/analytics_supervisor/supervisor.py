from __future__ import annotations
from typing import Any, Dict, AsyncGenerator, Optional, List
import time
import json
import uuid
import logging
import os
from datetime import datetime
import asyncio

logger = logging.getLogger(__name__)

# Debug configuration
SUPERVISOR_DEBUG = os.getenv('SUPERVISOR_DEBUG', 'false').lower() == 'true'

DEFAULT_OFFTOPIC_MESSAGE = "I'm focused on financial analytics..."

from analytics_memory.config import CONFIGS
from analytics_memory.intent import detect_intent_with_clarifications
from analytics_memory.types import ClarifyRequestModel

from .tools import SupervisorTools
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from unified_responses_client import get_unified_client, SUPERVISOR_REASONING_EFFORT
from .schemas import FinalSummarySchema, WorkflowState

# Registry of active supervisor workflows keyed by session_id
ACTIVE_WORKFLOWS: Dict[str, "SupervisorWorkflow"] = {}


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

            # ====== CLASSIFICATION PHASE ======
            state.current_phase = "classification"
            classification_start = time.time()

            yield {"event": "classification_started", "data": {"ts": datetime.utcnow().isoformat(), "model": "gpt-5-nano-2025-08-07"}}

            looks_financial = False
            polite_message = DEFAULT_OFFTOPIC_MESSAGE
            classification_reasoning = ""

            try:
                if self.client:
                    classification = await self.tools._classify_topic_internal(query, self.client)
                    classification_elapsed = int((time.time() - classification_start) * 1000)

                    # Extract reasoning and details
                    topic_category = getattr(classification, "topic_category", None)
                    confidence = getattr(classification, "confidence", 0.0)
                    classification_reasoning = getattr(classification, "reasoning", "")

                    yield {"event": "classification_reasoning", "data": {
                        "thinking": classification_reasoning,
                        "confidence": confidence,
                        "category": topic_category,
                        "ts": datetime.utcnow().isoformat()
                    }}

                    if topic_category == "financial_analytics":
                        looks_financial = True
                        yield {"event": "classification_complete", "data": {
                            "is_financial": True,
                            "category": topic_category,
                            "confidence": confidence,
                            "elapsed_ms": classification_elapsed,
                            "ts": datetime.utcnow().isoformat()
                        }}
                    else:
                        polite_message = getattr(classification, "polite_decline_message", None) or DEFAULT_OFFTOPIC_MESSAGE
                        yield {"event": "classification_complete", "data": {
                            "is_financial": False,
                            "category": topic_category,
                            "decline_message": polite_message,
                            "elapsed_ms": classification_elapsed,
                            "ts": datetime.utcnow().isoformat()
                        }}
            except Exception as classify_exc:
                classification_elapsed = int((time.time() - classification_start) * 1000)
                logger.warning(f"[SUPERVISOR] Classification failed for session {session_id}: {classify_exc}")
                yield {"event": "classification_error", "data": {
                    "error": str(classify_exc),
                    "elapsed_ms": classification_elapsed,
                    "ts": datetime.utcnow().isoformat()
                }}

            # Secondary guard: heuristic keyword/ticker check (no network)
            if not looks_financial and self._looks_like_financial_query(query):
                looks_financial = True
                yield {"event": "classification_fallback", "data": {
                    "method": "heuristic_keywords",
                    "is_financial": True,
                    "ts": datetime.utcnow().isoformat()
                }}

            if not looks_financial:
                state.early_exit = True
                state.current_phase = "completed"
                ts_final = datetime.utcnow().isoformat()
                state.completed_at = ts_final
                logger.info(f"[SUPERVISOR] Classified query as non-financial for session {session_id}; skipping workflow.")
                yield {"event": "final_answer", "event_type": "user", "data": {"message": polite_message, "category": "general_conversation", "is_financial": False, "ts": ts_final}}
                yield {"event": "workflow_complete", "event_type": "thinking", "data": {"message": "Workflow completed with early exit (classification)", "early_exit": True, "ts": ts_final, "total_elapsed_ms": int((time.time() - start_ts) * 1000)}}
                return

            # ====== SMART FOLLOW-UP DETECTION ======
            # Check if this is a follow-up query that can use cached context
            cached_artifact = state.structured_query_artifact
            if cached_artifact and self._is_follow_up_query(query, cached_artifact):
                logger.info(f"[SUPERVISOR] Detected follow-up query for session {session_id} - using agent context")
                yield {"event": "status", "data": {"step": "follow_up_detection", "message": "Detected follow-up query, using cached context...", "ts": datetime.utcnow().isoformat()}}

                # Let agent determine if and how to patch the artifact
                patched_artifact = await self._smart_patch_artifact(query, cached_artifact, session_id)
                if patched_artifact:
                    state.structured_query_artifact = patched_artifact
                    state.current_phase = "executing"
                    logger.info(f"[SUPERVISOR] Successfully patched artifact for session {session_id}, skipping intent detection")

                    # Jump directly to execution with patched artifact
                    async for event in self._execute_tools_direct(query, session_id):
                        yield event
                    return

            # ====== INTENT DETECTION ======
            state.current_phase = "intent_detection"
            try:
                yield {"event": "intent_detection_started", "data": {"ts": datetime.utcnow().isoformat()}}
                pre_intent = await asyncio.to_thread(
                    detect_intent_with_clarifications,
                    query,
                    self.tools.configs,
                    session_id=session_id
                )
                yield {"event": "intent_detection_complete", "data": {
                    "intent_key": pre_intent.intent_key,
                    "confidence": pre_intent.confidence,
                    "slots_detected": pre_intent.slots_detected,
                    "ts": datetime.utcnow().isoformat()
                }}

                # ====== SCHEMA VALIDATION ======
                state.current_phase = "schema_validation"
                yield {"event": "schema_validation_started", "data": {"ts": datetime.utcnow().isoformat()}}

                required_fields = self._get_required_fields_for_intent(pre_intent.intent_key)
                missing_fields = self._validate_schema(pre_intent.slots_detected, required_fields)

                yield {"event": "schema_validation_complete", "data": {
                    "required_fields": required_fields,
                    "provided_fields": list(pre_intent.slots_detected.keys()),
                    "missing_fields": missing_fields,
                    "validation_passed": len(missing_fields) == 0,
                    "ts": datetime.utcnow().isoformat()
                }}

                # ====== CLARIFICATION LOOP (ONLY IF SCHEMA VALIDATION FAILS) ======
                if missing_fields or getattr(pre_intent, 'clarifications_suggested', None):
                    state.current_phase = "clarification"
                    yield {"event": "clarification_needed", "data": {"missing_fields": missing_fields, "ts": datetime.utcnow().isoformat()}}

                    # Use missing fields from schema validation first, then fall back to LLM suggestions
                    clarifications_to_process = []

                    # Add clarifications for missing required fields
                    for field in missing_fields:
                        clarifications_to_process.append({
                            "slot": field,
                            "reason": f"Required field '{field}' is missing for {pre_intent.intent_key} analysis"
                        })

                    # Add any additional clarifications suggested by LLM
                    for clarification in getattr(pre_intent, 'clarifications_suggested', []):
                        if clarification.get('slot') not in missing_fields:
                            clarifications_to_process.append(clarification)

                    for clarification in clarifications_to_process:
                        # Get options with labels for enhanced UX (main flow only)
                        options_with_labels = self._get_options_with_labels(clarification.get('slot'))
                        # Extract just values for compatibility with existing schema
                        option_values = [opt["value"] for opt in options_with_labels]

                        clarify_request = ClarifyRequestModel(
                            slot=clarification.get('slot', 'unknown'),
                            question=clarification.get('reason', 'Please provide clarification'),
                            type='single',
                            options=option_values,
                            request_id=str(uuid.uuid4()),
                            reason=clarification.get('reason', ''),
                            session_id=session_id
                        )

                        # Add the enhanced options with labels to the dict for frontend
                        clarify_dict = clarify_request.dict()
                        clarify_dict['options_with_labels'] = options_with_labels

                        # Store pending clarification and emit request
                        self._pending_clarifications[session_id] = clarify_request
                        self._clarification_events[session_id] = asyncio.Event()
                        yield {"event": "clarification_request", "data": clarify_dict}

                        # Wait for user answer
                        await self._wait_for_clarification(session_id)

                        # Apply answer to detected intent slots
                        s = self.workflow_states.get(session_id)
                        if s and hasattr(s, 'clarification_answer'):
                            pre_intent.slots_detected[clarify_request.slot] = s.clarification_answer
                        yield {"event": "clarification_ack", "data": {"answer": getattr(self.workflow_states.get(session_id), 'clarification_answer', 'Unknown')}}

                        # Cleanup
                        self._pending_clarifications.pop(session_id, None)
                        self._clarification_events.pop(session_id, None)
                else:
                    yield {"event": "clarification_skipped", "data": {"reason": "All required fields present", "ts": datetime.utcnow().isoformat()}}

                # Persist resolved intent for reference
                state.structured_query_artifact = {"intent": getattr(pre_intent, 'dict', lambda: {} )() if hasattr(pre_intent, 'dict') else {}}
                yield {"event": "intent_finalized", "data": state.structured_query_artifact, "ts": datetime.utcnow().isoformat()}
            except Exception as pre_exc:
                logger.warning(f"[SUPERVISOR] Intent detection/validation failed: {pre_exc}")

            # ====== AGENT TOOL PLANNING & EXECUTION ======
            execution_start = time.time()
            state.current_phase = "executing"
            logger.info(f"[SUPERVISOR] Tool execution phase started for session {session_id}")

            yield {"event": "tool_planning_started", "data": {
                "message": "Agent planning tool execution strategy...",
                "intent_key": pre_intent.intent_key if 'pre_intent' in locals() else None,
                "ts": datetime.utcnow().isoformat()
            }}

            # Agent will decide tool selection strategy based on validated intent
            yield {"event": "tool_selection_reasoning", "data": {
                "available_tools": ["provisional_plan", "retrieve_templates_rag", "validate_sql", "apply_execute_sql", "plan_chart", "build_chart"],
                "strategy": "sequential_execution_based_on_intent",
                "ts": datetime.utcnow().isoformat()
            }}

            # Execute tools and forward their events
            data = None
            chart_spec = None
            sql_executed = None
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

            # If a tool error occurred, stop workflow before analysis/finalization
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


    def _looks_like_financial_query(self, query: str) -> bool:
        if not query:
            return False

        normalized = query.lower()

        keywords = getattr(self.tools, "_financial_keywords", []) or []
        for keyword in keywords:
            if keyword and keyword in normalized:
                return True

        tickers = getattr(self.tools, "_default_tickers", []) or []
        for ticker in tickers:
            if not ticker:
                continue
            ticker_value = ticker.lower() if isinstance(ticker, str) else str(ticker).lower()
            if ticker_value and ticker_value in normalized:
                return True

        return False

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

        # Tool loop with agent deciding what to call
        async for event in self._tool_calling_loop([], [], session_id, query):
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

                        yield {
                            "event": "tool_start",
                            "data": {
                                "tool": tool_name,
                                "args_summary": str(tool_args)[:100],
                                "ts": datetime.utcnow().isoformat()
                            }
                        }

                        # Handle special tool cases
                        if tool_name == "classify_query_relevance":
                            # Run classification with streaming clarification support
                            classification_result = None
                            try:
                                async for cls_event in self.tools.classify_query_relevance(
                                    tool_args.get("query") or query,
                                    session_id
                                ):
                                    # Forward any SSE-style events
                                    if isinstance(cls_event, dict) and cls_event.get("event"):
                                        yield cls_event
                                    else:
                                        classification_result = cls_event
                            except Exception as cls_exc:
                                logger.error(f"[TOOL_EXECUTION] classify_query_relevance failed: {cls_exc}")
                                classification_result = {"success": False, "error": str(cls_exc)}

                            # Default structure for tool output submission
                            if classification_result is None:
                                classification_result = {"success": True, "is_financial": True}

                            # Early exit if not financial
                            if not classification_result.get("is_financial", True) and classification_result.get("early_exit", False):
                                try:
                                    ts_final = datetime.utcnow().isoformat()
                                    # Update workflow state
                                    wf_state = self.workflow_states.get(session_id)
                                    if wf_state:
                                        wf_state.early_exit = True
                                        wf_state.current_phase = "completed"
                                        wf_state.completed_at = ts_final

                                    polite = classification_result.get("message") or DEFAULT_OFFTOPIC_MESSAGE
                                    category = classification_result.get("category", "general_conversation")
                                    yield {"event": "final_answer", "event_type": "user", "data": {"message": polite, "category": category, "is_financial": False, "ts": ts_final}}
                                    yield {"event": "workflow_complete", "event_type": "thinking", "data": {"message": "Workflow completed with early exit (classifier)", "early_exit": True, "ts": ts_final, "total_elapsed_ms": int((time.time() - loop_start) * 1000)}}
                                    early_exit_triggered = True
                                except Exception as ee:
                                    logger.error(f"[TOOL_EXECUTION] Error during early-exit handling: {ee}")

                            result = classification_result

                        elif tool_name == "detect_intent":
                            # Detect intent and emit clarification requests as needed (blocking loop)
                            intent = await asyncio.to_thread(
                                detect_intent_with_clarifications,
                                tool_args.get("query") or query,
                                self.tools.configs,
                                session_id=session_id
                            )

                            # Process clarifications sequentially
                            if intent.clarifications_suggested:
                                for clarification in intent.clarifications_suggested:
                                    from analytics_memory.types import ClarifyRequestModel
                                    clarify_request = ClarifyRequestModel(
                                        slot=clarification.get('slot', 'unknown'),
                                        question=clarification.get('reason', 'Please provide clarification'),
                                        type='single',
                                        options=self._get_options_for_slot(clarification.get('slot')),
                                        request_id=str(uuid.uuid4()),
                                        reason=clarification.get('reason', ''),
                                        session_id=session_id
                                    )

                                    # Store pending clarification and emit request
                                    self._pending_clarifications[session_id] = clarify_request
                                    self._clarification_events[session_id] = asyncio.Event()
                                    yield {"event": "clarification_request", "data": clarify_request.dict()}

                                    # Wait for clarification answer
                                    await self._wait_for_clarification(session_id)

                                    # Apply clarification answer
                                    state = self.workflow_states.get(session_id)
                                    if state and hasattr(state, 'clarification_answer'):
                                        intent.slots_detected[clarify_request.slot] = state.clarification_answer

                                    yield {"event": "clarification_ack", "data": {"answer": getattr(self.workflow_states.get(session_id), 'clarification_answer', 'Unknown')}}

                                    # Cleanup
                                    self._pending_clarifications.pop(session_id, None)
                                    self._clarification_events.pop(session_id, None)

                            result = {"intent": intent.dict()}

                        elif tool_name == "request_clarification":
                            # Handle clarification requests
                            result = await self._execute_single_tool(tool_name, tool_args, session_id)

                            # If clarifications are needed, emit request and wait
                            if result.get("success") and result.get("clarifications_needed"):
                                clarification_data = result["clarification"]

                                # Store pending clarification
                                from analytics_memory.types import ClarifyRequestModel
                                clarify_request = ClarifyRequestModel(**clarification_data)
                                self._pending_clarifications[session_id] = clarify_request
                                self._clarification_events[session_id] = asyncio.Event()

                                # Emit clarification request event
                                yield {
                                    "event": "clarification_request",
                                    "data": clarification_data
                                }

                                # Wait for clarification answer
                                await self._wait_for_clarification(session_id)

                                # Update result to indicate clarification was handled
                                result["clarification_resolved"] = True
                        else:
                            # Execute tool normally with enhanced error handling
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
                                "ts": datetime.utcnow().isoformat()
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
