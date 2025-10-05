import asyncio
import logging
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
    tools = search_call.get('tools')
    assert isinstance(tools, list) and len(tools) > 0
    assert isinstance(tools[0], dict) and 'google_search_retrieval' in tools[0]

    payload = result.to_payload()
    assert payload["summary"] == "Summary from Gemini"
    assert payload["snippets"][0]["title"] == "Headline"

def test_perform_response_search_runs_two_step_flow(monkeypatch):
    class TwoStepModelSpy:
        created_instances = []

        def __init__(self, model_name: str, generation_config: Dict[str, Any]):
            self.model_name = model_name
            self._config = generation_config
            self.calls = []
            TwoStepModelSpy.created_instances.append(self)

        def generate_content(self, **kwargs):
            self.calls.append(kwargs)
            if kwargs.get("tools"):
                return {
                    "text": "Synthesized search answer",
                    "response_id": "search-001",
                    "usage": {"input_tokens": 8, "output_tokens": 16},
                }
            return {"text": '  "NVDA 2025 revenue outlook?"\nAdd context that should be ignored.'}

    TwoStepModelSpy.created_instances = []
    monkeypatch.setattr(response_search, "_model", None)
    monkeypatch.setattr(response_search, "_genai_configured", False)
    monkeypatch.setattr(response_search, "_DEFAULT_MODEL", "gemini-two-step")

    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GEMIN_API_KEY", raising=False)
    monkeypatch.setenv("GEMINI_API_KEY", "two-step-key")
    monkeypatch.setenv("GEMINI_SEARCH_MODEL", "gemini-two-step")

    configured = {}

    def fake_configure(*, api_key):
        configured["api_key"] = api_key

    monkeypatch.setattr(response_search.genai, "configure", fake_configure)
    monkeypatch.setattr(response_search.genai, "GenerativeModel", TwoStepModelSpy)

    result = asyncio.run(
        response_search.perform_response_search('Tell me about "NVDA 2025" revenue outlook?')
    )

    assert configured["api_key"] == "two-step-key"

    instance = TwoStepModelSpy.created_instances[0]
    assert len(instance.calls) == 2

    rewrite_prompt = instance.calls[0]["contents"][0]["parts"][0]["text"]
    assert "User question: Tell me about \"NVDA 2025\" revenue outlook?" in rewrite_prompt

    search_call = instance.calls[1]
    tools = search_call.get("tools")
    assert isinstance(tools, list) and len(tools) > 0
    assert isinstance(tools[0], dict) and 'google_search_retrieval' in tools[0]

    search_prompt = search_call["contents"][0]
    assert search_prompt.endswith("NVDA 2025 revenue outlook?.")
    assert '"' not in search_prompt

    assert result.summary == "Synthesized search answer"
    assert result.model == "gemini-two-step"

def test_perform_response_search_logs_steps(monkeypatch, caplog):
    class AMDGenerativeModel:
        created_instances = []

        def __init__(self, model_name: str, generation_config: Dict[str, Any]):
            self.model_name = model_name
            self._config = generation_config
            self.calls = []
            AMDGenerativeModel.created_instances.append(self)

        def generate_content(self, **kwargs):
            self.calls.append(kwargs)
            if kwargs.get("tools"):
                return {
                    "text": "AMD expands MI300 deployments across hyperscalers",
                    "response_id": "search-amd-001",
                    "usage": {"input_tokens": 11, "output_tokens": 38},
                    "candidates": [
                        {
                            "content": {"parts": [{"text": "AMD MI300 orders climb on cloud demand."}]},
                            "grounding": {
                                "supports": [
                                    {
                                        "title": "AMD MI300 demand surges",
                                        "url": "https://example.com/amd-mi300",
                                        "snippet": "AMD reports record data center momentum.",
                                        "published_at": "2025-09-28",
                                    }
                                ]
                            },
                        }
                    ],
                }
            return {"text": "AMD data center AI updates"}

    AMDGenerativeModel.created_instances = []
    monkeypatch.setattr(response_search, "_model", None)
    monkeypatch.setattr(response_search, "_genai_configured", False)
    monkeypatch.setattr(response_search, "_DEFAULT_MODEL", "gemini-amd-news")

    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GEMIN_API_KEY", raising=False)
    monkeypatch.setenv("GEMINI_API_KEY", "amd-key")
    monkeypatch.setenv("GEMINI_SEARCH_MODEL", "gemini-amd-news")

    configured = {}

    def fake_configure(*, api_key):
        configured["api_key"] = api_key

    monkeypatch.setattr(response_search.genai, "configure", fake_configure)
    monkeypatch.setattr(response_search.genai, "GenerativeModel", AMDGenerativeModel)

    caplog.set_level(logging.INFO, logger=response_search.logger.name)

    result = asyncio.run(
        response_search.perform_response_search(
            "Latest AMD data center news?",
            session_id="session-amd",
        )
    )

    assert configured["api_key"] == "amd-key"

    messages = [record.message for record in caplog.records]
    assert "ResponseSearch Step 1: chat rewrite" in messages
    assert "ResponseSearch Step 2: search result" in messages

    step1 = next(record for record in caplog.records if record.message == "ResponseSearch Step 1: chat rewrite")
    step2 = next(record for record in caplog.records if record.message == "ResponseSearch Step 2: search result")

    assert step1.step == "response_search.step1"
    assert step1.phase == "chat"
    assert step1.query == "Latest AMD data center news?"
    assert step1.search_topic == "AMD data center AI updates"
    assert step1.session_id == "session-amd"

    assert step2.step == "response_search.step2"
    assert step2.phase == "search"
    assert step2.session_id == "session-amd"
    assert step2.search_topic == "AMD data center AI updates"
    assert step2.snippets == len(result.snippets)
    assert step2.summary_present == bool(result.summary)
    assert step2.latency_ms == result.latency_ms

    assert caplog.records.index(step1) < caplog.records.index(step2)

    assert result.summary == "AMD expands MI300 deployments across hyperscalers"
    assert result.snippets
    assert result.model == "gemini-amd-news"

