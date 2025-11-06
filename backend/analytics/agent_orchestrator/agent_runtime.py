from __future__ import annotations

import asyncio
import logging
import time
import uuid
from datetime import datetime, timezone
from dataclasses import dataclass, field
from typing import Any, Dict, Mapping, Optional

from agents import Agent, Runner
from agents.result import RunResultStreaming
from agents.run import RunConfig

from analytics.core import telemetry
from analytics.core.events import EventEmitter
from analytics.validators import sanitize_for_json
from analytics.flows.agents_stream_bridge import AgentsStreamBridge
from analytics.flows.schedulers import FlowMode, apply_mode_metadata

from .agent_plan import PlanNode, PlanNodeStatus, PlanState, PlanTemplate
from .event_bus import AgentEventBus
from .memory import AgentMemory


@dataclass
class AgentRuntimeConfig:
    """Runtime knobs shared across orchestrated agent runs."""

    model: str
    max_turns: int = 8
    temperature: Optional[float] = None
    reasoning_effort: Optional[str] = None
    retry_policy: Dict[str, Any] = field(default_factory=dict)
    plan_template: Optional[PlanTemplate] = None


@dataclass
class AgentRuntimeResult:
    """Structured response emitted after an orchestrated agent run completes."""

    run_result: RunResultStreaming
    plan_state: PlanState
    final_output: Dict[str, Any]
    run_id: Optional[str]
    trace_id: Optional[str]


class AgentRuntime:
    """Drives the plan -> act -> observe loop for single-agent analytics runs."""

    def __init__(
        self,
        *,
        agent: Agent,
        memory: AgentMemory,
        queue: "asyncio.Queue[Optional[Dict[str, Any]]]",
        flow_mode: FlowMode,
        logger: Optional[logging.Logger] = None,
        config: AgentRuntimeConfig,
    ) -> None:
        self._agent = agent
        self._memory = memory
        self._queue = queue
        self._flow_mode = flow_mode
        self._logger = logger or logging.getLogger(__name__)
        self._config = config
        self._event_bus = AgentEventBus(queue, flow_mode=flow_mode, logger=self._logger)

    async def run(
        self,
        query: str,
        *,
        session_id: Optional[str],
        run_context: Optional[Any] = None,
        plan_template: Optional[PlanTemplate] = None,
    ) -> AgentRuntimeResult:
        """
        Execute the orchestrated agent run.

        Returns the streaming result emitted by the OpenAI Agents SDK once the
        run completes. SSE events have already been dispatched onto the shared
        queue by the time this coroutine resolves.
        """
        start_time = time.time()
        template = plan_template or self._config.plan_template or PlanTemplate(
            name="single_agent_default",
            nodes=(),
        )
        plan_state = self._memory.load_plan_state(template)
        active_node_name = self._select_active_node(plan_state)
        plan_state.mark_running(active_node_name)
        self._memory.persist_plan_state(plan_state)
        await self._publish_plan(plan_state)

        run_config = self._build_run_config()
        context_payload: Dict[str, Any] = {
            "session_id": session_id,
            "plan": plan_state.to_dict(),
        }
        if isinstance(run_context, Mapping):
            context_payload["metadata"] = dict(run_context)
        if run_context is not None and hasattr(run_context, "__dict__"):
            try:
                setattr(run_context, "agent_plan_snapshot", context_payload["plan"])
            except Exception:
                self._logger.debug("Unable to attach plan snapshot to run context", exc_info=True)

        telemetry.tool_iteration(
            tool="agent_controller",
            status="started",
            step=active_node_name,
            session_id=session_id,
            flow="single-agent",
        )

        run_result_streaming: RunResultStreaming
        try:
            runner_callable = getattr(Runner, "stream", None)
            if runner_callable is not None:
                run_result_streaming = runner_callable(
                    self._agent,
                    input=query,
                    session=None,
                    context=run_context or context_payload,
                    run_config=run_config,
                )
            else:
                runner_callable = getattr(Runner, "run_streamed", None)
                if runner_callable is None:
                    raise RuntimeError("OpenAI Agents Runner missing stream/run_streamed APIs")
                run_result_streaming = runner_callable(
                    self._agent,
                    input=query,
                    context=run_context or context_payload,
                    max_turns=self._config.max_turns,
                    run_config=run_config,
                )
            bridge = AgentsStreamBridge(flow_mode=self._flow_mode, queue=self._queue, logger=self._logger)
            run_result = await bridge.forward(run_result_streaming)
        except Exception as exc:
            self._logger.exception("Agent runtime failed")
            plan_state.mark_finished(active_node_name, PlanNodeStatus.FAILED)
            self._memory.persist_plan_state(plan_state)
            await self._publish_plan(plan_state)
            telemetry.tool_iteration(
                tool="agent_controller",
                status="failed",
                step=active_node_name,
                session_id=session_id,
                flow="single-agent",
                details={"error": str(exc)},
            )
            raise

        final_output = self._extract_final_output(run_result)
        plan_state.record_artifacts(active_node_name, {"final_output": final_output})
        plan_state.mark_finished(active_node_name, PlanNodeStatus.SUCCEEDED)
        self._memory.persist_plan_state(plan_state)
        await self._publish_plan(plan_state)

        run_id = getattr(run_result, "run_id", None) or getattr(run_result, "id", None)
        trace_id = getattr(run_result, "trace_id", None) or getattr(run_config, "trace_id", None)
        retry_counts: Dict[str, int] = {}
        receipts = self._memory.agent_cache.get("tool_receipts", {})
        self._memory.record_agent_run(
            run_id=str(run_id) if run_id else None,
            trace_id=str(trace_id) if trace_id else run_config.trace_id,
            model=self._config.model,
            tool_attempts={},
            retry_counts=retry_counts,
            receipts=receipts if isinstance(receipts, Mapping) else {},
        )

        telemetry.tool_iteration(
            tool="agent_controller",
            status="completed",
            step=active_node_name,
            session_id=session_id,
            flow="single-agent",
        )

        await self._enqueue_analysis_bundle(query, session_id, final_output)
        await self._enqueue_workflow_complete(start_time)

        return AgentRuntimeResult(
            run_result=run_result,
            plan_state=plan_state,
            final_output=final_output,
            run_id=str(run_id) if run_id else None,
            trace_id=str(trace_id) if trace_id else str(getattr(run_config, "trace_id", "")),
        )

    def _build_run_config(self) -> RunConfig:
        kwargs: Dict[str, Any] = {
            "model": self._config.model,
            "trace_id": str(uuid.uuid4()),
        }
        if self._config.temperature is not None:
            kwargs["temperature"] = self._config.temperature
        if self._config.reasoning_effort is not None:
            kwargs["reasoning_effort"] = self._config.reasoning_effort
        return RunConfig(**kwargs)

    def _select_active_node(self, plan_state: PlanState) -> str:
        ready = plan_state.ready_nodes()
        if ready:
            return ready[0].name
        # Fallback to first node or synthetic root when templates empty.
        if plan_state.nodes:
            return next(iter(plan_state.nodes.values())).name
        synthetic = PlanNode(name="agent_run", kind="agent")
        plan_state.nodes[synthetic.name] = synthetic
        return synthetic.name

    async def _publish_plan(self, plan_state: PlanState) -> None:
        try:
            await self._event_bus.publish(
                "agent_plan_updated",
                {
                    "plan": plan_state.to_dict(),
                },
            )
        except Exception:
            self._logger.exception("Failed to publish plan update")

    async def _enqueue_analysis_bundle(
        self,
        query: str,
        session_id: Optional[str],
        final_output: Mapping[str, Any],
    ) -> None:
        payload: Dict[str, Any] = {
            "analysis_bundle": sanitize_for_json(final_output),
            "query": query,
            "flow": "single-agent",
        }
        if session_id:
            payload["session_id"] = session_id
        event = {"event": "analysis_bundle", "data": payload}
        event = apply_mode_metadata(event, self._flow_mode)
        await self._queue.put(event)

    async def _enqueue_workflow_complete(self, start_time: float) -> None:
        total_elapsed_ms = int((time.time() - start_time) * 1000)
        event = EventEmitter.result(
            "workflow_complete",
            {"total_elapsed_ms": total_elapsed_ms},
        )
        event["event"] = "workflow_complete"
        event["data"]["ts"] = datetime.now(timezone.utc).isoformat()
        event = apply_mode_metadata(event, self._flow_mode)
        await self._queue.put(event)

    def _extract_final_output(self, result: RunResultStreaming) -> Dict[str, Any]:
        final_output = getattr(result, "final_output", None)
        if isinstance(final_output, Mapping):
            return dict(final_output)
        if isinstance(final_output, str):
            return {"analysis": final_output, "analysis_length": len(final_output)}
        return {"analysis": str(final_output), "analysis_length": len(str(final_output))}
