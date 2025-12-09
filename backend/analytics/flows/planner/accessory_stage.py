# --- Analytics Function/Class Map ---
# Function: _accessory_tool_adapters
#   Role: Return tool adapters that supply market and web lanes.
#   Called from: analytics.flows.planner_executor, accessory executor factories
#   Invokes: analytics.flows.tooling.MarketQuestionAdapter, StockTrackerAdapter, WebRetrieverAdapter
#   Why: Centralizes accessory adapter creation.
# Class: _PayloadSearchResultProxy
#   Role: Minimal wrapper so seeded payloads satisfy ResponseSearchResult interface.
#   Called from: _seed_web_search_from_payload
#   Invokes: copy.deepcopy
#   Why: Provides consistent payload access for seeded web results.
# Function: _set_market_artifact
#   Role: Build market artifact from widget payload/errors.
#   Called from: analytics.flows.planner_executor accessory helpers
#   Invokes: analytics.artifacts.MarketArtifact
#   Why: Centralizes market artifact construction.
# Function: _set_web_artifact
#   Role: Build web context artifact from payload/search result.
#   Called from: analytics.flows.planner_executor accessory helpers
#   Invokes: analytics.artifacts.WebContextArtifact
#   Why: Centralizes web artifact construction.
# Function: _seed_web_search_from_payload
#   Role: Seed web search result into context and artifact.
#   Called from: analytics.flows.planner_executor accessory helpers
#   Invokes: analytics.validators.sanitize_for_json, _PayloadSearchResultProxy, _set_web_artifact
#   Why: Enables cached web payload reuse across revisions.
# Function: _seed_stock_widget_from_payload
#   Role: Seed stock widget payload into market artifact.
#   Called from: analytics.flows.planner_executor accessory helpers
#   Invokes: _set_market_artifact
#   Why: Enables cached market payload reuse across revisions.
# Function: run_web_stage
#   Role: Stream the web accessory lane using PlannerPipeline refresh logic (TTL + receipts).
#   Called from: analytics.flows.lane_executors.create_accessory_executor, analytics.flows.pipeline_orchestrator.build_pipeline_lane_executors
#   Invokes: PlannerPipeline.refresh_web_lane
#   Why: Provides a self-contained web lane runner for executor factories and sequencer proxies.
# Function: run_market_stage
#   Role: Stream the market accessory lane using PlannerPipeline refresh logic (TTL + receipts).
#   Called from: analytics.flows.lane_executors.create_accessory_executor, analytics.flows.pipeline_orchestrator.build_pipeline_lane_executors
#   Invokes: PlannerPipeline.refresh_market_lane
#   Why: Centralizes market lane execution so accessory executors avoid orchestrator passthroughs.
# --- End Analytics Function/Class Map ---
from __future__ import annotations

import copy
from typing import Any, AsyncGenerator, Dict, Optional, Tuple

from analytics.artifacts import MarketArtifact, WebContextArtifact
from analytics.validators import sanitize_for_json
from ..tooling import MarketQuestionAdapter, StockTrackerAdapter, WebRetrieverAdapter


def _accessory_tool_adapters() -> Tuple[Any, ...]:
    """Return tool adapters that supply market and web lanes."""
    return (
        MarketQuestionAdapter("market_question_a", "Market Research Question A"),
        MarketQuestionAdapter("market_question_b", "Market Research Question B"),
        StockTrackerAdapter(),
        WebRetrieverAdapter(),
    )


class _PayloadSearchResultProxy:
    """Minimal wrapper so seeded payloads satisfy the ResponseSearchResult interface."""

    def __init__(self, payload: Dict[str, Any]) -> None:
        self._payload = copy.deepcopy(payload)
        self.summary = self._payload.get("summary")
        self.latency_ms = self._payload.get("latency_ms")

    def to_payload(self) -> Dict[str, Any]:
        return copy.deepcopy(self._payload)


def _set_market_artifact(
    ctx: Any,
    *,
    widget: Optional[Dict[str, Any]] = None,
    error: Optional[str] = None,
    error_code: Optional[str] = None,
) -> None:
    tickers: list[str] = []
    snapshot: Optional[Dict[str, Any]] = None
    if isinstance(widget, dict):
        snapshot = widget
        symbols = widget.get("symbols")
        if isinstance(symbols, list):
            tickers = [str(symbol).strip() for symbol in symbols if isinstance(symbol, str) and symbol.strip()]
    ctx.artifacts.market = MarketArtifact(
        query=ctx.query,
        tickers=tickers,
        snapshot=snapshot,
        error=error,
        error_code=error_code,
    )


def _set_web_artifact(
    ctx: Any,
    *,
    payload: Dict[str, Any],
    topic: Optional[str],
    search_result: Optional[Any],
) -> None:
    metadata = {}
    if search_result is not None:
        metadata = dict(getattr(search_result, "metadata", {}) or {})
    ctx.artifacts.web = WebContextArtifact(
        query=ctx.query,
        summary=payload.get("summary"),
        snippets=list(payload.get("snippets") or []),
        search_id=payload.get("search_id"),
        from_cache=payload.get("from_cache"),
        metadata=metadata,
        topic=topic,
        latency_stats=payload.get("latency_stats"),
    )


def _seed_web_search_from_payload(ctx: Any, payload: Dict[str, Any]) -> None:
    if not isinstance(payload, dict):
        return
    sanitized_payload = sanitize_for_json(payload)
    ctx.web_search = _PayloadSearchResultProxy(sanitized_payload)
    ctx.web_search_seeded = True
    if sanitized_payload.get("from_cache"):
        ctx.reused_web = True
    topic = sanitized_payload.get("topic") or sanitized_payload.get("search_topic")
    _set_web_artifact(ctx, payload=sanitized_payload, topic=topic, search_result=None)


def _seed_stock_widget_from_payload(ctx: Any, payload: Dict[str, Any]) -> None:
    if not isinstance(payload, dict):
        return
    widget_payload = payload.get("stock_widget")
    if not isinstance(widget_payload, dict):
        if not payload.get("ready"):
            return
        return
    sanitized_widget = sanitize_for_json(widget_payload)
    ctx.stock_widget_seeded = True
    ctx.reused_stock = ctx.reused_stock or bool(payload.get("from_cache"))
    _set_market_artifact(
        ctx,
        widget=sanitized_widget,
        error=payload.get("error"),
        error_code=payload.get("error_code"),
    )


async def run_web_stage(
    pipeline: Any,
    *,
    ctx: Any,
    reason: Optional[str] = None,
    source: Optional[str] = None,
) -> AsyncGenerator[Dict[str, Any], None]:
    """Refresh the web lane using planner accessory logic."""

    async for event in pipeline.refresh_web_lane(
        ctx,
        reason=reason,
        source=source,
    ):
        yield event


async def run_market_stage(
    pipeline: Any,
    *,
    ctx: Any,
    reason: Optional[str] = None,
    source: Optional[str] = None,
) -> AsyncGenerator[Dict[str, Any], None]:
    """Refresh the market lane using planner accessory logic."""

    async for event in pipeline.refresh_market_lane(
        ctx,
        reason=reason,
        source=source,
    ):
        yield event
