from __future__ import annotations

import asyncio
import os
import time
from pathlib import Path
from typing import Any, Sequence

from dotenv import load_dotenv

try:
    from google import genai as google_genai  # type: ignore
    from google.genai import types as genai_types  # type: ignore
except ImportError:  # pragma: no cover - optional dependency in local shells
    google_genai = None  # type: ignore
    genai_types = None  # type: ignore


env_path = Path(__file__).resolve().parents[1] / ".env"
load_dotenv(dotenv_path=env_path, override=False)

EMBEDDING_MODEL = "gemini-embedding-001"
STORED_DIMENSIONS = 768

_client: Any | None = None


class EmbeddingUnavailable(RuntimeError):
    """Raised when Gemini embeddings cannot be generated."""


def _api_key() -> str:
    key = (
        os.getenv("GEMINI_API_KEY_Primary")
        or os.getenv("GEMINI_API_KEY")
        or os.getenv("GOOGLE_API_KEY")
    )
    if not key:
        raise EmbeddingUnavailable("Gemini API key is not configured")
    return key


def _client_instance() -> Any:
    global _client
    if google_genai is None or genai_types is None:
        raise EmbeddingUnavailable("google-genai is not installed")
    if _client is None:
        _client = google_genai.Client(api_key=_api_key())
    return _client


def _extract_values(response: Any) -> list[float]:
    embeddings = getattr(response, "embeddings", None)
    if embeddings:
        first = embeddings[0]
        values = getattr(first, "values", None)
        if values:
            return [float(v) for v in values]

    embedding = getattr(response, "embedding", None)
    if embedding is not None:
        values = getattr(embedding, "values", None)
        if values:
            return [float(v) for v in values]

    for attr in ("to_dict", "model_dump"):
        fn = getattr(response, attr, None)
        if not callable(fn):
            continue
        try:
            payload = fn()
        except Exception:
            continue
        if not isinstance(payload, dict):
            continue
        raw_embeddings = payload.get("embeddings")
        if isinstance(raw_embeddings, list) and raw_embeddings:
            raw_values = raw_embeddings[0].get("values") if isinstance(raw_embeddings[0], dict) else None
            if isinstance(raw_values, list):
                return [float(v) for v in raw_values]
        raw_embedding = payload.get("embedding")
        if isinstance(raw_embedding, dict):
            raw_values = raw_embedding.get("values")
            if isinstance(raw_values, list):
                return [float(v) for v in raw_values]

    raise EmbeddingUnavailable("Gemini embedding response did not contain values")


def _extract_many_values(response: Any) -> list[list[float]]:
    embeddings = getattr(response, "embeddings", None)
    if embeddings:
        rows: list[list[float]] = []
        for embedding in embeddings:
            values = getattr(embedding, "values", None)
            if not values:
                raise EmbeddingUnavailable("Gemini batch embedding row is empty")
            rows.append([float(v) for v in values[:STORED_DIMENSIONS]])
        return rows

    for attr in ("to_dict", "model_dump"):
        fn = getattr(response, attr, None)
        if not callable(fn):
            continue
        try:
            payload = fn()
        except Exception:
            continue
        if not isinstance(payload, dict):
            continue
        raw_embeddings = payload.get("embeddings")
        if isinstance(raw_embeddings, list):
            rows = []
            for item in raw_embeddings:
                raw_values = item.get("values") if isinstance(item, dict) else None
                if not isinstance(raw_values, list):
                    raise EmbeddingUnavailable("Gemini batch embedding row is malformed")
                rows.append([float(v) for v in raw_values[:STORED_DIMENSIONS]])
            return rows

    values = _extract_values(response)
    return [values[:STORED_DIMENSIONS]]


def embed_text_sync(text: str, *, task_type: str) -> list[float]:
    """Generate one Gemini embedding and store the same 768-dim prefix Homer stores."""
    client = _client_instance()
    config = genai_types.EmbedContentConfig(task_type=task_type)
    response = client.models.embed_content(
        model=EMBEDDING_MODEL,
        contents=text,
        config=config,
    )
    return _extract_values(response)[:STORED_DIMENSIONS]


def embed_texts_sync(texts: Sequence[str], *, task_type: str) -> list[list[float]]:
    client = _client_instance()
    config = genai_types.EmbedContentConfig(task_type=task_type)
    response = client.models.embed_content(
        model=EMBEDDING_MODEL,
        contents=list(texts),
        config=config,
    )
    rows = _extract_many_values(response)
    if len(rows) != len(texts):
        raise EmbeddingUnavailable(f"Gemini returned {len(rows)} embeddings for {len(texts)} texts")
    return rows


async def embed_query(text: str) -> tuple[list[float], int]:
    start = time.perf_counter()
    vector = await asyncio.to_thread(embed_text_sync, text, task_type="RETRIEVAL_QUERY")
    elapsed_ms = int(round((time.perf_counter() - start) * 1000))
    return vector, elapsed_ms
