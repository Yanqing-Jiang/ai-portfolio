from __future__ import annotations

import argparse
import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Dict, Iterable, Tuple, Any
from pathlib import Path
import sys

BACKEND_DIR = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BACKEND_DIR.parent
for candidate in (str(BACKEND_DIR), str(PROJECT_ROOT)):
    if candidate not in sys.path:
        sys.path.insert(0, candidate)

from analytics.core.session_state import (  # noqa: E402
    SessionStateSnapshot,
    close_session_state_repository,
    get_session_state_repository,
)
from analytics.flows.planner_executor import ToolInvocationReceipt  # noqa: E402
from analytics.prompt_versions import get_prompt_versions  # noqa: E402
from analytics.routing import FollowUpRoute  # noqa: E402
from analytics.flows.schedulers import FlowMode  # noqa: E402

logger = logging.getLogger(__name__)

DEFAULT_SESSION_ID = "agentic-analytics-staging"
DEFAULT_QUERY = "How did ACME's gross margin trend versus peers last quarter?"


def _build_tool_receipt(
    tool: str,
    *,
    lane: str,
    parallel_group: str,
    reused: bool,
    metadata: Dict[str, Any],
    elapsed_ms: int,
) -> ToolInvocationReceipt:
    """
    Construct a deterministic receipt mirroring what planner_executor stores.

    The metadata mirrors the telemetry observed in staging:
      - lane: identifies the ProcessPanel lane (e.g. ``market`` or ``web``)
      - parallel_group: matches the scheduler parallelism bucket
      - question_id/search_id: gives downstream exporters continuity
    """
    enriched_metadata = {**metadata, "lane": lane, "parallel_group": parallel_group}
    receipt = ToolInvocationReceipt(
        tool=tool,
        status="reused" if reused else "completed",
        attempts=1,
        metadata=enriched_metadata,
        reused=reused,
        elapsed_ms=elapsed_ms,
    )
    return receipt


def _build_snapshot(session_id: str, *, reuse_age_seconds: float) -> SessionStateSnapshot:
    prompt_versions = get_prompt_versions()
    snapshot = SessionStateSnapshot(session_id=session_id)
    snapshot.record_query(DEFAULT_QUERY, intent_key="margin_outlook_vs_peers")

    # Persist cached receipts for both market questions so reuse kicks in immediately.
    market_receipts: Iterable[Tuple[str, Dict[str, Any]]] = (
        (
            "market_question_a",
            {"question_id": "market_question_a", "prompt_versions": dict(prompt_versions)},
        ),
        (
            "market_question_b",
            {"question_id": "market_question_b", "prompt_versions": dict(prompt_versions)},
        ),
    )
    for tool_name, meta in market_receipts:
        receipt = _build_tool_receipt(
            tool_name,
            lane="market",
            parallel_group="single_agent_market",
            reused=True,
            metadata=meta,
            elapsed_ms=1150,
        )
        snapshot.record_tool_receipt(tool_name, receipt.to_dict())

    web_receipt = _build_tool_receipt(
        "web_retriever",
        lane="web",
        parallel_group="single_agent_web",
        reused=True,
        metadata={
            "search_id": "web-analytics-001",
            "prompt_versions": dict(prompt_versions),
        },
        elapsed_ms=720,
    )
    snapshot.record_tool_receipt("web_retriever", web_receipt.to_dict())

    # Capture the revision snapshot used by the controller to hydrate cached lanes.
    snapshot.record_revision_snapshot(
        {
            "stock_widget": {
                "quote": 123.45,
                "ticker": "ACME",
                "receipt_id": "mkt-cache-001",
                "cached_at": datetime.now(timezone.utc).isoformat(),
            },
            "web_context": {
                "summary": "Cached competitor margin analysis seeded for reuse.",
                "snippets": [
                    {
                        "title": "Analyst update highlights ACME margin resilience",
                        "url": "https://example.com/insight/acme-margin",
                    }
                ],
                "search_id": "web-analytics-001",
                "cached_at": datetime.now(timezone.utc).isoformat(),
            },
            "snapshot_age_seconds": reuse_age_seconds,
        }
    )

    planner_meta = snapshot.tool_cache.setdefault("planner_metadata", {})
    planner_meta.update(
        {
            "follow_up_route": FollowUpRoute.REUSE_SQL.value,
            "prompt_versions": prompt_versions,
            "snapshot_age_seconds": reuse_age_seconds,
        }
    )
    snapshot.tool_cache["planner_metadata"] = planner_meta

    analytics_meta = snapshot.tool_cache.setdefault("analytics", {})
    analytics_meta["cached_receipts_seeded_at"] = datetime.now(timezone.utc).isoformat()
    analytics_meta["cached_session_example"] = True
    analytics_meta["prompt_versions"] = prompt_versions
    snapshot.tool_cache["analytics"] = analytics_meta

    snapshot.record_schedule_stage(
        stage="tool_parallelism",
        parallel_group="tool_fanout",
        event="cached_receipts_seeded",
        ts=datetime.now(timezone.utc).isoformat(),
        flow_mode=FlowMode.SINGLE_AGENT.value,
    )
    return snapshot


async def _persist_snapshot(session_id: str, *, dry_run: bool, reuse_age_seconds: float) -> None:
    snapshot = _build_snapshot(session_id, reuse_age_seconds=reuse_age_seconds)
    if dry_run:
        payload = json.dumps(snapshot.snapshot(), indent=2, sort_keys=True)
        print(payload)
        return

    repo = get_session_state_repository()
    await repo.save(snapshot)
    await repo.touch(session_id)
    logger.info("Seeded analytics session '%s' with cached receipts.", session_id)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Seed staging Redis with cached agentic analytics receipts.",
    )
    parser.add_argument(
        "--session-id",
        default=DEFAULT_SESSION_ID,
        help="Session identifier to hydrate (default: %(default)s).",
    )
    parser.add_argument(
        "--reuse-age-seconds",
        type=float,
        default=42.0,
        help="Synthetic snapshot_age_seconds to record for seeded receipts.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the snapshot payload instead of writing to the repository.",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Log level for script output.",
    )
    return parser.parse_args()


async def _async_main() -> None:
    args = _parse_args()
    logging.basicConfig(level=getattr(logging, args.log_level))
    try:
        await _persist_snapshot(
            args.session_id,
            dry_run=args.dry_run,
            reuse_age_seconds=args.reuse_age_seconds,
        )
    finally:
        await close_session_state_repository()


def main() -> None:
    asyncio.run(_async_main())


if __name__ == "__main__":
    main()
