# --- Runtime Function/Class Map ---
# Class: A2UIRuntime
#   Role: Orchestrate the A2UI dashboard runtime loop (render -> clarifications -> data updates).
#   Called from: backend.generative_ui.routes.dashboard; can be imported by tests.
#   Invokes: A2UIMessageEmitter, A2UIAgent (selection/execute), LayoutPlanner, clarification helpers, TraceStore.
#   Why: Centralizes the runtime loop to enable incremental streaming, layout overrides, and tracing.
# Method: stream_dashboard
#   Role: Async generator that yields A2UI/Audit messages for SSE streaming.
#   Called from: A2UIRuntime consumers (routes/tests).
#   Invokes: agent selection/validation, layout planner, clarifications, execute_skill, trace recording.
#   Why: Provides a structured, step-aware runtime with full execution traces.
# Method: process_action
#   Role: Handle user actions through the runtime (trace + incremental data patches).
#   Called from: backend.generative_ui.routes.dashboard.handle_action
#   Invokes: A2UIAgent.execute_skill_streaming, TraceStore
#   Why: Ensures user actions respect runtime tracing + partial invalidation.
# --- End Runtime Function/Class Map ---
"""
Lightweight A2UI runtime orchestrator.

This module wraps the existing A2UI agent + emitter into a reusable runtime
loop that can be incrementally extended (layout overrides, step-level audits,
pause/resume on clarifications, execution traces, etc.).
"""

from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path
from typing import AsyncGenerator, Optional, Dict, List, Any

# Load .env before reading USE_SDK_FLOW
from dotenv import load_dotenv
_MODULE_DIR = Path(__file__).parent
load_dotenv(dotenv_path=_MODULE_DIR.parent / ".env", override=False)

from .a2ui.emitter import A2UIMessageEmitter
from .agent_v2 import A2UIAgent
from .layout_planner import LayoutOverride, LayoutPlanner
from .clarification import (
    await_clarification_response,
    build_visual_clarification,
    clarification_to_sse_event,
)
from .models.dashboard_state import DashboardState
from .traces import RunTrace, get_trace_store

# SDK Flow feature flag (Optimization #1: Activate SDK-Native Tool Execution)
# SDK flow is EXPERIMENTAL - set USE_SDK_FLOW=true to test LLM-driven execution
# Default: false (uses proven standard agent execution path)
USE_SDK_FLOW = os.getenv("USE_SDK_FLOW", "false").lower() in ("true", "1", "yes")

logger = logging.getLogger(__name__)
if USE_SDK_FLOW:
    logger.info("SDK Flow enabled: EXPERIMENTAL LLM-driven execution path")
else:
    logger.info("SDK Flow disabled: Using standard agent execution path (production)")


class A2UIRuntime:
    """
    Runtime orchestrator for A2UI dashboards.
    
    Class: A2UIRuntime — manages the full dashboard lifecycle.
    Called from: backend.generative_ui.routes.dashboard.stream_dashboard
    Invokes: A2UIAgent, LayoutPlanner, TraceStore, clarification helpers
    Purpose: Structured runtime with tracing, layout planning, and incremental streaming.
    """
    
    # SSE Heartbeat configuration (prevents proxy timeouts)
    HEARTBEAT_INTERVAL_SECONDS = 15.0
    HEARTBEAT_EVENT_NAME = "heartbeat"

    def __init__(self, agent: A2UIAgent, layout_planner: Optional[LayoutPlanner] = None) -> None:
        """
        Initialize runtime with agent and optional layout planner.
        
        Args:
            agent: The A2UI agent for skill selection/execution
            layout_planner: Optional layout planner (defaults to standard planner)
        """
        self.agent = agent
        self.layout_planner = layout_planner or LayoutPlanner()
        self.trace_store = get_trace_store()
        self._last_heartbeat = 0.0
        
        # Optional SDK Flow for LLM-driven execution (Optimization #1)
        # Uses ClaudeSDKClient with automatic MCP tool execution
        self._sdk_flow = None
        if USE_SDK_FLOW:
            try:
                from .sdk_flow import create_sdk_flow
                self._sdk_flow = create_sdk_flow()
                if self._sdk_flow:
                    logger.info("SDK Flow initialized for runtime (ClaudeSDKClient mode)")
                else:
                    logger.warning("SDK Flow not available - SDK not installed")
            except ImportError as e:
                logger.warning("SDK Flow import failed: %s", e)

    def _maybe_heartbeat(self) -> Optional[str]:
        """
        Emit a heartbeat event if enough time has passed since the last one.
        
        Returns SSE-formatted heartbeat string or None if not needed.
        Prevents proxy/load balancer timeouts during long-running operations.
        """
        now = time.time()
        if now - self._last_heartbeat >= self.HEARTBEAT_INTERVAL_SECONDS:
            self._last_heartbeat = now
            return f"event: {self.HEARTBEAT_EVENT_NAME}\ndata: {{}}\n\n"
        return None

    async def _execute_via_sdk_flow(
        self,
        skill_id: str,
        user_query: str,
        parameters: Dict[str, Any],
        emitter: "A2UIMessageEmitter",
        trace: "RunTrace",
        data_model_out: Dict[str, Any],  # Mutable output container
    ) -> AsyncGenerator[str, None]:
        """
        Execute skill using SDK flow for LLM-driven component generation.
        
        Function: _execute_via_sdk_flow
        Called from: stream_dashboard (when USE_SDK_FLOW enabled)
        Invokes: A2UISDKFlow.execute_with_skill_context
        Why: Enables LLM to see data and generate intelligent A2UI outputs.
        
        Args:
            skill_id: Skill identifier (e.g., 'a2ui_margin_analysis')
            user_query: Original user question
            parameters: Extracted slots (tickers, metric, time_range, etc.)
            emitter: A2UI message emitter for this surface
            trace: Run trace for debugging
            data_model_out: Mutable dict to populate with collected data model
            
        Yields:
            A2UI JSON messages (audit, data_update, surface_update)
        """
        if not self._sdk_flow:
            raise RuntimeError("SDK flow not initialized")
        
        message_count = 0
        
        yield emitter.audit("sdk_flow_started", f"skill={skill_id}")
        message_count += 1
        
        trace.add_step("sdk_flow_execute", details={
            "skill_id": skill_id,
            "parameters": parameters,
        })
        
        async for chunk in self._sdk_flow.execute_with_skill_context(
            skill_id=skill_id,
            user_query=user_query,
            parameters=parameters,
        ):
            chunk_type = chunk.get("type")
            
            if chunk_type == "audit":
                yield emitter.audit(chunk.get("event", "sdk_event"), chunk.get("details"))
                message_count += 1
                trace.add_step(f"sdk_audit::{chunk.get('event', 'unknown')}")
                
            elif chunk_type == "data_update":
                # Extract data payload and emit
                data = chunk.get("data", {})
                data_model_out.update(data)  # Update the mutable output container
                yield emitter.data_update(data, path=chunk.get("path", "/data"))
                message_count += 1
                trace.add_step("sdk_data_update", details={"keys": list(data.keys())})
                
            elif chunk_type == "surface_update":
                # SDK flow can emit layout changes
                components = chunk.get("components", [])
                if components:
                    yield emitter.surface_update(components)
                    message_count += 1
                    trace.add_step("sdk_surface_update", details={"count": len(components)})
                    
            elif chunk_type == "follow_ups":
                # Store follow-ups in data model
                suggestions = chunk.get("suggestions", [])
                if suggestions:
                    data_model_out["follow_ups"] = suggestions
                    yield emitter.data_update({"follow_ups": suggestions}, path="/data")
                    message_count += 1
                    
            elif chunk_type == "error":
                error_msg = chunk.get("message", "Unknown SDK flow error")
                trace.add_step("sdk_error", error=error_msg, success=False)
                raise RuntimeError(error_msg)
                
            elif chunk_type == "done":
                trace.add_step("sdk_flow_complete", success=chunk.get("success", True))
        
        yield emitter.audit("sdk_flow_completed", f"messages={message_count}")

    async def stream_dashboard(self, state: DashboardState) -> AsyncGenerator[str, None]:
        """
        Stream the full dashboard lifecycle as JSON strings (ready for SSE wrapping).

        Steps:
        1) beginRendering + trace initialization
        2) surfaceUpdate (with optional layout override)
        3) seed data
        4) optional clarification pause/resume
        5) execute skill + incremental dataModelUpdate
        6) done sentinel + trace completion
        
        All steps are recorded in a RunTrace for debugging.
        """
        emitter = A2UIMessageEmitter(surface_id=state.surface_id, catalog_id=state.catalog_id)
        
        # Initialize trace
        trace = self.trace_store.create(
            dashboard_id=state.dashboard_id,
            question=state.question
        )
        message_count = 0
        self._last_heartbeat = time.time()
        
        try:
            from .models.dashboard_state import RuntimeStatus
            state.transition(RuntimeStatus.streaming)
        except Exception:
            pass

        # 1) beginRendering + stream_started audit event
        yield emitter.begin_rendering()
        message_count += 1
        
        # Emit standardized stream_started audit event
        yield emitter.audit("stream_started", f"dashboard_id={state.dashboard_id}")
        message_count += 1

        try:
            run_signature = state.signature()

            # Skill selection
            step_start = time.time()
            selection = self.agent.selection_from_plan(state.plan_json)
            self.agent._validate_selection(selection)
            skill = self.agent.skill_lookup[selection.skill_id]
            context = self.agent._build_render_context(selection, skill)
            
            trace.skill_id = selection.skill_id
            trace.tickers = selection.tickers
            trace.metric = selection.metric
            trace.time_range = selection.time_range
            trace.add_step(
                "skill_selection",
                details={
                    "skill_id": selection.skill_id,
                    "tickers": selection.tickers,
                    "metric": selection.metric,
                    "time_range": selection.time_range,
                },
                duration_ms=(time.time() - step_start) * 1000
            )
            
            # Emit skill_selected audit event for frontend progress feedback
            yield emitter.audit("skill_selected", f"skill={skill.name} ({selection.skill_id})")
            message_count += 1

            # Layout planning
            step_start = time.time()
            layout_override: Optional[LayoutOverride] = self.layout_planner.propose_override(skill, state.question)
            components = emitter.build_components_for_skill(
                skill,
                context,
                variant=layout_override.layout_variant if layout_override else None,
                widget_order=layout_override.widget_order if layout_override else None,
                hidden_widgets=layout_override.hidden_widgets if layout_override else None,
                emphasis=layout_override.emphasis if layout_override else None,
            )
            
            if layout_override:
                trace.layout_override = {
                    "variant": layout_override.layout_variant,
                    "emphasis": layout_override.emphasis,
                    "widget_order": layout_override.widget_order,
                    "hidden_widgets": layout_override.hidden_widgets,
                }
                try:
                    state.update_plan_fields(layout_variant=layout_override.layout_variant)
                    state.update_params({"layout_override": trace.layout_override})
                except Exception:
                    pass
                yield emitter.audit(
                    "layout_override", 
                    f"variant={layout_override.layout_variant or 'default'}, emphasis={layout_override.emphasis or 'none'}"
                )
                message_count += 1
            
            trace.add_step(
                "layout_planning",
                details={
                    "layout_override": trace.layout_override,
                    "component_count": len(components) if components else 0,
                },
                duration_ms=(time.time() - step_start) * 1000
            )
            
            yield emitter.surface_update(components)
            message_count += 1

            # Seed data
            seed_data = {
                "title": context.title,
                "ticker": context.primary_ticker,
                "primary_ticker": context.primary_ticker,
                "tickers": context.tickers,
                "time_range": context.time_range,
                "metric": context.metric,
            }
            yield emitter.data_update(seed_data)
            message_count += 1
            trace.add_step("seed_data", details={"keys": list(seed_data.keys())})

            # Cache check before expensive execution
            cached_run = state.find_cached_run(run_signature)
            if cached_run and cached_run.data_json:
                yield emitter.audit("cache_hit", f"reused run {cached_run.run_id}")
                message_count += 1
                yield emitter.data_update(cached_run.data_json)
                message_count += 1
                trace.add_step(
                    "cache_hit",
                    details={"run_id": cached_run.run_id},
                    success=True,
                )
                trace.message_count = message_count
                trace.complete(success=True)
                self.trace_store.persist(trace)
                try:
                    from .models.dashboard_state import RuntimeStatus
                    state.transition(RuntimeStatus.complete)
                except Exception:
                    pass
                yield json.dumps({"done": True})
                return

            # Clarification gate
            clarification = build_visual_clarification(state.question, selection, state.plan_json, state.params)
            if clarification:
                trace.add_step(
                    "clarification_request",
                    details={
                        "request_id": clarification.request_id,
                        "fields": [f.field_id for f in clarification.fields],
                    }
                )
                try:
                    from .models.dashboard_state import RuntimeStatus
                    state.transition(RuntimeStatus.awaiting_clarification)
                except Exception:
                    pass
                
                state.update_params({
                    "pending_clarification": clarification.model_dump(),
                    "clarification_responses": state.params.get("clarification_responses") or {},
                })
                yield clarification_to_sse_event(clarification)
                message_count += 1
                
                step_start = time.time()
                await await_clarification_response(state, clarification.request_id, clarification.timeout_seconds)
                trace.add_step(
                    "clarification_response",
                    duration_ms=(time.time() - step_start) * 1000
                )
                try:
                    from .models.dashboard_state import RuntimeStatus
                    state.transition(RuntimeStatus.streaming)
                except Exception:
                    pass

                # Re-process after clarification
                selection = self.agent.selection_from_plan(state.plan_json)
                self.agent._validate_selection(selection)
                skill = self.agent.skill_lookup[selection.skill_id]
                context = self.agent._build_render_context(selection, skill)

                layout_override = self.layout_planner.propose_override(skill, state.question)
                components = emitter.build_components_for_skill(
                    skill,
                    context,
                    variant=layout_override.layout_variant if layout_override else None,
                    widget_order=layout_override.widget_order if layout_override else None,
                    hidden_widgets=layout_override.hidden_widgets if layout_override else None,
                    emphasis=layout_override.emphasis if layout_override else None,
                )
                if layout_override:
                    trace.layout_override = {
                        "variant": layout_override.layout_variant,
                        "emphasis": layout_override.emphasis,
                        "widget_order": layout_override.widget_order,
                        "hidden_widgets": layout_override.hidden_widgets,
                    }
                    try:
                        state.update_plan_fields(layout_variant=layout_override.layout_variant)
                        state.update_params({"layout_override": trace.layout_override})
                    except Exception:
                        pass
                yield emitter.surface_update(components)
                message_count += 1
                
                seed_data = {
                    "title": context.title,
                    "ticker": context.primary_ticker,
                    "primary_ticker": context.primary_ticker,
                    "tickers": context.tickers,
                    "time_range": context.time_range,
                    "metric": context.metric,
                }
                yield emitter.data_update(seed_data)
                message_count += 1

                # Recompute signature after clarification adjustments
                run_signature = state.signature()

            # Execute skill - use SDK flow if enabled, else standard agent execution
            yield emitter.audit("runtime_step_started", "execute_skill")
            message_count += 1

            step_start = time.time()
            result = None
            
            # SDK Flow path: LLM-driven execution (Optimization #1)
            if self._sdk_flow and USE_SDK_FLOW:
                yield emitter.audit("execution_mode", "sdk_flow")
                message_count += 1
                
                sdk_data_model: Dict[str, Any] = {}
                async for sdk_msg in self._execute_via_sdk_flow(
                    skill_id=selection.skill_id,
                    user_query=state.question,
                    parameters={
                        "tickers": selection.tickers,
                        "metric": selection.metric,
                        "time_range": selection.time_range,
                    },
                    emitter=emitter,
                    trace=trace,
                    data_model_out=sdk_data_model,  # Collect data model here
                ):
                    yield sdk_msg
                    message_count += 1
                
                # Create a synthetic result for state persistence
                from .agent_v2 import A2UIRunResult
                result = A2UIRunResult(
                    data_model=sdk_data_model,
                    citations=[],
                )
            else:
                # Standard agent execution path
                yield emitter.audit("execution_mode", "agent")
                message_count += 1
                
                async for chunk in self.agent.execute_skill_streaming(skill, selection):
                    if chunk.audit_event:
                        yield emitter.audit(chunk.audit_event, chunk.audit_details)
                        message_count += 1
                    if chunk.data_patch is not None:
                        yield emitter.data_update(chunk.data_patch, path=chunk.data_path)
                        message_count += 1
                    trace.add_step(
                        f"execute_skill::{chunk.step}",
                        details={
                            "path": chunk.data_path,
                            "keys": list((chunk.data_patch or {}).keys()),
                            "audit": chunk.audit_event,
                        },
                        success=True,
                    )
                    if chunk.final_result:
                        result = chunk.final_result

            skill_duration = (time.time() - step_start) * 1000
            yield emitter.audit("runtime_step_completed", "execute_skill")
            message_count += 1

            trace.add_step(
                "execute_skill_complete",
                details={
                    "data_keys": list(result.data_model.keys()) if result else [],
                    "citation_count": len(result.citations) if result else 0,
                    "execution_mode": "sdk_flow" if (self._sdk_flow and USE_SDK_FLOW) else "agent",
                },
                duration_ms=skill_duration,
                success=result is not None,
            )

            if result is None:
                raise RuntimeError("Skill execution returned no result")

            state.add_run(
                result.data_model,
                result.citations,
                trace_id=trace.trace_id,
                layout_override=trace.layout_override,
                plan_signature=run_signature,
                params_signature=run_signature,
            )

            # Complete trace
            trace.message_count = message_count
            trace.complete(success=True)
            self.trace_store.persist(trace)
            try:
                from .models.dashboard_state import RuntimeStatus
                state.transition(RuntimeStatus.complete)
            except Exception:
                pass
            
            # Emit stream_completed audit event
            yield emitter.audit("stream_completed", "success=true")
            message_count += 1
            
            yield json.dumps({"done": True})
            
        except Exception as exc:
            trace.add_step("error", error=str(exc), success=False)
            trace.message_count = message_count
            trace.complete(success=False, error=str(exc))
            self.trace_store.persist(trace)
            try:
                from .models.dashboard_state import RuntimeStatus
                state.transition(RuntimeStatus.error)
            except Exception:
                pass
            
            # Emit dedicated error audit event for frontend error handling
            yield emitter.audit("error", f"type=agent_error, message={str(exc)[:200]}")
            message_count += 1
            
            for msg in emitter.error_surface("agent_error", str(exc)):
                yield msg
            yield json.dumps({"done": True, "error": True})

    async def process_action(self, state: DashboardState, action: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle a user action through the runtime pipeline (with tracing + streaming).

        Returns a structured response containing the final data model and the
        intermediate data patches applied, so the caller can apply partial
        invalidation without reloading the whole dashboard.
        """
        action_name = action.get("name")
        context = action.get("context", {}) or {}
        trace = self.trace_store.create(dashboard_id=state.dashboard_id, question=state.question)
        trace.add_step("user_action_received", details={"name": action_name, "context": context})
        try:
            from .models.dashboard_state import RuntimeStatus
            state.transition(RuntimeStatus.streaming)
        except Exception:
            pass

        known_actions = {"change_timeframe", "add_ticker", "export_csv"}
        if action_name not in known_actions:
            trace.add_step("action_unknown", details={"name": action_name})
            trace.complete(success=True)
            self.trace_store.persist(trace)
            return {"status": "unknown_action", "action": action_name}

        # Mutate plan/params based on the action
        if action_name == "change_timeframe":
            new_timeframe = context.get("timeframe", "1M")
            state.update_params({"timeRange": new_timeframe})
            state.update_plan_fields(time_range=new_timeframe)
        elif action_name == "add_ticker":
            new_ticker = context.get("ticker")
            if new_ticker:
                tickers = list(state.plan.tickers or [])
                if new_ticker not in tickers:
                    tickers.append(new_ticker)
                    state.update_plan_fields(tickers=tickers, peers=tickers[1:])
                    state.update_params({"peers": tickers[1:]})
        elif action_name == "export_csv":
            trace.add_step("action_export_stub", details={"status": "not_implemented"})
            trace.complete(success=True)
            return {
                "status": "success",
                "action": action_name,
                "download_url": f"/api/dash/{state.dashboard_id}/export/csv",
            }

        run_signature = state.signature()

        agent = self.agent
        selection = agent.selection_from_plan(state.plan_json)
        agent._validate_selection(selection)
        skill = agent.skill_lookup[selection.skill_id]

        data_updates: List[Dict[str, Any]] = []
        result = None
        async for chunk in agent.execute_skill_streaming(skill, selection):
            if chunk.data_patch is not None:
                data_updates.append({"path": chunk.data_path, "data": chunk.data_patch})
            trace.add_step(
                f"action::{chunk.step}",
                details={
                    "path": chunk.data_path,
                    "keys": list((chunk.data_patch or {}).keys()),
                    "audit": chunk.audit_event,
                },
                success=True,
            )
            if chunk.final_result:
                result = chunk.final_result

        if not result:
            trace.add_step("action_error", success=False, error="No result from action execution")
            trace.complete(success=False, error="No result from action execution")
            self.trace_store.persist(trace)
            return {"status": "error", "action": action_name, "error": "No result produced"}

        state.add_run(
            result.data_model,
            result.citations,
            trace_id=trace.trace_id,
            layout_override=state.params.model_dump().get("layout_override"),
            plan_signature=run_signature,
            params_signature=run_signature,
        )
        trace.message_count = len(data_updates)
        trace.complete(success=True)
        self.trace_store.persist(trace)

        return {
            "status": "success",
            "action": action_name,
            "data": result.data_model,
            "data_updates": data_updates,
            "updated_params": state.params.model_dump(),
            "trace_id": trace.trace_id,
            "data_path": "/data",
        }


__all__ = ["A2UIRuntime"]
