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
        model="gpt-5-nano",
        raw={"category": "financial_analytics", "confidence": 0.84},
    )

    payload = artifact.to_dict()
    restored = ClassificationArtifact.from_dict(payload)

    assert restored.query == artifact.query
    assert restored.category == "financial_analytics"
    assert restored.confidence == 0.84
    assert restored.is_financial is True
    assert restored.model == "gpt-5-nano"
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
        analysis=AnalysisArtifact(query="q1", analysis_text="Summary", length=7, fragments=["Sum"]),
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


def test_session_snapshot_record_artifacts():
    snapshot = SessionStateSnapshot(session_id="sess")
    artifacts = PipelineArtifacts(classification=ClassificationArtifact(query="q"))
    payload = artifacts.to_dict()
    snapshot.record_artifacts(payload)
    assert snapshot.tool_cache.setdefault("analytics", {}).get("artifacts") == payload

