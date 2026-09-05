"""Classical BaZi text corpus loader and deterministic retrieval."""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections import Counter
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


def _stable_id(*parts: str) -> str:
    digest = hashlib.md5("|".join(parts).encode("utf-8")).hexdigest()[:8]
    return f"ref_{digest}"


def _tokenize(text: str) -> list[str]:
    # Split snake-case tags and Chinese into overlapping bigrams; hash vectors
    # conflated unrelated terms and treated whole Chinese sentences as tokens.
    stop = {"the", "a", "an", "and", "or", "of", "to", "in", "is", "it", "for", "my", "i", "with", "your",
            "will", "what", "how", "can", "should", "this", "that", "its", "their", "they", "be", "are", "new"}
    tokens = re.findall(r"[a-z0-9]+", text.lower())
    for run in re.findall(r"[\u3400-\u9fff]+", text):
        tokens.extend(run[i:i + 2] for i in range(max(1, len(run) - 1)))
    return [token for token in tokens if token not in stop]


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
def load_classics_index() -> tuple[tuple[ClassicalPassage, Counter], ...]:
    return tuple(
        (p, Counter(_tokenize(" ".join([p.passage, p.translation, p.source, *p.tags]))))
        for p in load_classics_corpus()
    )


def retrieve_classical_references(
    query: str, limit: int | None = None,
) -> list[dict[str, Any]]:
    """Exact lexical BM25 retrieval over the local Bazi corpus, with tag boosts.

    No positive match means no reference. Never pad with irrelevant citations.
    """
    settings = get_settings()
    target_limit = max(1, min(limit or settings.max_classical_references, 5))
    index = load_classics_index()
    terms = set(_tokenize(query))
    if terms & {"career", "role", "job", "work", "promotion"}:
        terms.update({"career", "authority", "officer"})
    requested_stems = terms & set("jia yi bing ding wu ji geng xin ren gui".split())
    if not index or not terms:
        return []
    count = len(index)
    avg_len = sum(sum(freq.values()) for _, freq in index) / count
    doc_freq = {term: sum(term in freq for _, freq in index) for term in terms}
    ranked = []
    for passage, freq in index:
        passage_stems = set(passage.tags) & set("jia yi bing ding wu ji geng xin ren gui".split())
        if requested_stems and passage_stems and not requested_stems & passage_stems:
            continue
        if "career" in terms and set(passage.tags) & {"children", "health", "illness", "romance", "marriage"}:
            continue
        matched = sorted(terms & freq.keys())
        score = 0.0
        tags = set(_tokenize(" ".join(passage.tags)))
        for term in matched:
            idf = math.log(1 + (count - doc_freq[term] + 0.5) / (doc_freq[term] + 0.5))
            tf = freq[term]
            score += idf * tf * 2.2 / (tf + 1.2 * (0.25 + 0.75 * sum(freq.values()) / avg_len))
            if term in tags:
                score += idf
        if score > 0:
            ranked.append((score, passage, matched))
    ranked.sort(key=lambda item: (-item[0], item[1].id))
    return [
        {
            "id": p.id, "passage": p.passage, "translation": p.translation,
            "source": p.source,
            "relevance": f"Bazi corpus; matched terms: {', '.join(matched)}; BM25 {score:.3f}",
        }
        for score, p, matched in ranked[:target_limit]
    ]


retrieve_classical_references_tool = function_tool(
    retrieve_classical_references,
    name_override="retrieve_classical_references",
    description_override=(
        "Retrieve relevant classical Chinese BaZi passages with translations "
        "and source metadata, ranked by relevance to the query."
    ),
)
