"""
Module: receipt_helpers.py
Purpose: Shared receipt and cache reuse helpers for analytics flows.
Called from: analytics.flows.single_agent_tools, analytics.flows.multi_agent,
             analytics.flows.planner_executor
Invokes: analytics.flows.planner_executor.ToolInvocationReceipt
Why: Centralizes TTL-based lane reuse logic to reduce duplication across flow modules.

Part of Phase 2.2 of the analytics refactor plan - extracting receipt logic from monolithic modules.
"""

from __future__ import annotations

from datetime import datetime
import json
from typing import Any, Dict, List, Mapping, Optional, TYPE_CHECKING

from analytics.validators import sanitize_for_json

if TYPE_CHECKING:  # pragma: no cover - typing only
    from analytics.flows.planner.context import PlannerPhaseContext
    from analytics.flows.planner.receipts import ToolInvocationReceipt

__all__ = [
    "LANE_TOOL_MAP",
    "LANE_TTL_DEFAULTS",
    "DEFAULT_CACHE_TTL_SECONDS",
    "receipt_age_seconds",
    "receipt_is_fresh",
    "lane_receipts",
    "should_reuse_web",
    "should_reuse_market",
    "should_reuse_sql",
    "should_reuse_chart",
    "apply_receipt_ttl_overrides",
]


# Default TTL for cached lane results (5 minutes)
DEFAULT_CACHE_TTL_SECONDS = 300

# Per-lane TTL overrides (30 minutes for most, 5 minutes for SQL)
LANE_TTL_DEFAULTS: Dict[str, int] = {
    "web": 1800,
    "market": 1800,
    "sql": 300,
    "chart": 1800,
    "analysis": 1800,
}

# Tool names associated with each lane
LANE_TOOL_MAP: Dict[str, tuple] = {
    "web": ("web_retriever", "web_refresh", "web_search"),
    "market": ("stock_tracker", "market_question", "market_refresh"),
    "sql": ("sql_generation", "sql_compilation", "sql_execution"),
    "chart": ("chart_generation", "chart_planning", "chart_revision"),
    "analysis": ("analysis_generation", "analysis_revision"),
}

# Input guardrail defaults
MAX_TOOL_INPUT_BYTES = 12000
MAX_TOOL_INPUT_KEYS = 128


def input_guardrail(
    payload: Any,
    *,
    max_bytes: int = MAX_TOOL_INPUT_BYTES,
    max_keys: int = MAX_TOOL_INPUT_KEYS,
) -> Optional[Dict[str, Any]]:
    """
    Function: input_guardrail
    Called from: pipeline_tools.PlannerToolRegistry.invoke
    Why: Enforces size/key-count limits before executing planner tools.
    """
    if payload is None:
        return None
    try:
        sanitized = sanitize_for_json(payload)
    except Exception:
        sanitized = payload
    key_count: Optional[int] = None
    if isinstance(sanitized, Mapping):
        key_count = len(sanitized)
        if key_count > max_keys:
            return {
                "status": "violation",
                "reason": "too_many_keys",
                "observed_keys": key_count,
                "max_keys": max_keys,
            }
    try:
        encoded = json.dumps(sanitized, default=str).encode("utf-8")
    except Exception:
        return None
    if len(encoded) > max_bytes:
        return {
            "status": "violation",
            "reason": "payload_too_large",
            "observed_bytes": len(encoded),
            "max_bytes": max_bytes,
        }
    return None


def receipt_age_seconds(receipt: "ToolInvocationReceipt") -> Optional[float]:
    """
    Function: receipt_age_seconds
    Called from: receipt_is_fresh
    Why: Computes the age of a receipt from its timestamp for TTL comparisons.
    """
    # First check if age_seconds is already set (Phase 1.2 field)
    if receipt.age_seconds is not None:
        return receipt.age_seconds
    
    timestamp = getattr(receipt, "timestamp", None)
    if not timestamp:
        return None
    
    try:
        receipt_time = datetime.fromisoformat(str(timestamp).replace("Z", "+00:00"))
        now = datetime.now(receipt_time.tzinfo) if receipt_time.tzinfo else datetime.now()
        delta = now - receipt_time
        return delta.total_seconds()
    except (ValueError, TypeError):
        return None


def receipt_is_fresh(
    receipt: Optional["ToolInvocationReceipt"],
    *,
    ttl_seconds: Optional[int] = None,
) -> bool:
    """
    Function: receipt_is_fresh
    Called from: should_reuse_web, should_reuse_market, should_reuse_sql, should_reuse_chart
    Why: Determines whether a cached tool receipt is still within the lane TTL window.
    """
    from analytics.flows.planner.receipts import ToolInvocationReceipt
    
    if receipt is None:
        return False
    
    # Handle dict-like receipts
    materialized = receipt
    if isinstance(receipt, Mapping) and not isinstance(receipt, ToolInvocationReceipt):
        try:
            materialized = ToolInvocationReceipt.from_dict(receipt)
        except Exception:
            return False
    
    if materialized is None:
        return False
    
    # Check status
    status = str(getattr(materialized, "status", "")).strip().lower()
    if status not in {"completed", "complete", "success", "reused"}:
        return False
    
    # Check for errors
    if getattr(materialized, "error", None):
        return False
    
    # Check from_cache field (Phase 1.2)
    if getattr(materialized, "from_cache", False):
        # Already cached, use its age
        age = receipt_age_seconds(materialized)
        if age is None:
            return False
        ttl = ttl_seconds or materialized.ttl_seconds or DEFAULT_CACHE_TTL_SECONDS
        return age <= ttl
    
    # Check age
    age = receipt_age_seconds(materialized)
    if age is None:
        return False
    
    ttl = ttl_seconds or DEFAULT_CACHE_TTL_SECONDS
    return age <= ttl


def lane_receipts(
    ctx: "PlannerPhaseContext",
    lane: str,
    *,
    tool_map: Optional[Dict[str, tuple]] = None,
) -> List["ToolInvocationReceipt"]:
    """
    Function: lane_receipts
    Called from: should_reuse_web, should_reuse_market, should_reuse_sql, should_reuse_chart
    Why: Collects cached tool receipts relevant to a given lane.
    """
    from analytics.flows.planner.receipts import ToolInvocationReceipt
    
    lane_key = (lane or "").strip().lower()
    if not lane_key:
        return []
    
    tool_receipts = getattr(ctx, "tool_receipts", {}) or {}
    candidates = (tool_map or LANE_TOOL_MAP).get(lane_key, ())
    
    resolved: Dict[str, ToolInvocationReceipt] = {}
    for tool_name, payload in tool_receipts.items():
        normalized = str(tool_name or "").strip().lower()
        if not normalized:
            continue
        if normalized in candidates or any(normalized.startswith(c) for c in candidates):
            if isinstance(payload, ToolInvocationReceipt):
                resolved[normalized] = payload
            elif isinstance(payload, Mapping):
                try:
                    resolved[normalized] = ToolInvocationReceipt.from_dict(payload)
                except Exception:
                    continue
    
    return list(resolved.values())


def should_reuse_web(
    ctx: "PlannerPhaseContext",
    *,
    ttl_seconds: Optional[int] = None,
    tool_map: Optional[Dict[str, tuple]] = None,
) -> bool:
    """
    Function: should_reuse_web
    Called from: apply_receipt_ttl_overrides, SingleAgentController, MultiAgentFlow
    Why: Decides whether the web lane can be reused from cached artifacts + receipts.
    """
    artifacts = getattr(ctx, "artifacts", None)
    web_art = getattr(artifacts, "web", None) if artifacts else None
    summary = getattr(web_art, "summary", None) if web_art else None
    snippets = getattr(web_art, "snippets", None) if web_art else None
    
    has_web_artifacts = bool(
        (isinstance(summary, str) and summary.strip())
        or (isinstance(snippets, (list, tuple)) and any(snippets))
    )
    if not has_web_artifacts:
        return False
    
    ttl = ttl_seconds or LANE_TTL_DEFAULTS.get("web", DEFAULT_CACHE_TTL_SECONDS)
    
    snapshot_age = getattr(ctx, "snapshot_age_seconds", None)
    if snapshot_age is not None and snapshot_age > ttl:
        return False
    
    receipts = lane_receipts(ctx, "web", tool_map=tool_map)
    if not receipts:
        return False
    
    return all(receipt_is_fresh(r, ttl_seconds=ttl) for r in receipts)


def should_reuse_market(
    ctx: "PlannerPhaseContext",
    *,
    ttl_seconds: Optional[int] = None,
    tool_map: Optional[Dict[str, tuple]] = None,
) -> bool:
    """
    Function: should_reuse_market
    Called from: apply_receipt_ttl_overrides, SingleAgentController, MultiAgentFlow
    Why: Decides whether the market lane can be reused from cached artifacts + receipts.
    """
    artifacts = getattr(ctx, "artifacts", None)
    market_art = getattr(artifacts, "market", None) if artifacts else None
    has_snapshot = bool(getattr(market_art, "snapshot", None))
    
    if not has_snapshot:
        return False
    
    ttl = ttl_seconds or LANE_TTL_DEFAULTS.get("market", DEFAULT_CACHE_TTL_SECONDS)
    
    snapshot_age = getattr(ctx, "snapshot_age_seconds", None)
    if snapshot_age is not None and snapshot_age > ttl:
        return False
    
    receipts = lane_receipts(ctx, "market", tool_map=tool_map)
    if not receipts:
        return False
    
    return all(receipt_is_fresh(r, ttl_seconds=ttl) for r in receipts)


def should_reuse_sql(
    ctx: "PlannerPhaseContext",
    *,
    ttl_seconds: Optional[int] = None,
    tool_map: Optional[Dict[str, tuple]] = None,
) -> bool:
    """
    Function: should_reuse_sql
    Called from: apply_receipt_ttl_overrides, SingleAgentController, MultiAgentFlow
    Why: Decides whether the SQL lane can be reused from cached artifacts + receipts.
    """
    artifacts = getattr(ctx, "artifacts", None)
    sql_art = getattr(artifacts, "sql_generation", None) if artifacts else None
    sql_text = getattr(sql_art, "sql", None) if sql_art else None
    sql_exec = getattr(artifacts, "sql_execution", None) if artifacts else None
    sql_error = getattr(sql_exec, "error", None) if sql_exec else None
    sql_error_code = getattr(sql_exec, "error_code", None) if sql_exec else None
    
    if not sql_text or sql_error or sql_error_code:
        return False
    
    ttl = ttl_seconds or LANE_TTL_DEFAULTS.get("sql", DEFAULT_CACHE_TTL_SECONDS)
    
    snapshot_age = getattr(ctx, "snapshot_age_seconds", None)
    if snapshot_age is not None and snapshot_age > ttl:
        return False
    
    receipts = lane_receipts(ctx, "sql", tool_map=tool_map)
    if not receipts:
        return False
    
    return all(receipt_is_fresh(r, ttl_seconds=ttl) for r in receipts)


def should_reuse_chart(
    ctx: "PlannerPhaseContext",
    *,
    sql_refresh_required: bool = False,
    ttl_seconds: Optional[int] = None,
    tool_map: Optional[Dict[str, tuple]] = None,
) -> bool:
    """
    Function: should_reuse_chart
    Called from: apply_receipt_ttl_overrides, SingleAgentController, MultiAgentFlow
    Why: Decides whether the chart lane can be reused when SQL remains fresh.
    """
    if sql_refresh_required:
        return False
    
    artifacts = getattr(ctx, "artifacts", None)
    chart_art = getattr(artifacts, "chart", None) if artifacts else None
    chart_spec = getattr(chart_art, "spec", None) if chart_art else None
    
    if not chart_spec:
        return False
    
    ttl = ttl_seconds or LANE_TTL_DEFAULTS.get("chart", DEFAULT_CACHE_TTL_SECONDS)
    
    snapshot_age = getattr(ctx, "snapshot_age_seconds", None)
    if snapshot_age is not None and snapshot_age > ttl:
        return False
    
    receipts = lane_receipts(ctx, "chart", tool_map=tool_map)
    if not receipts:
        return False
    
    return all(receipt_is_fresh(r, ttl_seconds=ttl) for r in receipts)


def apply_receipt_ttl_overrides(
    ctx: "PlannerPhaseContext",
    *,
    after_preflight: bool = False,
    ttl_seconds: Optional[int] = None,
    tool_map: Optional[Dict[str, tuple]] = None,
) -> Dict[str, bool]:
    """
    Function: apply_receipt_ttl_overrides
    Called from: SingleAgentController._prepare_sequencer_state, MultiAgentFlow
    Why: Applies TTL-based lane reuse overrides so allowlists drop fresh lanes.
    
    Returns the updated lane_refresh_required dict.
    """
    refresh_flags = dict(getattr(ctx, "lane_refresh_required", {}) or {})
    
    # Web lane
    if refresh_flags.get("web", True) and should_reuse_web(ctx, ttl_seconds=ttl_seconds, tool_map=tool_map):
        refresh_flags["web"] = False
    
    # Market lane
    if refresh_flags.get("market", True) and should_reuse_market(ctx, ttl_seconds=ttl_seconds, tool_map=tool_map):
        refresh_flags["market"] = False
    
    # Core lanes only after preflight (intent + plan sealed)
    if after_preflight:
        sql_refresh = refresh_flags.get("sql", True)
        if sql_refresh and should_reuse_sql(ctx, ttl_seconds=ttl_seconds, tool_map=tool_map):
            refresh_flags["sql"] = False
            sql_refresh = False
        
        if refresh_flags.get("chart", True) and should_reuse_chart(
            ctx, sql_refresh_required=sql_refresh, ttl_seconds=ttl_seconds, tool_map=tool_map
        ):
            refresh_flags["chart"] = False
    
    # Update context
    ctx.lane_refresh_required = refresh_flags  # type: ignore[attr-defined]
    return refresh_flags

