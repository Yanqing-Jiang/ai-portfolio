from __future__ import annotations
from typing import Dict, Any, List, Optional, Tuple
from .types import IntentModel, QueryPlanModel
from analytics_shared.sql.planner import plan_sql_rule_based, choose_template, get_granularity_clauses
from analytics_shared.sql.compiler import compile_sql_from_plan
from analytics_shared.companies.resolver import resolve_alias_to_ticker
from analytics_shared.companies.tickers import get_ticker_list, sanitize_ticker

# Phase 2: build QueryPlan/SQLPlan and deterministic compiler


# Import shared SQL planning function
# (plan_sql_rule_based imported from analytics_shared.sql.planner)


# Import shared template selection function
# (choose_template imported from analytics_shared.sql.planner)


# Import shared granularity function
# (get_granularity_clauses imported from analytics_shared.sql.planner)
_granularity_clauses = get_granularity_clauses


# Import shared company resolution function
# (resolve_alias_to_ticker imported from analytics_shared.companies.resolver)


# Import shared ticker list function
# (_ticker_list replaced with get_ticker_list from analytics_shared.companies.tickers)
_ticker_list = get_ticker_list


# Import shared ticker sanitization function
# (_sanitize_ticker imported as sanitize_ticker from analytics_shared.companies.tickers)
_sanitize_ticker = sanitize_ticker


# Import shared SQL compilation function
# (compile_sql_from_plan imported from analytics_shared.sql.compiler)
