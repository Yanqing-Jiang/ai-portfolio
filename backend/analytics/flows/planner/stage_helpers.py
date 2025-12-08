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
# --- End Analytics Function/Class Map ---
from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import date, datetime
from typing import Any, Dict, List, Mapping, Optional, TYPE_CHECKING

from analytics.validators import sanitize_for_json

if TYPE_CHECKING:
    from analytics.services.session_state import SessionStateSnapshot
    from analytics.artifacts import PipelineArtifacts

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
        from analytics.flows.planner_executor import ToolInvocationReceipt  # local import to avoid cycles

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

