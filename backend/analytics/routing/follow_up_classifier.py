# --- Analytics Function/Class Map ---
# Class: FollowUpRoute
#   Role: Handles FollowUpRoute logic for analytics.routing.follow_up_classifier.
#   Called from: analytics.flows.multi_agent, analytics.flows.planner.revision, analytics.flows.planner_executor, analytics.flows.single_agent_tools, +16 more
#   Collaborators: Internal helpers only
#   Why: Keeps analytics.routing.follow_up_classifier from duplicating FollowUpRoute behavior across flows.
# Function: _contains_any
#   Role: Handles contains any logic for analytics.routing.follow_up_classifier.
#   Called from: Internal to analytics.routing.follow_up_classifier
#   Invokes: Internal helpers only
#   Why: Keeps analytics.routing.follow_up_classifier from duplicating contains any behavior across flows.
# Class: FollowUpClassifier
#   Role: Handles FollowUpClassifier logic for analytics.routing.follow_up_classifier.
#   Called from: analytics.flows.workflow, analytics.routing, tests.analytics.test_follow_up_classifier, tests.analytics.test_revision_followups, +1 more
#   Collaborators: analytics.routing.follow_up_classifier._contains_any
#   Why: Keeps analytics.routing.follow_up_classifier from duplicating FollowUpClassifier behavior across flows.
# --- End Analytics Function/Class Map ---
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable, Mapping, Optional

from analytics.core.session_state import SessionStateSnapshot, chart_spec_has_numeric_payload


class FollowUpRoute(str, Enum):
    STOCK_ONLY = "stock_only"
    REUSE_SQL = "reuse_sql"
    FULL_PIPELINE = "full_pipeline"
    CHART_ONLY = "chart_only"
    NARRATIVE_ONLY = "narrative_only"


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

    def classify(
        self,
        query: str,
        snapshot: Optional[SessionStateSnapshot],
        lane_readiness: Optional[Mapping[str, bool]] = None,
    ) -> FollowUpRoute:
        normalized_query = (query or "").strip().lower()
        if not normalized_query:
            return FollowUpRoute.FULL_PIPELINE
        if lane_readiness is not None:
            has_sql = bool(lane_readiness.get("sql"))
            has_chart = bool(lane_readiness.get("chart"))
        else:
            has_sql = bool(snapshot and snapshot.last_sql) or self._stage_seen(snapshot, "sql")
            has_chart = bool(snapshot and snapshot.last_chart_spec) or self._stage_seen(snapshot, "chart")
        if has_sql and _contains_any(normalized_query, self.stock_keywords):
            return FollowUpRoute.STOCK_ONLY
        if has_chart and has_sql and _contains_any(normalized_query, self.chart_keywords):
            return FollowUpRoute.REUSE_SQL
        return FollowUpRoute.FULL_PIPELINE

    def _lanes_available(self, snapshot: Optional[SessionStateSnapshot]) -> set[str]:
        if snapshot is None:
            return set()
        lanes: set[str] = set()
        artifacts = ((snapshot.tool_cache or {}).get("analytics") or {}).get("artifacts") or {}

        if snapshot.last_sql or artifacts.get("sql_generation") or self._stage_seen(snapshot, "sql"):
            lanes.add("sql")
        chart_artifact = artifacts.get("chart")
        chart_ready = chart_spec_has_numeric_payload(snapshot.last_chart_spec)
        if not chart_ready and isinstance(chart_artifact, dict):
            candidate = chart_artifact.get("chart_spec") or chart_artifact.get("spec") or chart_artifact
            chart_ready = chart_spec_has_numeric_payload(candidate)
        if chart_ready or self._stage_seen(snapshot, "chart"):
            lanes.add("chart")
        if snapshot.last_analysis or artifacts.get("analysis") or self._stage_seen(snapshot, "analysis"):
            lanes.add("analysis")
        if artifacts.get("market") or self._stage_seen(snapshot, "hedged_accessories"):
            lanes.add("market")
        if artifacts.get("web") or self._stage_seen(snapshot, "hedged_accessories"):
            lanes.add("web")
        return lanes

    def detect_revision_targets(
        self,
        query: str,
        snapshot: Optional[SessionStateSnapshot] = None,
        lane_readiness: Optional[Mapping[str, bool]] = None,
    ) -> set[str]:
        normalized_query = (query or "").strip().lower()
        if not normalized_query or snapshot is None:
            return set()
        lanes: set[str] = set()
        if _contains_any(normalized_query, self.stock_keywords):
            lanes.add("stock")
        if _contains_any(normalized_query, self.market_keywords):
            lanes.add("market")
        if _contains_any(normalized_query, self.web_keywords):
            lanes.add("web")
        if _contains_any(normalized_query, self.chart_keywords):
            lanes.add("chart")
        if _contains_any(normalized_query, self.sql_keywords):
            lanes.add("sql")
        if _contains_any(normalized_query, self.analysis_keywords):
            lanes.add("analysis")
        if lane_readiness is not None:
            available = {lane for lane, ready in lane_readiness.items() if ready}
        else:
            available = self._lanes_available(snapshot)
        requested = {lane for lane in lanes if lane in available}
        if "analysis" in lanes:
            requested.add("analysis")
            requested.add("web")
        return requested
