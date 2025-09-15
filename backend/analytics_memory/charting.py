from __future__ import annotations
from typing import Dict, Any, List, Optional

from .types import ChartPlanModel
from .config import CONFIGS

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

def _generate_descriptive_title(intent_key: Optional[str], primary_metrics: List[str]) -> str:
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


def _detect_primary_series(intent_key: Optional[str], available_slugs: List[str]) -> List[str]:
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


def _assign_series_axes(series_list: List[Dict[str, Any]]) -> Dict[str, str]:
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


def plan_chart_rule_based(data: List[Dict[str, Any]], query: str, intent_key: str = None) -> ChartPlanModel:
    # Simple heuristics: if time columns exist -> line chart
    chart_type = 'line'
    if not data:
        title = _generate_descriptive_title(intent_key, [])
        return ChartPlanModel(chart_type=chart_type, title=title, series=[])
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
    primary_metrics = _detect_primary_series(intent_key, [s.get('source_column', '') for s in series])
    title = _generate_descriptive_title(intent_key, primary_metrics)
    
    return ChartPlanModel(chart_type=chart_type, x_axis={'field': x_field, 'type': 'category'}, title=title, series=series)


def build_chart_spec(data: List[Dict[str, Any]], chart_plan: Dict[str, Any], charts_cfg: Dict[str, Any], 
                     intent_key: Optional[str] = None, comparison: Optional[str] = None) -> Dict[str, Any]:
    """Enhanced chart spec builder with dual axes and primary series detection."""
    
    # Time axis
    x_field = chart_plan.get('x_axis', {}).get('field') or 'calendar_year'
    x_vals: List[str] = []
    seen = set()
    for row in data:
        xv = row.get(x_field)
        if xv is None:
            # Try composite for quarterly
            if x_field == 'calendar_quarter' and row.get('calendar_year') and row.get('calendar_quarter'):
                xv = f"{row.get('calendar_year')} {row.get('calendar_quarter')}"
        if xv is None:
            continue
        s = str(xv)
        if s not in seen:
            seen.add(s)
            x_vals.append(s)

    # Colors - enhanced with primary/secondary distinction and company colors
    colors = (charts_cfg.get('themes', {}).get('light', {}).get('chart_colors', {}).get('primary_palette') or
              ['#5470C6', '#91CC75', '#FAC858', '#EE6666', '#73C0DE'])
    
    # Get company-specific colors from config
    company_colors = CONFIGS.companies.get('display', {}).get('company_colors', {})
    
    primary_color = colors[0]
    secondary_colors = colors[1:] + ['#D4D4D4', '#B0B0B0', '#909090']

    # Special-case: All-companies market share — 100% stacked area with Top-N focus
    if (intent_key == 'market_share_all') or (comparison == 'all'):
        # Prepare per-year mapping of ticker -> share percent
        years = sorted({int(r.get('calendar_year')) for r in data if r.get('calendar_year') is not None})
        # Compute last year for ranking
        last_year = years[-1] if years else None
        tickers = sorted({r.get('ticker') for r in data if r.get('ticker')})

        # Build dictionary: year -> {ticker -> percent}
        by_year: Dict[int, Dict[str, float]] = {y: {} for y in years}
        for r in data:
            try:
                y = int(r.get('calendar_year'))
            except Exception:
                continue
            t = r.get('ticker')
            p = r.get('market_share_percent')
            if t and isinstance(p, (int, float)):
                by_year[y][t] = float(p)

        # Rank tickers by last_year share
        def last_share(t: str) -> float:
            return (by_year.get(last_year, {}) or {}).get(t, 0.0)
        tickers_sorted = sorted(tickers, key=last_share, reverse=True)

        top_n = 3
        top_tickers = tickers_sorted[:top_n]
        rest_tickers = tickers_sorted[top_n:]

        # Build X axis labels
        x_vals_stack = [str(y) for y in years]

        # Helper to collect series values
        def series_values_for(ticker: str) -> List[Optional[float]]:
            return [by_year.get(y, {}).get(ticker) for y in years]

        # Build series for top tickers
        stacked_series: List[Dict[str, Any]] = []
        for ticker in top_tickers:
            color = company_colors.get(ticker)
            stacked_series.append({
                'name': ticker,
                'type': 'line',
                'data': series_values_for(ticker),
                'yAxisIndex': 0,  # single percent axis defined below
                'stack': 'share',
                'areaStyle': {'opacity': 0.2},
                'lineStyle': {'width': 2, 'color': color} if color else {'width': 2},
                'itemStyle': {'color': color} if color else {},
            })

        # Compute Others = 100 - sum(top tickers) per year (when data exists)
        others_vals: List[Optional[float]] = []
        for y in years:
            if not by_year.get(y):
                others_vals.append(None)
                continue
            s = 0.0
            for t in top_tickers:
                s += by_year[y].get(t, 0.0) or 0.0
            others_vals.append(max(0.0, 100.0 - s))
        if rest_tickers:
            stacked_series.append({
                'name': 'Others',
                'type': 'line',
                'data': others_vals,
                'yAxisIndex': 0,
                'stack': 'share',
                'areaStyle': {'opacity': 0.15},
                'lineStyle': {'width': 1, 'type': 'dashed', 'color': '#999'},
                'itemStyle': {'color': '#BBBBBB'},
            })

        # Legend ordering and default selection (Top-N + Others)
        legend_order = top_tickers + (['Others'] if rest_tickers else [])
        default_selected = {name: True for name in legend_order}
        for t in rest_tickers:
            default_selected[t] = False

        spec_stack = {
            'title': {'left': 'center', 'top': '5%', 'text': chart_plan.get('title') or 'Financial Analytics'},
            'tooltip': {'trigger': 'axis', 'axisPointer': {'type': 'cross'}},
            'legend': {'top': '10%', 'left': 'center', 'data': legend_order + rest_tickers, 'selected': default_selected},
            'grid': {'left': '3%', 'right': '8%', 'bottom': '3%', 'top': '20%', 'containLabel': True},
            'xAxis': {'type': 'category', 'data': x_vals_stack, 'axisLabel': {'rotate': 45}},
            'yAxis': [{
                'type': 'value',
                'name': 'Percentage',
                'axisLabel': {'formatter': '{value}%'}
            }],
            'series': stacked_series,
            'meta': {
                'grouping': 'ticker',
                'measure': 'market_share_percent',
                'topN': top_n,
                'legendOrder': legend_order + rest_tickers,
                'defaultLegendSelection': default_selected,
                'seriesAxis': {name: 'right' for name in (legend_order + rest_tickers)},
                'seriesValueType': {name: 'percent' for name in (legend_order + rest_tickers)},
                'primarySeries': legend_order,  # focus on Top-N + Others
                'rawData': data,
                'includedColumns': legend_order + rest_tickers,
                'displayNames': {name: name for name in (legend_order + rest_tickers)},
                'defaultColumns': legend_order,
                'chartDesign': {
                    'intent': 'market_share_all',
                    'grouping': 'ticker',
                    'chart_type': 'stacked_area_100',
                    'y_axis': {'type': 'percent_only'}
                }
            }
        }
        return spec_stack

    # Build series with enhanced metadata (generic path)
    series_defs = chart_plan.get('series', [])
    series = []
    
    # Extract data columns (slugs) and create display name mapping
    slugs = [s['data_column'] for s in series_defs]
    display_names = {s['data_column']: s.get('name', s['data_column']) for s in series_defs}
    
    # Detect primary series using data columns (slugs)
    primary_slugs = _detect_primary_series(intent_key, slugs)
    
    # Add fallback when no primary series detected
    if not primary_slugs and slugs:
        # Fallback: first percent/margin series, or first series
        percent_slugs = [s for s in slugs if any(keyword in s for keyword in ['percent', 'margin', 'growth', 'share'])]
        primary_slugs = [percent_slugs[0]] if percent_slugs else [slugs[0]]
    
    # Convert primary slugs to display names for legend
    primary_series = [display_names[slug] for slug in primary_slugs]
    
    # Assign axes based on data type
    series_axes = _assign_series_axes(series_defs)
    
    # Default legend selection - primary series visible, others hidden
    default_legend_selection = {}
    
    for i, s in enumerate(series_defs):
        name = s.get('name') or s.get('data_column')
        col = s.get('data_column')
        
        # Determine if this is a primary series
        is_primary = name in primary_series
        default_legend_selection[name] = is_primary
        
        # Build data values
        vals: List[Any] = []
        for xv in x_vals:
            found = None
            for row in data:
                # Check ticker filter if present
                if 'ticker_filter' in s and row.get('ticker') != s.get('ticker_filter'):
                    continue
                    
                r_x = row.get(x_field)
                if x_field == 'calendar_quarter' and row.get('calendar_year') and row.get('calendar_quarter'):
                    r_x = f"{row.get('calendar_year')} {row.get('calendar_quarter')}"
                if str(r_x) == xv:
                    found = row
                    break
            vals.append(found.get(col) if found and col in found else None)
        
        # Determine axis index (0=left, 1=right)
        y_axis_index = 1 if series_axes.get(name) == 'right' else 0
        
        # Style based on primary/secondary and company colors
        if is_primary:
            # Check if this is a ticker series with company-specific color
            ticker_color = company_colors.get(name) if 'ticker_filter' in s else None
            line_style = {
                'color': ticker_color or primary_color,
                'width': 3,
                'opacity': 1
            }
        else:
            # For ticker series, use company colors even if not primary
            ticker_color = company_colors.get(name) if 'ticker_filter' in s else None
            line_style = {
                'color': ticker_color or secondary_colors[i % len(secondary_colors)],
                'width': 2 if ticker_color else 1,  # Thicker line for company colors
                'opacity': 0.8 if ticker_color else 0.6,
                'type': 'solid' if ticker_color else 'dashed'
            }
        
        series.append({
            'name': name,
            'type': 'line' if chart_plan.get('chart_type') != 'bar' else 'bar',
            'data': vals,
            'yAxisIndex': y_axis_index,
            'lineStyle': line_style,
            'itemStyle': {'color': line_style['color']},
            'emphasis': {
                'lineStyle': {'width': line_style['width'] + 1}
            }
        })

    # Create Y-axis configuration based on data types
    has_left_axis = any(series_axes.get(s['name']) == 'left' for s in series)
    has_right_axis = any(series_axes.get(s['name']) == 'right' for s in series)
    
    y_axes = []
    
    # Only create left axis if we have currency/numeric data
    if has_left_axis:
        y_axes.append({
            'type': 'value',
            'name': 'Currency',
            'position': 'left',
            'axisLabel': {
                'formatter': '{value}'
            }
        })
    
    # Always create right axis for percentages, but adjust position if no left axis
    y_axes.append({
        'type': 'value', 
        'name': 'Percentage',
        'position': 'right' if has_left_axis else 'left',
        'axisLabel': {
            'formatter': '{value}%'
        }
    })
    
    # Update yAxisIndex for series based on actual axis configuration
    for s in series:
        axis_side = series_axes.get(s['name'], 'left')
        if not has_left_axis and axis_side == 'right':
            s['yAxisIndex'] = 0  # Use the only axis (percent axis in left position)
        elif has_left_axis and axis_side == 'right':
            s['yAxisIndex'] = 1  # Use right axis
        else:
            s['yAxisIndex'] = 0  # Use left axis

    # Generate annotations for primary series
    annotations = []
    for series_name in primary_series:
        # Find the series data to get last value
        for s in series:
            if s['name'] == series_name:
                data_vals = [v for v in s['data'] if v is not None]
                if data_vals:
                    last_val = data_vals[-1]
                    annotations.append({
                        'series': series_name,
                        'type': 'last',
                        'label': f'Current: {last_val:.1f}{"%" if series_axes.get(series_name) == "right" else ""}'
                    })
                break

    title_text = chart_plan.get('title') or 'Financial Analytics'
    spec = {
        'title': {'left': 'center', 'top': '5%', 'text': title_text},
        'tooltip': {
            'trigger': 'axis',
            'axisPointer': {'type': 'cross'}
        },
        'legend': {
            'top': '10%',
            'left': 'center', 
            'data': [s['name'] for s in series],
            'selected': default_legend_selection
        },
        'grid': {'left': '3%', 'right': '8%', 'bottom': '3%', 'top': '20%', 'containLabel': True},
        'xAxis': {'type': 'category', 'data': x_vals, 'axisLabel': {'rotate': 45}},
        'yAxis': y_axes,
        'series': series,
        'meta': {
            # Enhanced metadata for frontend
            'primarySeries': primary_series,
            'seriesAxis': series_axes,
            'defaultLegendSelection': default_legend_selection,
            'annotations': annotations,
            'highlightRules': {
                'emphasizePrimary': True,
                'mutedSecondary': True
            },
            'seriesValueType': {s['name']: ('percent' if series_axes.get(s['name']) == 'right' else 'currency') for s in series},
            # Missing metadata for frontend compatibility
            'includedColumns': slugs if intent_key != 'revenue_growth_vs_avg' else ['YoY Growth', 'Company', 'Industry Average'],
            'displayNames': display_names if intent_key != 'revenue_growth_vs_avg' else {
                'YoY Growth': 'YoY Growth', 
                'Company': 'Company', 
                'Industry Average': 'Industry Average'
            },
            'defaultColumns': primary_slugs if intent_key != 'revenue_growth_vs_avg' else ['YoY Growth'],
            'rawData': data,
            'seriesPercentFormat': {
                slug: 'pre_multiplied' for slug in slugs if 'percent' in slug or 'share' in slug or 'margin' in slug
            }
        }
    }
    return spec
