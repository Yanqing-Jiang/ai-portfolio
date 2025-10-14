import asyncio
import logging
from typing import Any, Dict

import pytest
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parents[2]))

from analytics.services import response_search


@pytest.fixture(autouse=True)
def reset_response_search_state():
    original_state = (
        response_search._model,
        response_search._model_name,
        response_search._genai_configured,
        response_search._DEFAULT_MODEL,
    )
    response_search._model = None
    response_search._model_name = None
    response_search._genai_configured = False
    yield
    response_search._model, response_search._model_name, response_search._genai_configured, response_search._DEFAULT_MODEL = original_state



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
                "response_id": "search-primary",
                "usage": {"input_tokens": 10, "output_tokens": 42},
                "candidates": [
                    {
                        "content": {"parts": [{"text": "Candidate narrative chunk"}]},
                        "groundingMetadata": {
                            "groundingSupports": [
                                {
                                    "segment": {"text": "Snippet text"},
                                    "groundingChunkIndices": [0],
                                    "title": "Headline",
                                }
                            ],
                            "groundingChunks": [
                                {
                                    "web": {
                                        "uri": "https://example.com/article",
                                        "title": "Headline",
                                        "displayUri": "example.com",
                                        "publishedDate": "2025-10-01",
                                    }
                                }
                            ],
                        },
                    }
                ],
            }
        return {"text": '{"topics":[{"label":"Primary question","query":"NVDA latest earnings","reason":"Company focus"},{"label":"Industry context","query":"Semiconductor industry outlook","reason":"Sector backdrop"}]}' }


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

    assert 'Summary from Gemini' in (result.summary or '')
    assert result.model == "gemini-test-model"
    assert result.snippets, "Expected grounded snippets from dummy response"
    assert result.search_topics and result.search_topics[0] == "NVDA latest earnings"
    assert calls.get("configured_with") == "dummy-key"

    instance = DummyGenerativeModel.created_instances[0]
    assert len(instance.calls) == len(result.search_topics) + 1
    plan_call = instance.calls[0]
    assert 'tools' not in plan_call
    plan_prompt = plan_call['contents'][0]['parts'][0]['text']
    assert 'User question: What is NVDA' in plan_prompt
    search_calls = instance.calls[1:]
    for call, topic in zip(search_calls, result.search_topics):
        tools = call.get('tools')
        assert isinstance(tools, list) and len(tools) > 0
        assert isinstance(tools[0], dict) and 'google_search' in tools[0]
        prompt_preview = call['contents'][0]
        assert topic in prompt_preview

    payload = result.to_payload()
    assert 'Summary from Gemini' in (payload["summary"] or '')
    assert payload.get('topics') and payload['topics'][0]['snippets'][0]['title'] == "Headline"



def test_perform_response_search_handles_search_grounding_entries(monkeypatch):
    class SearchGroundingModel:
        created_instances = []

        def __init__(self, model_name: str, generation_config: Dict[str, Any]):
            self.model_name = model_name
            self._config = generation_config
            self.calls = []
            SearchGroundingModel.created_instances.append(self)

        def generate_content(self, **kwargs):
            self.calls.append(kwargs)
            if kwargs.get('tools'):
                return {
                    "text": "Grounded answer summary",
                    "response_id": "search-grounding-001",
                    "usage": {"input_tokens": 12, "output_tokens": 32},
                    "candidates": [
                        {
                            "content": {"parts": [{"text": "Grounded answer summary"}]},
                            "groundingMetadata": {
                                "searchGrounding": {
                                    "searchEntries": [
                                        {
                                            "id": "entry-1",
                                            "title": "IDC: AMD server market share climbs",
                                            "searchQuery": "amd server share 2025",
                                            "chunkSnippets": [
                                                {
                                                    "text": "IDC reports AMD server share rose to 35% in Q3 2025.",
                                                    "publishedDate": "2025-09-29",
                                                    "source": {
                                                        "uri": "https://example.com/amd-share",
                                                        "title": "IDC: AMD server market share climbs",
                                                        "displayUri": "example.com"
                                                    }
                                                }
                                            ]
                                        }
                                    ]
                                }
                            }
                        }
                    ]
                }
            return {"text": '{"topics":[{"label":"Primary question","query":"AMD server share 2025","reason":"Company trend"}]}' }

    SearchGroundingModel.created_instances = []
    monkeypatch.setattr(response_search, "_model", None)
    monkeypatch.setattr(response_search, "_genai_configured", False)
    monkeypatch.setattr(response_search, "_DEFAULT_MODEL", "gemini-grounding")

    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GEMIN_API_KEY", raising=False)
    monkeypatch.setenv("GEMINI_API_KEY", "grounding-key")
    monkeypatch.setenv("GEMINI_SEARCH_MODEL", "gemini-grounding")

    configured = {}

    def fake_configure(*, api_key):
        configured["api_key"] = api_key

    monkeypatch.setattr(response_search.genai, "configure", fake_configure)
    monkeypatch.setattr(response_search.genai, "GenerativeModel", SearchGroundingModel)

    result = asyncio.run(
        response_search.perform_response_search("How has AMD's server market share changed recently?")
    )

    assert configured["api_key"] == "grounding-key"
    assert result.snippets, "Expected snippets parsed from searchGrounding entries"

    snippet = result.snippets[0]
    assert snippet.snippet.startswith("IDC reports AMD")
    assert snippet.url == "https://example.com/amd-share"
    assert snippet.display_url == "example.com"
    assert snippet.annotation and snippet.annotation.get('entry_id') == 'entry-1'
    assert any(ann.get('id') == 'entry-1' for ann in result.annotations)
    assert "Grounded answer summary" in (result.summary or "")
    assert result.model == "gemini-grounding"

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
                    "candidates": [
                        {
                            "content": {"parts": [{"text": "Synthesized snippet"}]},
                            "groundingMetadata": {
                                "groundingSupports": [
                                    {
                                        "segment": {"text": "Synthesized snippet"},
                                        "groundingChunkIndices": [0],
                                        "title": "NVDA revenue analysis",
                                    }
                                ],
                                "groundingChunks": [
                                    {
                                        "web": {
                                            "uri": "https://example.com/nvda-outlook",
                                            "title": "NVDA revenue analysis",
                                            "displayUri": "example.com",
                                            "publishedDate": "2025-10-02",
                                        }
                                    }
                                ],
                            },
                        }
                    ],
                }
            return {"text": '{"topics":[{"label":"Primary question","query":"NVDA 2025 revenue outlook","reason":"Company view"},{"label":"Industry context","query":"Semiconductor industry trends 2025","reason":"Sector backdrop"}]}' }

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
    assert len(instance.calls) == len(result.search_topics) + 1

    plan_call = instance.calls[0]
    assert 'tools' not in plan_call
    plan_prompt = plan_call['contents'][0]['parts'][0]['text']
    assert 'User question: Tell me about "NVDA 2025" revenue outlook?' in plan_prompt

    search_calls = instance.calls[1:]
    for call, topic in zip(search_calls, result.search_topics):
        tools = call.get("tools")
        assert isinstance(tools, list) and len(tools) > 0
        assert isinstance(tools[0], dict) and 'google_search' in tools[0]
        prompt_text = call["contents"][0]
        assert topic in prompt_text

    assert result.topics and result.topics[0].summary == "Synthesized search answer"
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
                            "groundingMetadata": {
                                "groundingSupports": [
                                    {
                                        "segment": {"text": "AMD reports record data center momentum."},
                                        "groundingChunkIndices": [0],
                                        "title": "AMD MI300 demand surges",
                                    }
                                ],
                                "groundingChunks": [
                                    {
                                        "web": {
                                            "uri": "https://example.com/amd-mi300",
                                            "title": "AMD MI300 demand surges",
                                            "displayUri": "example.com",
                                            "publishedDate": "2025-09-28",
                                        }
                                    }
                                ],
                            },
                        }
                    ],
                }
            return {"text": '{"topics":[{"label":"Primary question","query":"Latest AMD data center news","reason":"Company focus"},{"label":"Industry context","query":"Semiconductor AI market 2025","reason":"Sector update"}]}' }

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
    assert step1.search_topics[0].startswith("Latest AMD data center news")
    assert step1.session_id == "session-amd"

    assert step2.step == "response_search.step2"
    assert step2.phase == "search"
    assert step2.session_id == "session-amd"
    assert step2.search_topics[0].startswith("Latest AMD data center news")
    assert step2.snippets == len(result.snippets)
    assert step2.summary_present == bool(result.summary)
    assert step2.latency_ms == result.latency_ms

    assert caplog.records.index(step1) < caplog.records.index(step2)

    assert result.topics and result.topics[0].summary == "AMD expands MI300 deployments across hyperscalers"
    assert result.snippets
    assert result.model == "gemini-amd-news"



def test_default_model_guardrail(monkeypatch):
    DummyGenerativeModel.created_instances = []
    monkeypatch.delenv("GEMINI_SEARCH_MODEL", raising=False)
    monkeypatch.setenv("GEMINI_API_KEY", "guardrail-key")
    monkeypatch.setattr(response_search.genai, "configure", lambda **kwargs: None)
    monkeypatch.setattr(response_search.genai, "GenerativeModel", DummyGenerativeModel)

    result = asyncio.run(response_search.perform_response_search("Do guardrails use flash lite by default?"))

    assert result.model == "gemini-2.5-flash-lite"
    assert DummyGenerativeModel.created_instances
    assert DummyGenerativeModel.created_instances[0].model_name == "gemini-2.5-flash-lite"
