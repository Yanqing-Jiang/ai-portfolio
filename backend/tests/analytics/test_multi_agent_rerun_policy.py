import sys
from pathlib import Path
import types

sys.path.append(str(Path(__file__).resolve().parents[2]))

google_stub = sys.modules.setdefault("google", types.ModuleType("google"))
google_stub.__path__ = []
genai_stub = types.ModuleType("google.genai")
genai_types_stub = types.ModuleType("google.genai.types")
setattr(genai_stub, "types", genai_types_stub)
setattr(google_stub, "genai", genai_stub)
sys.modules["google.genai"] = genai_stub
sys.modules["google.genai.types"] = genai_types_stub

from analytics.flows.multi_agent import MultiAgentFlow
from analytics.routing import FollowUpRoute


def test_lane_summary_emits_chart_revision_when_sql_reused():
    flow = MultiAgentFlow()
    flow._prepare_context("NVDA guidance rerun")

    sql_ctx = flow._shared_context["sql"]
    sql_ctx.update({"sql": "SELECT 1", "row_count": 12, "status": "reused"})

    chart_ctx = flow._shared_context["chart"]
    chart_ctx.update({"spec": {"title": "Price Trend"}, "status": "fresh"})

    analysis_ctx = flow._shared_context["analysis"]
    analysis_ctx["final"] = "Updated analysis"
    analysis_ctx["length"] = 18

    stock_widget = {"symbols": [["NASDAQ:AAPL", "AAPL"]]}
    flow._shared_context["stock_widget"] = stock_widget
    market_ctx = flow._shared_context["market"]
    market_ctx.update({"snapshot": stock_widget, "source": "cached"})

    web_ctx = flow._shared_context["web"]
    web_ctx.update({"summary": "Cached context", "source": "cached"})

    flow._shared_context.setdefault("_meta", {})["bundle_sources"] = {
        "stock_tracker": "cached",
        "web_retriever": "cached",
    }

    lane_states = flow._lane_state_snapshot()
    assert lane_states["sql"] == "reused"
    assert lane_states["chart"] == "fresh"

    event = flow._emit_lane_summary(lane_states)
    assert event is not None
    data = event["data"]
    assert data["decision"] == "chart_revision"
    scope = data.get("rerun_scope") or {}
    assert "chart" in scope.get("rerun", [])
    assert "sql" in scope.get("reuse", [])
    assert scope.get("route") == FollowUpRoute.REUSE_SQL.value
    assert flow.follow_up_route == FollowUpRoute.REUSE_SQL

    # Subsequent emissions should no-op once summary recorded.
    assert flow._emit_lane_summary(lane_states) is None
