# --- Analytics Function/Class Map ---
# Class: AgentRuntimeConfig
#   Role: Runtime knobs shared across orchestrated agent runs.
#   Called from: analytics.agent_orchestrator, analytics.flows.single_agent_tools, tests.analytics.test_agent_orchestrator
#   Collaborators: dataclasses.field
#   Why: Supports downstream analytics workflows that rely on AgentRuntimeConfig.
# Class: AgentRuntimeResult
#   Role: Structured response emitted after an orchestrated agent run completes.
#   Called from: analytics.agent_orchestrator, analytics.flows.single_agent_tools
#   Collaborators: Internal helpers only
#   Why: Supports downstream analytics workflows that rely on AgentRuntimeResult.
# Class: AgentRuntime
#   Role: Drives the plan -> act -> observe loop for single-agent analytics runs.
#   Called from: analytics.agent_orchestrator, analytics.flows.single_agent_tools, tests.analytics.test_agent_orchestrator
#   Collaborators: analytics.agent_orchestrator.event_bus.AgentEventBus, time.time, analytics.core.telemetry.tool_iteration, analytics.agent_orchestrator.agent_runtime.AgentRuntimeResult, +2 more
#   Why: Supports downstream analytics workflows that rely on AgentRuntime.
# Dataclass: HandoffConfig
#   Role: Defines handoff parameters for specialist child runtimes.
#   Called from: analytics.agent_orchestrator.agent_runtime.AgentRuntime.handoff_to_specialist
#   Invokes: n/a
#   Why: Enables supervisor flows to invoke scoped child runtimes while preserving receipts.
# --- End Analytics Function/Class Map ---
from __future__ import annotations

import asyncio
import logging
import time
import uuid
from datetime import datetime, timezone
from dataclasses import dataclass, field
from typing import Any, Dict, Mapping, Optional, Iterable

from agents import Agent, Runner
from agents.result import RunResultStreaming
from agents.run import RunConfig
from agents.model_settings import ModelSettings
from openai.types.shared import Reasoning

from analytics.core import telemetry
from analytics.core.events import EventEmitter
from analytics.validators import sanitize_for_json
from analytics.flows.agents_stream_bridge import AgentsStreamBridge, ForbiddenToolCallError
from analytics.flows.schedulers import FlowMode, apply_mode_metadata

from .agent_plan import AGENTIC_REVISION_PLAN, PlanNode, PlanNodeStatus, PlanState, PlanTemplate
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
    tool_allowlist: Optional[Iterable[str]] = None
    guardrail_payload: Optional[Mapping[str, Any]] = None
    parallel_tool_calls: Optional[bool] = None
    tool_choice: Optional[Any] = None
    tool_choice_body: Optional[Mapping[str, Any]] = None
    force_tool_calls: bool = False


@dataclass
class AgentRuntimeResult:
    """Structured response emitted after an orchestrated agent run completes."""

    run_result: RunResultStreaming
    plan_state: PlanState
    final_output: Dict[str, Any]
    run_id: Optional[str]
    trace_id: Optional[str]


@dataclass
class HandoffConfig:
    """Parameters for spawning a specialist child runtime."""

    specialist: str
    tool_allowlist: Optional[Iterable[str]] = None
    context: Optional[Mapping[str, Any]] = None


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
        self._tool_allowlist = {
            str(tool).strip() for tool in (config.tool_allowlist or []) if isinstance(tool, str) and str(tool).strip()
        }
        self._guardrail_payload = dict(config.guardrail_payload) if isinstance(config.guardrail_payload, Mapping) else None
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
        previous_lane_ts = self._lane_decision_timestamp()
        template = plan_template or self._config.plan_template or PlanTemplate(
            name="single_agent_default",
            nodes=(),
        )
        agentic_revision = self._is_agentic_revision(template, run_context)
        if agentic_revision and template.name != AGENTIC_REVISION_PLAN.name:
            template = AGENTIC_REVISION_PLAN
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
        # If caller provided a mapping (preferred), use it as metadata; otherwise fall back to attrs on the run_context object.
        if isinstance(run_context, Mapping):
            context_payload["metadata"] = dict(run_context)
        else:
            metadata: Dict[str, Any] = {}
            # Pull a nested agent_metadata payload if present (populated by SingleAgentController).
            agent_meta = getattr(run_context, "agent_metadata", None)
            if isinstance(agent_meta, Mapping):
                metadata.update(dict(agent_meta))
            # Also serialize any dataclass-like attributes the caller set.
            for attr in ("intent", "plan", "provisional_plan", "template", "selected_template_id", "slot_statuses", "clarification_answers", "assumptions", "follow_up_route"):
                if hasattr(run_context, attr):
                    try:
                        metadata[attr] = sanitize_for_json(copy.deepcopy(getattr(run_context, attr)))
                    except Exception:
                        metadata[attr] = getattr(run_context, attr)
            context_payload["metadata"] = metadata
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
            bridge = AgentsStreamBridge(
                flow_mode=self._flow_mode,
                queue=self._queue,
                logger=self._logger,
                tool_allowlist=self._tool_allowlist,
                guardrail_metadata=self._guardrail_payload,
            )
            run_result = await bridge.forward(run_result_streaming)
        except ForbiddenToolCallError as exc:
            self._logger.exception("Agent runtime blocked a tool call")
            plan_state.mark_finished(active_node_name, PlanNodeStatus.FAILED)
            self._memory.persist_plan_state(plan_state)
            await self._publish_plan(plan_state)
            telemetry.tool_iteration(
                tool="agent_controller",
                status="failed",
                step=active_node_name,
                session_id=session_id,
                flow="single-agent",
                details={"error": str(exc), "tool": getattr(exc, "tool_name", None)},
            )
            raise
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
        if agentic_revision and not self._has_fresh_lane_decision(previous_lane_ts):
            # Seed a default lane decision to keep revision flows moving even if the planner
            # did not emit an explicit lane choice.
            try:
                self._memory.record_lane_decision(
                    {
                        "lane": "narrative",
                        "ts": datetime.now(timezone.utc).isoformat(),
                        "source": "agent_runtime_fallback",
                        "rationale": "default_lane_for_revision",
                    }
                )
            except Exception:
                self._logger.debug("Failed to record fallback lane decision", exc_info=True)
            if not self._has_fresh_lane_decision(previous_lane_ts):
                await self._handle_missing_lane_decision(
                    session_id=session_id,
                    plan_state=plan_state,
                    node_name=active_node_name,
                )
                raise RuntimeError("agent_lane_decision_missing")
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

    async def force_call_tool(
        self,
        tool_name: str,
        payload: Optional[Mapping[str, Any]] = None,
        *,
        emit_event: bool = True,
    ) -> None:
        """Programmatically emit a tool receipt and (optionally) an SSE event without model initiation."""

        if not getattr(self._config, "force_tool_calls", False):
            return
        safe_payload = {}
        if isinstance(payload, Mapping):
            try:
                safe_payload = sanitize_for_json(dict(payload))
            except Exception:
                safe_payload = dict(payload)

        receipt = {
            "status": "completed",
            "tool": tool_name,
            "forced": True,
            "payload": safe_payload,
        }

        try:
            self._memory.record_tool_receipt(tool_name, receipt)
        except Exception:
            self._logger.debug("Failed to record forced tool receipt for %s", tool_name, exc_info=True)

        if not emit_event:
            return

        event = EventEmitter.status(tool_name, "forced_tool_call")
        event["event"] = tool_name
        event.setdefault("data", {}).update(receipt)
        event = apply_mode_metadata(event, self._flow_mode)
        await self._queue.put(event)

    async def handoff_to_specialist(
        self,
        config: HandoffConfig,
        *,
        payload: Mapping[str, Any],
    ) -> Dict[str, Any]:
        """Spawn a specialist handoff by emitting a scoped receipt and SSE event."""

        handoff_payload = {
            "specialist": config.specialist,
            "tool_allowlist": list(config.tool_allowlist or ()),
            "payload": sanitize_for_json(dict(payload)) if isinstance(payload, Mapping) else {},
        }
        if isinstance(config.context, Mapping):
            handoff_payload["context"] = sanitize_for_json(dict(config.context))

        receipt = {"status": "completed", **handoff_payload}
        try:
            self._memory.record_tool_receipt("agent_handoff", receipt)
        except Exception:
            self._logger.debug("Failed to record specialist handoff receipt", exc_info=True)

        event = EventEmitter.status("agent_handoff", "specialist handoff")
        event["event"] = "agent_handoff"
        event.setdefault("data", {}).update(receipt)
        event = apply_mode_metadata(event, self._flow_mode)
        await self._queue.put(event)
        return receipt

    def _build_run_config(self) -> RunConfig:
        settings_kwargs: Dict[str, Any] = {}
        if self._config.temperature is not None:
            settings_kwargs["temperature"] = self._config.temperature
        if self._config.reasoning_effort is not None:
            settings_kwargs["reasoning"] = Reasoning(effort=self._config.reasoning_effort)
        if self._config.parallel_tool_calls is not None:
            settings_kwargs["parallel_tool_calls"] = self._config.parallel_tool_calls
        if self._config.tool_choice is not None:
            settings_kwargs["tool_choice"] = self._config.tool_choice
        extra_body: Dict[str, Any] = {}
        if isinstance(self._config.tool_choice_body, Mapping) and self._config.tool_choice_body:
            extra_body["tool_choice"] = dict(self._config.tool_choice_body)
        if self._config.parallel_tool_calls is not None and "parallel_tool_calls" not in settings_kwargs:
            extra_body["parallel_tool_calls"] = self._config.parallel_tool_calls
        if extra_body:
            settings_kwargs["extra_body"] = extra_body
        model_settings = ModelSettings(**settings_kwargs) if settings_kwargs else None
        trace_id = f"trace_{uuid.uuid4()}"
        return RunConfig(
            model=self._config.model,
            model_settings=model_settings,
            trace_id=trace_id,
        )

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
        if getattr(self._config, "force_tool_calls", False):
            try:
                await self.force_call_tool(
                    "workflow_complete",
                    {"total_elapsed_ms": total_elapsed_ms},
                    emit_event=False,
                )
            except Exception:
                self._logger.debug("Failed to record forced workflow_complete receipt", exc_info=True)
        await self._queue.put(event)

    def _extract_final_output(self, result: RunResultStreaming) -> Dict[str, Any]:
        final_output = getattr(result, "final_output", None)
        if isinstance(final_output, Mapping):
            return dict(final_output)
        if isinstance(final_output, str):
            return {"analysis": final_output, "analysis_length": len(final_output)}
        return {"analysis": str(final_output), "analysis_length": len(str(final_output))}

    def _lane_decision_timestamp(self) -> Optional[str]:
        try:
            decision = self._memory.get_lane_decision()
        except Exception:  # pragma: no cover - defensive
            return None
        if isinstance(decision, Mapping):
            ts_value = decision.get("ts")
            if ts_value is None:
                return None
            return str(ts_value)
        return None

    def _has_fresh_lane_decision(self, previous_ts: Optional[str]) -> bool:
        try:
            latest = self._memory.get_lane_decision()
        except Exception:  # pragma: no cover - defensive
            return False
        if not isinstance(latest, Mapping):
            return False
        latest_ts = latest.get("ts")
        if latest_ts is None:
            return previous_ts is None
        return str(latest_ts) != str(previous_ts or "")

    def _extract_revision_directive(self, run_context: Optional[Any]) -> Optional[Any]:
        if run_context is None:
            return None
        directive = getattr(run_context, "revision_directive", None)
        if directive is not None:
            return directive
        if isinstance(run_context, Mapping):
            candidate = run_context.get("revision_directive")
            if candidate is not None:
                return candidate
        metadata = getattr(run_context, "metadata", None)
        if isinstance(metadata, Mapping):
            return metadata.get("revision_directive")
        return None

    def _is_agentic_revision(self, template: PlanTemplate, run_context: Optional[Any]) -> bool:
        if template and template.name == AGENTIC_REVISION_PLAN.name:
            return True
        directive = self._extract_revision_directive(run_context)
        return bool(directive and getattr(directive, "agentic", False))

    async def _handle_missing_lane_decision(
        self,
        *,
        session_id: Optional[str],
        plan_state: PlanState,
        node_name: str,
    ) -> None:
        node = plan_state.nodes.get(node_name)
        if node is not None:
            try:
                node.increment_retry()
            except Exception:  # pragma: no cover - defensive
                node.status = PlanNodeStatus.PENDING
                node.started_at = None
                node.finished_at = None
        self._memory.persist_plan_state(plan_state)
        payload = {
            "required_action": "agent_lane_decision",
            "reason": "lane_decision_missing",
            "agentic_revision": True,
        }
        if session_id:
            payload["session_id"] = session_id
        try:
            await self._event_bus.publish("analysis_revision_blocked", payload)
        except Exception:  # pragma: no cover - defensive
            self._logger.exception("Failed to publish analysis_revision_blocked event")
        telemetry.tool_iteration(
            tool="agent_controller",
            status="blocked",
            step=node_name,
            session_id=session_id,
            flow="single-agent",
            details={"reason": "lane_decision_missing"},
        )
