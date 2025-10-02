from __future__ import annotations

import asyncio
import inspect
import time
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Dict, Iterable, Mapping, MutableMapping, Optional, Sequence

__all__ = [
    "AgentExecutionError",
    "AgentResult",
    "AgentRunContext",
    "AgentSpec",
    "AgentTask",
    "OrchestratorContext",
    "AgentExecutionOrchestrator",
]


class AgentExecutionError(RuntimeError):
    """Raised when the orchestrator encounters an invalid plan or agent failure."""


@dataclass
class AgentResult:
    name: str
    output: Dict[str, Any] = field(default_factory=dict)
    events: Sequence[Dict[str, Any]] = field(default_factory=tuple)
    metrics: Dict[str, Any] = field(default_factory=dict)
    elapsed_ms: Optional[int] = None


@dataclass
class AgentRunContext:
    query: str
    session_id: Optional[str]
    shared: MutableMapping[str, Any]
    dependencies: Mapping[str, AgentResult]
    inputs: Dict[str, Any]


@dataclass(frozen=True)
class AgentSpec:
    name: str
    system_prompt: str
    capabilities: Sequence[str]
    latency_budget_ms: Optional[int]
    entrypoint: Callable[[AgentRunContext], Awaitable[AgentResult]]
    evaluation_hook: Optional[Callable[[AgentResult], Awaitable[None]]] = None


@dataclass
class AgentTask:
    name: str
    agent: str
    depends_on: Sequence[str] = field(default_factory=tuple)
    inputs: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.depends_on = tuple(self.depends_on)


@dataclass
class OrchestratorContext:
    query: str
    session_id: Optional[str] = None
    shared: Dict[str, Any] = field(default_factory=dict)


class AgentExecutionOrchestrator:
    """Executes agent DAGs with shallow depth constraints and TaskGroup fan-out."""

    def __init__(self, registry: Mapping[str, AgentSpec], *, max_depth: int = 3) -> None:
        if max_depth < 1:
            raise ValueError("max_depth must be >= 1")
        self._registry: Dict[str, AgentSpec] = dict(registry)
        self._max_depth = max_depth

    def _validate_plan(self, tasks: Iterable[AgentTask]) -> Dict[str, AgentTask]:
        plan: Dict[str, AgentTask] = {}
        for task in tasks:
            if task.name in plan:
                raise AgentExecutionError(f"Duplicate task name detected: {task.name}")
            if task.agent not in self._registry:
                raise AgentExecutionError(f"Agent '{task.agent}' not registered")
            plan[task.name] = task

        for task in plan.values():
            for dependency in task.depends_on:
                if dependency not in plan:
                    raise AgentExecutionError(
                        f"Task '{task.name}' references unknown dependency '{dependency}'"
                    )

        depth_cache: Dict[str, int] = {}
        visiting: Dict[str, bool] = {}

        def compute_depth(name: str) -> int:
            if name in depth_cache:
                return depth_cache[name]
            if visiting.get(name):
                raise AgentExecutionError("Cycle detected in agent task graph")
            visiting[name] = True
            task_depth = 1
            for dep in plan[name].depends_on:
                dep_depth = compute_depth(dep)
                task_depth = max(task_depth, dep_depth + 1)
            if task_depth > self._max_depth:
                raise AgentExecutionError(
                    f"Task '{name}' exceeds maximum depth of {self._max_depth}"
                )
            depth_cache[name] = task_depth
            visiting.pop(name, None)
            return task_depth

        for name in plan:
            compute_depth(name)

        return plan

    async def run(self, plan: Iterable[AgentTask], context: OrchestratorContext) -> Dict[str, AgentResult]:
        task_map = self._validate_plan(plan)
        pending = set(task_map.keys())
        completed: Dict[str, AgentResult] = {}

        while pending:
            ready = [name for name in pending if all(dep in completed for dep in task_map[name].depends_on)]
            if not ready:
                unresolved = ", ".join(sorted(pending))
                raise AgentExecutionError(
                    f"No runnable tasks found; unresolved dependencies: {unresolved}"
                )

            results: Dict[str, AgentResult] = {}
            try:
                async with asyncio.TaskGroup() as group:
                    tasks = {}
                    for task_name in ready:
                        spec = self._registry[task_map[task_name].agent]
                        run_context = AgentRunContext(
                            query=context.query,
                            session_id=context.session_id,
                            shared=context.shared,
                            dependencies={dep: completed[dep] for dep in task_map[task_name].depends_on},
                            inputs=dict(task_map[task_name].inputs),
                        )
                        tasks[task_name] = group.create_task(
                            self._execute_agent(task_name, spec, run_context)
                        )
            except* AgentExecutionError as group_error:
                raise group_error.exceptions[0]

            for task_name, async_task in tasks.items():
                results[task_name] = async_task.result()

            for name, result in results.items():
                completed[name] = result
                pending.remove(name)

        return completed

    async def _execute_agent(
        self, task_name: str, spec: AgentSpec, context: AgentRunContext
    ) -> AgentResult:
        budget = spec.latency_budget_ms
        timeout = budget / 1000 if budget else None
        start = time.perf_counter()
        try:
            if timeout:
                result = await asyncio.wait_for(spec.entrypoint(context), timeout)
            else:
                result = await spec.entrypoint(context)
        except asyncio.TimeoutError as exc:
            raise AgentExecutionError(
                f"Agent '{spec.name}' exceeded latency budget of {budget} ms"
            ) from exc
        except Exception as exc:  # pragma: no cover - defensive guard
            raise AgentExecutionError(
                f"Agent '{spec.name}' failed during execution"
            ) from exc

        if not isinstance(result, AgentResult):
            raise AgentExecutionError(
                f"Agent '{spec.name}' returned unsupported result type: {type(result)!r}"
            )

        elapsed_ms = int((time.perf_counter() - start) * 1000)
        result.elapsed_ms = elapsed_ms
        if not result.name:
            result.name = spec.name

        if spec.evaluation_hook:
            maybe = spec.evaluation_hook(result)
            if inspect.isawaitable(maybe):
                await maybe

        return result
