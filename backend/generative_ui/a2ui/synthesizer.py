"""
Dashboard Synthesizer

Uses Gemini 1.5 Pro to synthesize raw tool outputs into A2UI DataModel updates.
"""

from __future__ import annotations
import json
import google.generativeai as genai
from typing import Any, Dict, List, Optional
from ..models.dashboard_plan import DashboardPlan
from ..config import settings

class DashboardSynthesizer:
    """
    Synthesizes tool outputs (SQL results, News) into structured A2UI data model updates.
    """

    def __init__(self, api_key: Optional[str] = None):
        genai.configure(api_key=api_key or settings.GEMINI_API_KEY)
        self.model = genai.GenerativeModel('gemini-1.5-pro')

    async def synthesize(self, plan: DashboardPlan, tool_results: Dict[str, Any]) -> Dict[str, Any]:
        """
        Merge tool results and generate a synthesized data model.
        """
        prompt = f"""
        You are a financial data analyst. You have a dashboard plan and raw results from various tools (SQL queries, news results).
        Your job is to synthesize these results into a structured JSON for an A2UI Data Model.

        DASHBOARD PLAN:
        {plan.model_dump_json(indent=2)}

        TOOL RESULTS:
        {json.dumps(tool_results, indent=2)}

        Output a JSON object that maps to the Data Model paths expected by the widgets in the plan.
        Follow these path conventions:
        - /data/price: Current stock price (number)
        - /data/changePercent: Daily percentage change (number)
        - /data/volume: Trading volume (number)
        - /data/summary: A 1-2 paragraph synthesis for the 'explain_move' widget
        - /data/factors: An array of factors for 'explain_move' [{{ "title": "...", "description": "...", "impact": "positive|negative|neutral" }}]
        - /data/news: Array of synthesized news items for 'news_timeline'
        - /data/table: Rows for the 'table' widget

        Respond ONLY with the RAW JSON.
        """

        response = self.model.generate_content(prompt)
        content = response.text.strip()
        
        # Extract JSON if Gemini adds markdown formatting
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()

        try:
            return json.loads(content)
        except Exception as e:
            print(f"Error parsing Gemini synthesis: {e}")
            return {{}}
