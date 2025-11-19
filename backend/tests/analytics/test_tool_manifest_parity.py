# --- Analytics Function/Class Map ---
# Function: test_planner_registry_matches_canonical_definitions
#   Role: Asserts the planner registry emits identical schemas to the canonical tool registry to prevent DIRECT/agent drift.
#   Called from: pytest
#   Invokes: analytics.flows.pipeline_tools.get_planner_tool_registry, analytics.tools.TOOL_REGISTRY
#   Why: Guarantees the single source of truth is respected before manifests feed DIRECT and Agent SDK registrations.
# --- End Analytics Function/Class Map ---
from analytics.flows.pipeline_tools import get_planner_tool_registry
from analytics.tools import TOOL_REGISTRY


def test_planner_registry_matches_canonical_definitions() -> None:
    registry = get_planner_tool_registry()
    described = {entry["name"]: entry for entry in registry.describe_tools()}
    for tool_id, canonical in TOOL_REGISTRY.items():
        name = canonical.name
        assert name in described, f"Missing planner tool: {name}"
        entry = described[name]
        assert entry["parameters_schema"] == canonical.parameters_schema
        assert entry["response_schema"] == canonical.response_schema
        assert entry["schema_version"] == canonical.schema_version
        assert entry["telemetry_step"] == canonical.telemetry_step
        assert tuple(entry["prerequisites"]) == tuple(dep.value for dep in canonical.depends_on)
