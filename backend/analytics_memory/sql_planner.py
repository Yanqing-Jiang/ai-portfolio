from __future__ import annotations
from typing import Dict, Any, List, Optional, Tuple
from .types import IntentModel, QueryPlanModel

# Phase 2: build QueryPlan/SQLPlan and deterministic compiler


def plan_sql_rule_based(intent: IntentModel, configs: Dict[str, Any]) -> QueryPlanModel:
    metrics: List[str] = []
    derived: List[str] = []
    comparison: Optional[str] = None
    if intent.intent_key == 'market_share_all':
        metrics = ['Revenue']
        comparison = 'all'
    elif intent.intent_key == 'market_share_single':
        metrics = ['Revenue']
        comparison = 'single'
    elif intent.intent_key == 'margins_vs_peers':
        metrics = ['Revenue', 'Gross Profit', 'Operating Income', 'Net Income']
        derived = ['gross_margin', 'operating_margin', 'net_margin']
        comparison = 'vs_avg'
    elif intent.intent_key == 'margin_growth_vs_peers':
        metrics = ['Revenue', 'Gross Profit', 'Operating Income', 'Net Income']
        derived = ['gross_margin', 'operating_margin', 'net_margin']
        comparison = 'vs_avg'
    elif intent.intent_key == 'revenue_growth_analysis':
        metrics = ['Revenue']
        comparison = 'single'
    elif intent.intent_key == 'revenue_growth_vs_avg':
        metrics = ['Revenue']
        comparison = 'vs_avg'
    elif intent.intent_key == 'rnd_intensity_vs_peers':
        metrics = ['Revenue', 'R&D Expense']
        derived = ['rnd_intensity']
        comparison = 'vs_avg'
    elif intent.intent_key == 'rnd_expense_vs_peers':
        metrics = ['R&D Expense']
        comparison = 'vs_avg'
    else:
        metrics = ['Revenue']

    years_back = (intent.slots_detected.get('timeframe') or {}).get('years_back', 4)
    raw_granularity = intent.slots_detected.get('granularity')
    # Ensure granularity is always a valid enum value
    granularity = 'annual'  # default
    if raw_granularity in ['annual', 'quarterly']:
        granularity = raw_granularity
    elif raw_granularity and ('quarter' in raw_granularity.lower() or 'q1' in raw_granularity.lower()):
        granularity = 'quarterly'
    plan = QueryPlanModel(
        metrics=metrics,
        derived_metrics=derived,
        timeframe={'years_back': years_back},
        granularity=granularity,
        comparison=comparison,
        group_by=['calendar_year'] if granularity == 'annual' else ['calendar_year', 'calendar_quarter_num', 'calendar_quarter'],
        filters={},
        limit=(configs.get('database', {}).get('query_defaults', {}).get('default_limit', 500)),
    )
    return plan


def choose_template(intent: IntentModel, plan: QueryPlanModel, configs: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    patterns = (configs.get('queries', {}) or {}).get('query_patterns', {})
    key = intent.intent_key
    if key and key in patterns:
        return patterns[key]
    return None


def _granularity_clauses(granularity: str) -> Tuple[str, str, str, str]:
    if granularity == 'quarterly':
        select_clause = "calendar_year, calendar_quarter_num, calendar_quarter"
        group_by_clause = select_clause
        join_clause = (
            "cr.calendar_year = mr.calendar_year AND "
            "cr.calendar_quarter_num = mr.calendar_quarter_num AND "
            "cr.calendar_quarter = mr.calendar_quarter"
        )
        order_by_clause = "calendar_year, calendar_quarter_num"
    else:
        select_clause = "calendar_year"
        group_by_clause = select_clause
        join_clause = "cr.calendar_year = mr.calendar_year"
        order_by_clause = "calendar_year"
    return select_clause, group_by_clause, join_clause, order_by_clause


def resolve_alias_to_ticker(company_input: str, configs: Dict[str, Any]) -> Optional[str]:
    """
    Resolve a company alias (name, short name, or alias) to its official ticker.
    
    Args:
        company_input: User input like "Micron", "nvidia", "Advanced Micro Devices"
        configs: Configuration dictionary containing companies data
        
    Returns:
        Official ticker symbol if found, None if not found
    """
    if not company_input or not isinstance(company_input, str):
        return None
    
    # Clean input - strip whitespace and normalize case
    clean_input = company_input.strip().lower()
    
    # Get companies data from config
    companies_data = configs.get('companies', {}).get('companies', {})
    
    # Search through all sectors
    for sector_name, companies_list in companies_data.items():
        if not isinstance(companies_list, list):
            continue
            
        for company in companies_list:
            if not isinstance(company, dict):
                continue
                
            ticker = company.get('ticker', '')
            
            # Check exact ticker match (case insensitive)
            if ticker.lower() == clean_input:
                return ticker
            
            # Check company name match (case insensitive)
            company_name = company.get('name', '').lower()
            if company_name == clean_input:
                return ticker
                
            # Check short name match (case insensitive)
            short_name = company.get('short_name', '').lower()
            if short_name == clean_input:
                return ticker
                
            # Check aliases match (case insensitive)
            aliases = company.get('aliases', [])
            if isinstance(aliases, list):
                for alias in aliases:
                    if isinstance(alias, str) and alias.lower() == clean_input:
                        return ticker
    
    return None


def _ticker_list(configs: Dict[str, Any]) -> List[str]:
    tickers = (
        configs.get('companies', {})
        .get('selection_rules', {})
        .get('default_companies', {})
        .get('tickers', ["NVDA", "AMD", "INTC", "MU", "QCOM", "AVGO", "TXN"])
    )
    return tickers


def _sanitize_ticker(raw_ticker: str, allowed_tickers: List[str]) -> Optional[str]:
    """
    Sanitize ticker symbol to prevent SQL injection.
    
    Args:
        raw_ticker: The raw ticker input from user
        allowed_tickers: List of allowed ticker symbols
        
    Returns:
        Sanitized ticker symbol if valid, None if invalid
    """
    if not raw_ticker or not isinstance(raw_ticker, str):
        return None
    
    # Convert to uppercase and strip whitespace
    clean_ticker = raw_ticker.strip().upper()
    
    # Only allow alphanumeric characters (typical ticker format)
    if not clean_ticker.isalnum():
        return None
    
    # Check if ticker is in allowed list
    if clean_ticker in allowed_tickers:
        return clean_ticker
    
    # Return None if not found in allowed list
    return None


def compile_sql_from_plan(plan: QueryPlanModel, intent: IntentModel, configs: Dict[str, Any], template: Optional[Dict[str, Any]]) -> str:
    # If we have a template, fill it deterministically
    tickers = _ticker_list(configs)
    ticker_list = "'" + "','".join(tickers) + "'"
    
    # Get raw company input without defaulting to anything
    raw_company = intent.slots_detected.get('company')
    target_ticker = None
    
    # If we have a company input, try to resolve it
    if raw_company:
        # First try alias resolution (handles names like "Micron", "nvidia")
        target_ticker = resolve_alias_to_ticker(raw_company, configs)
        
        # If alias resolution didn't work, try direct ticker validation
        if not target_ticker:
            target_ticker = _sanitize_ticker(raw_company, tickers)
    
    years_back = plan.timeframe.years_back or configs.get('database', {}).get('query_defaults', {}).get('default_years_back', 5)
    select_clause, group_by_clause, join_clause, order_by_clause = _granularity_clauses(plan.granularity)

    if template and 'sql_template' in template:
        sql_template = template['sql_template']
        
        # Check if template requires a target_ticker
        requires_company = '{target_ticker}' in sql_template
        
        if requires_company and not target_ticker:
            # Template needs a company but we don't have a valid one
            if not raw_company:
                raise ValueError("This query requires specifying a company. Please mention a company ticker (e.g., 'NVDA', 'AMD') or company name (e.g., 'Nvidia', 'Micron') in your query.")
            else:
                available_companies = [f"{ticker} ({configs.get('companies', {}).get('companies', {}).get('semiconductor', [{}])[i].get('short_name', ticker)}" 
                                     for i, ticker in enumerate(tickers)]
                raise ValueError(f"Company '{raw_company}' not recognized. Available companies: {', '.join(available_companies[:5])}...")
        
        sql = sql_template
        # basic replacements
        if target_ticker:
            sql = sql.replace('{target_ticker}', str(target_ticker))
        sql = sql.replace('{years_back}', str(years_back))
        sql = sql.replace('{select_clause}', select_clause)
        sql = sql.replace('{group_by_clause}', group_by_clause)
        sql = sql.replace('{join_clause}', join_clause)
        sql = sql.replace('{order_by_clause}', order_by_clause)
        sql = sql.replace("('AMD','AVGO','INTC','MU','NVDA','QCOM','TXN')", f"({ticker_list})")
        # remove trailing semicolons to be consistent with executor
        return sql.strip().rstrip(';')

    # Fallback: Generic SQL builder for Revenue queries (quarterly/annual)
    # This is used when no specific template is found for the intent
    if plan.granularity == 'quarterly':
        # Quarterly data: Include quarter information and filter for complete quarters only
        return (
            "SELECT ticker, calendar_year, calendar_quarter_num, calendar_quarter, "
            "SUM(value) AS value FROM comp_financials "
            "WHERE metric='Revenue' AND calendar_quarter_num IS NOT NULL "
            f"AND calendar_year >= EXTRACT(YEAR FROM CURRENT_DATE) - {years_back} "
            f"AND ticker IN ({ticker_list}) "
            "GROUP BY ticker, calendar_year, calendar_quarter_num, calendar_quarter "
            "ORDER BY ticker, calendar_year, calendar_quarter_num LIMIT 500"
        )
    else:
        # Annual data: Sum quarterly data to get annual totals
        # Note: We use calendar_quarter_num IS NOT NULL to ensure we only sum from
        # quarterly records, which provides more accurate annual aggregation than
        # mixing quarterly and annual records in the database
        return (
            "SELECT ticker, calendar_year, SUM(value) AS value FROM comp_financials "
            "WHERE metric='Revenue' AND calendar_quarter_num IS NOT NULL "
            f"AND calendar_year >= EXTRACT(YEAR FROM CURRENT_DATE) - {years_back} "
            f"AND ticker IN ({ticker_list}) "
            "GROUP BY ticker, calendar_year "
            "ORDER BY ticker, calendar_year LIMIT 500"
        )
