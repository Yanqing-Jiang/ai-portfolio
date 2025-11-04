from analytics.flows.planner_executor import _coerce_to_mapping
plan_str = "@{metrics=System.Object[]; derived_metrics=System.Object[]; timeframe=; granularity=annual; comparison=all; statistic=; group_by=System.Object[]; filters=; limit=500}"
print(_coerce_to_mapping(plan_str))
