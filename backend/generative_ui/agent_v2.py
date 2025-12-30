# --- A2UI Agent Function/Class Map ---
# Class: A2UIAgentError
#   Role: Typed exception for A2UI agent failures.
#   Called from: backend.generative_ui.routes.dashboard
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
# Function: _build_skill_selection_tool
#   Role: Build the Claude tool schema for skill selection.
#   Called from: backend.generative_ui.agent_v2.A2UIAgent.select_skill
#   Invokes: n/a
#   Why: Encapsulates the selection tool schema with allowed skill IDs.
# Function: _normalize_tickers
#   Role: Filter and normalize tickers to the allowed universe.
#   Called from: backend.generative_ui.agent_v2.A2UIAgent._validate_selection, backend.generative_ui.agent_v2.A2UIAgent.selection_from_plan
#   Invokes: n/a
#   Why: Keeps tool queries within supported tickers.
# Function: _row_sort_key
#   Role: Produce a sortable key for comp_financials rows.
#   Called from: backend.generative_ui.agent_v2._sorted_rows, backend.generative_ui.agent_v2._metric_series
#   Invokes: n/a
#   Why: Ensures time-series values are ordered consistently.
# Function: _sorted_rows
#   Role: Sort comp_financials rows descending by period.
#   Called from: backend.generative_ui.agent_v2.A2UIAgent._execute_* methods
#   Invokes: backend.generative_ui.agent_v2._row_sort_key
#   Why: Simplifies latest value extraction.
# Function: _period_label
#   Role: Build a readable period label from row metadata.
#   Called from: backend.generative_ui.agent_v2.A2UIAgent._execute_* methods
#   Invokes: n/a
#   Why: Feeds DataTable period columns.
# Function: _coerce_float
#   Role: Convert numeric inputs to float when possible.
#   Called from: backend.generative_ui.agent_v2._metric_series
#   Invokes: n/a
#   Why: Normalizes SQL values for calculations.
# Function: _metric_series
#   Role: Extract ordered metric values from SQL rows.
#   Called from: backend.generative_ui.agent_v2.A2UIAgent._execute_* methods
#   Invokes: backend.generative_ui.agent_v2._sorted_rows, backend.generative_ui.agent_v2._coerce_float
#   Why: Provides consistent time-series inputs.
# Function: _latest_and_previous
#   Role: Return latest + previous numeric values from a series.
#   Called from: backend.generative_ui.agent_v2.A2UIAgent._execute_* methods
#   Invokes: n/a
#   Why: Enables delta calculations for KPIs.
# Function: _percentage_change
#   Role: Compute percentage change between two values.
#   Called from: backend.generative_ui.agent_v2.A2UIAgent._execute_* methods
#   Invokes: n/a
#   Why: Standardizes percent delta logic.
# Function: _compute_correlation_matrix
#   Role: Generate a Pearson correlation matrix from series data.
#   Called from: backend.generative_ui.agent_v2.A2UIAgent._execute_peer_compare
#   Invokes: math.sqrt
#   Why: Supplies correlation data for A2UI visualization.
# Function: _parse_published_at
#   Role: Normalize news timestamps into ISO-like strings.
#   Called from: backend.generative_ui.agent_v2._map_news_event
#   Invokes: datetime.strptime
#   Why: Produces consistent NewsTimeline dates.
# Function: _map_sentiment
#   Role: Map sentiment scores/labels to positive/neutral/negative.
#   Called from: backend.generative_ui.agent_v2._map_news_event
#   Invokes: n/a
#   Why: Aligns sentiment values with frontend styling.
# Function: _map_news_event
#   Role: Convert news tool payloads into NewsTimeline event objects.
#   Called from: backend.generative_ui.agent_v2.A2UIAgent._execute_explain_move
#   Invokes: backend.generative_ui.agent_v2._map_sentiment, backend.generative_ui.agent_v2._parse_published_at
#   Why: Standardizes news data for the UI.
# Function: _extract_tool_input
#   Role: Extract the tool input payload from a Claude response.
#   Called from: backend.generative_ui.agent_v2.A2UIAgent.select_skill
#   Invokes: n/a
#   Why: Pulls structured selection output from Claude tool-use blocks.
# Class: A2UIAgent
#   Role: Orchestrate skill selection, tool execution, and A2UI streaming.
#   Called from: backend.generative_ui.routes.dashboard
#   Invokes: anthropic ClaudeSDKClient, conversational_analytics.tools, backend.generative_ui.a2ui.emitter.A2UIMessageEmitter
#   Why: Implements the A2UI-native agent flow.
# Method: A2UIAgent.__init__
#   Role: Configure model + skill registry references.
#   Called from: backend.generative_ui.agent_v2.get_a2ui_agent
#   Invokes: backend.generative_ui.skills.get_a2ui_skills
#   Why: Shares cached skill metadata across requests.
# Method: A2UIAgent.select_skill
#   Role: Use the model to select a skill and extract slots.
#   Called from: backend.generative_ui.routes.dashboard.create_dashboard
#   Invokes: anthropic ClaudeSDKClient.messages.create
#   Why: Keeps routing logic centralized and model-driven.
# Method: A2UIAgent.selection_to_plan
#   Role: Convert a SkillSelection into a plan dict for storage.
#   Called from: backend.generative_ui.routes.dashboard.create_dashboard
#   Invokes: backend.generative_ui.skills.get_a2ui_skill
#   Why: Preserves routing outputs for downstream stream usage.
# Method: A2UIAgent.selection_from_plan
#   Role: Rehydrate a SkillSelection from stored plan JSON.
#   Called from: backend.generative_ui.routes.dashboard.stream_dashboard
#   Invokes: backend.generative_ui.skills.get_a2ui_skill
#   Why: Avoids re-calling the model during streaming.
# Method: A2UIAgent.stream_dashboard
#   Role: Emit A2UI messages for a full dashboard session.
#   Called from: backend.generative_ui.routes.dashboard.stream_dashboard
#   Invokes: backend.generative_ui.a2ui.emitter.A2UIMessageEmitter, A2UIAgent.execute_skill
#   Why: Provides the streaming backbone for the dashboard UI.
# Method: A2UIAgent.execute_skill
#   Role: Route tool execution based on the selected skill.
#   Called from: backend.generative_ui.agent_v2.A2UIAgent.stream_dashboard
#   Invokes: A2UIAgent._execute_explain_move/_execute_peer_compare/_execute_margin_analysis/_execute_revenue_trend
#   Why: Keeps tool usage aligned with skill intent.
# Method: A2UIAgent._execute_explain_move
#   Role: Run SQL + news tools and assemble explain-move data.
#   Called from: backend.generative_ui.agent_v2.A2UIAgent.execute_skill
#   Invokes: conversational_analytics.tools.execute_sql_tool, conversational_analytics.tools.execute_news_tool, conversational_analytics.tools.execute_analysis_tool
#   Why: Supplies KPIs, news, and explanations for explain-move dashboards.
# Method: A2UIAgent._execute_peer_compare
#   Role: Run SQL tool and compute comparison/correlation outputs.
#   Called from: backend.generative_ui.agent_v2.A2UIAgent.execute_skill
#   Invokes: conversational_analytics.tools.execute_sql_tool, backend.generative_ui.agent_v2._compute_correlation_matrix
#   Why: Powers peer comparison dashboards.
# Method: A2UIAgent._execute_margin_analysis
#   Role: Run SQL tool and compute margin KPIs + history.
#   Called from: backend.generative_ui.agent_v2.A2UIAgent.execute_skill
#   Invokes: conversational_analytics.tools.execute_sql_tool
#   Why: Supplies margin analysis dashboards with data.
# Method: A2UIAgent._execute_revenue_trend
#   Role: Run SQL tool and compute revenue trend KPIs + table.
#   Called from: backend.generative_ui.agent_v2.A2UIAgent.execute_skill
#   Invokes: conversational_analytics.tools.execute_sql_tool
#   Why: Supplies revenue trend dashboards with data.
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
import math
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from pydantic import BaseModel, Field

try:
    import anthropic  # type: ignore
    _anthropic_import_error: Optional[ImportError] = None
except ImportError as exc:  # pragma: no cover - optional dependency
    anthropic = None  # type: ignore
    _anthropic_import_error = exc

try:
    from anthropic import ClaudeSDKClient, ClaudeAgentOptions  # type: ignore
except Exception:  # pragma: no cover - SDK may be unavailable
    ClaudeSDKClient = None  # type: ignore
    ClaudeAgentOptions = None  # type: ignore

from .config import get_settings
from .skills import A2UISkillMeta, build_a2ui_skill_catalog, get_a2ui_skill, get_a2ui_skills
from .a2ui.emitter import A2UIMessageEmitter, SkillRenderContext
from conversational_analytics.tools import execute_sql_tool, execute_news_tool, execute_analysis_tool
from conversational_analytics.sdk_assets import (
    CLAUDE_DIR,
    get_allowed_tools,
    load_project_settings,
    should_use_sdk_assets,
)


AVAILABLE_TICKERS = ["AMD", "AVGO", "INTC", "MU", "NVDA", "QCOM", "TXN"]
ALLOWED_TIME_RANGES = {"1M", "3M", "6M", "1Y"}
DEFAULT_TIME_RANGE = "3M"
DEFAULT_METRIC = "Revenue"
DEFAULT_MODEL = "claude-haiku-4-5-20251001"
SKILL_SELECTION_TOOL_NAME = "select_a2ui_skill"


class A2UIAgentError(Exception):
    """Raised when the A2UI agent fails."""


@dataclass(frozen=True)
class A2UIRunResult:
    """Container for skill execution results."""

    data_model: Dict[str, Any]
    citations: List[Dict[str, Any]]


class SkillSelection(BaseModel):
    """Structured output for skill routing."""

    skill_id: str = Field(..., description="Selected skill_id from the catalog")
    tickers: List[str] = Field(default_factory=list, description="Ticker symbols referenced by the user")
    metric: str = Field(default=DEFAULT_METRIC, description="Primary metric for comparison")
    time_range: str = Field(default=DEFAULT_TIME_RANGE, description="Requested time range for charts")


def _build_skill_selection_tool(skill_ids: Sequence[str]) -> Dict[str, Any]:
    return {
        "name": SKILL_SELECTION_TOOL_NAME,
        "description": "Select the best A2UI skill and extract slots.",
        "input_schema": {
            "type": "object",
            "properties": {
                "skill_id": {
                    "type": "string",
                    "enum": list(skill_ids),
                    "description": "Selected skill_id from the catalog",
                },
                "tickers": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Ticker symbols mentioned by the user",
                },
                "metric": {
                    "type": "string",
                    "description": "Primary metric for comparison (e.g., Revenue, Net Income)",
                },
                "time_range": {
                    "type": "string",
                    "enum": sorted(ALLOWED_TIME_RANGES),
                    "description": "Requested chart time range",
                },
            },
            "required": ["skill_id", "tickers", "metric", "time_range"],
        },
    }


def _normalize_tickers(tickers: Iterable[str]) -> List[str]:
    normalized = []
    for ticker in tickers:
        if not ticker:
            continue
        candidate = str(ticker).upper().strip()
        if candidate and candidate in AVAILABLE_TICKERS and candidate not in normalized:
            normalized.append(candidate)
    return normalized


def _row_sort_key(row: Mapping[str, Any]) -> Tuple[int, int]:
    year = int(row.get("calendar_year") or 0)
    quarter = int(row.get("calendar_quarter_num") or 0)
    return (year, quarter)


def _sorted_rows(rows: Sequence[Mapping[str, Any]]) -> List[Mapping[str, Any]]:
    return sorted(rows, key=_row_sort_key, reverse=True)


def _period_label(row: Mapping[str, Any]) -> str:
    year = row.get("calendar_year")
    quarter = row.get("calendar_quarter_num")
    if year and quarter:
        return f"Q{quarter} {year}"
    if year:
        return str(year)
    return "Unknown"


def _coerce_float(value: Any) -> Optional[float]:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _metric_series(rows: Sequence[Mapping[str, Any]], metric: str) -> List[Dict[str, Any]]:
    filtered = [row for row in rows if str(row.get("metric", "")) == metric]
    series: List[Dict[str, Any]] = []
    for row in _sorted_rows(filtered):
        value = _coerce_float(row.get("value"))
        if value is None:
            continue
        series.append({"period": _period_label(row), "value": value})
    return series


def _latest_and_previous(series: Sequence[Mapping[str, Any]]) -> Tuple[Optional[float], Optional[float]]:
    if not series:
        return None, None
    latest = _coerce_float(series[0].get("value"))
    previous = _coerce_float(series[1].get("value")) if len(series) > 1 else None
    return latest, previous


def _percentage_change(current: Optional[float], previous: Optional[float]) -> Optional[float]:
    if current is None or previous is None:
        return None
    if previous == 0:
        return None
    return (current - previous) / previous * 100


def _compute_correlation_matrix(series_by_ticker: Mapping[str, Sequence[float]], tickers: Sequence[str]) -> List[List[float]]:
    matrix: List[List[float]] = []
    for i, ticker_a in enumerate(tickers):
        row: List[float] = []
        series_a = list(series_by_ticker.get(ticker_a, []))
        for j, ticker_b in enumerate(tickers):
            if i == j:
                row.append(1.0)
                continue
            series_b = list(series_by_ticker.get(ticker_b, []))
            n = min(len(series_a), len(series_b))
            if n < 2:
                row.append(0.0)
                continue
            a = series_a[:n]
            b = series_b[:n]
            mean_a = sum(a) / n
            mean_b = sum(b) / n
            cov = sum((a[k] - mean_a) * (b[k] - mean_b) for k in range(n)) / n
            var_a = sum((a[k] - mean_a) ** 2 for k in range(n)) / n
            var_b = sum((b[k] - mean_b) ** 2 for k in range(n)) / n
            if var_a == 0 or var_b == 0:
                row.append(0.0)
                continue
            corr = cov / math.sqrt(var_a * var_b)
            row.append(round(corr, 3))
        matrix.append(row)
    return matrix


def _parse_published_at(raw: str) -> str:
    if not raw:
        return ""
    try:
        if "T" in raw and len(raw) >= 15:
            dt = datetime.strptime(raw[:15], "%Y%m%dT%H%M%S")
            return dt.isoformat()
    except ValueError:
        return raw
    return raw


def _map_sentiment(score: Optional[float], label: Optional[str]) -> str:
    if score is not None:
        if score >= 0.15:
            return "positive"
        if score <= -0.15:
            return "negative"
        return "neutral"
    lowered = (label or "").lower()
    if "bull" in lowered:
        return "positive"
    if "bear" in lowered:
        return "negative"
    return "neutral"


def _map_news_event(article: Mapping[str, Any]) -> Dict[str, Any]:
    score = _coerce_float(article.get("sentiment_score"))
    sentiment = _map_sentiment(score, article.get("sentiment_label"))
    published_at = article.get("published_at") or ""
    return {
        "date": _parse_published_at(str(published_at)),
        "title": article.get("title", ""),
        "summary": article.get("summary", ""),
        "sentiment": sentiment,
        "source": article.get("source", ""),
        "url": article.get("url", ""),
    }


def _extract_tool_input(response: Any, tool_name: str) -> Dict[str, Any]:
    content = getattr(response, "content", []) or []
    for block in content:
        block_type = getattr(block, "type", None)
        block_name = getattr(block, "name", None)
        block_input = getattr(block, "input", None)
        if block_type == "tool_use" and block_name == tool_name and isinstance(block_input, dict):
            return block_input
        if isinstance(block, dict):
            if block.get("type") == "tool_use" and block.get("name") == tool_name:
                tool_input = block.get("input")
                if isinstance(tool_input, dict):
                    return tool_input
    raise A2UIAgentError("Claude response missing skill selection tool output")


class A2UIAgent:
    """A2UI-native agent that streams dashboard messages."""

    def __init__(self, model: Optional[str] = None) -> None:
        """Initialize the agent with model + skill catalog."""
        if anthropic is None or _anthropic_import_error:
            raise A2UIAgentError(
                "A2UI agent requires the 'anthropic' package. Install backend dependencies (pip install -r backend/requirements.txt)."
            )
        self.settings = get_settings()
        if not self.settings.claude_api_key:
            raise A2UIAgentError("Claude API key not configured")
        self.model = model or self.settings.claude_model or DEFAULT_MODEL
        self.skills = get_a2ui_skills()
        self.skill_catalog = build_a2ui_skill_catalog(self.skills)
        self.skill_lookup = {skill.skill_id: skill for skill in self.skills}
        self.use_sdk_assets = should_use_sdk_assets(True)
        self.sdk_settings = load_project_settings() if self.use_sdk_assets else {}
        self.allowed_tool_names = (
            get_allowed_tools([SKILL_SELECTION_TOOL_NAME])
            if self.use_sdk_assets
            else [SKILL_SELECTION_TOOL_NAME]
        )

        if self.use_sdk_assets and ClaudeSDKClient and ClaudeAgentOptions:
            self.client = ClaudeSDKClient(
                api_key=self.settings.claude_api_key,
                options=ClaudeAgentOptions(
                    setting_sources=["project"],
                    allowed_tools=self.allowed_tool_names,
                    project_path=str(CLAUDE_DIR),
                ),
            )
        else:
            self.client = anthropic.Anthropic(api_key=self.settings.claude_api_key)

    async def select_skill(self, question: str) -> SkillSelection:
        """Select a skill and slots using the model."""
        system_prompt = (
            "You are an A2UI skill router. Choose exactly one skill_id from the catalog and extract tickers, metric, and time range if present. "
            "Only use the allowed ticker list. time_range must be one of: 1M, 3M, 6M, 1Y."
        )
        if not self.allowed_tool_names:
            raise A2UIAgentError("Claude SDK allowlist blocks A2UI skill routing tool.")
        tool = _build_skill_selection_tool(self.skill_lookup.keys())
        response = self.client.messages.create(
            model=self.model,
            max_tokens=512,
            system=f"{system_prompt}\n\n{self.skill_catalog}",
            tools=[tool],
            tool_choice={"type": "tool", "name": SKILL_SELECTION_TOOL_NAME},
            messages=[
                {
                    "role": "user",
                    "content": (
                        f"Question: {question}\n\n"
                        f"Allowed tickers: {', '.join(AVAILABLE_TICKERS)}"
                    ),
                }
            ],
        )
        tool_input = _extract_tool_input(response, SKILL_SELECTION_TOOL_NAME)
        selection = SkillSelection(**tool_input)
        self._validate_selection(selection)
        return selection

    def selection_to_plan(self, selection: SkillSelection) -> Dict[str, Any]:
        """Convert a skill selection into plan JSON for storage."""
        skill = get_a2ui_skill(selection.skill_id)
        tickers = _normalize_tickers(selection.tickers)
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
        normalized = _normalize_tickers(tickers)
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
            return await self._execute_explain_move(selection)
        if skill.skill_id == "a2ui_peer_compare":
            return await self._execute_peer_compare(selection)
        if skill.skill_id == "a2ui_margin_analysis":
            return await self._execute_margin_analysis(selection)
        if skill.skill_id == "a2ui_revenue_trend":
            return await self._execute_revenue_trend(selection)
        raise A2UIAgentError(f"Unsupported skill_id: {skill.skill_id}")

    async def _execute_explain_move(self, selection: SkillSelection) -> A2UIRunResult:
        """Fetch KPI + news data for explain-move dashboards."""
        ticker = _normalize_tickers(selection.tickers)[0]
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

        rows = _sorted_rows(sql_result.get("rows", []))
        revenue_series = _metric_series(rows, "Revenue")
        net_income_series = _metric_series(rows, "Net Income")
        gross_margin_series = _metric_series(rows, "Gross Margin")

        revenue_latest, revenue_prev = _latest_and_previous(revenue_series)
        net_latest, net_prev = _latest_and_previous(net_income_series)
        gross_latest, _ = _latest_and_previous(gross_margin_series)

        revenue_delta = _percentage_change(revenue_latest, revenue_prev)
        net_delta = _percentage_change(net_latest, net_prev)

        news_result = await execute_news_tool(ticker=ticker, limit=5)
        if not news_result.get("success"):
            raise A2UIAgentError(news_result.get("error", "News tool failed"))

        articles = news_result.get("articles", [])
        events = [_map_news_event(article) for article in articles]
        factors = [
            {
                "title": article.get("title", ""),
                "description": article.get("summary", ""),
                "impact": _map_sentiment(_coerce_float(article.get("sentiment_score")), article.get("sentiment_label")),
                "source": article.get("source", ""),
            }
            for article in articles[:3]
        ]
        citations = [
            {
                "title": article.get("title", ""),
                "url": article.get("url", ""),
                "date": _parse_published_at(str(article.get("published_at") or "")),
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
        tickers = _normalize_tickers(selection.tickers)
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

        rows = _sorted_rows(sql_result.get("rows", []))
        rows_by_ticker: Dict[str, List[Mapping[str, Any]]] = {ticker: [] for ticker in tickers}
        for row in rows:
            ticker = row.get("ticker")
            if ticker in rows_by_ticker:
                rows_by_ticker[ticker].append(row)

        table_rows = []
        series_by_ticker: Dict[str, List[float]] = {}
        for ticker, ticker_rows in rows_by_ticker.items():
            series = _metric_series(ticker_rows, metric)
            latest, previous = _latest_and_previous(series)
            delta = _percentage_change(latest, previous)
            series_by_ticker[ticker] = [entry["value"] for entry in series]
            table_rows.append(
                {
                    "ticker": ticker,
                    "latest_value": latest or 0,
                    "yoy_change": delta or 0,
                }
            )

        columns = [
            {"key": "ticker", "label": "Ticker", "type": "string"},
            {"key": "latest_value", "label": f"Latest {metric}", "type": "currency"},
            {"key": "yoy_change", "label": "YoY %", "type": "percentage"},
        ]

        correlation = _compute_correlation_matrix(series_by_ticker, tickers)

        data_model = {
            "tickers": tickers,
            "primary_ticker": tickers[0],
            "table": {"columns": columns, "rows": table_rows},
            "correlation": {"tickers": tickers, "matrix": correlation},
        }
        return A2UIRunResult(data_model=data_model, citations=[])

    async def _execute_margin_analysis(self, selection: SkillSelection) -> A2UIRunResult:
        """Fetch margin KPIs and history."""
        ticker = _normalize_tickers(selection.tickers)[0]
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

        rows = _sorted_rows(sql_result.get("rows", []))
        gross_series = _metric_series(rows, "Gross Margin")
        operating_series = _metric_series(rows, "Operating Margin")
        revenue_series = _metric_series(rows, "Revenue")
        net_income_series = _metric_series(rows, "Net Income")
        net_income_by_period = {entry["period"]: entry["value"] for entry in net_income_series}

        gross_latest, _ = _latest_and_previous(gross_series)
        operating_latest, _ = _latest_and_previous(operating_series)

        net_margin_series: List[Dict[str, Any]] = []
        for entry in revenue_series:
            period = entry["period"]
            revenue_value = entry["value"]
            net_value = net_income_by_period.get(period)
            if net_value is None or revenue_value == 0:
                continue
            net_margin_series.append({"period": period, "value": (net_value / revenue_value) * 100})

        net_latest, _ = _latest_and_previous(net_margin_series)

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

        data_model = {
            "ticker": ticker,
            "kpis": {
                "gross_margin": gross_latest or 0,
                "operating_margin": operating_latest or 0,
                "net_margin": net_latest or 0,
            },
            "table": {"columns": columns, "rows": table_rows},
        }
        return A2UIRunResult(data_model=data_model, citations=[])

    async def _execute_revenue_trend(self, selection: SkillSelection) -> A2UIRunResult:
        """Fetch revenue trend metrics."""
        ticker = _normalize_tickers(selection.tickers)[0]
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

        rows = _sorted_rows(sql_result.get("rows", []))
        revenue_series = _metric_series(rows, "Revenue")
        latest, previous = _latest_and_previous(revenue_series)

        yoy_growth = None
        if len(revenue_series) > 4:
            yoy_value = revenue_series[4].get("value")
            yoy_growth = _percentage_change(latest, _coerce_float(yoy_value))

        columns = [
            {"key": "period", "label": "Period", "type": "string"},
            {"key": "revenue", "label": "Revenue", "type": "currency"},
        ]
        rows_table = [
            {"period": entry["period"], "revenue": entry["value"]}
            for entry in revenue_series[:8]
        ]

        data_model = {
            "ticker": ticker,
            "kpis": {
                "latest_revenue": latest or 0,
                "yoy_growth": yoy_growth or 0,
            },
            "table": {"columns": columns, "rows": rows_table},
        }
        return A2UIRunResult(data_model=data_model, citations=[])

    def _validate_selection(self, selection: SkillSelection) -> None:
        if selection.skill_id not in self.skill_lookup:
            raise A2UIAgentError(f"Unknown skill_id: {selection.skill_id}")
        if selection.time_range not in ALLOWED_TIME_RANGES:
            raise A2UIAgentError(f"Invalid time_range: {selection.time_range}")
        normalized = _normalize_tickers(selection.tickers)
        if not normalized:
            raise A2UIAgentError("No valid tickers provided")
        selection.tickers = normalized

    def _build_render_context(self, selection: SkillSelection, skill: A2UISkillMeta) -> SkillRenderContext:
        tickers = _normalize_tickers(selection.tickers)
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
