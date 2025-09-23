from __future__ import annotations
from typing import Any, Dict, List, Optional, AsyncGenerator
import os
import sys
import logging
import asyncio

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from analytics_memory.intent import (
    detect_intent_with_clarifications,
)
# Import shared functions
from analytics_shared.sql.planner import plan_sql_rule_based, choose_template as cfg_choose_template
from analytics_shared.sql.compiler import compile_sql_from_plan
from analytics_shared.sql.validator import validate_sql
from analytics_shared.database.executor import execute
from analytics_shared.charting.planner import plan_chart_rule_based
from analytics_shared.companies.tickers import get_ticker_list
from analytics_memory.charting import build_chart_spec
from analytics_memory.clarify import (
    compute_required_clarifications,
)
from analytics_memory.types import (
    IntentModel,
    QueryPlanModel,
    ClarifyRequestModel,
)
from .schemas import (
    OffTopicClassifierSchema,
)
from analytics_memory.config import CONFIGS

from .config_store import get_config_store

logger = logging.getLogger(__name__)

class SupervisorTools:
    """Thin wrappers around existing deterministic functions + RAG accessors.

    These tools are designed to be called by a single LLM agent ("supervisor")
    to reproduce the current analytics-memory flow with a different UX and
    thought-process events.
    
    Each tool includes JSON schema definitions for OpenAI function calling.
    """

    def __init__(self, configs: Optional[Dict[str, Any]] = None):
        self.configs = configs or CONFIGS.__dict__
        self.config_store = get_config_store()
        self._default_tickers = self._load_default_tickers()
        self._financial_keywords = self._load_financial_keywords()
        
    @staticmethod
    def get_tool_schemas() -> List[Dict[str, Any]]:
        """Return all tool schemas for OpenAI function calling"""
        return [
            {
                "type": "function",
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
                    "required": ["query"],
                    "additionalProperties": False
                }
            },
            {
                "type": "function",
                "name": "detect_intent",
                "description": "Detect user intent and extract slots from query (company, timeframe, granularity, comparison).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "User query to analyze"
                        }
                    },
                    "required": ["query"],
                    "additionalProperties": False
                }
            },
            
            {
                "type": "function",
                "name": "provisional_plan",
                "description": "Create provisional SQL query plan from detected intent.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "intent": {
                            "type": "object",
                            "description": "Intent model with detected slots"
                        }
                    },
                    "required": ["intent"],
                    "additionalProperties": False
                }
            },
            {
                "type": "function",
                "name": "retrieve_templates_rag",
                "description": "Search for relevant SQL templates using advanced RAG with embeddings and hybrid search.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Search query for finding relevant templates"
                        },
                        "intent_key": {
                            "type": "string",
                            "description": "Optional intent key to filter results"
                        },
                        "top_k": {
                            "type": "integer",
                            "description": "Number of results to return (default: 3)"
                        },
                        "mode": {
                            "type": "string",
                            "description": "Search mode: 'vector_only', 'keyword_only', 'hybrid', or 'auto' (default: 'hybrid')"
                        }
                    },
                    "required": ["query"],
                    "additionalProperties": False
                }
            },
            {
                "type": "function",
                "name": "search_metrics_rag",
                "description": "Search for relevant financial metrics using RAG with semantic matching and synonym expansion.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Search query for finding relevant metrics"
                        },
                        "category": {
                            "type": "string",
                            "description": "Optional metric category to filter results (e.g., 'income_statement', 'ratios')"
                        },
                        "top_k": {
                            "type": "integer",
                            "description": "Number of results to return (default: 5)"
                        },
                        "include_derived": {
                            "type": "boolean",
                            "description": "Whether to include derived metrics in results (default: true)"
                        }
                    },
                    "required": ["query"],
                    "additionalProperties": False
                }
            },
            {
                "type": "function",
                "name": "search_companies_rag",
                "description": "Search for relevant companies using RAG with alias resolution and sector filtering.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Search query for finding relevant companies (ticker, name, or alias)"
                        },
                        "sector": {
                            "type": "string",
                            "description": "Optional sector to filter results (e.g., 'semiconductor')"
                        },
                        "top_k": {
                            "type": "integer",
                            "description": "Number of results to return (default: 5)"
                        }
                    },
                    "required": ["query"],
                    "additionalProperties": False
                }
            },
            {
                "type": "function",
                "name": "get_analytics_context_rag",
                "description": "Get comprehensive analytics context including templates, metrics, companies, and related items.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Query to get context for"
                        },
                        "intent_key": {
                            "type": "string",
                            "description": "Optional intent key for template filtering"
                        },
                        "company_filter": {
                            "type": "string",
                            "description": "Optional company ticker to focus on"
                        },
                        "category_filter": {
                            "type": "string",
                            "description": "Optional metric category to focus on"
                        }
                    },
                    "required": ["query"],
                    "additionalProperties": False
                }
            },
            {
                "type": "function",
                "name": "choose_template_from_config",
                "description": "Pick template from static configuration using intent + plan context.",
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
                    "required": ["intent", "plan"],
                    "additionalProperties": False
                }
            },
            {
                "type": "function",
                "name": "plan_and_select_template",
                "description": "Combined tool: Create SQL query plan from intent and select appropriate template (reduces latency).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "intent": {
                            "type": "object",
                            "description": "Intent model with detected slots"
                        }
                    },
                    "required": ["intent"],
                    "additionalProperties": False
                }
            },
            {
                "type": "function",
                "name": "validate_sql",
                "description": "Validate SQL query for safety and correctness before execution.",
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
                            "description": "Granularity assumed by the SQL"
                        }
                    },
                    "required": ["sql", "granularity"],
                    "additionalProperties": False
                }
            },
            {
                "type": "function",
                "name": "apply_execute_sql",
                "description": "Execute validated SQL against the analytics warehouse.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "sql": {
                            "type": "string",
                            "description": "Validated SQL query to execute"
                        }
                    },
                    "required": ["sql"],
                    "additionalProperties": False
                }
            },
            {
                "type": "function",
                "name": "short_financial_analysis",
                "description": "Generate quick financial insights and analysis from query results before chart generation.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "data": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "additionalProperties": False
                            },
                            "description": "The financial data to analyze"
                        },
                        "query": {
                            "type": "string",
                            "description": "Original user query for context"
                        },
                        "sql": {
                            "type": "string",
                            "description": "SQL query that generated the data"
                        }
                    },
                    "required": ["data", "query", "sql"],
                    "additionalProperties": False
                }
            },
            {
                "type": "function",
                "name": "plan_chart",
                "description": "Plan chart visualization for the retrieved data.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "data": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "additionalProperties": False
                            },
                            "description": "Query result rows"
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
                    "required": ["data", "query"],
                    "additionalProperties": False
                }
            },
            {
                "type": "function",
                "name": "request_clarification",
                "description": "Request additional information from the user when slots are missing or ambiguous.",
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
                    "required": ["intent", "plan"],
                    "additionalProperties": False
                }
            },
            {
                "type": "function",
                "name": "build_chart",
                "description": "Build chart specification from plan and data for presentation.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "data": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "additionalProperties": False
                            },
                            "description": "Query result rows"
                        },
                        "chart_plan": {
                            "type": "object",
                            "description": "Chart plan returned by plan_chart"
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
                    "required": ["data", "chart_plan"],
                    "additionalProperties": False
                }
            }
        ]
    # -------- Intent + Planning --------
    def provisional_plan(self, intent: IntentModel) -> QueryPlanModel:
        return QueryPlanModel(**plan_sql_rule_based(intent, self.configs))

    def compute_clarifications(
        self, intent: IntentModel, plan: QueryPlanModel, template: Optional[Dict[str, Any]]
    ) -> List[ClarifyRequestModel]:
        return compute_required_clarifications(intent, plan, template, self.configs)

    def _load_default_tickers(self) -> List[str]:
        """Load default tickers using shared function."""
        # Use shared function and convert to lowercase for backward compatibility
        tickers = get_ticker_list(self.configs or {})
        return [ticker.lower() for ticker in tickers]

    def _load_financial_keywords(self) -> List[str]:
        keywords: set[str] = set()
        queries_cfg = {}
        metrics_cfg = {}
        if isinstance(self.configs, dict):
            queries_cfg = self.configs.get("queries", {}) or {}
            metrics_cfg = self.configs.get("metrics", {}) or {}

        if isinstance(queries_cfg, dict):
            patterns = queries_cfg.get("query_patterns", {}) or {}
            if isinstance(patterns, dict):
                for pattern in patterns.values():
                    if isinstance(pattern, dict):
                        name = pattern.get("name")
                        if isinstance(name, str):
                            keywords.add(name.lower())
                        for kw in pattern.get("keywords", []) or []:
                            if isinstance(kw, str):
                                keywords.add(kw.lower())

        if isinstance(metrics_cfg, dict):
            for section_name in ("metrics", "derived_metrics"):
                section = metrics_cfg.get(section_name, {}) or {}
                if isinstance(section, dict):
                    for metric in section.values():
                        if isinstance(metric, dict):
                            name = metric.get("name")
                            if isinstance(name, str):
                                keywords.add(name.lower())
                            for alias in metric.get("aliases", []) or []:
                                if isinstance(alias, str):
                                    keywords.add(alias.lower())

        keywords.update(
            {
                "financial",
                "finance",
                "revenue",
                "sales",
                "profit",
                "earnings",
                "eps",
                "margin",
                "margins",
                "operating",
                "net income",
                "gross",
                "market share",
                "share",
                "growth",
                "forecast",
                "guidance",
                "cash",
                "expense",
                "spending",
                "vs",
                "compare",
                "comparison",
                "benchmark",
                "industry",
                "peer",
                "stock",
                "ticker",
                "valuation",
            }
        )
        return list(keywords)


    # -------- Clarifications (blocking) --------

    async def retrieve_templates_rag(
        self, query: str, intent_key: Optional[str] = None, top_k: int = 3,
        mode: str = "hybrid", context: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Enhanced template retrieval using unified ConfigStore with automatic fallback coverage.

        Uses ConfigStore for deterministic fallback: RAG -> Template Store -> YAML -> Empty.
        Returns enriched template results with metadata about source and fallback attempts.
        """
        try:
            # Use ConfigStore for unified access with automatic fallback
            result = await self.config_store.get_templates(
                query=query,
                intent_key=intent_key,
                top_k=top_k,
                mode=mode
            )

            # Add metadata for debugging and telemetry
            for template in result.data:
                template['_config_metadata'] = {
                    'source': result.source.value,
                    'query_time_ms': result.query_time_ms,
                    'fallback_attempted': [s.value for s in result.fallback_attempted],
                    'cache_hit': result.cache_hit
                }

            return result.data

        except Exception as e:
            # Final safety fallback
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"ConfigStore template retrieval failed: {e}")
            return []

    def choose_template_from_config(self, intent: IntentModel, plan: QueryPlanModel) -> Optional[Dict[str, Any]]:
        return cfg_choose_template(intent, plan, self.configs)

    def plan_and_select_template(self, intent: IntentModel) -> Dict[str, Any]:
        """Combined tool: Create SQL query plan, select template, and compile SQL in one call for reduced latency."""
        # Step 1: Create provisional plan
        plan = self.provisional_plan(intent)

        # Step 2: Select template based on intent and plan
        template = self.choose_template_from_config(intent, plan)

        # Step 3: Compile SQL from plan and template
        sql = compile_sql_from_plan(plan, intent, self.configs, template)

        # Return combined result with SQL
        return {
            "plan": plan.dict() if hasattr(plan, 'dict') else plan,
            "template": template,
            "sql": sql,
            "granularity": plan.granularity,
            "combined": True
        }

    async def search_metrics_rag(
        self, query: str, category: Optional[str] = None, top_k: int = 5,
        include_derived: bool = True
    ) -> List[Dict[str, Any]]:
        """Search metrics using unified ConfigStore with automatic fallback coverage.

        Uses ConfigStore for deterministic fallback: RAG -> YAML -> Empty.
        Returns list of relevant metrics with metadata about source and performance.
        """
        try:
            # Use ConfigStore for unified access with automatic fallback
            result = await self.config_store.get_metrics(
                query=query,
                category=category,
                top_k=top_k,
                include_derived=include_derived
            )

            # Add metadata for debugging and telemetry
            for metric in result.data:
                metric['_config_metadata'] = {
                    'source': result.source.value,
                    'query_time_ms': result.query_time_ms,
                    'fallback_attempted': [s.value for s in result.fallback_attempted],
                    'cache_hit': result.cache_hit
                }

            return result.data

        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"ConfigStore metric search failed: {e}")
            return []

    async def search_companies_rag(
        self, query: str, sector: Optional[str] = None, top_k: int = 5
    ) -> List[Dict[str, Any]]:
        """Search companies using unified ConfigStore with automatic fallback coverage.

        Uses ConfigStore for deterministic fallback: RAG -> YAML -> Empty.
        Returns list of relevant companies with metadata about source and performance.
        """
        try:
            # Use ConfigStore for unified access with automatic fallback
            result = await self.config_store.get_companies(
                query=query,
                sector=sector,
                top_k=top_k,
                include_aliases=True
            )

            # Add metadata for debugging and telemetry
            for company in result.data:
                company['_config_metadata'] = {
                    'source': result.source.value,
                    'query_time_ms': result.query_time_ms,
                    'fallback_attempted': [s.value for s in result.fallback_attempted],
                    'cache_hit': result.cache_hit
                }

            return result.data

        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"ConfigStore company search failed: {e}")
            return []

    async def get_analytics_context_rag(
        self, query: str, intent_key: Optional[str] = None,
        company_filter: Optional[str] = None, category_filter: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get comprehensive analytics context using unified ConfigStore.

        Uses ConfigStore for deterministic fallback coverage across all config types.
        Returns templates, metrics, companies, and comprehensive metadata.
        """
        try:
            # Use ConfigStore for unified context retrieval with automatic fallback
            result = await self.config_store.get_analytics_context(
                query=query,
                intent_key=intent_key,
                company_filter=company_filter,
                category_filter=category_filter
            )

            if result.data:
                context_data = result.data[0]  # Context is returned as single item

                # Add ConfigStore metadata
                context_data['_config_metadata'] = {
                    'source': result.source.value,
                    'query_time_ms': result.query_time_ms,
                    'fallback_attempted': [s.value for s in result.fallback_attempted],
                    'cache_hit': result.cache_hit,
                    'success': result.success
                }

                return context_data
            else:
                # Empty fallback case
                return {
                    'templates': [],
                    'metrics': [],
                    'companies': [],
                    'charts': [],
                    'related_items': {},
                    '_config_metadata': {
                        'source': result.source.value,
                        'error': result.error,
                        'fallback_attempted': [s.value for s in result.fallback_attempted]
                    }
                }

        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"ConfigStore context retrieval failed: {e}")
            return {
                'templates': [],
                'metrics': [],
                'companies': [],
                'charts': [],
                'related_items': {},
                'error': str(e)
            }

    # -------- SQL --------
    def validate_sql(self, sql: str, granularity: str, max_limit: Optional[int] = None):
        max_limit = max_limit or self.configs.get('database', {}).get('query_defaults', {}).get('max_limit', 10000)
        return validate_sql(sql, allowed_tables=["comp_financials"], max_limit=max_limit, granularity=granularity)

    async def apply_execute_sql(self, sql: str) -> Dict[str, Any]:
        """Apply tool: Execute SQL query with safety checks
        
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
    def short_financial_analysis(self, data: List[Dict[str, Any]], query: str, sql: str) -> Dict[str, Any]:
        """Generate quick financial insights before chart generation."""
        if not data:
            return {
                "insights": ["No data available for analysis"],
                "summary": "No financial data was found for the specified criteria.",
                "data_points": 0
            }

        # Basic statistical analysis
        insights = []
        data_points = len(data)

        # Analyze numerical columns
        numeric_columns = []
        for row in data[:5]:  # Sample first 5 rows to identify numeric columns
            for key, value in row.items():
                if isinstance(value, (int, float)) and key not in ['year', 'quarter', 'date']:
                    if key not in [col['name'] for col in numeric_columns]:
                        numeric_columns.append({'name': key, 'values': []})

        # Collect values for numeric analysis
        for col in numeric_columns:
            for row in data:
                if col['name'] in row and row[col['name']] is not None:
                    col['values'].append(float(row[col['name']]))

        # Generate insights based on data patterns
        for col in numeric_columns:
            if col['values']:
                avg_val = sum(col['values']) / len(col['values'])
                max_val = max(col['values'])
                min_val = min(col['values'])

                if len(col['values']) > 1:
                    # Trend analysis for time series
                    if col['values'][-1] > col['values'][0]:
                        trend = "increasing"
                    elif col['values'][-1] < col['values'][0]:
                        trend = "decreasing"
                    else:
                        trend = "stable"

                    insights.append(f"{col['name'].title()} shows {trend} trend from {min_val:.2f} to {max_val:.2f}")

                insights.append(f"Average {col['name']}: {avg_val:.2f}")

        # Query-specific insights
        query_lower = query.lower()
        if "market share" in query_lower:
            insights.append("Market share analysis revealing competitive positioning")
        elif "revenue" in query_lower:
            insights.append("Revenue analysis showing financial performance trends")
        elif "growth" in query_lower:
            insights.append("Growth metrics indicating business expansion patterns")

        return {
            "insights": insights[:5],  # Limit to top 5 insights
            "summary": f"Analysis of {data_points} data points showing key financial metrics and trends.",
            "data_points": data_points,
            "numeric_columns": len(numeric_columns)
        }

    # Analysis streaming handled by Responses API client in supervisor

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

    # -------- Unified Query Processing --------
    async def classify_query_relevance(self, query: str, session_id: str) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Unified entry point that handles:
        1. Query classification (financial vs non-financial)
        2. Intent detection (if financial)
        3. Multi-step clarification loop (if needed)
        4. Returns complete result or early exit
        """
        import uuid
        from analytics_memory.types import ClarifyRequestModel, IntentModel
        import sys
        import os
        sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from unified_responses_client import get_unified_client

        try:
            client = get_unified_client()
            if not client:
                # Fail fast - no fallback
                yield {
                    "error": "OpenAI client unavailable. Financial analytics requires AI services.",
                    "early_exit": True,
                    "is_financial": False
                }
                return

            # Step 1: Classification
            classification = await self._classify_topic_internal(query, client)

            if classification.topic_category != "financial_analytics":
                # Early exit for non-financial queries
                yield {
                    "is_financial": False,
                    "category": classification.topic_category,
                    "message": classification.polite_decline_message or "I'm specialized in financial analytics. How can I help you analyze financial data?",
                    "complete": True,
                    "early_exit": True
                }
                return

            # Step 2: Intent Detection (internal)
            intent = await self._detect_intent_internal(query, session_id, client)

            # Step 3: Multi-Step Clarification Loop
            if intent.clarifications_suggested:
                # Start clarification loop
                all_clarifications = []
                clarification_answers = {}

                # Emit start of clarification loop
                yield {
                    "event": "clarification_loop_start",
                    "data": {
                        "total_clarifications": len(intent.clarifications_suggested),
                        "session_id": session_id
                    }
                }

                # Process each clarification sequentially
                for idx, clarification in enumerate(intent.clarifications_suggested):
                    clarify_request = ClarifyRequestModel(
                        slot=clarification.get('slot', 'unknown'),
                        question=clarification.get('reason', 'Please provide clarification'),
                        type='single',  # Default type
                        options=self._get_options_for_slot(clarification.get('slot')),
                        request_id=str(uuid.uuid4()),
                        reason=clarification.get('reason', ''),
                        session_id=session_id
                    )

                    # Emit clarification request to frontend
                    yield {
                        "event": "clarification_request",
                        "data": {
                            **clarify_request.dict(),
                            "question_number": idx + 1,
                            "total_questions": len(intent.clarifications_suggested),
                            "progress": f"{idx + 1}/{len(intent.clarifications_suggested)}"
                        }
                    }

                    # Wait for user answer with timeout
                    answer_value = await self._wait_for_clarification_answer(session_id, clarify_request, timeout=30.0)

                    if answer_value is not None:
                        clarification_answers[clarify_request.slot] = answer_value

                        # Apply answer to intent immediately
                        intent.slots_detected[clarify_request.slot] = answer_value

                        # Emit clarification acknowledged
                        yield {
                            "event": "clarification_acknowledged",
                            "data": {
                                "slot": clarify_request.slot,
                                "answer": answer_value,
                                "question_number": idx + 1,
                                "remaining": len(intent.clarifications_suggested) - idx - 1
                            }
                        }
                    else:
                        # Timeout or error - use default if available
                        default_value = self._get_default_for_slot(clarify_request.slot)
                        if default_value:
                            intent.slots_detected[clarify_request.slot] = default_value
                            clarification_answers[clarify_request.slot] = default_value

                    all_clarifications.append({
                        "slot": clarify_request.slot,
                        "answer": clarification_answers.get(clarify_request.slot)
                    })

                # Emit end of clarification loop
                yield {
                    "event": "clarification_loop_complete",
                    "data": {
                        "total_answered": len(all_clarifications),
                        "clarifications": all_clarifications,
                        "resolved_intent": intent.dict()
                    }
                }

                resolved_intent = intent
            else:
                resolved_intent = intent
                all_clarifications = []

            # Return complete analysis with all clarifications resolved
            yield {
                "is_financial": True,
                "category": "financial_analytics",
                "intent": resolved_intent.dict(),
                "complete": True,
                "early_exit": False,
                "clarifications_resolved": len(all_clarifications),
                "clarification_details": all_clarifications
            }

        except Exception as e:
            logger.error(f"Error in classify_query_relevance: {str(e)}")
            yield {
                "error": f"Classification failed: {str(e)}",
                "early_exit": True,
                "is_financial": False
            }

    # -------- Internal Methods for Unified Processing --------

    async def _classify_topic_internal(self, query: str, client) -> OffTopicClassifierSchema:
        """Internal classification logic using fast nano model"""
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

Provide a short polite decline message for off-topic queries and suggest how to rephrase."""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Classify this query: '{query}'"}
        ]

        # Use gpt-5-nano-2025-08-07 for fast classification
        result, _ = await client.create_structured(
            response_model=OffTopicClassifierSchema,
            messages=messages,
            model="gpt-5-nano-2025-08-07",  # Fast nano model for classification
            reasoning_effort="low"  # Fast classification
        )

        return result

    async def _detect_intent_internal(self, query: str, session_id: str, client) -> IntentModel:
        """Internal intent detection - reuses existing logic"""
        from analytics_memory.intent import detect_intent_with_clarifications

        # Use existing intent detection with clarifications
        intent = await asyncio.to_thread(
            detect_intent_with_clarifications,
            query,
            self.configs,
            session_id=session_id
        )
        return intent

    async def _wait_for_clarification_answer(self, session_id: str, clarify_request: ClarifyRequestModel, timeout: float = 30.0) -> Optional[Any]:
        """Wait for clarification answer with timeout"""
        # Store pending clarification (using supervisor's state management)
        from analytics_supervisor.supervisor import get_active_workflow

        workflow = get_active_workflow(session_id)
        if not workflow:
            logger.error(f"No active workflow found for session {session_id}")
            return None

        # Store clarification and wait
        workflow._pending_clarifications[session_id] = clarify_request
        workflow._clarification_events[session_id] = asyncio.Event()

        try:
            await asyncio.wait_for(
                workflow._clarification_events[session_id].wait(),
                timeout=timeout
            )

            # Get the answer
            state = workflow.workflow_states.get(session_id)
            if state and hasattr(state, 'clarification_answer'):
                answer = state.clarification_answer
                # Clear the answer for next question
                delattr(state, 'clarification_answer')
                return answer

        except asyncio.TimeoutError:
            logger.warning(f"Clarification timeout for session {session_id}, slot {clarify_request.slot}")
            return None
        finally:
            # Cleanup
            workflow._pending_clarifications.pop(session_id, None)
            workflow._clarification_events.pop(session_id, None)

        return None

    def _get_default_for_slot(self, slot: str) -> Optional[Any]:
        """Get default value for a clarification slot"""
        defaults = {
            "company": "NVDA",  # Default to NVIDIA
            "timeframe": {"years_back": 5},  # Default to 5 years
            "granularity": "annual",  # Default to annual
            "comparison": "single_company"  # Default to single company analysis
        }
        return defaults.get(slot)

    # -------- Question Completeness Analysis --------





