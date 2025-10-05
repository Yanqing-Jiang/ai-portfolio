import asyncio
from typing import Any, Dict

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parents[2]))

from analytics.services import response_search


class DummyGenerativeModel:
    created_instances = []

    def __init__(self, model_name: str, generation_config: Dict[str, Any]):
        self.model_name = model_name
        self._config = generation_config
        self.calls = []
        DummyGenerativeModel.created_instances.append(self)

    def generate_content(self, **kwargs):
        self.calls.append(kwargs)
        if kwargs.get('tools'):
            return {
                "text": "Summary from Gemini",
                "usage": {"input_tokens": 10, "output_tokens": 42},
                "candidates": [
                    {
                        "content": {"parts": [{"text": "Candidate narrative chunk"}]},
                        "grounding": {
                            "supports": [
                                {
                                    "title": "Headline",
                                    "url": "https://example.com/article",
                                    "snippet": "Snippet text",
                                    "published_at": "2025-10-01",
                                }
                            ]
                        },
                    }
                ],
            }
        return {"text": "NVDA latest earnings momentum"}


def test_perform_response_search_uses_gemin_api_key(monkeypatch):
    DummyGenerativeModel.created_instances = []
    response_search._genai_configured = False
    response_search._model = None

    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setenv("GEMIN_API_KEY", "dummy-key")
    monkeypatch.setenv("GEMINI_SEARCH_MODEL", "gemini-test-model")
    response_search._DEFAULT_MODEL = "gemini-test-model"
    response_search._model = None
    response_search._genai_configured = False

    calls = {}

    def fake_configure(*, api_key):
        calls["configured_with"] = api_key

    monkeypatch.setattr(response_search.genai, "configure", fake_configure)
    monkeypatch.setattr(response_search.genai, "GenerativeModel", DummyGenerativeModel)

    result = asyncio.run(response_search.perform_response_search("What is NVDA's guidance for next quarter?", session_id="session-123"))

    assert result.summary == "Summary from Gemini"
    assert result.model == "gemini-test-model"
    assert result.snippets, "Expected grounded snippets from dummy response"
    assert calls.get("configured_with") == "dummy-key"

    instance = DummyGenerativeModel.created_instances[0]
    assert len(instance.calls) == 2
    refine_call = instance.calls[0]
    search_call = instance.calls[1]
    assert 'tools' not in refine_call
    search_focus = refine_call['contents'][0]['parts'][0]['text']
    assert 'latest' in search_focus.lower()
    assert search_call.get('tools') == ['google_search']

    payload = result.to_payload()
    assert payload["summary"] == "Summary from Gemini"
    assert payload["snippets"][0]["title"] == "Headline"
