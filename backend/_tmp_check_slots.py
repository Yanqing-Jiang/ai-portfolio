from analytics.core.intent import detect_intent_with_clarifications
from analytics.sql.sql_planner import build_query_plan
from analytics.core.clarify import detect_missing_slots
from analytics.core.context import get_configs

query = "Nvidia market share in the past 5 years"
configs = get_configs().__dict__
intent = detect_intent_with_clarifications(query, configs)
plan = build_query_plan(intent, configs)
print('intent_key', intent.intent_key, 'confidence', intent.confidence)
print('plan.comparison', plan.comparison)
missing = detect_missing_slots(intent, plan, None, configs)
print('missing slots:', [m.slot for m in missing])
for req in missing:
    print(req.slot, req.question)
