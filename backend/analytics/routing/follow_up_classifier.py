from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable, Optional

from analytics.core.session_state import SessionStateSnapshot


class FollowUpRoute(str, Enum):
    STOCK_ONLY = "stock_only"
    REUSE_SQL = "reuse_sql"
    FULL_PIPELINE = "full_pipeline"


def _contains_any(text: str, candidates: Iterable[str]) -> bool:
    lowered = text.lower()
    return any(token in lowered for token in candidates)


@dataclass
class FollowUpClassifier:
    stock_keywords: tuple[str, ...] = (
        "stock",
        "share price",
        "price move",
        "trading range",
        "performance last",
        "close price",
    )
    chart_keywords: tuple[str, ...] = (
        "chart",
        "visualize",
        "graph",
        "plot",
        "update chart",
    )
    market_keywords: tuple[str, ...] = (
        "market",
        "competitor",
        "sentiment",
        "headline",
        "chatter",
        "industry news",
        "market research",
    )
    web_keywords: tuple[str, ...] = (
        "web",
        "article",
        "news",
        "press",
        "source",
        "coverage",
    )
    analysis_keywords: tuple[str, ...] = (
        "analysis",
        "summary",
        "narrative",
        "writeup",
    )
    sql_keywords: tuple[str, ...] = (
        "sql",
        "query",
        "dataset",
        "rebuild table",
        "filters",
        "metrics",
        "pivot",
        "visualization",
    )

    def _stage_seen(self, snapshot: Optional[SessionStateSnapshot], stage: str) -> bool:
        if not snapshot:
            return False
        history = getattr(snapshot, "schedule_history", []) or []
        return any((entry.get("stage") == stage) for entry in history)

    def classify(self, query: str, snapshot: Optional[SessionStateSnapshot]) -> FollowUpRoute:
        normalized_query = (query or "").strip().lower()
        if not normalized_query:
            return FollowUpRoute.FULL_PIPELINE
        has_sql = bool(snapshot and snapshot.last_sql) or self._stage_seen(snapshot, "sql")
        has_chart = bool(snapshot and snapshot.last_chart_spec) or self._stage_seen(snapshot, "chart")
        if has_sql and _contains_any(normalized_query, self.stock_keywords):
            return FollowUpRoute.STOCK_ONLY
        if has_chart and has_sql and _contains_any(normalized_query, self.chart_keywords):
            return FollowUpRoute.REUSE_SQL
        return FollowUpRoute.FULL_PIPELINE

    def detect_revision_targets(self, query: str) -> set[str]:
        normalized_query = (query or "").strip().lower()
        if not normalized_query:
            return set()
        lanes: set[str] = set()
        if _contains_any(normalized_query, self.stock_keywords):
            lanes.add("stock")
        if _contains_any(normalized_query, self.market_keywords):
            lanes.add("market")
        if _contains_any(normalized_query, self.web_keywords):
            lanes.add("web")
        if _contains_any(normalized_query, self.chart_keywords) or _contains_any(normalized_query, self.sql_keywords):
            lanes.add("sql")
        if _contains_any(normalized_query, self.analysis_keywords):
            lanes.add("analysis")
        return lanes
