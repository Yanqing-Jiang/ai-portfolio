"""
SQL Planning Shared Functions

Contains shared SQL planning and template selection functions used by both
analytics_memory and analytics_supervisor systems.
"""

from typing import Dict, Any, List, Optional


# Note: This will need to import IntentModel and QueryPlanModel from the original modules
# For now, using Dict[str, Any] as a placeholder


def plan_sql_rule_based(intent: Dict[str, Any], configs: Dict[str, Any]) -> Dict[str, Any]:
    """
    Generate a SQL query plan based on intent detection results.

    Args:
        intent: Intent detection results with intent_key and slots_detected
        configs: Configuration dictionary

    Returns:
        Query plan dictionary with metrics, comparison, timeframe, etc.
    """
    # Extract intent key and slots
    intent_key = intent.get('intent_key') if isinstance(intent, dict) else getattr(intent, 'intent_key', None)
    slots = intent.get('slots_detected') if isinstance(intent, dict) else getattr(intent, 'slots_detected', {})

    metrics: List[str] = []
    derived: List[str] = []
    comparison: Optional[str] = None

    # Intent-specific planning logic
    if intent_key == 'market_share_all':
        metrics = ['Revenue']
        comparison = 'all'
    elif intent_key == 'market_share_single':
        metrics = ['Revenue']
        comparison = 'single'
    elif intent_key == 'margins_vs_peers':
        metrics = ['Revenue', 'Gross Profit', 'Operating Income', 'Net Income']
        derived = ['gross_margin', 'operating_margin', 'net_margin']
        comparison = 'vs_avg'
    elif intent_key == 'margin_growth_vs_peers':
        metrics = ['Revenue', 'Gross Profit', 'Operating Income', 'Net Income']
        derived = ['gross_margin', 'operating_margin', 'net_margin']
        comparison = 'vs_avg'
    elif intent_key == 'revenue_growth_analysis':
        metrics = ['Revenue']
        comparison = 'single'
    elif intent_key == 'revenue_growth_vs_avg':
        metrics = ['Revenue']
        comparison = 'vs_avg'
    elif intent_key == 'rnd_intensity_vs_peers':
        metrics = ['Revenue', 'R&D Expense']
        derived = ['rnd_intensity']
        comparison = 'vs_avg'
    elif intent_key == 'rnd_expense_vs_peers':
        metrics = ['R&D Expense']
        comparison = 'vs_avg'
    else:
        metrics = ['Revenue']

    # Extract timeframe and granularity from slots
    tf = slots.get('timeframe', {})
    years_back = tf.get('years_back', 4) if isinstance(tf, dict) else 4
    raw_granularity = slots.get('granularity', 'annual')

    # Ensure granularity is always a valid enum value
    granularity = 'annual'  # default
    if raw_granularity in ['annual', 'quarterly']:
        granularity = raw_granularity
    elif raw_granularity and ('quarter' in raw_granularity.lower() or 'q1' in raw_granularity.lower()):
        granularity = 'quarterly'

    # Build query plan
    plan = {
        'metrics': metrics,
        'derived_metrics': derived,
        'timeframe': {'years_back': years_back},
        'granularity': granularity,
        'comparison': comparison,
        'group_by': ['calendar_year'] if granularity == 'annual' else ['calendar_year', 'calendar_quarter_num', 'calendar_quarter'],
        'filters': {},
        'limit': (configs.get('database', {}).get('query_defaults', {}).get('default_limit', 500)),
    }

    return plan


def choose_template(intent: Dict[str, Any], plan: Dict[str, Any], configs: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Choose appropriate SQL template based on intent and plan.

    Args:
        intent: Intent detection results
        plan: Query plan
        configs: Configuration dictionary

    Returns:
        Template dictionary if found, None otherwise
    """
    patterns = (configs.get('queries', {}) or {}).get('query_patterns', {})
    intent_key = intent.get('intent_key') if isinstance(intent, dict) else getattr(intent, 'intent_key', None)

    if intent_key and intent_key in patterns:
        return patterns[intent_key]
    return None


def get_granularity_clauses(granularity: str) -> tuple[str, str, str, str]:
    """
    Get SQL clauses for different granularity levels.

    Args:
        granularity: 'annual' or 'quarterly'

    Returns:
        Tuple of (select_clause, group_by_clause, join_clause, order_by_clause)
    """
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