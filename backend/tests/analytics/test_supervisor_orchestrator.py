from __future__ import annotations

from agents.tool import Tool

from analytics.flows.supervisor_orchestrator import (
    SupervisorBundle,
    SupervisorSpecialistConfig,
    build_supervisor_bundle,
)


def test_build_supervisor_bundle_creates_tool_bindings() -> None:
    specialists = [
        SupervisorSpecialistConfig(
            lane="sql",
            name="sql_specialist",
            instructions="Compile and validate SQL for planner tasks.",
            description="SQL lane specialist",
        ),
        SupervisorSpecialistConfig(
            lane="web",
            name="web_specialist",
            instructions="Fetch web research snippets.",
            description="Web research specialist",
            max_turns=6,
        ),
    ]

    bundle: SupervisorBundle = build_supervisor_bundle(
        supervisor_name="analytics_supervisor",
        supervisor_instructions="Coordinate specialists to deliver analytics responses.",
        model="gpt-5-mini-2025-08-07",
        reasoning_effort="medium",
        max_turns=4,
        specialist_configs=specialists,
    )

    assert bundle.tools.keys() == {"sql", "web"}
    for lane, tool in bundle.tools.items():
        assert isinstance(tool, Tool)
        assert tool.name.startswith(f"{lane}_")

    assert bundle.supervisor.name == "analytics_supervisor"
    assert bundle.supervisor.tools == list(bundle.tools.values())

    sql_binding = next(binding for binding in bundle.bindings if binding.lane == "sql")
    assert sql_binding.tool_name == "sql_specialist"
    assert sql_binding.tool in bundle.supervisor.tools
