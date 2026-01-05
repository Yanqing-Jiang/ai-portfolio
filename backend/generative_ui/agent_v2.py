# --- A2UI Agent Function/Class Map ---
# Class: A2UIAgentError
#   Role: Typed exception for A2UI agent failures.
#   Called from: backend.generative_ui.routes.dashboard, backend.generative_ui.agent_v2
#   Invokes: n/a
#   Why: Standardizes error reporting for the A2UI pipeline.
# Dataclass: A2UIRunResult
#   Role: Bundle skill execution output + citations for persistence.
#   Called from: backend.generative_ui.agent_v2.A2UIAgent.execute_skill, backend.generative_ui.routes.dashboard
#   Invokes: n/a
#   Why: Provides a consistent payload for streaming + storage.
# Pydantic Model: SkillSelection
#   Role: Structured skill routing output for the model.
#   Called from: backend.generative_ui.agent_v2.A2UIAgent.select_skill, backend.generative_ui.agent_v2.A2UIAgent.selection_from_plan
#   Invokes: pydantic validation
#   Why: Enforces the selection contract used by skill routing.
# Class: A2UIAgent
#   Role: Orchestrate skill selection, tool execution, and A2UI streaming.      
#   Called from: backend.generative_ui.routes.dashboard
#   Invokes: Claude Agent SDK client, conversational_analytics.tools, backend.generative_ui.a2ui.emitter.A2UIMessageEmitter
#   Why: Implements the A2UI-native agent flow with SDK-backed selection and data streaming.
# Method: A2UIAgent.__init__
#   Role: Configure model + skill registry references.
#   Called from: backend.generative_ui.agent_v2.get_a2ui_agent
#   Invokes: backend.generative_ui.skills.get_a2ui_skills
#   Why: Shares cached skill metadata across requests.
# Method: A2UIAgent.select_skill
#   Role: Use the Claude Agent SDK to select a skill and extract slots.
#   Called from: backend.generative_ui.routes.dashboard.create_dashboard        
#   Invokes: A2UISDKWrapper.query
#   Why: Keeps routing logic centralized and model-driven via the SDK.
# Method: A2UIAgent.selection_to_plan
#   Role: Convert a SkillSelection into a plan dict for storage.
#   Called from: backend.generative_ui.routes.dashboard.create_dashboard
#   Invokes: backend.generative_ui.skills.get_a2ui_skill
#   Why: Preserves routing outputs for downstream stream usage.
# Method: A2UIAgent.selection_from_plan
#   Role: Rehydrate a SkillSelection from stored plan JSON.
#   Called from: backend.generative_ui.routes.dashboard.stream_dashboard
#   Invokes: cached skill lookup
#   Why: Avoids re-calling the model during streaming.
# Method: A2UIAgent.stream_dashboard
#   Role: Emit A2UI messages for a full dashboard session.
#   Called from: backend.generative_ui.routes.dashboard.stream_dashboard
#   Invokes: backend.generative_ui.a2ui.emitter.A2UIMessageEmitter, A2UIAgent.execute_skill
#   Why: Provides the streaming backbone for the dashboard UI.
# Method: A2UIAgent.execute_skill
#   Role: Route tool execution based on the selected skill.
#   Called from: backend.generative_ui.agent_v2.A2UIAgent.stream_dashboard, backend.generative_ui.routes.dashboard.handle_action
#   Invokes: A2UIAgent._execute_explain_move/_execute_peer_compare/_execute_margin_analysis/_execute_revenue_trend, A2UIAgent._execute_narrative
#   Why: Keeps tool usage aligned with skill intent.
# Method: A2UIAgent._execute_narrative
#   Role: Generate concise narrative summaries for non-explain-move skills.
#   Called from: backend.generative_ui.agent_v2.A2UIAgent.execute_skill
#   Invokes: conversational_analytics.tools.execute_analysis_tool
#   Why: Supplies summary copy for ExplainMovePanel on metric dashboards.
# Method: A2UIAgent._execute_chart_annotations
#   Role: Build chart annotations from recent news events.
#   Called from: backend.generative_ui.agent_v2.A2UIAgent._execute_margin_analysis, backend.generative_ui.agent_v2.A2UIAgent._execute_revenue_trend
#   Invokes: conversational_analytics.tools.execute_news_tool, backend.generative_ui.utils.date_to_period_label
#   Why: Aligns narrative events with chart periods.
# Method: A2UIAgent._execute_explain_move
#   Role: Run SQL + news tools and assemble explain-move data.
#   Called from: backend.generative_ui.agent_v2.A2UIAgent.execute_skill
#   Invokes: conversational_analytics.tools.execute_sql_tool, conversational_analytics.tools.execute_news_tool, conversational_analytics.tools.execute_analysis_tool
#   Why: Supplies KPIs, news, and explanations for explain-move dashboards.
# Method: A2UIAgent._execute_peer_compare
#   Role: Run SQL tool and compute comparison, chart, and correlation outputs.
#   Called from: backend.generative_ui.agent_v2.A2UIAgent.execute_skill
#   Invokes: conversational_analytics.tools.execute_sql_tool, backend.generative_ui.utils.compute_correlation_matrix
#   Why: Powers peer comparison dashboards with metric series.
# Method: A2UIAgent._execute_margin_analysis
#   Role: Run SQL tool and compute margin KPIs + chart series.
#   Called from: backend.generative_ui.agent_v2.A2UIAgent.execute_skill
#   Invokes: conversational_analytics.tools.execute_sql_tool, A2UIAgent._execute_multi_ticker_margins
#   Why: Supplies margin analysis dashboards with data.
# Method: A2UIAgent._execute_multi_ticker_margins
#   Role: Build margin comparison data for multiple tickers.
#   Called from: backend.generative_ui.agent_v2.A2UIAgent._execute_margin_analysis
#   Invokes: conversational_analytics.tools.execute_sql_tool
#   Why: Provides multi-ticker margin comparisons.
# Method: A2UIAgent._execute_revenue_trend
#   Role: Run SQL tool and compute revenue trend KPIs + chart series.
#   Called from: backend.generative_ui.agent_v2.A2UIAgent.execute_skill
#   Invokes: conversational_analytics.tools.execute_sql_tool
#   Why: Supplies revenue trend dashboards with data.
# Method: A2UIAgent._validate_selection
#   Role: Validate skill selection inputs.
#   Called from: backend.generative_ui.agent_v2.A2UIAgent.select_skill, backend.generative_ui.agent_v2.A2UIAgent.stream_dashboard
#   Invokes: backend.generative_ui.utils.normalize_tickers
#   Why: Guards against unsupported tickers/time ranges.
# Method: A2UIAgent._build_render_context
#   Role: Build context used by layout emitters.
#   Called from: backend.generative_ui.agent_v2.A2UIAgent.stream_dashboard
#   Invokes: backend.generative_ui.agent_v2.A2UIAgent._build_title
#   Why: Keeps layout logic isolated from skill selection details.
# Method: A2UIAgent._build_title
#   Role: Generate dashboard titles based on skill + tickers.
#   Called from: backend.generative_ui.agent_v2.A2UIAgent._build_render_context
#   Invokes: n/a
#   Why: Ensures consistent titles across dashboards.
# Function: get_a2ui_agent
#   Role: Provide a singleton A2UIAgent instance.
#   Called from: backend.generative_ui.routes.dashboard
#   Invokes: backend.generative_ui.agent_v2.A2UIAgent
#   Why: Avoids reloading skills and settings per request.
# --- End A2UI Agent Function/Class Map ---
"""
A2UI-native agent for skill-driven dashboard streaming.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from pydantic import BaseModel, Field

from .config import get_settings
from .skills import A2UISkillMeta, build_a2ui_skill_catalog, get_a2ui_skill, get_a2ui_skills
from .a2ui.emitter import A2UIMessageEmitter, SkillRenderContext
from .sdk_wrapper import A2UISDKWrapper, get_sdk_wrapper, SDKResponse
from .mcp_tools import A2UI_MCP_TOOLS, A2UI_MCP_TOOL_NAMES
from .utils import (
    AVAILABLE_TICKERS,
    normalize_tickers,
    sorted_rows,
    period_label,
    coerce_float,
    metric_series,
    latest_and_previous,
    percentage_change,
    compute_correlation_matrix,
    parse_published_at,
    date_to_period_label,
    map_sentiment,
    map_news_event,
)
from conversational_analytics.tools import execute_sql_tool, execute_news_tool, execute_analysis_tool


ALLOWED_TIME_RANGES = {"1M", "3M", "6M", "1Y"}
DEFAULT_TIME_RANGE = "3M"
DEFAULT_METRIC = "Revenue"
DEFAULT_MODEL = "claude-haiku-4-5-20251001"


class A2UIAgentError(Exception):
    """Raised when the A2UI agent fails."""


@dataclass(frozen=True)
class A2UIRunResult:
    """Container for skill execution results."""

    data_model: Dict[str, Any]
    citations: List[Dict[str, Any]]


@dataclass
class SkillExecutionChunk:
    """
    Chunk emitted during streaming skill execution.
    
    Dataclass: SkillExecutionChunk — holds incremental data for streaming.
    Called from: A2UIAgent.execute_skill_streaming
    Purpose: Enables the runtime to yield partial results (data patches, audit events)
    before the full skill execution completes.
    """
    step: str  # e.g., "sql_query", "news_fetch", "narrative", "complete"
    data_patch: Optional[Dict[str, Any]] = None
    data_path: Optional[str] = None  # JSON path like "/kpis" or "/chart"
    audit_event: Optional[str] = None
    audit_details: Optional[str] = None
    final_result: Optional[A2UIRunResult] = None


class SkillSelection(BaseModel):
    """Structured output for skill routing."""

    skill_id: str = Field(..., description="Selected skill_id from the catalog")
    tickers: List[str] = Field(default_factory=list, description="Ticker symbols referenced by the user")
    metric: str = Field(default=DEFAULT_METRIC, description="Primary metric for comparison")
    time_range: str = Field(default=DEFAULT_TIME_RANGE, description="Requested time range for charts")


class A2UIAgent:
    """A2UI-native agent that streams dashboard messages."""

    def __init__(self, model: Optional[str] = None) -> None:
        """Initialize the agent with model + skill catalog."""
        self.settings = get_settings()
        if not self.settings.claude_api_key:
            raise A2UIAgentError("Claude API key not configured")
        self.model = model or self.settings.claude_model or DEFAULT_MODEL
        self.skills = get_a2ui_skills()
        self.skill_catalog = build_a2ui_skill_catalog(self.skills)
        self.skill_lookup = {skill.skill_id: skill for skill in self.skills}
        self.sdk_wrapper: A2UISDKWrapper = get_sdk_wrapper(
            model=self.model,
            api_key=self.settings.claude_api_key,
        )

    async def select_skill(self, question: str, max_retries: int = 2) -> SkillSelection:
        """Select a skill and slots using the model with retry logic.
        
        Args:
            question: User's question to route.
            max_retries: Number of retries on validation failure (default: 2).
            
        Returns:
            SkillSelection with skill_id, tickers, metric, and time_range.
            
        Raises:
            A2UIAgentError: If skill selection fails after all retries.
        """
        last_error: Optional[Exception] = None
        skill_ids = ", ".join(self.skill_lookup.keys())
        allowed_ranges = ", ".join(sorted(ALLOWED_TIME_RANGES))

        for attempt in range(max_retries):
            try:
                await self.sdk_wrapper.initialize(use_sdk=True, allowed_tools=[])

                system_prompt = (
                    "You route financial dashboard requests to predefined skills. "
                    "Only return compact JSON with fields: "
                    "skill_id (one of the allowed IDs), "
                    "tickers (array of uppercase symbols, min 1, max 6), "
                    "metric (string, default 'Revenue'), "
                    "time_range (one of allowed ranges). "
                    "Do not add prose or code fences."
                )
                user_prompt = (
                    f"Question: {question}\n"
                    f"Allowed skill_ids: {skill_ids}\n"
                    f"Allowed tickers: {', '.join(AVAILABLE_TICKERS)}\n"
                    f"Allowed time_range values: {allowed_ranges}\n"
                    "Respond with JSON only."
                )

                response: SDKResponse = await self.sdk_wrapper.query(
                    prompt=user_prompt,
                    system_prompt=system_prompt,
                    max_tokens=256,
                    temperature=0.3 if attempt else 0.7,
                )
                if response.error:
                    raise A2UIAgentError(response.error)
                parsed = json.loads(response.content or "{}")
                selection = SkillSelection(
                    skill_id=str(parsed.get("skill_id", "")).strip(),
                    tickers=normalize_tickers(parsed.get("tickers") or []),
                    metric=str(parsed.get("metric") or DEFAULT_METRIC),
                    time_range=str(parsed.get("time_range") or DEFAULT_TIME_RANGE),
                )
                self._validate_selection(selection)
                return selection

            except (ValueError, A2UIAgentError, Exception) as exc:
                last_error = exc
                if attempt < max_retries - 1:
                    import logging
                    logging.getLogger(__name__).warning(
                        f"Skill selection attempt {attempt + 1} failed: {exc}. Retrying..."
                    )
                continue

        raise A2UIAgentError(
            f"Skill selection failed after {max_retries} attempts: {last_error}"
        )

    def selection_to_plan(self, selection: SkillSelection) -> Dict[str, Any]:
        """Convert a skill selection into plan JSON for storage."""
        skill = get_a2ui_skill(selection.skill_id)
        tickers = normalize_tickers(selection.tickers)
        if not tickers:
            raise A2UIAgentError("No valid tickers selected")
        primary = tickers[0]
        peers = tickers[1:]
        return {
            "skill_id": selection.skill_id,
            "skill_name": skill.name,
            "layout": skill.layout,
            "widgets": skill.widgets,
            "ticker": primary,
            "peers": peers,
            "tickers": tickers,
            "metric": selection.metric,
            "time_range": selection.time_range,
        }

    def selection_from_plan(self, plan: Mapping[str, Any]) -> SkillSelection:
        """Rehydrate a SkillSelection from stored plan JSON."""
        skill_id = str(plan.get("skill_id", "")).strip()
        if not skill_id:
            raise A2UIAgentError("Plan missing skill_id")
        if skill_id not in self.skill_lookup:
            raise A2UIAgentError(f"Unknown skill_id in plan: {skill_id}")
        tickers = plan.get("tickers") or []
        if not tickers:
            ticker = plan.get("ticker")
            peers = plan.get("peers") or []
            tickers = [t for t in [ticker, *peers] if t]
        normalized = normalize_tickers(tickers)
        if not normalized:
            raise A2UIAgentError("Plan did not contain valid tickers")
        metric = str(plan.get("metric") or DEFAULT_METRIC)
        time_range = str(plan.get("time_range") or DEFAULT_TIME_RANGE)
        return SkillSelection(
            skill_id=skill_id,
            tickers=normalized,
            metric=metric,
            time_range=time_range,
        )

    async def stream_dashboard(
        self,
        question: str,
        surface_id: str,
        *,
        plan: Optional[Mapping[str, Any]] = None,
        on_result: Optional[Callable[[A2UIRunResult], None]] = None,
    ) -> "Iterable[str]":
        """Stream a full A2UI dashboard session as JSON strings."""
        emitter = A2UIMessageEmitter(surface_id=surface_id, catalog_id=self.settings.catalog_id)
        yield emitter.begin_rendering()

        try:
            selection = self.selection_from_plan(plan) if plan else await self.select_skill(question)
            self._validate_selection(selection)
            skill = self.skill_lookup[selection.skill_id]
            context = self._build_render_context(selection, skill)

            components = emitter.build_components_for_skill(skill, context)
            yield emitter.surface_update(components)

            seed_data = {
                "title": context.title,
                "ticker": context.primary_ticker,
                "primary_ticker": context.primary_ticker,
                "tickers": context.tickers,
                "time_range": context.time_range,
                "metric": context.metric,
            }
            yield emitter.data_update(seed_data)

            result = await self.execute_skill(skill, selection)
            yield emitter.data_update(result.data_model)

            if on_result is not None:
                on_result(result)

            yield json.dumps({"done": True})
        except Exception as exc:
            for msg in emitter.error_surface("agent_error", str(exc)):
                yield msg
            yield json.dumps({"done": True})

    async def execute_skill(self, skill: A2UISkillMeta, selection: SkillSelection) -> A2UIRunResult:
        """Execute tools for the selected skill."""
        if skill.skill_id == "a2ui_explain_move":
            result = await self._execute_explain_move(selection)
        elif skill.skill_id == "a2ui_peer_compare":
            result = await self._execute_peer_compare(selection)
        elif skill.skill_id == "a2ui_margin_analysis":
            result = await self._execute_margin_analysis(selection)
        elif skill.skill_id == "a2ui_revenue_trend":
            result = await self._execute_revenue_trend(selection)
        else:
            raise A2UIAgentError(f"Unsupported skill_id: {skill.skill_id}")
        
        # Add narrative summary for all skills except explain_move (which has its own)
        if skill.skill_id != "a2ui_explain_move":
            narrative = await self._execute_narrative(selection, result.data_model)
            result.data_model["explanation"] = narrative
            
        return result

    async def execute_skill_streaming(
        self, skill: A2UISkillMeta, selection: SkillSelection
    ) -> "AsyncGenerator[SkillExecutionChunk, None]":
        """
        Execute a skill and yield incremental streaming chunks.
        
        Method: A2UIAgent.execute_skill_streaming — streaming wrapper for execute_skill.
        Called from: runtime.py (A2UIRuntime.stream_dashboard, A2UIRuntime.process_action)
        Purpose: Enables the runtime to yield partial results (data patches, audit events)
        as skill execution progresses, providing real-time feedback to the UI.
        
        Yields:
            SkillExecutionChunk objects with incremental data patches and the final result.
        """
        from typing import AsyncGenerator  # Import here to avoid circular imports
        
        # Emit start of skill execution
        yield SkillExecutionChunk(
            step="skill_start",
            audit_event="skill_execution_started",
            audit_details=f"Executing {skill.skill_id}",
        )
        
        try:
            # Execute the skill (this is the heavy lifting)
            result = await self.execute_skill(skill, selection)
            
            # Emit data patches for key sections of the result
            if result.data_model.get("kpis"):
                yield SkillExecutionChunk(
                    step="kpis",
                    data_patch=result.data_model["kpis"],
                    data_path="/data/kpis",
                    audit_event="data_loaded",
                    audit_details="KPIs loaded",
                )

            if result.data_model.get("chart"):
                yield SkillExecutionChunk(
                    step="chart",
                    data_patch=result.data_model["chart"],
                    data_path="/data/chart",
                    audit_event="data_loaded",
                    audit_details="Chart data loaded",
                )

            if result.data_model.get("table"):
                yield SkillExecutionChunk(
                    step="table",
                    data_patch=result.data_model["table"],
                    data_path="/data/table",
                    audit_event="data_loaded",
                    audit_details="Table data loaded",
                )

            if result.data_model.get("explanation"):
                yield SkillExecutionChunk(
                    step="narrative",
                    data_patch=result.data_model["explanation"],
                    data_path="/data/explanation",
                    audit_event="narrative_generated",
                    audit_details="AI narrative complete",
                )

            # Emit final complete chunk with the full result
            yield SkillExecutionChunk(
                step="complete",
                data_patch=result.data_model,
                data_path="/data",
                audit_event="skill_execution_complete",
                audit_details=f"{skill.skill_id} execution complete",
                final_result=result,
            )
            
        except Exception as exc:
            yield SkillExecutionChunk(
                step="error",
                audit_event="skill_execution_error",
                audit_details=str(exc),
            )
            raise

    async def _execute_narrative(self, selection: SkillSelection, data_model: Dict[str, Any]) -> Dict[str, Any]:
        """Generate a concise AI narrative summarizing the data results."""
        ticker = selection.tickers[0] if selection.tickers else "the company"
        
        # Prepare a concise data summary for the LLM
        # We exclude large lists like table rows to keep the prompt small
        data_summary = {
            "ticker": ticker,
            "metric": selection.metric,
            "kpis": data_model.get("kpis", {}),
            "correlation": data_model.get("correlation", {}),
            "tickers": data_model.get("tickers", []),
        }

        system_prompt = (
            "You are a Senior Financial Analyst briefing a high-stakes trader. "
            "Write a concise, 2-3 sentence narrative summary based on the provided data. "
            "Focus on the most interesting trend or anomaly. "
            "Keep it professional, data-driven, and very concise. "
            "Do not use markdown formatting like bolding or lists. "
            f"The user asked about: {selection.skill_id} for {ticker}."
        )
        
        user_msg = f"Data Summary: {json.dumps(data_summary)}"
        
        try:
            # We reuse execute_analysis_tool if it's available and suitable, 
            # or we could use _call_claude directly. 
            # Given explain_move uses execute_analysis_tool, let's stick to that for consistency
            # but wrap it to provide the specific format ExplainPanel expects.
            
            findings = [f"Analyzing {selection.metric} data for {ticker}."]
            for k, v in data_summary["kpis"].items():
                findings.append(f"{k.replace('_', ' ').title()}: {v}")

            analysis_result = await execute_analysis_tool(
                data_summary=f"Financial data for {ticker}.",
                key_findings=findings,
                trend_direction="neutral",
            )
            
            text = "Analysis pending."
            if analysis_result.get("success"):
                text = analysis_result.get("analysis", {}).get("summary", text)
            
            return {
                "title": f"Insight: {selection.metric} for {ticker}",
                "text": text,
                "factors": [],
                "citations": [],
            }
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning("Narrative generation failed: %s", e)
            return {
                "title": "Analysis Summary",
                "text": "Data visualized below. Summarization currently unavailable.",
                "factors": [],
                "citations": [],
            }

    async def _execute_chart_annotations(self, tickers: List[str], period_set: set[str]) -> List[Dict[str, Any]]:
        """Fetch news and map to chart annotations if they land on valid chart periods."""
        annotations = []
        for ticker in tickers[:2]: # Limit to first 2 tickers to keep it snappy
            try:
                news = await execute_news_tool(ticker=ticker, limit=10)
                if news.get("success"):
                    for article in news.get("articles", []):
                        pub_date = article.get("published_at")
                        if not pub_date: continue
                        
                        period = date_to_period_label(str(pub_date))
                        if period in period_set:
                            annotations.append({
                                "period": period,
                                "ticker": ticker,
                                "label": "News",
                                "details": article.get("title", "Market update")
                            })
                            # Only one annotation per period per ticker to avoid clutter
                            period_set.remove(period)
            except Exception:
                continue
        return annotations

    async def _execute_explain_move(self, selection: SkillSelection) -> A2UIRunResult:
        """Fetch KPI + news data for explain-move dashboards."""
        ticker = normalize_tickers(selection.tickers)[0]
        sql = (
            "SELECT ticker, calendar_year, calendar_quarter_num, calendar_quarter, metric, value "
            "FROM comp_financials "
            f"WHERE ticker = '{ticker}' AND metric IN ('Revenue', 'Net Income', 'Gross Margin') "
            "ORDER BY calendar_year DESC, calendar_quarter_num DESC "
            "LIMIT 24"
        )
        sql_result = await execute_sql_tool(sql, reason="Explain price movement KPIs")
        if not sql_result.get("success"):
            raise A2UIAgentError(sql_result.get("error", "SQL query failed"))

        rows = sorted_rows(sql_result.get("rows", []))
        revenue_series = metric_series(rows, "Revenue")
        net_income_series = metric_series(rows, "Net Income")
        gross_margin_series = metric_series(rows, "Gross Margin")

        revenue_latest, revenue_prev = latest_and_previous(revenue_series)
        net_latest, net_prev = latest_and_previous(net_income_series)
        gross_latest, _ = latest_and_previous(gross_margin_series)

        revenue_delta = percentage_change(revenue_latest, revenue_prev)
        net_delta = percentage_change(net_latest, net_prev)

        news_result = await execute_news_tool(ticker=ticker, limit=5)
        if not news_result.get("success"):
            raise A2UIAgentError(news_result.get("error", "News tool failed"))

        articles = news_result.get("articles", [])
        events = [map_news_event(article) for article in articles]
        factors = [
            {
                "title": article.get("title", ""),
                "description": article.get("summary", ""),
                "impact": map_sentiment(coerce_float(article.get("sentiment_score")), article.get("sentiment_label")),
                "source": article.get("source", ""),
            }
            for article in articles[:3]
        ]
        citations = [
            {
                "title": article.get("title", ""),
                "url": article.get("url", ""),
                "date": parse_published_at(str(article.get("published_at") or "")),
            }
            for article in articles
        ]

        findings = []
        if revenue_delta is not None:
            findings.append(f"Revenue changed {revenue_delta:.2f}% quarter-over-quarter.")
        if net_delta is not None:
            findings.append(f"Net income changed {net_delta:.2f}% quarter-over-quarter.")
        if articles:
            findings.append(f"News sentiment leans {news_result.get('aggregate_label', 'Neutral')}.")

        analysis_result = await execute_analysis_tool(
            data_summary=f"Summary of recent metrics and news for {ticker}.",
            key_findings=findings or ["Recent financial metrics were reviewed."],
            trend_direction="mixed",
        )
        analysis_text = ""
        if analysis_result.get("success"):
            analysis = analysis_result.get("analysis", {})
            analysis_text = analysis.get("summary", "")

        data_model = {
            "ticker": ticker,
            "kpis": {
                "revenue": revenue_latest or 0,
                "revenue_delta": revenue_delta or 0,
                "net_income": net_latest or 0,
                "net_income_delta": net_delta or 0,
                "gross_margin": gross_latest or 0,
            },
            "news": {"events": events},
            "explanation": {
                "title": f"{ticker} Movement Drivers",
                "text": analysis_text or "Analysis pending.",
                "factors": factors,
                "citations": citations,
            },
        }
        return A2UIRunResult(data_model=data_model, citations=citations)

    async def _execute_peer_compare(self, selection: SkillSelection) -> A2UIRunResult:
        """Fetch comparison data for peer dashboards."""
        tickers = normalize_tickers(selection.tickers)
        if len(tickers) < 2:
            raise A2UIAgentError("Peer comparison requires at least two tickers")
        tickers_sql = ", ".join([f"'{t}'" for t in tickers])
        metric = selection.metric or DEFAULT_METRIC
        sql = (
            "SELECT ticker, calendar_year, calendar_quarter_num, calendar_quarter, metric, value "
            "FROM comp_financials "
            f"WHERE ticker IN ({tickers_sql}) AND metric = '{metric}' "
            "ORDER BY ticker, calendar_year DESC, calendar_quarter_num DESC "
            "LIMIT 200"
        )
        sql_result = await execute_sql_tool(sql, reason="Peer comparison metrics")
        if not sql_result.get("success"):
            raise A2UIAgentError(sql_result.get("error", "SQL query failed"))

        rows = sorted_rows(sql_result.get("rows", []))
        rows_by_ticker: Dict[str, List[Mapping[str, Any]]] = {ticker: [] for ticker in tickers}
        for row in rows:
            ticker = row.get("ticker")
            if ticker in rows_by_ticker:
                rows_by_ticker[ticker].append(row)

        table_rows = []
        chart_series: List[Dict[str, Any]] = []
        series_by_ticker: Dict[str, List[float]] = {}
        for ticker, ticker_rows in rows_by_ticker.items():
            series = metric_series(ticker_rows, metric)
            latest, _previous = latest_and_previous(series)
            yoy_change = None
            if len(series) > 4:
                yoy_value = coerce_float(series[4].get("value"))
                yoy_change = percentage_change(latest, yoy_value)
            series_values = [entry["value"] for entry in series]
            series_by_ticker[ticker] = series_values
            chart_series.append({"ticker": ticker, "data": series})
            table_rows.append(
                {
                    "ticker": ticker,
                    "latest_value": latest if latest is not None else 0,
                    "yoy_change": yoy_change,
                }
            )

        metric_lower = metric.lower()
        value_type = "percentage" if "margin" in metric_lower or "rate" in metric_lower else "currency"
        columns = [
            {"key": "ticker", "label": "Ticker", "type": "string"},
            {"key": "latest_value", "label": f"Latest {metric}", "type": value_type},
            {"key": "yoy_change", "label": "YoY %", "type": "percentage"},
        ]

        correlation = compute_correlation_matrix(series_by_ticker, tickers)

        data_model = {
            "tickers": tickers,
            "primary_ticker": tickers[0],
            "table": {"columns": columns, "rows": table_rows},
            "correlation": {"tickers": tickers, "matrix": correlation},
            "chart": {"series": chart_series, "annotations": []},
        }
        return A2UIRunResult(data_model=data_model, citations=[])

    async def _execute_margin_analysis(self, selection: SkillSelection) -> A2UIRunResult:
        """Fetch margin KPIs and history. Supports single or multi-ticker margin comparisons."""
        tickers = normalize_tickers(selection.tickers)
        if not tickers:
            raise A2UIAgentError("No valid tickers for margin analysis")

        # Multi-ticker margin comparison
        if len(tickers) > 1:
            return await self._execute_multi_ticker_margins(tickers)

        # Single ticker margin analysis (original logic)
        ticker = tickers[0]
        sql = (
            "SELECT ticker, calendar_year, calendar_quarter_num, calendar_quarter, metric, value "
            "FROM comp_financials "
            f"WHERE ticker = '{ticker}' AND metric IN ('Gross Margin', 'Operating Margin', 'Net Income', 'Revenue') "
            "ORDER BY calendar_year DESC, calendar_quarter_num DESC "
            "LIMIT 48"
        )
        sql_result = await execute_sql_tool(sql, reason="Margin analysis")
        if not sql_result.get("success"):
            raise A2UIAgentError(sql_result.get("error", "SQL query failed"))

        rows = sorted_rows(sql_result.get("rows", []))
        gross_series = metric_series(rows, "Gross Margin")
        operating_series = metric_series(rows, "Operating Margin")
        revenue_series = metric_series(rows, "Revenue")
        net_income_series = metric_series(rows, "Net Income")
        net_income_by_period = {entry["period"]: entry["value"] for entry in net_income_series}

        gross_latest, _ = latest_and_previous(gross_series)
        operating_latest, _ = latest_and_previous(operating_series)

        net_margin_series: List[Dict[str, Any]] = []
        for entry in revenue_series:
            period = entry["period"]
            revenue_value = entry["value"]
            net_value = net_income_by_period.get(period)
            if net_value is None or revenue_value == 0:
                continue
            net_margin_series.append({"period": period, "value": (net_value / revenue_value) * 100})

        net_latest, _ = latest_and_previous(net_margin_series)

        table_rows = []
        for entry in revenue_series[:8]:
            period = entry["period"]
            table_rows.append(
                {
                    "period": period,
                    "gross_margin": next((item["value"] for item in gross_series if item["period"] == period), None),
                    "operating_margin": next((item["value"] for item in operating_series if item["period"] == period), None),
                    "net_margin": next((item["value"] for item in net_margin_series if item["period"] == period), None),
                }
            )

        columns = [
            {"key": "period", "label": "Period", "type": "string"},
            {"key": "gross_margin", "label": "Gross Margin", "type": "percentage"},
            {"key": "operating_margin", "label": "Operating Margin", "type": "percentage"},
            {"key": "net_margin", "label": "Net Margin", "type": "percentage"},
        ]

        chart_series = [
            {"ticker": "Gross Margin", "data": gross_series},
            {"ticker": "Operating Margin", "data": operating_series},
            {"ticker": "Net Margin", "data": net_margin_series},
        ]

        data_model = {
            "ticker": ticker,
            "kpis": {
                "gross_margin": gross_latest or 0,
                "operating_margin": operating_latest or 0,
                "net_margin": net_latest or 0,
            },
            "table": {"columns": columns, "rows": table_rows},
            "chart": {
                "series": chart_series,
                "annotations": [],
            },
        }

        # Add annotations to chart
        periods = {entry["period"] for entry in revenue_series}
        data_model["chart"]["annotations"] = await self._execute_chart_annotations([ticker], periods)
        
        return A2UIRunResult(data_model=data_model, citations=[])

    async def _execute_multi_ticker_margins(self, tickers: List[str]) -> A2UIRunResult:
        """Fetch margin comparison data for multiple tickers."""
        tickers_sql = ", ".join([f"'{t}'" for t in tickers])
        sql = (
            "SELECT ticker, calendar_year, calendar_quarter_num, calendar_quarter, metric, value "
            "FROM comp_financials "
            f"WHERE ticker IN ({tickers_sql}) AND metric IN ('Gross Margin', 'Operating Margin', 'Net Income', 'Revenue') "
            "ORDER BY ticker, calendar_year DESC, calendar_quarter_num DESC "
            "LIMIT 200"
        )
        sql_result = await execute_sql_tool(sql, reason="Multi-ticker margin comparison")
        if not sql_result.get("success"):
            raise A2UIAgentError(sql_result.get("error", "SQL query failed"))

        rows = sorted_rows(sql_result.get("rows", []))
        rows_by_ticker: Dict[str, List[Mapping[str, Any]]] = {ticker: [] for ticker in tickers}
        for row in rows:
            ticker = row.get("ticker")
            if ticker in rows_by_ticker:
                rows_by_ticker[ticker].append(row)

        table_rows = []
        chart_series: List[Dict[str, Any]] = []
        for ticker, ticker_rows in rows_by_ticker.items():
            gross_series = metric_series(ticker_rows, "Gross Margin")
            operating_series = metric_series(ticker_rows, "Operating Margin")
            revenue_series = metric_series(ticker_rows, "Revenue")
            net_income_series = metric_series(ticker_rows, "Net Income")
            net_income_by_period = {entry["period"]: entry["value"] for entry in net_income_series}

            gross_latest, _ = latest_and_previous(gross_series)
            operating_latest, _ = latest_and_previous(operating_series)

            net_margin_series: List[Dict[str, Any]] = []
            for entry in revenue_series:
                period = entry["period"]
                revenue_value = entry["value"]
                net_value = net_income_by_period.get(period)
                if net_value is None or revenue_value == 0:
                    continue
                net_margin_series.append({"period": period, "value": (net_value / revenue_value) * 100})
            net_margin = net_margin_series[0]["value"] if net_margin_series else None
            if net_margin_series:
                chart_series.append({"ticker": ticker, "data": net_margin_series})

            table_rows.append({
                "ticker": ticker,
                "gross_margin": gross_latest or 0,
                "operating_margin": operating_latest or 0,
                "net_margin": net_margin or 0,
            })

        columns = [
            {"key": "ticker", "label": "Ticker", "type": "string"},
            {"key": "gross_margin", "label": "Gross Margin", "type": "percentage"},
            {"key": "operating_margin", "label": "Operating Margin", "type": "percentage"},
            {"key": "net_margin", "label": "Net Margin", "type": "percentage"},
        ]

        data_model = {
            "tickers": tickers,
            "primary_ticker": tickers[0],
            "kpis": {
                "gross_margin": table_rows[0]["gross_margin"] if table_rows else 0,
                "operating_margin": table_rows[0]["operating_margin"] if table_rows else 0,
                "net_margin": table_rows[0]["net_margin"] if table_rows else 0,
            },
            "table": {"columns": columns, "rows": table_rows},
            "chart": {"series": chart_series, "annotations": []},
        }
        return A2UIRunResult(data_model=data_model, citations=[])

    async def _execute_revenue_trend(self, selection: SkillSelection) -> A2UIRunResult:
        """Fetch revenue trend metrics."""
        ticker = normalize_tickers(selection.tickers)[0]
        sql = (
            "SELECT ticker, calendar_year, calendar_quarter_num, calendar_quarter, metric, value "
            "FROM comp_financials "
            f"WHERE ticker = '{ticker}' AND metric = 'Revenue' "
            "ORDER BY calendar_year DESC, calendar_quarter_num DESC "
            "LIMIT 24"
        )
        sql_result = await execute_sql_tool(sql, reason="Revenue trend")
        if not sql_result.get("success"):
            raise A2UIAgentError(sql_result.get("error", "SQL query failed"))

        rows = sorted_rows(sql_result.get("rows", []))
        revenue_series = metric_series(rows, "Revenue")
        latest, previous = latest_and_previous(revenue_series)

        yoy_growth = None
        if len(revenue_series) > 4:
            yoy_value = revenue_series[4].get("value")
            yoy_growth = percentage_change(latest, coerce_float(yoy_value))

        columns = [
            {"key": "period", "label": "Period", "type": "string"},
            {"key": "revenue", "label": "Revenue", "type": "currency"},
        ]
        rows_table = [
            {"period": entry["period"], "revenue": entry["value"]}
            for entry in revenue_series[:8]
        ]

        chart_series = [{"ticker": ticker, "data": revenue_series}]

        data_model = {
            "ticker": ticker,
            "kpis": {
                "latest_revenue": latest or 0,
                "yoy_growth": yoy_growth or 0,
            },
            "table": {"columns": columns, "rows": rows_table},
            "chart": {
                "series": chart_series,
                "annotations": [],
            },
        }

        # Add annotations to chart
        periods = {entry["period"] for entry in revenue_series}
        data_model["chart"]["annotations"] = await self._execute_chart_annotations([ticker], periods)
        
        return A2UIRunResult(data_model=data_model, citations=[])

    def _validate_selection(self, selection: SkillSelection) -> None:
        if selection.skill_id not in self.skill_lookup:
            raise A2UIAgentError(f"Unknown skill_id: {selection.skill_id}")
        if selection.time_range not in ALLOWED_TIME_RANGES:
            raise A2UIAgentError(f"Invalid time_range: {selection.time_range}")
        normalized = normalize_tickers(selection.tickers)
        if not normalized:
            raise A2UIAgentError("No valid tickers provided")
        selection.tickers = normalized

    def _build_render_context(self, selection: SkillSelection, skill: A2UISkillMeta) -> SkillRenderContext:
        tickers = normalize_tickers(selection.tickers)
        primary = tickers[0] if tickers else ""
        title = self._build_title(skill, tickers, selection.metric)
        return SkillRenderContext(
            title=title,
            primary_ticker=primary,
            tickers=tickers,
            time_range=selection.time_range,
            metric=selection.metric or DEFAULT_METRIC,
        )

    def _build_title(self, skill: A2UISkillMeta, tickers: Sequence[str], metric: str) -> str:
        if skill.skill_id == "a2ui_peer_compare":
            return f"Comparing {', '.join(tickers)}"
        if skill.skill_id == "a2ui_margin_analysis":
            if len(tickers) > 1:
                return f"{' vs '.join(tickers)} Margin Comparison"
            return f"{tickers[0]} Margin Analysis" if tickers else "Margin Analysis"
        if skill.skill_id == "a2ui_revenue_trend":
            return f"{tickers[0]} Revenue Trend" if tickers else "Revenue Trend"
        return f"{tickers[0]} Price Movement" if tickers else "Price Movement Analysis"


_agent_instance: Optional[A2UIAgent] = None


def get_a2ui_agent() -> A2UIAgent:
    """Get or create the singleton A2UI agent."""
    global _agent_instance
    if _agent_instance is None:
        _agent_instance = A2UIAgent()
    return _agent_instance
