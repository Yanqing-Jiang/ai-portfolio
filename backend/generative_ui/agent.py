"""
Dashboard Agent - Claude-powered dashboard plan generation.

This agent receives user questions and generates DashboardPlan objects
using Claude's structured output capability.
"""

from __future__ import annotations

import json
import logging
from typing import Any, AsyncGenerator, Dict, List, Optional

from .models import DashboardPlan, DashboardWidget
from .a2ui import A2UIMessageGenerator
from .a2ui.validator import allowed_component_names
from .config import get_settings
from conversational_analytics.tools.sql_tool import execute_sql_tool
from conversational_analytics.agent import get_conversational_analytics_agent

logger = logging.getLogger(__name__)


# Available tickers in comp_financials
AVAILABLE_TICKERS = ["AMD", "AVGO", "INTC", "MU", "NVDA", "QCOM", "TXN"]

# Widget catalog for Claude prompt
WIDGET_CATALOG = """
Available Widget Types:
1. price_chart - TradingView interactive chart (config: interval, showVolume)
2. kpi - Key metric card with optional delta (config: label, dataKey, unit, deltaKey)
3. table - Data table with sortable columns (config: sortable)
4. news_timeline - News articles with sentiment (config: none)
5. correlation - Correlation matrix heatmap (config: none)
6. explain_move - Price movement analysis panel (config: showCitations)
"""

# Question archetype descriptions
ARCHETYPE_DESCRIPTIONS = """
Question Archetypes:
- explain_move: "Why did X drop/rise?" - Use price_chart, kpis, news_timeline, explain_move
- compare: "Compare X vs Y" - Use price_chart (overlay), table, correlation
- trend_analysis: "X revenue/margin trend" - Use price_chart, kpi (trend), table
- earnings_focus: "Show X earnings" - Use kpis (EPS, Revenue, Margin), table
- sector_overview: "Semiconductor overview" - Use table (all tickers), correlation
"""

# System prompt for plan generation
PLAN_GENERATION_PROMPT = f"""You are a financial dashboard architect. Given a user's question about semiconductor companies, generate a DashboardPlan JSON object that specifies which widgets to display.

{WIDGET_CATALOG}

{ARCHETYPE_DESCRIPTIONS}

Available Tickers: {', '.join(AVAILABLE_TICKERS)}

IMPORTANT RULES:
1. Only use tickers from the available list
2. Select widgets appropriate for the question type
3. For "why did X drop" questions, always include explain_move widget
4. For comparison questions, include table and correlation widgets
5. Generate SQL queries that work with comp_financials table and its columns: ticker, calendar_year, calendar_quarter_num, calendar_quarter, metric, value. Do NOT reference columns like close, open, high, low, volume.
6. Keep widget count between 3-6 for good UX

Output ONLY valid JSON matching the DashboardPlan schema.
"""

# Tool definition for plan generation
PLAN_TOOL_DEFINITION = {
    "name": "generate_dashboard_plan",
    "description": "Generate a dashboard plan based on the user's financial question",
    "input_schema": {
        "type": "object",
        "properties": {
            "title": {
                "type": "string",
                "description": "Dashboard title summarizing the analysis"
            },
            "ticker": {
                "type": "string",
                "description": "Primary ticker symbol (AMD, AVGO, INTC, MU, NVDA, QCOM, or TXN)"
            },
            "peers": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Peer/comparison tickers"
            },
            "time_range": {
                "type": "string",
                "description": "Default time range (1M, 3M, 6M, 1Y)"
            },
            "archetype": {
                "type": "string",
                "enum": ["explain_move", "compare", "trend_analysis", "earnings_focus", "sector_overview"],
                "description": "Type of analysis question"
            },
            "widgets": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "type": {
                            "type": "string",
                            "enum": ["price_chart", "kpi", "table", "news_timeline", "correlation", "explain_move"]
                        },
                        "config": {"type": "object"}
                    },
                    "required": ["type"]
                },
                "description": "Widgets to display in the dashboard"
            },
            "sql_queries": {
                "type": "array",
                "items": {"type": "string"},
                "description": "SQL queries to execute against comp_financials"
            }
        },
        "required": ["title", "ticker", "archetype", "widgets"]
    }
}


class DashboardAgentError(Exception):
    """Raised when dashboard agent encounters an error."""
    pass


class DashboardAgent:
    """
    Claude-powered agent for generating financial dashboards.
    
    Uses Claude's tool calling to generate structured DashboardPlan objects
    and executes SQL queries to populate data.
    """
    
    def __init__(self):
        """
        Function: __init__ — called from get_dashboard_agent(); initializes Anthropic client
        with configured model/key and exposes settings for downstream calls.
        """
        try:
            import anthropic
            self.settings = get_settings()
            if not self.settings.claude_api_key:
                raise DashboardAgentError("Claude API key not configured")
            self.client = anthropic.Anthropic(api_key=self.settings.claude_api_key)
            self.model = self.settings.claude_model
        except ImportError:
            raise DashboardAgentError("anthropic package not installed")
        except Exception as e:
            logger.error("Failed to initialize Anthropic client: %s", e)
            raise DashboardAgentError(f"Anthropic client error: {e}")
    
    async def generate_plan(self, question: str) -> DashboardPlan:
        """
        Generate a DashboardPlan from a user question using Claude.
        Called from routes.dashboard.create_dashboard and generate_dashboard.
        
        Args:
            question: User's financial question
            
        Returns:
            DashboardPlan object with widgets and queries
        """
        logger.info("[DASHBOARD_AGENT] Generating plan for: %s", question)
        
        try:
            plan_data = self._stream_plan(question)
            logger.info("[DASHBOARD_AGENT] Generated plan: %s", plan_data.get("archetype"))

            widgets = [
                DashboardWidget(type=w["type"], config=w.get("config", {}))
                for w in plan_data.get("widgets", [])
            ]

            return DashboardPlan(
                title=plan_data.get("title", "Financial Dashboard"),
                ticker=plan_data.get("ticker", "NVDA"),
                peers=plan_data.get("peers", []),
                time_range=plan_data.get("time_range", "3M"),
                archetype=plan_data.get("archetype", "explain_move"),
                widgets=widgets,
                sql_queries=plan_data.get("sql_queries", []),
            )
            
        except Exception as e:
            logger.error("[DASHBOARD_AGENT] Plan generation failed: %s", e)
            raise DashboardAgentError(str(e))
    
    async def execute_queries(self, plan: DashboardPlan) -> Dict[str, Any]:
        """
        Execute SQL queries from the plan and return data.
        Called from generate_dashboard and SSE stream to populate widgets.
        
        Args:
            plan: DashboardPlan with sql_queries
            
        Returns:
            Dictionary of query results keyed by query_{i}
        """
        # Route through Conversational Analytics agent runtime so SQL is generated/validated by the existing agent.
        results: Dict[str, Any] = {}

        # Use the user's question + plan context to ask the analytics agent for data
        agent = get_conversational_analytics_agent()
        session_id = plan.ticker + "_genui"
        data_events: List[Dict[str, Any]] = []

        async for event_str in agent.run_with_tools(plan.title or plan.ticker, session_id=session_id):
            try:
                # event_str is "data: {...}\n\n"
                payload = json.loads(event_str.replace("data: ", "").strip())
                if payload.get("type") == "data":
                    data_events.append(payload.get("data", {}))
            except Exception:
                continue

        if data_events:
            first = data_events[0]
            results["query_0"] = {
                "success": True,
                "rows": first.get("rows", []),
                "columns": first.get("columns", []),
                "sql": first.get("sql"),
                "row_count": len(first.get("rows", [])),
            }
        else:
            results["query_0"] = {
                "success": False,
                "error": "No data returned from analytics agent",
                "rows": [],
                "columns": [],
                "row_count": 0,
            }

        return results

    
    async def generate_dashboard(
        self, 
        question: str,
        surface_id: str = "dashboard_main"
    ) -> AsyncGenerator[str, None]:
        """
        Full pipeline: generate plan, execute queries, stream A2UI.
        Called from SSE stream handlers to drive the UI.
        
        Args:
            question: User's financial question
            surface_id: A2UI surface identifier
            
        Yields:
            A2UI JSONL messages
        """
        try:
            # 1. Generate plan with Claude
            plan = await self.generate_plan(question)
        except Exception as exc:
            for msg in self._error_update(surface_id, "plan_generation_failed", str(exc)):
                yield msg
            yield json.dumps({"done": True})
            return
        
        # 2. Create A2UI generator
        a2ui = A2UIMessageGenerator(
            surface_id=surface_id,
            catalog_id="financial-standard-v1"
        )
        
        # 3. Stream structure immediately
        try:
            for msg in a2ui.generate_from_plan(plan):
                yield msg
        except ValueError as exc:
            for err_msg in a2ui.error_surface("catalog_validation_failed", str(exc)):
                yield err_msg
            yield json.dumps({"done": True})
            return

        # 4. Execute data fetch (agent runtime) AFTER layout is sent
        query_data = await self.execute_queries(plan)

        # 5. Stream data or error
        first_query = query_data.get("query_0", {}) if query_data else {}
        if first_query.get("success") and first_query.get("rows"):
            first_row = first_query["rows"][0]
            data_msg = a2ui.update_price_data(
                price=first_row.get("close", first_row.get("value", 0)),
                volume=first_row.get("volume", 0),
                change=first_row.get("change", 0),
                change_percent=first_row.get("change_percent", 0)
            )
            yield data_msg
        else:
            error_message = first_query.get("error", "Dashboard queries returned no data.")
            for msg in self._error_update(
                surface_id,
                "query_failed",
                error_message,
            ):
                yield msg

        # 6. Signal completion
        yield json.dumps({"done": True})

    def _error_update(self, surface_id: str, code: str, message: str) -> List[str]:
        """
        Function: _error_update — used internally by generate_dashboard to stream
        a standardized error payload and ErrorPanel surface so the frontend can render
        the failure context.
        """
        generator = A2UIMessageGenerator(surface_id=surface_id, catalog_id="financial-standard-v1")
        return generator.error_surface(code=code, message=message)

    def _stream_plan(self, question: str) -> Dict[str, Any]:
        """
        Function: _stream_plan — called from generate_plan; uses Anthropic streaming
        to buffer tool JSON, validating the tool name, with fallback to non-stream.
        """
        system_prompt = self._build_prompt()

        try:
            stream = self.client.messages.create(
                model=self.model,
                max_tokens=2048,
                system=system_prompt,
                tools=[PLAN_TOOL_DEFINITION],
                tool_choice={"type": "tool", "name": "generate_dashboard_plan"},
                messages=[{"role": "user", "content": question}],
                stream=True,
            )

            tool_json_chunks: List[str] = []
            tool_name: Optional[str] = None

            for event in stream:
                etype = getattr(event, "type", None)
                if etype == "content_block_start":
                    block = getattr(event, "content_block", None)
                    if block and getattr(block, "type", "") == "tool_use":
                        tool_name = getattr(block, "name", None)
                elif etype == "content_block_delta":
                    delta = getattr(event, "delta", None)
                    if delta and getattr(delta, "type", "") == "input_json_delta":
                        tool_json_chunks.append(getattr(delta, "partial_json", ""))
                elif etype == "message_stop":
                    break

            if not tool_json_chunks:
                raise DashboardAgentError("Claude stream did not return tool JSON")

            plan_data = json.loads("".join(tool_json_chunks))
            if tool_name != "generate_dashboard_plan":
                raise DashboardAgentError("Claude stream returned unexpected tool")
            return plan_data

        except Exception as exc:
            logger.warning("Streaming plan failed, falling back to non-stream: %s", exc)
            response = self.client.messages.create(
                model=self.model,
                max_tokens=2048,
                system=system_prompt,
                tools=[PLAN_TOOL_DEFINITION],
                tool_choice={"type": "tool", "name": "generate_dashboard_plan"},
                messages=[{"role": "user", "content": question}],
            )
            for block in response.content:
                if getattr(block, "type", None) == "tool_use" and getattr(block, "name", "") == "generate_dashboard_plan":
                    return block.input
            raise DashboardAgentError("Claude response missing tool output")

    def _build_prompt(self) -> str:
        """
        Function: _build_prompt — called from _stream_plan; injects catalog and component
        constraints to keep Claude output aligned with financial-standard-v1.
        """
        allowed = ", ".join(sorted(allowed_component_names()))
        return f"""{PLAN_GENERATION_PROMPT}

Available Tickers: {', '.join(AVAILABLE_TICKERS)}
Catalog ID: financial-standard-v1
Allowed Components: {allowed}

{ARCHETYPE_DESCRIPTIONS}

{WIDGET_CATALOG}

Rules:
- Only use Allowed Components.
- Respect catalog_id financial-standard-v1.
- Keep 3-6 widgets.
- Generate SQL for comp_financials and include time_range."""


# Singleton instance
_agent_instance: Optional[DashboardAgent] = None


def get_dashboard_agent() -> DashboardAgent:
    """Get or create the singleton dashboard agent."""
    global _agent_instance
    if _agent_instance is None:
        _agent_instance = DashboardAgent()
    return _agent_instance
