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

from analytics.flows.single_agent_tools import _build_single_agent_cohesive_payload  # noqa: E402
from analytics.artifacts.models import (  # noqa: E402
    AnalysisArtifact,
    ChartArtifact,
    PipelineArtifacts,
    SQLExecutionArtifact,
    SQLGenerationArtifact,
    WebContextArtifact,
)


def test_cohesive_payload_uses_artifacts() -> None:
    artifacts = PipelineArtifacts(
        sql_generation=SQLGenerationArtifact(query="q", sql="SELECT 1"),
        sql_execution=SQLExecutionArtifact(
            query="q",
            row_count=2,
            columns=["value"],
            sample_rows=[{"value": 1}],
        ),
        chart=ChartArtifact(
            query="q",
            spec={"series": [{"data": [1]}]},
            spec_id="chart-1",
            chart_type="line",
        ),
        analysis=AnalysisArtifact(
            query="q",
            analysis_text="analysis text",
            summary="summary",
            stock_widget={"symbols": [["NVDA"]]},
            web_context={"summary": "web"},
            evidence=[{"source": "example"}],
        ),
        web=WebContextArtifact(query="q", summary="web summary"),
    )

    analysis_payload = {
        "analysis": "analysis text",
        "analysis_length": 123,
        "tool_results": [{"tool": "stock_tracker"}],
        "stock_widget": {"symbols": [["NVDA"]]},
        "web_context": {"summary": "web summary"},
        "analysis_overview": {"tldr": "summary"},
    }

    payload = _build_single_agent_cohesive_payload(
        analysis_payload,
        artifacts,
        default_manifest=[{"name": "web_retriever"}],
    )

    assert payload is not None
    assert payload["sql"] == "SELECT 1"
    assert payload["sql_row_count"] == 2
    assert payload["columns"] == ["value"]
    assert payload["data_sample"] == [{"value": 1}]
    assert payload["chart_spec"]["series"][0]["data"] == [1]
    assert payload["chart_spec_id"] == "chart-1"
    assert payload["tool_manifest"][0]["name"] == "web_retriever"
    assert payload["web_context"]["summary"] == "web summary"
    assert "stock_widget" in payload and payload["stock_widget"]


def test_cohesive_payload_falls_back_to_defaults() -> None:
    artifacts = PipelineArtifacts(
        sql_generation=SQLGenerationArtifact(query="q", sql="SELECT 1"),
    )

    payload = _build_single_agent_cohesive_payload(
        {},
        artifacts,
        default_manifest=[{"name": "sql_planner"}],
    )

    assert payload is not None
    assert payload["sql"] == "SELECT 1"
    assert payload["tool_manifest"][0]["name"] == "sql_planner"
