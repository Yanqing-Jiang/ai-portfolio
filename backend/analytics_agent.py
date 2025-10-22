import json
import os
import re
import traceback
import yaml
from pathlib import Path
from typing import Dict, Any, List, Optional, AsyncGenerator, TypedDict, Tuple

import asyncpg
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from unified_responses_client import get_unified_client


class WorkflowState(TypedDict):
    query: str
    sql: Optional[str]
    data: Optional[List[Dict[str, Any]]]
    chart_spec: Optional[Dict[str, Any]]
    analysis: Optional[str]
    errors: List[str]
    thinking: Optional[str]
    step: str
    years_back: Optional[int]
    granularity: Optional[str]

def load_config_schemas():
    """Load all YAML configuration schemas"""
    config_dir = Path(__file__).parent / "config" / "schemas"
    configs = {}
    
    schema_files = ["companies.yaml", "metrics.yaml", "queries.yaml", "charts.yaml"]
    
    for schema_file in schema_files:
        schema_path = config_dir / schema_file
        if schema_path.exists():
            with open(schema_path, 'r', encoding='utf-8') as f:
                schema_name = schema_file.replace('.yaml', '')
                configs[schema_name] = yaml.safe_load(f)
        else:
            print(f"Warning: Schema file {schema_file} not found at {schema_path}")
            configs[schema_file.replace('.yaml', '')] = {}
    
    return configs

class AnalyticsWorkflow:
    def __init__(self, database_url: str, openai_api_key: str):
        self.database_url = database_url
        # Use unified client with Responses API
        self.unified_client = get_unified_client()
        if not self.unified_client:
            raise ValueError("Failed to initialize unified responses client")
        
        # Load configuration schemas
        self.configs = load_config_schemas()
        
        # Synonym mapping for common financial terms from metrics.yaml
        metrics_config = self.configs.get('metrics', {})
        self.metric_synonyms = metrics_config.get('synonyms', {
            "OpEx": "Operating Expenses",
            "CapEx": "CapEx", 
            "CFO": "CFO",
            "Cash": "Cash & Equiv.",
            "R&D": "R&D Expense",
            "SG&A": "SG&A",
            "Gross Profit": "Gross Profit",
            "Revenue": "Revenue",
            "Net Income": "Net Income"
        })

    def _detect_intent(self, query: str) -> Dict[str, Any]:
        """Detect user intent (kind, ticker, names) from the query using queries.yaml patterns."""
        q_lower = (query or '').lower()
        print(f"[INTENT DEBUG START] Processing query: '{q_lower}'")
        companies_in_query = self._extract_companies(query)
        if companies_in_query:
            ticker, name = companies_in_query[0]
        else:
            _, default_company = self._get_company_mapping()
            ticker, name = default_company
        tickers_detected = [company[0] for company in companies_in_query]
        print(f"[INTENT DEBUG] Extracted company: ticker='{ticker}', name='{name}', candidates={tickers_detected}")
        kind: Optional[str] = None
        start_year, end_year = self._extract_year_bounds(query)

        # High-signal feature gating to avoid false matches on generic words like 'average'
        has_market_share = ('market share' in q_lower) or ('share of market' in q_lower) or ('market position' in q_lower)
        has_all = ('all' in q_lower) or ('all companies' in q_lower) or ('everyone' in q_lower)
        has_margin = ('margin' in q_lower) or ('gross margin' in q_lower) or ('operating margin' in q_lower) or ('net margin' in q_lower)
        has_growth = ('growth' in q_lower) or ('growing' in q_lower) or ('expansion' in q_lower) or ('fast' in q_lower)
        has_rnd = ('r&d' in q_lower) or ('r and d' in q_lower) or ('rnd' in q_lower) or ('research and development' in q_lower)
        has_expense = ('expense' in q_lower) or ('spending' in q_lower) or ('spend' in q_lower) or ('expenditure' in q_lower)
        has_compare = ('peer' in q_lower) or ('peers' in q_lower) or ('compare' in q_lower) or ('comparison' in q_lower) or ('vs' in q_lower)
        has_vs_keyword = (' vs ' in q_lower) or ('versus' in q_lower) or ('vs.' in q_lower)
        has_revenue = 'revenue' in q_lower
        has_average = ('average' in q_lower) or ('industry average' in q_lower) or ('mean' in q_lower)
        has_rank = any(word in q_lower for word in ('highest', 'top', 'leading', 'leader', 'largest', 'biggest', 'most', 'rank', 'dominant'))

        if not kind:
            # Scored routing across possible intents
            candidates = []
            def add_candidate(key: str, condition: bool, base: int):
                if condition:
                    candidates.append([key, base])
            add_candidate('market_share_all', has_market_share and has_all, 10)
            add_candidate('market_share_single', has_market_share, 8)
            add_candidate('margin_growth_vs_peers', has_margin and has_growth and (has_compare or has_average), 9)
            add_candidate('margins_vs_peers', has_margin and (has_compare or has_average), 7)
            # Treat single-company revenue growth even without explicit compare keywords
            add_candidate('revenue_growth_analysis', has_growth, 7)
            add_candidate('revenue_comparison', has_revenue and (has_compare or has_vs_keyword or 'revenue comparison' in q_lower), 9)
            add_candidate('rnd_expense_vs_peers', has_rnd and has_expense and (has_compare or has_average), 6)
            add_candidate('rnd_intensity_vs_peers', has_rnd and (('intensity' in q_lower) or (has_compare or has_average)), 5)
            add_candidate('rnd_top_spender', has_rnd and has_expense and has_rank, 6)

            # Phrase boosts
            if 'margin growth' in q_lower:
                for c in candidates:
                    if c[0] == 'margin_growth_vs_peers':
                        c[1] += 4
            if 'market share' in q_lower:
                for c in candidates:
                    if c[0].startswith('market_share'):
                        c[1] += 3
            if ('r&d expense' in q_lower) or ('rnd expense' in q_lower) or ('research and development expense' in q_lower):
                for c in candidates:
                    if c[0] == 'rnd_expense_vs_peers':
                        c[1] += 4

            # Choose highest scoring candidate
            if candidates:
                candidates.sort(key=lambda x: x[1], reverse=True)
                kind = candidates[0][0]
                print(f"[INTENT DEBUG] Scored candidates: {candidates}. Selected: {kind}")

        # Get query patterns from queries.yaml
        queries_config = self.configs.get('queries', {})
        query_patterns = queries_config.get('query_patterns', {})
        print(f"[INTENT DEBUG] Loaded {len(query_patterns)} patterns from YAML: {list(query_patterns.keys())}")
        if not query_patterns:
            print(f"[INTENT DEBUG] WARNING: No query patterns found in config! Available keys: {list(queries_config.keys())}")
            print(f"[INTENT DEBUG] Full config: {self.configs}")
        
        # Check YAML patterns only if kind still unknown
        if not kind:
            # Sort patterns by keyword specificity (longest keywords first) to avoid premature matches
            pattern_items = list(query_patterns.items())
            pattern_items.sort(key=lambda x: -max(len(keyword) for keyword in x[1].get('keywords', [''])))
            for pattern_key, pattern_info in pattern_items:
                keywords = pattern_info.get('keywords', [])
                # Debug logging
                print(f"[INTENT DEBUG] Checking pattern '{pattern_key}' with keywords: {keywords}")
                # Check if any keywords match the query
                if any(keyword in q_lower for keyword in keywords):
                    print(f"[INTENT DEBUG] MATCHED! Query '{q_lower}' matches pattern '{pattern_key}'")
                    kind = pattern_key
                    break
        
        # Fallback to hardcoded patterns if no YAML match
        if not kind:
            if 'market share' in q_lower and 'all' in q_lower:
                kind = 'market_share_all'
            elif 'market share' in q_lower:
                kind = 'market_share_single'
            elif 'revenue comparison' in q_lower or (has_revenue and has_vs_keyword):
                kind = 'revenue_comparison'
            # Margin growth vs peers/industry
            elif ('margin' in q_lower and 'growth' in q_lower and ('peer' in q_lower or 'peers' in q_lower or 'compare' in q_lower or 'average' in q_lower)):
                kind = 'margin_growth_vs_peers'
            elif ('margin' in q_lower and ('peer' in q_lower or 'compare' in q_lower)):
                kind = 'margins_vs_peers'
            # R&D expense vs average (absolute spending)
            elif (('r&d' in q_lower or 'r and d' in q_lower or 'rnd' in q_lower) and 'expense' in q_lower and ('average' in q_lower or 'peer' in q_lower or 'peers' in q_lower or 'compare' in q_lower)):
                kind = 'rnd_expense_vs_peers'
            elif (('growth' in q_lower or 'growing' in q_lower or 'fast' in q_lower) and ('peer' in q_lower or 'peers' in q_lower or 'vs' in q_lower)):
                kind = 'growth_vs_peers'
            elif (has_rnd and has_expense and has_rank):
                kind = 'rnd_top_spender'
            elif ('r&d' in q_lower or 'r and d' in q_lower or 'rnd' in q_lower or 'r&d expense' in q_lower or 'r&d expenses' in q_lower or ('intensity' in q_lower and ('r' in q_lower or 'rnd' in q_lower or 'r&d' in q_lower))):
                kind = 'rnd_intensity_vs_peers'
        
        result = {
            'kind': kind,
            'ticker': ticker,
            'name': name,
            'tickers': tickers_detected,
            'start_year': start_year,
            'end_year': end_year,
        }
        print(f"[INTENT DEBUG FINAL] Result: {result}")
        return result

    def _build_market_share_sql(self, all_companies: bool, target_ticker: str, years_back: int = 4, granularity: str = 'annual') -> str:
        """Return SQL for market share over the specified time period.
        If all_companies is True, returns per-ticker market share vs total market.
        Else returns target ticker vs market.
        years_back: Number of years to look back (default 4 = 5 years total)
        """
        tickers = self._get_default_tickers()
        ticker_list = "'" + "','".join(tickers) + "'"
        
        if granularity == 'quarterly':
            if all_companies:
                # Quarterly market share for all companies
                return (
                    "WITH market AS (\n"
                    "  SELECT calendar_year, calendar_quarter_num, calendar_quarter, SUM(value) AS market_revenue\n"
                    "  FROM comp_financials\n"
                    "  WHERE metric = 'Revenue'\n"
                    f"    AND ticker IN ({ticker_list})\n"
                    "    AND calendar_quarter_num IS NOT NULL\n"
                    f"    AND calendar_year >= EXTRACT(YEAR FROM CURRENT_DATE) - {years_back}\n"
                    "  GROUP BY calendar_year, calendar_quarter_num, calendar_quarter\n"
                    "), per AS (\n"
                    "  SELECT ticker, calendar_year, calendar_quarter_num, calendar_quarter, SUM(value) AS ticker_revenue\n"
                    "  FROM comp_financials\n"
                    "  WHERE metric = 'Revenue'\n"
                    f"    AND ticker IN ({ticker_list})\n"
                    "    AND calendar_quarter_num IS NOT NULL\n"
                    f"    AND calendar_year >= EXTRACT(YEAR FROM CURRENT_DATE) - {years_back}\n"
                    "  GROUP BY ticker, calendar_year, calendar_quarter_num, calendar_quarter\n"
                    ")\n"
                    "SELECT\n"
                    "  p.ticker, p.calendar_year, p.calendar_quarter_num, p.calendar_quarter, p.ticker_revenue, m.market_revenue,\n"
                    "  p.ticker_revenue / NULLIF(m.market_revenue, 0) AS market_share\n"
                    "FROM per p JOIN market m USING (calendar_year, calendar_quarter_num, calendar_quarter)\n"
                    "ORDER BY p.ticker, p.calendar_year, p.calendar_quarter_num"
                )
            else:
                # Quarterly market share for single company
                ticker_lower = target_ticker.lower()
                return (
                    "WITH market AS (\n"
                    "  SELECT calendar_year, calendar_quarter_num, calendar_quarter, SUM(value) AS market_revenue\n"
                    "  FROM comp_financials\n"
                    "  WHERE metric = 'Revenue'\n"
                    f"    AND ticker IN ({ticker_list})\n"
                    "    AND calendar_quarter_num IS NOT NULL\n"
                    f"    AND calendar_year >= EXTRACT(YEAR FROM CURRENT_DATE) - {years_back}\n"
                    "  GROUP BY calendar_year, calendar_quarter_num, calendar_quarter\n"
                    "), t AS (\n"
                    "  SELECT calendar_year, calendar_quarter_num, calendar_quarter, SUM(value) AS t_revenue\n"
                    "  FROM comp_financials\n"
                    f"  WHERE metric = 'Revenue' AND ticker = '{target_ticker}'\n"
                    "    AND calendar_quarter_num IS NOT NULL\n"
                    f"    AND calendar_year >= EXTRACT(YEAR FROM CURRENT_DATE) - {years_back}\n"
                    "  GROUP BY calendar_year, calendar_quarter_num, calendar_quarter\n"
                    ")\n"
                    f"SELECT t.calendar_year, t.calendar_quarter_num, t.calendar_quarter, t.t_revenue AS {ticker_lower}_revenue, m.market_revenue,\n"
                    f"       t.t_revenue / NULLIF(m.market_revenue, 0) AS {ticker_lower}_market_share\n"
                    "FROM t JOIN market m USING (calendar_year, calendar_quarter_num, calendar_quarter)\n"
                    "ORDER BY t.calendar_year, t.calendar_quarter_num"
                )
        else:
            # Annual market share (original logic)
            if all_companies:
                return (
                    "WITH market AS (\n"
                    "  SELECT calendar_year, SUM(value) AS market_revenue\n"
                    "  FROM comp_financials\n"
                    "  WHERE metric = 'Revenue'\n"
                    f"    AND ticker IN ({ticker_list})\n"
                    "    AND calendar_quarter_num IS NOT NULL\n"
                    f"    AND calendar_year >= EXTRACT(YEAR FROM CURRENT_DATE) - {years_back}\n"
                    "  GROUP BY calendar_year\n"
                    "), per AS (\n"
                    "  SELECT ticker, calendar_year, SUM(value) AS ticker_revenue\n"
                    "  FROM comp_financials\n"
                    "  WHERE metric = 'Revenue'\n"
                    f"    AND ticker IN ({ticker_list})\n"
                    "    AND calendar_quarter_num IS NOT NULL\n"
                    f"    AND calendar_year >= EXTRACT(YEAR FROM CURRENT_DATE) - {years_back}\n"
                    "  GROUP BY ticker, calendar_year\n"
                    ")\n"
                    "SELECT\n"
                    "  p.ticker, p.calendar_year, p.ticker_revenue, m.market_revenue,\n"
                    "  p.ticker_revenue / NULLIF(m.market_revenue, 0) AS market_share\n"
                    "FROM per p JOIN market m USING (calendar_year)\n"
                    "ORDER BY p.ticker, p.calendar_year"
                )
            # single company
            ticker_lower = target_ticker.lower()
            return (
                "WITH market AS (\n"
                "  SELECT calendar_year, SUM(value) AS market_revenue\n"
                "  FROM comp_financials\n"
                "  WHERE metric = 'Revenue'\n"
                f"    AND ticker IN ({ticker_list})\n"
                "    AND calendar_quarter_num IS NOT NULL\n"
                f"    AND calendar_year >= EXTRACT(YEAR FROM CURRENT_DATE) - {years_back}\n"
                "  GROUP BY calendar_year\n"
                "), t AS (\n"
                "  SELECT calendar_year, SUM(value) AS t_revenue\n"
                "  FROM comp_financials\n"
                f"  WHERE metric = 'Revenue' AND ticker = '{target_ticker}'\n"
                "    AND calendar_quarter_num IS NOT NULL\n"
                f"    AND calendar_year >= EXTRACT(YEAR FROM CURRENT_DATE) - {years_back}\n"
                "  GROUP BY calendar_year\n"
                ")\n"
                f"SELECT t.calendar_year, t.t_revenue AS {ticker_lower}_revenue, m.market_revenue,\n"
                f"       t.t_revenue / NULLIF(m.market_revenue, 0) AS {ticker_lower}_market_share\n"
                "FROM t JOIN market m USING (calendar_year)\n"
                "ORDER BY t.calendar_year"
            )

    def _build_margins_sql(self, target_ticker: str, years_back: int = 4, granularity: str = 'annual') -> str:
        ticker_lower = target_ticker.lower()
        tickers = self._get_default_tickers()
        ticker_list = "'" + "','".join(tickers) + "'"
        
        if granularity == 'quarterly':
            # Quarterly margins analysis
            return (
                "WITH q AS (\n"
                "  SELECT * FROM comp_financials\n"
                "  WHERE calendar_quarter_num IS NOT NULL\n"
                f"    AND ticker IN ({ticker_list})\n"
                "    AND metric IN ('Revenue','Gross Profit','Operating Income','Net Income')\n"
                f"    AND calendar_year >= EXTRACT(YEAR FROM CURRENT_DATE) - {years_back}\n"
                "), qtr AS (\n"
                "  SELECT ticker, calendar_year, calendar_quarter_num, calendar_quarter,\n"
                "         SUM(CASE WHEN metric='Revenue' THEN value END) AS rev,\n"
                "         SUM(CASE WHEN metric='Gross Profit' THEN value END) AS gp,\n"
                "         SUM(CASE WHEN metric='Operating Income' THEN value END) AS op,\n"
                "         SUM(CASE WHEN metric='Net Income' THEN value END) AS ni\n"
                "  FROM q GROUP BY 1,2,3,4\n"
                "), industry_avg AS (\n"
                "  SELECT calendar_year, calendar_quarter_num,\n"
                "         AVG(gp/NULLIF(rev,0)) AS industry_avg_gross_margin,\n"
                "         AVG(op/NULLIF(rev,0)) AS industry_avg_operating_margin,\n"
                "         AVG(ni/NULLIF(rev,0)) AS industry_avg_net_margin\n"
                f"  FROM qtr WHERE ticker <> '{target_ticker}' GROUP BY 1,2\n"
                ")\n"
                "SELECT q.calendar_year, q.calendar_quarter_num, q.calendar_quarter,\n"
                f"       q.gp/NULLIF(q.rev,0) AS {ticker_lower}_gross_margin,\n"
                f"       q.op/NULLIF(q.rev,0) AS {ticker_lower}_operating_margin,\n"
                f"       q.ni/NULLIF(q.rev,0) AS {ticker_lower}_net_margin,\n"
                "       p.industry_avg_gross_margin, p.industry_avg_operating_margin, p.industry_avg_net_margin\n"
                "FROM qtr q JOIN industry_avg p USING (calendar_year, calendar_quarter_num)\n"
                f"WHERE q.ticker='{target_ticker}'\n"
                "ORDER BY q.calendar_year, q.calendar_quarter_num"
            )
        else:
            # Annual margins analysis (original logic)
            return (
                "WITH q AS (\n"
                "  SELECT * FROM comp_financials\n"
                "  WHERE calendar_quarter_num IS NOT NULL\n"
                f"    AND ticker IN ({ticker_list})\n"
                "    AND metric IN ('Revenue','Gross Profit','Operating Income','Net Income')\n"
                "), yr AS (\n"
                "  SELECT ticker, calendar_year,\n"
                "         SUM(CASE WHEN metric='Revenue' THEN value END) AS rev,\n"
                "         SUM(CASE WHEN metric='Gross Profit' THEN value END) AS gp,\n"
                "         SUM(CASE WHEN metric='Operating Income' THEN value END) AS op,\n"
                "         SUM(CASE WHEN metric='Net Income' THEN value END) AS ni\n"
                "  FROM q GROUP BY 1,2\n"
                "), industry_avg AS (\n"
                "  SELECT calendar_year,\n"
                "         AVG(gp/NULLIF(rev,0)) AS industry_avg_gross_margin,\n"
                "         AVG(op/NULLIF(rev,0)) AS industry_avg_operating_margin,\n"
                "         AVG(ni/NULLIF(rev,0)) AS industry_avg_net_margin\n"
                f"  FROM yr WHERE ticker <> '{target_ticker}' GROUP BY 1\n"
                ")\n"
                "SELECT y.calendar_year,\n"
                f"       y.gp/NULLIF(y.rev,0) AS {ticker_lower}_gross_margin,\n"
                f"       y.op/NULLIF(y.rev,0) AS {ticker_lower}_operating_margin,\n"
                f"       y.ni/NULLIF(y.rev,0) AS {ticker_lower}_net_margin,\n"
                "       p.industry_avg_gross_margin, p.industry_avg_operating_margin, p.industry_avg_net_margin\n"
                "FROM yr y JOIN industry_avg p USING (calendar_year)\n"
                f"WHERE y.ticker='{target_ticker}' AND y.calendar_year >= EXTRACT(YEAR FROM CURRENT_DATE) - {years_back}\n"
                "ORDER BY y.calendar_year"
            )

    def _build_growth_sql(self, target_ticker: str, years_back: int = 4, granularity: str = 'annual') -> str:
        ticker_lower = target_ticker.lower()
        tickers = self._get_default_tickers()
        ticker_list = "'" + "','".join(tickers) + "'"
        
        if granularity == 'quarterly':
            # Quarterly growth analysis (QoQ and YoY)
            return (
                "WITH revenue_q AS (\n"
                "    SELECT ticker, calendar_year, calendar_quarter_num, calendar_quarter, SUM(value) AS revenue\n"
                "    FROM comp_financials\n"
                "    WHERE metric = 'Revenue'\n"
                f"      AND ticker IN ({ticker_list})\n"
                "      AND calendar_quarter_num IS NOT NULL\n"
                f"      AND calendar_year >= EXTRACT(YEAR FROM CURRENT_DATE) - {years_back}\n"
                "    GROUP BY ticker, calendar_year, calendar_quarter_num, calendar_quarter\n"
                "), growth AS (\n"
                "    SELECT\n"
                "        ticker, calendar_year, calendar_quarter_num, calendar_quarter,\n"
                "        revenue,\n"
                "        (revenue - LAG(revenue, 1) OVER (PARTITION BY ticker ORDER BY calendar_year, calendar_quarter_num))\n"
                "        / NULLIF(LAG(revenue, 1) OVER (PARTITION BY ticker ORDER BY calendar_year, calendar_quarter_num), 0) AS qoq_growth,\n"
                "        (revenue - LAG(revenue, 4) OVER (PARTITION BY ticker ORDER BY calendar_year, calendar_quarter_num))\n"
                "        / NULLIF(LAG(revenue, 4) OVER (PARTITION BY ticker ORDER BY calendar_year, calendar_quarter_num), 0) AS yoy_growth\n"
                "    FROM revenue_q\n"
                "), industry_avg AS (\n"
                "    SELECT calendar_year, calendar_quarter_num, \n"
                "           AVG(qoq_growth) AS industry_avg_qoq_growth,\n"
                "           AVG(yoy_growth) AS industry_avg_yoy_growth\n"
                f"    FROM growth WHERE ticker <> '{target_ticker}'\n"
                "    GROUP BY calendar_year, calendar_quarter_num\n"
                ")\n"
                "SELECT\n"
                "    g.calendar_year, g.calendar_quarter_num, g.calendar_quarter, g.revenue,\n"
                f"    g.qoq_growth AS {ticker_lower}_qoq_growth,\n"
                f"    g.yoy_growth AS {ticker_lower}_yoy_growth,\n"
                "    ia.industry_avg_qoq_growth, ia.industry_avg_yoy_growth\n"
                "FROM growth g\n"
                "JOIN industry_avg ia\n"
                "ON g.calendar_year = ia.calendar_year AND g.calendar_quarter_num = ia.calendar_quarter_num\n"
                f"WHERE g.ticker = '{target_ticker}'\n"
                "ORDER BY g.calendar_year, g.calendar_quarter_num"
            )
        else:
            # Annual growth analysis (YoY)
            return (
                "WITH revenue_yr AS (\n"
                "    SELECT ticker, calendar_year, SUM(value) AS revenue\n"
                "    FROM comp_financials\n"
                "    WHERE metric = 'Revenue'\n"
                f"      AND ticker IN ({ticker_list})\n"
                "      AND calendar_quarter_num IS NOT NULL\n"
                "    GROUP BY ticker, calendar_year\n"
                "), growth AS (\n"
                "    SELECT\n"
                "        ticker, calendar_year, revenue,\n"
                "        (revenue - LAG(revenue) OVER (PARTITION BY ticker ORDER BY calendar_year))\n"
                "        / NULLIF(LAG(revenue) OVER (PARTITION BY ticker ORDER BY calendar_year), 0) AS yoy_growth\n"
                "    FROM revenue_yr\n"
                "), industry_avg AS (\n"
                "    SELECT calendar_year, AVG(yoy_growth) AS industry_avg_yoy_growth\n"
                f"    FROM growth WHERE ticker <> '{target_ticker}'\n"
                "    GROUP BY calendar_year\n"
                ")\n"
                "SELECT\n"
                "    g.calendar_year, g.revenue,\n"
                f"    g.yoy_growth AS {ticker_lower}_yoy_growth,\n"
                "    ia.industry_avg_yoy_growth\n"
                "FROM growth g\n"
                "JOIN industry_avg ia ON g.calendar_year = ia.calendar_year\n"
                f"WHERE g.ticker = '{target_ticker}' AND g.calendar_year >= EXTRACT(YEAR FROM CURRENT_DATE) - {years_back}\n"
                "ORDER BY g.calendar_year"
            )

    def _build_rnd_sql(self, target_ticker: str, years_back: int = 4, granularity: str = 'annual') -> str:
        ticker_lower = target_ticker.lower()
        tickers = self._get_default_tickers()
        ticker_list = "'" + "','".join(tickers) + "'"
        
        if granularity == 'quarterly':
            # Quarterly R&D intensity analysis
            return (
                "WITH q AS (\n"
                "  SELECT * FROM comp_financials\n"
                "  WHERE calendar_quarter_num IS NOT NULL\n"
                f"    AND ticker IN ({ticker_list})\n"
                "    AND metric IN ('Revenue','R&D Expense')\n"
                f"    AND calendar_year >= EXTRACT(YEAR FROM CURRENT_DATE) - {years_back}\n"
                "), qtr AS (\n"
                "  SELECT ticker, calendar_year, calendar_quarter_num, calendar_quarter,\n"
                "         SUM(CASE WHEN metric='Revenue' THEN value END) AS rev,\n"
                "         SUM(CASE WHEN metric='R&D Expense' THEN value END) AS rnd\n"
                "  FROM q GROUP BY 1,2,3,4\n"
                "), industry_avg AS (\n"
                "  SELECT calendar_year, calendar_quarter_num, AVG(rnd/NULLIF(rev,0)) AS industry_avg_rnd_ratio\n"
                f"  FROM qtr WHERE ticker <> '{target_ticker}' GROUP BY 1,2\n"
                ")\n"
                "SELECT q.calendar_year, q.calendar_quarter_num, q.calendar_quarter,\n"
                f"       q.rnd/NULLIF(q.rev,0) AS {ticker_lower}_rnd_intensity,\n"
                "       p.industry_avg_rnd_ratio\n"
                "FROM qtr q JOIN industry_avg p USING (calendar_year, calendar_quarter_num)\n"
                f"WHERE q.ticker='{target_ticker}'\n"
                "ORDER BY q.calendar_year, q.calendar_quarter_num"
            )
        else:
            # Annual R&D intensity analysis (original logic)
            return (
                "WITH q AS (\n"
                "  SELECT * FROM comp_financials\n"
                "  WHERE calendar_quarter_num IS NOT NULL\n"
                f"    AND ticker IN ({ticker_list})\n"
                "    AND metric IN ('Revenue','R&D Expense')\n"
                "), yr AS (\n"
                "  SELECT ticker, calendar_year,\n"
                "         SUM(CASE WHEN metric='Revenue' THEN value END) AS rev,\n"
                "         SUM(CASE WHEN metric='R&D Expense' THEN value END) AS rnd\n"
                "  FROM q GROUP BY 1,2\n"
                "), industry_avg AS (\n"
                "  SELECT calendar_year, AVG(rnd/NULLIF(rev,0)) AS industry_avg_rnd_ratio\n"
                f"  FROM yr WHERE ticker <> '{target_ticker}' GROUP BY 1\n"
                ")\n"
                "SELECT y.calendar_year,\n"
                f"       y.rnd/NULLIF(y.rev,0) AS {ticker_lower}_rnd_intensity,\n"
                "       p.industry_avg_rnd_ratio\n"
                "FROM yr y JOIN industry_avg p USING (calendar_year)\n"
                f"WHERE y.ticker='{target_ticker}' AND y.calendar_year >= EXTRACT(YEAR FROM CURRENT_DATE) - {years_back}\n"
                "ORDER BY y.calendar_year"
            )

    def _get_company_mapping(self) -> Tuple[Dict[str, Tuple[str, str]], Tuple[str, str]]:
        """Return lowercase alias -> (ticker, short_name) mapping and default company tuple."""
        companies_config = self.configs.get('companies', {})
        companies = companies_config.get('companies', {}).get('semiconductor', [])

        mapping: Dict[str, Tuple[str, str]] = {}
        default_company: Tuple[str, str] = ('NVDA', 'Nvidia')

        for company in companies:
            ticker = company.get('ticker', '')
            short_name = company.get('short_name', '') or ticker
            aliases = company.get('aliases', [])

            if company.get('priority') == 1 and ticker:
                default_company = (ticker, short_name)

            if ticker:
                mapping[ticker.lower()] = (ticker, short_name)
            for alias in aliases:
                if isinstance(alias, str) and alias.strip():
                    mapping[alias.lower()] = (ticker, short_name)

        return mapping, default_company

    def _extract_companies(self, query: str) -> List[Tuple[str, str]]:
        """Return ordered list of (ticker, short_name) appearing in the query."""
        q = (query or '').lower()
        mapping, _ = self._get_company_mapping()
        matches: List[Tuple[int, Tuple[str, str]]] = []

        for alias, value in mapping.items():
            idx = q.find(alias)
            if idx != -1:
                matches.append((idx, value))

        # Sort by position in query and deduplicate tickers preserving order
        matches.sort(key=lambda item: item[0])
        seen: set[str] = set()
        ordered: List[Tuple[str, str]] = []
        for _, company in matches:
            ticker = company[0]
            if ticker not in seen:
                ordered.append(company)
                seen.add(ticker)
        return ordered

    def _extract_company(self, query: str) -> Tuple[str, str]:
        """Extract primary company ticker and display name from the query text."""
        companies = self._extract_companies(query)
        if companies:
            return companies[0]
        _, default_company = self._get_company_mapping()
        return default_company
        
    def _extract_time_period(self, query: str) -> int:
        """Extract time period (years back) from user query"""
        q_lower = (query or '').lower()
        
        # Look for patterns like "past 6 years", "last 3 years", "6 years", etc.
        import re

        start_year, end_year = self._extract_year_bounds(query)
        if start_year is not None and end_year is not None:
            span = max(end_year - start_year, 0)
            print(f"[TIME EXTRACTION] Found explicit year range {start_year}-{end_year}, using years_back = {span}")
            return span or 0
        
        # Pattern to match numbers followed by year/years (with optional punctuation)
        year_patterns = [
            r'(?:past|last)\s+(\d+)\s+years?\??',  # "past 3 years?" or "last 5 years"
            r'(\d+)\s+years?\??',                   # "3 years?" or "5 years"
            r'(?:past|last)\s+(\d+)\s+yrs?\??',     # "past 3 yrs?" or "last 5 yrs"
            r'(\d+)\s+yrs?\??'                      # "3 yrs?" or "5 yrs"
        ]
        
        print(f"[TIME EXTRACTION DEBUG] Input query: '{query}' -> processed: '{q_lower}'")
        
        for i, pattern in enumerate(year_patterns):
            match = re.search(pattern, q_lower)
            if match:
                years = int(match.group(1))
                print(f"[TIME EXTRACTION] Pattern {i+1} matched! Found {years} years in query: '{query}'")
                print(f"[TIME EXTRACTION] Returning years_back = {years - 1} (total {years} years)")
                return years - 1  # Convert to years back (3 years = current + 2 back)
            else:
                print(f"[TIME EXTRACTION DEBUG] Pattern {i+1} '{pattern}' did not match")
        
        # Default to 5 years back (6 years total including current)
        print(f"[TIME EXTRACTION] No time period found in query '{query}', using default 4 years back (5 total)")
        return 4  # Default: current year + 4 years back = 5 years total

    def _extract_year_bounds(self, query: str) -> Tuple[Optional[int], Optional[int]]:
        """Extract explicit start/end year (4-digit) from the query if present."""
        if not query:
            return None, None
        import re

        tokens = re.findall(r"(20\d{2})", query)
        ordered_years: List[int] = []
        for token in tokens:
            try:
                year = int(token)
                if year not in ordered_years:
                    ordered_years.append(year)
            except ValueError:
                continue
        if len(ordered_years) >= 2:
            return ordered_years[0], ordered_years[1]
        if len(ordered_years) == 1:
            return ordered_years[0], ordered_years[0]
        return None, None
        
    def _extract_granularity(self, query: str) -> str:
        """Extract data granularity (quarterly vs annual) from user query"""
        q_lower = (query or '').lower()
        
        # Quarterly keywords - explicit quarterly requests
        quarterly_keywords = [
            'quarterly', 'quarter', 'quarters',
            'q1', 'q2', 'q3', 'q4',
            'qoq', 'quarter over quarter', 'quarter-over-quarter',
            'by quarter', 'each quarter', 'per quarter'
        ]
        
        # Annual keywords - explicit annual requests  
        annual_keywords = [
            'annual', 'annually', 'yearly', 'year',
            'yoy', 'year over year', 'year-over-year',
            'by year', 'each year', 'per year'
        ]
        
        # Check for quarterly indicators
        if any(keyword in q_lower for keyword in quarterly_keywords):
            print(f"[GRANULARITY] Detected quarterly request in query: {query}")
            return 'quarterly'
            
        # Check for explicit annual indicators
        if any(keyword in q_lower for keyword in annual_keywords):
            print(f"[GRANULARITY] Detected annual request in query: {query}")
            return 'annual'
            
        # Default to annual for most financial analysis unless quarterly is explicitly requested
        print(f"[GRANULARITY] No specific granularity found, defaulting to annual")
        return 'annual'
        
    def _get_default_tickers(self) -> List[str]:
        """Get default company tickers from companies.yaml"""
        companies_config = self.configs.get('companies', {})
        selection_rules = companies_config.get('selection_rules', {})
        default_companies = selection_rules.get('default_companies', {})
        return default_companies.get('tickers', ["AMD", "AVGO", "INTC", "MU", "NVDA", "QCOM", "TXN"])
        
    def _get_available_metrics_from_config(self) -> List[str]:
        """Get available metrics from metrics.yaml"""
        metrics_config = self.configs.get('metrics', {})
        metrics = metrics_config.get('metrics', {})
        
        available_metrics = []
        for metric_key, metric_info in metrics.items():
            database_name = metric_info.get('database_name', metric_key)
            available_metrics.append(database_name)
            
        # If no metrics found in config, return hardcoded fallback
        if not available_metrics:
            available_metrics = [
                "Accounts Payable", "Accounts Receivable", "CFF", "CFI", "CFO", "CapEx",
                "Cash & Equiv.", "Cost of Revenue", "EPS Basic", "EPS Diluted", "Gross Profit",
                "Income Tax", "Interest Expense", "Inventory", "Long-Term Debt", "Net Income",
                "Operating Income", "PP&E Net", "R&D Expense", "Revenue", "SG&A", "Share Repurchase",
                "Stockholders' Equity", "Total Assets", "Total Curr. Assets", "Wtd Avg Shares Basic",
                "Wtd Avg Shares Diluted", "Dividends Paid", "Income Before Tax", "Total Liabilities",
                "Assets", "Cost of Goods Sold", "Current Assets", "Current Liabilities",
                "Depreciation & Amortization", "EBITDA", "Equity", "Expenses", "Fixed Assets",
                "Income Tax Expense", "Liabilities", "Operating Expenses", "Other Expenses",
                "Other Income", "Pre-Tax Income", "SG&A Expenses", "Total Liabilities & Equity",
                "Working Capital"
            ]
            
        return available_metrics
        
    def _get_sql_template(self, pattern_key: str) -> Optional[str]:
        """Get SQL template from queries.yaml"""
        queries_config = self.configs.get('queries', {})
        query_patterns = queries_config.get('query_patterns', {})
        print(f"[TEMPLATE DEBUG] Looking up template for key: '{pattern_key}'")
        print(f"[TEMPLATE DEBUG] Available patterns: {list(query_patterns.keys())}")
        pattern_info = query_patterns.get(pattern_key, {})
        template = pattern_info.get('sql_template')
        print(f"[TEMPLATE DEBUG] Template found: {'YES' if template else 'NO'}")
        if template:
            print(f"[TEMPLATE DEBUG] Template length: {len(template)} chars, preview: {template[:100]}...")
        return template
        
    def _substitute_sql_template(
        self,
        template: str,
        target_ticker: str,
        years_back: Optional[int] = None,
        granularity: str = 'annual',
        *,
        primary_metric: Optional[str] = None,
        start_year: Optional[int] = None,
        end_year: Optional[int] = None,
        tickers: Optional[List[str]] = None,
    ) -> str:
        """Substitute parameters in SQL template with conditional clauses based on granularity"""
        default_tickers = [ticker.upper() for ticker in self._get_default_tickers()]
        ticker_choices = [ticker.upper() for ticker in (tickers or []) if ticker and isinstance(ticker, str)]
        ticker_subset = [ticker for ticker in ticker_choices if ticker in default_tickers]
        if not ticker_subset:
            ticker_subset = default_tickers
        ticker_list = "'" + "','".join(ticker_subset) + "'"

        # Use provided years_back or fall back to config default
        if years_back is None:
            queries_config = self.configs.get('queries', {})
            template_vars = queries_config.get('template_variables', {})
            years_back = template_vars.get('default_years_back', 5)
        
        # Generate conditional SQL clauses based on granularity
        if granularity == 'quarterly':
            select_clause = "calendar_year, calendar_quarter_num, calendar_quarter"
            group_by_clause = "calendar_year, calendar_quarter_num, calendar_quarter"
            join_clause = "cr.calendar_year = mr.calendar_year AND cr.calendar_quarter_num = mr.calendar_quarter_num"
            order_by_clause = "cr.calendar_year, cr.calendar_quarter_num"
            growth_window = "4"  # same quarter last year
            period_filter_clause = "calendar_quarter_num IS NOT NULL"
        else:  # annual
            select_clause = "calendar_year"
            group_by_clause = "calendar_year"
            join_clause = "cr.calendar_year = mr.calendar_year"
            order_by_clause = "cr.calendar_year"
            growth_window = "1"  # prior year
            period_filter_clause = "1=1"

        if start_year is not None and end_year is not None:
            year_filter_clause = f"calendar_year BETWEEN {start_year} AND {end_year}"
        elif start_year is not None:
            year_filter_clause = f"calendar_year >= {start_year}"
        elif end_year is not None:
            year_filter_clause = f"calendar_year <= {end_year}"
        elif years_back is not None:
            year_filter_clause = f"calendar_year >= EXTRACT(YEAR FROM CURRENT_DATE) - {years_back}"
        else:
            year_filter_clause = "1=1"

        # Perform substitutions
        substituted = template.replace('{target_ticker}', target_ticker)
        substituted = substituted.replace('{ticker_list}', ticker_list)
        substituted = substituted.replace('{years_back}', str(years_back))
        substituted = substituted.replace('{select_clause}', select_clause)
        substituted = substituted.replace('{group_by_clause}', group_by_clause)
        substituted = substituted.replace('{join_clause}', join_clause)
        substituted = substituted.replace('{order_by_clause}', order_by_clause)
        substituted = substituted.replace('{growth_window}', growth_window)
        substituted = substituted.replace('{period_filter_clause}', period_filter_clause)
        substituted = substituted.replace('{year_filter_clause}', year_filter_clause)

        metric_name = (primary_metric or 'Revenue').strip()
        metric_name = metric_name.replace("'", "''")
        substituted = substituted.replace('{primary_metric}', metric_name)

        start_year_value = str(start_year) if start_year is not None else 'NULL'
        end_year_value = str(end_year) if end_year is not None else 'NULL'
        substituted = substituted.replace('{start_year}', start_year_value)
        substituted = substituted.replace('{end_year}', end_year_value)

        print(f"[SQL TEMPLATE] Using {granularity} granularity with clauses:")
        print(f"[SQL TEMPLATE]   SELECT: {select_clause}")
        print(f"[SQL TEMPLATE]   GROUP BY: {group_by_clause}")

        return substituted
        
    def _get_chart_colors(self, theme: str = 'light') -> List[str]:
        """Get chart colors from charts.yaml"""
        charts_config = self.configs.get('charts', {})
        themes = charts_config.get('themes', {})
        theme_config = themes.get(theme, {})
        chart_colors = theme_config.get('chart_colors', {})
        primary_palette = chart_colors.get('primary_palette', [])
        
        # Fallback to hardcoded colors
        if not primary_palette:
            primary_palette = ['#5470C6', '#91CC75', '#FAC858', '#EE6666', '#73C0DE', '#3BA272', '#FC8452']
            
        return primary_palette
        
    def _get_chart_title(self, query: str, target_name: str, years_back: int = 4) -> str:
        """Get chart title using patterns from charts.yaml"""
        charts_config = self.configs.get('charts', {})
        title_patterns = charts_config.get('title_patterns', {})
        
        q = (query or '').lower()
        years = str(years_back + 1)  # Convert years_back to total years for display
        
        # Match query patterns to title patterns
        if 'market share' in q and 'all' in q:
            pattern = title_patterns.get('market_share', {}).get('all_companies', '{company_name} Market Share – Last {years} Years')
            return pattern.replace('{company_name}', 'Semiconductor').replace('{years}', years)
        elif 'market share' in q:
            pattern = title_patterns.get('market_share', {}).get('single_company', '{company_name} Market Share – Last {years} Years')
            return pattern.replace('{company_name}', target_name).replace('{years}', years)
        elif ('margin' in q and ('peer' in q or 'compare' in q or 'average' in q)):
            if 'average' in q or 'industry average' in q:
                pattern = title_patterns.get('margins', {}).get('vs_peers', '{company_name} Margins vs Industry Average – Last {years} Years')
            else:
                pattern = title_patterns.get('margins', {}).get('vs_peers', '{company_name} Margins vs Peers – Last {years} Years')
            return pattern.replace('{company_name}', target_name).replace('{years}', years)
        elif ('r&d' in q or 'r and d' in q or 'rnd' in q):
            if 'average' in q or 'industry average' in q:
                pattern = title_patterns.get('rnd', {}).get('intensity', '{company_name} R&D Intensity vs Industry Average – Last {years} Years')
            else:
                pattern = title_patterns.get('rnd', {}).get('intensity', '{company_name} R&D Intensity vs Peers – Last {years} Years')
            return pattern.replace('{company_name}', target_name).replace('{years}', years)
        elif ('growth' in q or 'growing' in q):
            if 'average' in q or 'industry average' in q:
                pattern = title_patterns.get('growth', {}).get('revenue_growth', '{company_name} Revenue Growth vs Industry Average – Last {years} Years')
                return pattern.replace('{company_name}', target_name).replace('{years}', years)
            else:
                pattern = title_patterns.get('growth', {}).get('revenue_growth', '{company_name} Revenue Growth – {period} Analysis')
                return pattern.replace('{company_name}', target_name).replace('{period}', 'Time Series')
        else:
            # Generic fallback
            pattern = title_patterns.get('generic', {}).get('time_series', '{metric} – Time Series Analysis')
            return pattern.replace('{metric}', 'Financial Metrics')
            
    def _get_chart_layout(self, layout_name: str = 'default') -> Dict[str, Any]:
        """Get chart layout configuration from charts.yaml"""
        charts_config = self.configs.get('charts', {})
        layouts = charts_config.get('layouts', {})
        layout = layouts.get(layout_name, {})
        
        # Fallback to hardcoded layout
        if not layout:
            layout = {
                'title': {'left': 'center', 'top': '5%', 'textStyle': {'fontSize': 18, 'fontWeight': 'bold'}},
                'legend': {'top': '10%', 'left': 'center', 'orient': 'horizontal', 'itemGap': 20},
                'grid': {'left': '3%', 'right': '4%', 'bottom': '3%', 'top': '20%', 'containLabel': True},
                'tooltip': {'trigger': 'axis', 'axisPointer': {'type': 'cross'}}
            }
            
        return layout

    def _select_chart_columns(self, query: str, candidate_columns: List[str]) -> List[str]:
        """Select which measure(s) to chart based on the user's query intent.
        Always keep full data available for analysis, but restrict chart to most relevant columns.
        """
        q = (query or '').lower()
        cols_lower = {c.lower(): c for c in candidate_columns}
        ticker, _ = self._extract_company(query)
        ticker_lower = ticker.lower()

        # 1) Market share → prefer {ticker}_market_share; if 'all' present, show generic 'market_share'
        if 'market share' in q and 'all' in q:
            # Prefer explicit percent column first
            for key in ['market_share_percent']:
                if key in cols_lower:
                    return [cols_lower[key]]
            # Next: generic market_share (ratio)
            for key in ['market_share']:
                if key in cols_lower:
                    return [cols_lower[key]]
            # Fallback: any *_market_share* column
            for name in candidate_columns:
                nl = name.lower()
                if nl.endswith('market_share_percent') or nl.endswith('_market_share_percent') or nl.endswith('_market_share') or nl == 'market_share':
                    return [name]
        if 'market share' in q:
            # First: exact ticker-specific market share column
            preferred = f"{ticker_lower}_market_share_percent"
            if preferred in cols_lower:
                return [cols_lower[preferred]]
            preferred = f"{ticker_lower}_market_share"
            if preferred in cols_lower:
                return [cols_lower[preferred]]
            # Next: any *_market_share column
            for name in candidate_columns:
                if name.lower().endswith('market_share_percent') or name.lower().endswith('_market_share'):
                    return [name]
            # Then generic tokens
            for key in ['market_share_percent', 'market_share', 'share']:
                if key in cols_lower:
                    return [cols_lower[key]]
            # fallback to ratio-like single column
            ratio_like = [c for c in candidate_columns if 'share' in c or 'ratio' in c]
            if ratio_like:
                return [ratio_like[0]]

        # 2) Margin compare → prefer nvda_nm and peer_nm (net margin)
        if ('margin' in q and ('peer' in q or 'compare' in q)):
            picks = []
            for key in [f'{ticker_lower}_net_margin', 'peer_net_margin']:
                if key in cols_lower:
                    picks.append(cols_lower[key])
            if picks:
                return picks

        # 3) Working capital stress (R&D intensity proxy) → nvda_rnd_ratio and peer_rnd_ratio
        if ('working-capital' in q or 'working capital' in q):
            picks = []
            for key in [f'{ticker_lower}_rnd_ratio', 'peer_rnd_ratio']:
                if key in cols_lower:
                    picks.append(cols_lower[key])
            if picks:
                return picks

        # Default: chart all candidate columns
        return candidate_columns
    

    async def _get_available_metrics(self) -> List[str]:
        """Query database for actual available metrics"""
        conn = None
        try:
            import time as _time
            _t0 = _time.perf_counter()
            conn = await asyncpg.connect(self.database_url, statement_cache_size=0)
            _t_conn = (_time.perf_counter() - _t0) * 1000.0
            print(f"[DB] Metrics fetch: connected in {int(_t_conn)} ms")
            _t1 = _time.perf_counter()
            rows = await conn.fetch("SELECT DISTINCT metric FROM comp_financials ORDER BY metric")
            _t_q = (_time.perf_counter() - _t1) * 1000.0
            metrics = [row['metric'] for row in rows]
            print(f"[DB] Metrics fetch: {len(metrics)} metrics in {int(_t_q)} ms")
            return metrics
        except Exception as e:
            print(f"[METRICS QUERY ERROR] {e}")
            # Return fallback list from schema
            return self._get_available_metrics_from_config()
        finally:
            if conn:
                await conn.close()
    
    async def _sql_agent(self, state: WorkflowState) -> WorkflowState:
        """Stage 1: LLM-driven schema analysis and SQL generation"""
        try:
            print(f"[SQL AGENT] Starting SQL generation for query: {state['query'][:100]}...")
            
            # Route known questions to handcrafted SQL for precision
            q_lower = (state.get('query') or '').lower()
            handcrafted_sql: Optional[str] = None

            # Determine target company and intent once
            intent = self._detect_intent(state.get('query', ''))
            print(f"[SQL AGENT DEBUG] Query: '{state.get('query', '')}' -> Intent: {intent}")
            target_ticker, target_name = intent['ticker'], intent['name']
            ticker_lower = target_ticker.lower()
            tickers_override = intent.get('tickers') or []
            start_year = intent.get('start_year')
            end_year = intent.get('end_year')
            template_tickers_override = tickers_override if (intent.get('kind') == 'revenue_comparison' and tickers_override) else None
            primary_metric_override = 'Revenue' if intent.get('kind') == 'revenue_comparison' else None

            # Extract time period and granularity from user query
            years_back = self._extract_time_period(state.get('query', ''))
            granularity = self._extract_granularity(state.get('query', ''))
            if start_year is not None and end_year is not None:
                years_back = max(end_year - start_year, 0)
                print(f"[SQL AGENT] Using explicit year range {start_year}-{end_year} (span {years_back + 1} years)")
            else:
                print(f"[SQL AGENT] Using {years_back + 1} years of data (current + {years_back} back)")
            print(f"[SQL AGENT] Using {granularity} granularity")
            
            # Try to get SQL template from YAML first
            handcrafted_sql = None
            template = None
            if intent['kind']:
                template = self._get_sql_template(intent['kind'])
                print(f"[SQL DEBUG] Template lookup for '{intent['kind']}': {'FOUND' if template else 'NOT FOUND'}")
                if template:
                    handcrafted_sql = self._substitute_sql_template(
                        template,
                        target_ticker,
                        years_back,
                        granularity,
                        primary_metric=primary_metric_override,
                        start_year=start_year,
                        end_year=end_year,
                        tickers=template_tickers_override,
                    )
                    print(f"[SQL AGENT] Using YAML template for pattern: {intent['kind']}")
                    print(f"[SQL DEBUG] Generated SQL (first 500 chars): {handcrafted_sql[:500]}...")
                    print("[SQL AGENT] Using YAML template for known query pattern")
            
            # Fallback to hardcoded SQL methods if no YAML template found
            if not handcrafted_sql:
                
                if intent['kind'] == 'market_share_all' or intent['kind'] == 'market_share' or intent['kind'] == 'market_share_single':
                    handcrafted_sql = self._build_market_share_sql(all_companies=(intent['kind'] == 'market_share_all'), target_ticker=target_ticker, years_back=years_back, granularity=granularity)
                elif intent['kind'] == 'margins_vs_peers':
                    handcrafted_sql = self._build_margins_sql(target_ticker, years_back, granularity)
                elif intent['kind'] == 'margin_growth_vs_peers':
                    # Prefer YAML template; if missing, derive via margins + LAG
                    template = self._get_sql_template('margin_growth_vs_peers')
                    if template:
                        handcrafted_sql = self._substitute_sql_template(
                            template,
                            target_ticker,
                            years_back,
                            granularity,
                            primary_metric=primary_metric_override,
                            start_year=start_year,
                            end_year=end_year,
                            tickers=template_tickers_override,
                        )
                    else:
                        handcrafted_sql = None
                elif intent['kind'] == 'growth_vs_peers' or intent['kind'] == 'revenue_growth_analysis':
                    handcrafted_sql = self._build_growth_sql(target_ticker, years_back, granularity)
                elif intent['kind'] == 'rnd_intensity_vs_peers':
                    handcrafted_sql = self._build_rnd_sql(target_ticker, years_back, granularity)
                elif intent['kind'] == 'rnd_expense_vs_peers':
                    template = self._get_sql_template('rnd_expense_vs_peers')
                    if template:
                        handcrafted_sql = self._substitute_sql_template(
                            template,
                            target_ticker,
                            years_back,
                            granularity,
                            primary_metric=primary_metric_override,
                            start_year=start_year,
                            end_year=end_year,
                            tickers=template_tickers_override,
                        )
                    else:
                        handcrafted_sql = None

            if handcrafted_sql:
                sql_source = "YAML template" if template else "hardcoded SQL"
                print(f"[SQL AGENT DEBUG] Final SQL source: {sql_source} for pattern: {intent['kind']}")
                print(f"[SQL AGENT] Using {sql_source} for pattern: {intent['kind']}")
                sql_query = handcrafted_sql
                data = await self._execute_query(sql_query)
                result = {
                    **state,
                    "sql": sql_query,
                    "data": data,
                    "years_back": years_back,
                    "step": "sql_complete"
                }
                # Attach display company for title context
                result["thinking"] = f"Target company: {target_name} ({target_ticker})"
                return result

            # Query database for real metrics
            print("[SQL AGENT] Querying database for available metrics...")
            available_metrics = await self._get_available_metrics()
            print(f"[SQL AGENT] Found {len(available_metrics)} metrics in database")
            
            # Build comprehensive SQL prompt with all improvements
            schema_prompt = f"""
You are a PostgreSQL expert generating queries for financial data analysis.

DATABASE STRUCTURE:
comp_financials is long-format: one row = one metric value per ticker/quarter.
- Table: comp_financials  
- Columns: ticker, metric, value, tag_used, date, calendar_year, calendar_quarter_num, calendar_quarter
- Companies: {', '.join(self._get_default_tickers())}

AVAILABLE METRICS (use EXACT names from this list):
{', '.join(available_metrics)}

Synonyms: R&D → "R&D Expense", OpEx → "Operating Expenses", CapEx → "CapEx", CFO → "CFO", Cash → "Cash & Equiv."



3) Derived metrics (gross margin %):
SELECT
  ticker, calendar_year, calendar_quarter_num, calendar_quarter,
  100 * (SUM(value) FILTER (WHERE metric = 'Gross Profit') / 
         NULLIF(SUM(value) FILTER (WHERE metric = 'Revenue'), 0)) AS gross_margin_pct
FROM comp_financials  
WHERE ticker IN ('AMD', 'INTC') AND calendar_year >= 2023
GROUP BY ticker, calendar_year, calendar_quarter_num, calendar_quarter
ORDER BY ticker, calendar_year, calendar_quarter_num
LIMIT 500


USER QUERY: {state['query']}

Generate ONLY a valid PostgreSQL SELECT statement:
Rules:
- Never use ROUND(), TRUNC(), TO_CHAR(), or other formatting helpers. Return raw numeric values and let downstream layers format.
- If precision is required, cast expressions using ::numeric or ::decimal instead of formatting.
"""

            print("[SQL AGENT] Calling Responses API for SQL generation...")

            # Use unified client with Responses API (sync)
            messages = [{"role": "system", "content": schema_prompt}]
            import asyncio
            import concurrent.futures

            async def _generate_sql():
                response, _ = await self.unified_client.simple_completion(
                    messages=messages,
                    reasoning_effort="low",
                    model="gpt-5-mini-2025-08-07"
                )
                return response

            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(asyncio.run, _generate_sql())
                sql_query = future.result().strip()
            print(f"[SQL AGENT] Generated SQL: {sql_query[:200]}...")
            
            # Clean up SQL query
            sql_query = re.sub(r'```sql\s*', '', sql_query)
            sql_query = re.sub(r'```\s*$', '', sql_query)
            sql_query = sql_query.strip()
            
            # Remove trailing semicolons and comments
            sql_query = re.sub(r';+\s*$', '', sql_query)
            sql_query = re.sub(r'--.*$', '', sql_query, flags=re.MULTILINE)
            sql_query = sql_query.strip()
            
            # Basic SQL validation
            if not sql_query.upper().startswith('SELECT'):
                raise ValueError("Generated query must start with SELECT")
            
            if ';' in sql_query:
                raise ValueError("Query contains semicolon - not allowed")
                
            if not ('comp_financials' in sql_query.lower()):
                raise ValueError("Query must use comp_financials table")
            
            print(f"[SQL AGENT] Cleaned SQL: (len={len(sql_query)}) {sql_query[:200]}...")
            
            # Execute query
            print("[SQL AGENT] Executing query...")
            data = await self._execute_query(sql_query)
            print(f"[SQL AGENT] Query returned {len(data)} rows")
            
            # Log SQL data details for debugging
            if data:
                print(f"[SQL AGENT] Data structure - Columns: {list(data[0].keys())}")
                print(f"[SQL AGENT] Sample rows:")
                for i, row in enumerate(data[:3]):
                    print(f"[SQL AGENT]   Row {i+1}: {dict(row)}")
                
                # Check for required columns
                required_cols = ['ticker', 'calendar_year', 'calendar_quarter_num', 'calendar_quarter']
                missing_cols = [col for col in required_cols if col not in data[0].keys()]
                if missing_cols:
                    print(f"[SQL AGENT] WARNING: Missing required columns: {missing_cols}")
            else:
                print("[SQL AGENT] WARNING: No data returned from query")
            
            return {
                **state,
                "sql": sql_query,
                "data": data,
                "years_back": years_back,
                "granularity": granularity,
                "step": "sql_complete"
            }
            
        except Exception as e:
            error_msg = f"SQL Agent Error: {str(e)}"
            print(f"[SQL AGENT ERROR] {error_msg}")
            return {
                **state,
                "errors": state.get("errors", []) + [error_msg],
                "step": "sql_error"
            }
    
    async def _echarts_agent(self, state: WorkflowState) -> WorkflowState:
        """Stage 2: Convert query results into ECharts visualizations"""
        try:
            print("[ECHARTS AGENT] Starting chart generation...")
            
            if not state.get("data"):
                raise ValueError("No data available for chart generation")
            
            data = state["data"]
            print(f"[ECHARTS AGENT] Processing {len(data)} data rows")
            
            # Analyze data structure for chart type determination
            has_time_data = any(
                row.get('date') or row.get('calendar_quarter') or (row.get('calendar_year') is not None)
                for row in data
            )
            unique_tickers = list(set(row.get('ticker', '') for row in data if row.get('ticker')))
            unique_metrics = list(set(row.get('metric', '') for row in data if row.get('metric')))
            
            print(f"[ECHARTS AGENT] Data analysis - Time data: {has_time_data}, Tickers: {unique_tickers}, Metrics: {unique_metrics}")
            
            # Determine chart type based on data characteristics
            chart_type = self._determine_chart_type(data, unique_tickers, unique_metrics, has_time_data, state.get('query', ''))
            print(f"[ECHARTS AGENT] Determined chart type: {chart_type}")
            
            # Get years_back from state for chart title generation
            years_back = state.get('years_back', 4)
            print(f"[ECHARTS AGENT] Using years_back: {years_back}")
            
            # Generate ECharts specification (pass user query to guide column selection)
            chart_spec = self._build_echarts_spec(
                data,
                chart_type,
                unique_tickers,
                unique_metrics,
                has_time_data,
                state.get('query', ''),
                years_back
            )
            print(f"[ECHARTS AGENT] Generated chart spec with keys: {list(chart_spec.keys())}")
            
            return {
                **state,
                "chart_spec": chart_spec,
                "step": "echarts_complete"
            }
            
        except Exception as e:
            error_msg = f"ECharts Agent Error: {str(e)}"
            print(f"[ECHARTS AGENT ERROR] {error_msg}")
            return {
                **state,
                "errors": state.get("errors", []) + [error_msg],
                "step": "echarts_error"
            }
    
    async def _analysis_agent(self, state: WorkflowState) -> WorkflowState:
        """Stage 3: Stream real-time financial insights"""
        try:
            if not state.get("data"):
                raise ValueError("No data available for analysis")
            
            # Prepare analysis prompt
            data_summary = self._prepare_data_summary(state["data"])
            
            analysis_prompt = f"""
You are a financial analyst providing concise, number-driven insights. Analyze this financial data and provide 4-6 bullet points with specific figures, growth rates, and comparisons.

USER QUESTION:
{state['query']}

SQL USED:
{state.get('sql', '')}

DATA SUMMARY:
{data_summary}

Focus on:
- Exact figures and specific time periods  
- Growth rates and percentage changes
- Company comparisons where relevant
- Key trends and patterns
- Actionable insights

Important:
- Use the context from the SQL to understand what the measures represent (e.g., market_share, net_margin, QoQ growth).
- Do not restate the SQL verbatim; interpret the results for the user.
- Keep each bullet point concise and data-driven.
"""

            # This will be handled by the streaming endpoint
            analysis_text = "Analysis will be streamed in real-time"
            
            return {
                **state,
                "analysis": analysis_text,
                "step": "analysis_complete"
            }
            
        except Exception as e:
            error_msg = f"Analysis Agent Error: {str(e)}"
            return {
                **state,
                "errors": state.get("errors", []) + [error_msg],
                "step": "analysis_error"
            }
    
    async def _execute_query(self, sql_query: str) -> List[Dict[str, Any]]:
        """Execute SQL query with modern async patterns"""
        conn = None
        try:
            # Mask DSN for logs
            def _mask_dsn(dsn: str) -> str:
                try:
                    if '://' in dsn and '@' in dsn:
                        scheme, rest = dsn.split('://', 1)
                        userinfo, hostpart = rest.split('@', 1)
                        user = userinfo.split(':', 1)[0]
                        host = hostpart.split('/', 1)[0]
                        return f"{scheme}://{user}:***@{host}/…"
                except Exception:
                    pass
                return "postgresql://***"

            print(f"[DB] Connecting to {_mask_dsn(self.database_url)}...")
            import time as _time
            _t0 = _time.perf_counter()
            conn = await asyncpg.connect(self.database_url, statement_cache_size=0)
            _t_conn = (_time.perf_counter() - _t0) * 1000.0
            print(f"[DB] Connected in {int(_t_conn)} ms")
            
            # Set statement timeout at database level
            try:
                await conn.execute("SET statement_timeout = '15s'")
                print("[DB] statement_timeout set to 15s")
            except Exception as _st_err:
                print(f"[DB] Unable to set statement_timeout: {_st_err}")
            
            # Execute query - LLM should already include LIMIT 500 and proper ORDER BY
            preview = sql_query[:120].replace("\n", " ")
            print(f"[DB] Executing SQL (len={len(sql_query)}): {preview}...")
            
            # Direct query execution - let asyncpg handle timeouts
            _t1 = _time.perf_counter()
            rows = await conn.fetch(sql_query)
            _t_exec = (_time.perf_counter() - _t1) * 1000.0
            
            # Convert to list of dicts
            data = [dict(row) for row in rows]
            sample_keys = list(data[0].keys()) if data else []
            print(f"[DB] Query completed in {int(_t_exec)} ms, rows={len(data)}, sample_keys={sample_keys}")
            
            return data
            
        except Exception as e:
            print(f"[DB ERROR] {e.__class__.__name__}: {str(e)}")
            _preview = sql_query[:160].replace("\n", " ")
            print(f"[DB ERROR] SQL len={len(sql_query)} preview={_preview}...")
            raise Exception(f"Database query failed: {str(e)}")
        finally:
            if conn:
                print("[DB] Closing connection")
                await conn.close()
    
    def _determine_chart_type(self, data: List[Dict], tickers: List[str], metrics: List[str], has_time: bool, query: str = "") -> str:
        """Determine appropriate chart type based on data characteristics and user wording"""
        q = (query or '').lower()
        if 'bar chart' in q or 'bar' in q:
            return 'bar'
        # If time axis is present, prefer a line chart even with no ticker column (e.g., year-only data)
        if has_time:
            return "line"
        if len(tickers) > 1 and len(metrics) == 1:
            return "bar"   # Compare companies on single metric
        if len(metrics) > 1 and len(tickers) == 1:
            return "bar"   # Compare metrics for single company
        return "bar"       # Default to bar chart
    
    def _build_echarts_spec(self, data: List[Dict], chart_type: str, tickers: List[str], metrics: List[str], has_time: bool, query: str, years_back: int = 4) -> Dict[str, Any]:
        """Build deterministic ECharts specification"""
        
        if has_time:
            series_type = 'bar' if chart_type == 'bar' else 'line'
            return self._build_time_series_chart(data, tickers, metrics, query, series_type, years_back)
        else:
            return self._build_bar_chart(data, tickers, metrics, years_back)
    
    def _build_time_series_chart(self, data: List[Dict], tickers: List[str], metrics: List[str], query: str, series_type: str = 'line', years_back: int = 4) -> Dict[str, Any]:
        """Build time series chart (line or bar) for both traditional and derived metrics"""
        
        print(f"[ECHARTS] Building time series chart with {len(data)} data points")
        print(f"[ECHARTS] Sample data structure: {data[0] if data else 'N/A'}")
        
        # Identify data columns (exclude standard columns)
        standard_cols = {'ticker', 'calendar_year', 'calendar_quarter_num', 'calendar_quarter', 'date', 'tag_used'}
        if data:
            all_cols = set(data[0].keys())
            candidate_columns = list(all_cols - standard_cols)
            # Decide which columns to include and which to show by default
            default_columns = self._select_chart_columns(query, candidate_columns)
            q_lower = (query or '').lower()
            if ('margin' in q_lower and ('peer' in q_lower or 'compare' in q_lower)):
                # Include all margin-related columns so user can pick via UI
                data_columns = [c for c in candidate_columns if ('margin' in c.lower())]
                if not data_columns:
                    data_columns = default_columns
            else:
                data_columns = default_columns
            print(f"[ECHARTS] Candidate columns: {candidate_columns}")
            print(f"[ECHARTS] Default columns: {default_columns}")
            print(f"[ECHARTS] Included columns: {data_columns}")
        else:
            data_columns = []
            default_columns = []
        
        # Group data by ticker and create time axis
        series_data = {}
        time_points = []
        series_to_source_column = {}  # Track which column each series came from
        
        for row in data:
            ticker = row.get('ticker', '')
            calendar_year = row.get('calendar_year', None)
            calendar_quarter = row.get('calendar_quarter', '')
            calendar_quarter_num = row.get('calendar_quarter_num', None)
            
            # Create proper time point: "2023 Q2" when quarter exists, otherwise just year
            if calendar_year is not None:
                q_label = calendar_quarter or (f"Q{int(calendar_quarter_num)}" if calendar_quarter_num else "")
                time_point = f"{calendar_year} {q_label}".strip()
            else:
                # Fallback to date or index
                time_point = row.get('date') or ''
            if time_point not in time_points:
                time_points.append(time_point)
            
            # Handle each data column as a separate metric
            for col in data_columns:
                if col in row and row[col] is not None:
                    value = row[col]
                    
                    # Create series key with sensible defaults when ticker missing
                    col_title = col.replace('_', ' ').title()
                    if len(tickers) == 0:
                        series_key = col_title
                    elif len(data_columns) > 1 or len(tickers) > 1:
                        series_key = f"{ticker} - {col_title}".strip(' -')
                    else:
                        series_key = ticker or col_title
                    
                    # Track the source column for this series
                    series_to_source_column[series_key] = col
                    
                    if series_key not in series_data:
                        series_data[series_key] = {}
                    
                    series_data[series_key][time_point] = value
        
        # Sort time points chronologically
        def sort_time_key(time_str):
            try:
                parts = time_str.split(' ', 1)
                year = int(parts[0]) if parts and parts[0].isdigit() else 0
                if len(parts) == 2:
                    quarter_num = {'Q1': 1, 'Q2': 2, 'Q3': 3, 'Q4': 4}.get(parts[1], 0)
                else:
                    quarter_num = 0
                return (year, quarter_num)
            except Exception:
                return (0, 0)
        
        sorted_times = sorted(time_points, key=sort_time_key)
        print(f"[ECHARTS] Sorted time points: {sorted_times}")
        
        # Build series
        series = []
        colors = self._get_chart_colors('light')
        
        for i, (series_name, time_values) in enumerate(series_data.items()):
            series_values = [time_values.get(time_point, None) for time_point in sorted_times]
            print(f"[ECHARTS] Series '{series_name}': {series_values[:3]}...")
            
            series.append({
                'name': series_name,
                'type': series_type,
                'data': series_values,
                'itemStyle': {'color': colors[i % len(colors)]},
                'emphasis': {'focus': 'series'},
                'connectNulls': False
            })
        
        # Determine appropriate title using charts.yaml patterns
        target_ticker, target_name = self._extract_company(query)
        title_text = self._get_chart_title(query, target_name, years_back)

        # Compute per-series value types for frontend formatting
        def _is_percent_name(name: str) -> bool:
            n = name.lower()
            return any(k in n for k in ['share', 'ratio', 'margin', '_gm', '_om', '_nm', 'pct', 'percent', 'growth', 'qoq'])
        
        def _is_pre_multiplied_percent(name: str) -> bool:
            """Check if this is a percentage that's already multiplied by 100 (not 0-1 range)"""
            n = name.lower()
            # Treat any column that contains 'percent' as pre-multiplied by default
            # e.g., market_share_percent, gross_margin_percent
            return any(k in n for k in ['market_share_percent', 'share_percent', '_percent', 'percent'])
        
        series_value_types = {}
        series_percent_format = {}
        
        for s in series:
            name = s['name']
            # Check the original column name, not just the series name
            source_col = series_to_source_column.get(name, name)
            print(f"[ECHARTS TYPE DEBUG] Series '{name}' -> source_col '{source_col}', is_percent: {_is_percent_name(source_col)}")
            
            # Use source column for type detection
            if _is_percent_name(source_col):
                series_value_types[name] = 'percent'
                # Indicate if percentage is pre-multiplied (already 0-100 range)
                series_percent_format[name] = 'pre_multiplied' if _is_pre_multiplied_percent(source_col) else 'decimal'
            else:
                series_value_types[name] = 'currency'

        # Chart-level hint: if all included columns are percent-like, mark chart as percent for frontend fallback
        chart_value_type = 'percent' if (data_columns and all(_is_percent_name(c) for c in data_columns)) else 'currency'

        # Build legend.selected so only default columns are shown initially
        legend_selected = {}
        # For single-series charts (like market share), always show the series
        # For multi-series charts, determine which series to show based on default columns
        if len(series) == 1:
            # Single series - always show it
            legend_selected[series[0]['name']] = True
        else:
            # Multi-series - check if the series represents a default column
            def _normalize_title(col: str) -> str:
                return col.replace('_', ' ').title()
            default_titles = set(_normalize_title(c) for c in default_columns)
            for s in series:
                # if series like "AMD - Net Margin" extract after dash to get the metric name
                name = s['name']
                if ' - ' in name:
                    display = name.split(' - ', 1)[1]
                else:
                    display = name
                legend_selected[name] = (display in default_titles) if default_titles else True
        
        # For multi-company, multi-metric queries, show first metric for all companies by default
        if len(tickers) > 1 and len(data_columns) > 1:
            # Reset legend selection to show only series for the first metric
            first_metric = data_columns[0] if data_columns else None
            if first_metric:
                first_metric_title = first_metric.replace('_', ' ').title()
                metric_legend_selected = {}
                for series_name in series_data.keys():
                    # Check if this series represents the first metric (ends with the metric name)
                    metric_legend_selected[series_name] = series_name.endswith(' - ' + first_metric_title)
                legend_selected = metric_legend_selected
                print(f"[ECHARTS] Updated legend selection for metric grouping: showing '{first_metric_title}' for all companies")

        # Get layout configuration from charts.yaml
        layout = self._get_chart_layout('default')
        
        chart_spec = {
            'title': {
                **layout.get('title', {}),
                'text': title_text
            },
            'tooltip': layout.get('tooltip', {
                'trigger': 'axis',
                'axisPointer': {'type': 'cross'}
            }),
            'legend': {
                **layout.get('legend', {}),
                'data': list(series_data.keys()),
                'selected': legend_selected
            },
            'grid': layout.get('grid', {
                'left': '3%',
                'right': '4%',
                'bottom': '3%',
                'top': '20%',
                'containLabel': True
            }),
            'xAxis': {
                'type': 'category',
                'data': sorted_times,
                'axisLabel': {'rotate': 45}
            },
            'yAxis': {
                'type': 'value',
                'axisLabel': {
                    'formatter': '{value}'
                }
            },
            'series': series,
            'meta': {
                'seriesValueType': series_value_types,
                'seriesPercentFormat': series_percent_format,
                'rawData': data,
                'defaultColumns': default_columns,
                'includedColumns': data_columns,
                'chartValueType': chart_value_type,
                'groupingType': 'metric',
                'metricsList': data_columns  # Always use metric grouping
            }
        }
        
        return chart_spec
    
    def _build_bar_chart(self, data: List[Dict], tickers: List[str], metrics: List[str], years_back: int = 4) -> Dict[str, Any]:
        """Build bar chart for comparisons"""
        
        # Group data for bar chart
        categories = []
        series_data = {}
        
        if len(tickers) > 1 and len(metrics) == 1:
            # Compare companies on single metric
            categories = tickers
            metric_name = metrics[0]
            
            for ticker in tickers:
                ticker_data = [row for row in data if row.get('ticker') == ticker]
                if ticker_data:
                    # Use most recent value or average
                    avg_value = sum(row.get('value', 0) for row in ticker_data) / len(ticker_data)
                    series_data[ticker] = avg_value
            
            series = [{
                'name': metric_name,
                'type': 'bar',
                'data': [series_data.get(ticker, 0) for ticker in categories],
                'itemStyle': {'color': '#5470C6'}
            }]
            
        else:
            # Compare metrics or default grouping
            categories = metrics or tickers
            
            for category in categories:
                category_data = [row for row in data if 
                               row.get('metric') == category or row.get('ticker') == category]
                if category_data:
                    avg_value = sum(row.get('value', 0) for row in category_data) / len(category_data)
                    series_data[category] = avg_value
            
            series = [{
                'name': 'Value',
                'type': 'bar', 
                'data': [series_data.get(cat, 0) for cat in categories],
                'itemStyle': {'color': '#91CC75'}
            }]
        
        # Build lightweight meta to help frontend format units in bar charts
        meta_series_value_type = {}
        meta_series_percent_format = {}
        if len(tickers) > 1 and len(metrics) == 1:
            # Single metric compared across companies
            metric_name = (metrics[0] or '').lower()
            def _metric_is_percent(n: str) -> bool:
                return any(k in n for k in ['margin', 'share', 'ratio', 'rate', 'percent', 'intensity', 'growth'])
            def _metric_pre_multiplied(n: str) -> bool:
                return any(k in n for k in ['percent', '%'])
            if _metric_is_percent(metric_name):
                # Series name equals metric label
                series_name = metrics[0]
                meta_series_value_type[series_name] = 'percent'
                meta_series_percent_format[series_name] = 'pre_multiplied' if _metric_pre_multiplied(metric_name) else 'decimal'

        return {
            'title': {
                'text': f'Financial Comparison - {metrics[0] if len(metrics) == 1 else "Financial Data"}',
                'left': 'center'
            },
            'tooltip': {
                'trigger': 'axis',
                'axisPointer': {'type': 'shadow'}
            },
            'grid': {
                'left': '3%',
                'right': '4%',
                'bottom': '3%',
                'top': '15%',
                'containLabel': True
            },
            'xAxis': {
                'type': 'category',
                'data': categories,
                'axisLabel': {'rotate': 45}
            },
            'yAxis': {
                'type': 'value',
                # Leave neutral; frontend applies smart units based on meta
                'axisLabel': {'formatter': '{value}'}
            },
            'series': series,
            'meta': {
                'seriesValueType': meta_series_value_type,
                'seriesPercentFormat': meta_series_percent_format,
            }
        }
    
    def _prepare_data_summary(self, data: List[Dict]) -> str:
        """Prepare concise data summary for analysis"""
        if not data:
            return "No data available"
        
        print(f"[DATA SUMMARY] Processing {len(data)} rows")
        print(f"[DATA SUMMARY] Sample row structure: {data[0] if data else 'N/A'}")
        
        # Basic statistics
        total_rows = len(data)
        companies = list(set(row.get('ticker', '') for row in data if row.get('ticker')))
        
        # For derived metrics (like gross_margin_pct), get column names that aren't standard
        standard_cols = {'ticker', 'calendar_year', 'calendar_quarter_num', 'calendar_quarter', 'date', 'tag_used'}
        derived_metrics = []
        if data:
            all_cols = set(data[0].keys())
            derived_metrics = list(all_cols - standard_cols)
        
        # Get traditional metrics if available
        traditional_metrics = list(set(row.get('metric', '') for row in data if row.get('metric')))
        
        # Combine both types
        all_metrics = traditional_metrics + derived_metrics
        
        print(f"[DATA SUMMARY] Traditional metrics: {traditional_metrics}")
        print(f"[DATA SUMMARY] Derived metrics: {derived_metrics}")
        print(f"[DATA SUMMARY] All metrics: {all_metrics}")
        
        # Sample recent data points
        sample_size = min(5, len(data))
        sample_data = data[:sample_size]
        
        summary = f"""
Total Records: {total_rows}
Companies: {', '.join(companies)}
Metrics: {', '.join(all_metrics)}

Sample Data Points:
"""
        
        for row in sample_data:
            ticker = row.get('ticker', 'N/A')
            quarter = row.get('calendar_quarter', row.get('date', 'N/A'))
            
            # Handle both traditional and derived metric formats
            if row.get('metric') and row.get('value') is not None:
                # Traditional format: ticker, metric, value
                metric = row.get('metric', 'N/A')
                value = row.get('value', 0)
                summary += f"- {ticker}: {metric} = ${value:,.0f} ({quarter})\n"
            else:
                # Derived format: find the calculated columns
                for col in derived_metrics:
                    if col in row and row[col] is not None:
                        value = row[col]
                        if isinstance(value, (int, float)):
                            summary += f"- {ticker}: {col} = {value:.2f}% ({quarter})\n"
                        else:
                            summary += f"- {ticker}: {col} = {value} ({quarter})\n"
                        break
        
        print(f"[DATA SUMMARY] Generated summary: {summary}")
        return summary
    
    async def stream_analysis(self, query: str) -> AsyncGenerator[Dict[str, Any], None]:
        """Stream the complete analytics workflow with real-time updates and comprehensive debugging"""
        try:
            print(f"[WORKFLOW START] Processing query: {query}")
            
            # Initialize state
            initial_state = WorkflowState(
                query=query,
                sql=None,
                data=None,
                chart_spec=None,
                analysis=None,
                errors=[],
                thinking=None,
                step="starting",
                years_back=None,
                granularity=None
            )
            
            # Stream status update
            yield {
                "event": "status",
                "data": {
                    "step": "sql_generation",
                    "message": "🔍 Starting SQL generation...",
                    "thinking": "LLM analyzing schema and user query"
                }
            }
            
            # Execute SQL agent
            state = await self._sql_agent(initial_state)
            print(f"[WORKFLOW] SQL agent completed with step: {state.get('step')}")
            
            if state.get("errors"):
                print(f"[WORKFLOW ERROR] SQL agent errors: {state['errors']}")
                yield {"event": "errors", "data": {"errors": state["errors"]}}
                return
            
            # Log detailed data passing information
            print(f"[WORKFLOW] Data passing check:")
            print(f"[WORKFLOW]   - SQL length: {len(state.get('sql', '')) if state.get('sql') else 0} chars")
            print(f"[WORKFLOW]   - Data rows: {len(state.get('data', [])) if state.get('data') else 0}")
            if state.get('data'):
                print(f"[WORKFLOW]   - Data keys: {list(state['data'][0].keys()) if state['data'] else 'N/A'}")
                print(f"[WORKFLOW]   - State data type: {type(state.get('data'))}")
            
            # Stream SQL result
            yield {
                "event": "sql_generated",
                "data": {"sql": state["sql"]}
            }
            
            yield {
                "event": "data_retrieved", 
                "data": {
                    "row_count": len(state["data"]) if state["data"] else 0,
                    "sample_data": state["data"][:3] if state["data"] else []
                }
            }
            
            # Generate chart FIRST before starting analysis stream
            yield {
                "event": "status",
                "data": {
                    "step": "chart_generation",
                    "message": "📊 Generating interactive chart...",
                    "thinking": "Creating ECharts visualization"
                }
            }
            
            print(f"[WORKFLOW] Passing data to ECharts agent: {len(state.get('data', []))} rows")
            chart_state = await self._echarts_agent(state)
            print(f"[WORKFLOW] ECharts agent completed with step: {chart_state.get('step')}")
            
            if chart_state.get("errors"):
                print(f"[WORKFLOW ERROR] ECharts agent errors: {chart_state['errors']}")
                yield {"event": "errors", "data": {"errors": chart_state["errors"]}}
                return
            
            # Send chart immediately after generation
            if chart_state.get("chart_spec"):
                print(f"[WORKFLOW] Sending chart spec with keys: {list(chart_state['chart_spec'].keys())}")
                yield {"event": "chart_generated", "data": {"chart_spec": chart_state["chart_spec"]}}
                state.update(chart_state)  # Update state with chart info
            
            # NOW start analysis streaming
            if not state.get("data"):
                print("[WORKFLOW ERROR] No data available for analysis")
                yield {"event": "errors", "data": {"errors": ["No data available for analysis"]}}
                return

            total_rows = len(state['data'])
            max_rows_for_llm = int(os.getenv('ANALYTICS_MAX_ROWS_FOR_LLM', '200'))
            preview_rows = state['data'][:max_rows_for_llm]
            print(f"[WORKFLOW] Building analysis prompt from {total_rows} rows (previewing {len(preview_rows)})")
            try:
                data_json = json.dumps(preview_rows, default=str)
            except Exception:
                # Fallback if any non-serializable value sneaks in
                data_json = json.dumps([{k: str(v) for k, v in row.items()} for row in preview_rows])

            analysis_prompt = f"""
You are a financial analyst. Analyze the user's question using the SQL and a preview of the data below.

USER QUESTION:
{state['query']}

SQL USED:
{state.get('sql', '')}

ROW COUNT: {total_rows}
PREVIEW COUNT: {len(preview_rows)} (showing only the first rows)
DATA PREVIEW (JSON):
{data_json}

Guidelines:
- Focus on the user's intent; interpret what the measures represent based on the SQL (e.g., market_share, net_margin, QoQ growth).
- When multiple metrics are present, summarize the relationships.
- Use specific numbers, years/quarters, and compare to peers where applicable.
- Be concise and avoid restating the SQL.
"""

            # Announce analysis start
            yield {
                "event": "status",
                "data": {
                    "step": "analysis_generation",
                    "message": "🧠 Generating financial insights...",
                    "thinking": "Streaming real-time analysis"
                }
            }

            # Stream analysis using unified client Responses API
            full_analysis = ""
            messages = [{"role": "system", "content": analysis_prompt}]
            async for delta in self.unified_client.stream_response(
                messages=messages,
                reasoning_effort="low",
                model="gpt-5-mini-2025-08-07"
            ):
                if delta.content:
                    full_analysis += delta.content
                    yield {"event": "analysis_streaming", "data": {"partial_analysis": delta.content}}
            
            # Send final analysis
            yield {"event": "analysis_complete", "data": {"analysis": full_analysis}}
            
            # Workflow complete
            yield {
                "event": "workflow_complete",
                "data": {"message": "Analytics workflow completed successfully"}
            }
            
        except Exception as e:
            error_msg = f"Workflow Error: {str(e)}"
            print(f"[WORKFLOW ERROR] {error_msg}")
            import traceback
            print(f"[WORKFLOW ERROR] Traceback: {traceback.format_exc()}")
            yield {
                "event": "errors",
                "data": {"errors": [error_msg]}
            }

async def create_analytics_workflow() -> AnalyticsWorkflow:
    """Factory function to create analytics workflow with environment variables"""
    database_url = os.getenv("DATABASE_URL")
    openai_api_key = os.getenv("OPENAI_API_KEY")
    
    if not database_url:
        raise ValueError("DATABASE_URL environment variable is required")
    if not openai_api_key:
        raise ValueError("OPENAI_API_KEY environment variable is required")

    # Ensure sslmode=require for providers like Supabase
    try:
        from urllib.parse import urlparse, parse_qsl, urlencode, urlunparse
        parsed = urlparse(database_url)
        query = dict(parse_qsl(parsed.query))
        if 'sslmode' not in query:
            query['sslmode'] = 'require'
            new_query = urlencode(query)
            database_url = urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, new_query, parsed.fragment))
    except Exception:
        # Fallback silently; connection may still work
        pass

    return AnalyticsWorkflow(database_url, openai_api_key)

