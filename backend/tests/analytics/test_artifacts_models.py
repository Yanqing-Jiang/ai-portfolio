from __future__ import annotations

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[3]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from analytics.artifacts import (  # noqa: E402
    AnalysisArtifact,
    ChartArtifact,
    ClassificationArtifact,
    PipelineArtifacts,
    SQLExecutionArtifact,
    SQLGenerationArtifact,
)
from analytics.core.session_state import SessionStateSnapshot


def test_classification_artifact_roundtrip():
    artifact = ClassificationArtifact(
        query="How is NVDA doing?",
        category="financial_analytics",
        confidence=0.84,
        is_financial=True,
        model="gpt-5-mini-2025-08-07",
        raw={"category": "financial_analytics", "confidence": 0.84},
    )

    payload = artifact.to_dict()
    restored = ClassificationArtifact.from_dict(payload)

    assert restored.query == artifact.query
    assert restored.category == "financial_analytics"
    assert restored.confidence == 0.84
    assert restored.is_financial is True
    assert restored.model == "gpt-5-mini-2025-08-07"
    assert restored.raw == {"category": "financial_analytics", "confidence": 0.84}


def test_pipeline_artifacts_nested_roundtrip():
    pipeline = PipelineArtifacts(
        classification=ClassificationArtifact(query="q1", category="finance"),
        chart=ChartArtifact(query="q1", spec={"type": "line"}),
        sql_generation=SQLGenerationArtifact(query="q1", sql="SELECT 1", attempts=[{"status": "valid"}]),
        sql_execution=SQLExecutionArtifact(
            query="q1",
            row_count=120,
            columns=["ticker", "value"],
            sample_rows=[{"ticker": "NVDA", "value": 42}],
            elapsed_ms=250,
            status="success",
        ),
        analysis=AnalysisArtifact(
            query="q1",
            analysis_text="Summary",
            length=7,
            fragments=["Sum"],
            key_numbers=["Revenue up 12%"],
            risk_watch=["FX volatility could pressure margins"],
            next_steps=["Monitor FX exposure each quarter"],
        evidence=[
            {
                "claim": "Revenue up 12%",
                "source_url": "https://example.com/nvda",
                "title": "NVIDIA earnings beat expectations",
                "snippet": "NVIDIA reported revenue climbing 12% year over year.",
                "confidence": 0.85,
            }
        ],
        ),
    )

    payload = pipeline.to_dict()
    restored = PipelineArtifacts.from_dict(payload)

    assert restored.classification is not None
    assert restored.classification.category == "finance"
    assert restored.chart is not None
    assert restored.chart.spec == {"type": "line"}
    assert restored.sql_generation is not None
    assert restored.sql_generation.sql == "SELECT 1"
    assert restored.sql_execution is not None
    assert restored.sql_execution.row_count == 120
    assert restored.analysis is not None
    assert restored.analysis.analysis_text == "Summary"
    assert restored.analysis.key_numbers == ["Revenue up 12%"]
    assert restored.analysis.risk_watch == ["FX volatility could pressure margins"]
    assert restored.analysis.next_steps == ["Monitor FX exposure each quarter"]
    assert restored.analysis.evidence == [
        {
            "claim": "Revenue up 12%",
            "source_url": "https://example.com/nvda",
            "title": "NVIDIA earnings beat expectations",
            "snippet": "NVIDIA reported revenue climbing 12% year over year.",
            "confidence": 0.85,
        }
    ]


def test_session_snapshot_record_artifacts():
    snapshot = SessionStateSnapshot(session_id="sess")
    artifacts = PipelineArtifacts(classification=ClassificationArtifact(query="q"))
    payload = artifacts.to_dict()
    snapshot.record_artifacts(payload)
    analytics_cache = snapshot.tool_cache.setdefault("analytics", {})
    assert analytics_cache.get("artifacts") == payload
    assert analytics_cache.get("artifact_version") == 1
    history = analytics_cache.get("artifacts_history")
    assert isinstance(history, list)
    assert len(history) == 1
    assert history[0]["version"] == 1
    assert history[0]["artifacts"] == payload

