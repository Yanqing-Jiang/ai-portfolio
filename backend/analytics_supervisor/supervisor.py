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

from analytics_memory.sql_planner import compile_sql_from_plan
from analytics_memory.types import ValidationError
from analytics_memory.config import CONFIGS
from analytics_memory.intent import detect_intent_with_clarifications
from analytics_memory.types import ClarifyRequestModel

from .tools import SupervisorTools
from .responses_client import get_supervisor_client, SUPERVISOR_REASONING_EFFORT
from .schemas import PlanSchema, FinalSummarySchema, WorkflowState, ToolExecution

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
            self.client = get_supervisor_client()
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
        if not session_id:
            session_id = str(uuid.uuid4())

        # Initialize workflow state
        state = WorkflowState(
            session_id=session_id,
            current_phase="planning",
            started_at=now
        )
        self.workflow_states[session_id] = state
        # Register active workflow for this session
        ACTIVE_WORKFLOWS[session_id] = self

        yield {"event": "session_started", "data": {"session_id": session_id, "ts": now}}

        try:
            # ====== PHASE 1: PLANNING ======
            planning_start = time.time()
            logger.info(f"[SUPERVISOR] Planning phase started for session {session_id}, query: {query[:50]}...")
            yield {"event": "status", "data": {"step": "planning", "message": "Agent planning approach...", "ts": now}}

            # Add streaming status during planning
            yield {"event": "status", "data": {"step": "planning", "message": "Connecting to planning service...", "ts": datetime.utcnow().isoformat()}}

            # Intermediate status updates during planning
            def status_callback(message: str):
                return {"event": "status", "data": {"step": "planning", "message": message, "ts": datetime.utcnow().isoformat()}}

            yield status_callback("Analyzing query and building context...")
            plan = await self._planning_turn(query, session_id)

            planning_duration = time.time() - planning_start
            logger.info(f"[SUPERVISOR] Planning completed in {planning_duration:.2f}s for session {session_id}")
            yield {"event": "status", "data": {"step": "planning", "message": f"Planning completed ({planning_duration:.1f}s)", "ts": datetime.utcnow().isoformat()}}
            state.plan = plan
            state.current_phase = "executing"

            yield {
                "event": "planning_proposed",
                "data": {
                    "plan": plan.plan,
                    "steps": [step.dict() for step in plan.steps],
                    "reasoning": plan.reasoning,
                    "ts": now
                }
            }

            # ====== PHASE 2: TOOL EXECUTION ======
            execution_start = time.time()
            state.current_phase = "executing"
            logger.info(f"[SUPERVISOR] Tool execution phase started for session {session_id}")
            yield {"event": "status", "data": {"step": "execution", "message": "Executing planned tools...", "ts": datetime.utcnow().isoformat()}}
            
            # Execute tools and forward their events
            data = None
            chart_spec = None
            sql_executed = None
            tool_count = 0

            async for tool_event in self._execute_tools(plan, query, session_id):
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
                yield tool_event
            
            execution_duration = time.time() - execution_start
            logger.info(f"[SUPERVISOR] Tool execution completed in {execution_duration:.2f}s, processed {tool_count} events for session {session_id}")

            state.data_retrieved = data
            state.chart_spec = chart_spec
            state.sql_executed = sql_executed

            # ====== PHASE 3: ANALYSIS STREAMING ======
            state.current_phase = "analysis"
            yield {"event": "status", "data": {"step": "analysis_generation", "message": "Generating insights...", "ts": datetime.utcnow().isoformat()}}
            
            full_analysis = ""
            if self.client and data:
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
                    full_analysis = f"Analysis generation failed: {str(e)}"
                    yield {"event": "analysis_streaming", "data": {"partial_analysis": full_analysis}}
            else:
                # Fallback analysis without OpenAI
                full_analysis = f"Analysis completed for query: {query}. Retrieved {len(data) if data else 0} rows of data."
                yield {"event": "analysis_streaming", "data": {"partial_analysis": full_analysis}}

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


    async def _planning_turn(self, query: str, session_id: str) -> PlanSchema:
        """Phase 1: Agent plans the approach using GPT-5 with configurable reasoning effort"""

        planning_start = time.time()
        logger.info(f"[PLANNING] Starting planning turn for session {session_id}")

        if not self.client:
            logger.warning(f"[PLANNING] No OpenAI client available for session {session_id}, using fallback")
            return await self._fallback_planning_turn(query, session_id)
        
        # Use GPT-5 with configurable reasoning effort for planning
        system_message = """You are a Claude Code-style supervisor agent planning financial analytics workflows.

Your task is to create a detailed execution plan for financial data analysis queries. You have access to these tools:
- detect_intent: Analyze user query to extract intent and slots - ALWAYS use this first to identify missing information
- provisional_plan: Create SQL query plan from detected intent
- retrieve_templates_rag: Search for relevant SQL templates
- request_clarification: Request clarification from user when information is missing or ambiguous
- validate_sql: Validate compiled SQL for safety
- apply_execute_sql: Execute validated SQL query directly after validation
- plan_chart: Plan visualization for the data
- build_chart: Generate chart specification

CRITICAL: If the user query is ambiguous or missing key information, you MUST include clarification steps. For example:
- Market share queries: Ask if they want single company analysis or all companies comparison
- Missing company names: Ask which company to analyze
- Missing time periods: Ask for specific timeframe

Always include these steps in order:
1. Intent detection (detect_intent)
2. Clarifications (request_clarification) - IF needed based on intent detection
3. Query planning (provisional_plan)
4. Template retrieval (retrieve_templates_rag)
5. SQL validation (validate_sql)
6. SQL execution (apply_execute_sql)
7. Chart planning and generation (plan_chart, build_chart)

Provide clear reasoning for your approach and why clarifications are needed."""

        user_message = f"""Plan a financial analytics workflow for this user query: "{query}"

Create a detailed plan that:
1. Detects the user's intent and identifies any missing or ambiguous information
2. Requests clarifications from the user if the query is incomplete or ambiguous
3. Plans the appropriate SQL query for financial data analysis
4. Validates the SQL for safety before execution
5. Executes the SQL directly after validation
6. Generates appropriate visualizations for the results

IMPORTANT: For ambiguous queries like "market share" without specifying single vs all companies, you MUST include clarification steps.

Focus on thorough intent detection and clarification gathering upfront."""

        messages = [
            {"role": "system", "content": system_message},
            {"role": "user", "content": user_message}
        ]

        try:
            api_start = time.time()
            logger.info(f"[PLANNING] Calling OpenAI API with reasoning effort= {SUPERVISOR_REASONING_EFFORT} for session {session_id}")
            if SUPERVISOR_DEBUG:
                logger.info(f"[PLANNING] Message count: {len(messages)}, total chars: {sum(len(str(m)) for m in messages)}")

            if SUPERVISOR_DEBUG:
                logger.debug(f"[PLANNING] Full request - Model: gpt-5-mini-2025-08-07, Reasoning: {SUPERVISOR_REASONING_EFFORT}")
                logger.debug(f"[PLANNING] Query: {query}")

            plan = await self.client.planning_turn(
                messages=messages,
                response_format=PlanSchema,
                session_id=session_id,
                reasoning_effort=SUPERVISOR_REASONING_EFFORT
            )

            api_duration = time.time() - api_start
            logger.info(f"[PLANNING] OpenAI API call completed in {api_duration:.2f}s for session {session_id}")
            logger.info(f"[PLANNING] Plan generated with {len(plan.steps)} steps")

            return plan
            
        except Exception as e:
            planning_duration = time.time() - planning_start
            logger.error(f"[PLANNING] GPT-5 planning failed after {planning_duration:.2f}s for session {session_id}: {str(e)}")
            logger.error(f"[PLANNING] Error type: {type(e).__name__}, falling back to deterministic plan")

            if SUPERVISOR_DEBUG:
                logger.debug(f"[PLANNING] Full error details: {repr(e)}")

            return await self._fallback_planning_turn(query, session_id)

    async def _fallback_planning_turn(self, query: str, session_id: str) -> PlanSchema:
        """Fallback deterministic planning when GPT-5 is unavailable"""

        fallback_start = time.time()
        logger.info(f"[PLANNING] Using fallback deterministic planning for session {session_id}")
        from .schemas import ToolStep
        
        plan_steps = [
            ToolStep(
                tool="detect_intent",
                description="Analyze user query to extract intent and slots",
                inputs={"query": query},
                expected_output="Intent object with key, confidence, and slots"
            ),
            ToolStep(
                tool="provisional_plan", 
                description="Create SQL query plan from detected intent",
                inputs={"intent": "intent_object"},
                expected_output="Query plan with metrics and timeframe"
            ),
            ToolStep(
                tool="retrieve_templates_rag",
                description="Search for relevant SQL templates",
                inputs={"query": query, "intent_key": "detected_intent", "top_k": 3},
                expected_output="List of matching SQL templates"
            ),
            ToolStep(
                tool="validate_sql",
                description="Validate compiled SQL for safety",
                inputs={"sql": "compiled_sql", "granularity": "annual"},
                expected_output="Validation result with ok/issues"
            ),
            ToolStep(
                tool="apply_execute_sql",
                description="Execute validated SQL query",
                inputs={"sql": "validated_sql"},
                expected_output="Query results data"
            ),
            ToolStep(
                tool="plan_chart",
                description="Plan visualization for the data",
                inputs={"data": "query_results", "query": query},
                expected_output="Chart plan specification"
            ),
            ToolStep(
                tool="build_chart",
                description="Generate chart specification",
                inputs={"data": "query_results", "chart_plan": "chart_plan"},
                expected_output="Complete chart specification"
            )
        ]
        
        fallback_duration = time.time() - fallback_start
        logger.info(f"[PLANNING] Fallback plan generated in {fallback_duration:.3f}s for session {session_id}")

        return PlanSchema(
            plan="Execute financial analytics workflow: detect intent → plan query → find templates → validate SQL → execute → visualize",
            steps=plan_steps,
            reasoning="Standard analytics workflow with safety validation"
        )

    async def _execute_tools(self, plan: PlanSchema, query: str, session_id: str):
        """Phase 3: Execute tools using proper Responses API tool calling"""

        execute_start = time.time()
        logger.info(f"[TOOLS] Starting tool execution for session {session_id} with {len(plan.steps)} planned steps")

        if not self.client:
            logger.warning(f"[TOOLS] No OpenAI client available for session {session_id}, using fallback execution")
            async for event in self._fallback_execute_tools(plan, query, session_id):
                yield event
            return
        
        # Use tool-calling turn with the model to decide which tools to call
        messages = [
            {
                "role": "system",
                "content": f"""You are a Claude Code-style supervisor executing a financial analytics plan.

Plan: {plan.plan}
User Query: {query}

Execute the tools step by step according to the plan. You have access to these tools:
- detect_intent: Analyze user query to extract intent and slots
- provisional_plan: Create SQL query plan from detected intent
- retrieve_templates_rag: Search for relevant SQL templates
- request_clarification: Request clarification from user when information is missing or ambiguous
- validate_sql: Validate compiled SQL for safety
- apply_execute_sql: Execute validated SQL query directly after validation
- plan_chart: Plan visualization for the data
- build_chart: Generate chart specification

Important rules:
1. Call tools in the planned sequence
2. ALWAYS call detect_intent first to identify missing information
3. If information is missing or ambiguous (e.g., market share without specifying single vs all companies), call request_clarification before proceeding
4. Pass results from one tool to the next as needed
5. Stop if any tool returns an error or clarification is needed

Start by calling detect_intent with the user query."""
            },
            {
                "role": "user",
                "content": f"Execute the analytics plan for query: '{query}'"
            }
        ]
        
        # Get tool schemas for function calling
        tool_schemas = self.tools.get_tool_schemas()

        if SUPERVISOR_DEBUG:
            logger.debug(f"[TOOLS] Tool schemas count: {len(tool_schemas)}")
            if tool_schemas:
                logger.debug(f"[TOOLS] First tool schema: {tool_schemas[0]}")
                logger.debug(f"[TOOLS] First tool has 'name' field: {'name' in tool_schemas[0]}")
                if 'function' in tool_schemas[0]:
                    logger.debug(f"[TOOLS] First tool function has 'name': {'name' in tool_schemas[0]['function']}")

        # Execute tool calling loop
        logger.info(f"[TOOLS] Starting OpenAI tool calling loop for session {session_id}")
        loop_start = time.time()

        async for event in self._tool_calling_loop(messages, tool_schemas, session_id, query):
            yield event

        loop_duration = time.time() - loop_start
        execute_duration = time.time() - execute_start
        logger.info(f"[TOOLS] Tool calling loop completed in {loop_duration:.2f}s, total execution: {execute_duration:.2f}s for session {session_id}")

    async def _fallback_execute_tools(self, plan: PlanSchema, query: str, session_id: str):
        """Fallback direct tool execution when OpenAI is unavailable"""

        fallback_start = time.time()
        logger.info(f"[TOOLS] Starting fallback tool execution for session {session_id}")

        data = None
        chart_spec = None
        sql_executed = None
        
        try:
            # Step 1: Detect intent with clarifications
            yield {"event": "tool_start", "data": {"tool": "detect_intent", "args_summary": f"query: {query}", "ts": datetime.utcnow().isoformat()}}
            intent = await asyncio.to_thread(detect_intent_with_clarifications, query, self.tools.configs, session_id=session_id)
            yield {"event": "intent_decided", "data": intent.dict(), "ts": datetime.utcnow().isoformat()}
            yield {"event": "tool_end", "data": {"tool": "detect_intent", "output_summary": f"intent_key: {intent.intent_key}", "ts": datetime.utcnow().isoformat()}}
            
            # Check if clarifications are needed
            if intent.clarifications_suggested:
                # Handle clarifications - emit clarification request and wait for answer
                for clarification in intent.clarifications_suggested:
                    clarify_request = ClarifyRequestModel(
                        slot=clarification.get('slot', 'unknown'),
                        question=clarification.get('reason', 'Please provide clarification'),
                        type='single',  # Default to single choice for supervisor mode
                        options=self._get_options_for_slot(clarification.get('slot')),
                        request_id=str(uuid.uuid4()),
                        reason=clarification.get('reason', ''),
                        session_id=session_id
                    )
                    
                    # Store pending clarification
                    self._pending_clarifications[session_id] = clarify_request
                    self._clarification_events[session_id] = asyncio.Event()
                    
                    # Emit clarification request
                    yield {
                        "event": "clarification_request",
                        "data": clarify_request.dict()
                    }
                    
                    # Wait for clarification answer
                    await self._wait_for_clarification(session_id)
                    
                    # Update intent with clarification answer
                    if session_id in self.workflow_states:
                        state = self.workflow_states[session_id]
                        if hasattr(state, 'clarification_answer'):
                            # Apply the clarification to intent slots
                            intent.slots_detected[clarify_request.slot] = state.clarification_answer
                    
                    # Clean up clarification state
                    self._pending_clarifications.pop(session_id, None)
                    self._clarification_events.pop(session_id, None)
                    
                    yield {
                        "event": "clarification_ack",
                        "data": {"answer": getattr(self.workflow_states.get(session_id), 'clarification_answer', 'Unknown')}
                    }
            
            # Step 2: Create provisional plan
            yield {"event": "tool_start", "data": {"tool": "provisional_plan", "args_summary": f"intent: {intent.intent_key}", "ts": datetime.utcnow().isoformat()}}
            plan_obj = self.tools.provisional_plan(intent)
            yield {"event": "tool_end", "data": {"tool": "provisional_plan", "output_summary": f"metrics: {plan_obj.metrics}", "ts": datetime.utcnow().isoformat()}}
            
            # Step 3: Get template (try RAG first)
            yield {"event": "tool_start", "data": {"tool": "retrieve_templates_rag", "args_summary": f"query: {query}", "ts": datetime.utcnow().isoformat()}}
            templates = await self.tools.retrieve_templates_rag(query, intent.intent_key, 3)
            template = templates[0] if templates else self.tools.choose_template_from_config(intent, plan_obj)
            yield {"event": "tool_end", "data": {"tool": "retrieve_templates_rag", "output_summary": f"found: {len(templates)} templates", "ts": datetime.utcnow().isoformat()}}
            
            # Step 4: Compile SQL
            from analytics_memory.sql_planner import compile_sql_from_plan
            sql = compile_sql_from_plan(plan_obj, intent, self.tools.configs, template)
            
            # Step 5: Validate SQL
            yield {"event": "tool_start", "data": {"tool": "validate_sql", "args_summary": f"sql length: {len(sql)}", "ts": datetime.utcnow().isoformat()}}
            ok, issues = self.tools.validate_sql(sql, plan_obj.granularity)
            yield {"event": "sql_validated", "data": {"validation": {"ok": ok, "issues": issues}}}
            yield {"event": "tool_end", "data": {"tool": "validate_sql", "output_summary": f"valid: {ok}", "ts": datetime.utcnow().isoformat()}}
            
            if not ok:
                yield {"event": "tool_error", "data": {"tool": "validate_sql", "error": f"Validation failed: {issues}", "ts": datetime.utcnow().isoformat()}}
                return  # Exit early if validation fails
            
            # Step 6: Execute SQL after safety validation
            yield {"event": "tool_start", "data": {"tool": "apply_execute_sql", "args_summary": f"sql: {sql[:50]}...", "ts": datetime.utcnow().isoformat()}}
            result = await self._execute_single_tool("apply_execute_sql", {"sql": sql}, session_id)
            
            if result.get("success"):
                data = result["data"]
                sql_executed = sql
                yield {"event": "data_retrieved", "data": {"row_count": len(data), "sample_data": data[:3], "sql_executed": sql}}
                yield {"event": "tool_end", "data": {"tool": "apply_execute_sql", "output_summary": f"rows: {len(data)}", "ts": datetime.utcnow().isoformat()}}
                
                # Step 7: Plan and build chart
                yield {"event": "tool_start", "data": {"tool": "plan_chart", "args_summary": f"data rows: {len(data)}", "ts": datetime.utcnow().isoformat()}}
                chart_plan = self.tools.plan_chart(data, query, intent.intent_key)
                yield {"event": "tool_end", "data": {"tool": "plan_chart", "output_summary": f"chart type: {chart_plan.chart_type if hasattr(chart_plan, 'chart_type') else 'planned'}", "ts": datetime.utcnow().isoformat()}}
                
                yield {"event": "tool_start", "data": {"tool": "build_chart", "args_summary": f"chart plan ready", "ts": datetime.utcnow().isoformat()}}
                chart_spec = self.tools.build_chart(data, chart_plan, plan_obj.comparison, intent.intent_key)
                yield {"event": "chart_generated", "data": {"chart_spec": chart_spec}}
                yield {"event": "tool_end", "data": {"tool": "build_chart", "output_summary": "chart spec generated", "ts": datetime.utcnow().isoformat()}}
            else:
                yield {"event": "tool_error", "data": {"tool": "apply_execute_sql", "error": result.get("error", "SQL execution failed"), "ts": datetime.utcnow().isoformat()}}
                
        except Exception as e:
            yield {"event": "tool_error", "data": {"tool": "workflow", "error": str(e), "ts": datetime.utcnow().isoformat()}}

    async def _execute_single_tool(self, tool_name: str, tool_args: Dict[str, Any], session_id: str):
        """Execute a single tool call"""

        tool_start = time.time()
        if SUPERVISOR_DEBUG:
            logger.info(f"[SINGLE_TOOL] Executing {tool_name} for session {session_id}")

        if SUPERVISOR_DEBUG:
            logger.debug(f"[SINGLE_TOOL] Args for {tool_name}: {tool_args}")
        
        if tool_name == "detect_intent":
            result = self.tools.detect_intent(tool_args["query"])
            return result.dict()
            
        elif tool_name == "provisional_plan":
            from analytics_memory.types import IntentModel
            intent = IntentModel(**tool_args["intent"])
            result = self.tools.provisional_plan(intent)
            return result.dict()
            
        elif tool_name == "retrieve_templates_rag":
            result = await self.tools.retrieve_templates_rag(
                tool_args["query"],
                tool_args.get("intent_key"),
                tool_args.get("top_k", 3)
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
            if state:
                state.executed_tools.append("apply_execute_sql")
                if result.get("success"):
                    state.sql_executed = sql
                    state.data_retrieved = result.get("data", [])
            
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
        
        if self.client:
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
                # Fallback to manual summary
                pass
        
        # Fallback summary without OpenAI
        return FinalSummarySchema(
            sql_summary=f"Executed SQL query: {sql[:100]}..." if sql else "No SQL executed",
            chart_summary=f"Generated chart specification" if chart_spec else "No chart generated",
            key_findings=[
                f"Retrieved {len(data) if data else 0} rows of data",
                "Analytics workflow completed successfully" if data else "Workflow completed with limited data"
            ],
            data_summary=f"{len(data) if data else 0} rows retrieved from financial database",
            next_questions=[
                "Would you like to analyze a different time period?",
                "Are there other metrics you'd like to explore?"
            ],
            execution_time="< 1 minute"
        )


    def _get_options_for_slot(self, slot: str) -> List[str]:
        """Get available options for a clarification slot"""
        if slot == "company":
            return self.tools.configs.get("companies", {}).get("selection_rules", {}).get("default_companies", {}).get("tickers", ["NVDA", "AMD", "INTC", "MU", "QCOM", "AVGO", "TXN"])
        return []

    async def _wait_for_clarification(self, session_id: str):
        """Block until a clarification answer is received for the session."""
        evt = self._clarification_events.get(session_id)
        if not evt:
            evt = asyncio.Event()
            self._clarification_events[session_id] = evt
        await evt.wait()

    def submit_clarification(self, session_id: str, answer: Any) -> bool:
        """Submit clarification answer and signal any waiters for the session."""
        state = self.workflow_states.get(session_id)
        evt = self._clarification_events.get(session_id)
        
        if state and session_id in self._pending_clarifications:
            # Store the answer in the workflow state
            state.clarification_answer = answer
            
            # Signal the waiting clarification process
            if evt and not evt.is_set():
                evt.set()
            return True
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
                        if tool_name == "detect_intent":
                            result = await self._handle_detect_intent_with_clarifications(
                                tool_args, session_id, query
                            )
                            # Emit clarification events if needed
                            for clarification_event in result.get("clarification_events", []):
                                yield clarification_event
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
                        elif tool_name == "build_chart":
                            chart_spec = result
                            yield {"event": "chart_generated", "data": {"chart_spec": chart_spec}}

                        tool_duration = time.time() - tool_start
                        if SUPERVISOR_DEBUG:
                            logger.info(f"[TOOL_LOOP] Tool {tool_name} completed in {tool_duration:.2f}s for session {session_id}")

                        yield {
                            "event": "tool_end",
                            "data": {
                                "tool": tool_name,
                                "output_summary": str(result)[:100] if result else "completed",
                                "duration_ms": int(tool_duration * 1000),
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

                    # Submit tool outputs to OpenAI API (FIXED)
                    if hasattr(response, 'response_id') and response.response_id:
                        try:
                            tool_outputs = []
                            for tool_call, execution_result in zip(response.tool_calls, tool_execution_results):
                                tool_outputs.append({
                                    "tool_call_id": tool_call.id,
                                    "output": json.dumps(execution_result) if execution_result else "{}"
                                })

                            # Submit the tool outputs to continue the conversation
                            await self.client.unified_client.client.responses.submit_tool_outputs(
                                response_id=response.response_id,
                                tool_outputs=tool_outputs
                            )

                            if SUPERVISOR_DEBUG:
                                logger.info(f"[TOOL_LOOP] Submitted {len(tool_outputs)} tool outputs for session {session_id}")
                        except Exception as submit_error:
                            logger.error(f"[TOOL_LOOP] Failed to submit tool outputs for session {session_id}: {str(submit_error)}")

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

    async def _handle_detect_intent_with_clarifications(self, tool_args: Dict, session_id: str, query: str):
        """Handle intent detection with clarification support"""
        
        # Use the enhanced intent detection 
        intent = await asyncio.to_thread(detect_intent_with_clarifications, query, self.tools.configs, session_id=session_id)
        
        # Check for clarifications
        clarification_events = []
        if intent.clarifications_suggested:
            for clarification in intent.clarifications_suggested:
                clarify_request = ClarifyRequestModel(
                    slot=clarification.get('slot', 'unknown'),
                    question=clarification.get('reason', 'Please provide clarification'),
                    type='single',
                    options=self._get_options_for_slot(clarification.get('slot')),
                    request_id=str(uuid.uuid4()),
                    reason=clarification.get('reason', ''),
                    session_id=session_id
                )
                
                # Store and wait for clarification
                self._pending_clarifications[session_id] = clarify_request
                self._clarification_events[session_id] = asyncio.Event()
                
                clarification_events.append({
                    "event": "clarification_request",
                    "data": clarify_request.dict()
                })
                
                # Wait for clarification answer
                await self._wait_for_clarification(session_id)
                
                # Apply clarification answer
                if session_id in self.workflow_states:
                    state = self.workflow_states[session_id]
                    if hasattr(state, 'clarification_answer'):
                        intent.slots_detected[clarify_request.slot] = state.clarification_answer
                
                clarification_events.append({
                    "event": "clarification_ack",
                    "data": {"answer": getattr(self.workflow_states.get(session_id), 'clarification_answer', 'Unknown')}
                })
                
                # Cleanup
                self._pending_clarifications.pop(session_id, None)
                self._clarification_events.pop(session_id, None)
        
        return {
            "intent": intent.dict(),
            "clarification_events": clarification_events
        }



def get_active_workflow(session_id: str) -> Optional[SupervisorWorkflow]:
    """Lookup the active SupervisorWorkflow instance for a session, if any."""
    return ACTIVE_WORKFLOWS.get(session_id)


async def supervisor_workflow(query: str, session_id: Optional[str] = None):
    """Entry point for supervisor workflow"""
    wf = SupervisorWorkflow()
    async for ev in wf.events(query, session_id):
        yield ev





