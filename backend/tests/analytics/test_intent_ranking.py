import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[2]))

from analytics.core.intent_impl.detection import heuristic_intent
from analytics.core.intent_impl.models import IntentModel, intent_to_sql_criteria


def test_heuristic_sets_ranking_slots_defaults():
    query = "Who leads operating leverage right now?"
    intent = heuristic_intent(query, configs={})
    assert intent.slots_detected.get("comparison") == "all"
    assert intent.slots_detected.get("statistic") == "ranking_latest"
    assert intent.slots_detected.get("tickers"), "Default tickers should be populated"


def test_intent_to_sql_criteria_copies_statistic():
    slots = {
        "company": None,
        "tickers": ["AMD", "NVDA"],
        "statistic": "ranking_latest",
        "comparison": "all",
    }
    intent = IntentModel(intent_key="margins_vs_peers", confidence=0.9, slots_detected=slots)
    criteria = intent_to_sql_criteria(intent, configs={})
    assert criteria.statistic == "ranking_latest"
    assert criteria.comparison == "all"
