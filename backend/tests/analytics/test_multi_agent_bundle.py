from __future__ import annotations

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[3]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from analytics.flows.multi_agent import _create_planner_bundle


def test_create_planner_bundle_sanitizes_slice_and_generates_id() -> None:
    session_id = "session-demo"
    planner_ctx = {"intent_key": "market_share_single", "confidence": 0.9, "tickers": ["AMD", "NVDA"]}
    sql_ctx = {"sql": "SELECT 1", "status": "complete", "attempts": [{"window": slice(0, 4, 1)}]}
    chart_ctx = {"spec": {"title": "Chart"}, "spec_id": None, "spec_summary": {"series": slice(1, 3, None)}}
    analysis_ctx = {"final": "TL;DR", "id": "analysis-1"}
    tasks = [{"name": "sql_execution", "status": "complete"}]
    bundle = _create_planner_bundle(
        session_id,
        "amd market share",
        planner_ctx,
        sql_ctx,
        chart_ctx,
        analysis_ctx,
        tasks,
        tool_manifest=[{"name": "web_retriever", "latency_budget_ms": 1000}],
        tool_results=[{"tool": "web_retriever", "status": "complete"}],
        stock_widget={"symbols": ["AMD"]},
        web_context={"summary": "AMD accelerated"},
    )
    assert bundle["id"].startswith("analytics:")
    assert bundle["sql"]["attempts"][0]["window"] == {"start": 0, "stop": 4, "step": 1}
    assert bundle["chart"]["summary"]["series"] == {"start": 1, "stop": 3, "step": None}
