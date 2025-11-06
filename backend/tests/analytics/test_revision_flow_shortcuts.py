import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Optional

import pytest

sys.path.append(str(Path(__file__).resolve().parents[2]))

from analytics.flows.multi_agent import MultiAgentFlow  # noqa: E402
from analytics.flows.planner.revision import (  # noqa: E402
    apply_revision_plan,
    build_revision_plan,
)
from analytics.flows.schedulers import FlowMode  # noqa: E402
from analytics.routing import FollowUpRoute  # noqa: E402


class _DummyPlanner:
    async def initialize_context(self, query: str, session_id: Optional[str] = None) -> SimpleNamespace:
        return SimpleNamespace(
            query=query,
            session_id=session_id or "revision-session",
            artifacts=SimpleNamespace(classification=None),
            classification=None,
            is_financial_query=None,
            intent=SimpleNamespace(intent_key="analysis_revision"),
            plan=SimpleNamespace(),
            provisional_plan=None,
            intent_resolution=SimpleNamespace(followups=[]),
            follow_up_route=FollowUpRoute.REUSE_SQL,
            revision_targets={"analysis"},
            revision_directive=None,
            agentic_revision_mode=False,
            lane_refresh_required={},
            parallelism_enabled=False,
            reuse_sql=False,
            stock_only=False,
        )

    async def _persist_session_state(self, ctx: SimpleNamespace, record_artifacts: bool = True) -> None:  # noqa: ARG002
        return None


@pytest.mark.asyncio
async def test_revision_follow_up_marks_classifier_lanes_executed():
    flow = object.__new__(MultiAgentFlow)
    flow.flow_mode = FlowMode.MULTI_AGENT
    flow.flow_label = "multi-agent-test"
    flow.follow_up_route = FollowUpRoute.REUSE_SQL
    flow._planner = _DummyPlanner()
    flow._revision_directive = None
    flow._agentic_revision_mode = False
    flow._prefetched_snapshot = None
    flow._lane_refresh_required = {}
    flow._shared_context = {
        "planner": {},
        "sql": {},
        "analysis": {"fragments": [], "final": None},
        "chart": {},
        "market": {},
        "web": {},
        "_meta": {},
    }
    flow._pending_artifact_events = []
    flow._artifact_flush_pending = False
    flow._chart_revision_missing_session = False
    flow._hedged_completion = {}
    flow._planner_event_bus = None
    flow._sequencer_state = None
    flow._latest_lane_states = {}
    flow._planner_tool_manifest = []
    flow._tool_metadata_by_registry = {}
    flow._tool_metadata_by_role = {}
    flow._prepare_context = lambda query: None  # type: ignore[assignment]

    state = await flow._prepare_sequencer_state(
        "analysis revision request",
        session_id="revision-session",
    )

    assert {"classification", "intent_detection", "clarification", "plan_generation"} <= state.executed
    assert state.lane_states["intent"] == "reused"
    assert state.ctx.intent_reused is True
    assert flow._shared_context["planner"]["intent_reused"] is True


def test_analysis_revision_targets_force_web_lane():
    ctx = SimpleNamespace(
        revision_targets={"analysis"},
        revision_hint_active=False,
        revision_id=None,
        lane_refresh_required={},
    )
    plan = build_revision_plan(ctx, targets={"analysis"})

    assert plan.targets == {"analysis", "web"}

    apply_revision_plan(ctx, plan)

    assert ctx.revision_targets == {"analysis", "web"}
    assert ctx.lane_refresh_required["web"] is True
    assert ctx.reused_web is False
