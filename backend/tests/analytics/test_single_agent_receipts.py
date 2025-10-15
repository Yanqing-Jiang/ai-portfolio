from __future__ import annotations

from datetime import datetime, timedelta
from types import SimpleNamespace

from analytics.flows.single_agent_tools import SingleAgentController
from analytics.flows.planner_executor import ToolInvocationReceipt


def _make_receipt(tool: str, *, age_seconds: int = 0) -> ToolInvocationReceipt:
    receipt = ToolInvocationReceipt(tool=tool, status="completed")
    if age_seconds:
        receipt.timestamp = (datetime.utcnow() - timedelta(seconds=age_seconds)).isoformat()
    else:
        receipt.timestamp = datetime.utcnow().isoformat()
    return receipt


def test_should_reuse_market_based_on_receipts() -> None:
    controller = SingleAgentController()
    artifacts = SimpleNamespace(
        market=SimpleNamespace(snapshot={"widget": {"id": 1}}),
        web=None,
        analysis=None,
    )
    ctx = SimpleNamespace(
        artifacts=artifacts,
        snapshot_age_seconds=None,
        tool_receipts={
            "market_question_a": _make_receipt("market_question_a"),
            "market_question_b": _make_receipt(
                "market_question_b",
                age_seconds=controller.LANE_CACHE_TTL_SECONDS // 2,
            ),
            "stock_tracker": _make_receipt("stock_tracker"),
        },
        revision_snapshot=None,
    )
    assert controller._should_reuse_market(ctx)

    stale_age = controller.LANE_CACHE_TTL_SECONDS + 60
    ctx.tool_receipts = {
        "market_question_a": _make_receipt("market_question_a", age_seconds=stale_age),
        "market_question_b": _make_receipt("market_question_b", age_seconds=stale_age),
        "stock_tracker": _make_receipt("stock_tracker", age_seconds=stale_age),
    }
    assert not controller._should_reuse_market(ctx)


def test_should_reuse_web_receipt_ttl() -> None:
    controller = SingleAgentController()
    artifacts = SimpleNamespace(
        market=None,
        web=SimpleNamespace(summary="cached summary"),
        analysis=None,
    )
    ctx = SimpleNamespace(
        artifacts=artifacts,
        snapshot_age_seconds=None,
        tool_receipts={"web_retriever": _make_receipt("web_retriever")},
        revision_snapshot=None,
    )
    assert controller._should_reuse_web(ctx)

    ctx.tool_receipts["web_retriever"] = _make_receipt(
        "web_retriever",
        age_seconds=controller.LANE_CACHE_TTL_SECONDS + 5,
    )
    assert not controller._should_reuse_web(ctx)
