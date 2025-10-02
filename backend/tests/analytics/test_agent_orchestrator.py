import asyncio
import time
from pathlib import Path
from typing import Dict, List

import pytest

import sys
import importlib.util

ROOT = Path(__file__).resolve().parents[3]
MODULE_PATH = ROOT / "backend" / "analytics" / "flows" / "orchestrator.py"
spec = importlib.util.spec_from_file_location("analytics.flows.orchestrator", MODULE_PATH)
if spec is None or spec.loader is None:
    raise RuntimeError("Failed to load orchestrator module for testing")
orchestrator_module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = orchestrator_module
spec.loader.exec_module(orchestrator_module)

AgentExecutionError = orchestrator_module.AgentExecutionError
AgentExecutionOrchestrator = orchestrator_module.AgentExecutionOrchestrator
AgentResult = orchestrator_module.AgentResult
AgentRunContext = orchestrator_module.AgentRunContext
AgentSpec = orchestrator_module.AgentSpec
AgentTask = orchestrator_module.AgentTask
OrchestratorContext = orchestrator_module.OrchestratorContext

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.usefixtures("anyio_backend")
async def test_orchestrator_runs_dag_concurrently():
    shared_state: Dict[str, Dict[str, float]] = {"starts": {}, "finishes": {}}

    async def planner_agent(context: AgentRunContext) -> AgentResult:
        shared_state["starts"]["planner"] = time.perf_counter()
        await asyncio.sleep(0.05)
        shared_state["finishes"]["planner"] = time.perf_counter()
        return AgentResult(name="planner", output={"deps": list(context.dependencies.keys())})

    async def chart_agent(context: AgentRunContext) -> AgentResult:
        assert "planner_phase" in context.dependencies
        shared_state["starts"]["chart"] = time.perf_counter()
        await asyncio.sleep(0.05)
        shared_state["finishes"]["chart"] = time.perf_counter()
        return AgentResult(name="chart", output={"deps": list(context.dependencies.keys())})

    async def market_agent(context: AgentRunContext) -> AgentResult:
        assert "planner_phase" in context.dependencies
        shared_state["starts"]["market"] = time.perf_counter()
        await asyncio.sleep(0.05)
        shared_state["finishes"]["market"] = time.perf_counter()
        return AgentResult(name="market", output={"deps": list(context.dependencies.keys())})

    registry: Dict[str, AgentSpec] = {
        "planner": AgentSpec(
            name="planner",
            system_prompt="Plan tasks for specialists.",
            capabilities=("planning",),
            latency_budget_ms=200,
            entrypoint=planner_agent,
        ),
        "chart": AgentSpec(
            name="chart",
            system_prompt="Build chart specs.",
            capabilities=("visualization",),
            latency_budget_ms=200,
            entrypoint=chart_agent,
        ),
        "market": AgentSpec(
            name="market",
            system_prompt="Provide market updates.",
            capabilities=("market",),
            latency_budget_ms=200,
            entrypoint=market_agent,
        ),
    }

    orchestrator = AgentExecutionOrchestrator(registry)
    plan = [
        AgentTask(name="planner_phase", agent="planner"),
        AgentTask(name="chart_phase", agent="chart", depends_on=("planner_phase",)),
        AgentTask(name="market_phase", agent="market", depends_on=("planner_phase",)),
    ]

    context = OrchestratorContext(query="q", session_id="s", shared={})
    results = await orchestrator.run(plan, context)

    assert set(results.keys()) == {"planner_phase", "chart_phase", "market_phase"}
    planner_done = shared_state["finishes"]["planner"]
    chart_start = shared_state["starts"]["chart"]
    market_start = shared_state["starts"]["market"]
    assert chart_start >= planner_done
    assert market_start >= planner_done


@pytest.mark.usefixtures("anyio_backend")
async def test_orchestrator_enforces_depth_limit():
    async def noop_agent(context: AgentRunContext) -> AgentResult:
        return AgentResult(name="noop", output={})

    registry = {
        "noop": AgentSpec(
            name="noop",
            system_prompt="Do nothing.",
            capabilities=("noop",),
            latency_budget_ms=200,
            entrypoint=noop_agent,
        )
    }

    orchestrator = AgentExecutionOrchestrator(registry)
    plan = [
        AgentTask(name="layer1", agent="noop"),
        AgentTask(name="layer2", agent="noop", depends_on=("layer1",)),
        AgentTask(name="layer3", agent="noop", depends_on=("layer2",)),
        AgentTask(name="layer4", agent="noop", depends_on=("layer3",)),
    ]

    with pytest.raises(AgentExecutionError):
        await orchestrator.run(plan, OrchestratorContext(query="q", session_id=None, shared={}))


@pytest.mark.usefixtures("anyio_backend")
async def test_orchestrator_calls_evaluation_hook_and_records_elapsed():
    hook_calls: List[int] = []

    async def agent(context: AgentRunContext) -> AgentResult:
        await asyncio.sleep(0.01)
        return AgentResult(name="agent", output={})

    async def eval_hook(result: AgentResult) -> None:
        hook_calls.append(result.elapsed_ms or 0)

    registry = {
        "agent": AgentSpec(
            name="agent",
            system_prompt="Test agent.",
            capabilities=("test",),
            latency_budget_ms=200,
            entrypoint=agent,
            evaluation_hook=eval_hook,
        )
    }

    orchestrator = AgentExecutionOrchestrator(registry)
    plan = [AgentTask(name="task", agent="agent")]

    results = await orchestrator.run(plan, OrchestratorContext(query="q", session_id=None, shared={}))

    assert "task" in results
    assert results["task"].elapsed_ms is not None
    assert hook_calls and hook_calls[0] == results["task"].elapsed_ms


@pytest.mark.usefixtures("anyio_backend")
async def test_orchestrator_times_out_slow_agent():
    async def slow_agent(context: AgentRunContext) -> AgentResult:
        await asyncio.sleep(0.05)
        return AgentResult(name="slow", output={})

    registry = {
        "slow": AgentSpec(
            name="slow",
            system_prompt="Slow agent.",
            capabilities=("slow",),
            latency_budget_ms=10,
            entrypoint=slow_agent,
        )
    }

    orchestrator = AgentExecutionOrchestrator(registry)
    plan = [AgentTask(name="slow_task", agent="slow")]

    with pytest.raises(AgentExecutionError):
        await orchestrator.run(plan, OrchestratorContext(query="q", session_id=None, shared={}))

