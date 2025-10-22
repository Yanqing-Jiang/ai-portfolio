import json
from pathlib import Path

from analytics.agents.schema_clarifier import SCHEMA_CLARIFIER_SYSTEM_PROMPT
from analytics.flows.multi_agent import (
    MultiAgentFlow,
    SUPERVISOR_AGENT_SYSTEM_PROMPTS,
)
from analytics.flows.planner_executor import PlannerExecutorFlow


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
    expected_versions = PlannerExecutorFlow.get_prompt_versions()
    assert expected_versions == MultiAgentFlow.get_prompt_versions()

    multi_flow = MultiAgentFlow()
    annotated_multi = multi_flow._annotate({"event": "progress", "data": {}})
    assert annotated_multi["data"]["prompt_versions"] == expected_versions

    single_flow = PlannerExecutorFlow()
    annotated_single = single_flow._annotate({"event": "progress", "data": {}})
    assert annotated_single["data"]["prompt_versions"] == expected_versions


def test_rerun_directive_exemplar_matches_contract():
    exemplar_path = (
        Path(__file__).resolve().parents[3]
        / "examples"
        / "prompts"
        / "rerun_directive_market_cached.json"
    )
    exemplar = json.loads(exemplar_path.read_text(encoding="utf-8"))

    assert exemplar["prompt_versions"] == PlannerExecutorFlow.get_prompt_versions()
    supervisor_response = exemplar["supervisor_response"]

    rerun_directive = supervisor_response["rerun_directive"]
    assert rerun_directive["rerun"] == ["chart_lane"]
    assert rerun_directive["reuse"] == ["market_lane", "web_lane"]

    guidance = supervisor_response["guidance"]
    assert guidance["final_answer_only"] is False
    assert guidance["decline_reason"] is None
    assert any("chart" in note.lower() for note in guidance["notes"])

    telemetry = exemplar["telemetry_expectations"]
    assert "final answer uses cached" in telemetry["final_answer_banner_copy"].lower()


def test_decline_exemplar_matches_contract():
    exemplar_path = (
        Path(__file__).resolve().parents[3]
        / "examples"
        / "prompts"
        / "rerun_directive_decline_market.json"
    )
    exemplar = json.loads(exemplar_path.read_text(encoding="utf-8"))

    assert exemplar["prompt_versions"] == PlannerExecutorFlow.get_prompt_versions()
    supervisor_response = exemplar["supervisor_response"]

    assert supervisor_response["decision"] == "decline"
    assert supervisor_response["decline_reason"] == "insufficient_inputs"
    assert "request" in supervisor_response["next_step"].lower()
    assert "ttl" in supervisor_response["summary"].lower()

    guidance = supervisor_response["guidance"]
    assert guidance["final_answer_only"] is False
    assert any("cached" in note.lower() for note in guidance["notes"])

    telemetry = exemplar["telemetry_expectations"]
    assert telemetry["declined_lanes"] == [
        "market_lane",
        "web_lane",
        "chart_lane",
    ]
    assert "declined" in telemetry["decline_banner_copy"].lower()
