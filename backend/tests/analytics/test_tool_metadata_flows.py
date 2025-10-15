from __future__ import annotations

import pathlib
import sys
import types

ROOT = pathlib.Path(__file__).resolve().parents[3]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

# Stub optional google.genai dependency used by response_search imports.
google_stub = sys.modules.setdefault("google", types.ModuleType("google"))
genai_stub = types.ModuleType("google.genai")
genai_types_stub = types.ModuleType("google.genai.types")
setattr(genai_stub, "types", genai_types_stub)
setattr(google_stub, "genai", genai_stub)
sys.modules["google.genai"] = genai_stub
sys.modules["google.genai.types"] = genai_types_stub

from analytics.flows.single_agent_tools import SingleAgentController  # noqa: E402
from analytics.flows.multi_agent import MultiAgentFlow  # noqa: E402


def test_single_agent_metadata_lookup() -> None:
    flow = SingleAgentController()

    sql_step_meta = flow.get_tool_metadata_for_step("sql_compilation")
    assert sql_step_meta is not None
    assert sql_step_meta["latency_budget_ms"] == 7000
    assert sql_step_meta["concurrency_limit"] == 1
    assert "sql_execution" in sql_step_meta["output_artifacts"] or "sql_generation" in sql_step_meta["output_artifacts"]

    alias_meta = flow.get_tool_metadata_for_alias("sql_generator")
    assert alias_meta == sql_step_meta

    classification_meta = flow.get_tool_metadata_for_event("classification_complete")
    assert classification_meta is not None
    assert classification_meta["latency_budget_ms"] == 500
    assert classification_meta.get("concurrency_limit") == 1


def test_multi_agent_metadata_lookup() -> None:
    flow = MultiAgentFlow()

    start_meta = flow._get_tool_metadata_for_step("analysis_generation")
    assert start_meta is not None
    assert start_meta["latency_budget_ms"] == 5000
    assert start_meta.get("concurrency_limit") == 1

    role_meta = flow._get_tool_metadata_for_role("intent_analyst")
    assert role_meta is not None
    assert role_meta["latency_budget_ms"] == 1500
    assert role_meta.get("concurrency_limit") == 1

    event_meta = flow._get_tool_metadata_for_event("chart_patch")
    assert event_meta is not None
    assert event_meta["latency_budget_ms"] == 800
    assert event_meta.get("concurrency_limit") == 2
