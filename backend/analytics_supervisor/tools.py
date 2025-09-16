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
    QuestionAnalysisModel,
    ClarificationArtifactModel,
)
from .schemas import (
    OffTopicClassifierSchema,
    StructuredQueryArtifact,
    ModernClarificationRequest,
    ClarificationField,
    ClarificationOption
)
from shared_artifacts import (
    UnifiedClarificationArtifact,
    UnifiedClarificationField,
    UnifiedClarificationOption,
    UnifiedQueryArtifact,
    create_clarification_artifact,
    create_query_artifact
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
                    "name": "classify_query_relevance",
                    "description": "Classify if query is about financial analytics before processing. CALL THIS FIRST for off-topic guard.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "User query to classify for topic relevance"
                            }
                        },
                        "required": ["query"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "check_question_completeness",
                    "description": "Check if question has all required information for SQL generation. Call after topic classification.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "question": {
                                "type": "string",
                                "description": "User question to analyze for completeness"
                            }
                        },
                        "required": ["question"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "create_clarification_artifact",
                    "description": "Create modern ChatGPT-inspired clarification interface with smart suggestions, progressive disclosure, and enhanced UX. Call when question is incomplete.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "missing_slots": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "List of missing information slots"
                            },
                            "question": {
                                "type": "string",
                                "description": "Original user question"
                            }
                        },
                        "required": ["missing_slots", "question"]
                    }
                }
            },
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
                                "items": {
                                    "type": "object",
                                    "additionalProperties": False
                                },
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
                                "items": {
                                    "type": "object",
                                    "additionalProperties": False
                                },
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
            },
            {
                "type": "function",
                "function": {
                    "name": "emit_structured_query",
                    "description": "Emit structured query artifact after intent detection. Single source of truth for SQL generation.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "intent_key": {
                                "type": "string",
                                "description": "Primary intent classification"
                            },
                            "company": {
                                "type": "string",
                                "description": "Target company for analysis",
                                "default": None
                            },
                            "metrics": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Requested metrics/KPIs",
                                "default": []
                            },
                            "timeframe": {
                                "type": "string",
                                "description": "Time period for analysis",
                                "default": None
                            },
                            "comparison_type": {
                                "type": "string",
                                "description": "Single company vs all companies",
                                "default": None
                            },
                            "original_query": {
                                "type": "string",
                                "description": "Original user question"
                            },
                            "session_id": {
                                "type": "string",
                                "description": "Session identifier"
                            },
                            "confidence": {
                                "type": "number",
                                "description": "Confidence in intent classification",
                                "default": 0.8
                            },
                            "assumptions": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Assumptions made during processing",
                                "default": []
                            }
                        },
                        "required": ["intent_key", "original_query", "session_id"]
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

    # -------- Off-Topic Guard --------
    async def classify_query_relevance(self, query: str) -> OffTopicClassifierSchema:
        """Classify if query is about financial analytics. Implements off-topic guard."""
        from .responses_client import get_supervisor_client

        try:
            client = get_supervisor_client()
            if not client:
                # Fallback to heuristic classification
                return self._heuristic_topic_classification(query)

            system_prompt = """You classify user queries to determine if they are about financial analytics.

Financial analytics queries include:
- Company financial performance (revenue, profit, growth)
- Market share analysis
- Stock prices and trends
- Financial ratios and metrics
- Competitor analysis
- Industry benchmarking
- Revenue forecasting
- Cost analysis

Off-topic queries include:
- General conversation ("hello", "how are you")
- Technical support for software/hardware
- Personal questions
- Non-financial business questions
- Academic questions not related to finance
- Entertainment or lifestyle topics

Provide polite decline messages for off-topic queries and suggest how to rephrase."""

            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Classify this query: '{query}'"}
            ]

            result = await client.planning_turn(
                messages=messages,
                response_format=OffTopicClassifierSchema,
                reasoning_effort="low"  # Fast classification
            )

            return result

        except Exception as e:
            # Fallback to heuristic if LLM fails
            return self._heuristic_topic_classification(query)

    def _heuristic_topic_classification(self, query: str) -> OffTopicClassifierSchema:
        """Fallback heuristic classification when LLM is unavailable"""
        query_lower = query.lower()

        # Financial keywords
        financial_keywords = [
            'revenue', 'profit', 'market share', 'stock', 'financial', 'earnings',
            'sales', 'growth', 'performance', 'analysis', 'metrics', 'ratio',
            'company', 'business', 'industry', 'competitor', 'benchmark'
        ]

        # Off-topic keywords
        offtopic_keywords = [
            'hello', 'hi', 'how are you', 'weather', 'personal', 'help me with',
            'technical support', 'bug', 'error', 'install', 'download'
        ]

        financial_score = sum(1 for kw in financial_keywords if kw in query_lower)
        offtopic_score = sum(1 for kw in offtopic_keywords if kw in query_lower)

        if financial_score > 0:
            return OffTopicClassifierSchema(
                is_financial_query=True,
                confidence=min(0.8, 0.5 + financial_score * 0.1),
                topic_category="financial_analytics"
            )
        elif offtopic_score > 0:
            return OffTopicClassifierSchema(
                is_financial_query=False,
                confidence=min(0.9, 0.6 + offtopic_score * 0.1),
                topic_category="general_conversation",
                polite_decline_message="I'm specialized in financial analytics. For general questions, I'd recommend asking a general-purpose AI assistant.",
                suggested_rephrase="Try asking about company performance, market data, or financial metrics instead."
            )
        else:
            # Uncertain case - lean towards allowing it
            return OffTopicClassifierSchema(
                is_financial_query=True,
                confidence=0.3,
                topic_category="other"
            )

    # -------- Question Completeness Analysis --------
    async def check_question_completeness(self, question: str) -> QuestionAnalysisModel:
        """Analyze if question has all required information for SQL generation"""
        from .responses_client import get_supervisor_client

        try:
            client = get_supervisor_client()
            if not client:
                # Fallback to heuristic analysis
                return self._heuristic_question_analysis(question)

            system_prompt = """You analyze questions to determine if they have enough information for SQL query generation.

Return JSON with:
- has_company: Is a specific company mentioned? (NVDA, AMD, etc.)
- has_timeframe: Is timeframe specified? (5 years, Q1 2023, etc.)
- has_metrics: Are metrics/analysis type clear? (market share, revenue, etc.)
- has_comparison_type: Is it clear if single company or all companies analysis?
- detected_*: What values were found
- is_complete: Can we generate SQL without asking user for more info?
- missing_slots: What critical info is missing?

Examples:
"NVDA market share in 5 years" → complete (has company, timeframe, metrics)
"market share in 5 years" → incomplete (missing company)
"NVDA performance" → incomplete (missing timeframe, unclear metrics)"""

            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Analyze this question: {question}"}
            ]

            # Use structured output
            response = await client.tool_calling_turn(
                messages=messages,
                tools=[],  # No tools needed, just analysis
                tool_choice="none",
                session_id="question_analysis",
                reasoning_effort="medium"
            )

            # Parse the response into our model
            import json
            try:
                analysis_data = json.loads(response.content)
                return QuestionAnalysisModel(**analysis_data)
            except:
                # If JSON parsing fails, fall back to heuristic
                return self._heuristic_question_analysis(question)

        except Exception as e:
            print(f"Question completeness analysis failed: {e}")
            return self._heuristic_question_analysis(question)

    def _heuristic_question_analysis(self, question: str) -> QuestionAnalysisModel:
        """Fallback heuristic analysis when LLM is unavailable"""
        q = question.lower()

        # Check for company
        companies = ["nvda", "nvidia", "amd", "intel", "intc", "qualcomm", "qcom", "micron", "mu"]
        has_company = any(company in q for company in companies)
        detected_company = None
        for company in companies:
            if company in q:
                detected_company = company.upper() if len(company) <= 4 else company.title()
                break

        # Check for timeframe
        timeframe_indicators = ["year", "month", "quarter", "q1", "q2", "q3", "q4", "2020", "2021", "2022", "2023", "2024"]
        has_timeframe = any(indicator in q for indicator in timeframe_indicators)

        # Check for metrics
        metrics_indicators = ["market share", "revenue", "growth", "margin", "profit", "sales"]
        has_metrics = any(metric in q for metric in metrics_indicators)

        # Check for comparison type
        has_comparison_type = "all" in q or "compare" in q or has_company

        # Determine missing slots
        missing_slots = []
        if not has_company and "all" not in q:
            missing_slots.append("company")
        if not has_timeframe:
            missing_slots.append("timeframe")
        if not has_metrics:
            missing_slots.append("metrics")
        if not has_comparison_type:
            missing_slots.append("comparison_type")

        is_complete = len(missing_slots) == 0

        return QuestionAnalysisModel(
            has_company=has_company,
            has_timeframe=has_timeframe,
            has_metrics=has_metrics,
            has_comparison_type=has_comparison_type,
            detected_company=detected_company,
            detected_timeframe=None,  # Could add timeframe detection
            detected_metrics=None,    # Could add metrics detection
            is_complete=is_complete,
            missing_slots=missing_slots,
            confidence=0.8  # Heuristic confidence
        )

    def create_clarification_artifact(self, missing_slots: List[str], question: str, session_id: str = None) -> UnifiedClarificationArtifact:
        """Create enhanced interactive form with ChatGPT-inspired UX for user clarifications"""

        fields = []

        # Analyze question for smart suggestions
        query_lower = question.lower()

        if "company" in missing_slots:
            # Smart company suggestion based on query content
            suggested_company = None
            confidence = 0.0

            # Check for company mentions in query
            company_hints = {
                "nvidia": ("NVDA", 0.95),
                "nvda": ("NVDA", 0.9),
                "amd": ("AMD", 0.9),
                "intel": ("INTC", 0.9),
                "qualcomm": ("QCOM", 0.9),
                "micron": ("MU", 0.9),
                "broadcom": ("AVGO", 0.85),
                "texas instruments": ("TXN", 0.85)
            }

            for hint, (ticker, conf) in company_hints.items():
                if hint in query_lower:
                    suggested_company = ticker
                    confidence = conf
                    break

            # Create enhanced company field
            company_options = [
                UnifiedClarificationOption(value="NVDA", label="NVIDIA Corporation", description="GPU & AI chips leader", recommended=(suggested_company == "NVDA")),
                UnifiedClarificationOption(value="AMD", label="Advanced Micro Devices", description="CPU & GPU manufacturer", recommended=(suggested_company == "AMD")),
                UnifiedClarificationOption(value="INTC", label="Intel Corporation", description="Semiconductor giant", recommended=(suggested_company == "INTC")),
                UnifiedClarificationOption(value="QCOM", label="Qualcomm", description="Mobile chip leader", recommended=(suggested_company == "QCOM")),
                UnifiedClarificationOption(value="MU", label="Micron Technology", description="Memory specialist", recommended=(suggested_company == "MU")),
                UnifiedClarificationOption(value="AVGO", label="Broadcom", description="Semiconductor solutions", recommended=(suggested_company == "AVGO")),
                UnifiedClarificationOption(value="TXN", label="Texas Instruments", description="Analog & embedded processing", recommended=(suggested_company == "TXN"))
            ]

            fields.append(UnifiedClarificationField(
                field_id="company",
                type="select",
                label="Which company would you like to analyze?",
                description="Select the specific company for your financial analysis",
                placeholder="Choose a company...",
                required=True,
                options=company_options,
                suggested_value=suggested_company,
                confidence=confidence,
                icon="🏢",
                priority=3
            ))

        if "timeframe" in missing_slots:
            # Smart timeframe suggestion
            suggested_timeframe = "5 years"  # Default
            confidence = 0.7

            # Check for timeframe hints in query
            if any(x in query_lower for x in ["past year", "last year", "1 year"]):
                suggested_timeframe = "1 year"
                confidence = 0.9
            elif any(x in query_lower for x in ["3 years", "three years"]):
                suggested_timeframe = "3 years"
                confidence = 0.9
            elif any(x in query_lower for x in ["decade", "10 years", "ten years"]):
                suggested_timeframe = "10 years"
                confidence = 0.9
            elif any(x in query_lower for x in ["5 years", "five years"]):
                confidence = 0.9

            timeframe_options = [
                UnifiedClarificationOption(value="1 year", label="Past Year", description="Recent performance"),
                UnifiedClarificationOption(value="3 years", label="3 Years", description="Short-term trends"),
                UnifiedClarificationOption(value="5 years", label="5 Years", description="Medium-term analysis", recommended=True),
                UnifiedClarificationOption(value="10 years", label="10 Years", description="Long-term perspective")
            ]

            fields.append(UnifiedClarificationField(
                field_id="timeframe",
                type="select",
                label="What time period should we analyze?",
                description="Choose the historical timeframe for your analysis",
                required=True,
                options=timeframe_options,
                suggested_value=suggested_timeframe,
                confidence=confidence,
                icon="📅",
                priority=2
            ))

        if "comparison_type" in missing_slots:
            # Smart comparison type suggestion
            suggested_comparison = "single"
            confidence = 0.6

            if any(x in query_lower for x in ["compare", "vs", "versus", "against", "all companies"]):
                suggested_comparison = "all"
                confidence = 0.8

            comparison_options = [
                UnifiedClarificationOption(value="single", label="Single Company Analysis", description="Focus on one company's performance", recommended=True),
                UnifiedClarificationOption(value="all", label="Compare All Companies", description="Benchmark against industry peers")
            ]

            fields.append(UnifiedClarificationField(
                field_id="comparison_type",
                type="radio",
                label="How would you like to analyze the data?",
                description="Choose between focused analysis or industry comparison",
                required=True,
                options=comparison_options,
                suggested_value=suggested_comparison,
                confidence=confidence,
                icon="📊",
                priority=1
            ))

        if "metrics" in missing_slots:
            # Smart metrics suggestion based on query
            suggested_metrics = []
            confidence = 0.5

            if any(x in query_lower for x in ["market share", "share"]):
                suggested_metrics = ["Market Share"]
                confidence = 0.9
            elif any(x in query_lower for x in ["revenue", "sales", "growth"]):
                suggested_metrics = ["Revenue Growth"]
                confidence = 0.85
            elif any(x in query_lower for x in ["profit", "margin", "profitability"]):
                suggested_metrics = ["Profit Margins"]
                confidence = 0.85
            elif any(x in query_lower for x in ["r&d", "research", "development"]):
                suggested_metrics = ["R&D Spending"]
                confidence = 0.85
            else:
                suggested_metrics = ["Market Share"]  # Default fallback

            metrics_options = [
                UnifiedClarificationOption(value="Market Share", label="Market Share", description="Company's portion of total market", recommended=("Market Share" in suggested_metrics)),
                UnifiedClarificationOption(value="Revenue Growth", label="Revenue Growth", description="Year-over-year revenue changes", recommended=("Revenue Growth" in suggested_metrics)),
                UnifiedClarificationOption(value="Profit Margins", label="Profit Margins", description="Profitability metrics", recommended=("Profit Margins" in suggested_metrics)),
                UnifiedClarificationOption(value="R&D Spending", label="R&D Investment", description="Research & development expenditure", recommended=("R&D Spending" in suggested_metrics))
            ]

            fields.append(UnifiedClarificationField(
                field_id="metrics",
                type="multi_select",
                label="Which metrics would you like to analyze?",
                description="Select one or more financial metrics to examine",
                required=True,
                options=metrics_options,
                suggested_value=suggested_metrics[0] if suggested_metrics else None,
                confidence=confidence,
                icon="📈",
                priority=2
            ))

        # Generate smart title with context
        if len(missing_slots) == 1:
            slot_names = {"company": "company", "timeframe": "time period", "comparison_type": "analysis scope", "metrics": "metrics"}
            title = f"Let's clarify the {slot_names.get(missing_slots[0], missing_slots[0])} for your analysis"
        elif len(missing_slots) > 1:
            title = f"Let's refine your analysis: \"{question[:60]}{'...' if len(question) > 60 else ''}\""
        else:
            title = "Complete your analysis request"

        return create_clarification_artifact(
            session_id=session_id or "default",
            title=title,
            fields=fields,
            original_query=question,
            missing_slots=missing_slots
        )

    async def emit_structured_query(
        self,
        intent_key: str,
        company: Optional[str] = None,
        metrics: Optional[List[str]] = None,
        timeframe: Optional[str] = None,
        comparison_type: Optional[str] = None,
        original_query: str = "",
        session_id: str = "",
        confidence: float = 0.8,
        assumptions: Optional[List[str]] = None
    ) -> StructuredQueryArtifact:
        """
        Emit structured query artifact as single source of truth for SQL generation.

        This consolidates all detected intent and parameters into a standardized format
        that can be reliably consumed by downstream SQL generation tools.
        """

        # Determine completeness
        missing_components = []

        # Basic completeness checks
        if not company and intent_key.endswith("_single"):
            missing_components.append("company")
        if not timeframe:
            missing_components.append("timeframe")
        if not metrics:
            missing_components.append("metrics")
        if not comparison_type and "_" not in intent_key:
            missing_components.append("comparison_type")

        is_complete = len(missing_components) == 0

        # Set defaults based on intent
        if not metrics:
            metrics = ["market_share"] if "market_share" in intent_key else ["revenue"]
        if not timeframe:
            timeframe = "5 years"
        if not comparison_type:
            comparison_type = "single" if intent_key.endswith("_single") else "all"

        # Determine SQL strategy and template
        sql_strategy = "template"
        template_id = None
        if intent_key in ["market_share_single", "market_share_all"]:
            template_id = "market_share_analysis"
        elif intent_key in ["revenue_single", "revenue_all"]:
            template_id = "revenue_analysis"
        else:
            sql_strategy = "generic"

        return StructuredQueryArtifact(
            intent_key=intent_key,
            confidence=confidence,
            company=company,
            metrics=metrics or [],
            timeframe=timeframe,
            comparison_type=comparison_type,
            sql_strategy=sql_strategy,
            template_id=template_id,
            original_query=original_query,
            assumptions=assumptions or [],
            session_id=session_id,
            is_complete=is_complete,
            missing_components=missing_components
        )

    async def create_modern_clarification(
        self,
        missing_slots: List[str],
        question: str,
        session_id: str,
        detected_intent: Optional[str] = None,
        confidence: float = 0.0
    ) -> ModernClarificationRequest:
        """
        Create modern ChatGPT-inspired clarification interface with thinking mode design patterns.

        Features progressive disclosure, smart suggestions, and contextual help.
        """
        import uuid
        request_id = str(uuid.uuid4())

        # Smart title generation based on missing slots
        if len(missing_slots) == 1:
            titles = {
                "company": "Which company would you like to analyze?",
                "timeframe": "What time period interests you?",
                "metrics": "What specific metrics should we examine?",
                "comparison_type": "How would you like to compare the data?"
            }
            title = titles.get(missing_slots[0], "Please provide additional details")
        else:
            title = "Let's refine your analysis request"

        # ChatGPT-style subtitle with context
        subtitle = f"I understand you want to analyze \"{question.lower()}\" - let me gather a few more details to give you the best results."

        # Progressive disclosure: prioritize most important fields
        field_priority = {"company": 3, "timeframe": 2, "metrics": 2, "comparison_type": 1}
        sorted_slots = sorted(missing_slots, key=lambda x: field_priority.get(x, 0), reverse=True)

        fields = []

        for slot in sorted_slots:
            if slot == "company":
                # Smart company suggestions with context
                options = [
                    ClarificationOption(value="NVDA", label="NVIDIA", description="Graphics and AI chips", recommended=True),
                    ClarificationOption(value="AMD", label="AMD", description="Processors and graphics"),
                    ClarificationOption(value="INTC", label="Intel", description="Processors and chips"),
                    ClarificationOption(value="QCOM", label="Qualcomm", description="Mobile chips"),
                    ClarificationOption(value="MU", label="Micron", description="Memory and storage"),
                    ClarificationOption(value="AVGO", label="Broadcom", description="Semiconductors"),
                    ClarificationOption(value="TXN", label="Texas Instruments", description="Analog chips")
                ]

                # AI suggestion based on question content
                suggested_company = None
                question_lower = question.lower()
                if "nvid" in question_lower or "gpu" in question_lower:
                    suggested_company = "NVDA"
                elif "intel" in question_lower:
                    suggested_company = "INTC"
                elif "amd" in question_lower:
                    suggested_company = "AMD"

                fields.append(ClarificationField(
                    field_id="company",
                    type="select",
                    label="Company",
                    description="Select the company you'd like to analyze",
                    placeholder="Choose a company...",
                    options=options,
                    suggested_value=suggested_company,
                    confidence=0.8 if suggested_company else 0.0,
                    icon="building",
                    priority=3
                ))

            elif slot == "timeframe":
                options = [
                    ClarificationOption(value="1_year", label="Past year", description="Most recent 12 months", recommended=False),
                    ClarificationOption(value="3_years", label="Past 3 years", description="Good for trend analysis"),
                    ClarificationOption(value="5_years", label="Past 5 years", description="Comprehensive view", recommended=True),
                    ClarificationOption(value="10_years", label="Past 10 years", description="Long-term perspective")
                ]

                fields.append(ClarificationField(
                    field_id="timeframe",
                    type="radio",
                    label="Time Period",
                    description="How far back should we look?",
                    options=options,
                    suggested_value="5_years",
                    confidence=0.7,
                    icon="calendar",
                    priority=2
                ))

            elif slot == "metrics":
                options = [
                    ClarificationOption(value="market_share", label="Market Share", description="Percentage of market controlled", recommended=True),
                    ClarificationOption(value="revenue", label="Revenue", description="Total sales and income"),
                    ClarificationOption(value="growth", label="Growth Rate", description="Year-over-year changes"),
                    ClarificationOption(value="profitability", label="Profitability", description="Profit margins and efficiency"),
                    ClarificationOption(value="rd_spending", label="R&D Investment", description="Research and development costs")
                ]

                suggested_metric = "market_share" if "market" in question.lower() or "share" in question.lower() else None

                fields.append(ClarificationField(
                    field_id="metrics",
                    type="multi_select",
                    label="Metrics",
                    description="What aspects would you like to analyze?",
                    options=options,
                    suggested_value=suggested_metric,
                    confidence=0.6 if suggested_metric else 0.0,
                    icon="chart",
                    priority=2
                ))

            elif slot == "comparison_type":
                options = [
                    ClarificationOption(value="single", label="Single Company", description="Focus on one company's performance"),
                    ClarificationOption(value="all", label="Industry Comparison", description="Compare across all major players", recommended=True)
                ]

                fields.append(ClarificationField(
                    field_id="comparison_type",
                    type="radio",
                    label="Analysis Scope",
                    description="How would you like to structure the analysis?",
                    options=options,
                    suggested_value="all",
                    confidence=0.5,
                    icon="compare",
                    priority=1
                ))

        # ChatGPT-style progress and flow
        progress = 100.0 - (len(missing_slots) / 4.0) * 100.0
        estimated_time = len(fields) * 15  # 15 seconds per field

        return ModernClarificationRequest(
            request_id=request_id,
            session_id=session_id,
            title=title,
            subtitle=subtitle,
            explanation="This helps me provide more accurate and relevant analysis tailored to your needs.",
            fields=fields,
            step_number=1,
            total_steps=1,
            can_skip=len(missing_slots) <= 1,  # Allow skip if only one missing slot
            progress_percentage=progress,
            estimated_time_seconds=estimated_time,
            original_query=question,
            detected_intent=detected_intent
        )

