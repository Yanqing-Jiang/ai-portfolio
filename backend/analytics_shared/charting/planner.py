"""
Chart Planning Shared Functions

Contains shared chart planning logic used by both analytics_memory and analytics_supervisor systems.
"""

from typing import Dict, Any, List, Optional


# Intent-based chart titles
INTENT_TITLES = {
    'market_share_single': 'Market Share Analysis',
    'market_share_all': 'Market Share Comparison',
    'margins_vs_peers': 'Margin Comparison vs Industry',
    'margin_growth_vs_peers': 'Margin Growth vs Industry',
    'revenue_growth_analysis': 'Revenue Growth Analysis',
    'revenue_growth_vs_avg': 'Revenue Growth vs Industry Average',
    'rnd_intensity_vs_peers': 'R&D Intensity vs Industry',
    'rnd_expense_vs_peers': 'R&D Expense vs Industry'
}


def generate_descriptive_title(intent_key: Optional[str], primary_metrics: List[str]) -> str:
    """Generate a descriptive chart title based on intent and metrics."""
    if not intent_key:
        return 'Financial Analytics'

    base_title = INTENT_TITLES.get(intent_key, 'Financial Analytics')

    # Enhance title with primary metrics if available
    if primary_metrics:
        # Get the first primary metric and make it readable
        metric = primary_metrics[0].replace('_', ' ').title()
        if 'Growth' in base_title and 'Growth' in metric:
            return base_title  # Avoid redundancy
        elif 'Margin' in base_title and 'Margin' in metric:
            return base_title  # Avoid redundancy
        else:
            return f'{base_title} - {metric}'

    return base_title


def detect_primary_series(intent_key: Optional[str], available_slugs: List[str]) -> List[str]:
    """Detect primary series based on intent type using data column slugs."""
    if not intent_key:
        return []

    primary_patterns = {
        'market_share_single': ['market_share_percent', 'share_percent'],
        'market_share_all': ['market_share_percent', 'share_percent'],
        'margins_vs_peers': ['gross_margin', 'operating_margin', 'net_margin'],
        'margin_growth_vs_peers': ['company_gross_margin_change_pp', 'company_operating_margin_change_pp', 'company_net_margin_change_pp', 'peer_avg_gross_margin_change_pp', 'peer_avg_operating_margin_change_pp', 'peer_avg_net_margin_change_pp'],
        'revenue_growth_analysis': ['qoq_growth_percent', 'yoy_growth_percent'],
        'revenue_growth_vs_avg': ['company_yoy_growth_percent', 'yoy_growth_percent', 'industry_avg_yoy_growth_percent'],
        'rnd_intensity_vs_peers': ['company_rnd_intensity', 'rnd_intensity_percent'],
        'rnd_expense_vs_peers': ['company_rnd_expense']
    }

    patterns = primary_patterns.get(intent_key, [])
    primary = []

    # Compare against data column slugs directly (already snake_case)
    for pattern in patterns:
        for slug in available_slugs:
            if pattern in slug:
                primary.append(slug)
                break

    return primary


def assign_series_axes(series_list: List[Dict[str, Any]]) -> Dict[str, str]:
    """Assign series to left (currency) or right (percent) axis."""
    axis_assignment = {}

    for series in series_list:
        name = series.get('name', '')
        value_type = series.get('value_type', 'number')

        # Assign to right axis if it's a percentage/ratio type
        if (value_type == 'percent' or
            any(keyword in name.lower() for keyword in ['percent', 'share', 'margin', 'ratio', 'growth', '%'])):
            axis_assignment[name] = 'right'
        else:
            axis_assignment[name] = 'left'

    return axis_assignment


def plan_chart_rule_based(data: List[Dict[str, Any]], query: str, intent_key: str = None) -> Dict[str, Any]:
    """
    Plan chart configuration based on data structure and intent.

    Args:
        data: Query result data
        query: Original user query
        intent_key: Detected intent key

    Returns:
        Chart plan dictionary with chart_type, x_axis, title, and series
    """
    # Simple heuristics: if time columns exist -> line chart
    chart_type = 'line'
    if not data:
        title = generate_descriptive_title(intent_key, [])
        return {
            'chart_type': chart_type,
            'title': title,
            'series': [],
            'x_axis': {'field': 'calendar_year', 'type': 'category'}
        }

    cols = list(data[0].keys())
    has_time = any(c in cols for c in ['calendar_year', 'calendar_quarter'])
    if not has_time:
        chart_type = 'bar'

    x_field = 'calendar_year'
    if 'calendar_quarter' in cols:
        x_field = 'calendar_quarter'

    # Detect multi-ticker data structure
    has_multiple_tickers = False
    unique_tickers = set()
    if 'ticker' in cols and len(data) > 1:
        unique_tickers = set(row.get('ticker') for row in data if row.get('ticker'))
        has_multiple_tickers = len(unique_tickers) > 1

    series = []

    if has_multiple_tickers and intent_key != 'revenue_growth_vs_avg':
        # Multi-ticker data: create one series per ticker
        # Skip this for revenue growth comparisons which need column-based series
        # Find the primary metric to display
        primary_metric = None
        if 'market_share_percent' in cols:
            primary_metric = 'market_share_percent'
        elif 'value' in cols:
            primary_metric = 'value'
        else:
            # Find first numeric column
            for c in cols:
                if c not in {'ticker', 'metric', 'date', 'tag_used', 'calendar_year', 'calendar_quarter', 'calendar_quarter_num'}:
                    v = data[0].get(c)
                    if isinstance(v, (int, float)):
                        primary_metric = c
                        break

        if primary_metric:
            for ticker in sorted(unique_tickers):
                vtype = 'percent' if any(k in primary_metric.lower() for k in ['margin', 'share', 'ratio', 'growth', 'percent', 'pct']) else 'number'
                series.append({
                    'name': ticker,
                    'data_column': primary_metric,
                    'value_type': vtype,
                    'ticker_filter': ticker
                })
    else:
        # Single-ticker or non-ticker data: use column-based series
        # Candidate numeric columns excluding standard keys
        std = {'ticker', 'metric', 'value', 'date', 'tag_used', 'calendar_year', 'calendar_quarter', 'calendar_quarter_num'}
        numeric_cols: List[str] = []
        for c in cols:
            if c in std:
                continue
            v = data[0].get(c)
            if isinstance(v, (int, float)):
                numeric_cols.append(c)
        if not numeric_cols:
            # fallback to 'value' if present
            if 'value' in cols:
                numeric_cols = ['value']

        for c in numeric_cols[:4]:  # cap to avoid clutter
            vtype = 'percent' if any(k in c.lower() for k in ['margin', 'share', 'ratio', 'growth', 'percent', 'pct']) else 'number'

            # Special naming for revenue growth comparisons
            if intent_key == 'revenue_growth_vs_avg':
                if 'industry_avg' in c:
                    name = 'Industry Average - YoY Growth'
                elif 'yoy_growth_percent' in c:
                    # Get company ticker if available in data
                    company_ticker = None
                    for row in data:
                        if row.get('ticker'):
                            company_ticker = row['ticker']
                            break
                    name = f'{company_ticker} - YoY Growth' if company_ticker else 'Company - YoY Growth'
                else:
                    name = c.replace('_', ' ').title()
            elif intent_key == 'margin_growth_vs_peers':
                # Special naming for margin growth comparisons
                if 'peer_avg' in c:
                    if 'gross_margin' in c:
                        name = 'Industry Average - Gross Margin Change'
                    elif 'operating_margin' in c:
                        name = 'Industry Average - Operating Margin Change'
                    elif 'net_margin' in c:
                        name = 'Industry Average - Net Margin Change'
                    else:
                        name = 'Industry Average - ' + c.replace('_', ' ').replace('peer avg ', '').title()
                elif 'company_' in c:
                    # Get company ticker if available in data
                    company_ticker = None
                    for row in data:
                        if row.get('ticker'):
                            company_ticker = row['ticker']
                            break

                    if 'gross_margin' in c:
                        name = f'{company_ticker} - Gross Margin Change' if company_ticker else 'Company - Gross Margin Change'
                    elif 'operating_margin' in c:
                        name = f'{company_ticker} - Operating Margin Change' if company_ticker else 'Company - Operating Margin Change'
                    elif 'net_margin' in c:
                        name = f'{company_ticker} - Net Margin Change' if company_ticker else 'Company - Net Margin Change'
                    else:
                        name = f'{company_ticker} - ' + c.replace('company_', '').replace('_', ' ').title() if company_ticker else 'Company - ' + c.replace('company_', '').replace('_', ' ').title()
                else:
                    name = c.replace('_', ' ').title()
            else:
                name = c.replace('_', ' ').title()

            series.append({'name': name, 'data_column': c, 'value_type': vtype})

    # Generate descriptive title based on intent and detected metrics
    primary_metrics = detect_primary_series(intent_key, [s.get('source_column', '') for s in series])
    title = generate_descriptive_title(intent_key, primary_metrics)

    return {
        'chart_type': chart_type,
        'x_axis': {'field': x_field, 'type': 'category'},
        'title': title,
        'series': series
    }