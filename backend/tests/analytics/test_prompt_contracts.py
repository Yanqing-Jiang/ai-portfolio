from analytics.agents.schema_clarifier import SCHEMA_CLARIFIER_SYSTEM_PROMPT
from analytics.flows.multi_agent import (
    MultiAgentFlow,
    SUPERVISOR_AGENT_SYSTEM_PROMPTS,
)
from analytics.flows.planner_executor import PlannerExecutorFlow
from analytics.prompt_versions import get_prompt_versions


def test_schema_clarifier_prompt_mentions_decline_and_cache():
    prompt = SCHEMA_CLARIFIER_SYSTEM_PROMPT
    assert "decline" in prompt.lower()
    assert "cached receipts" in prompt.lower()
    assert "insufficient_inputs" in prompt


def test_supervisor_prompts_include_rerun_directive_and_guidance():
    planner_prompt = SUPERVISOR_AGENT_SYSTEM_PROMPTS["planner"]
    analyst_prompt = SUPERVISOR_AGENT_SYSTEM_PROMPTS["analyst"]
    assert "rerun_directive" in planner_prompt
    assert "final_answer_only" in analyst_prompt


def test_prompt_versions_surface_in_event_annotations():
    expected_versions = get_prompt_versions()

    multi_flow = MultiAgentFlow()
    annotated_multi = multi_flow._annotate({"event": "progress", "data": {}})
    assert annotated_multi["data"]["prompt_versions"] == expected_versions

    single_flow = PlannerExecutorFlow()
    annotated_single = single_flow._annotate({"event": "progress", "data": {}})
    assert annotated_single["data"]["prompt_versions"] == expected_versions

