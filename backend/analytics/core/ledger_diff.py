# --- Analytics Function/Class Map ---
# Module: ledger_diff.py
# Purpose: Ledger comparison and diff utilities for analytics debugging.
# Called from: scripts/compare_ledgers.py, debugging tools
# Invokes: json.load, difflib.SequenceMatcher
# Why: Enables comparison of agent process ledgers to identify behavioral changes.
# Part of Phase 6: Observability implementation.
# --- End Analytics Function/Class Map ---

from __future__ import annotations

import json
import difflib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

__all__ = [
    "LedgerDiff",
    "EventDiff",
    "compare_ledgers",
    "find_missing_events",
    "find_divergence_point",
    "summarize_differences",
]


@dataclass
class EventDiff:
    """
    Dataclass: EventDiff
    Role: Represents a difference between two events.
    Why: Provides structured diff information for debugging.
    """
    event_type: str
    field_name: str
    baseline_value: Any
    compare_value: Any
    diff_type: str  # "added", "removed", "changed"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "event_type": self.event_type,
            "field_name": self.field_name,
            "baseline_value": self.baseline_value,
            "compare_value": self.compare_value,
            "diff_type": self.diff_type,
        }


@dataclass
class LedgerDiff:
    """
    Dataclass: LedgerDiff
    Role: Comprehensive diff between two ledgers.
    Why: Provides structured comparison results.
    """
    baseline_path: str
    compare_path: str
    event_count_baseline: int
    event_count_compare: int
    missing_events: List[Dict[str, Any]] = field(default_factory=list)
    extra_events: List[Dict[str, Any]] = field(default_factory=list)
    changed_events: List[EventDiff] = field(default_factory=list)
    divergence_point: Optional[int] = None
    identical: bool = False

    @property
    def has_differences(self) -> bool:
        """Check if ledgers have any differences."""
        return not self.identical and (
            bool(self.missing_events) 
            or bool(self.extra_events) 
            or bool(self.changed_events)
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "baseline_path": self.baseline_path,
            "compare_path": self.compare_path,
            "event_count_baseline": self.event_count_baseline,
            "event_count_compare": self.event_count_compare,
            "missing_events_count": len(self.missing_events),
            "extra_events_count": len(self.extra_events),
            "changed_events_count": len(self.changed_events),
            "divergence_point": self.divergence_point,
            "identical": self.identical,
            "has_differences": self.has_differences,
            "summary": self.summarize(),
        }

    def summarize(self) -> str:
        """Generate a summary of differences."""
        if self.identical:
            return "Ledgers are identical"
        
        parts = []
        if self.missing_events:
            parts.append(f"{len(self.missing_events)} missing events")
        if self.extra_events:
            parts.append(f"{len(self.extra_events)} extra events")
        if self.changed_events:
            parts.append(f"{len(self.changed_events)} changed fields")
        if self.divergence_point is not None:
            parts.append(f"diverged at event {self.divergence_point}")
        
        return "; ".join(parts)


def load_ledger(path: Path) -> List[Dict[str, Any]]:
    """
    Function: load_ledger
    Called from: compare_ledgers
    Why: Loads and normalizes a ledger file.
    """
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    # Handle different ledger formats
    if isinstance(data, dict):
        # Extract events array
        events = data.get("events", [])
    elif isinstance(data, list):
        events = data
    else:
        raise ValueError(f"Unknown ledger format: {type(data)}")
    
    return events


def normalize_event(event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Function: normalize_event
    Called from: compare_ledgers
    Why: Normalizes event for comparison (removes timestamps, session IDs, etc.).
    """
    normalized = dict(event)
    
    # Remove fields that vary between runs
    fields_to_remove = {
        "timestamp",
        "ts",
        "session_id",
        "request_id",
        "run_id",
        "trace_id",
        "thought_id",
        "elapsed_ms",
        "latency_ms",
        "age_seconds",
    }
    
    for field in fields_to_remove:
        normalized.pop(field, None)
        # Also check nested data
        if "data" in normalized and isinstance(normalized["data"], dict):
            normalized["data"].pop(field, None)
    
    return normalized


def compare_events(
    baseline: Dict[str, Any],
    compare: Dict[str, Any],
    *,
    normalize: bool = True,
) -> List[EventDiff]:
    """
    Function: compare_events
    Called from: compare_ledgers
    Why: Compares two events and returns list of differences.
    """
    if normalize:
        baseline = normalize_event(baseline)
        compare = normalize_event(compare)
    
    diffs: List[EventDiff] = []
    event_type = baseline.get("event", "unknown")
    
    # Compare top-level fields
    all_keys = set(baseline.keys()) | set(compare.keys())
    for key in all_keys:
        if key not in baseline:
            diffs.append(EventDiff(
                event_type=event_type,
                field_name=key,
                baseline_value=None,
                compare_value=compare[key],
                diff_type="added",
            ))
        elif key not in compare:
            diffs.append(EventDiff(
                event_type=event_type,
                field_name=key,
                baseline_value=baseline[key],
                compare_value=None,
                diff_type="removed",
            ))
        elif baseline[key] != compare[key]:
            diffs.append(EventDiff(
                event_type=event_type,
                field_name=key,
                baseline_value=baseline[key],
                compare_value=compare[key],
                diff_type="changed",
            ))
    
    return diffs


def find_missing_events(
    baseline_events: List[Dict[str, Any]],
    compare_events: List[Dict[str, Any]],
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Function: find_missing_events
    Called from: compare_ledgers
    Why: Finds events present in one ledger but not the other.
    """
    baseline_event_types = [e.get("event") for e in baseline_events]
    compare_event_types = [e.get("event") for e in compare_events]
    
    baseline_set = set(baseline_event_types)
    compare_set = set(compare_event_types)
    
    missing_types = baseline_set - compare_set
    extra_types = compare_set - baseline_set
    
    missing_events = [e for e in baseline_events if e.get("event") in missing_types]
    extra_events = [e for e in compare_events if e.get("event") in extra_types]
    
    return missing_events, extra_events


def find_divergence_point(
    baseline_events: List[Dict[str, Any]],
    compare_events: List[Dict[str, Any]],
) -> Optional[int]:
    """
    Function: find_divergence_point
    Called from: compare_ledgers
    Why: Finds the first point where event sequences diverge.
    """
    min_length = min(len(baseline_events), len(compare_events))
    
    for i in range(min_length):
        baseline_event = normalize_event(baseline_events[i])
        compare_event = normalize_event(compare_events[i])
        
        if baseline_event.get("event") != compare_event.get("event"):
            return i
    
    # If all events match up to min_length but lengths differ
    if len(baseline_events) != len(compare_events):
        return min_length
    
    return None


def compare_ledgers(
    baseline_path: Path,
    compare_path: Path,
    *,
    normalize: bool = True,
    detailed: bool = False,
) -> LedgerDiff:
    """
    Function: compare_ledgers
    Called from: scripts/compare_ledgers.py
    Why: Main entry point for ledger comparison.
    """
    baseline_events = load_ledger(baseline_path)
    compare_events = load_ledger(compare_path)
    
    # Find missing/extra events
    missing_events, extra_events = find_missing_events(baseline_events, compare_events)
    
    # Find divergence point
    divergence_point = find_divergence_point(baseline_events, compare_events)
    
    # Compare matching events for detailed differences
    changed_events: List[EventDiff] = []
    if detailed:
        min_length = min(len(baseline_events), len(compare_events))
        for i in range(min_length):
            diffs = compare_events(
                baseline_events[i],
                compare_events[i],
                normalize=normalize,
            )
            changed_events.extend(diffs)
    
    # Check if identical
    identical = (
        len(missing_events) == 0
        and len(extra_events) == 0
        and len(changed_events) == 0
        and len(baseline_events) == len(compare_events)
    )
    
    return LedgerDiff(
        baseline_path=str(baseline_path),
        compare_path=str(compare_path),
        event_count_baseline=len(baseline_events),
        event_count_compare=len(compare_events),
        missing_events=missing_events,
        extra_events=extra_events,
        changed_events=changed_events,
        divergence_point=divergence_point,
        identical=identical,
    )


def summarize_differences(diff: LedgerDiff) -> str:
    """
    Function: summarize_differences
    Called from: scripts/compare_ledgers.py
    Why: Generates a human-readable summary of ledger differences.
    """
    lines = [
        f"Ledger Comparison Summary",
        f"=" * 60,
        f"Baseline: {diff.baseline_path}",
        f"Compare:  {diff.compare_path}",
        f"",
        f"Event Counts:",
        f"  Baseline: {diff.event_count_baseline}",
        f"  Compare:  {diff.event_count_compare}",
        f"",
    ]
    
    if diff.identical:
        lines.append("✓ Ledgers are identical")
        return "\n".join(lines)
    
    lines.append(f"Differences Found:")
    lines.append(f"  Missing events: {len(diff.missing_events)}")
    lines.append(f"  Extra events: {len(diff.extra_events)}")
    lines.append(f"  Changed fields: {len(diff.changed_events)}")
    
    if diff.divergence_point is not None:
        lines.append(f"  Divergence at event: {diff.divergence_point}")
    
    lines.append("")
    
    if diff.missing_events:
        lines.append("Missing Events (in baseline but not compare):")
        for event in diff.missing_events[:5]:  # Show first 5
            lines.append(f"  - {event.get('event', 'unknown')}")
        if len(diff.missing_events) > 5:
            lines.append(f"  ... and {len(diff.missing_events) - 5} more")
        lines.append("")
    
    if diff.extra_events:
        lines.append("Extra Events (in compare but not baseline):")
        for event in diff.extra_events[:5]:  # Show first 5
            lines.append(f"  - {event.get('event', 'unknown')}")
        if len(diff.extra_events) > 5:
            lines.append(f"  ... and {len(diff.extra_events) - 5} more")
        lines.append("")
    
    if diff.changed_events:
        lines.append("Changed Fields:")
        event_groups: Dict[str, List[EventDiff]] = {}
        for change in diff.changed_events:
            event_groups.setdefault(change.event_type, []).append(change)
        
        for event_type, changes in list(event_groups.items())[:5]:  # Show first 5 events
            lines.append(f"  {event_type}:")
            for change in changes[:3]:  # Show first 3 changes per event
                lines.append(f"    {change.field_name}: {change.diff_type}")
            if len(changes) > 3:
                lines.append(f"    ... and {len(changes) - 3} more fields")
        if len(event_groups) > 5:
            lines.append(f"  ... and {len(event_groups) - 5} more events")
    
    return "\n".join(lines)

