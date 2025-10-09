from __future__ import annotations

import copy
from typing import Any, Dict, Optional, List

from ..core.context import get_configs
from ..core.state import IntentModel, QueryPlanModel
from ..semantic.catalog import get_semantic_catalog

CONFIGS = get_configs()
SEMANTIC_CATALOG = get_semantic_catalog()


def _coerce_slots(intent: IntentModel) -> Dict[str, Any]:
    slots = intent.slots_detected or {}
    if isinstance(slots, dict):
        return slots
    return dict(slots)


def _fallback_plan_defaults(slots: Dict[str, Any]) -> Dict[str, Any]:
    defaults = SEMANTIC_CATALOG.query_defaults()
    years_back = defaults.get("default_years_back", 5)
    raw_granularity = slots.get("granularity")
    granularity = "quarterly" if isinstance(raw_granularity, str) and "quarter" in raw_granularity.lower() else "annual"
    time_grain = SEMANTIC_CATALOG.get_time_grain(granularity)
    limit = defaults.get("default_limit", SEMANTIC_CATALOG.default_limit() or 500)
    timeframe = {}
    timeframe_slot = slots.get("timeframe")
    if isinstance(timeframe_slot, dict):
        timeframe.update(timeframe_slot)
    timeframe.setdefault("years_back", years_back)
    statistic = slots.get("statistic")
    if isinstance(statistic, str):
        statistic = statistic.strip() or None
    else:
        statistic = None

    return {
        "metrics": ["Revenue"],
        "derived_metrics": [],
        "comparison": None,
        "statistic": statistic,
        "granularity": granularity,
        "timeframe": timeframe,
        "group_by": time_grain.group_by,
        "filters": {},
        "limit": limit,
    }


def plan_sql_rule_based(intent: IntentModel, configs: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    _ = configs or CONFIGS.__dict__
    slots = _coerce_slots(intent)
    intent_spec = SEMANTIC_CATALOG.get_intent_spec(intent.intent_key)
    statistic = slots.get("statistic")
    if isinstance(statistic, str):
        statistic = statistic.strip() or None
    else:
        statistic = None

    if not intent_spec:
        slots_with_stat = dict(slots)
        slots_with_stat["statistic"] = statistic
        return _fallback_plan_defaults(slots_with_stat)

    defaults = SEMANTIC_CATALOG.query_defaults()

    # ---- metrics ----
    metric_specs = SEMANTIC_CATALOG.list_metric_specs(intent_spec.metrics)
    metrics: List[str] = [spec.source for spec in metric_specs if not spec.is_derived]
    if not metrics:
        metrics = intent_spec.metrics or ["Revenue"]
    metrics = list(dict.fromkeys(metrics))

    derived_specs = SEMANTIC_CATALOG.list_metric_specs(intent_spec.derived_metrics)
    derived = [spec.key for spec in derived_specs]

    # ---- timeframe ----
    timeframe_input = slots.get("timeframe")
    timeframe: Dict[str, Any] = {}
    if isinstance(timeframe_input, dict):
        timeframe.update(timeframe_input)
    years_back = timeframe.get("years_back")
    if not years_back:
        years_back = intent_spec.default_years_back or defaults.get("default_years_back") or SEMANTIC_CATALOG.default_years_back() or 5
        timeframe["years_back"] = years_back

    # ---- granularity ----
    requested_grain = slots.get("granularity")
    granularity = SEMANTIC_CATALOG.resolve_granularity(
        requested=requested_grain,
        allowed=intent_spec.allowed_granularities,
        default_key=intent_spec.default_granularity,
    )
    time_grain = SEMANTIC_CATALOG.get_time_grain(granularity)

    group_by = intent_spec.group_by or time_grain.group_by
    group_by = list(dict.fromkeys(group_by)) if group_by else time_grain.group_by

    filters = dict(intent_spec.filters or {})
    if time_grain.filter and not filters.get("time_grain_filter"):
        filters["time_grain_filter"] = time_grain.filter

    limit = intent_spec.default_limit or defaults.get("default_limit") or SEMANTIC_CATALOG.default_limit() or 500

    plan_dict = {
        "metrics": metrics,
        "derived_metrics": derived,
        "timeframe": timeframe,
        "granularity": granularity,
        "comparison": intent_spec.comparison,
        "statistic": statistic,
        "group_by": group_by,
        "filters": filters,
        "limit": limit,
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

