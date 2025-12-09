# --- Analytics Function/Class Map ---
# Function: hash_payload
#   Role: Produces a stable SHA1 digest for payload deduping/telemetry.
#   Called from: analytics.flows.planner_executor, analytics.flows.single_agent_tools, analytics.flows.multi_agent
#   Invokes: analytics.validators.sanitize_for_json, json.dumps, hashlib.sha1
#   Why: Normalizes tool inputs/outputs for receipts and cache reuse.
# Function: normalize_metric_slots
#   Role: Normalizes metric slot statuses to clear missing/followups when values exist.
#   Called from: analytics.flows.planner_executor intent stage helpers
#   Invokes: slot_state.model_copy
#   Why: Keeps intent resolution consistent before planning and clarifications.
# Function: build_slot_assumptions
#   Role: Derives assumption strings for defaulted/assumed slots.
#   Called from: analytics.flows.planner_executor intent stage helpers
#   Invokes: None
#   Why: Annotates intent/plan context with slot defaults for downstream prompts.
# Function: _safe_year
#   Role: Coerces incoming values to a safe integer year for dataset summaries.
#   Called from: analytics.flows.planner_executor dataset summarization helpers
#   Invokes: int, str.strip
#   Why: Centralizes tolerant year parsing to avoid duplicated heuristics.
# Function: _safe_date
#   Role: Coerces incoming values to a date for dataset summaries.
#   Called from: analytics.flows.planner_executor dataset summarization helpers
#   Invokes: datetime.fromisoformat, date.isoformat
#   Why: Keeps date parsing consistent when summarizing planner SQL outputs.
# Function: _summarize_sql_rows
#   Role: Builds column/metric/timeframe summaries for SQL dataset previews.
#   Called from: analytics.flows.planner_executor SQL execution artifacts
#   Invokes: _safe_year, _safe_date
#   Why: Provides reusable dataset preview metadata shared across modes.
# Function: ensure_tool_receipt
#   Role: Creates/updates a tool receipt with common status/reuse metadata.
#   Called from: analytics.flows.planner_executor
#   Invokes: None
#   Why: Centralizes receipt mutation to keep parity across flows.
# Function: _extract_tldr
#   Role: Extracts the first sentence from narrative text for tldr display.
#   Called from: analytics.flows.planner_executor analysis artifact helpers
#   Invokes: str.split
#   Why: Centralizes tldr extraction for analysis artifacts.
# Function: _extract_bullets
#   Role: Extracts bullet points from markdown-like text.
#   Called from: analytics.flows.planner_executor analysis artifact helpers
#   Invokes: str.splitlines
#   Why: Centralizes bullet extraction for analysis artifacts.
# Function: _split_line
#   Role: Splits a text line into sentence fragments.
#   Called from: analytics.flows.planner.stage_helpers._collect_sentences
#   Invokes: _SENTENCE_SPLIT regex
#   Why: Supports sentence extraction for numeric/risk/action analysis.
# Function: _normalize_sentence
#   Role: Normalizes whitespace in sentence fragments.
#   Called from: analytics.flows.planner.stage_helpers._collect_sentences
#   Invokes: re.sub
#   Why: Deduplicates and cleans sentences for evidence extraction.
# Function: _collect_sentences
#   Role: Collects unique, normalized sentences from text.
#   Called from: analytics.flows.planner.stage_helpers._extract_*
#   Invokes: _split_line, _normalize_sentence
#   Why: Shared sentence parsing for key number and risk extraction.
# Function: _extract_key_numbers
#   Role: Extracts sentences containing numeric indicators.
#   Called from: analytics.flows.planner_executor analysis artifact helpers
#   Invokes: _collect_sentences
#   Why: Highlights quantitative findings in analysis artifacts.
# Function: _extract_risk_watch
#   Role: Extracts sentences mentioning risk-related terms.
#   Called from: analytics.flows.planner_executor analysis artifact helpers
#   Invokes: _collect_sentences
#   Why: Surfaces risk indicators in analysis artifacts.
# Function: _extract_next_steps
#   Role: Extracts sentences containing action-oriented language.
#   Called from: analytics.flows.planner_executor analysis artifact helpers
#   Invokes: _collect_sentences
#   Why: Surfaces actionable recommendations in analysis artifacts.
# Function: _evaluate_latency_guardrail
#   Role: Checks observed latency stats against configurable thresholds.
#   Called from: analytics.flows.multi_agent, analytics.flows.agents_stream_bridge
#   Invokes: None
#   Why: Enforces latency guardrails and exposes violation metadata.
# Function: _build_evidence_entries
#   Role: Constructs evidence entries from web search snippets.
#   Called from: analytics.flows.planner_executor analysis artifact helpers
#   Invokes: None
#   Why: Formats web evidence for analysis artifact display.
# Function: _clear_tool_state
#   Role: Removes cached tool receipts/results for given tool ids.
#   Called from: analytics.flows.planner_executor, analytics.flows.single_agent_tools
#   Invokes: Internal filtering on PlannerPhaseContext receipt/state fields
#   Why: Ensures accessory refresh/reset clears prior tool artifacts.
# Function: _reset_revision_accessories
#   Role: Resets web/market accessory state for revision reruns.
#   Called from: analytics.flows.planner_executor, analytics.flows.single_agent_tools
#   Invokes: _clear_tool_state
#   Why: Forces accessory lanes to rerun when refresh is required.
# Function: _build_revision_snapshot_payload
#   Role: Builds revision snapshot payload from the current planner context.
#   Called from: analytics.flows.planner_executor
#   Invokes: analytics.core.revision_snapshot.build_intent_signature, analytics.flows.planner.sql_lane.limit_sample_rows
#   Why: Persists planner outputs for revision reuse with TTLs.
# Function: _hydrate_context_from_snapshot
#   Role: Hydrates PlannerPhaseContext from a SessionStateSnapshot payload.
#   Called from: analytics.flows.planner_executor
#   Invokes: analytics.core.revision_snapshot.extract_revision_snapshot, analytics.artifacts.*
#   Why: Restores cached lane artifacts/receipts for revision flows.
# Function: _apply_revision_context_hints
#   Role: Applies revision_context refresh hints and reasoning to context.
#   Called from: analytics.flows.planner_executor
#   Invokes: _hydrate_revision_payload
#   Why: Honors revision TTL hints and cached payloads across lanes.
# Function: _hydrate_revision_payload
#   Role: Hydrates PlannerPhaseContext from a revision payload dict.
#   Called from: analytics.flows.planner_executor
#   Invokes: Intent/plan/slot model coercion helpers
#   Why: Reuses revision data without recomputing classification/intent.
# --- End Analytics Function/Class Map ---
from __future__ import annotations

import copy
import hashlib
import json
import os
import re
from datetime import date, datetime
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, TYPE_CHECKING

from analytics.validators import sanitize_for_json

if TYPE_CHECKING:
    from analytics.services.session_state import SessionStateSnapshot
    from analytics.artifacts import (
        AnalysisArtifact,
        ChartArtifact,
        PipelineArtifacts,
        SQLExecutionArtifact,
        SQLGenerationArtifact,
        WebContextArtifact,
    )
    from analytics.core.intent import OffTopicClassifierSchema, IntentModel
    from analytics.core.intent_impl.models import FollowUpModel, IntentResolutionModel, SlotStatusModel
    from analytics.core.types import ClarifyRequestModel, QueryPlanModel
    from analytics.flows.planner.context import PlannerPhaseContext

# ─────────────────────────────────────────────────────────────────────────────
# Text Extraction Constants
# ─────────────────────────────────────────────────────────────────────────────
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")
_DEFAULT_GUARDRAIL_P50 = int(os.getenv("WEB_SEARCH_GUARDRAIL_P50_MS", "1200"))
_DEFAULT_GUARDRAIL_P95 = int(os.getenv("WEB_SEARCH_GUARDRAIL_P95_MS", "2500"))
_RISK_TERMS = (
    "risk",
    "headwind",
    "concern",
    "pressure",
    "downside",
    "volatility",
    "slowdown",
    "uncertain",
    "watchlist",
    "caution",
)
_ACTION_TERMS = (
    "consider",
    "monitor",
    "focus",
    "plan to",
    "plan for",
    "watch",
    "track",
    "follow up",
    "prepare",
    "should",
    "next step",
    "next steps",
    "keep an eye",
)
_NUMERIC_HINTS = ("%", "bps", "basis point", "million", "billion", "m$", "bn")


def hash_payload(payload: Any) -> str:
    """Return a deterministic hash for an arbitrary payload."""
    try:
        normalized = sanitize_for_json(payload)
    except Exception:
        normalized = payload
    try:
        encoded = json.dumps(
            normalized,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
    except TypeError:
        encoded = json.dumps(str(normalized), sort_keys=True).encode("utf-8")
    return hashlib.sha1(encoded).hexdigest()


def normalize_metric_slots(resolution: Any) -> None:
    """Mark metric slots as defaulted when values are present to clear followups."""
    if resolution is None or not hasattr(resolution, "slots"):
        return

    def _normalize(slot_name: str) -> None:
        slot_state = resolution.slots.get(slot_name)
        if slot_state is None:
            return
        value = getattr(slot_state, "value", None)
        has_value = False
        if isinstance(value, (list, tuple, set)):
            has_value = any(item is not None for item in value)
        elif value not in (None, "", []):
            has_value = True
        if getattr(slot_state, "status", None) == "missing" and has_value:
            if hasattr(slot_state, "model_copy"):
                resolution.slots[slot_name] = slot_state.model_copy(update={"status": "defaulted"})
        updated = resolution.slots.get(slot_name)
        if updated and getattr(updated, "status", None) != "missing":
            resolution.followups = [
                followup
                for followup in list(getattr(resolution, "followups", []) or [])
                if getattr(followup, "slot", None) != slot_name
            ]

    _normalize("metric")
    _normalize("metrics")


def build_slot_assumptions(slots: Mapping[str, Any]) -> List[str]:
    """Compose human-readable assumption statements for slots."""
    assumptions: List[str] = []
    for slot_name, status in (slots or {}).items():
        if not hasattr(status, "status"):
            continue
        slot_status = getattr(status, "status", None)
        value = getattr(status, "value", None)
        if slot_status == "defaulted" and value is not None:
            assumptions.append(f"{slot_name} defaulted to {value}")
        elif slot_status == "assumed":
            assumptions.append(f"{slot_name} assumed ({slot_status})")
    return assumptions


def _safe_year(value: Any) -> Optional[int]:
    """Parse a loose value into a year integer when possible."""
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return int(value)
    if isinstance(value, str):
        stripped = value.strip()
        if stripped.isdigit() and len(stripped) <= 4:
            return int(stripped)
    return None


def _safe_date(value: Any) -> Optional[date]:
    """Parse a loose value into a date when possible."""
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return None
        cleaned = stripped.rstrip("Z")
        try:
            return datetime.fromisoformat(cleaned).date()
        except ValueError:
            return None
    return None


def _summarize_sql_rows(data: Optional[List[Dict[str, Any]]]) -> Dict[str, Any]:
    """Create column/metric/timeframe summaries for SQL dataset previews."""
    if not isinstance(data, list):
        data = []
    columns: List[str] = sorted({key for row in data if isinstance(row, dict) for key in row.keys()})
    sample_rows: List[Dict[str, Any]] = []
    for row in data[:5]:
        if isinstance(row, dict):
            sample_rows.append({column: row.get(column) for column in columns})
    tickers = sorted(
        {
            str(row.get("ticker")).strip()
            for row in data
            if isinstance(row, dict) and row.get("ticker")
        }
    )
    metric_keys = ("metric", "metric_name", "series", "measure", "line_item")
    metrics = sorted(
        {
            str(row.get(key)).strip()
            for row in data
            if isinstance(row, dict)
            for key in metric_keys
            if row.get(key)
        }
    )
    years: List[int] = []
    dates: List[date] = []
    for row in data:
        if not isinstance(row, dict):
            continue
        for key, value in row.items():
            lower = key.lower()
            if "year" in lower:
                maybe_year = _safe_year(value)
                if maybe_year is not None:
                    years.append(maybe_year)
            if "date" in lower or "period" in lower:
                maybe_date = _safe_date(value)
                if maybe_date is not None:
                    dates.append(maybe_date)
    timeframe: Dict[str, Any] = {}
    if years:
        timeframe["years"] = {"min": min(years), "max": max(years)}
    if dates:
        timeframe["dates"] = {
            "start": min(dates).isoformat(),
            "end": max(dates).isoformat(),
        }
    return {
        "columns": columns,
        "sample_rows": sample_rows,
        "tickers": tickers,
        "metrics": metrics,
        "timeframe": timeframe,
    }


def ensure_tool_receipt(
    ctx: Any,
    tool: str,
    *,
    status: str,
    reused: bool = False,
    attempts: Optional[int] = None,
    input_hash: Optional[str] = None,
    output_hash: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Any:
    """
    Create or update a tool receipt with consistent fields.

    - status: receipt status (running/reused/completed/failed)
    - reused: flag for cache hits
    - attempts: override attempts counter (default increments by one)
    """
    receipts = getattr(ctx, "tool_receipts", None)
    if receipts is None:
        receipts = {}
        ctx.tool_receipts = receipts
    receipt = receipts.get(tool)
    if receipt is None:
        from analytics.flows.planner.receipts import ToolInvocationReceipt  # local import to avoid cycles

        receipt = ToolInvocationReceipt(
            tool=tool,
            status=status,
            attempts=attempts if attempts is not None else 0,
            reused=reused,
            input_hash=input_hash,
            output_hash=output_hash,
            metadata=dict(metadata or {}),
        )
        receipts[tool] = receipt
        return receipt

    receipt.status = status
    receipt.reused = reused
    if attempts is not None:
        receipt.attempts = attempts
    elif status == "running":
        receipt.attempts = 0
    receipt.error = None
    receipt.output_hash = output_hash
    if input_hash and not receipt.input_hash:
        receipt.input_hash = input_hash
    if metadata:
        meta = dict(getattr(receipt, "metadata", {}) or {})
        meta.update(metadata)
        receipt.metadata = meta
    receipts[tool] = receipt
    return receipt


# ─────────────────────────────────────────────────────────────────────────────
# Text Extraction Helpers
# ─────────────────────────────────────────────────────────────────────────────


def _extract_tldr(text: str) -> Optional[str]:
    """Extract first sentence from narrative text for tldr display."""
    stripped = (text or "").strip()
    if not stripped:
        return None
    first_paragraph = stripped.split("\n\n", 1)[0].strip()
    first_sentence = first_paragraph.split(". ", 1)[0].strip()
    return first_sentence[:240] if first_sentence else None


def _extract_bullets(text: str, limit: int = 3) -> List[str]:
    """Extract bullet points from markdown-like text."""
    bullets: List[str] = []
    for line in (text or "").splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped[0] in {"-", "*", "\u2022"}:
            content = stripped.lstrip("-* \u2022").strip()
            if content:
                bullets.append(content)
        if len(bullets) >= limit:
            break
    return bullets


def _split_line(line: str) -> List[str]:
    """Split a text line into sentence fragments."""
    stripped = line.strip()
    if not stripped:
        return []
    if stripped[0] in {"-", "*", "\u2022"}:
        cleaned = stripped.lstrip("-*\u2022 ").strip()
        return [cleaned] if cleaned else []
    return _SENTENCE_SPLIT.split(stripped)


def _normalize_sentence(sentence: str) -> Optional[str]:
    """Normalize whitespace in sentence fragments."""
    cleaned = re.sub(r"\s+", " ", sentence or "").strip()
    return cleaned or None


def _collect_sentences(text: str) -> List[str]:
    """Collect unique, normalized sentences from text."""
    sentences: List[str] = []
    seen: set[str] = set()
    for raw_line in (text or "").splitlines():
        for fragment in _split_line(raw_line):
            normalized = _normalize_sentence(fragment)
            if not normalized:
                continue
            lowered = normalized.lower()
            if lowered in seen:
                continue
            seen.add(lowered)
            sentences.append(normalized)
    return sentences


def _extract_key_numbers(text: str, limit: int = 3) -> List[str]:
    """Extract sentences containing numeric indicators."""
    sentences = _collect_sentences(text)
    key_numbers: List[str] = []
    for sentence in sentences:
        lowered = sentence.lower()
        has_numeric = any(char.isdigit() for char in sentence)
        if not has_numeric and not any(hint in lowered for hint in _NUMERIC_HINTS):
            continue
        key_numbers.append(sentence[:240])
        if len(key_numbers) >= limit:
            break
    return key_numbers


def _extract_risk_watch(text: str, limit: int = 2) -> List[str]:
    """Extract sentences mentioning risk-related terms."""
    sentences = _collect_sentences(text)
    risks: List[str] = []
    for sentence in sentences:
        lowered = sentence.lower()
        if any(term in lowered for term in _RISK_TERMS):
            risks.append(sentence[:240])
        if len(risks) >= limit:
            break
    return risks


def _extract_next_steps(text: str, limit: int = 2) -> List[str]:
    """Extract sentences containing action-oriented language."""
    sentences = _collect_sentences(text)
    next_steps: List[str] = []
    for sentence in sentences:
        lowered = sentence.lower()
        if any(term in lowered for term in _ACTION_TERMS):
            next_steps.append(sentence[:240])
        if len(next_steps) >= limit:
            break
    return next_steps


def _evaluate_latency_guardrail(
    stats: Optional[Dict[str, Any]],
    *,
    p50_threshold: Optional[int] = None,
    p95_threshold: Optional[int] = None,
) -> Optional[Dict[str, Any]]:
    """Check observed latency stats against configurable thresholds."""
    if not stats or not isinstance(stats, dict):
        return None

    observed_p50 = stats.get("p50_ms")
    observed_p95 = stats.get("p95_ms") or stats.get("max_ms")
    observed_total = stats.get("total_ms")
    thresholds = {
        "p50_ms": p50_threshold if p50_threshold is not None else _DEFAULT_GUARDRAIL_P50,
        "p95_ms": p95_threshold if p95_threshold is not None else _DEFAULT_GUARDRAIL_P95,
    }

    violations: List[str] = []
    if isinstance(observed_p50, (int, float)) and observed_p50 > thresholds["p50_ms"]:
        violations.append("p50_ms")
    if isinstance(observed_p95, (int, float)) and observed_p95 > thresholds["p95_ms"]:
        violations.append("p95_ms")

    status = "ok"
    if violations:
        status = "violation"

    guardrail_payload: Dict[str, Any] = {
        "status": status,
        "violations": violations,
        "observed": {
            key: stats.get(key)
            for key in ("total_ms", "p50_ms", "p95_ms", "max_ms", "samples")
            if stats.get(key) is not None
        },
        "thresholds": thresholds,
    }
    if observed_total is not None and guardrail_payload["observed"].get("total_ms") is None:
        guardrail_payload["observed"]["total_ms"] = observed_total
    return guardrail_payload


def _build_evidence_entries(
    *,
    web_context: Optional[Dict[str, Any]],
    highlights: Optional[List[str]],
    summary: Optional[str],
    max_items: int = 5,
) -> List[Dict[str, Any]]:
    """Construct evidence entries from web search snippets."""
    if not web_context or not isinstance(web_context, dict):
        return []

    snippets = web_context.get("snippets") or []
    if not isinstance(snippets, list):
        return []

    claims: List[str] = []
    if summary:
        claims.append(summary)
    if highlights:
        claims.extend(highlights)

    evidence: List[Dict[str, Any]] = []
    seen_urls: set[str] = set()

    for index, raw_snippet in enumerate(snippets):
        if not isinstance(raw_snippet, dict):
            continue
        url = raw_snippet.get("url") or ""
        normalized_url = url.strip().lower()
        if not normalized_url or normalized_url in seen_urls:
            continue
        snippet_text = raw_snippet.get("snippet") or ""
        title = raw_snippet.get("title") or ""
        entry: Dict[str, Any] = {
            "url": url,
            "title": title,
            "snippet": snippet_text[:500],
            "source_index": index,
        }
        # Confidence scoring based on snippet overlap with claims
        confidence: Optional[float] = raw_snippet.get("confidence")
        if confidence is None or not isinstance(confidence, (int, float)):
            claim_overlap = 0.0
            snippet_lower = snippet_text.lower()
            for claim in claims[:5]:
                claim_words = set(claim.lower().split())
                overlap = sum(1 for w in claim_words if w in snippet_lower)
                claim_overlap = max(claim_overlap, overlap / max(len(claim_words), 1))
            # Decay confidence for later snippets
            position_factor = max(0.5, 1.0 - index * 0.1)
            derived = claim_overlap * position_factor
            confidence = max(0.1, round(derived, 2))
        else:
            confidence = round(max(0.0, min(float(confidence), 1.0)), 2)
        entry["confidence"] = confidence
        evidence.append(entry)
        seen_urls.add(normalized_url)
        if len(evidence) >= max_items:
            break

    return evidence


# ─────────────────────────────────────────────────────────────────────────────
# Snapshot Helpers (moved from planner_executor.py for P0.3 decomposition)
# ─────────────────────────────────────────────────────────────────────────────
SNAPSHOT_MAX_AGE_SECONDS = int(os.getenv("ANALYTICS_SNAPSHOT_MAX_AGE_SECONDS", "600"))


def _artifacts_from_snapshot(snapshot: Optional["SessionStateSnapshot"]) -> Optional["PipelineArtifacts"]:
    """
    Extract PipelineArtifacts from a SessionStateSnapshot tool_cache.

    Function: _artifacts_from_snapshot
    Called from: planner_executor.py context hydration
    Invokes: PipelineArtifacts.from_dict
    Why: Rehydrates artifacts for revision flows without re-executing lanes.
    """
    if snapshot is None:
        return None
    analytics_cache = snapshot.tool_cache.get("analytics", {}) if hasattr(snapshot, "tool_cache") else {}
    artifacts_payload = analytics_cache.get("artifacts")
    if isinstance(artifacts_payload, dict):
        try:
            # Import here to avoid circular dependency
            from analytics.artifacts import PipelineArtifacts
            return PipelineArtifacts.from_dict(artifacts_payload)
        except Exception:
            return None
    return None


def _dataset_preview_from_snapshot(snapshot: Optional["SessionStateSnapshot"]) -> Optional[Dict[str, Any]]:
    """
    Extract dataset preview from a SessionStateSnapshot tool_cache.

    Function: _dataset_preview_from_snapshot
    Called from: planner_executor.py context hydration
    Invokes: dict access
    Why: Provides SQL row previews for cached sessions without re-executing queries.
    """
    if snapshot is None or not hasattr(snapshot, "tool_cache"):
        return None
    preview_payload = snapshot.tool_cache.get("planner_dataset_preview")
    if isinstance(preview_payload, dict):
        rows = preview_payload.get("rows")
        if isinstance(rows, list):
            return preview_payload
    return None


def _snapshot_age_seconds_from_snapshot(snapshot: Dict[str, Any]) -> Optional[float]:
    """
    Calculate the age of a snapshot in seconds from its updated_at timestamp.

    Function: _snapshot_age_seconds_from_snapshot
    Called from: _is_snapshot_fresh
    Invokes: datetime.fromisoformat
    Why: Enables TTL checks for snapshot freshness in revision flows.
    """
    updated_at = snapshot.get("updated_at")
    if not isinstance(updated_at, str):
        return None
    try:
        stamp = datetime.fromisoformat(updated_at)
    except ValueError:
        return None
    if stamp.tzinfo is None:
        delta = datetime.utcnow() - stamp
    else:
        delta = datetime.now(stamp.tzinfo) - stamp
    return max(delta.total_seconds(), 0.0)


def _is_snapshot_fresh(snapshot: Optional[Dict[str, Any]]) -> bool:
    """
    Check if a snapshot is within the maximum age threshold.

    Function: _is_snapshot_fresh
    Called from: planner_executor.py revision context
    Invokes: _snapshot_age_seconds_from_snapshot
    Why: Gates revision reuse on snapshot TTL to avoid stale data.
    """
    if not isinstance(snapshot, dict):
        return False
    age_seconds = _snapshot_age_seconds_from_snapshot(snapshot)
    if age_seconds is None:
        return False
    return age_seconds <= SNAPSHOT_MAX_AGE_SECONDS


# ─────────────────────────────────────────────────────────────────────────────
# Accessory and Snapshot Reset Helpers (moved from planner_executor.py)
# ─────────────────────────────────────────────────────────────────────────────
_WEB_TOOL_NAMES = {"web_retriever", "web_retriever_cached", "web_retriever_live"}
_MARKET_TOOL_NAMES = {"stock_tracker", "market_question_a", "market_question_b"}


def _clear_tool_state(ctx: "PlannerPhaseContext", tool_names: Iterable[str]) -> None:
    """Remove cached tool receipts/results for the provided tool identifiers."""
    names = {str(name).strip().lower() for name in tool_names if name}
    if not names:
        return
    receipts = getattr(ctx, "tool_receipts", None)
    if isinstance(receipts, dict):
        for key in list(receipts.keys()):
            if str(key).strip().lower() in names:
                receipts.pop(key, None)
    results = getattr(ctx, "tool_parallel_results", None)
    if isinstance(results, list):
        filtered = []
        for entry in results:
            tool_id = str((entry or {}).get("tool") or "").strip().lower()
            event_id = str((entry or {}).get("event") or "").strip().lower()
            lane_id = str((entry or {}).get("lane") or "").strip().lower()
            if tool_id in names or event_id in names or (lane_id in {"web", "market"} and tool_id in names):
                continue
            filtered.append(entry)
        ctx.tool_parallel_results = filtered
    manifest = getattr(ctx, "tool_parallel_manifest", None)
    if isinstance(manifest, list):
        ctx.tool_parallel_manifest = [
            entry for entry in manifest if str((entry or {}).get("tool") or "").strip().lower() not in names
        ]


def _reset_revision_accessories(ctx: "PlannerPhaseContext", lanes: Iterable[str]) -> None:
    """Reset web/market accessory state for revision reruns."""
    lanes_normalized = {str(lane).strip().lower() for lane in lanes if lane}
    if not lanes_normalized:
        return
    if "web" in lanes_normalized:
        ctx.web_search = None
        ctx.web_search_seeded = False
        ctx.reused_web = False
        ctx.web_ready_emitted = False  # type: ignore[attr-defined]
        _clear_tool_state(ctx, _WEB_TOOL_NAMES)
    if "market" in lanes_normalized or "stock" in lanes_normalized:
        ctx.stock_widget_seeded = False
        ctx.reused_stock = False
        ctx.stock_ready_emitted = False  # type: ignore[attr-defined]
        _clear_tool_state(ctx, _MARKET_TOOL_NAMES)
    ctx.accessories_prefetched = False


def _build_revision_snapshot_payload(ctx: "PlannerPhaseContext") -> Optional[Dict[str, Any]]:
    """Build a revision snapshot payload from the current planner context."""
    from analytics.core.revision_snapshot import build_intent_signature
    from analytics.core.intent_impl.models import SlotStatusModel
    from analytics.core.intent_impl.models import FollowUpModel
    from analytics.core.state import QueryPlanModel
    from analytics.core.types import ClarifyRequestModel
    from analytics.flows.planner.sql_lane import limit_sample_rows

    plan_model: Optional["QueryPlanModel"] = getattr(ctx, "plan", None) or getattr(ctx, "provisional_plan", None)
    if plan_model is None:
        plan_model = QueryPlanModel()
        ctx.plan = plan_model
        ctx.provisional_plan = plan_model

    signature = ctx.intent_signature or build_intent_signature(ctx.intent, plan_model)
    if signature is None:
        signature = {
            "query": (ctx.query or "")[:256],
            "generated_at": datetime.utcnow().isoformat(),
            "reason": "missing_intent_signature",
        }

    payload: Dict[str, Any] = {"intent_signature": signature}

    classification_model = getattr(ctx, "classification", None)
    if classification_model is not None:
        try:
            payload["classification"] = classification_model.model_dump()
        except Exception:
            payload["classification"] = sanitize_for_json(classification_model)

    sql_generation = ctx.artifacts.sql_generation
    if sql_generation and sql_generation.sql:
        payload["sql"] = sql_generation.sql

    sql_execution = ctx.artifacts.sql_execution
    if sql_execution:
        if sql_execution.row_count is not None:
            payload["sql_row_count"] = sql_execution.row_count
        if sql_execution.columns:
            payload["columns"] = list(sql_execution.columns)
        sample_source = sql_execution.sample_rows or sql_execution.dataset_preview
        samples = limit_sample_rows(sample_source)
        if samples:
            payload["data_sample"] = samples

    chart_artifact = ctx.artifacts.chart
    if chart_artifact:
        if chart_artifact.spec:
            payload["chart_spec"] = copy.deepcopy(chart_artifact.spec)
        if chart_artifact.spec_id:
            payload["chart_spec_id"] = chart_artifact.spec_id

    analysis_artifact = ctx.artifacts.analysis
    if analysis_artifact:
        if analysis_artifact.analysis_text:
            payload["analysis"] = analysis_artifact.analysis_text
            if analysis_artifact.length is not None:
                payload["analysis_length"] = analysis_artifact.length
        if analysis_artifact.stock_widget and analysis_artifact.stock_widget not in ({}, None):
            payload["stock_widget"] = copy.deepcopy(analysis_artifact.stock_widget)
        if analysis_artifact.web_context and analysis_artifact.web_context not in ({}, None):
            payload["web_context"] = copy.deepcopy(analysis_artifact.web_context)

    if ctx.web_search is not None and not payload.get("web_context"):
        try:
            payload["web_context"] = ctx.web_search.to_payload()
        except Exception:
            pass

    if ctx.artifacts.market and ctx.artifacts.market.snapshot and not payload.get("stock_widget"):
        payload["stock_widget"] = copy.deepcopy(ctx.artifacts.market.snapshot)

    intent_model = getattr(ctx, "intent", None)
    if intent_model is not None:
        try:
            payload["intent"] = intent_model.model_dump()
        except Exception:
            payload["intent"] = sanitize_for_json(intent_model)

    if plan_model is not None:
        try:
            payload["plan"] = plan_model.model_dump()
        except Exception:
            plan_payload = getattr(plan_model, "dict", None)
            payload["plan"] = plan_payload() if callable(plan_payload) else sanitize_for_json(plan_model)

    intent_resolution = getattr(ctx, "intent_resolution", None)
    if intent_resolution is not None:
        try:
            payload["intent_resolution"] = intent_resolution.model_dump()
        except Exception:
            payload["intent_resolution"] = sanitize_for_json(intent_resolution)

    slot_statuses_payload: Dict[str, Any] = {}
    for slot_name, status in (getattr(ctx, "slot_statuses", {}) or {}).items():
        if isinstance(status, SlotStatusModel):
            try:
                slot_statuses_payload[str(slot_name)] = status.model_dump()
            except Exception:
                slot_statuses_payload[str(slot_name)] = sanitize_for_json(status)
        elif isinstance(status, Mapping):
            slot_statuses_payload[str(slot_name)] = dict(status)
    if slot_statuses_payload:
        payload["slot_statuses"] = slot_statuses_payload

    followup_payload: List[Dict[str, Any]] = []
    for followup in getattr(ctx, "slot_followups", []) or []:
        if isinstance(followup, FollowUpModel):
            try:
                followup_payload.append(followup.model_dump())
            except Exception:
                followup_payload.append(sanitize_for_json(followup))
        elif isinstance(followup, Mapping):
            followup_payload.append(dict(followup))
    if followup_payload:
        payload["slot_followups"] = followup_payload

    clarification_payload: List[Dict[str, Any]] = []
    for clarification in getattr(ctx, "clarifications", []) or []:
        if isinstance(clarification, ClarifyRequestModel):
            try:
                clarification_payload.append(clarification.model_dump())
            except Exception:
                clarification_payload.append(sanitize_for_json(clarification))
        elif isinstance(clarification, Mapping):
            clarification_payload.append(dict(clarification))
    if clarification_payload:
        payload["clarifications"] = clarification_payload

    clarification_rounds = getattr(ctx, "clarification_rounds", 0)
    if isinstance(clarification_rounds, int) and clarification_rounds > 0:
        payload["clarification_rounds"] = clarification_rounds

    assumptions = getattr(ctx, "assumptions", None)
    if isinstance(assumptions, (list, tuple, set)) and assumptions:
        payload["assumptions"] = [str(item) for item in assumptions if item not in (None, "")]

    payload["updated_at"] = datetime.utcnow().isoformat()
    sanitized = sanitize_for_json(payload)
    return sanitized if isinstance(sanitized, dict) else None


def _hydrate_context_from_snapshot(
    ctx: "PlannerPhaseContext",
    snapshot: Optional["SessionStateSnapshot"],
    artifacts: Optional["PipelineArtifacts"],
) -> None:
    """Hydrate PlannerPhaseContext from a SessionStateSnapshot payload."""
    from analytics.core.revision_snapshot import extract_revision_snapshot
    from analytics.artifacts import (
        AnalysisArtifact,
        ChartArtifact,
        PipelineArtifacts,
        SQLExecutionArtifact,
        SQLGenerationArtifact,
        WebContextArtifact,
    )
    from analytics.flows.planner.sql_lane import limit_sample_rows

    revision_snapshot = extract_revision_snapshot(snapshot)
    if revision_snapshot:
        ctx.revision_snapshot = copy.deepcopy(revision_snapshot)
        ctx.prior_intent_signature = revision_snapshot.get("intent_signature")
    else:
        ctx.revision_snapshot = None
        ctx.prior_intent_signature = None

    if ctx.revision_snapshot:

        def _coerce_model(model_cls, payload):
            if not isinstance(payload, Mapping):
                return None
            try:
                if hasattr(model_cls, "model_validate"):
                    return model_cls.model_validate(payload)
                if hasattr(model_cls, "parse_obj"):
                    return model_cls.parse_obj(payload)  # type: ignore[attr-defined]
                return model_cls(**payload)
            except Exception:
                return None

        hydrated_intent: Optional["IntentModel"] = None
        intent_payload = ctx.revision_snapshot.get("intent")
        if intent_payload and getattr(ctx, "intent", None) is None:
            from analytics.core.types import IntentModel as _IntentModel

            intent_model = _coerce_model(_IntentModel, intent_payload)
            if intent_model:
                hydrated_intent = intent_model
                ctx.intent = intent_model

        plan_payload = ctx.revision_snapshot.get("plan")
        if plan_payload:
            from analytics.core.state import QueryPlanModel as _QueryPlanModel

            plan_model = _coerce_model(_QueryPlanModel, plan_payload)
            if plan_model:
                ctx.plan = plan_model
                ctx.provisional_plan = plan_model

        from analytics.core.intent_impl.models import IntentResolutionModel as _IntentResolutionModel, SlotStatusModel
        from analytics.core.intent_impl.models import FollowUpModel
        from analytics.core.types import ClarifyRequestModel

        resolution_payload = ctx.revision_snapshot.get("intent_resolution")
        slot_status_models: Dict[str, SlotStatusModel] = {}
        followup_models: List[FollowUpModel] = []
        if resolution_payload:
            resolution_model = _coerce_model(_IntentResolutionModel, resolution_payload)
            if resolution_model:
                ctx.intent_resolution = resolution_model
                slot_status_models = dict(resolution_model.slots or {})
                followup_models = list(resolution_model.followups or [])

        slot_status_payload = ctx.revision_snapshot.get("slot_statuses")
        if isinstance(slot_status_payload, Mapping):
            for slot_name, raw in slot_status_payload.items():
                if slot_name in slot_status_models:
                    continue
                status_model = _coerce_model(SlotStatusModel, raw)
                if status_model:
                    slot_status_models[str(slot_name)] = status_model
        if slot_status_models:
            ctx.slot_statuses = slot_status_models

        followup_payload = ctx.revision_snapshot.get("slot_followups")
        if isinstance(followup_payload, Sequence):
            for raw in followup_payload:
                followup_model = _coerce_model(FollowUpModel, raw)
                if followup_model:
                    followup_models.append(followup_model)
        if followup_models:
            ctx.slot_followups = followup_models

        if getattr(ctx, "intent_resolution", None) is None and (slot_status_models or followup_models):
            ctx.intent_resolution = _IntentResolutionModel(
                slots=slot_status_models or {},
                followups=followup_models or [],
            )
        elif getattr(ctx, "intent_resolution", None) is not None:
            ctx.intent_resolution = ctx.intent_resolution.model_copy(  # type: ignore[assignment]
                update={
                    "slots": slot_status_models or dict(ctx.intent_resolution.slots or {}),
                    "followups": followup_models or list(ctx.intent_resolution.followups or []),
                }
            )

        clarifications_payload = ctx.revision_snapshot.get("clarifications")
        if isinstance(clarifications_payload, Sequence):
            clarifications: List[ClarifyRequestModel] = []
            for raw in clarifications_payload:
                clarification_model = _coerce_model(ClarifyRequestModel, raw)
                if clarification_model:
                    clarifications.append(clarification_model)
            if clarifications:
                ctx.clarifications = clarifications

        rounds_value = ctx.revision_snapshot.get("clarification_rounds")
        if isinstance(rounds_value, int) and rounds_value > 0:
            ctx.clarification_rounds = max(ctx.clarification_rounds, rounds_value)

        assumptions_payload = ctx.revision_snapshot.get("assumptions")
        if isinstance(assumptions_payload, Sequence) and assumptions_payload:
            ctx.assumptions = [str(item) for item in assumptions_payload if item not in (None, "")]
        elif hydrated_intent and getattr(hydrated_intent, "assumptions", None):
            ctx.assumptions = list(hydrated_intent.assumptions or [])
        elif getattr(ctx, "intent", None) and getattr(ctx.intent, "assumptions", None):
            ctx.assumptions = list(ctx.intent.assumptions or [])

        if ctx.prior_intent_signature and not getattr(ctx, "intent_signature", None):
            ctx.intent_signature = copy.deepcopy(ctx.prior_intent_signature)

        ctx.reuse_snapshot_active = True

    if artifacts is None:
        if ctx.revision_snapshot:
            artifacts = PipelineArtifacts()
        else:
            return

    if ctx.revision_snapshot:
        chart_spec = ctx.revision_snapshot.get("chart_spec")
        if chart_spec and artifacts.chart is None:
            artifacts.chart = ChartArtifact(
                query=ctx.query,
                spec=copy.deepcopy(chart_spec),
                spec_id=ctx.revision_snapshot.get("chart_spec_id"),
            )
        if ctx.revision_snapshot.get("sql") and artifacts.sql_generation is None:
            artifacts.sql_generation = SQLGenerationArtifact(
                query=ctx.query,
                sql=ctx.revision_snapshot.get("sql"),
                status="completed",
            )
        if artifacts.sql_execution is None:
            if ctx.revision_snapshot.get("sql_row_count") is not None or ctx.revision_snapshot.get("data_sample"):
                artifacts.sql_execution = SQLExecutionArtifact(
                    query=ctx.query,
                    row_count=ctx.revision_snapshot.get("sql_row_count"),
                    columns=list(ctx.revision_snapshot.get("columns") or []),
                    sample_rows=limit_sample_rows(ctx.revision_snapshot.get("data_sample") or []),
                    dataset_preview=limit_sample_rows(ctx.revision_snapshot.get("data_sample") or []),
                    status="completed",
                )
        if artifacts.analysis is None and (
            ctx.revision_snapshot.get("analysis")
            or ctx.revision_snapshot.get("stock_widget")
            or ctx.revision_snapshot.get("web_context")
        ):
            artifacts.analysis = AnalysisArtifact(
                query=ctx.query,
                analysis_text=ctx.revision_snapshot.get("analysis"),
                length=ctx.revision_snapshot.get("analysis_length"),
                stock_widget=copy.deepcopy(ctx.revision_snapshot.get("stock_widget")) if ctx.revision_snapshot.get("stock_widget") else None,
                web_context=copy.deepcopy(ctx.revision_snapshot.get("web_context")) if ctx.revision_snapshot.get("web_context") else None,
            )
        if artifacts.web is None and isinstance(ctx.revision_snapshot.get("web_context"), dict):
            web_payload = copy.deepcopy(ctx.revision_snapshot["web_context"])
            artifacts.web = WebContextArtifact(
                query=ctx.query,
                summary=web_payload.get("summary"),
                snippets=list(web_payload.get("snippets") or []),
                search_id=web_payload.get("search_id"),
                from_cache=web_payload.get("from_cache"),
                metadata=copy.deepcopy(web_payload.get("metadata") or {}),
                topic=web_payload.get("topic"),
                latency_stats=web_payload.get("latency_stats"),
            )
    if artifacts.web is None and snapshot is not None and hasattr(snapshot, "tool_cache"):
        tool_cache = snapshot.tool_cache if isinstance(snapshot.tool_cache, Mapping) else {}
        web_cache = tool_cache.get("web_search") if isinstance(tool_cache, Mapping) else None
        if isinstance(web_cache, Mapping) and web_cache:
            sanitized = sanitize_for_json(dict(web_cache)) or {}
            if isinstance(sanitized, Mapping) and sanitized:
                artifacts.web = WebContextArtifact(
                    query=ctx.query,
                    summary=sanitized.get("summary"),
                    snippets=list(sanitized.get("snippets") or sanitized.get("articles") or []),
                    search_id=sanitized.get("search_id") or sanitized.get("searchId"),
                    from_cache=sanitized.get("from_cache") or True,
                    metadata=copy.deepcopy(sanitized.get("metadata") or {}),
                    topic=sanitized.get("topic") or sanitized.get("search_topic"),
                    latency_stats=sanitized.get("latency_stats"),
                )
                setattr(ctx, "web_search_seeded", True)

    cached_tool_results: List[Dict[str, Any]] = []
    if ctx.revision_snapshot:
        stock_snapshot = ctx.revision_snapshot.get("stock_widget")
        if stock_snapshot:
            cached_tool_results.append(
                {
                    "tool": "stock_tracker",
                    "status": "completed",
                    "payload": {"stock_widget": copy.deepcopy(stock_snapshot)},
                    "reused": True,
                }
            )
        web_snapshot = ctx.revision_snapshot.get("web_context")
        if web_snapshot:
            cached_tool_results.append(
                {
                    "tool": "web_retriever",
                    "status": "completed",
                    "payload": copy.deepcopy(web_snapshot),
                    "reused": True,
                }
            )
    ctx.tool_parallel_results = cached_tool_results + (getattr(ctx, "tool_parallel_results", []) or [])
    ctx.artifacts = artifacts
    ctx.snapshot_artifacts = artifacts
    execution_artifact = getattr(ctx.artifacts, "sql_execution", None)
    preview_payload = _dataset_preview_from_snapshot(snapshot)
    if execution_artifact and preview_payload:
        rows = list(preview_payload.get("rows") or [])
        if rows:
            execution_artifact.dataset_preview = rows
            if not getattr(execution_artifact, "dataset", None):
                execution_artifact.dataset = list(rows)
            if execution_artifact.row_count is None:
                row_count = preview_payload.get("row_count")
                from analytics.core.session_state import normalize_row_count

                normalized_row_count = normalize_row_count(row_count)
                if normalized_row_count is not None:
                    execution_artifact.row_count = normalized_row_count


def _apply_revision_context_hints(ctx: "PlannerPhaseContext") -> None:
    """Apply revision_context refresh hints and snapshot payloads to context."""
    revision_ctx = getattr(ctx, "revision_context", None)
    if revision_ctx is None:
        return
    refresh_flags = dict(getattr(ctx, "lane_refresh_required", {}) or {})
    candidate_lanes = ("analysis", "chart", "web", "market")
    for lane in candidate_lanes:
        needs_refresh = revision_ctx.should_refresh(lane)
        if needs_refresh is False:
            refresh_flags[lane] = False
        elif lane not in refresh_flags and needs_refresh is True:
            refresh_flags[lane] = True
    ctx.lane_refresh_required = refresh_flags
    if revision_ctx.reasoning_summaries and not ctx.revision_reasoning:
        ctx.revision_reasoning = copy.deepcopy(revision_ctx.reasoning_summaries)
    payload = getattr(revision_ctx, "snapshot_payload", None)
    if isinstance(payload, Mapping):
        if getattr(ctx, "revision_snapshot", None) is None:
            ctx.revision_snapshot = copy.deepcopy(payload)
        _hydrate_revision_payload(ctx, payload)


def _hydrate_revision_payload(ctx: "PlannerPhaseContext", payload: Mapping[str, Any]) -> None:
    """Hydrate PlannerPhaseContext from a revision payload dict."""
    from analytics.core.types import ClarifyRequestModel, IntentModel, OffTopicClassifierSchema
    from analytics.core.intent_impl.models import IntentResolutionModel, SlotStatusModel, FollowUpModel
    from analytics.core.state import QueryPlanModel

    if not isinstance(payload, Mapping) or not payload:
        return

    def _coerce_model(model_cls, raw_payload):
        if not isinstance(raw_payload, Mapping):
            return None
        try:
            if hasattr(model_cls, "model_validate"):
                return model_cls.model_validate(raw_payload)  # type: ignore[attr-defined]
            if hasattr(model_cls, "parse_obj"):
                return model_cls.parse_obj(raw_payload)  # type: ignore[attr-defined]
            return model_cls(**raw_payload)
        except Exception:
            return None

    classification_payload = payload.get("classification")
    if classification_payload and getattr(ctx, "classification", None) is None:
        classification_model = _coerce_model(OffTopicClassifierSchema, classification_payload)
        if classification_model:
            ctx.classification = classification_model
            is_financial = getattr(classification_model, "is_financial_query", None)
            if is_financial is not None:
                ctx.is_financial_query = bool(is_financial)

    if getattr(ctx, "intent_signature", None) is None:
        signature = payload.get("intent_signature")
        if isinstance(signature, Mapping):
            ctx.intent_signature = copy.deepcopy(signature)

    hydrated_intent: Optional[IntentModel] = None
    if getattr(ctx, "intent", None) is None:
        intent_payload = payload.get("intent")
        if intent_payload:
            intent_model = _coerce_model(IntentModel, intent_payload)
            if intent_model:
                ctx.intent = intent_model
                hydrated_intent = intent_model
    plan_payload = payload.get("plan")
    if plan_payload and getattr(ctx, "plan", None) is None:
        plan_model = _coerce_model(QueryPlanModel, plan_payload)
        if plan_model:
            ctx.plan = plan_model
            ctx.provisional_plan = plan_model

    slot_status_models: Dict[str, SlotStatusModel] = {}
    followup_models: List[FollowUpModel] = []
    resolution_payload = payload.get("intent_resolution")
    if resolution_payload and getattr(ctx, "intent_resolution", None) is None:
        resolution_model = _coerce_model(IntentResolutionModel, resolution_payload)
        if resolution_model:
            ctx.intent_resolution = resolution_model
            slot_status_models = dict(resolution_model.slots or {})
            followup_models = list(resolution_model.followups or [])

    slot_status_payload = payload.get("slot_statuses")
    if isinstance(slot_status_payload, Mapping):
        for slot_name, raw in slot_status_payload.items():
            if slot_name in slot_status_models:
                continue
            status_model = _coerce_model(SlotStatusModel, raw)
            if status_model:
                slot_status_models[str(slot_name)] = status_model
    if slot_status_models:
        ctx.slot_statuses = slot_status_models

    followup_payload = payload.get("slot_followups")
    if isinstance(followup_payload, Sequence):
        for raw in followup_payload:
            followup_model = _coerce_model(FollowUpModel, raw)
            if followup_model:
                followup_models.append(followup_model)
    if followup_models:
        ctx.slot_followups = followup_models

    if getattr(ctx, "intent_resolution", None) is None and (slot_status_models or followup_models):
        ctx.intent_resolution = IntentResolutionModel(
            slots=slot_status_models or {},
            followups=followup_models or [],
        )
    elif getattr(ctx, "intent_resolution", None) is not None and slot_status_models:
        ctx.intent_resolution = ctx.intent_resolution.model_copy(  # type: ignore[assignment]
            update={
                "slots": slot_status_models or dict(ctx.intent_resolution.slots or {}),
                "followups": followup_models or list(ctx.intent_resolution.followups or []),
            }
        )

    clarifications_payload = payload.get("clarifications")
    if isinstance(clarifications_payload, Sequence) and not getattr(ctx, "clarifications", None):
        clarifications: List[ClarifyRequestModel] = []
        for raw in clarifications_payload:
            clarification_model = _coerce_model(ClarifyRequestModel, raw)
            if clarification_model:
                clarifications.append(clarification_model)
        if clarifications:
            ctx.clarifications = clarifications

    rounds_value = payload.get("clarification_rounds")
    if isinstance(rounds_value, int) and rounds_value > 0:
        ctx.clarification_rounds = max(ctx.clarification_rounds, rounds_value)

    assumptions_payload = payload.get("assumptions")
    if isinstance(assumptions_payload, Sequence) and assumptions_payload:
        ctx.assumptions = [str(item) for item in assumptions_payload if item not in (None, "")]
    elif hydrated_intent and getattr(hydrated_intent, "assumptions", None) and not ctx.assumptions:
        ctx.assumptions = list(hydrated_intent.assumptions or [])

