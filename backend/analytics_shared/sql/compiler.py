"""
SQL Compilation Shared Functions

Contains shared SQL compilation and template processing functions used by both
analytics_memory and analytics_supervisor systems.
"""

from typing import Dict, Any, Optional
from ..companies.tickers import get_ticker_list, validate_and_resolve_company, format_company_error
from .planner import get_granularity_clauses


def compile_sql_from_plan(plan: Dict[str, Any], intent: Dict[str, Any], configs: Dict[str, Any], template: Optional[Dict[str, Any]]) -> str:
    """
    Compile SQL query from plan, intent, and template.

    Args:
        plan: Query plan dictionary
        intent: Intent detection results
        configs: Configuration dictionary
        template: SQL template dictionary (optional)

    Returns:
        Compiled SQL query string

    Raises:
        ValueError: If required company is missing or invalid
    """
    # Get ticker list and build ticker list string
    tickers = get_ticker_list(configs)
    ticker_list = "'" + "','".join(tickers) + "'"

    # Extract company from intent slots
    slots = intent.get('slots_detected') if isinstance(intent, dict) else getattr(intent, 'slots_detected', {})
    raw_company = slots.get('company')
    target_ticker = None

    # If we have a company input, try to resolve it
    if raw_company:
        target_ticker = validate_and_resolve_company(raw_company, configs)

    # Extract plan parameters
    years_back = plan.get('timeframe', {}).get('years_back') or configs.get('database', {}).get('query_defaults', {}).get('default_years_back', 5)
    granularity = plan.get('granularity', 'annual')
    select_clause, group_by_clause, join_clause, order_by_clause = get_granularity_clauses(granularity)

    # Use template if available
    if template and 'sql_template' in template:
        sql_template = template['sql_template']

        # Check if template requires a target_ticker
        requires_company = '{target_ticker}' in sql_template

        if requires_company and not target_ticker:
            # Template needs a company but we don't have a valid one
            raise ValueError(format_company_error(raw_company, configs))

        sql = sql_template
        # Basic template replacements
        if target_ticker:
            sql = sql.replace('{target_ticker}', str(target_ticker))
        sql = sql.replace('{years_back}', str(years_back))
        sql = sql.replace('{select_clause}', select_clause)
        sql = sql.replace('{group_by_clause}', group_by_clause)
        sql = sql.replace('{join_clause}', join_clause)
        sql = sql.replace('{order_by_clause}', order_by_clause)
        sql = sql.replace("('AMD','AVGO','INTC','MU','NVDA','QCOM','TXN')", f"({ticker_list})")
        # Remove trailing semicolons to be consistent with executor
        return sql.strip().rstrip(';')

    # Fallback: Generic SQL builder for Revenue queries (quarterly/annual)
    # This is used when no specific template is found for the intent
    if granularity == 'quarterly':
        # Quarterly data: Include quarter information and filter for complete quarters only
        return (
            "SELECT ticker, calendar_year, calendar_quarter_num, calendar_quarter, "
            "SUM(value) AS value FROM comp_financials "
            "WHERE metric='Revenue' AND calendar_quarter_num IS NOT NULL "
            f"AND calendar_year >= EXTRACT(YEAR FROM CURRENT_DATE) - {years_back} "
            f"AND ticker IN ({ticker_list}) "
            "GROUP BY ticker, calendar_year, calendar_quarter_num, calendar_quarter "
            f"ORDER BY ticker, {order_by_clause}"
        )
    else:
        # Annual data: Simple aggregation by year
        return (
            "SELECT ticker, calendar_year, SUM(value) AS value FROM comp_financials "
            "WHERE metric='Revenue' "
            f"AND calendar_year >= EXTRACT(YEAR FROM CURRENT_DATE) - {years_back} "
            f"AND ticker IN ({ticker_list}) "
            "GROUP BY ticker, calendar_year "
            f"ORDER BY ticker, {order_by_clause}"
        )


def validate_template_requirements(template: Dict[str, Any], intent: Dict[str, Any], configs: Dict[str, Any]) -> tuple[bool, Optional[str]]:
    """
    Validate that template requirements are met by the intent.

    Args:
        template: SQL template dictionary
        intent: Intent detection results
        configs: Configuration dictionary

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not template or 'sql_template' not in template:
        return True, None

    sql_template = template['sql_template']
    requires_company = '{target_ticker}' in sql_template

    if requires_company:
        slots = intent.get('slots_detected') if isinstance(intent, dict) else getattr(intent, 'slots_detected', {})
        raw_company = slots.get('company')
        target_ticker = validate_and_resolve_company(raw_company, configs) if raw_company else None

        if not target_ticker:
            return False, format_company_error(raw_company, configs)

    return True, None


def extract_template_parameters(template: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract parameter placeholders from SQL template.

    Args:
        template: SQL template dictionary

    Returns:
        Dictionary of found parameters and their requirements
    """
    if not template or 'sql_template' not in template:
        return {}

    sql_template = template['sql_template']
    parameters = {}

    # Common template parameters
    if '{target_ticker}' in sql_template:
        parameters['target_ticker'] = {'required': True, 'type': 'company'}
    if '{years_back}' in sql_template:
        parameters['years_back'] = {'required': False, 'type': 'integer', 'default': 5}
    if '{select_clause}' in sql_template:
        parameters['select_clause'] = {'required': False, 'type': 'sql_clause'}
    if '{group_by_clause}' in sql_template:
        parameters['group_by_clause'] = {'required': False, 'type': 'sql_clause'}

    return parameters