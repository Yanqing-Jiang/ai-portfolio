from __future__ import annotations

import asyncio
import inspect
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Dict, Iterable, List, Mapping, MutableMapping, Optional, Sequence, Tuple

__all__ = [
    "AgentExecutionError",
    "AgentResult",
    "AgentRunContext",
    "AgentSpec",
    "AgentTask",
    "OrchestratorContext",
    "AgentExecutionOrchestrator",
    "AgentToolRetryableError",
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

    def to_events(
        self,
        *,
        role: Optional[str] = None,
        run_id: Optional[str] = None,
        retry_count: Optional[int] = None,
        extra: Optional[Mapping[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        base_events: List[Dict[str, Any]] = [dict(event) for event in self.events] if self.events else []
        if not base_events:
            base_events = [{"event": "agent_result", "data": {}}]
        enriched: List[Dict[str, Any]] = []
        for event in base_events:
            payload = dict(event)
            data = payload.setdefault("data", {})
            if not isinstance(data, dict):
                data = {}
                payload["data"] = data
            if role:
                data.setdefault("role", role)
            if run_id:
                data.setdefault("run_id", run_id)
            if retry_count is not None:
                data.setdefault("retry_count", retry_count)
            if extra:
                for key, value in extra.items():
                    data.setdefault(key, value)
            if isinstance(self.output, Mapping):
                status_value = self.output.get("status")
                if status_value is not None:
                    data.setdefault("status", status_value)
                error_value = self.output.get("error") or self.output.get("error_code")
                if error_value is not None:
                    data.setdefault("error", error_value)
            if self.elapsed_ms is not None:
                data.setdefault("elapsed_ms", self.elapsed_ms)
            enriched.append(payload)
        return enriched


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

    BackpressureCallback = Callable[[str, Mapping[str, Any]], None]

    def __init__(
        self,
        registry: Mapping[str, AgentSpec],
        *,
        max_depth: int = 3,
        max_retries: int = 0,
        retry_decider: Optional[
            Callable[[str, AgentSpec, int, AgentRunContext, Mapping[str, Any]], Tuple[bool, Optional[Dict[str, Any]]]]
        ] = None,
    ) -> None:
        if max_depth < 1:
            raise ValueError("max_depth must be >= 1")
        self._registry: Dict[str, AgentSpec] = dict(registry)
        self._max_depth = max_depth
        self._max_retries = max(0, int(max_retries))
        self._retry_decider = retry_decider

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

    async def run(
        self,
        plan: Iterable[AgentTask],
        context: OrchestratorContext,
        *,
        task_groups: Optional[Mapping[str, str]] = None,
        group_limits: Optional[Mapping[str, int]] = None,
        on_backpressure: Optional[BackpressureCallback] = None,
    ) -> Dict[str, AgentResult]:
        task_map = self._validate_plan(plan)
        group_lookup = dict(task_groups or {})
        limits_lookup: Dict[str, int] = {}
        if group_limits:
            for key, value in group_limits.items():
                try:
                    parsed = int(value)
                except (TypeError, ValueError):
                    continue
                limits_lookup[key] = parsed if parsed > 0 else 1
        pending = set(task_map.keys())
        completed: Dict[str, AgentResult] = {}

        while pending:
            ready = [name for name in pending if all(dep in completed for dep in task_map[name].depends_on)]
            if not ready:
                unresolved = ", ".join(sorted(pending))
                raise AgentExecutionError(
                    f"No runnable tasks found; unresolved dependencies: {unresolved}"
                )

            group_counts: Dict[str, int] = defaultdict(int)
            blocked_by_group: Dict[str, list[str]] = defaultdict(list)
            runnable: list[str] = []

            for task_name in ready:
                group = group_lookup.get(task_name)
                if group is None or group not in limits_lookup:
                    runnable.append(task_name)
                    if group:
                        group_counts[group] += 1
                    continue
                limit = limits_lookup[group]
                if group_counts[group] >= limit:
                    blocked_by_group[group].append(task_name)
                    continue
                runnable.append(task_name)
                group_counts[group] += 1

            if on_backpressure:
                for group, blocked_tasks in blocked_by_group.items():
                    limit = limits_lookup.get(group)
                    if not blocked_tasks or limit is None:
                        continue
                    running = group_counts.get(group, 0)
                    total_blocked = len(blocked_tasks)
                    for position, blocked_task in enumerate(blocked_tasks, start=1):
                        on_backpressure(
                            blocked_task,
                            {
                                "group": group,
                                "limit": limit,
                                "running": running,
                                "queue_size": total_blocked,
                                "position": position,
                            },
                        )

            if not runnable:
                runnable = list(ready)

            results: Dict[str, AgentResult] = {}
            try:
                async with asyncio.TaskGroup() as group:
                    tasks = {}
                    for task_name in runnable:
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
        attempts = 0
        retry_history: list[Dict[str, Any]] = []
        shared_retry_trace = context.shared.setdefault("retry_trace", [])

        while True:
            start = time.perf_counter()
            try:
                if timeout:
                    result = await asyncio.wait_for(spec.entrypoint(context), timeout)
                else:
                    result = await spec.entrypoint(context)
                if not isinstance(result, AgentResult):
                    raise AgentExecutionError(
                        f"Agent '{spec.name}' returned unsupported result type: {type(result)!r}"
                    )

                elapsed_ms = int((time.perf_counter() - start) * 1000)
                result.elapsed_ms = elapsed_ms
                if not result.name:
                    result.name = spec.name

                if retry_history:
                    result.output.setdefault("retry_trace", list(retry_history))
                    result.output.setdefault("attempts", attempts + 1)

                if spec.evaluation_hook:
                    maybe = spec.evaluation_hook(result)
                    if inspect.isawaitable(maybe):
                        await maybe

                return result
            except AgentToolRetryableError as exc:
                elapsed_ms = int((time.perf_counter() - start) * 1000)
                attempts += 1
                retry_entry = {
                    "agent": spec.name,
                    "task": task_name,
                    "error": str(exc),
                    "error_code": exc.code,
                    "elapsed_ms": elapsed_ms,
                }
                if exc.metadata:
                    retry_entry["metadata"] = dict(exc.metadata)
                retry_history.append(retry_entry)
                shared_retry_trace.append(
                    {
                        "agent": spec.name,
                        "task": task_name,
                        "error_code": exc.code,
                        "message": str(exc),
                        "attempt": attempts,
                    }
                )
                decision_metadata: Optional[Dict[str, Any]] = None
                if self._retry_decider:
                    allow_retry, decision_metadata = self._retry_decider(
                        task_name,
                        spec,
                        attempts,
                        context,
                        retry_entry,
                    )
                    if not allow_retry:
                        failure = AgentResult(
                            name=spec.name,
                            output={
                                "status": "declined",
                                "error": str(exc),
                                "error_code": exc.code,
                                "retry_trace": list(retry_history),
                                "attempts": attempts,
                                "delegation_decision": decision_metadata,
                            },
                            metrics={},
                            events=tuple(),
                            elapsed_ms=elapsed_ms,
                        )
                        return failure
                if attempts > self._max_retries:
                    failure = AgentResult(
                        name=spec.name,
                        output={
                            "status": "failed",
                            "error": str(exc),
                            "error_code": exc.code,
                            "retry_trace": list(retry_history),
                            "attempts": attempts,
                        },
                        metrics={},
                        events=tuple(),
                        elapsed_ms=elapsed_ms,
                    )
                    return failure
                await asyncio.sleep(0)
                continue
            except asyncio.TimeoutError as exc:
                raise AgentExecutionError(
                    f"Agent '{spec.name}' exceeded latency budget of {budget} ms"
                ) from exc
            except Exception as exc:  # pragma: no cover - defensive guard
                raise AgentExecutionError(
                    f"Agent '{spec.name}' failed during execution"
                ) from exc
class AgentToolRetryableError(RuntimeError):
    """Raised by specialist agents to request a retry without aborting the workflow."""

    def __init__(self, code: str, message: str | None = None, *, metadata: Optional[Mapping[str, Any]] = None) -> None:
        self.code = code
        self.metadata = dict(metadata or {})
        super().__init__(message or code)
