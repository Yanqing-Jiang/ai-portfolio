# --- Skill Executor Pattern (Optimization #11) ---
# Class: BaseSkillExecutor
#   Role: Abstract base for all skill execution with common patterns.
#   Called from: A2UIAgent.execute_skill
#   Invokes: execute_sql_tool, execute_news_tool, execute_analysis_tool
#   Why: DRY principle - extracts common SQL construction, result parsing, error handling.
#
# Subclasses: ExplainMoveExecutor, PeerCompareExecutor, MarginAnalysisExecutor, RevenueTrendExecutor
#   Role: Skill-specific data fetching and transformation.
#   Each handles: build_sql(), parse_result(), optional post_process()
"""
Skill Executor Pattern for A2UI Agent

This module implements Optimization #11 from optimization-recommendations.md.
Provides a common base class for skill execution with:
- Standardized SQL construction
- Consistent result parsing
- Error handling
- Incremental data patch emission for streaming

Each skill inherits from BaseSkillExecutor and implements:
- build_queries(): Return list of SQL queries to execute
- parse_result(): Transform raw rows into data model
- Optional: post_process() for additional enrichment (news, analysis)
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Optional, Sequence

from backend.shared_tools.sql_executor import execute_sql_tool, execute_parameterized_query
from backend.shared_tools.news_service import execute_news_tool
from backend.shared_tools.analysis_service import execute_analysis_tool


logger = logging.getLogger(__name__)


# ============================================================================
# Data Types
# ============================================================================

@dataclass
class SQLQuery:
    """A SQL query with metadata."""
    sql: str
    reason: str
    key: str  # Key to store result under in intermediate results


@dataclass
class ExecutorResult:
    """Result from a skill executor."""
    data_model: Dict[str, Any]
    citations: List[Dict[str, Any]]
    
    
@dataclass
class DataPatch:
    """Incremental data patch for streaming (Optimization #18)."""
    path: str  # JSON pointer path, e.g., "/data/kpis"
    data: Dict[str, Any]


# ============================================================================
# Utility Functions
# ============================================================================

def normalize_tickers(tickers: Sequence[str]) -> List[str]:
    """Normalize ticker list to uppercase, removing invalid entries."""
    from backend.generative_ui.utils import normalize_tickers as _normalize
    return _normalize(tickers)


def sorted_rows(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Sort rows by year and quarter descending."""
    return sorted(
        rows, 
        key=lambda r: (r.get("calendar_year", 0), r.get("calendar_quarter_num", 0)),
        reverse=True
    )


def metric_series(rows: List[Dict[str, Any]], metric: str) -> List[Dict[str, Any]]:
    """Extract series for a specific metric."""
    return [
        {
            "period": f"{r.get('calendar_quarter', 'Q?')} {r.get('calendar_year', '')}",
            "value": r.get("value", 0),
        }
        for r in rows
        if r.get("metric") == metric
    ]


def latest_and_previous(series: List[Dict[str, Any]]) -> tuple:
    """Get latest and previous values from series."""
    latest = series[0]["value"] if series else None
    previous = series[1]["value"] if len(series) > 1 else None
    return latest, previous


def percentage_change(current: Optional[float], previous: Optional[float]) -> Optional[float]:
    """Calculate percentage change."""
    if current is None or previous is None or previous == 0:
        return None
    return ((current - previous) / abs(previous)) * 100


def coerce_float(value: Any) -> Optional[float]:
    """Safely coerce value to float."""
    if value is None:
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


# ============================================================================
# Base Executor
# ============================================================================

class BaseSkillExecutor(ABC):
    """
    Base class for skill executors.
    
    Class: BaseSkillExecutor
    Role: Abstract base providing common execution patterns.
    Called from: A2UIAgent.execute_skill
    Invokes: execute_sql_tool, subclass parse_result()
    Why: DRY principle - centralizes SQL execution, error handling, and result parsing.
    
    Subclasses must implement:
    - build_queries(): List of SQL queries to execute
    - parse_result(results): Transform query results to data model
    
    Optional overrides:
    - post_process(data_model): Enrich with news, analysis, etc.
    - get_data_patches(): Return incremental patches for streaming
    """
    
    def __init__(
        self,
        tickers: Sequence[str],
        metric: str = "Revenue",
        time_range: str = "3M",
    ):
        """
        Initialize executor with common parameters.
        
        Args:
            tickers: List of ticker symbols
            metric: Metric to analyze
            time_range: Time range for analysis
        """
        self.tickers = normalize_tickers(tickers)
        self.metric = metric
        self.time_range = time_range
        self._intermediate_results: Dict[str, Any] = {}
        self._data_patches: List[DataPatch] = []
        
        if not self.tickers:
            raise ValueError("No valid tickers provided")
    
    @property
    def primary_ticker(self) -> str:
        """Get the primary (first) ticker."""
        return self.tickers[0]
    
    @abstractmethod
    def build_queries(self) -> List[SQLQuery]:
        """
        Build SQL queries for this skill.
        
        Returns:
            List of SQLQuery objects to execute.
        """
        pass
    
    @abstractmethod
    def parse_result(self, results: Dict[str, List[Dict[str, Any]]]) -> Dict[str, Any]:
        """
        Parse query results into data model.
        
        Args:
            results: Dict mapping query keys to result rows.
            
        Returns:
            Data model dict ready for A2UI components.
        """
        pass
    
    async def post_process(self, data_model: Dict[str, Any]) -> Dict[str, Any]:
        """
        Optional post-processing (news, analysis, etc.).
        
        Override in subclasses that need enrichment.
        
        Args:
            data_model: Parsed data model
            
        Returns:
            Enriched data model
        """
        return data_model
    
    def get_data_patches(self) -> List[DataPatch]:
        """
        Get incremental data patches for streaming.
        
        Returns patches accumulated during execution for A2UI streaming.
        """
        return self._data_patches
    
    def _add_patch(self, path: str, data: Dict[str, Any]) -> None:
        """Add an incremental data patch."""
        self._data_patches.append(DataPatch(path=path, data=data))
    
    async def execute(self) -> ExecutorResult:
        """
        Execute the skill and return results.
        
        Method: execute
        Role: Main execution entry point.
        Invokes: build_queries, execute_sql_tool, parse_result, post_process
        Why: Centralizes execution flow with error handling.
        
        Returns:
            ExecutorResult with data_model and citations.
            
        Raises:
            RuntimeError: If SQL queries fail.
        """
        # Build and execute queries
        queries = self.build_queries()
        results: Dict[str, List[Dict[str, Any]]] = {}
        
        for query in queries:
            logger.debug("Executing query: %s", query.key)
            sql_result = await execute_sql_tool(query.sql, reason=query.reason)
            
            if not sql_result.get("success"):
                raise RuntimeError(f"SQL query failed: {sql_result.get('error', 'Unknown error')}")
            
            results[query.key] = sorted_rows(sql_result.get("rows", []))
            self._intermediate_results[query.key] = results[query.key]
        
        # Parse results
        data_model = self.parse_result(results)
        
        # Add KPIs patch
        if "kpis" in data_model:
            self._add_patch("/data/kpis", data_model["kpis"])
        
        # Add chart patch
        if "chart" in data_model:
            self._add_patch("/data/chart", data_model["chart"])
        
        # Add table patch
        if "table" in data_model:
            self._add_patch("/data/table", data_model["table"])
        
        # Post-process (news, analysis, etc.)
        data_model = await self.post_process(data_model)
        
        # Add explanation patch
        if "explanation" in data_model:
            self._add_patch("/data/explanation", data_model["explanation"])
        
        return ExecutorResult(data_model=data_model, citations=[])


# ============================================================================
# Skill Executors
# ============================================================================

class ExplainMoveExecutor(BaseSkillExecutor):
    """
    Executor for explain-move skill (price movement analysis).
    
    Class: ExplainMoveExecutor
    Role: Fetch KPI + news data for explain-move dashboards.
    Called from: A2UIAgent.execute_skill
    Invokes: BaseSkillExecutor.execute, execute_news_tool, execute_analysis_tool
    """
    
    def build_queries(self) -> List[SQLQuery]:
        ticker = self.primary_ticker
        return [
            SQLQuery(
                sql=(
                    f"SELECT ticker, calendar_year, calendar_quarter_num, calendar_quarter, metric, value "
                    f"FROM comp_financials "
                    f"WHERE ticker = '{ticker}' AND metric IN ('Revenue', 'Net Income', 'Gross Profit') "
                    f"ORDER BY calendar_year DESC, calendar_quarter_num DESC "
                    f"LIMIT 24"
                ),
                reason="Explain price movement KPIs",
                key="financials",
            )
        ]
    
    def parse_result(self, results: Dict[str, List[Dict[str, Any]]]) -> Dict[str, Any]:
        rows = results.get("financials", [])
        ticker = self.primary_ticker
        
        revenue_series = metric_series(rows, "Revenue")
        net_income_series = metric_series(rows, "Net Income")
        gross_profit_series = metric_series(rows, "Gross Profit")
        
        revenue_latest, revenue_prev = latest_and_previous(revenue_series)
        net_latest, net_prev = latest_and_previous(net_income_series)
        gross_profit_latest, _ = latest_and_previous(gross_profit_series)
        
        revenue_delta = percentage_change(revenue_latest, revenue_prev)
        net_delta = percentage_change(net_latest, net_prev)
        
        # Calculate gross margin as percentage from gross profit and revenue
        gross_margin = None
        if gross_profit_latest is not None and revenue_latest is not None and revenue_latest != 0:
            gross_margin = (gross_profit_latest / revenue_latest) * 100.0
        
        return {
            "ticker": ticker,
            "kpis": {
                "revenue": revenue_latest or 0,
                "revenue_delta": revenue_delta or 0,
                "net_income": net_latest or 0,
                "net_income_delta": net_delta or 0,
                "gross_margin": round(gross_margin, 2) if gross_margin is not None else 0,
            },
            "news": {"events": []},  # Filled in post_process
            "explanation": {},  # Filled in post_process
        }
    
    async def post_process(self, data_model: Dict[str, Any]) -> Dict[str, Any]:
        ticker = self.primary_ticker
        
        # Fetch news
        news_result = await execute_news_tool(ticker=ticker, limit=5)
        if news_result.get("success"):
            articles = news_result.get("articles", [])
            events = [
                {
                    "date": str(a.get("published_at", "")),
                    "title": a.get("title", ""),
                    "sentiment": a.get("sentiment_label", "Neutral"),
                }
                for a in articles
            ]
            factors = [
                {
                    "title": a.get("title", ""),
                    "description": a.get("summary", ""),
                    "impact": self._map_sentiment(a.get("sentiment_score"), a.get("sentiment_label")),
                    "source": a.get("source", ""),
                }
                for a in articles[:3]
            ]
            citations = [
                {
                    "title": a.get("title", ""),
                    "url": a.get("url", ""),
                    "date": str(a.get("published_at", ""))[:10],
                }
                for a in articles
            ]
            data_model["news"]["events"] = events
        else:
            factors = []
            citations = []
        
        # Generate analysis
        kpis = data_model.get("kpis", {})
        findings = []
        
        # Add revenue finding
        if kpis.get("revenue"):
            rev = kpis["revenue"]
            rev_delta = kpis.get("revenue_delta", 0)
            if rev >= 1e9:
                rev_str = f"${rev/1e9:.1f}B"
            else:
                rev_str = f"${rev/1e6:.0f}M"
            findings.append(f"Revenue stands at {rev_str}, {'up' if rev_delta > 0 else 'down'} {abs(rev_delta):.1f}% quarter-over-quarter.")
        
        # Add net income finding
        if kpis.get("net_income"):
            ni = kpis["net_income"]
            ni_delta = kpis.get("net_income_delta", 0)
            if ni >= 1e9:
                ni_str = f"${ni/1e9:.1f}B"
            else:
                ni_str = f"${ni/1e6:.0f}M"
            findings.append(f"Net income is {ni_str}, {'up' if ni_delta > 0 else 'down'} {abs(ni_delta):.1f}% QoQ.")
        
        # Add gross margin finding
        if kpis.get("gross_margin"):
            gm = kpis["gross_margin"]
            findings.append(f"Gross margin is {gm:.1f}%, {'above' if gm > 40 else 'below'} industry average.")
        
        # Determine trend direction from revenue change
        rev_delta = kpis.get("revenue_delta", 0)
        if rev_delta > 5:
            trend = "up"
        elif rev_delta < -5:
            trend = "down"
        elif abs(rev_delta) < 2:
            trend = "stable"
        else:
            trend = "mixed"
        
        analysis_result = await execute_analysis_tool(
            data_summary=f"Financial analysis for {ticker}.",
            key_findings=findings or ["Recent financial metrics were reviewed."],
            trend_direction=trend,
        )
        
        analysis_text = ""
        if analysis_result.get("success"):
            analysis_text = analysis_result.get("analysis", {}).get("summary", "")
        
        data_model["explanation"] = {
            "title": f"{ticker} Movement Drivers",
            "text": analysis_text or "Analysis pending.",
            "factors": factors,
            "citations": citations,
        }
        
        return data_model
    
    def _map_sentiment(self, score: Any, label: Any) -> str:
        """Map sentiment to impact label."""
        score = coerce_float(score)
        if score is not None:
            if score > 0.3:
                return "positive"
            elif score < -0.3:
                return "negative"
        if isinstance(label, str):
            label_lower = label.lower()
            if "positive" in label_lower or "bullish" in label_lower:
                return "positive"
            elif "negative" in label_lower or "bearish" in label_lower:
                return "negative"
        return "neutral"


class PeerCompareExecutor(BaseSkillExecutor):
    """
    Executor for peer comparison skill.
    
    Class: PeerCompareExecutor
    Role: Fetch comparison data for multi-ticker dashboards.
    Called from: A2UIAgent.execute_skill
    """
    
    def __init__(self, tickers: Sequence[str], metric: str = "Revenue", time_range: str = "3M"):
        super().__init__(tickers, metric, time_range)
        if len(self.tickers) < 2:
            raise ValueError("Peer comparison requires at least two tickers")
    
    def build_queries(self) -> List[SQLQuery]:
        tickers_sql = ", ".join([f"'{t}'" for t in self.tickers])
        return [
            SQLQuery(
                sql=(
                    f"SELECT ticker, calendar_year, calendar_quarter_num, calendar_quarter, metric, value "
                    f"FROM comp_financials "
                    f"WHERE ticker IN ({tickers_sql}) AND metric = '{self.metric}' "
                    f"ORDER BY ticker, calendar_year DESC, calendar_quarter_num DESC "
                    f"LIMIT 200"
                ),
                reason="Peer comparison metrics",
                key="comparison",
            )
        ]
    
    def parse_result(self, results: Dict[str, List[Dict[str, Any]]]) -> Dict[str, Any]:
        rows = results.get("comparison", [])
        
        # Group by ticker
        rows_by_ticker: Dict[str, List[Dict[str, Any]]] = {t: [] for t in self.tickers}
        for row in rows:
            ticker = row.get("ticker")
            if ticker in rows_by_ticker:
                rows_by_ticker[ticker].append(row)
        
        table_rows = []
        chart_series = []
        series_by_ticker: Dict[str, List[float]] = {}
        
        for ticker, ticker_rows in rows_by_ticker.items():
            series = metric_series(ticker_rows, self.metric)
            latest, _previous = latest_and_previous(series)
            
            yoy_change = None
            if len(series) > 4:
                yoy_value = coerce_float(series[4].get("value"))
                yoy_change = percentage_change(latest, yoy_value)
            
            series_values = [entry["value"] for entry in series]
            series_by_ticker[ticker] = series_values
            chart_series.append({"ticker": ticker, "data": series})
            table_rows.append({
                "ticker": ticker,
                "latest_value": latest if latest is not None else 0,
                "yoy_change": yoy_change,
            })
        
        # Determine value type
        metric_lower = self.metric.lower()
        value_type = "percentage" if "margin" in metric_lower or "rate" in metric_lower else "currency"
        
        columns = [
            {"key": "ticker", "label": "Ticker", "type": "string"},
            {"key": "latest_value", "label": f"Latest {self.metric}", "type": value_type},
            {"key": "yoy_change", "label": "YoY %", "type": "percentage"},
        ]
        
        # Compute correlation matrix
        correlation = self._compute_correlation(series_by_ticker)
        
        # Find primary ticker's row for KPIs (the main ticker user asked about)
        primary_row = next((r for r in table_rows if r["ticker"] == self.primary_ticker), None)
        if primary_row is None and table_rows:
            primary_row = table_rows[0]
        
        # Find leader (highest value) for comparison
        sorted_by_value = sorted(table_rows, key=lambda r: r.get("latest_value", 0) or 0, reverse=True)
        leader_row = sorted_by_value[0] if sorted_by_value else None
        
        # Build KPIs with keys matching layout.json schema:
        # - primary_value: Primary ticker's latest value
        # - primary_yoy: Primary ticker's YoY change
        # - leader: Ticker symbol of the leader
        # - leader_value: Leader's latest value
        kpis = {}
        if primary_row:
            kpis = {
                # Keys from layout.json data_schema
                "primary_value": primary_row.get("latest_value", 0),
                "primary_yoy": primary_row.get("yoy_change", 0),
                "leader": leader_row["ticker"] if leader_row else self.primary_ticker,
                "leader_value": leader_row.get("latest_value", 0) if leader_row else 0,
                # Legacy keys for backward compatibility
                "latest_value": primary_row.get("latest_value", 0),
                "yoy_change": primary_row.get("yoy_change", 0),
                "ticker": self.primary_ticker,
            }
        
        return {
            "tickers": self.tickers,
            "primary_ticker": self.primary_ticker,
            "kpis": kpis,
            "table": {"columns": columns, "rows": table_rows},
            "correlation": {"tickers": self.tickers, "matrix": correlation},
            "chart": {"series": chart_series, "annotations": []},
        }
    
    def _compute_correlation(self, series_by_ticker: Dict[str, List[float]]) -> List[List[float]]:
        """Compute correlation matrix for tickers."""
        n = len(self.tickers)
        matrix = [[0.0] * n for _ in range(n)]
        
        for i, t1 in enumerate(self.tickers):
            for j, t2 in enumerate(self.tickers):
                if i == j:
                    matrix[i][j] = 1.0
                elif j > i:
                    s1 = series_by_ticker.get(t1, [])
                    s2 = series_by_ticker.get(t2, [])
                    corr = self._pearson(s1, s2)
                    matrix[i][j] = corr
                    matrix[j][i] = corr
        
        return matrix
    
    def _pearson(self, x: List[float], y: List[float]) -> float:
        """Calculate Pearson correlation coefficient."""
        n = min(len(x), len(y))
        if n < 2:
            return 0.0
        
        x = x[:n]
        y = y[:n]
        
        mean_x = sum(x) / n
        mean_y = sum(y) / n
        
        numerator = sum((xi - mean_x) * (yi - mean_y) for xi, yi in zip(x, y))
        denom_x = sum((xi - mean_x) ** 2 for xi in x) ** 0.5
        denom_y = sum((yi - mean_y) ** 2 for yi in y) ** 0.5
        
        if denom_x == 0 or denom_y == 0:
            return 0.0
        
        return numerator / (denom_x * denom_y)
    
    async def post_process(self, data_model: Dict[str, Any]) -> Dict[str, Any]:
        """Generate factors and explanation based on peer comparison data."""
        ticker = self.primary_ticker
        table_rows = data_model.get("table", {}).get("rows", [])
        kpis = data_model.get("kpis", {})
        
        # Build factors from comparison data
        factors = []
        
        if table_rows:
            # Find best and worst performers
            sorted_rows = sorted(table_rows, key=lambda r: r.get("latest_value", 0) or 0, reverse=True)
            leader = sorted_rows[0] if sorted_rows else None
            laggard = sorted_rows[-1] if len(sorted_rows) > 1 else None
            
            # Primary ticker analysis
            primary_data = next((r for r in table_rows if r["ticker"] == ticker), None)
            if primary_data:
                latest = primary_data.get("latest_value", 0)
                yoy = primary_data.get("yoy_change")
                
                factors.append({
                    "title": f"{ticker} Performance",
                    "description": f"{ticker} latest {self.metric}: ${latest/1e9:.2f}B" if latest >= 1e9 else f"{ticker} latest {self.metric}: ${latest/1e6:.2f}M" if latest else f"{ticker} data pending",
                    "impact": "positive" if yoy and yoy > 0 else "negative" if yoy and yoy < 0 else "neutral",
                    "source": "Financial Data",
                    "icon": "📊",
                })
            
            # Leader insight
            if leader and leader["ticker"] != ticker:
                factors.append({
                    "title": "Market Leader",
                    "description": f"{leader['ticker']} leads the peer group in {self.metric}.",
                    "impact": "neutral",
                    "source": "Peer Analysis",
                    "icon": "🏆",
                })
            
            # YoY trend
            if primary_data and primary_data.get("yoy_change") is not None:
                yoy = primary_data["yoy_change"]
                factors.append({
                    "title": "Year-over-Year Trend",
                    "description": f"{ticker} {self.metric} {'grew' if yoy > 0 else 'declined'} {abs(yoy):.1f}% year-over-year.",
                    "impact": "positive" if yoy > 5 else "negative" if yoy < -5 else "neutral",
                    "source": "Historical Comparison",
                    "icon": "📈" if yoy > 0 else "📉",
                })
        
        # Build findings for AI analysis
        findings = []
        for row in table_rows[:5]:
            latest = row.get("latest_value", 0)
            yoy = row.get("yoy_change")
            if latest:
                formatted = f"${latest/1e9:.2f}B" if latest >= 1e9 else f"${latest/1e6:.2f}M"
                yoy_str = f" ({yoy:+.1f}% YoY)" if yoy is not None else ""
                findings.append(f"{row['ticker']}: Latest {self.metric} of {formatted}{yoy_str}")
        
        # Generate AI analysis
        analysis_result = await execute_analysis_tool(
            data_summary=f"Comparing {self.metric} for {', '.join(self.tickers)}.",
            key_findings=findings or [f"Comparing {self.metric} across {len(self.tickers)} peers."],
            trend_direction="mixed",
        )
        
        analysis_text = ""
        if analysis_result.get("success"):
            analysis_text = analysis_result.get("analysis", {}).get("summary", "")
        
        data_model["explanation"] = {
            "title": f"Insight: {self.metric} for {ticker}",
            "text": analysis_text or f"Comparing {self.metric} performance across {', '.join(self.tickers)}.",
            "factors": factors,
            "citations": [],
        }
        
        return data_model


class MarginAnalysisExecutor(BaseSkillExecutor):
    """
    Executor for margin analysis skill.
    
    Class: MarginAnalysisExecutor
    Role: Fetch margin KPIs and history for single or multiple tickers.
    Called from: A2UIAgent.execute_skill
    """
    
    def build_queries(self) -> List[SQLQuery]:
        if len(self.tickers) > 1:
            return self._build_multi_ticker_queries()
        return self._build_single_ticker_queries()
    
    def _build_single_ticker_queries(self) -> List[SQLQuery]:
        ticker = self.primary_ticker
        return [
            SQLQuery(
                sql=(
                    f"SELECT ticker, calendar_year, calendar_quarter_num, calendar_quarter, metric, value "
                    f"FROM comp_financials "
                    f"WHERE ticker = '{ticker}' AND metric IN ('Gross Margin', 'Operating Margin', 'Net Income', 'Revenue') "
                    f"ORDER BY calendar_year DESC, calendar_quarter_num DESC "
                    f"LIMIT 48"
                ),
                reason="Margin analysis",
                key="margins",
            )
        ]
    
    def _build_multi_ticker_queries(self) -> List[SQLQuery]:
        tickers_sql = ", ".join([f"'{t}'" for t in self.tickers])
        return [
            SQLQuery(
                sql=(
                    f"SELECT ticker, calendar_year, calendar_quarter_num, calendar_quarter, metric, value "
                    f"FROM comp_financials "
                    f"WHERE ticker IN ({tickers_sql}) AND metric IN ('Gross Margin', 'Operating Margin', 'Net Income', 'Revenue') "
                    f"ORDER BY ticker, calendar_year DESC, calendar_quarter_num DESC "
                    f"LIMIT 200"
                ),
                reason="Multi-ticker margin comparison",
                key="margins",
            )
        ]
    
    def parse_result(self, results: Dict[str, List[Dict[str, Any]]]) -> Dict[str, Any]:
        if len(self.tickers) > 1:
            return self._parse_multi_ticker(results)
        return self._parse_single_ticker(results)
    
    def _parse_single_ticker(self, results: Dict[str, List[Dict[str, Any]]]) -> Dict[str, Any]:
        rows = results.get("margins", [])
        ticker = self.primary_ticker
        
        gross_series = metric_series(rows, "Gross Margin")
        operating_series = metric_series(rows, "Operating Margin")
        revenue_series = metric_series(rows, "Revenue")
        net_income_series = metric_series(rows, "Net Income")
        
        net_income_by_period = {e["period"]: e["value"] for e in net_income_series}
        
        gross_latest, _ = latest_and_previous(gross_series)
        operating_latest, _ = latest_and_previous(operating_series)
        
        # Calculate net margin
        net_margin_series = []
        for entry in revenue_series:
            period = entry["period"]
            rev_value = entry["value"]
            net_value = net_income_by_period.get(period)
            if net_value is not None and rev_value != 0:
                net_margin_series.append({"period": period, "value": (net_value / rev_value) * 100})
        
        net_latest, _ = latest_and_previous(net_margin_series)
        
        # Build table
        table_rows = []
        for entry in revenue_series[:8]:
            period = entry["period"]
            table_rows.append({
                "period": period,
                "gross_margin": next((i["value"] for i in gross_series if i["period"] == period), None),
                "operating_margin": next((i["value"] for i in operating_series if i["period"] == period), None),
                "net_margin": next((i["value"] for i in net_margin_series if i["period"] == period), None),
            })
        
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
        
        return {
            "ticker": ticker,
            "kpis": {
                "gross_margin": gross_latest or 0,
                "operating_margin": operating_latest or 0,
                "net_margin": net_latest or 0,
            },
            "table": {"columns": columns, "rows": table_rows},
            "chart": {"series": chart_series, "annotations": []},
        }
    
    def _parse_multi_ticker(self, results: Dict[str, List[Dict[str, Any]]]) -> Dict[str, Any]:
        rows = results.get("margins", [])
        
        # Group by ticker
        rows_by_ticker: Dict[str, List[Dict[str, Any]]] = {t: [] for t in self.tickers}
        for row in rows:
            ticker = row.get("ticker")
            if ticker in rows_by_ticker:
                rows_by_ticker[ticker].append(row)
        
        table_rows = []
        chart_series = []
        
        for ticker, ticker_rows in rows_by_ticker.items():
            gross_series = metric_series(ticker_rows, "Gross Margin")
            operating_series = metric_series(ticker_rows, "Operating Margin")
            revenue_series = metric_series(ticker_rows, "Revenue")
            net_income_series = metric_series(ticker_rows, "Net Income")
            
            net_income_by_period = {e["period"]: e["value"] for e in net_income_series}
            
            gross_latest, _ = latest_and_previous(gross_series)
            operating_latest, _ = latest_and_previous(operating_series)
            
            net_margin_series = []
            for entry in revenue_series:
                period = entry["period"]
                rev_value = entry["value"]
                net_value = net_income_by_period.get(period)
                if net_value is not None and rev_value != 0:
                    net_margin_series.append({"period": period, "value": (net_value / rev_value) * 100})
            
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
        
        # Find primary ticker's row for KPIs (the main ticker user asked about)
        primary_row = next((r for r in table_rows if r["ticker"] == self.primary_ticker), None)
        if primary_row is None and table_rows:
            primary_row = table_rows[0]
        
        return {
            "tickers": self.tickers,
            "primary_ticker": self.primary_ticker,
            "kpis": {
                "gross_margin": primary_row["gross_margin"] if primary_row else 0,
                "operating_margin": primary_row["operating_margin"] if primary_row else 0,
                "net_margin": primary_row["net_margin"] if primary_row else 0,
            },
            "table": {"columns": columns, "rows": table_rows},
            "chart": {"series": chart_series, "annotations": []},
        }
    
    async def post_process(self, data_model: Dict[str, Any]) -> Dict[str, Any]:
        """Generate factors and explanation based on margin data."""
        ticker = self.primary_ticker
        kpis = data_model.get("kpis", {})
        table_rows = data_model.get("table", {}).get("rows", [])
        
        # Build factors from actual data
        factors = []
        
        gross = kpis.get("gross_margin", 0)
        operating = kpis.get("operating_margin", 0)
        net = kpis.get("net_margin", 0)
        
        if gross > 0:
            factors.append({
                "title": "Gross Margin",
                "description": f"{ticker} has a gross margin of {gross:.1f}%, indicating cost efficiency in production.",
                "impact": "positive" if gross > 40 else "neutral" if gross > 20 else "negative",
                "source": "Financial Statements",
                "icon": "📊",
            })
        
        if operating > 0:
            factors.append({
                "title": "Operating Efficiency",
                "description": f"Operating margin of {operating:.1f}% reflects operational performance and overhead control.",
                "impact": "positive" if operating > 20 else "neutral" if operating > 10 else "negative",
                "source": "Financial Statements",
                "icon": "⚙️",
            })
        
        if net > 0:
            factors.append({
                "title": "Net Profitability",
                "description": f"Net margin of {net:.1f}% represents bottom-line profitability after all expenses.",
                "impact": "positive" if net > 15 else "neutral" if net > 5 else "negative",
                "source": "Financial Statements",
                "icon": "💰",
            })
        
        # Generate comparative insight if multiple tickers
        if len(table_rows) > 1:
            best_gross = max(table_rows, key=lambda r: r.get("gross_margin", 0))
            factors.append({
                "title": "Peer Comparison",
                "description": f"{best_gross['ticker']} leads with highest gross margin at {best_gross['gross_margin']:.1f}%.",
                "impact": "positive" if best_gross["ticker"] == ticker else "neutral",
                "source": "Comparative Analysis",
                "icon": "📈",
            })
        
        # Build findings for analysis
        findings = []
        if gross > 0:
            findings.append(f"{ticker} gross margin: {gross:.1f}%")
        if operating > 0:
            findings.append(f"{ticker} operating margin: {operating:.1f}%")
        if net > 0:
            findings.append(f"{ticker} net margin: {net:.1f}%")
        
        # Generate AI analysis
        analysis_result = await execute_analysis_tool(
            data_summary=f"Margin analysis for {ticker}. Gross: {gross:.1f}%, Operating: {operating:.1f}%, Net: {net:.1f}%.",
            key_findings=findings or ["Margin data being analyzed."],
            trend_direction="stable",
        )
        
        analysis_text = ""
        if analysis_result.get("success"):
            analysis_text = analysis_result.get("analysis", {}).get("summary", "")
        
        data_model["explanation"] = {
            "title": f"Insight: {self.metric} for {ticker}",
            "text": analysis_text or f"Analyzing {ticker} margin performance across gross, operating, and net profitability metrics.",
            "factors": factors,
            "citations": [],
        }
        
        return data_model


class RevenueTrendExecutor(BaseSkillExecutor):
    """
    Executor for revenue trend skill.
    
    Class: RevenueTrendExecutor
    Role: Fetch revenue trend metrics for a single ticker.
    Called from: A2UIAgent.execute_skill
    """
    
    def build_queries(self) -> List[SQLQuery]:
        ticker = self.primary_ticker
        return [
            SQLQuery(
                sql=(
                    f"SELECT ticker, calendar_year, calendar_quarter_num, calendar_quarter, metric, value "
                    f"FROM comp_financials "
                    f"WHERE ticker = '{ticker}' AND metric = 'Revenue' "
                    f"ORDER BY calendar_year DESC, calendar_quarter_num DESC "
                    f"LIMIT 24"
                ),
                reason="Revenue trend",
                key="revenue",
            )
        ]
    
    def parse_result(self, results: Dict[str, List[Dict[str, Any]]]) -> Dict[str, Any]:
        rows = results.get("revenue", [])
        ticker = self.primary_ticker
        
        revenue_series = metric_series(rows, "Revenue")
        latest, previous = latest_and_previous(revenue_series)
        
        yoy_growth = None
        if len(revenue_series) > 4:
            yoy_value = coerce_float(revenue_series[4].get("value"))
            yoy_growth = percentage_change(latest, yoy_value)
        
        columns = [
            {"key": "period", "label": "Period", "type": "string"},
            {"key": "revenue", "label": "Revenue", "type": "currency"},
        ]
        
        table_rows = [
            {"period": entry["period"], "revenue": entry["value"]}
            for entry in revenue_series[:8]
        ]
        
        chart_series = [{"ticker": ticker, "data": revenue_series}]
        
        return {
            "ticker": ticker,
            "kpis": {
                "latest_revenue": latest or 0,
                "yoy_growth": yoy_growth or 0,
            },
            "table": {"columns": columns, "rows": table_rows},
            "chart": {"series": chart_series, "annotations": []},
        }


# ============================================================================
# Factory Function
# ============================================================================

def get_executor(
    skill_id: str,
    tickers: Sequence[str],
    metric: str = "Revenue",
    time_range: str = "3M",
) -> BaseSkillExecutor:
    """
    Factory function to get the appropriate executor for a skill.
    
    Function: get_executor
    Role: Create skill-specific executor instance.
    Called from: A2UIAgent.execute_skill
    Why: Clean factory pattern for skill routing.
    
    Args:
        skill_id: The A2UI skill ID
        tickers: List of ticker symbols
        metric: Metric to analyze
        time_range: Time range for analysis
        
    Returns:
        Appropriate BaseSkillExecutor subclass instance
        
    Raises:
        ValueError: If skill_id is not supported
    """
    executors = {
        "a2ui_explain_move": ExplainMoveExecutor,
        "a2ui_peer_compare": PeerCompareExecutor,
        "a2ui_margin_analysis": MarginAnalysisExecutor,
        "a2ui_revenue_trend": RevenueTrendExecutor,
    }
    
    executor_class = executors.get(skill_id)
    if not executor_class:
        raise ValueError(f"Unsupported skill_id: {skill_id}")
    
    return executor_class(tickers=tickers, metric=metric, time_range=time_range)


__all__ = [
    "BaseSkillExecutor",
    "ExplainMoveExecutor",
    "PeerCompareExecutor",
    "MarginAnalysisExecutor",
    "RevenueTrendExecutor",
    "ExecutorResult",
    "DataPatch",
    "get_executor",
]
