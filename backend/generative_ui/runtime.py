# --- Runtime Function/Class Map ---
# Class: A2UIRuntime
#   Role: Orchestrate the A2UI dashboard runtime loop (render -> clarifications -> data updates).
#   Called from: (future) backend.generative_ui.routes.dashboard; can be imported by tests.
#   Invokes: A2UIMessageEmitter, A2UIAgent (selection/execute), LayoutPlanner, clarification helpers.
#   Why: Centralizes the runtime loop to enable incremental streaming and future layout overrides.
# Method: stream_dashboard
#   Role: Async generator that yields A2UI/Audit messages for SSE streaming.
#   Called from: A2UIRuntime consumers (routes/tests).
#   Invokes: agent selection/validation, layout planner, clarifications, execute_skill.
#   Why: Provides a structured, step-aware runtime instead of ad-hoc streaming.
# --- End Runtime Function/Class Map ---
"""
Lightweight A2UI runtime orchestrator.

This module wraps the existing A2UI agent + emitter into a reusable runtime
loop that can be incrementally extended (layout overrides, step-level audits,
pause/resume on clarifications, etc.).
"""

from __future__ import annotations

import json
from typing import AsyncGenerator, Optional

from .a2ui.emitter import A2UIMessageEmitter
from .agent_v2 import A2UIAgent
from .layout_planner import LayoutOverride, LayoutPlanner
from .clarification import (
    await_clarification_response,
    build_visual_clarification,
    clarification_to_sse_event,
)
from .models.dashboard_state import DashboardState


class A2UIRuntime:
    """Runtime orchestrator for A2UI dashboards."""

    def __init__(self, agent: A2UIAgent, layout_planner: Optional[LayoutPlanner] = None) -> None:
        """Initialize runtime with agent and optional layout planner."""
        self.agent = agent
        self.layout_planner = layout_planner or LayoutPlanner()

    async def stream_dashboard(self, state: DashboardState) -> AsyncGenerator[str, None]:
        """
        Stream the full dashboard lifecycle as JSON strings (ready for SSE wrapping).

        Steps:
        1) beginRendering
        2) surfaceUpdate (with optional layout override)
        3) seed data
        4) optional clarification pause/resume
        5) execute skill + incremental dataModelUpdate
        6) done sentinel
        """
        emitter = A2UIMessageEmitter(surface_id=state.surface_id, catalog_id=state.catalog_id)

        # 1) beginRendering
        yield emitter.begin_rendering()

        try:
            selection = self.agent.selection_from_plan(state.plan_json)
            self.agent._validate_selection(selection)
            skill = self.agent.skill_lookup[selection.skill_id]
            context = self.agent._build_render_context(selection, skill)

            # Optional layout override (currently no-op)
            layout_override: Optional[LayoutOverride] = self.layout_planner.propose_override(skill, state.question)
            components = emitter.build_components_for_skill(skill, context, variant=layout_override.layout_variant if layout_override else None)
            if layout_override:
                yield emitter.audit("layout_override", f"variant={layout_override.layout_variant or 'default'}, emphasis={layout_override.emphasis or 'none'}")
            yield emitter.surface_update(components)

            seed_data = {
                "title": context.title,
                "ticker": context.primary_ticker,
                "primary_ticker": context.primary_ticker,
                "tickers": context.tickers,
                "time_range": context.time_range,
                "metric": context.metric,
            }
            yield emitter.data_update(seed_data)

            # Clarification gate
            clarification = build_visual_clarification(state.question, selection, state.plan_json, state.params)
            if clarification:
                state.update_params({
                    "pending_clarification": clarification.model_dump(),
                    "clarification_responses": state.params.get("clarification_responses") or {},
                })
                yield clarification_to_sse_event(clarification)
                await await_clarification_response(state, clarification.request_id, clarification.timeout_seconds)

                selection = self.agent.selection_from_plan(state.plan_json)
                self.agent._validate_selection(selection)
                skill = self.agent.skill_lookup[selection.skill_id]
                context = self.agent._build_render_context(selection, skill)

                components = emitter.build_components_for_skill(skill, context)
                yield emitter.surface_update(components)
                seed_data = {
                    "title": context.title,
                    "ticker": context.primary_ticker,
                    "primary_ticker": context.primary_ticker,
                    "tickers": context.tickers,
                    "time_range": context.time_range,
                    "metric": context.metric,
                }
                yield emitter.data_update(seed_data)

            yield emitter.audit("runtime_step_started", "execute_skill")
            result = await self.agent.execute_skill(skill, selection)
            yield emitter.audit("runtime_step_completed", "execute_skill")

            # Incremental data updates: emit core metrics first, then enrichments.
            full_data = result.data_model
            core_keys = {"kpis", "chart", "table", "tickers", "ticker", "primary_ticker", "time_range", "metric", "title"}
            enrich_keys = set(full_data.keys()) - core_keys

            core_payload = {k: v for k, v in full_data.items() if k in core_keys}
            if core_payload:
                yield emitter.data_update(core_payload)

            enrich_payload = {k: v for k, v in full_data.items() if k in enrich_keys}
            if enrich_payload:
                yield emitter.data_update(enrich_payload)

            state.add_run(result.data_model, result.citations)

            yield json.dumps({"done": True})
        except Exception as exc:
            for msg in emitter.error_surface("agent_error", str(exc)):
                yield msg
            yield json.dumps({"done": True})


__all__ = ["A2UIRuntime"]
