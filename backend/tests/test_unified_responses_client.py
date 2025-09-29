import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.unified_responses_client import UnifiedResponsesClient


def _make_client():
    return object.__new__(UnifiedResponsesClient)


def test_extract_tool_calls_from_required_action_payload():
    client = _make_client()
    payload = {
        "id": "resp_123",
        "required_action": {
            "type": "submit_tool_outputs",
            "submit_tool_outputs": {
                "tool_calls": [
                    {
                        "id": "call_1",
                        "type": "function",
                        "function": {
                            "name": "lookup_metrics",
                            "arguments": json.dumps({"query": "revenue growth"})
                        }
                    }
                ]
            }
        }
    }

    calls = client._extract_tool_calls(payload)
    assert len(calls) == 1

    call = calls[0]
    assert call.id == "call_1"
    assert getattr(call, "type", None) == "function"
    assert call.function.name == "lookup_metrics"
    assert json.loads(call.function.arguments)["query"] == "revenue growth"


def test_extract_tool_calls_preserves_existing_tool_objects():
    client = _make_client()

    function_obj = SimpleNamespace(name="plan_and_select_template", arguments="{}")
    original_call = SimpleNamespace(id="call_2", type="function", function=function_obj)
    response = SimpleNamespace(tool_calls=[original_call])

    calls = client._extract_tool_calls(response)
    assert calls == [original_call]
