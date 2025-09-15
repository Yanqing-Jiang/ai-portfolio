from __future__ import annotations
from typing import Any, Dict, List, Optional, AsyncGenerator, Tuple

from analytics_memory.intent import (
    detect_intent_with_clarifications,
)
from analytics_memory.sql_planner import (
    plan_sql_rule_based,
    choose_template as cfg_choose_template,
)
from analytics_memory.sql_validate import validate_sql
from analytics_memory.db import execute
from analytics_memory.charting import (
    build_chart_spec,
    plan_chart_rule_based,
)
from analytics_memory.analysis import stream_insights_llm
from analytics_memory.clarify import (
    compute_required_clarifications,
    wait_for_answer_blocking,
    merge_answers,
)
from analytics_memory.types import (
    IntentModel,
    QueryPlanModel,
    ClarifyRequestModel,
    ClarifyAnswerModel,
)
from analytics_memory.config import CONFIGS

from .template_store import search_templates


class SupervisorTools:
    """Thin wrappers around existing deterministic functions + RAG accessors.

    These tools are designed to be called by a single LLM agent ("supervisor")
    to reproduce the current analytics-memory flow with a different UX and
    thought-process events.
    
    Each tool includes JSON schema definitions for OpenAI function calling.
    """

    def __init__(self, configs: Optional[Dict[str, Any]] = None):
        self.configs = configs or CONFIGS.__dict__
        
    @staticmethod
    def get_tool_schemas() -> List[Dict[str, Any]]:
        """Return all tool schemas for OpenAI function calling"""
        return [
            {
                "type": "function",
                "function": {
                    "name": "detect_intent",
                    "description": "Detect user intent and extract slots from query",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "User query to analyze"
                            }
                        },
                        "required": ["query"]
                    }
                }
            },
            {
                "type": "function", 
                "function": {
                    "name": "provisional_plan",
                    "description": "Create provisional SQL query plan from intent",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "intent": {
                                "type": "object",
                                "description": "Intent model with detected slots"
                            }
                        },
                        "required": ["intent"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "retrieve_templates_rag",
                    "description": "Search for relevant SQL templates using vector similarity",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "Query to search for templates"
                            },
                            "intent_key": {
                                "type": "string",
                                "description": "Optional intent key filter"
                            },
                            "top_k": {
                                "type": "integer",
                                "description": "Number of templates to retrieve",
                                "default": 3
                            }
                        },
                        "required": ["query"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "choose_template_from_config",
                    "description": "Choose template from configuration based on intent and plan",
                    "parameters": {
                        "type": "object", 
                        "properties": {
                            "intent": {
                                "type": "object",
                                "description": "Intent model with detected slots"
                            },
                            "plan": {
                                "type": "object", 
                                "description": "Query plan model"
                            }
                        },
                        "required": ["intent", "plan"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "validate_sql",
                    "description": "Validate SQL query for safety and correctness",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "sql": {
                                "type": "string",
                                "description": "SQL query to validate"
                            },
                            "granularity": {
                                "type": "string",
                                "enum": ["annual", "quarterly"],
                                "description": "Data granularity"
                            },
                            "max_limit": {
                                "type": "integer",
                                "description": "Maximum row limit"
                            }
                        },
                        "required": ["sql", "granularity"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "apply_execute_sql", 
                    "description": "Execute SQL query against database (requires approval)",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "sql": {
                                "type": "string",
                                "description": "Validated SQL query to execute"
                            }
                        },
                        "required": ["sql"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "plan_chart",
                    "description": "Plan chart visualization for data",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "data": {
                                "type": "array",
                                "description": "Query result data"
                            },
                            "query": {
                                "type": "string", 
                                "description": "Original user query"
                            },
                            "intent_key": {
                                "type": "string",
                                "description": "Intent key for chart customization"
                            }
                        },
                        "required": ["data", "query"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "request_clarification",
                    "description": "Request clarification from the user when information is missing or ambiguous",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "intent": {
                                "type": "object",
                                "description": "Intent model with detected slots"
                            },
                            "plan": {
                                "type": "object",
                                "description": "Query plan model"
                            },
                            "template": {
                                "type": "object",
                                "description": "Selected SQL template (optional)"
                            }
                        },
                        "required": ["intent", "plan"]
                    }
                }
            },
            {
                "type": "function", 
                "function": {
                    "name": "build_chart",
                    "description": "Build chart specification from plan and data",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "data": {
                                "type": "array",
                                "description": "Query result data"
                            },
                            "chart_plan": {
                                "type": "object",
                                "description": "Chart plan from plan_chart"
                            },
                            "comparison": {
                                "type": "string",
                                "description": "Optional comparison context"
                            },
                            "intent_key": {
                                "type": "string",
                                "description": "Intent key for chart customization"
                            }
                        },
                        "required": ["data", "chart_plan"]
                    }
                }
            }
        ]

    # -------- Intent + Planning --------
    def detect_intent(self, query: str, session_id: Optional[str] = None) -> IntentModel:
        return detect_intent_with_clarifications(query, self.configs, session_id=session_id)

    def provisional_plan(self, intent: IntentModel) -> QueryPlanModel:
        return plan_sql_rule_based(intent, self.configs)

    def compute_clarifications(
        self, intent: IntentModel, plan: QueryPlanModel, template: Optional[Dict[str, Any]]
    ) -> List[ClarifyRequestModel]:
        return compute_required_clarifications(intent, plan, template, self.configs)

    # -------- Clarifications (blocking) --------
    async def ask_single_clarification(
        self, session_id: str, request: ClarifyRequestModel
    ) -> ClarifyAnswerModel:
        """Block until a single clarification answer arrives for this session.

        The Supervisor orchestrator is responsible for emitting the corresponding
        `clarification_request` SSE event before awaiting here.
        """
        answer = await wait_for_answer_blocking(session_id, request.request_id)
        return answer

    async def merge_clarification_answers(
        self,
        intent: IntentModel,
        plan: QueryPlanModel,
        answers: List[ClarifyAnswerModel],
    ) -> Tuple[IntentModel, QueryPlanModel, List[str]]:
        return await merge_answers(intent, plan, answers, self.configs)

    # -------- RAG Templates --------
    async def retrieve_templates_rag(
        self, query: str, intent_key: Optional[str] = None, top_k: int = 3
    ) -> List[Dict[str, Any]]:
        """Search Supabase pgvector store for relevant SQL templates.

        Returns a list of {id, name, intent_key, description, sql_template, distance}.
        If vector search isn't available (no DB/API key), returns empty list.
        """
        try:
            return await search_templates(query, intent_key=intent_key, top_k=top_k)
        except Exception:
            # Fail silent - supervisor can fallback to config templates
            return []

    def choose_template_from_config(self, intent: IntentModel, plan: QueryPlanModel) -> Optional[Dict[str, Any]]:
        return cfg_choose_template(intent, plan, self.configs)

    # -------- SQL --------
    def validate_sql(self, sql: str, granularity: str, max_limit: Optional[int] = None):
        max_limit = max_limit or self.configs.get('database', {}).get('query_defaults', {}).get('max_limit', 10000)
        return validate_sql(sql, allowed_tables=["comp_financials"], max_limit=max_limit, granularity=granularity)

    async def execute_sql(self, sql: str):
        return await execute(sql)

    async def apply_execute_sql(self, sql: str) -> Dict[str, Any]:
        """Apply tool: Execute SQL query (requires approval)
        
        Enforces Claude Code-style safety checks:
        - Pre-execution validation
        - Allowed tables only
        - LIMIT clause required
        - SELECT-only operations
        - Bounded result size
        
        Returns data with bounded size plus summary metadata for agent reasoning.
        """
        try:
            # Safety check 1: Pre-validate SQL before execution
            validation_result = self.validate_sql(sql, "annual")  # Default granularity for validation
            ok, issues = validation_result if isinstance(validation_result, tuple) else (validation_result.get("ok", False), validation_result.get("issues", []))
            
            if not ok:
                return {
                    "success": False,
                    "error": f"SQL validation failed: {'; '.join(issues)}",
                    "summary": {"error": f"Pre-execution validation failed: {'; '.join(issues)}"}
                }
            
            # Safety check 2: Ensure SQL is SELECT only (done in validator but double-check)
            sql_upper = sql.upper().strip()
            if not sql_upper.startswith('SELECT'):
                return {
                    "success": False,
                    "error": "Only SELECT queries are allowed",
                    "summary": {"error": "Non-SELECT query blocked for safety"}
                }
            
            # Safety check 3: Ensure LIMIT clause exists
            if 'LIMIT' not in sql_upper:
                return {
                    "success": False,
                    "error": "LIMIT clause required for all queries",
                    "summary": {"error": "Missing LIMIT clause - required for safety"}
                }
            
            # Execute with additional safety measures
            data = await execute(sql)
            
            # Safety check 4: Bound data size for token efficiency and memory safety
            max_rows = 50
            bounded_data = data[:max_rows] if data else []
            
            # Safety check 5: Log execution for audit
            import logging
            logger = logging.getLogger(__name__)
            logger.info(f"SQL executed via supervisor: {sql[:100]}... returned {len(data) if data else 0} rows")
            
            summary = {
                "total_rows": len(data) if data else 0,
                "returned_rows": len(bounded_data),
                "columns": list(bounded_data[0].keys()) if bounded_data else [],
                "data_sample": bounded_data[:3],  # Show first 3 rows
                "truncated": len(data) > max_rows if data else False,
                "sql_validated": True,
                "safety_checks_passed": True
            }
            
            return {
                "success": True,
                "data": bounded_data,
                "summary": summary
            }
            
        except Exception as e:
            # Log errors for debugging
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"SQL execution failed: {str(e)}")
            
            return {
                "success": False,
                "error": str(e),
                "summary": {"error": f"SQL execution failed: {str(e)}", "safety_checks_passed": False}
            }

    # -------- Charting --------
    def plan_chart(self, data, query: str, intent_key: Optional[str]):
        return plan_chart_rule_based(data, query, intent_key)

    def build_chart(self, data, chart_plan, comparison: Optional[str], intent_key: Optional[str]):
        return build_chart_spec(
            data,
            chart_plan.dict() if hasattr(chart_plan, 'dict') else chart_plan,
            CONFIGS.charts,
            intent_key=intent_key,
            comparison=comparison,
        )

    # -------- Analysis --------
    async def stream_analysis(self, data, sql: str, query: str, session_id: Optional[str] = None) -> AsyncGenerator[str, None]:
        async for chunk in stream_insights_llm(data, sql, query, session_id=session_id):
            yield chunk

    # -------- Clarifications --------
    async def request_clarification(
        self, 
        intent: IntentModel, 
        plan: QueryPlanModel, 
        template: Optional[Dict[str, Any]] = None,
        session_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Request clarification from user for missing or ambiguous information.
        
        This is a Claude Code-style tool that:
        1. Detects what needs clarification
        2. Emits clarification_request events
        3. Waits for user responses
        4. Returns updated intent/plan
        """
        try:
            # Step 1: Detect what needs clarification
            clarifications_needed = self.compute_clarifications(intent, plan, template)
            
            if not clarifications_needed:
                return {
                    "success": True,
                    "clarifications_needed": False,
                    "message": "No clarifications needed"
                }
            
            # Step 2: Request clarifications from user (only first one for now)
            clarification = clarifications_needed[0]
            clarification.session_id = session_id or "default"
            
            # This will be handled by the supervisor workflow to emit the SSE event
            return {
                "success": True, 
                "clarifications_needed": True,
                "clarification": clarification.dict(),
                "total_clarifications": len(clarifications_needed),
                "message": f"Clarification needed: {clarification.question}"
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "clarifications_needed": False
            }

