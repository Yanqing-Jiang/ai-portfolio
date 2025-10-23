import asyncio
import os

import pytest

from analytics.core.intent_impl.models import (
    IntentSelectionModel,
    LLMIntentResolutionModel,
)
from unified_responses_client import (
    UnifiedResponsesClient,
    _wrap_response_model,
)


class _DummyParsedResponse:
    def __init__(self, payload):
        self.parsed = payload


@pytest.mark.asyncio
async def test_create_structured_uses_wrapped_model(monkeypatch):
    os.environ.setdefault("OPENAI_API_KEY", "test-key")

    captured = {}

    class _StubResponses:
        async def parse(self, **kwargs):
            captured.update(kwargs)
            payload = LLMIntentResolutionModel(
                intent=IntentSelectionModel(key="revenue_comparison", confidence=0.9, mode="single_agent"),
                slots={},
                followups=[],
                notes=None,
            )
            return _DummyParsedResponse(payload)

    class _StubClient:
        def __init__(self, api_key=None):
            self.responses = _StubResponses()

    monkeypatch.setattr("unified_responses_client.AsyncOpenAI", _StubClient)
    monkeypatch.setattr("unified_responses_client.responses_call", lambda **kwargs: None)

    client = UnifiedResponsesClient("test-key")
    result, response_id = await client.create_structured(
        response_model=LLMIntentResolutionModel,
        messages=[{"role": "system", "content": "test"}, {"role": "user", "content": "Hello"}],
        reasoning_effort="low",
        session_id="session-123",
    )

    assert isinstance(result, LLMIntentResolutionModel)
    assert response_id is None  # stubbed client never sets an id
    assert "text_format" in captured
    wrapped_model = captured["text_format"]
    assert getattr(wrapped_model, "__responses_schema_normalized__", False)
    assert "response_format" not in captured


def test_wrap_response_model_schema_normalisation():
    wrapped = _wrap_response_model(LLMIntentResolutionModel)
    assert getattr(wrapped, "__responses_schema_normalized__", False)

    schema = wrapped.model_json_schema()
    required_fields = schema.get("required") or []
    # slots is emitted as a map and should stay optional for Responses compatibility
    assert "slots" not in required_fields
    slots_schema = schema["properties"]["slots"]
    assert slots_schema.get("type") == "object"
    assert slots_schema.get("additionalProperties") == {"$ref": "#/$defs/LLMSlotStatusModel"}
