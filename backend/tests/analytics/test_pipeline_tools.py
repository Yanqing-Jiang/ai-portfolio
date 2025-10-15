from __future__ import annotations

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[3]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

import types  # noqa: E402

# Provide stubs for optional google.genai dependency used in response_search imports.
google_stub = sys.modules.setdefault("google", types.ModuleType("google"))  # noqa: E402
genai_stub = types.ModuleType("google.genai")
genai_types_stub = types.ModuleType("google.genai.types")
setattr(genai_stub, "types", genai_types_stub)
setattr(google_stub, "genai", genai_stub)
sys.modules["google.genai"] = genai_stub
sys.modules["google.genai.types"] = genai_types_stub

from analytics.flows.pipeline_tools import get_planner_tool_registry  # noqa: E402
from analytics.flows.tool_bundle import collect_tool_bundle  # noqa: E402


def _select_fields(payload: dict[str, object]) -> dict[str, object]:
    include = (
        "prerequisites",
        "telemetry_step",
        "inputs",
        "outputs",
        "output_artifacts",
        "latency_budget_ms",
        "concurrency_limit",
    )
    return {key: payload.get(key) for key in include}


def test_planner_tool_registry_describe_tools_snapshot() -> None:
    registry = get_planner_tool_registry()
    described = {_payload["name"]: _select_fields(_payload) for _payload in registry.describe_tools()}

    expected = {
        "analysis_generation": {
            "prerequisites": ["chart_generation"],
            "telemetry_step": "analysis_generation",
            "inputs": ["chart_spec"],
            "outputs": ["analysis"],
            "output_artifacts": ["analysis"],
            "latency_budget_ms": 5000,
            "concurrency_limit": 1,
        },
        "analysis_revision": {
            "prerequisites": [],
            "telemetry_step": "analysis_revision",
            "inputs": ["analysis"],
            "outputs": ["analysis"],
            "output_artifacts": ["revision"],
            "latency_budget_ms": 1200,
            "concurrency_limit": 2,
        },
        "chart_generation": {
            "prerequisites": ["sql_generation"],
            "telemetry_step": "chart_generation",
            "inputs": ["sql"],
            "outputs": ["chart_spec"],
            "output_artifacts": ["chart"],
            "latency_budget_ms": 1500,
            "concurrency_limit": 1,
        },
        "chart_revision": {
            "prerequisites": [],
            "telemetry_step": "chart_revision",
            "inputs": ["patch"],
            "outputs": ["chart_patch"],
            "output_artifacts": ["revision"],
            "latency_budget_ms": 800,
            "concurrency_limit": 2,
        },
        "classification": {
            "prerequisites": [],
            "telemetry_step": "classification",
            "inputs": ["query"],
            "outputs": ["classification"],
            "output_artifacts": ["classification"],
            "latency_budget_ms": 500,
            "concurrency_limit": 1,
        },
        "clarification": {
            "prerequisites": ["intent_detection"],
            "telemetry_step": "clarification",
            "inputs": ["intent"],
            "outputs": ["clarifications"],
            "output_artifacts": ["clarification"],
            "latency_budget_ms": 2000,
            "concurrency_limit": 1,
        },
        "intent_detection": {
            "prerequisites": ["classification"],
            "telemetry_step": "intent_detection",
            "inputs": ["classification"],
            "outputs": ["intent"],
            "output_artifacts": ["intent"],
            "latency_budget_ms": 1500,
            "concurrency_limit": 1,
        },
        "plan_generation": {
            "prerequisites": ["clarification"],
            "telemetry_step": "plan_generation",
            "inputs": ["clarifications"],
            "outputs": ["plan"],
            "output_artifacts": ["plan"],
            "latency_budget_ms": 2000,
            "concurrency_limit": 1,
        },
        "sql_generation": {
            "prerequisites": ["plan_generation"],
            "telemetry_step": "sql_generation",
            "inputs": ["plan"],
            "outputs": ["sql"],
            "output_artifacts": ["sql_generation", "sql_execution"],
            "latency_budget_ms": 7000,
            "concurrency_limit": 1,
        },
        "sql_regeneration": {
            "prerequisites": ["plan_generation"],
            "telemetry_step": "sql_regeneration",
            "inputs": ["plan"],
            "outputs": ["sql"],
            "output_artifacts": ["sql_generation", "sql_execution"],
            "latency_budget_ms": 7000,
            "concurrency_limit": 1,
        },
    }

    assert described == expected


def test_collect_tool_bundle_sources_reused_and_fanout() -> None:
    results = [
        {
            "tool": "web_retriever",
            "status": "completed",
            "payload": {
                "ready": True,
                "summary": "Cached context",
                "snippets": [],
                "from_cache": True,
            },
        },
        {
            "tool": "stock_tracker",
            "status": "completed",
            "payload": {
                "ready": True,
                "stock_widget": {
                    "symbols": ["NASDAQ:NVDA"],
                },
            },
        },
    ]

    bundle = collect_tool_bundle(results=results)

    assert bundle["sources"]["web_retriever"] == "cached"
    assert bundle["sources"]["stock_tracker"] == "fanout"
    assert bundle["web_context"]["summary"] == "Cached context"
    assert bundle["stock_widget"]["symbols"] == ["NASDAQ:NVDA"]
