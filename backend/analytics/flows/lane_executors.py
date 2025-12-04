# --- Analytics Function/Class Map ---
# Class: SqlLaneExecutor
#   Role: Executes the SQL lane using the existing PlannerOrchestratorAdapter callbacks.
#   Called from: analytics.flows.multi_agent.MultiAgentFlow.sequencer_stream, tests.analytics.test_lane_executors
#   Collaborators: analytics.flows.orchestrator_adapter.PlannerOrchestratorAdapter, analytics.flows.sequencer.PlannerSequencer
#   Why: Supports Phase 0.5 by isolating SQL lane behavior from the monolithic PlannerSequencer and multi_agent flow logic.
# Class: ChartLaneExecutor
#   Role: Executes the chart lane using the existing PlannerOrchestratorAdapter callbacks.
#   Called from: analytics.flows.multi_agent.MultiAgentFlow.sequencer_stream (future), tests.analytics.test_lane_executors
#   Collaborators: analytics.flows.orchestrator_adapter.PlannerOrchestratorAdapter, analytics.flows.sequencer.PlannerSequencer
#   Why: Supports Phase 0.5 by isolating chart lane behavior from the monolithic PlannerSequencer and multi_agent flow logic.
# Class: AnalysisLaneExecutor
#   Role: Executes the analysis lane using the existing PlannerOrchestratorAdapter callbacks.
#   Called from: analytics.flows.multi_agent.MultiAgentFlow.sequencer_stream, tests.analytics.test_lane_executors
#   Collaborators: analytics.flows.orchestrator_adapter.PlannerOrchestratorAdapter, analytics.flows.sequencer.PlannerSequencer
#   Why: Supports Phase 0.5 by isolating analysis lane behavior from the monolithic PlannerSequencer and multi_agent flow logic.
# Class: LaneExecutorOrchestratorProxy
#   Role: Wraps a FlowOrchestrator so PlannerSequencer lanes execute through lane executors while keeping metadata/pass-through behavior intact.
#   Called from: analytics.flows.multi_agent.MultiAgentFlow.sequencer_stream via wrap_sequencer_with_lane_executors
#   Collaborators: analytics.flows.lane_executors.SqlLaneExecutor, ChartLaneExecutor, AnalysisLaneExecutor
#   Why: Enables Phase 0.5 decomposition without changing PlannerSequencer event ordering or payloads.
# Function: wrap_sequencer_with_lane_executors
#   Role: Injects LaneExecutorOrchestratorProxy into an existing PlannerSequencer instance to route lane execution through the thin executor wrappers.
#   Called from: analytics.flows.multi_agent.MultiAgentFlow.sequencer_stream
#   Invokes: LaneExecutorOrchestratorProxy
#   Why: Centralizes behavior-preserving wiring so tests can lock executor usage and later refactors can expand per-lane logic safely.
# --- End Analytics Function/Class Map ---
from __future__ import annotations

from typing import Any, AsyncGenerator, Iterable, Mapping, Optional

from .orchestrator_types import PlannerOrchestratorAdapter, FlowOrchestrator


class SqlLaneExecutor:
    """Thin wrapper around PlannerOrchestratorAdapter to execute the SQL lane.

    This is a behavior-preserving adapter introduced as part of Phase 0.5 to make
    the SQL lane execution explicit and independently testable without changing
    PlannerSequencer semantics.
    """

    def __init__(self, orchestrator: PlannerOrchestratorAdapter) -> None:
        self._orchestrator = orchestrator

    async def run(self) -> AsyncGenerator[Mapping[str, Any], None]:
        async for event in self._orchestrator.run_sql_stage():
            yield event


class ChartLaneExecutor:
    """Thin wrapper around PlannerOrchestratorAdapter to execute the chart lane."""

    def __init__(self, orchestrator: PlannerOrchestratorAdapter) -> None:
        self._orchestrator = orchestrator

    async def run(self) -> AsyncGenerator[Mapping[str, Any], None]:
        async for event in self._orchestrator.run_chart_stage():
            yield event


class AnalysisLaneExecutor:
    """Thin wrapper around PlannerOrchestratorAdapter to execute the analysis lane."""

    def __init__(self, orchestrator: PlannerOrchestratorAdapter) -> None:
        self._orchestrator = orchestrator

    async def run(self) -> AsyncGenerator[Mapping[str, Any], None]:
        async for event in self._orchestrator.run_analysis_stage():
            yield event


class LaneExecutorOrchestratorProxy:
    """
    FlowOrchestrator proxy that routes lane execution through lane executors
    while delegating metadata and bookkeeping to the underlying orchestrator.
    """

    def __init__(
        self,
        base: FlowOrchestrator,
        *,
        sql_executor: SqlLaneExecutor,
        analysis_executor: AnalysisLaneExecutor,
        chart_executor: Optional[ChartLaneExecutor] = None,
    ) -> None:
        self._base = base
        self._sql_executor = sql_executor
        self._analysis_executor = analysis_executor
        self._chart_executor = chart_executor
        self.optional_lanes = getattr(base, "optional_lanes", None)

    async def run_intent_stage(self) -> AsyncGenerator[Mapping[str, Any], None]:
        async for event in self._base.run_intent_stage():
            yield event

    async def run_sql_stage(self) -> AsyncGenerator[Mapping[str, Any], None]:
        async for event in self._sql_executor.run():
            yield event

    async def run_web_stage(self) -> AsyncGenerator[Mapping[str, Any], None]:
        async for event in self._base.run_web_stage():
            yield event

    async def run_market_stage(self) -> AsyncGenerator[Mapping[str, Any], None]:
        async for event in self._base.run_market_stage():
            yield event

    async def run_analysis_stage(self) -> AsyncGenerator[Mapping[str, Any], None]:
        async for event in self._analysis_executor.run():
            yield event

    async def run_chart_stage(self) -> AsyncGenerator[Mapping[str, Any], None]:
        if self._chart_executor is None:
            raise AttributeError("run_chart_stage")
        async for event in self._chart_executor.run():
            yield event

    def pending_lanes(self) -> Iterable[str]:
        return self._base.pending_lanes()

    def lane_complete(
        self,
        lane: str,
        *,
        success: bool,
        reused: bool = False,
        reason: Optional[str] = None,
    ) -> None:
        return self._base.lane_complete(lane, success=success, reused=reused, reason=reason)

    def event_metadata(self) -> Mapping[str, Any]:
        return self._base.event_metadata()

    def __getattr__(self, name: str) -> Any:
        return getattr(self._base, name)


def wrap_sequencer_with_lane_executors(sequencer: Any) -> None:
    """
    Behavior-preserving wiring that replaces a sequencer's orchestrator with a
    LaneExecutorOrchestratorProxy so SQL/analysis lanes run through the new
    executor wrappers (Phase 0.5 scaffolding).
    """

    orchestrator = getattr(sequencer, "_orchestrator", None)
    if orchestrator is None or isinstance(orchestrator, LaneExecutorOrchestratorProxy):
        return
    sql_executor = SqlLaneExecutor(orchestrator)
    analysis_executor = AnalysisLaneExecutor(orchestrator)
    chart_executor: Optional[ChartLaneExecutor] = None
    if hasattr(orchestrator, "run_chart_stage"):
        chart_executor = ChartLaneExecutor(orchestrator)
    proxy = LaneExecutorOrchestratorProxy(
        orchestrator,
        sql_executor=sql_executor,
        analysis_executor=analysis_executor,
        chart_executor=chart_executor,
    )
    try:
        sequencer._orchestrator = proxy  # type: ignore[attr-defined]
    except Exception:  # pragma: no cover - defensive write guard
        return
