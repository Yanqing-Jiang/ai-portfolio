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
        def __init__(self, api_key=None, **kwargs):
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
    assert required_fields == ["intent", "followups"]
    # slots is emitted as a map and should stay optional for Responses compatibility
    assert "slots" not in required_fields
    slots_schema = schema["properties"]["slots"]
    assert slots_schema.get("type") == "object"
    slot_additional = slots_schema.get("additionalProperties") or {}
    assert slot_additional.get("$ref") == "#/$defs/LLMSlotStatusModel"
    assert slot_additional.get("additionalProperties") is False


@pytest.mark.asyncio
async def test_create_structured_emits_schema_metric_on_schema_error(monkeypatch):
    os.environ.setdefault("OPENAI_API_KEY", "test-key")

    class _StubResponses:
        async def parse(self, **kwargs):
            raise RuntimeError("text.format.schema violation in test harness")

    class _StubClient:
        def __init__(self, api_key=None, **kwargs):
            self.responses = _StubResponses()

    monkeypatch.setattr("unified_responses_client.AsyncOpenAI", _StubClient)
    monkeypatch.setattr("unified_responses_client.responses_call", lambda **kwargs: None)

    captured = {}

    def _capture_metric(**kwargs):
        captured.update(kwargs)

    monkeypatch.setattr("unified_responses_client.intent_resolution_schema_error", _capture_metric)

    client = UnifiedResponsesClient("test-key")
    with pytest.raises(RuntimeError):
        await client.create_structured(
            response_model=LLMIntentResolutionModel,
            messages=[{"role": "user", "content": "force schema error"}],
            reasoning_effort="medium",
            session_id="schema-metric",
        )

    assert captured["error"] == "text.format.schema"
    assert captured["response_model"] == "LLMIntentResolutionModel"
    assert captured["session_id"] == "schema-metric"
