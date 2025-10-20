from __future__ import annotations

import logging
from typing import Any, Dict, Optional
import re

from ..core.companies import (
    format_company_error,
    get_ticker_list,
    resolve_alias_to_ticker,
    sanitize_ticker,
    validate_and_resolve_company,
)
from ..core.context import get_configs
from ..core.state import IntentModel, QueryPlanModel
from ..semantic.catalog import get_semantic_catalog
from .sql_planner import plan_sql_rule_based

CONFIGS = get_configs()
SEMANTIC_CATALOG = get_semantic_catalog()
logger = logging.getLogger(__name__)


def _resolve_company(intent: IntentModel, configs: Dict[str, Any]) -> Optional[str]:
    slots = intent.slots_detected or {}
    raw_company = slots.get('company')
    if not raw_company:
        return None
    ticker = validate_and_resolve_company(raw_company, configs)
    if ticker:
        return ticker
    return None


def compile_sql_from_plan(
    plan: QueryPlanModel,
    intent: IntentModel,
    configs: Optional[Dict[str, Any]] = None,
    template: Optional[Dict[str, Any]] = None,
) -> str:
    cfg = configs or CONFIGS.__dict__
    intent_dict = intent.model_dump() if hasattr(intent, 'model_dump') else intent
    plan_dict = plan.model_dump() if hasattr(plan, 'model_dump') else plan_sql_rule_based(intent, cfg)

    intent_key = intent.intent_key
    logger.info("[SQL_COMPILER] Compiling SQL for intent %s", intent_key)

    ticker_list = get_ticker_list(cfg)
    ticker_clause = "'" + "','".join(ticker_list) + "'"

    target_ticker = _resolve_company(intent, cfg)

    years_back = plan_dict.get('timeframe', {}).get('years_back')
    if not years_back:
        defaults = SEMANTIC_CATALOG.query_defaults()
        years_back = defaults.get('default_years_back', 5)

    granularity = plan.granularity if isinstance(plan, QueryPlanModel) else plan_dict.get('granularity', 'annual')

    template_choice: Optional[str] = None
    if template:
        if granularity == 'annual' and template.get('sql_template_annual'):
            template_choice = template.get('sql_template_annual')
        elif granularity == 'quarterly' and template.get('sql_template_quarterly'):
            template_choice = template.get('sql_template_quarterly')
        elif template.get('sql_template'):
            template_choice = template.get('sql_template')
        elif isinstance(template.get('sql_template_map'), dict):
            template_choice = template['sql_template_map'].get(granularity) or template['sql_template_map'].get('default')
    if template_choice:
        sql_template = template_choice or ""
        requires_company = '{target_ticker}' in sql_template
        if requires_company and not target_ticker:
            raise ValueError(format_company_error(intent.slots_detected.get('company'), cfg))
        sql = sql_template
        if target_ticker:
            sql = sql.replace('{target_ticker}', target_ticker)
        primary_metric = None
        plan_metrics = []
        if isinstance(plan, QueryPlanModel):
            plan_metrics = plan.metrics
        elif isinstance(plan_dict.get('metrics'), list):
            plan_metrics = plan_dict.get('metrics')
        if plan_metrics:
            primary_metric = plan_metrics[0]
        safe_metric = (primary_metric or 'Revenue').replace("'", "''")
        sql = sql.replace('{primary_metric}', safe_metric)
        sql = sql.replace('{years_back}', str(years_back))
        start_year = plan_dict.get('timeframe', {}).get('start_year')
        end_year = plan_dict.get('timeframe', {}).get('end_year')
        sql = sql.replace('{start_year}', 'NULL' if start_year is None else str(start_year))
        sql = sql.replace('{end_year}', 'NULL' if end_year is None else str(end_year))
        select_clause, group_by_clause, join_clause, order_by_clause, period_filter_clause = _granularity_clauses(granularity)
        sql = sql.replace('{select_clause}', select_clause)
        sql = sql.replace('{group_by_clause}', group_by_clause)
        sql = sql.replace('{join_clause}', join_clause)
        sql = sql.replace('{order_by_clause}', order_by_clause)
        sql = sql.replace('{period_filter_clause}', period_filter_clause)
        sql = sql.replace("('AMD','AVGO','INTC','MU','NVDA','QCOM','TXN')", f"({ticker_clause})")
        # If granularity is annual, strip quarterly-only filters to avoid empty results
        if granularity != 'quarterly':
            sql = re.sub(r"\s+AND\s+calendar_quarter_num\s+IS\s+NOT\s+NULL\s*", " ", sql)
            sql = re.sub(r"\s+AND\s+\{period_filter_clause\}\s*", " ", sql)
            sql = re.sub(r"\s+AND\s+1\s*=\s*1\s*", " ", sql)
        return sql.strip().rstrip(';')

    return _generic_sql(plan, ticker_clause, years_back, granularity)


def _granularity_clauses(granularity: str) -> tuple[str, str, str, str, str]:
    if granularity == 'quarterly':
        select_clause = "calendar_year, calendar_quarter_num, calendar_quarter"
        group_by_clause = select_clause
        join_clause = (
            "cr.calendar_year = mr.calendar_year AND "
            "cr.calendar_quarter_num = mr.calendar_quarter_num AND "
            "cr.calendar_quarter = mr.calendar_quarter"
        )
        order_by_clause = "calendar_year, calendar_quarter_num"
        period_filter_clause = "calendar_quarter_num IS NOT NULL"
    else:
        select_clause = "calendar_year"
        group_by_clause = select_clause
        join_clause = "cr.calendar_year = mr.calendar_year"
        order_by_clause = "calendar_year"
        period_filter_clause = "1=1"
    return select_clause, group_by_clause, join_clause, order_by_clause, period_filter_clause


def _generic_sql(plan: QueryPlanModel, ticker_clause: str, years_back: int, granularity: str) -> str:
    order_by_clause = "calendar_year, calendar_quarter_num" if granularity == 'quarterly' else "calendar_year"
    metric_name = plan.metrics[0] if getattr(plan, "metrics", []) else "Revenue"
    metric_name = metric_name.replace("'", "''")
    base = [
        "SELECT ticker, calendar_year",
    ]
    if granularity == 'quarterly':
        base.append(", calendar_quarter_num, calendar_quarter")
    base.append(", SUM(value) AS value")
    base.append(" FROM comp_financials")
    base.append(f" WHERE metric = '{metric_name}'")
    if granularity == 'quarterly':
        base.append(" AND calendar_quarter_num IS NOT NULL")
    base.append(" AND calendar_year >= EXTRACT(YEAR FROM CURRENT_DATE) - {}".format(years_back))
    base.append(f" AND ticker IN ({ticker_clause})")
    if granularity == 'quarterly':
        base.append(" GROUP BY ticker, calendar_year, calendar_quarter_num, calendar_quarter")
    else:
        base.append(" GROUP BY ticker, calendar_year")
    base.append(f" ORDER BY ticker, {order_by_clause}")
    return "".join(base)
