from __future__ import annotations

import copy
from typing import Any, Dict, Optional

from ..core.context import get_configs
from ..core.state import IntentModel, QueryPlanModel

CONFIGS = get_configs()


def _coerce_slots(intent: IntentModel) -> Dict[str, Any]:
    slots = intent.slots_detected or {}
    if isinstance(slots, dict):
        return slots
    return dict(slots)


def plan_sql_rule_based(intent: IntentModel, configs: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    cfg = configs or CONFIGS.__dict__
    slots = _coerce_slots(intent)
    intent_key = intent.intent_key

    metrics: list[str] = []
    derived: list[str] = []
    comparison: Optional[str] = None

    if intent_key == "market_share_all":
        metrics = ["Revenue"]
        comparison = "all"
    elif intent_key == "market_share_single":
        metrics = ["Revenue"]
        comparison = "single"
    elif intent_key in {"margins_vs_peers", "margin_growth_vs_peers"}:
        metrics = ["Revenue", "Gross Profit", "Operating Income", "Net Income"]
        derived = ["gross_margin", "operating_margin", "net_margin"]
        comparison = "vs_avg"
    elif intent_key == "revenue_growth_vs_avg":
        metrics = ["Revenue"]
        comparison = "vs_avg"
    elif intent_key in {"rnd_intensity_vs_peers", "rnd_expense_vs_peers"}:
        metrics = ["Revenue", "R&D Expense"] if intent_key == "rnd_intensity_vs_peers" else ["R&D Expense"]
        if intent_key == "rnd_intensity_vs_peers":
            derived = ["rnd_intensity"]
        comparison = "vs_avg"
    elif intent_key == "rnd_top_spender":
        metrics = ["R&D Expense"]
        comparison = "leaderboard"
    else:
        metrics = ["Revenue"]

    timeframe = slots.get("timeframe", {}) if isinstance(slots.get("timeframe"), dict) else {}
    years_back = timeframe.get("years_back")
    default_years = (cfg.get("database", {}) or {}).get("query_defaults", {}).get("default_years_back", 5)
    years_back = years_back or default_years

    raw_granularity = slots.get("granularity", "annual")
    granularity = "quarterly" if raw_granularity and "quarter" in str(raw_granularity).lower() else "annual"

    group_by = ["calendar_year"]
    if granularity == "quarterly":
        group_by.extend(["calendar_quarter_num", "calendar_quarter"])

    default_limit = (cfg.get("database", {}) or {}).get("query_defaults", {}).get("default_limit", 500)

    plan_dict = {
        "metrics": metrics,
        "derived_metrics": derived,
        "timeframe": {"years_back": years_back},
        "granularity": granularity,
        "comparison": comparison,
        "group_by": group_by,
        "filters": {},
        "limit": default_limit,
    }
    return plan_dict


def build_query_plan(intent: IntentModel, configs: Optional[Dict[str, Any]] = None) -> QueryPlanModel:
    return QueryPlanModel(**plan_sql_rule_based(intent, configs))


def choose_template(
    intent: IntentModel,
    plan: QueryPlanModel,
    configs: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    cfg = configs or CONFIGS.__dict__
    patterns = (cfg.get("queries", {}) or {}).get("query_patterns", {})
    if not intent.intent_key:
        return None
    template_entry = patterns.get(intent.intent_key)
    if not template_entry:
        return None
    template = copy.deepcopy(template_entry)
    if intent.intent_key == 'rnd_top_spender':
        timeframe = getattr(plan, 'timeframe', None)
        start_year = getattr(timeframe, 'start_year', None) if timeframe else None
        end_year = getattr(timeframe, 'end_year', None) if timeframe else None
        single_year_sql = template.get('single_year_template')
        if start_year is not None and single_year_sql and (end_year is None or end_year == start_year):
            template['sql_template'] = single_year_sql
            if template.get('single_year_description'):
                template['description'] = template['single_year_description']
    return template



