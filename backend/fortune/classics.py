"""Classical BaZi text corpus loader and deterministic retrieval."""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Sequence

from agents import function_tool
from pydantic import BaseModel, Field

try:
    from .config import get_settings
except ImportError:
    from config import get_settings  # type: ignore[no-redef]


class ClassicalPassage(BaseModel):
    id: str
    passage: str
    translation: str
    source: str
    tags: list[str] = Field(default_factory=list)


@dataclass(frozen=True)
class IndexedClassicalPassage:
    passage: ClassicalPassage
    vector: tuple[float, ...]


def _stable_id(*parts: str) -> str:
    digest = hashlib.md5("|".join(parts).encode("utf-8")).hexdigest()[:8]
    return f"ref_{digest}"


def _tokenize(text: str) -> list[str]:
    normalized = "".join(ch.lower() if ch.isalnum() else " " for ch in text)
    return [t for t in normalized.split() if t]


def _hash_embed(text: str, dims: int = 64) -> list[float]:
    vec = [0.0] * dims
    for token in _tokenize(text):
        digest = hashlib.md5(token.encode("utf-8")).hexdigest()
        slot = int(digest[:8], 16) % dims
        sign = -1.0 if int(digest[8:10], 16) % 2 else 1.0
        vec[slot] += sign
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]


def _cosine(a: Sequence[float], b: Sequence[float]) -> float:
    return sum(x * y for x, y in zip(a, b, strict=False))


@lru_cache(maxsize=1)
def load_classics_corpus() -> list[ClassicalPassage]:
    settings = get_settings()
    path = Path(settings.classics_corpus_path)
    raw_items = json.loads(path.read_text(encoding="utf-8"))
    return [
        ClassicalPassage(
            id=item.get("id") or _stable_id(item["source"], item["passage"]),
            passage=item["passage"],
            translation=item["translation"],
            source=item["source"],
            tags=item.get("tags", []),
        )
        for item in raw_items
    ]


@lru_cache(maxsize=1)
def load_classics_index() -> tuple[IndexedClassicalPassage, ...]:
    index: list[IndexedClassicalPassage] = []
    for passage in load_classics_corpus():
        joined = " ".join([
            passage.passage,
            passage.translation,
            passage.source,
            *passage.tags,
        ])
        index.append(
            IndexedClassicalPassage(
                passage=passage,
                vector=tuple(_hash_embed(joined)),
            )
        )
    return tuple(index)


def retrieve_classical_references(
    query: str,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    """Retrieve relevant classical passages via hash-based cosine similarity.

    Plain callable for direct import/testing. The Agents SDK wrapper is
    exposed separately as ``retrieve_classical_references_tool``.
    """
    settings = get_settings()
    target_limit = limit or settings.max_classical_references
    query_vec = _hash_embed(query)

    ranked: list[tuple[float, ClassicalPassage]] = []
    for item in load_classics_index():
        score = _cosine(query_vec, item.vector)
        ranked.append((score, item.passage))

    ranked.sort(key=lambda item: item[0], reverse=True)
    return [
        {
            "id": p.id,
            "passage": p.passage,
            "translation": p.translation,
            "source": p.source,
            "relevance": f"Cosine similarity {score:.3f} against query: {query[:60]}",
        }
        for score, p in ranked[:target_limit]
    ]


retrieve_classical_references_tool = function_tool(
    retrieve_classical_references,
    name_override="retrieve_classical_references",
    description_override=(
        "Retrieve relevant classical Chinese BaZi passages with translations "
        "and source metadata, ranked by relevance to the query."
    ),
)
