"""
Dashboard Planner

Uses Claude 3.5 Sonnet to analyze user questions and generate a structured DashboardPlan.
"""

from __future__ import annotations
import json
import anthropic
from typing import Any, Dict, List, Optional
from ..models.dashboard_plan import DashboardPlan, DashboardWidget
from ..config import settings

class DashboardPlanner:
    """
    Orchestrates the planning phase of the generative dashboard.
    Uses Claude to decide which widgets to show and which data to fetch.
    """

    def __init__(self, api_key: Optional[str] = None):
        self.client = anthropic.Anthropic(api_key=api_key or settings.ANTHROPIC_API_KEY)

    async def generate_plan(self, question: str) -> DashboardPlan:
        """
        Send the question to Claude and parse the resulting DashboardPlan.
        """
        system_prompt = f"""
        You are a Financial Dashboard Architect. Your goal is to design a data-driven dashboard layout in response to a user's question about semiconductor stocks (AMD, AVGO, INTC, MU, NVDA, QCOM, TXN).

        Respond ONLY with a JSON object that matches the following schema:
        {{
            "title": "Clear, descriptive title for the dashboard",
            "ticker": "The primary ticker symbol discussed (e.g., NVDA)",
            "peers": ["Any competitor tickers mentioned or relevant for comparison"],
            "time_range": "Default time range for charts (e.g., 1M, 3M, 1Y, 5Y)",
            "archetype": "One of: explain_move, compare, screen, monitor, portfolio_doctor",
            "widgets": [
                {{
                    "type": "price_chart",
                    "config": {{ "interval": "1D", "showVolume": true }}
                }},
                {{
                    "type": "kpi",
                    "config": {{ "label": "Price", "dataKey": "price", "unit": "$" }}
                }},
                {{
                    "type": "table",
                    "config": {{ "title": "Quarterly Financials" }}
                }},
                {{
                    "type": "news_timeline",
                    "config": {{ "count": 10 }}
                }},
                {{
                    "type": "correlation",
                    "config": {{ "peers": ["AMD", "INTC"] }}
                }},
                {{
                    "type": "explain_move",
                    "config": {{ "showCitations": true }}
                }}
            ],
            "sql_queries": ["Valid SQL queries against the 'comp_financials' table if needed"],
            "research_queries": ["Search terms for web news if news/explanation is needed"]
        }}

        CATALOG OF AVAILABLE WIDGET TYPES:
        - price_chart: Interactive TradingView chart.
        - kpi: Single metric card with label/value/delta.
        - table: Data table for financial numbers.
        - news_timeline: Vertical list of recent news articles.
        - correlation: Heatmap or comparison chart for multiple tickers.
        - explain_move: AI-generated text explanation of why a stock moved.

        Rules:
        1. Always include a 'price_chart' for the primary ticker.
        2. If the user asks 'Why', always include an 'explain_move' and 'news_timeline'.
        3. If the user asks 'Compare', always include multiple tickers in 'peers'.
        4. Queries must only target the 'comp_financials' table.
        """

        response = self.client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=2000,
            system=system_prompt,
            messages=[
                {"role": "user", "content": question}
            ]
        )

        content = response.content[0].text
        # Extract JSON if Claude adds markdown formatting
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()

        plan_dict = json.loads(content)
        return DashboardPlan(**plan_dict)
