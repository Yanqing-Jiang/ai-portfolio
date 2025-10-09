"""Scheduler summaries and helpers for analytics FlowMode variants."""

from analytics.flows.schedulers import (
    FlowMode,
    apply_mode_metadata,
    describe_mode_schedule,
    get_mode_schedule,
    get_stage_index,
    resolve_stage,
)


def _stage(schedule, key: str):
    for stage in schedule.stages:
        if stage.key == key:
            return stage
    raise AssertionError(f"Stage {key} missing in schedule {schedule.mode}")


def test_direct_schedule_is_sequential():
    schedule = get_mode_schedule(FlowMode.DIRECT)
    assert schedule.mode is FlowMode.DIRECT
    assert not schedule.default_parallelism
    assert [stage.key for stage in schedule.stages] == [
        "classification",
        "intent",
        "sql",
        "chart",
        "analysis",
        "accessories_post",
    ]
    assert all(stage.parallel_group == "core_sequential" or stage.key == "accessories_post" for stage in schedule.stages)
    assert all(stage.allows_parallel is False for stage in schedule.stages)


def test_single_agent_schedule_has_parallel_accessories():
    schedule = get_mode_schedule(FlowMode.SINGLE_AGENT)
    accessories_stage = _stage(schedule, "accessories_pre_analysis")
    assert accessories_stage.allows_parallel is True
    assert set(accessories_stage.accessories) >= {"web_retriever_cached", "web_retriever_live"}
    assert schedule.default_parallelism is True
    assert schedule.accessory_strategy == "pre_analysis_fanout"


def test_multi_agent_schedule_tracks_hedged_tools():
    schedule = get_mode_schedule(FlowMode.MULTI_AGENT)
    hedged_stage = _stage(schedule, "hedged_accessories")
    assert schedule.hedging_enabled is True
    assert hedged_stage.allows_parallel is True
    assert set(hedged_stage.hedged_tools) == {"web_retriever_cached", "web_retriever_live"}
    assert "stock_tracker" in hedged_stage.accessories


def test_apply_mode_metadata_embeds_schedule_summary():
    event = {"event": "analysis_complete", "data": {"badges": {}}}
    annotated = apply_mode_metadata(event, FlowMode.MULTI_AGENT)
    schedule_data = annotated["data"].get("schedule")
    assert schedule_data["mode"] == FlowMode.MULTI_AGENT.value
    hedged_stage = next(stage for stage in schedule_data["stages"] if stage["key"] == "hedged_accessories")
    assert "web_retriever_cached" in hedged_stage["hedged_tools"]
    badges = annotated["data"].get("badges")
    assert badges["mode"] == "Supervisor"
    assert badges.get("hedging") == "enabled"
    assert annotated["data"]["schedule_stage"] == "analysis"
    assert annotated["data"]["parallel_group"] == "analysis_stream"


def test_describe_mode_schedule_matches_summary():
    summary = describe_mode_schedule(FlowMode.SINGLE_AGENT)
    assert summary["mode"] == FlowMode.SINGLE_AGENT.value
    stage_keys = [stage["key"] for stage in summary["stages"]]
    assert stage_keys[0] == "classification"
    assert "analysis" in stage_keys


def test_stage_index_resolves_events_and_steps():
    index = get_stage_index(FlowMode.DIRECT)
    stage = resolve_stage(index, event_name="analysis_complete")
    assert stage is not None
    assert stage.key == "analysis"
    step_stage = resolve_stage(index, step_name="sql_compilation")
    assert step_stage is not None
    assert step_stage.key == "sql"
