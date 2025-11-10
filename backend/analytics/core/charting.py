# --- Analytics Function/Class Map ---
# Function: _compose_series_column
#   Role: Handles compose series column logic for analytics.core.charting.
#   Called from: Internal to analytics.core.charting
#   Invokes: Internal helpers only
#   Why: Keeps analytics.core.charting from duplicating compose series column behavior across flows.
# Function: _derive_metric_label
#   Role: Handles derive metric label logic for analytics.core.charting.
#   Called from: Internal to analytics.core.charting
#   Invokes: Internal helpers only
#   Why: Keeps analytics.core.charting from duplicating derive metric label behavior across flows.
# Function: _sort_axis_values
#   Role: Return axis labels sorted ascending using date/quarter heuristics.
#   Called from: Internal to analytics.core.charting
#   Invokes: Internal helpers only
#   Why: Supports downstream analytics workflows that rely on _sort_axis_values.
# Function: _coerce_float
#   Role: Handles coerce float logic for analytics.core.charting.
#   Called from: Internal to analytics.core.charting
#   Invokes: Internal helpers only
#   Why: Keeps analytics.core.charting from duplicating coerce float behavior across flows.
# Function: _build_candlestick_spec
#   Role: Handles build candlestick spec logic for analytics.core.charting.
#   Called from: Internal to analytics.core.charting
#   Invokes: analytics.core.charting._sort_axis_values, analytics.core.charting._coerce_float
#   Why: Keeps analytics.core.charting from duplicating build candlestick spec behavior across flows.
# Function: _attach_comparison_meta
#   Role: Attach comparison metadata to the chart spec and design.
#   Called from: Internal to analytics.core.charting
#   Invokes: Internal helpers only
#   Why: Supports downstream analytics workflows that rely on _attach_comparison_meta.
# Function: _format_scope_banner
#   Role: Handles format scope banner logic for analytics.core.charting.
#   Called from: Internal to analytics.core.charting
#   Invokes: Internal helpers only
#   Why: Keeps analytics.core.charting from duplicating format scope banner behavior across flows.
# Function: _build_ranking_bar_spec
#   Role: Handles build ranking bar spec logic for analytics.core.charting.
#   Called from: Internal to analytics.core.charting
#   Invokes: analytics.core.charting._format_scope_banner
#   Why: Keeps analytics.core.charting from duplicating build ranking bar spec behavior across flows.
# Function: plan_chart_rule_based
#   Role: Wrapper around the shared chart planning logic that returns ChartPlanModel.
#   Called from: analytics.flows.planner_executor, analytics.tools.registry, tests.analytics.test_chart_candlestick, tests.analytics.test_chart_comparison, +2 more
#   Invokes: analytics.core.charting_impl.plan_chart_rule_based, analytics.core.types.ChartPlanModel
#   Why: Supports downstream analytics workflows that rely on plan_chart_rule_based.
# Function: build_chart_spec
#   Role: Enhanced chart spec builder with dual axes and primary series detection.
#   Called from: analytics.flows.planner_executor, analytics.tools.registry, tests.analytics.test_chart_candlestick, tests.analytics.test_chart_comparison, +2 more
#   Invokes: analytics.core.charting._sort_axis_values, analytics.core.charting_impl.detect_primary_series, analytics.core.charting_impl.assign_series_axes, analytics.core.charting._attach_comparison_meta, +2 more
#   Why: Supports downstream analytics workflows that rely on build_chart_spec.
# --- End Analytics Function/Class Map ---
from __future__ import annotations

import re
from typing import Dict, Any, List, Optional, Tuple

from .types import ChartPlanModel
from .config import CONFIGS
from .charting_impl import (
    generate_descriptive_title,
    detect_primary_series,
    assign_series_axes,
    plan_chart_rule_based as _plan_chart_rule_based_dict,
    INTENT_TITLES as SHARED_INTENT_TITLES,
)

# Use shared intent titles
INTENT_TITLES = SHARED_INTENT_TITLES


_NUMERIC_REGEX = re.compile(r'^-?\d+(?:\.\d+)?$')
_QUARTER_REGEX = re.compile(r'(?i)q\s*([1-4])')
_DIGIT_REGEX = re.compile(r'\d+')


def _compose_series_column(ticker: Optional[str], metric: str) -> str:
    ticker_clean = (ticker or "").strip()
    if ticker_clean:
        return f"{ticker_clean}|{metric}"
    return metric


def _derive_metric_label(display_name: str, metric: str) -> str:
    if isinstance(display_name, str) and ' - ' in display_name:
        tail = display_name.split(' - ', 1)[1].strip()
        if tail:
            return tail
    return metric.replace('_', ' ').title()


def _sort_axis_values(values: List[str], x_field: str) -> List[str]:
    """Return axis labels sorted ascending using date/quarter heuristics."""
    _ = x_field  # reserved for future heuristics

    def sort_key(raw: Any) -> tuple:
        if raw is None:
            return (5, float('inf'), 0, '')
        text = str(raw).strip()
        if not text:
            return (5, float('inf'), 0, '')
        if _NUMERIC_REGEX.match(text):
            return (0, float(text), 0, text.lower())

        digits = [int(token) for token in _DIGIT_REGEX.findall(text)]
        year_candidates = [d for d in digits if d >= 1000]
        year = year_candidates[0] if year_candidates else (digits[0] if digits else None)
        remaining = digits.copy()
        if year is not None and year in remaining:
            remaining.remove(year)

        quarter_match = _QUARTER_REGEX.search(text)
        if quarter_match:
            quarter = int(quarter_match.group(1))
            year_value = year if year is not None else 0
            return (1, year_value, quarter, text.lower())

        if year is not None and remaining:
            month = remaining[0]
            day = remaining[1] if len(remaining) > 1 else 0
            return (2, year, month, day, text.lower())

        if year is not None:
            return (3, year, text.lower())

        return (4, text.lower())

    try:
        unique_values = list(dict.fromkeys(values))
        return sorted(unique_values, key=sort_key)
    except Exception:
        return values



def _coerce_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    try:
        cleaned = str(value).replace(',', '').strip()
        if not cleaned:
            return None
        return float(cleaned)
    except (TypeError, ValueError):
        return None


def _build_candlestick_spec(
    data: List[Dict[str, Any]],
    chart_plan: Dict[str, Any],
    charts_cfg: Dict[str, Any],
    intent_key: Optional[str],
    comparison: Optional[str],
) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
    series_list = chart_plan.get('series') or []
    if not series_list:
        return None, None

    primary = series_list[0]
    open_col = primary.get('open_column')
    high_col = primary.get('high_column')
    low_col = primary.get('low_column')
    close_col = primary.get('close_column')

    if not all([open_col, high_col, low_col, close_col]):
        fallback_column = close_col or primary.get('data_column')
        if fallback_column:
            fallback_plan = {
                'chart_type': 'line',
                'title': chart_plan.get('title'),
                'x_axis': chart_plan.get('x_axis', {}),
                'series': [{
                    'name': primary.get('name') or fallback_column,
                    'data_column': fallback_column,
                    'value_type': primary.get('value_type', 'currency'),
                }],
            }
            return None, fallback_plan
        return None, None

    axis_field = (chart_plan.get('x_axis') or {}).get('field') or 'date'
    axis_type = (chart_plan.get('x_axis') or {}).get('type') or 'time'
    fallback_candidates = ['calendar_date', 'date', 'trading_day', 'trading_date', 'time', 'timestamp', 'day']

    values_by_label: Dict[str, Dict[str, Any]] = {}
    for row in data:
        label_value = row.get(axis_field)
        if label_value is None:
            for candidate in fallback_candidates:
                if row.get(candidate) is not None:
                    label_value = row.get(candidate)
                    axis_field = candidate
                    break
        if label_value is None:
            continue

        o = _coerce_float(row.get(open_col))
        h = _coerce_float(row.get(high_col))
        l = _coerce_float(row.get(low_col))
        c = _coerce_float(row.get(close_col))
        if None in (o, h, l, c):
            continue

        label = str(label_value)
        volume_col = primary.get('volume_column')
        volume_value = _coerce_float(row.get(volume_col)) if volume_col else None
        values_by_label[label] = {
            'ohlc': [o, c, l, h],
            'volume': volume_value,
        }

    if not values_by_label:
        fallback_plan = {
            'chart_type': 'line',
            'title': chart_plan.get('title'),
            'x_axis': chart_plan.get('x_axis', {}),
            'series': [{
                'name': primary.get('name') or (close_col or 'Close'),
                'data_column': close_col or primary.get('data_column'),
                'value_type': primary.get('value_type', 'currency'),
            }],
        }
        return None, fallback_plan

    ordered_labels = _sort_axis_values(list(values_by_label.keys()), axis_field)
    candlestick_data = [values_by_label[label]['ohlc'] for label in ordered_labels]
    volume_values = [values_by_label[label]['volume'] for label in ordered_labels]

    light_theme = charts_cfg.get('themes', {}).get('light', {}) if isinstance(charts_cfg.get('themes'), dict) else {}
    candle_theme = light_theme.get('candlestick', {}) if isinstance(light_theme, dict) else {}
    up_color = candle_theme.get('upColor') or '#26A69A'
    down_color = candle_theme.get('downColor') or '#EF5350'
    border_up = candle_theme.get('upBorderColor') or up_color
    border_down = candle_theme.get('downBorderColor') or down_color

    series_name = primary.get('name') or 'Price'
    x_axis_option: Dict[str, Any] = {
        'type': 'category',
        'data': ordered_labels,
        'boundaryGap': True,
        'axisLabel': {'rotate': 0},
    }
    if axis_type == 'time':
        x_axis_option['axisLabel'] = {**x_axis_option['axisLabel'], 'formatter': '{value}'}

    y_axes: List[Dict[str, Any]] = [
        {
            'type': 'value',
            'scale': True,
            'name': 'Price',
        }
    ]

    echarts_series: List[Dict[str, Any]] = [
        {
            'name': series_name,
            'type': 'candlestick',
            'data': candlestick_data,
            'itemStyle': {
                'color': up_color,
                'color0': down_color,
                'borderColor': border_up,
                'borderColor0': border_down,
            },
            'emphasis': {
                'itemStyle': {
                    'color': up_color,
                    'color0': down_color,
                    'borderColor': border_up,
                    'borderColor0': border_down,
                }
            },
        }
    ]

    if any(v is not None for v in volume_values):
        volumes = [v if v is not None else 0 for v in volume_values]
        y_axes.append(
            {
                'type': 'value',
                'scale': True,
                'name': 'Volume',
                'axisLabel': {'formatter': '{value:,.0f}'},
                'splitLine': {'show': False},
            }
        )
        echarts_series.append(
            {
                'name': 'Volume',
                'type': 'bar',
                'data': volumes,
                'yAxisIndex': 1,
                'itemStyle': {'color': '#3F51B5', 'opacity': 0.35},
            }
        )

    included_columns = [col for col in [open_col, high_col, low_col, close_col] if col]
    volume_column = primary.get('volume_column')
    if volume_column:
        included_columns.append(volume_column)

    spec = {
        'title': {
            'left': 'center',
            'text': chart_plan.get('title') or 'Financial Analytics',
        },
        'tooltip': {
            'trigger': 'axis',
            'axisPointer': {'type': 'cross'},
        },
        'legend': {'data': [series_name] + (['Volume'] if len(echarts_series) > 1 else [])},
        'grid': {'left': '5%', 'right': '5%', 'bottom': '8%', 'top': '12%', 'containLabel': True},
        'xAxis': x_axis_option,
        'yAxis': y_axes,
        'series': echarts_series,
        'meta': {
            'chartDesign': {
                'chart_type': 'candlestick',
                'intent': intent_key,
                'comparison': comparison,
                'series': [series_name],
                'x_field': axis_field,
            },
            'seriesValueType': {series_name: primary.get('value_type', 'currency')},
            'seriesAxis': {series_name: 'left'},
            'includedColumns': included_columns,
            'defaultColumns': [series_name],
            'rawData': data,
            'ohlcColumns': {
                'open': open_col,
                'high': high_col,
                'low': low_col,
                'close': close_col,
                'volume': volume_column,
            },
        },
    }

    return spec, None


def _attach_comparison_meta(spec: Optional[Dict[str, Any]], comparison: Optional[str]) -> Optional[Dict[str, Any]]:
    """Attach comparison metadata to the chart spec and design."""
    if not spec or not isinstance(spec, dict) or not comparison:
        return spec
    meta = spec.setdefault('meta', {})
    if isinstance(meta, dict):
        meta['comparison'] = comparison
        chart_design = meta.get('chartDesign')
        if isinstance(chart_design, dict):
            chart_design['comparison'] = comparison
            if comparison == 'all':
                chart_design.setdefault('comparison_mode', 'multi_company')
    return spec


def _format_scope_banner(metric_label: str, tickers: List[str]) -> str:
    metric_label = metric_label.strip() if metric_label else "metric"
    if len(tickers) <= 6:
        tickers_fragment = ", ".join(tickers)
    else:
        tickers_fragment = ", ".join(tickers[:5]) + f", +{len(tickers) - 5} more"
    return f"Ranking latest {metric_label} across {tickers_fragment}"


def _build_ranking_bar_spec(
    data: List[Dict[str, Any]],
    chart_plan: Dict[str, Any],
    charts_cfg: Dict[str, Any],
    intent_key: Optional[str],
    comparison: Optional[str],
    statistic: Optional[str],
) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
    series_list = chart_plan.get('series') or []
    if not series_list:
        fallback = dict(chart_plan)
        fallback['chart_type'] = 'bar'
        fallback.setdefault('x_axis', {'field': 'ticker', 'type': 'category'})
        return None, fallback

    primary = series_list[0]
    metric_col = chart_plan.get('ranking_metric') or primary.get('data_column')
    if not metric_col:
        fallback = dict(chart_plan)
        fallback['chart_type'] = 'bar'
        fallback.setdefault('x_axis', {'field': 'ticker', 'type': 'category'})
        return None, fallback

    value_type = primary.get('value_type', 'number')
    entries: List[Tuple[str, Optional[float]]] = []
    for row in data:
        ticker = row.get('ticker')
        if not ticker:
            continue
        raw_val = row.get(metric_col)
        try:
            val = float(raw_val)
        except (TypeError, ValueError):
            val = None
        entries.append((str(ticker), val))

    filtered = [(ticker, val) for ticker, val in entries if val is not None]
    if not filtered:
        fallback = dict(chart_plan)
        fallback['chart_type'] = 'bar'
        fallback.setdefault('x_axis', {'field': 'ticker', 'type': 'category'})
        return None, fallback

    filtered.sort(key=lambda item: item[1], reverse=True)
    tickers_sorted = [ticker for ticker, _ in filtered]
    values_sorted = [val for _, val in filtered]

    palette = charts_cfg.get('themes', {}).get('light', {}).get('chart_colors', {}).get('primary_palette')
    if not isinstance(palette, list) or not palette:
        palette = ['#5470C6', '#91CC75', '#FAC858', '#EE6666', '#73C0DE']
    colors = [palette[i % len(palette)] for i in range(len(values_sorted))]

    label_formatter = '{c}'
    if value_type == 'percent':
        label_formatter = '{c}%'

    series = [{
        'name': primary.get('name') or metric_col.replace('_', ' ').title(),
        'type': 'bar',
        'data': [
            {'value': val, 'itemStyle': {'color': colors[idx]}}
            for idx, val in enumerate(values_sorted)
        ],
        'label': {
            'show': True,
            'position': 'right',
            'formatter': label_formatter,
        },
        'emphasis': {'focus': 'series'},
    }]

    metric_label = primary.get('name') or metric_col.replace('_', ' ').title()
    scope_banner = _format_scope_banner(metric_label, tickers_sorted)

    meta = {
        'chartDesign': {
            'chart_type': 'ranking_bar',
            'intent': intent_key,
            'comparison': comparison or ('all' if statistic == 'ranking_latest' else None),
            'statistic': statistic,
            'metric': metric_col,
        },
        'scopeBanner': scope_banner,
        'ranking': {
            'ordering': 'descending',
            'metric': metric_col,
            'statistic': statistic,
            'tickers': tickers_sorted,
        },
        'seriesValueType': {series[0]['name']: value_type},
        'rawData': data,
    }

    spec = {
        'title': {'left': 'center', 'top': '5%', 'text': chart_plan.get('title') or 'Ranking'},
        'tooltip': {'trigger': 'axis', 'axisPointer': {'type': 'shadow'}},
        'grid': {'left': '5%', 'right': '8%', 'bottom': '5%', 'top': '18%', 'containLabel': True},
        'xAxis': {
            'type': 'value',
            'axisLabel': {'formatter': '{value}%' if value_type == 'percent' else '{value}'},
        },
        'yAxis': {
            'type': 'category',
            'data': tickers_sorted,
            'axisLabel': {'interval': 0},
            'inverse': False,
        },
        'series': series,
        'legend': {'show': False},
        'meta': meta,
    }
    return spec, None


# Wrapper to convert shared function result to ChartPlanModel
def plan_chart_rule_based(
    data: List[Dict[str, Any]],
    query: str,
    intent_key: Optional[str] = None,
    *,
    statistic: Optional[str] = None,
) -> ChartPlanModel:
    """Wrapper around the shared chart planning logic that returns ChartPlanModel."""
    result = _plan_chart_rule_based_dict(data, query, intent_key, statistic=statistic)

    # Convert dict result to ChartPlanModel
    return ChartPlanModel(
        chart_type=result.get('chart_type', 'line'),
        x_axis=result.get('x_axis', {'field': 'calendar_year', 'type': 'category'}),
        title=result.get('title', 'Financial Analytics'),
        series=result.get('series', []),
        statistic=statistic or result.get('statistic'),
        ranking_metric=result.get('ranking_metric'),
    )

# Alias for backward compatibility


def build_chart_spec(
    data: List[Dict[str, Any]],
    chart_plan: Dict[str, Any],
    charts_cfg: Dict[str, Any],
    intent_key: Optional[str] = None,
    comparison: Optional[str] = None,
    statistic: Optional[str] = None,
) -> Dict[str, Any]:
    """Enhanced chart spec builder with dual axes and primary series detection."""
    chart_type = chart_plan.get('chart_type')
    if chart_type == 'candlestick':
        spec_result, fallback_plan = _build_candlestick_spec(data, chart_plan, charts_cfg, intent_key, comparison)
        if spec_result is not None:
            return _attach_comparison_meta(spec_result, comparison)
        if fallback_plan is not None:
            chart_plan = fallback_plan
            chart_type = chart_plan.get('chart_type')
    if chart_type == 'ranking_bar':
        spec_result, fallback_plan = _build_ranking_bar_spec(
            data,
            chart_plan,
            charts_cfg,
            intent_key,
            comparison,
            statistic,
        )
        if spec_result is not None:
            return _attach_comparison_meta(spec_result, comparison)
        if fallback_plan is not None:
            chart_plan = fallback_plan
            chart_type = chart_plan.get('chart_type')
    
    # Time axis
    x_field = chart_plan.get('x_axis', {}).get('field') or 'calendar_year'
    x_vals: List[str] = []
    seen = set()
    for row in data:
        xv = row.get(x_field)
        # Always normalize quarterly axis to "YYYY Qn" when year information exists
        if x_field == 'calendar_quarter' and row.get('calendar_year') and row.get('calendar_quarter'):
            xv = f"{row.get('calendar_year')} {row.get('calendar_quarter')}"
        if xv is None:
            continue
        s = str(xv)
        if s not in seen:
            seen.add(s)
            x_vals.append(s)

    x_vals = _sort_axis_values(x_vals, x_field)

    # Guardrail: if quarterly axis ended up as plain Q1..Q4 while data spans multiple years,
    # rebuild labels as composite year+quarter.
    try:
        if x_field == 'calendar_quarter' and x_vals and all(v in {'Q1','Q2','Q3','Q4'} for v in x_vals):
            years = [int(r.get('calendar_year')) for r in data if r.get('calendar_year') is not None]
            if years and (max(years) != min(years)):
                seen = set()
                rebuilt: List[str] = []
                for r in data:
                    if r.get('calendar_year') and r.get('calendar_quarter'):
                        label = f"{r.get('calendar_year')} {r.get('calendar_quarter')}"
                        if label not in seen:
                            seen.add(label)
                            rebuilt.append(label)
                if rebuilt:
                    x_vals = _sort_axis_values(rebuilt, 'calendar_quarter')
    except Exception:
        # Non-fatal; continue with current x_vals
        pass

    # Colors - enhanced with primary/secondary distinction and company colors
    colors = (charts_cfg.get('themes', {}).get('light', {}).get('chart_colors', {}).get('primary_palette') or
              ['#5470C6', '#91CC75', '#FAC858', '#EE6666', '#73C0DE'])
    
    # Get company-specific colors from config
    company_colors = CONFIGS.companies.get('display', {}).get('company_colors', {})
    
    primary_color = colors[0]
    secondary_colors = colors[1:] + ['#D4D4D4', '#B0B0B0', '#909090']

    # Special-case: All-companies market share — 100% stacked area with Top-N focus
    if intent_key == 'market_share_all':
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
        return _attach_comparison_meta(spec_stack, comparison)

    # Build series with enhanced metadata (generic path)
    series_defs = chart_plan.get('series', [])
    series = []
    
    metric_slugs = [s.get('data_column') for s in series_defs if s.get('data_column')]
    metric_slugs = [slug for slug in metric_slugs if isinstance(slug, str)]
    slugs = list(dict.fromkeys(metric_slugs))

    primary_slugs = detect_primary_series(intent_key, slugs)
    if not primary_slugs and slugs:
        percent_slugs = [s for s in slugs if any(keyword in s for keyword in ['percent', 'margin', 'growth', 'share'])]
        primary_slugs = [percent_slugs[0]] if percent_slugs else [slugs[0]]
    else:
        primary_slugs = list(dict.fromkeys(primary_slugs))

    composite_columns: List[str] = []
    display_names: Dict[str, str] = {}
    metric_display_names: Dict[str, str] = {}
    metric_series_columns: Dict[str, List[str]] = {}
    metric_legend_map: Dict[str, List[str]] = {}
    primary_series: List[str] = []
    
    # Assign axes based on data type
    series_axes = assign_series_axes(series_defs)
    
    # Default legend selection - primary series visible, others hidden
    default_legend_selection = {}
    
    has_ticker_filters = any(s.get('ticker_filter') for s in series_defs)
    multi_ticker_single_metric = has_ticker_filters and len(slugs) <= 1

    for i, s in enumerate(series_defs):
        name = s.get('name') or s.get('data_column')
        col = s.get('data_column')
        ticker_value = s.get('ticker_filter') or s.get('ticker')

        if isinstance(col, str):
            composite_key = _compose_series_column(ticker_value, col)
            composite_columns.append(composite_key)
            display_names[composite_key] = name
            display_names.setdefault(col, _derive_metric_label(name, col))
            metric_series_columns.setdefault(col, []).append(composite_key)
            metric_legend_map.setdefault(col, []).append(name)
            if col not in metric_display_names:
                metric_display_names[col] = _derive_metric_label(name, col)

        is_primary = name in primary_series or (isinstance(col, str) and col in primary_slugs)
        if comparison == 'all' or (comparison == 'multi' and 'ticker_filter' in s) or multi_ticker_single_metric:
            default_legend_selection[name] = True
        else:
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
            # Support derived percent series when only a ratio exists (e.g., market_share -> market_share_percent)
            value: Any = None
            if found:
                if col in found:
                    value = found.get(col)
                elif col.endswith('_percent'):
                    base = col[:-8]  # strip "_percent"
                    if base in found:
                        try:
                            raw = found.get(base)
                            value = float(raw) * 100.0 if raw is not None else None
                        except Exception:
                            value = None
            vals.append(value)
        
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

    if primary_slugs and not primary_series:
        for slug in primary_slugs:
            for legend_name in metric_legend_map.get(slug, []):
                if legend_name not in primary_series:
                    primary_series.append(legend_name)
    if not primary_series:
        primary_series = [s.get('name') or s.get('data_column') for s in series_defs]
    primary_series = list(dict.fromkeys(primary_series))

    is_multi_ticker_comparison = (
        comparison == 'all'
        or any(len(names) > 1 for names in metric_series_columns.values())
        or has_ticker_filters
    )

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
                'mutedSecondary': not is_multi_ticker_comparison
            },
            'seriesValueType': {s['name']: ('percent' if series_axes.get(s['name']) == 'right' else 'currency') for s in series},
            # Missing metadata for frontend compatibility
            'includedColumns': list(dict.fromkeys(composite_columns)),
            'metricColumns': slugs,
            'metricSeriesColumns': {key: list(dict.fromkeys(values)) for key, values in metric_series_columns.items()},
            'metricLegendMap': {key: list(dict.fromkeys(values)) for key, values in metric_legend_map.items()},
            'metricDisplayNames': metric_display_names,
            'displayNames': display_names,
            'defaultColumns': primary_slugs,
            'rawData': data,
            'seriesPercentFormat': {
                slug: 'pre_multiplied' for slug in slugs if 'percent' in slug or 'share' in slug or 'margin' in slug
            }
        }
    }
    return _attach_comparison_meta(spec, comparison)
