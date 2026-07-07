from __future__ import annotations

import json
import math
import re
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Sequence


CORPUS_PATH = Path(__file__).resolve().parent / "corpus.json"

# Ranking constants ported from /Users/yj/homer/src/memory/ranking.ts.
RRF_K = 20
SIMILARITY_FLOOR = 0.40
RECENCY_FLOOR = 0.75
RECENCY_HALFLIFE_DAYS = 90
CLAIM_APPROVED_ENTITY_MULTIPLIER = 1.20
# ranking.ts currently uses 1.02 for approved claims without entity hits.
# The task brief listed approved=1.0, but this demo follows the live source.
CLAIM_APPROVED_MULTIPLIER = 1.02
CLAIM_CANDIDATE_MULTIPLIER = 0.90
CLAIM_OTHER_MULTIPLIER = 0.85

DAY_SECONDS = 24 * 60 * 60
TOKEN_RE = re.compile(r"[a-z0-9][a-z0-9_.-]*", re.IGNORECASE)


@dataclass(frozen=True)
class CorpusClaim:
    id: str
    content: str
    claim_type: str
    target: str
    confidence: float
    status: str
    created_at: str
    embedding: tuple[float, ...]

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "CorpusClaim":
        embedding_raw = raw.get("embedding") or []
        return cls(
            id=str(raw["id"]),
            content=str(raw["content"]),
            claim_type=str(raw["claim_type"]),
            target=str(raw["target"]),
            confidence=float(raw["confidence"]),
            status=str(raw["status"]),
            created_at=str(raw["created_at"]),
            embedding=tuple(float(x) for x in embedding_raw),
        )


@dataclass(frozen=True)
class LegResult:
    claim_id: str
    rank: int
    score: float


@dataclass(frozen=True)
class SearchTrace:
    bm25_rank: int | None
    bm25_score: float | None
    vector_rank: int | None
    cosine: float | None
    rrf_score: float
    tier_multiplier: float
    recency_multiplier: float
    final_score: float


@dataclass(frozen=True)
class SearchHit:
    claim: CorpusClaim
    trace: SearchTrace


@dataclass(frozen=True)
class SearchMeta:
    query_embedding_ms: int | None
    legs_used: tuple[str, ...]
    corpus_size: int
    fused_candidates: int
    vector_leg: str


@dataclass(frozen=True)
class SearchResponseData:
    hits: tuple[SearchHit, ...]
    meta: SearchMeta


def tokenize(text: str) -> list[str]:
    return [m.group(0).lower() for m in TOKEN_RE.finditer(text)]


def load_corpus(path: Path = CORPUS_PATH) -> tuple[CorpusClaim, ...]:
    with path.open("r", encoding="utf-8") as fh:
        payload = json.load(fh)
    if not isinstance(payload, list):
        raise ValueError("Homer memory corpus must be a JSON array")
    return tuple(CorpusClaim.from_dict(item) for item in payload)


class BM25Index:
    def __init__(self, claims: Sequence[CorpusClaim], *, k1: float = 1.5, b: float = 0.75) -> None:
        self.claims = tuple(claims)
        self.k1 = k1
        self.b = b
        self._doc_tokens = {claim.id: tokenize(claim.content) for claim in self.claims}
        self._doc_lengths = {claim.id: len(self._doc_tokens[claim.id]) for claim in self.claims}
        self._avgdl = (
            sum(self._doc_lengths.values()) / len(self._doc_lengths)
            if self._doc_lengths
            else 0.0
        )
        df: Counter[str] = Counter()
        for tokens in self._doc_tokens.values():
            df.update(set(tokens))
        self._idf = {
            term: math.log(1 + (len(self.claims) - freq + 0.5) / (freq + 0.5))
            for term, freq in df.items()
        }
        self._term_freqs = {
            claim_id: Counter(tokens)
            for claim_id, tokens in self._doc_tokens.items()
        }

    def search(self, query: str) -> list[LegResult]:
        terms = tokenize(query)
        if not terms:
            return []
        unique_terms = set(terms)
        scored: list[LegResult] = []
        for claim in self.claims:
            score = 0.0
            doc_len = self._doc_lengths.get(claim.id, 0)
            if doc_len == 0 or self._avgdl <= 0:
                continue
            term_freq = self._term_freqs[claim.id]
            for term in unique_terms:
                freq = term_freq.get(term, 0)
                if freq <= 0:
                    continue
                numerator = freq * (self.k1 + 1)
                denominator = freq + self.k1 * (1 - self.b + self.b * doc_len / self._avgdl)
                score += self._idf.get(term, 0.0) * numerator / denominator
            if score > 0:
                scored.append(LegResult(claim_id=claim.id, rank=0, score=score))
        scored.sort(key=lambda r: (-r.score, r.claim_id))
        return [LegResult(claim_id=r.claim_id, rank=idx + 1, score=r.score) for idx, r in enumerate(scored)]


def cosine_similarity(a: Sequence[float], b: Sequence[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = 0.0
    norm_a = 0.0
    norm_b = 0.0
    for av, bv in zip(a, b):
        dot += av * bv
        norm_a += av * av
        norm_b += bv * bv
    denominator = math.sqrt(norm_a) * math.sqrt(norm_b)
    return 0.0 if denominator == 0 else dot / denominator


def vector_search(claims: Sequence[CorpusClaim], query_embedding: Sequence[float]) -> list[LegResult]:
    scored: list[LegResult] = []
    for claim in claims:
        if not claim.embedding:
            continue
        cosine = cosine_similarity(query_embedding, claim.embedding)
        if cosine >= SIMILARITY_FLOOR:
            scored.append(LegResult(claim_id=claim.id, rank=0, score=cosine))
    scored.sort(key=lambda r: (-r.score, r.claim_id))
    return [LegResult(claim_id=r.claim_id, rank=idx + 1, score=r.score) for idx, r in enumerate(scored)]


def extract_query_entities(query: str) -> tuple[str, ...]:
    entities: list[str] = []
    for phrase in re.findall(r'"([^"]+)"', query):
        cleaned = phrase.strip().lower()
        if cleaned:
            entities.append(cleaned)
    for token in query.split():
        cleaned = re.sub(r"[^A-Za-z0-9_-]", "", token)
        if len(cleaned) >= 2 and cleaned[0].isupper():
            entities.append(cleaned.lower())
    return tuple(dict.fromkeys(entities))


def has_entity_hit(claim: CorpusClaim, query_entities: Iterable[str]) -> bool:
    haystack = f"{claim.content} {claim.target} {claim.claim_type}".lower()
    return any(entity in haystack for entity in query_entities)


def claim_tier_multiplier(status: str, entity_hit: bool) -> float:
    if status == "approved":
        return CLAIM_APPROVED_ENTITY_MULTIPLIER if entity_hit else CLAIM_APPROVED_MULTIPLIER
    if status == "candidate":
        return CLAIM_CANDIDATE_MULTIPLIER
    return CLAIM_OTHER_MULTIPLIER


def recency_multiplier(date_value: str | None, now: datetime | None = None) -> float:
    if not date_value:
        return 1.0
    try:
        timestamp = datetime.fromisoformat(date_value.replace("Z", "+00:00"))
    except ValueError:
        return 1.0
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    age_days = max(0.0, (now.timestamp() - timestamp.timestamp()) / DAY_SECONDS)
    return RECENCY_FLOOR + (1 - RECENCY_FLOOR) * math.pow(2, -age_days / RECENCY_HALFLIFE_DAYS)


def fuse_candidates(
    claims: Sequence[CorpusClaim],
    bm25_results: Sequence[LegResult],
    vector_results: Sequence[LegResult],
    *,
    query: str,
    now: datetime | None = None,
) -> list[SearchHit]:
    claims_by_id = {claim.id: claim for claim in claims}
    bm25_by_id = {item.claim_id: item for item in bm25_results}
    vector_by_id = {item.claim_id: item for item in vector_results}
    candidate_ids = sorted(set(bm25_by_id) | set(vector_by_id))
    entities = extract_query_entities(query)

    hits: list[SearchHit] = []
    for claim_id in candidate_ids:
        claim = claims_by_id.get(claim_id)
        if claim is None:
            continue
        bm25 = bm25_by_id.get(claim_id)
        vector = vector_by_id.get(claim_id)
        rrf = 0.0
        if bm25:
            rrf += 1 / (RRF_K + bm25.rank)
        if vector:
            rrf += 1 / (RRF_K + vector.rank)
        tier = claim_tier_multiplier(claim.status, has_entity_hit(claim, entities))
        recency = recency_multiplier(claim.created_at, now)
        final = rrf * tier * recency
        hits.append(
            SearchHit(
                claim=claim,
                trace=SearchTrace(
                    bm25_rank=bm25.rank if bm25 else None,
                    bm25_score=bm25.score if bm25 else None,
                    vector_rank=vector.rank if vector else None,
                    cosine=vector.score if vector else None,
                    rrf_score=rrf,
                    tier_multiplier=tier,
                    recency_multiplier=recency,
                    final_score=final,
                ),
            )
        )
    hits.sort(key=lambda hit: (-hit.trace.final_score, hit.claim.id))
    return hits


def search_memory(
    query: str,
    *,
    claims: Sequence[CorpusClaim],
    query_embedding: Sequence[float] | None,
    query_embedding_ms: int | None,
    vector_unavailable_reason: str | None = None,
    now: datetime | None = None,
    limit: int = 6,
) -> SearchResponseData:
    bm25 = BM25Index(claims).search(query)
    vectors: list[LegResult] = []
    vector_leg = "unavailable"
    if query_embedding is not None and any(claim.embedding for claim in claims):
        vectors = vector_search(claims, query_embedding)
        vector_leg = "available"
    elif vector_unavailable_reason:
        vector_leg = "unavailable"

    hits = fuse_candidates(claims, bm25, vectors, query=query, now=now)
    legs = ["bm25"]
    if vector_leg == "available":
        legs.append("vector")

    return SearchResponseData(
        hits=tuple(hits[:limit]),
        meta=SearchMeta(
            query_embedding_ms=query_embedding_ms,
            legs_used=tuple(legs),
            corpus_size=len(claims),
            fused_candidates=len(hits),
            vector_leg=vector_leg,
        ),
    )


def format_float(value: float | None, digits: int = 6) -> float | None:
    return None if value is None else round(value, digits)


def hit_to_dict(hit: SearchHit) -> dict[str, Any]:
    claim = hit.claim
    trace = hit.trace
    return {
        "id": claim.id,
        "content": claim.content,
        "claim_type": claim.claim_type,
        "target": claim.target,
        "status": claim.status,
        "created_at": claim.created_at,
        "trace": {
            "bm25_rank": trace.bm25_rank,
            "bm25_score": format_float(trace.bm25_score),
            "vector_rank": trace.vector_rank,
            "cosine": format_float(trace.cosine),
            "rrf_score": format_float(trace.rrf_score),
            "tier_multiplier": format_float(trace.tier_multiplier, 4),
            "recency_multiplier": format_float(trace.recency_multiplier, 4),
            "final_score": format_float(trace.final_score),
        },
    }


def response_to_dict(query: str, data: SearchResponseData) -> dict[str, Any]:
    return {
        "query": query,
        "vector_leg": data.meta.vector_leg,
        "results": [hit_to_dict(hit) for hit in data.hits],
        "meta": {
            "query_embedding_ms": data.meta.query_embedding_ms,
            "legs_used": list(data.meta.legs_used),
            "corpus_size": data.meta.corpus_size,
            "fused_candidates": data.meta.fused_candidates,
        },
    }


def build_searcher(
    claims: Sequence[CorpusClaim],
    embed_query: Callable[[str], tuple[Sequence[float], int]],
) -> Callable[[str], dict[str, Any]]:
    def _run(query: str) -> dict[str, Any]:
        try:
            query_embedding, elapsed_ms = embed_query(query)
            data = search_memory(
                query,
                claims=claims,
                query_embedding=query_embedding,
                query_embedding_ms=elapsed_ms,
            )
        except Exception as exc:
            data = search_memory(
                query,
                claims=claims,
                query_embedding=None,
                query_embedding_ms=None,
                vector_unavailable_reason=str(exc),
            )
        return response_to_dict(query, data)

    return _run
