from __future__ import annotations
from typing import Any, Dict, AsyncGenerator, Optional, List
import time
import json
import uuid
import logging
from datetime import datetime
import asyncio

logger = logging.getLogger(__name__)

from analytics_memory.sql_planner import compile_sql_from_plan
from analytics_memory.types import ValidationError
from analytics_memory.config import CONFIGS
from analytics_memory.intent import detect_intent_with_clarifications
from analytics_memory.types import ClarifyRequestModel

from .tools import SupervisorTools
from .responses_client import get_supervisor_client
from .schemas import PlanSchema, FinalSummarySchema, WorkflowState, ToolExecution

# Registry of active supervisor workflows keyed by session_id
ACTIVE_WORKFLOWS: Dict[str, "SupervisorWorkflow"] = {}


class SupervisorWorkflow:
    """
    Claude Code-style single-agent orchestrator with planning, approval, and tool execution.
    
    Implements the propose → approve → apply pattern with explicit side-effect gating.
    """

    def __init__(self):
        self.tools = SupervisorTools(CONFIGS.__dict__)
        try:
            self.client = get_supervisor_client()
        except ValueError:
            # For development/testing without OpenAI API key
            self.client = None
        self.workflow_states: Dict[str, WorkflowState] = {}  # Session-based state tracking
        self._approval_events: Dict[str, asyncio.Event] = {}  # Session-based approval events
        self._clarification_events: Dict[str, asyncio.Event] = {}  # Session-based clarification events
        self._pending_clarifications: Dict[str, ClarifyRequestModel] = {}  # Session-based clarification requests

    async def events(self, query: str, session_id: Optional[str] = None) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Claude Code-style orchestration with planning → approval → execution phases.
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
        # Register approval event and active workflow for this session
        self._approval_events[session_id] = asyncio.Event()
        ACTIVE_WORKFLOWS[session_id] = self

        yield {"event": "session_started", "data": {"session_id": session_id, "ts": now}}

        try:
            # ====== PHASE 1: PLANNING ======
            yield {"event": "status", "data": {"step": "planning", "message": "Agent planning approach...", "ts": now}}
            
            plan = await self._planning_turn(query, session_id)
            state.plan = plan
            state.current_phase = "approval_pending" if plan.requires_approval else "executing"
            
            yield {
                "event": "planning_proposed",
                "data": {
                    "plan": plan.plan,
                    "steps": [step.dict() for step in plan.steps],
                    "requires_approval": plan.requires_approval,
                    "apply_targets": plan.apply_targets,
                    "risks": plan.risks,
                    "reasoning": plan.reasoning,
                    "ts": now
                }
            }

            # ====== PHASE 2: APPROVAL (always required for SQL execution) ======
            if plan.requires_approval:
                yield {
                    "event": "approval_required",
                    "data": {
                        "session_id": session_id,
                        "apply_targets": plan.apply_targets,
                        "preview_sql": self._get_preview_sql_if_available(plan),
                        "ts": datetime.utcnow().isoformat()
                    }
                }
                
                # Wait for approval (handled by separate endpoint)
                await self._wait_for_approval(session_id)
                state.approval_granted = True
                state.current_phase = "executing"
                
                yield {"event": "approval_granted", "data": {"session_id": session_id, "ts": datetime.utcnow().isoformat()}}

            # ====== PHASE 3: TOOL EXECUTION ======
            state.current_phase = "executing"
            yield {"event": "status", "data": {"step": "execution", "message": "Executing planned tools...", "ts": datetime.utcnow().isoformat()}}
            
            # Execute tools and forward their events
            data = None
            chart_spec = None
            sql_executed = None
            
            async for tool_event in self._execute_tools(plan, query, session_id):
                if tool_event.get("event") == "data_retrieved":
                    data = tool_event["data"].get("sample_data", [])
                    sql_executed = tool_event["data"].get("sql_executed")
                elif tool_event.get("event") == "chart_generated":
                    chart_spec = tool_event["data"].get("chart_spec")
                yield tool_event
            
            state.data_retrieved = data
            state.chart_spec = chart_spec
            state.sql_executed = sql_executed

            # ====== PHASE 4: ANALYSIS STREAMING ======
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

            # ====== PHASE 5: FINALIZATION ======
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
            # Cleanup active workflow, approval event, and clarification events for this session
            ACTIVE_WORKFLOWS.pop(session_id, None)
            self._approval_events.pop(session_id, None)
            self._clarification_events.pop(session_id, None)
            self._pending_clarifications.pop(session_id, None)


    async def _planning_turn(self, query: str, session_id: str) -> PlanSchema:
        """Phase 1: Agent plans the approach using GPT-5 with high reasoning effort"""
        
        if not self.client:
            # Fallback to deterministic plan if no OpenAI client available
            return await self._fallback_planning_turn(query, session_id)
        
        # Use GPT-5 with high reasoning effort for planning
        system_message = """You are a Claude Code-style supervisor agent planning financial analytics workflows.

Your task is to create a detailed execution plan for financial data analysis queries. You have access to these tools:
- detect_intent: Analyze user query to extract intent and slots  
- provisional_plan: Create SQL query plan from detected intent
- retrieve_templates_rag: Search for relevant SQL templates
- validate_sql: Validate compiled SQL for safety
- apply_execute_sql: Execute validated SQL query (REQUIRES APPROVAL)
- plan_chart: Plan visualization for the data
- build_chart: Generate chart specification

Always include these steps in order:
1. Intent detection and clarifications
2. Query planning 
3. Template retrieval
4. SQL validation
5. SQL execution (needs approval due to side effects)
6. Chart planning and generation

Identify if the workflow requires approval (always true for SQL execution).
List specific risks like "SQL execution on financial database" and "Potential large result sets".
Provide clear reasoning for your approach."""

        user_message = f"""Plan a financial analytics workflow for this user query: "{query}"

Create a detailed plan that:
1. Detects the user's intent and handles any missing information via clarifications
2. Plans the appropriate SQL query for financial data analysis
3. Validates the SQL for safety before execution
4. Requires approval for SQL execution due to database side effects
5. Generates appropriate visualizations for the results

Focus on safety, validation, and user approval for database operations."""

        messages = [
            {"role": "system", "content": system_message},
            {"role": "user", "content": user_message}
        ]

        try:
            plan = await self.client.planning_turn(
                messages=messages,
                response_format=PlanSchema,
                session_id=session_id,
                reasoning_effort="high"
            )
            
            # Ensure apply_execute_sql is marked as requiring approval
            if not plan.requires_approval:
                plan.requires_approval = True
            if "apply_execute_sql" not in plan.apply_targets:
                plan.apply_targets.append("apply_execute_sql")
                
            return plan
            
        except Exception as e:
            logger.error(f"GPT-5 planning failed: {str(e)}, falling back to deterministic plan")
            return await self._fallback_planning_turn(query, session_id)

    async def _fallback_planning_turn(self, query: str, session_id: str) -> PlanSchema:
        """Fallback deterministic planning when GPT-5 is unavailable"""
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
        
        return PlanSchema(
            plan="Execute financial analytics workflow: detect intent → plan query → find templates → validate SQL → execute → visualize",
            steps=plan_steps,
            requires_approval=True,  # SQL execution requires approval
            apply_targets=["apply_execute_sql"],
            risks=["SQL execution on financial database", "Potential large result sets"],
            reasoning="Standard analytics workflow with safety validation and approval for SQL execution"
        )

    async def _execute_tools(self, plan: PlanSchema, query: str, session_id: str):
        """Phase 3: Execute tools using proper Responses API tool calling"""
        
        if not self.client:
            # Fallback to direct execution if no OpenAI client
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
- apply_execute_sql: Execute validated SQL query (REQUIRES APPROVAL - only call if approval granted)
- plan_chart: Plan visualization for the data
- build_chart: Generate chart specification

Important rules:
1. Call tools in the planned sequence
2. If information is missing (e.g., company name), call request_clarification before proceeding
3. Only call apply_execute_sql if approval has been granted for this session
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
        
        # Execute tool calling loop
        async for event in self._tool_calling_loop(messages, tool_schemas, session_id, query):
            yield event

    async def _fallback_execute_tools(self, plan: PlanSchema, query: str, session_id: str):
        """Fallback direct tool execution when OpenAI is unavailable"""
        
        data = None
        chart_spec = None 
        sql_executed = None
        
        try:
            # Step 1: Detect intent with clarifications
            yield {"event": "tool_start", "data": {"tool": "detect_intent", "args_summary": f"query: {query}", "ts": datetime.utcnow().isoformat()}}
            intent = detect_intent_with_clarifications(query, self.tools.configs, session_id)
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
            
            # Step 6: Execute SQL (requires approval)
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
            # Additional safety check: ensure this tool is only called after validation
            sql = tool_args["sql"]
            
            # Safety gate: ensure the workflow state indicates approval was granted
            state = self.workflow_states.get(session_id)
            if state and not state.approval_granted:
                return {
                    "success": False,
                    "error": "SQL execution requires approval - call approve endpoint",
                    "summary": {"error": "Approval required for SQL execution"}
                }
            
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
            raise ValueError(f"Unknown tool: {tool_name}")

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

    def _get_preview_sql_if_available(self, plan: PlanSchema) -> Optional[str]:
        """Extract SQL preview if available from plan steps"""
        for step in plan.steps:
            if step.tool == "apply_execute_sql" and "sql" in step.inputs:
                return step.inputs["sql"]
        return None

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
        
        max_iterations = 10  # Prevent infinite loops
        data = None
        chart_spec = None
        sql_executed = None
        
        for iteration in range(max_iterations):
            try:
                # Call the model with tools
                response = await self.client.tool_calling_turn(
                    messages=messages,
                    tools=tool_schemas,
                    tool_choice="auto",
                    session_id=session_id,
                    reasoning_effort="medium"
                )
                
                # Check if model wants to call tools
                if hasattr(response, 'tool_calls') and response.tool_calls:
                    # Execute each tool call
                    tool_results = []
                    
                    for tool_call in response.tool_calls:
                        tool_name = tool_call.function.name
                        tool_args = json.loads(tool_call.function.arguments)
                        
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
                            # Execute tool normally
                            result = await self._execute_single_tool(tool_name, tool_args, session_id)
                        
                        # Track important results
                        if tool_name == "apply_execute_sql" and result.get("success"):
                            data = result.get("data", [])
                            sql_executed = tool_args.get("sql")
                            yield {
                                "event": "data_retrieved", 
                                "data": {
                                    "row_count": len(data),
                                    "sample_data": data[:3],
                                    "sql_executed": sql_executed
                                }
                            }
                        elif tool_name == "build_chart":
                            chart_spec = result
                            yield {"event": "chart_generated", "data": {"chart_spec": chart_spec}}
                        
                        yield {
                            "event": "tool_end",
                            "data": {
                                "tool": tool_name,
                                "output_summary": str(result)[:100] if result else "completed",
                                "ts": datetime.utcnow().isoformat()
                            }
                        }
                        
                        # Add tool result to conversation
                        tool_results.append({
                            "tool_call_id": tool_call.id,
                            "role": "tool",
                            "name": tool_name,
                            "content": json.dumps(result)
                        })
                    
                    # Add assistant message and tool results to conversation
                    messages.append({
                        "role": "assistant",
                        "content": response.content,
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
                    break
                    
            except Exception as e:
                yield {"event": "tool_error", "data": {"tool": "workflow", "error": str(e)}}
                break

    async def _handle_detect_intent_with_clarifications(self, tool_args: Dict, session_id: str, query: str):
        """Handle intent detection with clarification support"""
        
        # Use the enhanced intent detection 
        intent = detect_intent_with_clarifications(query, self.tools.configs, session_id)
        
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

    async def _wait_for_approval(self, session_id: str):
        """Block until an approval signal is received for the session."""
        evt = self._approval_events.get(session_id)
        if not evt:
            evt = asyncio.Event()
            self._approval_events[session_id] = evt
        await evt.wait()

    def approve_plan(self, session_id: str) -> bool:
        """Approve a pending plan and signal any waiters for the session."""
        state = self.workflow_states.get(session_id)
        evt = self._approval_events.get(session_id)
        if state and state.current_phase == "approval_pending":
            state.approval_granted = True
            state.current_phase = "executing"
            if evt and not evt.is_set():
                evt.set()
            return True
        # If already executing but event not set, set it to unblock
        if state and state.current_phase == "executing":
            if evt and not evt.is_set():
                evt.set()
            return True
        return False


def get_active_workflow(session_id: str) -> Optional[SupervisorWorkflow]:
    """Lookup the active SupervisorWorkflow instance for a session, if any."""
    return ACTIVE_WORKFLOWS.get(session_id)


async def supervisor_workflow(query: str, session_id: Optional[str] = None):
    """Entry point for supervisor workflow"""
    wf = SupervisorWorkflow()
    async for ev in wf.events(query, session_id):
        yield ev
