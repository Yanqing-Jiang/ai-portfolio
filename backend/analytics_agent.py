import asyncio
import json
import os
import re
import traceback
from typing import Dict, Any, List, Optional, AsyncGenerator, TypedDict
from datetime import datetime

import asyncpg
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from langgraph.graph import StateGraph, END

# Database schema for comp_financials table
COMP_FINANCIALS_SCHEMA = {
    "table": "comp_financials",
    "columns": [
        "ticker", "metric", "value", "tag_used", "date",
        "calendar_year", "calendar_quarter_num", "calendar_quarter"
    ],
    "structure": "long_format",
    "available_metrics": [
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
    ],
    "tickers": ["AMD", "AVGO", "INTC", "MU", "NVDA", "QCOM", "TXN"]
}

class WorkflowState(TypedDict):
    query: str
    sql: Optional[str]
    data: Optional[List[Dict[str, Any]]]
    chart_spec: Optional[Dict[str, Any]]
    analysis: Optional[str]
    errors: List[str]
    thinking: Optional[str]
    step: str

class AnalyticsWorkflow:
    def __init__(self, database_url: str, openai_api_key: str):
        self.database_url = database_url
        # Use gpt-5-mini-2025-08-07 for SQL generation
        self.llm = ChatOpenAI(
            model="gpt-4o-mini-2024-07-18",
            api_key=openai_api_key,
            temperature=0,
            max_tokens=None,
            timeout=None,
            max_retries=2,
        )
        self.streaming_llm = ChatOpenAI(
            model="gpt-4o-mini-2024-07-18",
            api_key=openai_api_key,
            temperature=0,
            max_tokens=None,
            timeout=None,
            max_retries=2,
            streaming=True
        )
        
        # Build LangGraph workflow
        self.workflow = self._build_workflow()
        
        # Synonym mapping for common financial terms
        self.metric_synonyms = {
            "OpEx": "Operating Expenses",
            "CapEx": "CapEx", 
            "CFO": "CFO",
            "Cash": "Cash & Equiv.",
            "R&D": "R&D Expense",
            "SG&A": "SG&A",
            "Gross Profit": "Gross Profit",
            "Revenue": "Revenue",
            "Net Income": "Net Income"
        }

    def _detect_intent(self, query: str) -> Dict[str, Any]:
        """Detect user intent (kind, ticker, names) from the query in a single place."""
        q_lower = (query or '').lower()
        ticker, name = self._extract_company(query)
        kind: Optional[str] = None
        if 'market share' in q_lower and 'all' in q_lower:
            kind = 'market_share_all'
        elif 'market share' in q_lower:
            kind = 'market_share'
        elif ('margin' in q_lower and ('peer' in q_lower or 'compare' in q_lower)):
            kind = 'margins_vs_peers'
        elif (('growth' in q_lower or 'growing' in q_lower or 'fast' in q_lower) and ('peer' in q_lower or 'peers' in q_lower or 'vs' in q_lower)):
            kind = 'growth_vs_peers'
        elif ('r&d' in q_lower or 'r and d' in q_lower or 'rnd' in q_lower or 'r&d expense' in q_lower or 'r&d expenses' in q_lower or ('intensity' in q_lower and ('r' in q_lower or 'rnd' in q_lower or 'r&d' in q_lower))):
            kind = 'rnd_intensity_vs_peers'
        return {
            'kind': kind,
            'ticker': ticker,
            'name': name,
        }

    def _build_market_share_sql(self, all_companies: bool, target_ticker: str) -> str:
        """Return SQL for market share over the last 5 years.
        If all_companies is True, returns per-ticker market share vs total market.
        Else returns target ticker vs market.
        """
        if all_companies:
            return (
                "WITH market AS (\n"
                "  SELECT calendar_year, SUM(value) AS market_revenue\n"
                "  FROM comp_financials\n"
                "  WHERE metric = 'Revenue'\n"
                "    AND ticker IN ('AMD','AVGO','INTC','MU','NVDA','QCOM','TXN')\n"
                "    AND calendar_quarter_num IS NOT NULL\n"
                "    AND calendar_year >= EXTRACT(YEAR FROM CURRENT_DATE) - 4\n"
                "  GROUP BY calendar_year\n"
                "), per AS (\n"
                "  SELECT ticker, calendar_year, SUM(value) AS ticker_revenue\n"
                "  FROM comp_financials\n"
                "  WHERE metric = 'Revenue'\n"
                "    AND ticker IN ('AMD','AVGO','INTC','MU','NVDA','QCOM','TXN')\n"
                "    AND calendar_quarter_num IS NOT NULL\n"
                "    AND calendar_year >= EXTRACT(YEAR FROM CURRENT_DATE) - 4\n"
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
            "    AND ticker IN ('AMD','AVGO','INTC','MU','NVDA','QCOM','TXN')\n"
            "    AND calendar_quarter_num IS NOT NULL\n"
            "    AND calendar_year >= EXTRACT(YEAR FROM CURRENT_DATE) - 4\n"
            "  GROUP BY calendar_year\n"
            "), t AS (\n"
            "  SELECT calendar_year, SUM(value) AS t_revenue\n"
            "  FROM comp_financials\n"
            f"  WHERE metric = 'Revenue' AND ticker = '{target_ticker}'\n"
            "    AND calendar_quarter_num IS NOT NULL\n"
            "    AND calendar_year >= EXTRACT(YEAR FROM CURRENT_DATE) - 4\n"
            "  GROUP BY calendar_year\n"
            ")\n"
            f"SELECT t.calendar_year, t.t_revenue AS {ticker_lower}_revenue, m.market_revenue,\n"
            f"       t.t_revenue / NULLIF(m.market_revenue, 0) AS {ticker_lower}_market_share\n"
            "FROM t JOIN market m USING (calendar_year)\n"
            "ORDER BY t.calendar_year"
        )

    def _build_margins_sql(self, target_ticker: str) -> str:
        ticker_lower = target_ticker.lower()
        return (
            "WITH q AS (\n"
            "  SELECT * FROM comp_financials\n"
            "  WHERE calendar_quarter_num IS NOT NULL\n"
            "    AND ticker IN ('AMD','AVGO','INTC','MU','NVDA','QCOM','TXN')\n"
            "    AND metric IN ('Revenue','Gross Profit','Operating Income','Net Income')\n"
            "), yr AS (\n"
            "  SELECT ticker, calendar_year,\n"
            "         SUM(CASE WHEN metric='Revenue' THEN value END) AS rev,\n"
            "         SUM(CASE WHEN metric='Gross Profit' THEN value END) AS gp,\n"
            "         SUM(CASE WHEN metric='Operating Income' THEN value END) AS op,\n"
            "         SUM(CASE WHEN metric='Net Income' THEN value END) AS ni\n"
            "  FROM q GROUP BY 1,2\n"
            "), peer AS (\n"
            "  SELECT calendar_year,\n"
            "         AVG(gp/rev) AS peer_gross_margin,\n"
            "         AVG(op/rev) AS peer_operating_margin,\n"
            "         AVG(ni/rev) AS peer_net_margin\n"
            "  FROM yr WHERE ticker <> 'NVDA' GROUP BY 1\n"
            ")\n"
            "SELECT y.calendar_year,\n"
            f"       y.gp/y.rev AS {ticker_lower}_gross_margin,\n"
            f"       y.op/y.rev AS {ticker_lower}_operating_margin,\n"
            f"       y.ni/y.rev AS {ticker_lower}_net_margin,\n"
            "       p.peer_gross_margin, p.peer_operating_margin, p.peer_net_margin\n"
            "FROM yr y JOIN peer p USING (calendar_year)\n"
            f"WHERE y.ticker='{target_ticker}' AND y.calendar_year >= EXTRACT(YEAR FROM CURRENT_DATE) - 4\n"
            "ORDER BY y.calendar_year"
        )

    def _build_growth_sql(self, target_ticker: str) -> str:
        ticker_lower = target_ticker.lower()
        return (
            "WITH revenue_q AS (\n"
            "    SELECT ticker, calendar_year, calendar_quarter_num, SUM(value) AS revenue\n"
            "    FROM comp_financials\n"
            "    WHERE metric = 'Revenue'\n"
            "      AND ticker IN ('AMD','AVGO','INTC','MU','NVDA','QCOM','TXN')\n"
            "      AND calendar_quarter_num IS NOT NULL\n"
            "    GROUP BY ticker, calendar_year, calendar_quarter_num\n"
            "), growth AS (\n"
            "    SELECT\n"
            "        ticker, calendar_year, calendar_quarter_num,\n"
            "        (revenue - LAG(revenue) OVER (PARTITION BY ticker ORDER BY calendar_year, calendar_quarter_num))\n"
            "        / NULLIF(LAG(revenue) OVER (PARTITION BY ticker ORDER BY calendar_year, calendar_quarter_num), 0) AS qoq_growth\n"
            "    FROM revenue_q\n"
            ")\n"
            "SELECT\n"
            "    g.calendar_year, g.calendar_quarter_num,\n"
            f"    g.qoq_growth AS {ticker_lower}_qoq_growth,\n"
            "    p.peer_qoq_growth\n"
            "FROM growth g\n"
            "JOIN (\n"
            "    SELECT calendar_year, calendar_quarter_num, AVG(qoq_growth) AS peer_qoq_growth\n"
            "    FROM growth WHERE ticker <> 'NVDA'\n"
            "    GROUP BY calendar_year, calendar_quarter_num\n"
            ") p\n"
            "ON g.calendar_year = p.calendar_year AND g.calendar_quarter_num = p.calendar_quarter_num\n"
            f"WHERE g.ticker = '{target_ticker}' AND g.calendar_year >= EXTRACT(YEAR FROM CURRENT_DATE) - 4\n"
            "ORDER BY g.calendar_year, g.calendar_quarter_num"
        )

    def _build_rnd_sql(self, target_ticker: str) -> str:
        ticker_lower = target_ticker.lower()
        return (
            "WITH q AS (\n"
            "  SELECT * FROM comp_financials\n"
            "  WHERE calendar_quarter_num IS NOT NULL\n"
            "    AND ticker IN ('AMD','AVGO','INTC','MU','NVDA','QCOM','TXN')\n"
            "    AND metric IN ('Revenue','R&D Expense')\n"
            "), yr AS (\n"
            "  SELECT ticker, calendar_year,\n"
            "         SUM(CASE WHEN metric='Revenue' THEN value END) AS rev,\n"
            "         SUM(CASE WHEN metric='R&D Expense' THEN value END) AS rnd\n"
            "  FROM q GROUP BY 1,2\n"
            "), peer AS (\n"
            "  SELECT calendar_year, AVG(rnd/rev) AS peer_rnd_ratio\n"
            "  FROM yr WHERE ticker <> 'NVDA' GROUP BY 1\n"
            ")\n"
            "SELECT y.calendar_year,\n"
            f"       y.rnd/NULLIF(y.rev,0) AS {ticker_lower}_rnd_ratio,\n"
            "       p.peer_rnd_ratio\n"
            "FROM yr y JOIN peer p USING (calendar_year)\n"
            f"WHERE y.ticker='{target_ticker}' AND y.calendar_year >= EXTRACT(YEAR FROM CURRENT_DATE) - 4\n"
            "ORDER BY y.calendar_year"
        )

    def _extract_company(self, query: str) -> (str, str):
        """Extract target company ticker and display name from the query text."""
        q = (query or '').lower()
        mapping = {
            'nvidia': ('NVDA', 'Nvidia'), 'nvda': ('NVDA', 'Nvidia'),
            'amd': ('AMD', 'AMD'), 'advanced micro devices': ('AMD', 'AMD'),
            'intel': ('INTC', 'Intel'), 'intc': ('INTC', 'Intel'),
            'micron': ('MU', 'Micron'), 'mu': ('MU', 'Micron'),
            'qualcomm': ('QCOM', 'Qualcomm'), 'qcom': ('QCOM', 'Qualcomm'),
            'broadcom': ('AVGO', 'Broadcom'), 'avgo': ('AVGO', 'Broadcom'),
            'texas instruments': ('TXN', 'Texas Instruments'), 'txn': ('TXN', 'Texas Instruments'),
        }
        for key, val in mapping.items():
            if key in q:
                return val
        # default to Nvidia if unspecified
        return ('NVDA', 'Nvidia')

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
            for key in ['market_share']:
                if key in cols_lower:
                    return [cols_lower[key]]
            # fallback to any *_market_share
            for name in candidate_columns:
                if name.lower().endswith('_market_share') or name.lower() == 'market_share':
                    return [name]
        if 'market share' in q:
            # First: exact ticker-specific market share column
            preferred = f"{ticker_lower}_market_share"
            if preferred in cols_lower:
                return [cols_lower[preferred]]
            # Next: any *_market_share column
            for name in candidate_columns:
                if name.lower().endswith('_market_share'):
                    return [name]
            # Then generic tokens
            for key in ['market_share', 'share']:
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
    
    def _build_workflow(self) -> StateGraph:
        workflow = StateGraph(WorkflowState)
        
        # Add nodes
        workflow.add_node("sql_agent", self._sql_agent)
        workflow.add_node("echarts_agent", self._echarts_agent)
        workflow.add_node("analysis_agent", self._analysis_agent)
        
        # Add edges
        workflow.set_entry_point("sql_agent")
        workflow.add_edge("sql_agent", "echarts_agent")
        workflow.add_edge("echarts_agent", "analysis_agent")
        workflow.add_edge("analysis_agent", END)
        
        return workflow.compile()
    
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
            return COMP_FINANCIALS_SCHEMA['available_metrics']
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
            target_ticker, target_name = intent['ticker'], intent['name']
            ticker_lower = target_ticker.lower()

            # 1) Market share over past 5 years (all or single ticker)
            if intent['kind'] == 'market_share_all' or intent['kind'] == 'market_share':
                handcrafted_sql = self._build_market_share_sql(all_companies=(intent['kind'] == 'market_share_all'), target_ticker=target_ticker)
            # 2) Margin growth compared to peers over past 5 years
            elif intent['kind'] == 'margins_vs_peers':
                handcrafted_sql = self._build_margins_sql(target_ticker)
            # 3) Revenue growth vs peers (QoQ)
            elif intent['kind'] == 'growth_vs_peers':
                handcrafted_sql = self._build_growth_sql(target_ticker)
            # 4) R&D expense/intensity vs peers
            elif intent['kind'] == 'rnd_intensity_vs_peers':
                handcrafted_sql = self._build_rnd_sql(target_ticker)

            if handcrafted_sql:
                print("[SQL AGENT] Using handcrafted SQL for known query pattern")
                sql_query = handcrafted_sql
                data = await self._execute_query(sql_query)
                result = {
                    **state,
                    "sql": sql_query,
                    "data": data,
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
- Companies: {', '.join(COMP_FINANCIALS_SCHEMA['tickers'])}

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
"""

            print("[SQL AGENT] Calling LLM for SQL generation...")
            
            # Use synchronous invoke for faster SQL generation
            response = self.llm.invoke([SystemMessage(content=schema_prompt)])
            
            sql_query = response.content.strip()
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
            
            # Generate ECharts specification (pass user query to guide column selection)
            chart_spec = self._build_echarts_spec(
                data,
                chart_type,
                unique_tickers,
                unique_metrics,
                has_time_data,
                state.get('query', '')
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
    
    def _build_echarts_spec(self, data: List[Dict], chart_type: str, tickers: List[str], metrics: List[str], has_time: bool, query: str) -> Dict[str, Any]:
        """Build deterministic ECharts specification"""
        
        if has_time:
            series_type = 'bar' if chart_type == 'bar' else 'line'
            return self._build_time_series_chart(data, tickers, metrics, query, series_type)
        else:
            return self._build_bar_chart(data, tickers, metrics)
    
    def _build_time_series_chart(self, data: List[Dict], tickers: List[str], metrics: List[str], query: str, series_type: str = 'line') -> Dict[str, Any]:
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
        colors = ['#5470C6', '#91CC75', '#FAC858', '#EE6666', '#73C0DE', '#3BA272', '#FC8452']
        
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
        
        # Determine appropriate title (override with query context when applicable)
        q = (query or '').lower()
        target_ticker, target_name = self._extract_company(query)
        if 'market share' in q:
            title_text = f"{target_name} Market Share – Last 5 Years"
        elif ('margin' in q and ('peer' in q or 'compare' in q)):
            title_text = f"{target_name} Margins vs Peers – Last 5 Years"
        elif ('r&d' in q or 'r and d' in q or 'rnd' in q or 'r&d expense' in q or 'r&d expenses' in q):
            title_text = f"{target_name} R&D Expense vs Peers – Last 5 Years"
        elif len(data_columns) == 1:
            title_text = f"{data_columns[0].replace('_', ' ').title()} – Time Series"
        else:
            title_text = "Financial Metrics – Time Series"

        # Compute per-series value types for frontend formatting
        def _is_percent_name(name: str) -> bool:
            n = name.lower()
            return any(k in n for k in ['share', 'ratio', 'margin', '_gm', '_om', '_nm', 'pct', 'percent', 'growth', 'qoq'])
        series_value_types = {s['name']: ('percent' if _is_percent_name(s['name']) else 'currency') for s in series}

        # Build legend.selected so only default columns are shown initially
        legend_selected = {}
        # Map series_name back to column heuristic: series name is either ticker - Title or just Title
        def _normalize_title(col: str) -> str:
            return col.replace('_', ' ').title()
        default_titles = set(_normalize_title(c) for c in default_columns)
        for s in series:
            # if series like "AMD - Net Margin" extract after dash
            name = s['name']
            if ' - ' in name:
                display = name.split(' - ', 1)[1]
            else:
                display = name
            legend_selected[name] = (display in default_titles) if default_titles else True
        
        return {
            'title': {
                'text': title_text,
                'left': 'center'
            },
            'tooltip': {
                'trigger': 'axis',
                'axisPointer': {'type': 'cross'},
                # Avoid non-serializable functions in JSON output. Keep default formatting on frontend.
            },
            'legend': {
                'data': list(series_data.keys()),
                'top': '10%',
                'selected': legend_selected
            },
            'grid': {
                'left': '3%',
                'right': '4%',
                'bottom': '3%',
                'top': '20%',
                'containLabel': True
            },
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
            'series': series
            ,
            'meta': {
                'seriesValueType': series_value_types,
                'rawData': data,
                'defaultColumns': default_columns,
                'includedColumns': data_columns
            }
        }
    
    def _build_bar_chart(self, data: List[Dict], tickers: List[str], metrics: List[str]) -> Dict[str, Any]:
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
                'axisLabel': {'formatter': '${value}'}
            },
            'series': series
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
                step="starting"
            )
            
            print("[WORKFLOW] Sending initial status...")
            # Stream status update
            yield {
                "event": "status",
                "data": {
                    "step": "sql_generation",
                    "message": "🔍 Starting SQL generation...",
                    "thinking": "LLM analyzing schema and user query"
                }
            }
            
            print("[WORKFLOW] Calling SQL agent...")
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
            
            print("[WORKFLOW] Sending SQL result...")
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
            
            print("[WORKFLOW] Starting ECharts agent (concurrent with analysis)...")
            print(f"[WORKFLOW] Passing data to ECharts agent: {len(state.get('data', []))} rows")

            # Prepare analysis prompt and start streaming task immediately
            if not state.get("data"):
                print("[WORKFLOW ERROR] No data available for analysis")
                yield {"event": "errors", "data": {"errors": ["No data available for analysis"]}}
                return

            print(f"[WORKFLOW] Building analysis prompt directly from SQL and data rows: {len(state['data'])} rows")
            try:
                data_json = json.dumps(state["data"], default=str)
            except Exception:
                # Fallback if any non-serializable value sneaks in
                data_json = json.dumps([{k: str(v) for k, v in row.items()} for row in state["data"]])

            analysis_prompt = f"""
You are a financial analyst. Analyze the user's question using the SQL and raw data rows below. 

USER QUESTION:
{state['query']}

SQL USED:
{state.get('sql', '')}

DATA ROWS (JSON):
{data_json}

Guidelines:
- Focus on the user's intent; interpret what the measures represent based on the SQL (e.g., market_share, net_margin, QoQ growth).
- when there are multiple metrics, provide a summary of the metrics and their relationships.
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

            # Queue to collect streaming chunks
            analysis_queue: asyncio.Queue = asyncio.Queue()
            analysis_done = False

            async def _run_analysis_stream():
                full_text = ""
                async for chunk in self.streaming_llm.astream([SystemMessage(content=analysis_prompt)]):
                    if hasattr(chunk, 'content') and chunk.content:
                        full_text += chunk.content
                        await analysis_queue.put({"type": "chunk", "text": chunk.content})
                await analysis_queue.put({"type": "final", "text": full_text})

            analysis_task = asyncio.create_task(_run_analysis_stream())

            # Start chart generation concurrently
            echarts_task = asyncio.create_task(self._echarts_agent(state))

            # Interleave: drain analysis chunks while chart builds
            while not echarts_task.done():
                try:
                    item = await asyncio.wait_for(analysis_queue.get(), timeout=0.05)
                    if item["type"] == "chunk":
                        yield {"event": "analysis_streaming", "data": {"partial_analysis": item["text"]}}
                    elif item["type"] == "final":
                        # Hold final until after chart is sent
                        analysis_done = True
                        final_text = item["text"]
                        # Store in variable to send later
                        state["_final_analysis_text"] = final_text
                        break
                except asyncio.TimeoutError:
                    pass

            # Finish chart and emit
            state = await echarts_task
            print(f"[WORKFLOW] ECharts agent completed with step: {state.get('step')}")
            if state.get("errors"):
                print(f"[WORKFLOW ERROR] ECharts agent errors: {state['errors']}")
                yield {"event": "errors", "data": {"errors": state["errors"]}}
                return
            yield {"event": "chart_generated", "data": {"chart_spec": state["chart_spec"]}}

            # Continue draining analysis stream until complete
            while True:
                try:
                    item = await asyncio.wait_for(analysis_queue.get(), timeout=0.2)
                    if item["type"] == "chunk":
                        yield {"event": "analysis_streaming", "data": {"partial_analysis": item["text"]}}
                    elif item["type"] == "final":
                        yield {"event": "analysis_complete", "data": {"analysis": item["text"]}}
                        break
                except asyncio.TimeoutError:
                    if analysis_task.done():
                        # If task finished but no final captured (edge), break
                        if analysis_done and state.get("_final_analysis_text"):
                            yield {"event": "analysis_complete", "data": {"analysis": state["_final_analysis_text"]}}
                        break
            
            print("[WORKFLOW] Workflow complete!")
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
    # Support interpolated DB_PASSWORD in DATABASE_URL
    db_password = os.getenv("DB_PASSWORD")
    if database_url and "${DB_PASSWORD}" in database_url and db_password is not None:
        database_url = database_url.replace("${DB_PASSWORD}", db_password)
    openai_api_key = os.getenv("OPENAI_API_KEY")
    
    if not database_url:
        raise ValueError("DATABASE_URL environment variable is required")
    if not openai_api_key:
        raise ValueError("OPENAI_API_KEY environment variable is required")
    
    return AnalyticsWorkflow(database_url, openai_api_key)