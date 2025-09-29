import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
BACKEND_ROOT = Path(__file__).resolve().parents[2]
for entry in (ROOT, BACKEND_ROOT):
    entry_str = str(entry)
    if entry_str not in sys.path:
        sys.path.insert(0, entry_str)

from backend.analytics.core.state import IntentModel, QueryPlanModel
from backend.analytics.sql.prompt_builder import build_sql_messages, extract_sql_from_response


@pytest.mark.asyncio
async def test_build_sql_messages_contains_plan_details():
    intent = IntentModel(intent_key="market_share_single", confidence=0.92, slots_detected={"company": "NVDA"})
    plan = QueryPlanModel(metrics=["Revenue"], granularity="annual")

    messages = await build_sql_messages(
        original_query="What is NVDA market share?",
        intent=intent,
        plan=plan,
    )

    assert messages[0]["role"] == "system"
    user_message = messages[1]["content"]
    assert "market_share_single" in user_message
    assert "Revenue" in user_message
    assert "Allowed tables" in user_message


def test_extract_sql_from_response_handles_code_block():
    content = """```sql
SELECT 1;
```"""
    sql = extract_sql_from_response(content)
    assert sql.strip() == "SELECT 1;"

    sql = extract_sql_from_response("SELECT 2;")
    assert sql == "SELECT 2;"
