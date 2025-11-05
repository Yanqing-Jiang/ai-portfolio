from __future__ import annotations

from typing import Any, AsyncGenerator, Awaitable, Callable, Dict, Iterable, Optional

from .orchestrator_protocol import FlowOrchestrator

AsyncGenFactory = Callable[[], AsyncGenerator[Dict[str, Any], None]]
LaneCompleteCallback = Callable[[str, bool, bool, Optional[str]], None]


class PlannerOrchestratorAdapter(FlowOrchestrator):
    """
    Wraps a set of stage runners (intent, sql, web, market, analysis) so the
    PlannerSequencer can operate without depending on a specific controller
    implementation. Metadata is merged into every emitted event.
    """

    def __init__(
        self,
        *,
        intent_runner: AsyncGenFactory,
        sql_runner: AsyncGenFactory,
        web_runner: AsyncGenFactory,
        market_runner: AsyncGenFactory,
        analysis_runner: AsyncGenFactory,
        metadata: Optional[Dict[str, Any]] = None,
        optional_lanes: Optional[Iterable[str]] = None,
        lane_complete_callback: Optional[LaneCompleteCallback] = None,
    ) -> None:
        self._intent_runner = intent_runner
        self._sql_runner = sql_runner
        self._web_runner = web_runner
        self._market_runner = market_runner
        self._analysis_runner = analysis_runner
        self._metadata = dict(metadata or {})
        self.optional_lanes = tuple(optional_lanes or ("web", "market"))
        self._lane_complete_callback = lane_complete_callback
        self._pending: Dict[str, bool] = {
            "intent": True,
            "sql": True,
            "web": True,
            "market": True,
            "analysis": True,
        }

    async def run_intent_stage(self) -> AsyncGenerator[Dict[str, Any], None]:
        async for event in self._intent_runner():
            yield self._decorate(event)

    async def run_sql_stage(self) -> AsyncGenerator[Dict[str, Any], None]:
        async for event in self._sql_runner():
            yield self._decorate(event)

    async def run_web_stage(self) -> AsyncGenerator[Dict[str, Any], None]:
        async for event in self._web_runner():
            yield self._decorate(event)

    async def run_market_stage(self) -> AsyncGenerator[Dict[str, Any], None]:
        async for event in self._market_runner():
            yield self._decorate(event)

    async def run_analysis_stage(self) -> AsyncGenerator[Dict[str, Any], None]:
        async for event in self._analysis_runner():
            yield self._decorate(event)

    def pending_lanes(self) -> Iterable[str]:
        return tuple(lane for lane, pending in self._pending.items() if pending)

    def lane_complete(
        self,
        lane: str,
        *,
        success: bool,
        reused: bool = False,
        reason: Optional[str] = None,
    ) -> None:
        self._pending[lane] = False
        status_map = self._metadata.setdefault("lane_status", {})
        if isinstance(status_map, dict):
            status_map[lane] = "success" if success else "error"
        if self._lane_complete_callback:
            try:
                self._lane_complete_callback(lane, success, reused, reason)
            except Exception:  # pragma: no cover - defensive logging
                pass

    def event_metadata(self) -> Dict[str, Any]:
        enriched = dict(self._metadata)
        enriched["pending_lanes"] = list(self.pending_lanes())
        return enriched

    def _decorate(self, event: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(event, dict):
            return event
        data = event.setdefault("data", {})
        if isinstance(data, dict):
            for key, value in self._metadata.items():
                data.setdefault(key, value)
        return event
