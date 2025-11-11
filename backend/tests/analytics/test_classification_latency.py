from __future__ import annotations

import asyncio
import json
import os
import pathlib
import sys
import time
import uuid
from typing import Any, Dict, List, Optional, Tuple

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[3]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from analytics.core.intent import OffTopicClassifierSchema  # noqa: E402
from analytics.core.intent_impl.detection import classify_query_async  # noqa: E402
import gemini_service  # noqa: E402

CLASSIFICATION_QUERY = "Compare NVIDIA and AMD gross margin trends over the last four quarters."
CURRENT_MODEL = "gpt-5-nano-2025-08-07"
ALT_OPENAI_MODEL = "gpt-4o-mini-2024-07-18"
GEMINI_MODEL = "gemini-2.5-flash-lite"


# Function: _measure_openai_model_latency
#   Called from: test_classification_latency_models
#   Invokes: analytics.core.intent_impl.detection.classify_query_async, time.perf_counter
#   Why: Encapsulates stopwatch logic for OpenAI-backed classifiers so the test stays readable.
async def _measure_openai_model_latency(model_name: str, session_id: str) -> Tuple[float, OffTopicClassifierSchema]:
    start = time.perf_counter()
    classification = await classify_query_async(
        CLASSIFICATION_QUERY,
        session_id=session_id,
        model=model_name,
        reasoning_effort="low",
        provider="openai",
    )
    elapsed_ms = (time.perf_counter() - start) * 1000.0
    return elapsed_ms, classification


# Function: _call_gemini_classifier_payload
#   Called from: _measure_gemini_model_latency
#   Invokes: gemini_service._genai_configure, gemini_service._GenerativeModel.generate_content, json.loads
#   Why: Wraps Gemini Flash Lite function-calling style responses into the schema used for analytics classification.
def _call_gemini_classifier_payload(
    model_name: str,
    query: str,
    session_id: str,
    api_key: str,
) -> Dict[str, Any]:
    gemini_service._genai_configure(api_key=api_key)
    prompt = (
        "You classify enterprise analytics queries. "
        "Return ONLY JSON with keys is_financial_query (bool), confidence (0-1 float), "
        "topic_category (string), polite_decline_message (string or null), suggested_rephrase (string or null).\n"
        f"Session: {session_id}\n"
        f"Query: {query}"
    )
    generation_config = {
        "temperature": 0.1,
        "top_p": 0.8,
        "response_mime_type": "application/json",
        "max_output_tokens": 512,
    }
    generator = gemini_service._GenerativeModel(model_name, generation_config)
    response = generator.generate_content(contents=prompt)
    raw_text: Optional[str]
    if isinstance(response, dict):
        raw_text = response.get("text")  # type: ignore[arg-type]
        if not raw_text:
            raw_text = json.dumps(response)
    else:
        raw_text = str(response)

    try:
        payload = json.loads(raw_text or "{}")
    except json.JSONDecodeError:
        payload = {}

    if not isinstance(payload, dict):
        payload = {}

    payload.setdefault("is_financial_query", False)
    payload.setdefault("confidence", 0.0)
    payload.setdefault("topic_category", "unknown")
    payload.setdefault("polite_decline_message", None)
    payload.setdefault("suggested_rephrase", None)
    payload["model"] = model_name
    payload["session_id"] = session_id
    return payload


# Function: _measure_gemini_model_latency
#   Called from: test_classification_latency_models
#   Invokes: asyncio.to_thread, _call_gemini_classifier_payload, time.perf_counter
#   Why: Provides an async-friendly wrapper for the blocking Gemini Python SDK.
async def _measure_gemini_model_latency(model_name: str, session_id: str, api_key: str) -> Tuple[float, Dict[str, Any]]:
    start = time.perf_counter()
    payload = await asyncio.to_thread(
        _call_gemini_classifier_payload,
        model_name,
        CLASSIFICATION_QUERY,
        session_id,
        api_key,
    )
    elapsed_ms = (time.perf_counter() - start) * 1000.0
    return elapsed_ms, payload


# Function: test_classification_latency_models
#   Called from: pytest (integration bench)
#   Invokes: _measure_openai_model_latency, _measure_gemini_model_latency
#   Why: Documents relative latency for the standard classification query across supported models.
@pytest.mark.asyncio
async def test_classification_latency_models() -> None:
    if not os.getenv("OPENAI_API_KEY"):
        pytest.skip("OPENAI_API_KEY is required to measure OpenAI model latency.")

    if getattr(gemini_service, "google_genai", None) is None:
        pytest.skip("google-genai is not installed; install google-genai to exercise Gemini latency.")

    gemini_api_key = os.getenv("GEMINI_API_KEY")
    if not gemini_api_key:
        pytest.skip("GEMINI_API_KEY is required to measure Gemini model latency.")

    session_seed = uuid.uuid4().hex[:8]
    measurements: List[Dict[str, Any]] = []

    for label, model_name in (
        ("Current (GPT-5 Nano)", CURRENT_MODEL),
        ("GPT-4o Mini (2024-07-18)", ALT_OPENAI_MODEL),
    ):
        elapsed_ms, classification = await _measure_openai_model_latency(model_name, f"{session_seed}-{model_name}")
        measurements.append(
            {
                "label": label,
                "model": model_name,
                "elapsed_ms": elapsed_ms,
                "confidence": getattr(classification, "confidence", None),
                "is_financial": bool(getattr(classification, "is_financial_query", False)),
            }
        )

    gem_elapsed_ms, gem_payload = await _measure_gemini_model_latency(GEMINI_MODEL, f"{session_seed}-{GEMINI_MODEL}", gemini_api_key)
    measurements.append(
        {
            "label": "Gemini Flash 2.5 Lite",
            "model": GEMINI_MODEL,
            "elapsed_ms": gem_elapsed_ms,
            "confidence": gem_payload.get("confidence"),
            "is_financial": bool(gem_payload.get("is_financial_query")),
        }
    )

    assert len(measurements) == 3
    assert all(entry["elapsed_ms"] > 0 for entry in measurements)

    ordered = sorted(measurements, key=lambda entry: entry["elapsed_ms"])
    assert ordered[-1]["elapsed_ms"] >= ordered[0]["elapsed_ms"]

    summary_lines = [
        f"{entry['label']} [{entry['model']}]: {entry['elapsed_ms']:.1f} ms "
        f"(is_financial={entry['is_financial']}, confidence={entry['confidence']})"
        for entry in ordered
    ]
    print("Classification latency snapshot:\n" + "\n".join(summary_lines))
