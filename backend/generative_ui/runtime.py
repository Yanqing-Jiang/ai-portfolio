# --- Runtime Function/Class Map ---
# Class: A2UIRuntime
#   Role: Orchestrate the A2UI dashboard runtime loop (render -> clarifications -> data updates).
#   Called from: backend.generative_ui.routes.dashboard; can be imported by tests.
#   Invokes: A2UIMessageEmitter, A2UIAgent (selection), LayoutPlanner, clarification helpers, TraceStore.
#   Why: Centralizes the runtime loop for streaming, layout overrides, and tracing.
# Method: stream_dashboard
#   Role: Async generator that yields A2UI/Audit messages for SSE streaming.
#   Called from: A2UIRuntime consumers (routes/tests).
#   Invokes: agent selection/validation, layout planner, clarifications, trace recording.
#   Why: Provides a structured, step-aware stream with full execution traces.
# Method: process_action
#   Role: Handle user actions through the runtime (trace + incremental data patches).
#   Called from: backend.generative_ui.routes.dashboard.handle_action
#   Invokes: A2UIAgent.execute_skill, TraceStore
#   Why: Ensures user actions respect execution flow and partial invalidation.
# --- End Runtime Function/Class Map ---
"""
Lightweight A2UI runtime orchestrator.

This module wraps the existing A2UI agent + emitter into a reusable runtime
loop that can be incrementally extended (layout overrides, step-level audits,
pause/resume on clarifications, execution traces, etc.).

Note: This version uses direct agent execution instead of SDK flow to avoid
cold-boot overhead (~2-12s) that causes timeouts on resource-constrained
backends like Render.com.
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import AsyncGenerator, Optional, Dict, List, Any

# Load .env for runtime settings
from dotenv import load_dotenv
_MODULE_DIR = Path(__file__).parent
load_dotenv(dotenv_path=_MODULE_DIR.parent / ".env", override=False)

from .a2ui.emitter import A2UIMessageEmitter
from .agent_v2 import A2UIAgent, A2UIRunResult
from .layout_planner import LayoutOverride, LayoutPlanner
from .clarification import (
    await_clarification_response,
    build_visual_clarification,
    clarification_to_sse_event,
)
from .models.dashboard_state import DashboardState
from .traces import RunTrace, get_trace_store

logger = logging.getLogger(__name__)


def _normalize_comparison_kpis(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Function: _normalize_comparison_kpis — map ticker-prefixed KPIs to generic keys.
    Called from: A2UIRuntime.stream_dashboard
    Invokes: n/a
    Why: The layout expects keys like 'gross_margin', but peer comparison skills
         return 'qcom_gross_margin', 'avgo_gross_margin'. This adds generic keys
         using the primary ticker's values and comparison delta for display.
    
    Example transformation:
        Input:  {"qcom_gross_margin": 55.5, "avgo_gross_margin": 67.9, ...}
        Output: {"qcom_gross_margin": 55.5, "avgo_gross_margin": 67.9, 
                 "gross_margin": 55.5, "gross_margin_compare": 67.9, ...}
    """
    kpis = data.get("kpis")
    if not isinstance(kpis, dict):
        return data
    
    # Detect primary ticker from data
    primary_ticker = data.get("primary_ticker", "").lower()
    tickers = data.get("tickers", [])
    
    if not primary_ticker and tickers:
        primary_ticker = tickers[0].lower()
    
    if not primary_ticker:
        return data
    
    # Find secondary ticker for comparison
    secondary_ticker = None
    if isinstance(tickers, list) and len(tickers) >= 2:
        for t in tickers:
            if t.lower() != primary_ticker:
                secondary_ticker = t.lower()
                break
    
    # Map of generic key -> (primary_prefixed_key, secondary_prefixed_key)
    margin_keys = ["gross_margin", "operating_margin", "net_margin"]
    
    normalized = dict(kpis)  # Copy original
    
    for base_key in margin_keys:
        primary_key = f"{primary_ticker}_{base_key}"
        
        # Add generic key from primary ticker
        if primary_key in kpis:
            normalized[base_key] = kpis[primary_key]
            
            # Add comparison value from secondary ticker if available
            if secondary_ticker:
                secondary_key = f"{secondary_ticker}_{base_key}"
                if secondary_key in kpis:
                    # Store comparison value for potential delta display
                    normalized[f"{base_key}_compare"] = kpis[secondary_key]
                    # Calculate delta (primary - secondary)
                    try:
                        primary_val = float(kpis[primary_key])
                        secondary_val = float(kpis[secondary_key])
                        normalized[f"{base_key}_delta"] = round(primary_val - secondary_val, 2)
                    except (TypeError, ValueError):
                        pass
    
    data["kpis"] = normalized
    return data


class A2UIRuntime:
    """
    Runtime orchestrator for A2UI dashboards.
    
    Class: A2UIRuntime - manages the full dashboard lifecycle.
    Called from: backend.generative_ui.routes.dashboard.stream_dashboard
    Invokes: A2UIAgent, LayoutPlanner, TraceStore, clarification helpers
    Purpose: Structured runtime with tracing, layout planning, and streaming.
    
    Note: Uses direct agent execution instead of SDK flow for faster response times.
    """
    
    # SSE Heartbeat configuration (prevents proxy timeouts)
    HEARTBEAT_INTERVAL_SECONDS = 15.0
    HEARTBEAT_EVENT_NAME = "heartbeat"

    def __init__(self, agent: A2UIAgent, layout_planner: Optional[LayoutPlanner] = None) -> None:
        """
        Method: A2UIRuntime.__init__ - configure runtime dependencies.
        Called from: backend.generative_ui.routes.dashboard.stream_dashboard.
        Invokes: backend.generative_ui.traces.get_trace_store.
        Why: Prepares runtime state and tracing.
        """
        self.agent = agent
        self.layout_planner = layout_planner or LayoutPlanner()
        self.trace_store = get_trace_store()
        self._last_heartbeat = 0.0

    def _maybe_heartbeat(self) -> Optional[str]:
        """
        Method: A2UIRuntime._maybe_heartbeat - emit SSE heartbeat when idle.
        Called from: backend.generative_ui.runtime.A2UIRuntime.stream_dashboard.
        Invokes: time.time.
        Why: Prevents proxy timeouts during long-running streams.
        """
        now = time.time()
        if now - self._last_heartbeat >= self.HEARTBEAT_INTERVAL_SECONDS:
            self._last_heartbeat = now
            return f"event: {self.HEARTBEAT_EVENT_NAME}\ndata: {{}}\n\n"
        return None

    async def stream_dashboard(self, state: DashboardState) -> AsyncGenerator[str, None]:
        """
        Method: A2UIRuntime.stream_dashboard - stream dashboard lifecycle via direct agent execution.
        Called from: backend.generative_ui.routes.dashboard.stream_dashboard.
        Invokes: A2UIMessageEmitter, LayoutPlanner.propose_override, A2UIAgent.execute_skill.
        Why: Emits SSE-ready A2UI messages with tracing and clarifications.
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

            # -------------------------------------------------------------------------
            # Component Selection: Streaming (Phase 5) with Fallback
            # Streaming is the primary path - enables progressive widget rendering
            # -------------------------------------------------------------------------
            step_start = time.time()
            llm_selection = None
            components = None
            streaming_succeeded = False
            
            # Try streaming component selection first (primary path)
            try:
                yield emitter.audit("component_selection_mode", "streaming")
                message_count += 1
                
                async for msg in self._stream_component_selection(
                    emitter, skill, state.question, context, trace
                ):
                    yield msg
                    message_count += 1
                
                streaming_succeeded = True
                # Skip to data execution - components already emitted by streaming
                components = []  # Mark as handled
                
            except Exception as e:
                logger.warning("[RUNTIME] Streaming component selection failed, falling back: %s", e)
                yield emitter.audit("streaming_fallback", f"error={str(e)[:100]}")
                message_count += 1
                # Continue to standard selection path
            
            # Standard LLM component selection (fallback when streaming fails)
            if not streaming_succeeded:
                # Try LLM component selection first
                try:
                    from .component_selector import get_component_selector
                    from .component_validator import get_component_validator
                    
                    selector = get_component_selector()
                    validator = get_component_validator()
                    
                    # Build context dict for LLM
                    context_dict = {
                        "primary_ticker": context.primary_ticker,
                        "tickers": context.tickers,
                        "metric": context.metric,
                        "time_range": context.time_range,
                    }
                    
                    # Get LLM component selection
                    llm_selection = await selector.select_components(
                        skill=skill,
                        question=state.question,
                        context=context_dict,
                    )
                    
                    if llm_selection:
                        # Validate LLM selection
                        is_valid, errors = validator.validate_selection(llm_selection, skill)
                        
                        if is_valid:
                            # Build components from LLM selection
                            components = emitter.build_components_from_selection(
                                llm_selection,
                                context,
                            )
                            yield emitter.audit(
                                "llm_component_selection",
                                f"widgets={[w.widget_type for w in llm_selection.widgets]}, "
                                f"emphasis={llm_selection.emphasis}"
                            )
                            message_count += 1
                            trace.add_step(
                                "llm_component_selection",
                                details={
                                    "widgets": [w.widget_type for w in llm_selection.widgets],
                                    "emphasis": llm_selection.emphasis,
                                    "rationale": llm_selection.rationale,
                                },
                                success=True,
                            )
                        else:
                            # Validation failed, log and fallback
                            logger.warning(
                                "[RUNTIME] LLM selection failed validation: %s", 
                                errors[:3]
                            )
                            llm_selection = None
                            
                except Exception as e:
                    logger.warning("[RUNTIME] LLM component selection failed: %s", e)
                    llm_selection = None
                
                # Fallback to hardcoded layouts if LLM selection failed
                if components is None:
                    # Use traditional layout planning
                    layout_override: Optional[LayoutOverride] = await self.layout_planner.propose_override(
                        skill,
                        state.question,
                    )
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
                            "layout_override_fallback", 
                            f"variant={layout_override.layout_variant or 'default'}, emphasis={layout_override.emphasis or 'none'}"
                        )
                        message_count += 1
            
            trace.add_step(
                "layout_planning",
                details={
                    "layout_override": trace.layout_override,
                    "component_count": len(components) if components else 0,
                    "llm_selected": llm_selection is not None,
                    "streaming": streaming_succeeded,
                },
                duration_ms=(time.time() - step_start) * 1000
            )
            
            # Emit surface update (skip if streaming already emitted components)
            if components and not streaming_succeeded:
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
                "loading": True,
            }
            yield emitter.data_update(seed_data)
            message_count += 1
            trace.add_step("seed_data", details={"keys": list(seed_data.keys())})

            # Cache check before expensive execution
            cached_run = state.find_cached_run(run_signature)
            if cached_run and cached_run.data_json:
                yield emitter.audit("cache_hit", f"reused run {cached_run.run_id}")
                message_count += 1
                cached_data = dict(cached_run.data_json)
                cached_data["loading"] = False

                session_id = state.params.get("session_id")
                if session_id:
                    from .session_memory import load_explanation_memory
                    cached_explanation = await load_explanation_memory(session_id, state.dashboard_id)
                    if cached_explanation:
                        explanation_payload = cached_data.get("explanation")
                        if not isinstance(explanation_payload, dict):
                            explanation_payload = {}
                        explanation_payload.update(cached_explanation)
                        explanation_payload["cached"] = True
                        cached_data["explanation"] = explanation_payload

                yield emitter.data_update(cached_data)
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

                # Try LLM component selection after clarification
                components = None
                try:
                    from .component_selector import get_component_selector
                    from .component_validator import get_component_validator
                    
                    selector = get_component_selector()
                    validator = get_component_validator()
                    
                    context_dict = {
                        "primary_ticker": context.primary_ticker,
                        "tickers": context.tickers,
                        "metric": context.metric,
                        "time_range": context.time_range,
                    }
                    
                    llm_selection = await selector.select_components(
                        skill=skill,
                        question=state.question,
                        context=context_dict,
                    )
                    
                    if llm_selection:
                        is_valid, errors = validator.validate_selection(llm_selection, skill)
                        if is_valid:
                            components = emitter.build_components_from_selection(
                                llm_selection, context
                            )
                except Exception as e:
                    logger.warning("[RUNTIME] Post-clarification LLM selection failed: %s", e)
                
                # Fallback to hardcoded layout
                if components is None:
                    layout_override = await self.layout_planner.propose_override(
                        skill,
                        state.question,
                    )
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
                    "loading": True,
                }
                yield emitter.data_update(seed_data)
                message_count += 1

                # Recompute signature after clarification adjustments
                run_signature = state.signature()

            # Execute skill using direct agent execution (no SDK flow)
            yield emitter.audit("runtime_step_started", "execute_skill")
            message_count += 1

            step_start = time.time()
            yield emitter.audit("execution_mode", "direct_agent")
            message_count += 1

            # Execute skill directly through agent
            result = await self.agent.execute_skill(skill, selection)

            # Normalize ticker-prefixed KPIs for the layout
            if result.data_model.get("kpis"):
                context_data = {
                    "primary_ticker": result.data_model.get("primary_ticker") or (selection.tickers[0] if selection.tickers else ""),
                    "tickers": result.data_model.get("tickers") or selection.tickers,
                    "kpis": result.data_model["kpis"],
                }
                normalized = _normalize_comparison_kpis(context_data)
                result.data_model["kpis"] = normalized["kpis"]

            # Mark data loading as complete for per-widget skeletons
            result.data_model["loading"] = False

            # Ensure explanation cached flag defaults to false on first run
            explanation = result.data_model.get("explanation")
            if isinstance(explanation, dict):
                explanation.setdefault("cached", False)

            # Persist explanation content for session-memory replay
            session_id = state.params.get("session_id")
            if session_id and isinstance(explanation, dict):
                from .session_memory import store_explanation_memory
                await store_explanation_memory(session_id, state.dashboard_id, explanation)

            # Emit data update with full result
            yield emitter.data_update(result.data_model, path="/data")
            message_count += 1
            trace.add_step("data_update", details={"keys": list(result.data_model.keys())})

            # Generate follow-up suggestions
            follow_ups = self._generate_follow_ups(selection, result.data_model)
            if follow_ups:
                result.data_model["follow_ups"] = follow_ups
                yield emitter.data_update({"follow_ups": follow_ups}, path="/data")
                message_count += 1

            skill_duration = (time.time() - step_start) * 1000
            yield emitter.audit("runtime_step_completed", "execute_skill")
            message_count += 1

            trace.add_step(
                "execute_skill_complete",
                details={
                    "data_keys": list(result.data_model.keys()) if result else [],
                    "citation_count": len(result.citations) if result else 0,
                    "execution_mode": "direct_agent",
                },
                duration_ms=skill_duration,
                success=result is not None,
            )

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

    async def _stream_component_selection(
        self,
        emitter: A2UIMessageEmitter,
        skill: Any,
        question: str,
        context: Any,
        trace: RunTrace,
    ) -> AsyncGenerator[str, None]:
        """
        Stream component selection for progressive rendering.
        
        Method: _stream_component_selection - progressive widget emission.
        Called from: stream_dashboard (when streaming mode enabled)
        Invokes: ComponentSelector.stream_components, ComponentValidator.validate_widget
        Why: Enables progressive widget rendering with per-widget safety checks.
        
        Args:
            emitter: A2UI message emitter
            skill: The selected skill
            question: User's original question
            context: Render context
            trace: Current execution trace
            
        Yields:
            A2UI JSONL messages for incremental surface updates
        """
        from .component_selector import get_component_selector
        from .component_validator import get_component_validator
        from .a2ui.messages import A2UIComponent, SurfaceUpdate
        
        selector = get_component_selector()
        validator = get_component_validator()
        
        pending_ids: List[str] = []
        widget_count = 0
        rejected_count = 0
        
        context_dict = {
            "primary_ticker": context.primary_ticker,
            "tickers": context.tickers,
            "metric": context.metric,
            "time_range": context.time_range,
        }
        
        yield emitter.audit("streaming_components", "started")

        # Emit header + initial layout root so streamed widgets can attach immediately
        title_component = A2UIComponent.text_bound("title_text", "/data/title", "h2")
        header_row = A2UIComponent.row("header_row", ["title_text"])
        layout_root = A2UIComponent(
            id="layout_root",
            component={"Column": {
                "children": {"explicitList": ["header_row"]},
                "gap": {"literalNumber": 24},
            }}
        )
        header_update = SurfaceUpdate(
            surfaceId=emitter.surface_id,
            components=[title_component, header_row, layout_root],
            incremental=False,
        )
        yield header_update.to_json()
        
        try:
            async for widget in selector.stream_components(skill, question, context_dict):
                is_valid, errors = validator.validate_widget(widget, skill)
                if not is_valid:
                    rejected_count += 1
                    yield emitter.audit(
                        "widget_rejected",
                        f"type={widget.widget_type}, id={widget.widget_id}, errors={errors[:2]}"
                    )
                    continue

                if widget.widget_id in pending_ids:
                    rejected_count += 1
                    yield emitter.audit(
                        "widget_rejected",
                        f"type={widget.widget_type}, id={widget.widget_id}, reason=duplicate"
                    )
                    continue

                # Build component from widget selection
                component = emitter._build_widget_from_selection(widget)
                if not component:
                    rejected_count += 1
                    yield emitter.audit(
                        "widget_rejected",
                        f"type={widget.widget_type}, id={widget.widget_id}, reason=build_failed"
                    )
                    continue

                pending_ids.append(widget.widget_id)
                widget_count += 1

                # Emit incremental surface update for this widget
                incremental_update = SurfaceUpdate(
                    surfaceId=emitter.surface_id,
                    components=[component],
                    incremental=True,  # Mark as streaming for animations
                )
                yield incremental_update.to_json()

                # Update layout root to include the newly streamed widget
                layout_root = A2UIComponent(
                    id="layout_root",
                    component={"Column": {
                        "children": {"explicitList": ["header_row"] + pending_ids},
                        "gap": {"literalNumber": 24},
                    }}
                )
                layout_update = SurfaceUpdate(
                    surfaceId=emitter.surface_id,
                    components=[layout_root],
                    incremental=False,
                )
                yield layout_update.to_json()

                yield emitter.audit(
                    "widget_streamed",
                    f"type={widget.widget_type}, id={widget.widget_id}"
                )

            if widget_count == 0:
                raise ValueError("streaming produced zero widgets")

            yield emitter.audit(
                "streaming_components",
                f"complete, widgets={widget_count}, rejected={rejected_count}"
            )
            
            trace.add_step(
                "stream_component_selection",
                details={
                    "widget_count": widget_count,
                    "widget_ids": pending_ids,
                    "rejected_count": rejected_count,
                },
                success=True,
            )
            
        except Exception as e:
            logger.warning("[RUNTIME] Streaming component selection failed: %s", e)
            yield emitter.audit("streaming_components", f"error: {str(e)[:100]}")
            trace.add_step(
                "stream_component_selection",
                details={"error": str(e)},
                success=False,
            )
            # Caller should fallback to non-streaming selection

    def _generate_follow_ups(
        self,
        selection: Any,
        data_model: Dict[str, Any],
    ) -> List[str]:
        """
        Method: A2UIRuntime._generate_follow_ups - generate rule-based follow-up suggestions.
        Called from: backend.generative_ui.runtime.A2UIRuntime.stream_dashboard.
        Invokes: follow_up_generator.generate_follow_ups.
        Why: Supplies contextual follow-up suggestions from the shared generator.
        """
        from .follow_up_generator import generate_follow_ups
        
        tickers = getattr(selection, 'tickers', [])
        skill_id = getattr(selection, 'skill_id', '')

        suggestions = generate_follow_ups(
            skill_id=skill_id,
            tickers=tickers,
            data_model=data_model,
            include_data_insights=True,
            max_suggestions=3,
        )
        return [s.query for s in suggestions]

    async def process_action(self, state: DashboardState, action: Dict[str, Any]) -> Dict[str, Any]:
        """
        Method: A2UIRuntime.process_action - apply user actions via direct agent execution.
        Called from: backend.generative_ui.routes.dashboard.handle_action.
        Invokes: A2UIAgent.execute_skill, TraceStore.
        Why: Keeps action handling aligned with direct execution and tracing.
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

        known_actions = {
            "change_timeframe", 
            "add_ticker", 
            "export_csv",
            # Layout switching actions (Jan 9, 2026)
            "switch_layout",      # Change layout variant
            "toggle_widget",      # Show/hide a specific widget
            "set_emphasis",       # Focus on chart/table/news/balanced
            "reorder_widgets",    # Change widget ordering
        }
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
        # -------------------------------------------------------------------------
        # Layout Switching Actions (Jan 9, 2026)
        # -------------------------------------------------------------------------
        elif action_name == "switch_layout":
            # Change layout variant (e.g., "focus_chart", "split-view", "balanced")
            new_variant = context.get("variant", "balanced")
            current_override = state.params.model_dump().get("layout_override") or {}
            current_override["variant"] = new_variant
            state.update_params({"layout_override": current_override})
            state.update_plan_fields(layout_variant=new_variant)
            trace.add_step("switch_layout", details={"variant": new_variant})
            trace.complete(success=True)
            self.trace_store.persist(trace)
            return {
                "status": "success",
                "action": action_name,
                "layout_override": current_override,
                "requires_rerender": True,
            }
        elif action_name == "toggle_widget":
            # Show/hide a specific widget (e.g., "NewsTimeline", "DataTable")
            widget_name = context.get("widget")
            if widget_name:
                current_override = state.params.model_dump().get("layout_override") or {}
                hidden = set(current_override.get("hidden_widgets") or [])
                if widget_name in hidden:
                    hidden.discard(widget_name)
                else:
                    hidden.add(widget_name)
                current_override["hidden_widgets"] = list(hidden)
                state.update_params({"layout_override": current_override})
                trace.add_step("toggle_widget", details={"widget": widget_name, "now_hidden": widget_name in hidden})
            trace.complete(success=True)
            self.trace_store.persist(trace)
            return {
                "status": "success",
                "action": action_name,
                "layout_override": current_override,
                "requires_rerender": True,
            }
        elif action_name == "set_emphasis":
            # Set emphasis mode (focus_chart, focus_table, focus_news, balanced)
            emphasis = context.get("emphasis", "balanced")
            current_override = state.params.model_dump().get("layout_override") or {}
            current_override["emphasis"] = emphasis
            state.update_params({"layout_override": current_override})
            trace.add_step("set_emphasis", details={"emphasis": emphasis})
            trace.complete(success=True)
            self.trace_store.persist(trace)
            return {
                "status": "success",
                "action": action_name,
                "layout_override": current_override,
                "requires_rerender": True,
            }
        elif action_name == "reorder_widgets":
            # Change widget ordering
            widget_order = context.get("widget_order", [])
            if isinstance(widget_order, list):
                current_override = state.params.model_dump().get("layout_override") or {}
                current_override["widget_order"] = widget_order
                state.update_params({"layout_override": current_override})
                trace.add_step("reorder_widgets", details={"widget_order": widget_order})
            trace.complete(success=True)
            self.trace_store.persist(trace)
            return {
                "status": "success",
                "action": action_name,
                "layout_override": current_override,
                "requires_rerender": True,
            }

        run_signature = state.signature()

        agent = self.agent
        selection = agent.selection_from_plan(state.plan_json)
        agent._validate_selection(selection)
        skill = agent.skill_lookup[selection.skill_id]

        # Execute skill directly
        result = await agent.execute_skill(skill, selection)

        # Normalize KPIs
        if result.data_model.get("kpis"):
            context_data = {
                "primary_ticker": result.data_model.get("primary_ticker") or (selection.tickers[0] if selection.tickers else ""),
                "tickers": result.data_model.get("tickers") or selection.tickers,
                "kpis": result.data_model["kpis"],
            }
            normalized = _normalize_comparison_kpis(context_data)
            result.data_model["kpis"] = normalized["kpis"]

        # Build data updates
        data_updates = [{"path": "/data", "data": result.data_model}]
        trace.add_step(
            "action_data_update",
            details={"path": "/data", "keys": list(result.data_model.keys())},
            success=True,
        )

        # Add follow-ups
        follow_ups = self._generate_follow_ups(selection, result.data_model)
        if follow_ups:
            result.data_model["follow_ups"] = follow_ups
            data_updates.append({"path": "/data", "data": {"follow_ups": follow_ups}})

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
