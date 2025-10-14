import copy
import sys
from pathlib import Path

import pytest

sys.path.append(str(Path(__file__).resolve().parents[2]))

from analytics.flows.planner_executor import FOLLOW_UP_BANNERS
from analytics.flows.schedulers import (
    FlowMode,
    apply_mode_metadata,
    get_mode_config,
    get_mode_schedule,
    get_stage_index,
)
from analytics.routing import FollowUpRoute


def _stage_order(mode: FlowMode):
    schedule = get_mode_schedule(mode)
    return {stage.key: index for index, stage in enumerate(schedule.stages)}


def _annotate_events(mode: FlowMode, events):
    annotated = []
    for raw in events:
        event = copy.deepcopy(raw)
        annotated.append(apply_mode_metadata(event, mode))
    return annotated


def test_direct_ledger_stage_progression():
    direct_events = [
        {"event": "classification_complete", "data": {}},
        {"event": "intent_detection_complete", "data": {}},
        {"event": "sql_compiled", "data": {}},
        {"event": "chart_spec_ready", "data": {}},
        {"event": "analysis_complete", "data": {}},
    ]
    annotated = _annotate_events(FlowMode.DIRECT, direct_events)
    order = _stage_order(FlowMode.DIRECT)
    sequence = [evt["data"]["schedule_stage"] for evt in annotated]
    numeric_sequence = [order[stage] for stage in sequence]
    assert numeric_sequence == sorted(numeric_sequence)
    assert numeric_sequence == list(range(len(numeric_sequence)))


def test_multi_agent_ledger_traces_fanout():
    multi_events = [
        {"event": "agent_supervisor_started", "data": {}},
        {"event": "classification_complete", "data": {}},
        {"event": "sql_compiled", "data": {}},
        {"event": "tool_parallel_result", "data": {"tool": "web_retriever_cached"}},
        {"event": "tool_parallel_result", "data": {"tool": "web_retriever_live"}},
        {"event": "chart_spec_ready", "data": {}},
        {"event": "analysis_complete", "data": {}},
        {"event": "cohesive_result", "data": {}},
    ]
    annotated = _annotate_events(FlowMode.MULTI_AGENT, multi_events)
    stage_index = get_stage_index(FlowMode.MULTI_AGENT)
    hedged_stage = next(stage for stage in stage_index.schedule.stages if stage.key == "hedged_accessories")
    observed_hedged = [evt for evt in annotated if evt["data"].get("schedule_stage") == "hedged_accessories"]
    assert len(observed_hedged) == 2
    assert {evt["data"].get("parallel_group") for evt in observed_hedged} == {hedged_stage.parallel_group}
    supervisors = [evt for evt in annotated if evt["data"].get("schedule_stage") == "supervisor"]
    assert supervisors, "Supervisor stage should appear for multi-agent ledger"
    analysis = [evt for evt in annotated if evt["data"].get("schedule_stage") == "analysis"]
    assert any(evt["event"] == "analysis_complete" for evt in analysis)
    assert any(evt["event"] == "cohesive_result" for evt in analysis)


@pytest.mark.parametrize("mode", list(FlowMode))
@pytest.mark.parametrize("route", list(FollowUpRoute))
def test_follow_up_routes_emit_analysis_stage_badges(mode: FlowMode, route: FollowUpRoute):
    stage_index = get_stage_index(mode)
    analysis_stage = stage_index.events_to_stage.get("follow_up_route")
    assert analysis_stage is not None, f"follow_up_route should map to a stage for mode={mode}"
    assert analysis_stage.key == "analysis"

    copy_defaults = FOLLOW_UP_BANNERS[route]
    banner_event = {
        "event": "progress",
        "data": {
            "step": "follow_up_route",
            "banner": {
                "title": copy_defaults["title"],
                "message": copy_defaults["message"],
                "route": route.value,
            },
        },
    }
    annotated = apply_mode_metadata(copy.deepcopy(banner_event), mode)
    data = annotated["data"]

    assert data["mode"] == mode.value
    assert data["banner"]["route"] == route.value
    assert data["schedule"]["mode"] == mode.value
    assert data["schedule_stage"] == analysis_stage.key
    assert data["parallel_group"] == analysis_stage.parallel_group

    badges = data.get("badges", {})
    config = get_mode_config(mode)
    assert badges.get("mode") == config.deterministic_badge
    if mode is FlowMode.MULTI_AGENT:
        assert badges.get("hedging") == "enabled"
    else:
        assert badges.get("hedging") != "enabled"
    assert data.get("supports_deltas") is True
