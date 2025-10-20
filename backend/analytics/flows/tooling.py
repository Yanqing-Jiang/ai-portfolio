from __future__ import annotations

import logging
import asyncio
import contextlib
import copy
import os
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import (
    Any,
    Awaitable,
    Callable,
    Dict,
    List,
    Optional,
    Sequence,
    Set,
    Tuple,
    TYPE_CHECKING,
    AsyncGenerator,
)
import inspect

from analytics.core import telemetry
from analytics.core.events import EventEmitter
from analytics.core.session_state import SessionStateSnapshot, get_session_state_repository
from analytics.services.response_search import ResponseSearchError, perform_response_search, has_search_api_key
from analytics.services.polygon import PolygonMarketDataClient, PolygonError, fetch_daily_snapshot

logger = logging.getLogger(__name__)


if TYPE_CHECKING:  # pragma: no cover - import guard for typing only
    from .planner_executor import PlannerPhaseContext


@dataclass(frozen=True)
class ToolExecutionContext:
    """Context exposed to tool adapters during fan-out."""

    session_id: str
    query: str
    intent: Any
    plan: Any
    template: Optional[Any]
    configs: Dict[str, Any]


@dataclass
class ToolAdapterResult:
    """Normalized result emitted by a tool adapter."""

    name: str
    status: str
    payload: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    elapsed_ms: Optional[int] = None
    fatal: bool = False


class BaseToolAdapter:
    """Minimal async interface each adapter must implement."""

    name: str = "tool"
    display_name: str = "Tool"
    description: str = ""
    preview_only: bool = True
    capabilities: Tuple[str, ...] = ()
    fatal_on_exception: bool = False
    outputs: Tuple[str, ...] = ()

    def get_metadata(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "display_name": self.display_name,
            "description": self.description,
            "preview_only": self.preview_only,
            "capabilities": list(self.capabilities),
            "outputs": list(self.outputs),
        }

    async def execute(self, context: ToolExecutionContext) -> ToolAdapterResult:  # pragma: no cover - interface
        raise NotImplementedError


class _FatalAdapterException(Exception):
    """Signal used to cancel sibling adapters when a fatal error occurs."""

    def __init__(self, result: ToolAdapterResult) -> None:
        super().__init__(result.error or "fatal tool adapter error")
        self.result = result


class ToolTaskGroup:
    """Coordinate tool adapters with bounded concurrency."""

    def __init__(self, adapters: Sequence[BaseToolAdapter], *, concurrency_limit: int = 5) -> None:
        self._adapters: Sequence[BaseToolAdapter] = adapters
        self._semaphore = asyncio.Semaphore(max(1, concurrency_limit))

    async def run(
        self,
        context: ToolExecutionContext,
        *,
        on_result: Optional[Callable[[ToolAdapterResult], Optional[Awaitable[None]]]] = None,
    ) -> List[ToolAdapterResult]:
        results: Dict[int, ToolAdapterResult] = {}

        def _record(index: int, result: ToolAdapterResult) -> None:
            results.setdefault(index, result)

        async def _dispatch_result(index: int, result: ToolAdapterResult) -> None:
            if on_result is None:
                return
            try:
                maybe = on_result(result)
                if inspect.isawaitable(maybe):
                    await maybe
            except Exception:
                logger.exception(
                    "tool_parallelism.result_callback_failed",
                    extra={"adapter_index": index, "adapter": getattr(result, "name", None)},
                )

        async def _runner(index: int, adapter: BaseToolAdapter) -> None:
            adapter_meta = adapter.get_metadata()
            started = datetime.utcnow()
            await self._semaphore.acquire()
            try:
                try:
                    result = await adapter.execute(context)
                except asyncio.CancelledError:
                    cancelled_at = datetime.utcnow()
                    cancel_result = ToolAdapterResult(
                        name=getattr(adapter, "name", f"adapter_{index}"),
                        status="cancelled",
                        payload={},
                        metadata=dict(adapter_meta),
                        error="cancelled due to fatal sibling",
                        started_at=started.isoformat(),
                        completed_at=cancelled_at.isoformat(),
                        elapsed_ms=int((cancelled_at - started).total_seconds() * 1000),
                        fatal=False,
                    )
                    await _dispatch_result(index, cancel_result)
                    _record(index, cancel_result)
                    raise
                except Exception as exc:  # pragma: no cover - defensive fan-out guard
                    fatal = getattr(adapter, 'fatal_on_exception', False)
                    result = ToolAdapterResult(
                        name=getattr(adapter, "name", f"adapter_{index}"),
                        status="error",
                        payload={},
                        metadata=dict(adapter_meta),
                        error=str(exc),
                        fatal=fatal,
                    )
                else:
                    if result.metadata:
                        merged = dict(adapter_meta)
                        merged.update(result.metadata)
                        result.metadata = merged
                    else:
                        result.metadata = dict(adapter_meta)
                    if result.payload is None:
                        result.payload = {}
                completed = datetime.utcnow()
                if result.started_at is None:
                    result.started_at = started.isoformat()
                if result.completed_at is None:
                    result.completed_at = completed.isoformat()
                if result.elapsed_ms is None:
                    result.elapsed_ms = int((completed - started).total_seconds() * 1000)
                await _dispatch_result(index, result)
                _record(index, result)
                if result.status == "error" and result.fatal:
                    raise _FatalAdapterException(result)
            finally:
                self._semaphore.release()

        fatal_detected = False
        try:
            async with asyncio.TaskGroup() as tg:
                for idx, adapter in enumerate(self._adapters):
                    tg.create_task(_runner(idx, adapter))
        except _FatalAdapterException:
            fatal_detected = True
        except Exception:
            raise

        ordered = [results[idx] for idx in sorted(results.keys())]

        # Ensure adapters that never started (e.g., cancelled before acquiring semaphore) appear as cancelled
        if len(ordered) < len(self._adapters):
            synthetic_results: List[ToolAdapterResult] = []
            for idx, adapter in enumerate(self._adapters):
                if idx not in results:
                    synthetic = ToolAdapterResult(
                        name=getattr(adapter, "name", f"adapter_{idx}"),
                        status="cancelled",
                        payload={},
                        metadata=adapter.get_metadata(),
                        error="cancelled before start",
                        fatal=False,
                    )
                    synthetic_results.append(synthetic)
                    _record(idx, synthetic)
                    await _dispatch_result(idx, synthetic)
            ordered = [results[idx] for idx in sorted(results.keys())]

        if fatal_detected:
            # flag results so downstream callers can surface cancellation reason
            for res in ordered:
                if res.status == "cancelled" and res.error == "cancelled due to fatal sibling":
                    res.payload.setdefault("cancelled", True)
        return ordered


# ----------------------------------------------------------------------------
# Default adapter implementations
# ----------------------------------------------------------------------------


class SQLPlannerAdapter(BaseToolAdapter):
    name = "sql_planner"
    display_name = "SQL Planner"
    description = "Preview metrics and comparisons before execution."
    capabilities = ("plan_summary", "telemetry")
    outputs = ("intent", "metrics_count", "comparison", "granularity")

    async def execute(self, context: ToolExecutionContext) -> ToolAdapterResult:
        plan = context.plan
        metrics = getattr(plan, "metrics", []) or []
        comparison = getattr(plan, "comparison", None)
        granularity = getattr(plan, "granularity", None)
        payload = {
            "intent": getattr(context.intent, "intent_key", None),
            "metrics_count": len(metrics),
            "comparison": comparison,
            "granularity": granularity,
        }
        metadata = self.get_metadata()
        metadata["summary"] = f"{len(metrics)} metric{'s' if len(metrics) != 1 else ''} planned"
        metadata["preview_keys"] = list(payload.keys())
        if metrics:
            metadata["sample_metrics"] = metrics[:3]
        return ToolAdapterResult(name=self.name, status="planned", payload=payload, metadata=metadata)


class ChartBuilderAdapter(BaseToolAdapter):
    name = "chart_builder"
    display_name = "Chart Builder"
    description = "Echo chart scaffolding before data arrives."
    capabilities = ("chart_stub", "telemetry")
    outputs = ("group_by", "timeframe")

    async def execute(self, context: ToolExecutionContext) -> ToolAdapterResult:
        plan = context.plan
        fields = {
            "group_by": getattr(plan, "group_by", []),
            "timeframe": getattr(plan, "timeframe", None),
        }
        group_by = fields.get("group_by") or []
        group_count = len(group_by)
        metadata = self.get_metadata()
        metadata["summary"] = f"{group_count} grouping{'s' if group_count != 1 else ''} staged" if group_count else "Awaiting grouping details"
        if fields.get("timeframe"):
            metadata["timeframe"] = fields["timeframe"]
        if group_by:
            metadata["group_by_preview"] = group_by[:3]
        metadata["preview_keys"] = list(fields.keys())
        return ToolAdapterResult(name=self.name, status="awaiting_data", payload=fields, metadata=metadata)



class WebRetrieverAdapter(BaseToolAdapter):
    name = "web_retriever"
    display_name = "Web Search"
    description = "Fetch fresh external context using Gemini (Google Search retrieval)."
    capabilities = ("web_context", "telemetry")
    outputs = ("query_terms", "ready", "summary", "snippets", "search_id", "annotations", "from_cache")
    preview_only = False
    _RECENCY_KEYWORDS = (
        "today",
        "latest",
        "recent",
        "news",
        "headline",
        "update",
        "guidance",
        "filing",
        "quarter",
        "earnings",
        "as of",
        "current",
    )

    async def execute(self, context: ToolExecutionContext) -> ToolAdapterResult:
        query_terms = self._resolve_query_terms(context)
        metadata = self.get_metadata()
        payload: Dict[str, Any] = {"query_terms": query_terms, "ready": False}
        metadata["preview_keys"] = list(payload.keys())
        metadata.setdefault("summary", "Search adapter seeded with query terms.")

        if not query_terms:
            metadata["summary"] = "Waiting for query text before triggering web search."
            metadata["preview_only"] = True
            return ToolAdapterResult(name=self.name, status="queued", payload=payload, metadata=metadata)

        if not has_search_api_key():
            metadata["summary"] = "Web search disabled until GOOGLE_API_KEY or GEMINI_API_KEY is configured."
            metadata["preview_only"] = True
            metadata["error"] = "search_api_missing"
            payload["error"] = "search_api_missing"
            return ToolAdapterResult(name=self.name, status="skip", payload=payload, metadata=metadata)

        repository = get_session_state_repository()
        snapshot = await repository.load(context.session_id)
        if snapshot is None:
            snapshot = SessionStateSnapshot(session_id=context.session_id)

        cached_payload = self._maybe_get_cached(snapshot, query_terms)
        if cached_payload:
            metadata["summary"] = cached_payload.get("summary") or metadata.get("summary")
            metadata["cache_hit"] = True
            metadata["preview_only"] = False
            metadata["snippets_count"] = len(cached_payload.get("snippets") or [])
            payload.update(cached_payload)
            payload["query_terms"] = query_terms
            payload["ready"] = True
            payload.setdefault("from_cache", True)
            metadata["preview_keys"] = list(payload.keys())
            return ToolAdapterResult(name=self.name, status="completed", payload=payload, metadata=metadata)

        if not self._should_refresh(query_terms, snapshot):
            metadata["summary"] = "Web search will run when the user requests the latest context."
            metadata["preview_only"] = True
            metadata["cache_hit"] = False
            return ToolAdapterResult(name=self.name, status="queued", payload=payload, metadata=metadata)

        try:
            search_result = await perform_response_search(
                query_terms,
                session_id=context.session_id,
                context=self._build_context(context),
            )
        except ResponseSearchError as exc:
            error_stage = getattr(exc, "stage", "unknown")
            metadata["summary"] = "Web search unavailable (Gemini search error)."
            metadata["preview_only"] = True
            metadata["error"] = str(exc)
            metadata["error_stage"] = error_stage
            payload["error"] = str(exc)
            payload["error_stage"] = error_stage
            existing_keys = metadata.get("preview_keys", list(payload.keys()))
            metadata["preview_keys"] = list(dict.fromkeys(list(existing_keys) + list(payload.keys())))
            logger.warning("WebRetrieverAdapter search failed during %s: %s", error_stage, exc)
            return ToolAdapterResult(
                name=self.name,
                status="error",
                payload=payload,
                metadata=metadata,
                error=str(exc),
            )

        result_payload = search_result.to_payload()
        result_payload["query_terms"] = query_terms
        result_payload["ready"] = True
        result_payload["from_cache"] = False
        payload.update(result_payload)
        metadata["summary"] = search_result.summary or "Web search results ready."
        metadata["preview_only"] = False
        metadata["snippets_count"] = len(result_payload.get("snippets") or [])
        metadata["latency_ms"] = search_result.latency_ms
        metadata["search_id"] = search_result.search_id
        metadata["provider"] = "Gemini"
        if getattr(search_result, "model", None):
            metadata["model"] = search_result.model
        metadata["preview_keys"] = list(payload.keys())

        cache_payload = dict(result_payload)
        cache_payload["query"] = query_terms
        snapshot.record_tool_result("web_search", cache_payload)
        await repository.save(snapshot)

        return ToolAdapterResult(name=self.name, status="completed", payload=payload, metadata=metadata)

    def _resolve_query_terms(self, context: ToolExecutionContext) -> str:
        slots = getattr(context.intent, "slots_detected", {}) or {}
        return str(slots.get("original_query") or context.query or "").strip()

    def _maybe_get_cached(self, snapshot: SessionStateSnapshot, query_terms: str) -> Optional[Dict[str, Any]]:
        cache = (snapshot.tool_cache or {}).get("web_search") if snapshot else None
        if not cache:
            return None
        cached_query = str(cache.get("query") or cache.get("query_terms") or "").strip().lower()
        if cached_query and cached_query == query_terms.strip().lower():
            cached = dict(cache)
            cached["from_cache"] = True
            cached.setdefault("ready", True)
            return cached
        return None

    def _should_refresh(self, query_terms: str, snapshot: Optional[SessionStateSnapshot]) -> bool:
        normalized = query_terms.strip().lower()
        if any(keyword in normalized for keyword in self._RECENCY_KEYWORDS):
            return True
        if snapshot is None:
            return True
        cache = snapshot.tool_cache.get("web_search") if snapshot.tool_cache else None
        if not cache:
            return True
        cached_query = str(cache.get("query") or cache.get("query_terms") or "").strip().lower()
        if cached_query and cached_query != normalized:
            return True
        return False

    def _build_context(self, context: ToolExecutionContext) -> Optional[str]:
        intent = getattr(context.intent, "intent_key", None)
        plan = context.plan
        metrics = []
        if plan is not None:
            metrics = list(getattr(plan, "metrics", []) or [])
        parts: List[str] = []
        if intent:
            parts.append(f"Intent: {intent}.")
        if metrics:
            parts.append("Focus metrics: " + ", ".join(metrics[:3]))
        configs = context.configs if isinstance(context.configs, dict) else {}
        assumptions = configs.get("assumptions")
        if isinstance(assumptions, list) and assumptions:
            parts.append("Assumptions: " + "; ".join(str(item) for item in assumptions[:2]))
        return " ".join(parts) if parts else None


class StockTrackerAdapter(BaseToolAdapter):
    name = "stock_tracker"
    display_name = "Stock Tracker"
    description = "Fetch live stock snapshots for planner tickers."
    capabilities = ("market_data", "telemetry")
    outputs = ("tickers", "ready", "insights", "bars", "stock_widget")

    _TICKER_BLACKLIST = {"WITH", "FROM", "AND", "THE", "WHERE", "SELECT", "JOIN"}

    async def execute(self, context: ToolExecutionContext) -> ToolAdapterResult:
        slots = getattr(context.intent, "slots_detected", {}) or {}
        query = (context.query or "").strip()

        def _normalize_candidates(raw: Any) -> List[str]:
            ordered: List[str] = []
            candidates: List[str] = []
            if isinstance(raw, str):
                candidates.append(raw)
            elif isinstance(raw, (list, tuple, set)):
                candidates.extend(str(item) for item in raw)
            deduped: List[str] = []
            for item in candidates:
                symbol = str(item).strip().upper()
                if symbol and symbol not in deduped:
                    deduped.append(symbol)
            if query:
                for match in re.finditer(r"[A-Za-z0-9\.]{2,6}", query):
                    token = match.group(0).strip().upper()
                    if token in deduped and token not in ordered:
                        ordered.append(token)
            for symbol in deduped:
                if symbol not in ordered:
                    ordered.append(symbol)
            return ordered

        tickers: List[str] = _normalize_candidates(slots.get("company"))
        if not tickers:
            tickers = _normalize_candidates(slots.get("tickers"))

        if not tickers and query:
            inferred: List[str] = []
            seen: Set[str] = set()
            for match in re.finditer(r"\b[A-Z]{2,5}\b", query):
                token = match.group(0).upper()
                if token not in self._TICKER_BLACKLIST and token not in seen:
                    inferred.append(token)
                    seen.add(token)
            tickers = inferred[:3]
        payload: Dict[str, Any] = {
            "tickers": tickers,
            "ready": False,
        }
        metadata = self.get_metadata()
        metadata["preview_keys"] = list(payload.keys())

        widget_symbols: List[List[str]] = []
        for raw in tickers:
            symbol = raw.upper()
            if ":" in symbol:
                base, alias = symbol.split(":", 1)
                widget_symbols.append([symbol, alias or base])
            else:
                widget_symbols.append([f"NASDAQ:{symbol}", symbol])
        widget_config: Optional[Dict[str, Any]] = None
        if widget_symbols:
            locale = "en"
            configs = getattr(context, "configs", {})
            if isinstance(configs, dict):
                locale = configs.get("locale", locale)
            widget_config = {
                "symbols": widget_symbols,
                "original": tickers,
                "chartType": "candlesticks",
                "showVolume": True,
                "showMA": False,
                "autosize": True,
                "height": 440,
                "locale": locale,
            }
            payload["stock_widget"] = widget_config
            metadata["preview_keys"].append("stock_widget")

        if not tickers:
            metadata["summary"] = "No planner tickers detected; market snapshot idle."
            metadata["preview_only"] = True
            return ToolAdapterResult(
                name=self.name,
                status="queued",
                payload=payload,
                metadata=metadata,
            )

        client = PolygonMarketDataClient()
        if not getattr(client, "is_configured", False):
            metadata["summary"] = "Polygon client not configured; showing TradingView fallback."
            metadata["preview_only"] = False
            payload["ready"] = False
            return ToolAdapterResult(
                name=self.name,
                status="completed",
                payload=payload,
                metadata=metadata,
            )

        symbol = tickers[0].upper()
        try:
            snapshot = await fetch_daily_snapshot(symbol, client=client)
        except PolygonError as exc:
            error_message = str(exc)
            metadata["summary"] = f"Polygon error for {symbol}: {error_message}"
            metadata["error"] = error_message
            payload["error"] = error_message
            return ToolAdapterResult(
                name=self.name,
                status="error",
                payload=payload,
                metadata=metadata,
            )

        bars = snapshot.bars[-30:]
        formatted_bars = [
            {
                "time": bar.time,
                "open": round(bar.open, 2),
                "high": round(bar.high, 2),
                "low": round(bar.low, 2),
                "close": round(bar.close, 2),
                "volume": int(bar.volume),
            }
            for bar in bars
        ]
        payload.update(
            {
                "ready": True,
                "symbol": snapshot.symbol,
                "latest_close": snapshot.latest_close,
                "previous_close": snapshot.previous_close,
                "change_percent": snapshot.change_percent,
                "bars": formatted_bars,
                "chartType": payload.get("chartType") or "candlestick",
                "showVolume": payload.get("showVolume", True),
                "showMA": payload.get("showMA", False),
                "autosize": payload.get("autosize", True),
                "fetched_at": datetime.utcnow().isoformat(),
                "insights": {
                    "symbol": snapshot.symbol,
                    "latest_close": snapshot.latest_close,
                    "previous_close": snapshot.previous_close,
                    "change_percent": snapshot.change_percent,
                },
            }
        )
        if widget_config:
            payload["stock_widget"] = {
                **widget_config,
                "chartType": payload.get("chartType"),
                "showVolume": payload.get("showVolume"),
                "showMA": payload.get("showMA"),
                "autosize": payload.get("autosize"),
                "height": widget_config.get("height", 440),
            }

        metadata["summary"] = (
            f"{snapshot.symbol} close {snapshot.latest_close:.2f}"
            + (
                f" ({snapshot.change_percent:+.2f}% vs prior close)"
                if snapshot.change_percent is not None
                else ""
            )
        )
        metadata["preview_only"] = False
        metadata["preview_keys"] = sorted(set(metadata["preview_keys"]))

        return ToolAdapterResult(
            name=self.name,
            status="completed",
            payload=payload,
            metadata=metadata,
        )


class MarketQuestionAdapter(StockTrackerAdapter):
    """Stock tracker wrapper that tags outputs for specific market questions."""

    def __init__(self, alias: str, label: str) -> None:
        super().__init__()
        self.name = alias
        self.display_name = label
        self._question_id = alias

    async def execute(self, context: ToolExecutionContext) -> ToolAdapterResult:  # type: ignore[override]
        result = await super().execute(context)
        if isinstance(result.metadata, dict):
            meta = dict(result.metadata)
        else:
            meta = {}
        meta.setdefault("question_id", self._question_id)
        result.metadata = meta
        if isinstance(result.payload, dict):
            payload = dict(result.payload)
            payload.setdefault("question_id", self._question_id)
            result.payload = payload
        return result


class NarrativeSynthesizerAdapter(BaseToolAdapter):
    name = "narrative_synthesizer"
    display_name = "Narrative Synthesizer"
    description = "Draft narrative preview text from planned metrics."
    capabilities = ("analysis_preview", "telemetry")
    outputs = ("preview",)

    async def execute(self, context: ToolExecutionContext) -> ToolAdapterResult:
        plan = context.plan
        metrics = getattr(plan, "metrics", []) or []
        preview = f"Preparing narrative for {', '.join(metrics[:3]) or 'selected metrics'}"
        payload = {
            "preview": preview,
        }
        metadata = self.get_metadata()
        metadata["summary"] = preview
        if metrics:
            metadata["sample_metrics"] = metrics[:3]
        metadata["preview_keys"] = list(payload.keys())
        return ToolAdapterResult(name=self.name, status="drafting", payload=payload, metadata=metadata)


_DEFAULT_ADAPTERS: Tuple[BaseToolAdapter, ...] = (
    SQLPlannerAdapter(),
    ChartBuilderAdapter(),
    WebRetrieverAdapter(),
    StockTrackerAdapter(),
    NarrativeSynthesizerAdapter(),
)


def get_default_tool_adapters() -> Tuple[BaseToolAdapter, ...]:
    return _DEFAULT_ADAPTERS




def _resolve_concurrency_limit(ctx: "PlannerPhaseContext", default: int = 5) -> int:
    configs = getattr(ctx, "configs", {}) or {}
    limit: Optional[int] = None

    if isinstance(configs, dict):
        tooling_cfg = configs.get("tooling")
        if isinstance(tooling_cfg, dict):
            value = tooling_cfg.get("concurrency_limit")
            if isinstance(value, int):
                limit = value
        if limit is None:
            analytics_cfg = configs.get("analytics")
            if isinstance(analytics_cfg, dict):
                fanout_cfg = analytics_cfg.get("tool_parallelism")
                if isinstance(fanout_cfg, dict):
                    value = fanout_cfg.get("concurrency_limit")
                    if isinstance(value, int):
                        limit = value

    env_value = os.getenv("ANALYTICS_TOOL_CONCURRENCY_LIMIT")
    if env_value is not None:
        try:
            parsed = int(env_value)
            if parsed >= 1:
                limit = parsed
        except ValueError:
            pass

    if not limit or limit < 1:
        return default
    return min(limit, len(get_default_tool_adapters()))

async def run_tool_parallelism(
    ctx: "PlannerPhaseContext",
    *,
    adapters: Optional[Sequence[BaseToolAdapter]] = None,
    concurrency_override: Optional[int] = None,
) -> AsyncGenerator[Dict[str, Any], None]:
    """Execute the registered tool adapters and yield telemetry events."""

    intent = getattr(ctx, "intent", None)
    plan = getattr(ctx, "plan", None) or getattr(ctx, "provisional_plan", None)
    if not intent or not plan:
        return

    selected_adapters: Tuple[BaseToolAdapter, ...] = (
        tuple(adapters) if adapters is not None else get_default_tool_adapters()
    )
    if not selected_adapters:
        return

    execution_context = ToolExecutionContext(
        session_id=ctx.session_id,
        query=ctx.query,
        intent=intent,
        plan=plan,
        template=getattr(ctx, "template", None),
        configs=getattr(ctx, "configs", {}),
    )

    tool_manifests = [adapter.get_metadata() for adapter in selected_adapters]

    default_concurrency = len(selected_adapters)
    concurrency_limit = concurrency_override or _resolve_concurrency_limit(ctx, default=default_concurrency)
    if adapters is None:
        ctx.tool_parallel_manifest = tool_manifests
        ctx.tool_parallel_results = []
    else:
        existing_manifest = getattr(ctx, "tool_parallel_manifest", []) or []
        ctx.tool_parallel_manifest = [*existing_manifest, *tool_manifests]
        ctx.tool_parallel_results = getattr(ctx, "tool_parallel_results", []) or []
    ctx.tool_parallel_concurrency = concurrency_limit
    telemetry.tool_parallelism(
        stage="start",
        session_id=getattr(ctx, "session_id", None),
        flow=getattr(ctx, "flow_label", None),
        payload={
            "tool_group": "single_agent",
            "parallel_group": "tool_fanout",
            "tool_count": len(selected_adapters),
            "concurrency_limit": concurrency_limit,
            "tools": tool_manifests,
        },
    )
    yield {
        "event": "tool_parallel_start",
        "data": {
            "tool_group": "single_agent",
            "parallel_group": "tool_fanout",
            "tool_count": len(selected_adapters),
            "concurrency_limit": concurrency_limit,
            "tools": tool_manifests,
            "ts": datetime.utcnow().isoformat(),
        },
    }

    task_group = ToolTaskGroup(selected_adapters, concurrency_limit=concurrency_limit)
    result_queue: asyncio.Queue[Dict[str, Any]] = asyncio.Queue()
    total_expected = len(selected_adapters)
    fatal_detected = False

    async def _handle_result(result: ToolAdapterResult) -> None:
        nonlocal fatal_detected
        payload_for_context = (
            copy.deepcopy(result.payload) if result.payload is not None else {}
        )
        metadata_for_context = (
            copy.deepcopy(result.metadata) if result.metadata is not None else {}
        )
        serialized = {
            "tool": result.name,
            "status": result.status,
            "payload": payload_for_context,
            "metadata": metadata_for_context,
            "error": result.error,
            "elapsed_ms": result.elapsed_ms,
            "started_at": result.started_at,
            "completed_at": result.completed_at,
            "fatal": result.fatal,
        }
        ctx.tool_parallel_results.append(serialized)
        if len(ctx.tool_parallel_results) > 10:
            ctx.tool_parallel_results = ctx.tool_parallel_results[-10:]
        telemetry.tool_parallelism(
            stage="result",
            session_id=getattr(ctx, "session_id", None),
            flow=getattr(ctx, "flow_label", None),
            payload={**serialized, "concurrency_limit": concurrency_limit},
        )
        if result.status == "error" and result.fatal:
            fatal_detected = True
        event_payload = {
            "tool": result.name,
            "status": result.status,
            "payload": copy.deepcopy(serialized["payload"]),
            "metadata": copy.deepcopy(serialized["metadata"]),
            "error": result.error,
            "elapsed_ms": result.elapsed_ms,
            "started_at": result.started_at,
            "completed_at": result.completed_at,
            "fatal": result.fatal,
            "parallel_group": "tool_fanout",
            "tool_group": "single_agent",
            "concurrency_limit": concurrency_limit,
            "ts": datetime.utcnow().isoformat(),
        }
        await result_queue.put({"event": "tool_parallel_result", "data": event_payload})

    task = asyncio.create_task(task_group.run(execution_context, on_result=_handle_result))
    results: List[ToolAdapterResult] = []

    try:
        emitted = 0
        while emitted < total_expected:
            event = await result_queue.get()
            emitted += 1
            yield event

        # Drain any remaining events that might have arrived while awaiting completion.
        while not result_queue.empty():
            yield result_queue.get_nowait()

        results = await task
    finally:
        if not task.done():
            task.cancel()
            with contextlib.suppress(Exception):
                await task
    if not fatal_detected:
        fatal_detected = any(result.status == "error" and result.fatal for result in results)

    completion_status = "cancelled" if fatal_detected else "complete"
    telemetry.tool_parallelism(
        stage="complete",
        session_id=getattr(ctx, "session_id", None),
        flow=getattr(ctx, "flow_label", None),
        payload={
            "status": completion_status,
            "concurrency_limit": concurrency_limit,
            "tool_group": "single_agent",
            "parallel_group": "tool_fanout",
        },
    )
    yield {
        "event": "tool_parallel_complete",
        "data": {
            "tool_group": "single_agent",
            "parallel_group": "tool_fanout",
            "status": completion_status,
            "concurrency_limit": concurrency_limit,
            "ts": datetime.utcnow().isoformat(),
        },
    }


