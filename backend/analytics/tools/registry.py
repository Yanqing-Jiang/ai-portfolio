# --- Analytics Function/Class Map ---
# Class: SupervisorTools
#   Role: Thin wrappers around existing deterministic functions + YAML-backed accessors.
#   Called from: analytics.flows.planner_executor
#   Collaborators: analytics.core.state.QueryPlanModel, analytics.core.clarify.compute_required_clarifications, analytics.sql.sql_planner.choose_template, analytics.sql.compiler.compile_sql_from_plan, +2 more
#   Why: These tools are designed to be called by a single LLM agent ("supervisor") to reproduce the current analytics-memory flow with a different UX and thought-process events.
# --- End Analytics Function/Class Map ---
from __future__ import annotations
from typing import Any, Dict, List, Optional, AsyncGenerator
import asyncio
import logging
import re

# Shared utilities
from ..sql.sql_planner import plan_sql_rule_based, choose_template as cfg_choose_template
from ..sql.compiler import compile_sql_from_plan
from ..sql.validator import validate_sql
from ..semantic.catalog import get_semantic_catalog
from ..sql.executor import execute_sql
from ..core.charting import plan_chart_rule_based
from ..core.companies import get_ticker_list
from ..core.events import EventEmitter
from ..core.charting import build_chart_spec
from ..core.clarify import (
    compute_required_clarifications,
)
from ..core.state import (
    IntentModel,
    QueryPlanModel,
    ClarifyRequestModel,
)
from ..core.context import get_configs

CONFIGS = get_configs()
SEMANTIC_CATALOG = get_semantic_catalog()

from ..core.config_store import get_config_store

logger = logging.getLogger(__name__)

class SupervisorTools:
    """Thin wrappers around existing deterministic functions + YAML-backed accessors.

    These tools are designed to be called by a single LLM agent ("supervisor")
    to reproduce the current analytics-memory flow with a different UX and
    thought-process events.
    
    Each tool includes JSON schema definitions for OpenAI function calling.
    """

    def __init__(
        self,
        configs: Optional[Dict[str, Any]] = None,
        config_store=None,
    ):
        self.configs = configs or CONFIGS.__dict__
        self.config_store = config_store or get_config_store()
    @staticmethod
    def get_tool_schemas() -> List[Dict[str, Any]]:
        """Return all tool schemas for OpenAI function calling.
        
        DEPRECATED (2025-12-03): Use CanonicalToolRegistry.get_tool_schemas() instead.
        This function returns inline schemas that may drift from the canonical registry.
        See backend/analytics/tools/canonical_registry.py for the single source of truth.
        
        Migration: Replace calls with:
            from analytics.tools.canonical_registry import get_canonical_registry
            registry = get_canonical_registry()
            schemas = registry.get_openai_function_schemas()
        """
        import warnings
        warnings.warn(
            "SupervisorTools.get_tool_schemas() is deprecated. "
            "Use CanonicalToolRegistry.get_openai_function_schemas() instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return [
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
                "name": "lookup_templates",
                "description": "Retrieve SQL templates from the YAML catalogue based on the query or intent key.",
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
                        }
                    },
                    "required": ["query"],
                    "additionalProperties": False
                }
            },
            {
                "type": "function",
                "name": "lookup_metrics",
                "description": "Retrieve financial metrics definitions from YAML, including optional categories and derived metrics.",
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
                "name": "lookup_companies",
                "description": "Retrieve company records from the YAML catalogue with optional sector filtering.",
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
                "name": "lookup_analytics_context",
                "description": "Summarise YAML-backed assets (templates, metrics, charts, companies) relevant to the query.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Query to contextualise"
                        },
                        "include": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Optional list of segments to include (e.g., ['queries','metrics'])"
                        },
                        "top_k": {
                            "type": "integer",
                            "description": "Number of examples per segment (default: 5)"
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
                "description": "Validate compiled SQL against guardrails (LIMIT, allowed tables).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "sql": {
                            "type": "string",
                            "description": "SQL query to validate"
                        },
                        "granularity": {
                            "type": "string",
                            "description": "Optional granularity hint (e.g., 'annual')"
                        }
                    },
                    "required": ["sql"],
                    "additionalProperties": False
                }
            },
            {
                "type": "function",
                "name": "compile_sql",
                "description": "Compile SQL from plan and template, returning the raw statement.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "plan": {
                            "type": "object",
                            "description": "Query plan model"
                        },
                        "intent": {
                            "type": "object",
                            "description": "Intent model"
                        },
                        "template": {
                            "type": "object",
                            "description": "Optional template metadata"
                        }
                    },
                    "required": ["plan", "intent"],
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

    
    
    
    # -------- Clarifications (blocking) --------

    async def lookup_templates(
        self,
        query: str,
        intent_key: Optional[str] = None,
        top_k: int = 3,
    ) -> List[Dict[str, Any]]:
        """Retrieve SQL templates from the YAML catalogue."""
        try:
            result = await self.config_store.get_templates(
                query=query,
                intent_key=intent_key,
                top_k=top_k,
            )

            for template in result.data:
                template["_config_metadata"] = {
                    "source": result.source.value,
                    "query_time_ms": result.query_time_ms,
                    "fallback_attempted": [s.value for s in result.fallback_attempted],
                    "cache_hit": result.cache_hit,
                }

            return result.data
        except Exception as exc:  # pragma: no cover - defensive
            logger.error("ConfigStore template retrieval failed: %s", exc)
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

    async def lookup_metrics(
        self,
        query: str,
        category: Optional[str] = None,
        top_k: int = 5,
        include_derived: bool = True,
    ) -> List[Dict[str, Any]]:
        """Retrieve financial metrics definitions from YAML."""
        try:
            result = await self.config_store.get_metrics(
                query=query,
                category=category,
                top_k=top_k,
                include_derived=include_derived,
            )

            for metric in result.data:
                metric["_config_metadata"] = {
                    "source": result.source.value,
                    "query_time_ms": result.query_time_ms,
                    "fallback_attempted": [s.value for s in result.fallback_attempted],
                    "cache_hit": result.cache_hit,
                }

            return result.data
        except Exception as exc:  # pragma: no cover - defensive
            logger.error("ConfigStore metric lookup failed: %s", exc)
            return []


    async def lookup_companies(
        self,
        query: str,
        sector: Optional[str] = None,
        top_k: int = 5,
    ) -> List[Dict[str, Any]]:
        """Retrieve company records from the YAML catalogue."""
        try:
            result = await self.config_store.get_companies(
                query=query,
                sector=sector,
                top_k=top_k,
            )

            for company in result.data:
                company["_config_metadata"] = {
                    "source": result.source.value,
                    "query_time_ms": result.query_time_ms,
                    "fallback_attempted": [s.value for s in result.fallback_attempted],
                    "cache_hit": result.cache_hit,
                }

            return result.data
        except Exception as exc:  # pragma: no cover - defensive
            logger.error("ConfigStore company lookup failed: %s", exc)
            return []


    async def lookup_analytics_context(
        self,
        query: str,
        include: Optional[List[str]] = None,
        top_k: int = 5,
    ) -> Dict[str, Any]:
        """Return aggregated analytics context segments sourced from YAML."""
        try:
            result = await self.config_store.get_analytics_context(
                query=query,
                include=include,
                top_k=top_k,
            )

            return {
                "segments": result.data,
                "_config_metadata": {
                    "source": result.source.value,
                    "query_time_ms": result.query_time_ms,
                    "fallback_attempted": [s.value for s in result.fallback_attempted],
                    "cache_hit": result.cache_hit,
                },
            }
        except Exception as exc:  # pragma: no cover - defensive
            logger.error("ConfigStore analytics context lookup failed: %s", exc)
            return {
                "segments": [],
                "error": str(exc),
            }


    def validate_sql(self, sql: str, granularity: str, max_limit: Optional[int] = None):
        semantic_defaults = SEMANTIC_CATALOG.query_defaults()
        effective_limit = max_limit or semantic_defaults.get("max_limit", 10000)
        return validate_sql(
            sql,
            allowed_tables=["comp_financials"],
            max_limit=effective_limit,
            granularity=granularity,
        )

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
            data = await execute_sql(sql)
            
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
    def plan_chart(self, data, query: str, intent_key: Optional[str], statistic: Optional[str] = None):
        return plan_chart_rule_based(data, query, intent_key, statistic=statistic)

    def build_chart(self, data, chart_plan, comparison: Optional[str], intent_key: Optional[str], statistic: Optional[str] = None):
        return build_chart_spec(
            data,
            chart_plan.dict() if hasattr(chart_plan, 'dict') else chart_plan,
            CONFIGS.charts,
            intent_key=intent_key,
            comparison=comparison,
            statistic=statistic,
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

    
    # -------- Internal Methods for Unified Processing --------

    
    def _get_default_for_slot(self, slot: str) -> Optional[Any]:
        """Get default value for a clarification slot"""
        defaults = {
            "company": "NVDA",  # Default to NVIDIA
            "timeframe": {"years_back": 5},  # Default to 5 years
            "granularity": "annual",  # Default to annual
            "comparison": "single_company"  # Default to single company analysis
        }
        return defaults.get(slot)

    def _get_options_for_slot(self, slot: str) -> List[str]:
        """Get available options for a clarification slot (backward compatible)"""
        if not slot:
            return []

        slot = str(slot).lower()

        if slot == "company":
            return self.configs.get("companies", {}).get("selection_rules", {}).get("default_companies", {}).get("tickers", ["NVDA", "AMD", "INTC", "MU", "QCOM", "AVGO", "TXN"])
        if slot == "comparison":
            # Derive comparison choices from YAML-defined intents
            try:
                qp = (self.configs.get("queries", {}) or {}).get("query_patterns", {}) or {}
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











