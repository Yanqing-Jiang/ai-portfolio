# --- Analytics Function/Class Map ---
# Class: SqlLaneExecutor
#   Role: Executes the SQL lane using either a dedicated runner or the PlannerOrchestratorAdapter.
#   Called from: analytics.flows.multi_agent.MultiAgentFlow.sequencer_stream, tests.analytics.test_lane_executors
#   Collaborators: analytics.flows.orchestrator_types.PlannerOrchestratorAdapter, analytics.flows.planner.sql_stage
#   Why: Moves lane behavior toward self-contained executors while keeping legacy adapter compatibility.
# Class: ChartLaneExecutor
#   Role: Executes the chart lane using either a dedicated runner or the PlannerOrchestratorAdapter.
#   Called from: analytics.flows.multi_agent.MultiAgentFlow.sequencer_stream, tests.analytics.test_lane_executors
#   Collaborators: analytics.flows.orchestrator_types.PlannerOrchestratorAdapter, analytics.flows.planner.chart_stage
#   Why: Enables chart lane reuse across direct, single-agent, and multi-agent flows.
# Class: AnalysisLaneExecutor
#   Role: Executes the analysis lane using either a dedicated runner or the PlannerOrchestratorAdapter.
#   Called from: analytics.flows.multi_agent.MultiAgentFlow.sequencer_stream, tests.analytics.test_lane_executors
#   Collaborators: analytics.flows.orchestrator_types.PlannerOrchestratorAdapter, analytics.flows.planner.analysis_stage
#   Why: Centralizes analysis execution so AgentRuntime and Sequencer share the same lane behavior.
# Class: AccessoryLaneExecutor
#   Role: Executes accessory lanes (web/market) with dedicated runners or legacy adapter methods.
#   Called from: analytics.flows.multi_agent.MultiAgentFlow.sequencer_stream, future single-agent tool wrappers
#   Collaborators: analytics.flows.orchestrator_types.PlannerOrchestratorAdapter, analytics.flows.planner.sql_lane
#   Why: Removes bespoke accessory handling from specialist coroutines and prepares toolized accessory lanes.
# Class: LaneExecutorOrchestratorProxy
#   Role: Wraps a FlowOrchestrator so PlannerSequencer lanes execute through lane executors while keeping metadata/pass-through behavior intact.
#   Called from: analytics.flows.multi_agent.MultiAgentFlow.sequencer_stream via wrap_sequencer_with_lane_executors
#   Collaborators: analytics.flows.lane_executors.SqlLaneExecutor, ChartLaneExecutor, AnalysisLaneExecutor, AccessoryLaneExecutor
#   Why: Enables Phase 0.5 decomposition without changing PlannerSequencer event ordering or payloads.
# Function: create_sql_executor
#   Role: Factory that wires SqlLaneExecutor to the shared SQL stage runner.
#   Called from: analytics.flows.pipeline_tools (executor binding), analytics.tools registry
#   Invokes: analytics.flows.planner.sql_stage.run_sql_stage
#   Why: Ensures lane execution is shared between DIRECT and agent flows.
# Function: create_chart_executor
#   Role: Factory that wires ChartLaneExecutor to the shared chart stage runner.
#   Called from: analytics.flows.pipeline_tools
#   Invokes: analytics.flows.planner.chart_stage.run_chart_stage
#   Why: Aligns chart execution across planner and agent tool calls.
# Function: create_analysis_executor
#   Role: Factory that wires AnalysisLaneExecutor to the shared analysis stage runner.
#   Called from: analytics.flows.pipeline_tools
#   Invokes: analytics.flows.planner.analysis_stage.run_analysis_stage
#   Why: Centralizes analysis execution for Direct, Single, and Multi-Agent flows.
# Function: create_accessory_executor
#   Role: Factory that wires AccessoryLaneExecutor to planner accessory refreshers.
#   Called from: analytics.flows.pipeline_tools
#   Invokes: PlannerPipeline.refresh_web_lane / refresh_market_lane
#   Why: Provides reusable accessory lane execution without legacy specialist coroutines.
# Function: wrap_sequencer_with_lane_executors
#   Role: Injects LaneExecutorOrchestratorProxy into an existing PlannerSequencer instance to route lane execution through the executor wrappers.
#   Called from: analytics.flows.multi_agent.MultiAgentFlow.sequencer_stream
#   Invokes: LaneExecutorOrchestratorProxy
#   Why: Centralizes behavior-preserving wiring so tests can lock executor usage and later refactors can expand per-lane logic safely.
# --- End Analytics Function/Class Map ---
from __future__ import annotations

from typing import Any, AsyncGenerator, Callable, Iterable, Mapping, Optional

from .orchestrator_types import PlannerOrchestratorAdapter, FlowOrchestrator
from .planner.sql_stage import run_sql_stage
from .planner.chart_stage import run_chart_stage
from .planner.analysis_stage import run_analysis_stage

LaneRunner = Callable[[], AsyncGenerator[Mapping[str, Any], None]]


class SqlLaneExecutor:
    """Executes the SQL lane via a dedicated runner or legacy adapter."""

    def __init__(
        self,
        orchestrator: Optional[PlannerOrchestratorAdapter] = None,
        *,
        runner: Optional[LaneRunner] = None,
    ) -> None:
        self._orchestrator = orchestrator
        self._runner = runner

    async def run(self) -> AsyncGenerator[Mapping[str, Any], None]:
        runner = self._runner
        if runner is not None:
            async for event in runner():
                yield event
            return
        if self._orchestrator is None:
            raise RuntimeError("SqlLaneExecutor missing runner")
        async for event in self._orchestrator.run_sql_stage():
            yield event


class ChartLaneExecutor:
    """Executes the chart lane via a dedicated runner or legacy adapter."""

    def __init__(
        self,
        orchestrator: Optional[PlannerOrchestratorAdapter] = None,
        *,
        runner: Optional[LaneRunner] = None,
    ) -> None:
        self._orchestrator = orchestrator
        self._runner = runner

    async def run(self) -> AsyncGenerator[Mapping[str, Any], None]:
        runner = self._runner
        if runner is not None:
            async for event in runner():
                yield event
            return
        if self._orchestrator is None:
            raise RuntimeError("ChartLaneExecutor missing runner")
        async for event in self._orchestrator.run_chart_stage():
            yield event


class AnalysisLaneExecutor:
    """Executes the analysis lane via a dedicated runner or legacy adapter."""

    def __init__(
        self,
        orchestrator: Optional[PlannerOrchestratorAdapter] = None,
        *,
        runner: Optional[LaneRunner] = None,
    ) -> None:
        self._orchestrator = orchestrator
        self._runner = runner

    async def run(self) -> AsyncGenerator[Mapping[str, Any], None]:
        runner = self._runner
        if runner is not None:
            async for event in runner():
                yield event
            return
        if self._orchestrator is None:
            raise RuntimeError("AnalysisLaneExecutor missing runner")
        async for event in self._orchestrator.run_analysis_stage():
            yield event


class AccessoryLaneExecutor:
    """Executes accessory (web/market) lanes via dedicated runners or legacy adapter."""

    def __init__(
        self,
        orchestrator: Optional[PlannerOrchestratorAdapter] = None,
        *,
        runner: Optional[LaneRunner] = None,
        lane: str,
    ) -> None:
        self._orchestrator = orchestrator
        self._runner = runner
        self._lane = lane

    async def run(self) -> AsyncGenerator[Mapping[str, Any], None]:
        runner = self._runner
        if runner is not None:
            async for event in runner():
                yield event
            return
        if self._orchestrator is None:
            raise RuntimeError(f"{self._lane.capitalize()}LaneExecutor missing runner")
        if self._lane == "web":
            async for event in self._orchestrator.run_web_stage():
                yield event
            return
        if self._lane == "market":
            async for event in self._orchestrator.run_market_stage():
                yield event
            return
        raise AttributeError(f"Unsupported accessory lane: {self._lane}")


def create_sql_executor(
    *,
    pipeline: Any,
    ctx: Any,
    registry: Any,
    executed: Iterable[str],
    tool_state: Optional[Mapping[str, Any]] = None,
    run_sql_lane: bool = True,
) -> SqlLaneExecutor:
    """Factory to build a SqlLaneExecutor backed by the shared SQL stage."""

    async def _runner() -> AsyncGenerator[Mapping[str, Any], None]:
        async for event in run_sql_stage(
            pipeline,
            ctx=ctx,
            registry=registry,
            executed=set(executed),
            tool_state=dict(tool_state) if tool_state else None,
            run_sql_lane=run_sql_lane,
        ):
            yield event

    return SqlLaneExecutor(runner=_runner)


def create_chart_executor(
    *,
    pipeline: Any,
    ctx: Any,
    registry: Any,
    executed: Iterable[str],
    tool_state: Optional[Mapping[str, Any]] = None,
    run_chart_lane: bool = True,
) -> ChartLaneExecutor:
    """Factory to build a ChartLaneExecutor backed by the shared chart stage."""

    async def _runner() -> AsyncGenerator[Mapping[str, Any], None]:
        async for event in run_chart_stage(
            pipeline,
            ctx=ctx,
            registry=registry,
            executed=set(executed),
            tool_state=dict(tool_state) if tool_state else None,
            run_chart_lane=run_chart_lane,
        ):
            yield event

    return ChartLaneExecutor(runner=_runner)


def create_analysis_executor(
    *,
    pipeline: Any,
    ctx: Any,
    registry: Any,
    executed: Iterable[str],
    tool_state: Optional[Mapping[str, Any]] = None,
    mode_config: Any = None,
) -> AnalysisLaneExecutor:
    """Factory to build an AnalysisLaneExecutor backed by the shared analysis stage."""

    async def _runner() -> AsyncGenerator[Mapping[str, Any], None]:
        async for event in run_analysis_stage(
            pipeline,
            ctx=ctx,
            registry=registry,
            executed=set(executed),
            tool_state=dict(tool_state) if tool_state else None,
            mode_config=mode_config,
        ):
            yield event

    return AnalysisLaneExecutor(runner=_runner)


def create_accessory_executor(
    *,
    pipeline: Any,
    ctx: Any,
    lane: str,
    reason: Optional[str] = None,
    source: Optional[str] = None,
) -> AccessoryLaneExecutor:
    """Factory to build an AccessoryLaneExecutor backed by planner accessory refreshers."""

    async def _runner() -> AsyncGenerator[Mapping[str, Any], None]:
        if lane == "web":
            async for event in pipeline.refresh_web_lane(
                ctx,
                reason=reason or "executor_factory",
                source=source or "planner_pipeline",
            ):
                yield event
            return
        if lane == "market":
            async for event in pipeline.refresh_market_lane(
                ctx,
                reason=reason or "executor_factory",
                source=source or "planner_pipeline",
            ):
                yield event
            return
        raise AttributeError(f"Unsupported accessory lane: {lane}")

    return AccessoryLaneExecutor(runner=_runner, lane=lane)


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
        web_executor: Optional[AccessoryLaneExecutor] = None,
        market_executor: Optional[AccessoryLaneExecutor] = None,
        chart_executor: Optional[ChartLaneExecutor] = None,
    ) -> None:
        self._base = base
        self._sql_executor = sql_executor
        self._analysis_executor = analysis_executor
        self._chart_executor = chart_executor
        self._web_executor = web_executor
        self._market_executor = market_executor
        self.optional_lanes = getattr(base, "optional_lanes", None)

    async def run_intent_stage(self) -> AsyncGenerator[Mapping[str, Any], None]:
        async for event in self._base.run_intent_stage():
            yield event

    async def run_sql_stage(self) -> AsyncGenerator[Mapping[str, Any], None]:
        async for event in self._sql_executor.run():
            yield event

    async def run_web_stage(self) -> AsyncGenerator[Mapping[str, Any], None]:
        if self._web_executor is not None:
            async for event in self._web_executor.run():
                yield event
            return
        async for event in self._base.run_web_stage():
            yield event

    async def run_market_stage(self) -> AsyncGenerator[Mapping[str, Any], None]:
        if self._market_executor is not None:
            async for event in self._market_executor.run():
                yield event
            return
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
    web_executor: Optional[AccessoryLaneExecutor] = None
    market_executor: Optional[AccessoryLaneExecutor] = None
    if hasattr(orchestrator, "run_chart_stage"):
        chart_executor = ChartLaneExecutor(orchestrator)
    if hasattr(orchestrator, "run_web_stage"):
        web_executor = AccessoryLaneExecutor(orchestrator, lane="web")
    if hasattr(orchestrator, "run_market_stage"):
        market_executor = AccessoryLaneExecutor(orchestrator, lane="market")
    proxy = LaneExecutorOrchestratorProxy(
        orchestrator,
        sql_executor=sql_executor,
        analysis_executor=analysis_executor,
        web_executor=web_executor,
        market_executor=market_executor,
        chart_executor=chart_executor,
    )
    try:
        sequencer._orchestrator = proxy  # type: ignore[attr-defined]
    except Exception:  # pragma: no cover - defensive write guard
        return
