# --- Trace Store Function/Class Map ---
# Dataclass: TraceStep
#   Role: Immutable record of a single runtime step.
#   Called from: RunTrace.add_step
#   Invokes: n/a
#   Why: Captures fine-grained runtime events.
# Dataclass: RunTrace
#   Role: Aggregate trace for a dashboard run.
#   Called from: A2UIRuntime, TraceStore
#   Invokes: TraceStep
#   Why: Persistable log for debugging and replay.
# Class: TraceStore
#   Role: Manage in-memory + persisted traces.
#   Called from: A2UIRuntime, API debug endpoints.
#   Invokes: RunTrace persistence helpers.
#   Why: Central trace repository with file persistence.
# Function: get_trace_store
#   Role: Singleton accessor for TraceStore.
#   Called from: runtime, routes
#   Invokes: TraceStore constructor (once)
#   Why: Ensures shared traces across requests.
# --- End Trace Store Function/Class Map ---
"""
Structured run traces for A2UI dashboards.

Function: Run trace persistence and retrieval for debugging and replay.
Called from: backend.generative_ui.runtime.A2UIRuntime
Invokes: In-memory storage (future: database/file persistence).
Purpose: Enable reproducible debugging without reading logs.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import uuid4
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class TraceStep:
    """
    A single step in the runtime trace.
    
    Dataclass: TraceStep — records one runtime event.
    Called from: RunTrace.add_step
    Invokes: n/a
    Purpose: Immutable record of a single runtime action.
    """
    step_id: str = field(default_factory=lambda: str(uuid4())[:8])
    step_type: str = ""  # e.g., "skill_selection", "data_update", "layout_override"
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    duration_ms: Optional[float] = None
    success: bool = True
    details: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None


@dataclass
class RunTrace:
    """
    Complete trace of a dashboard run.
    
    Dataclass: RunTrace — full execution trace for a dashboard session.
    Called from: A2UIRuntime.stream_dashboard, TraceStore
    Invokes: TraceStep
    Purpose: Bundles all runtime events for debugging and replay.
    """
    trace_id: str = field(default_factory=lambda: str(uuid4()))
    dashboard_id: str = ""
    question: str = ""
    skill_id: str = ""
    
    # Resolved slots
    tickers: List[str] = field(default_factory=list)
    metric: str = ""
    time_range: str = ""
    
    # Layout override (if any)
    layout_override: Optional[Dict[str, Any]] = None
    
    # Execution steps
    steps: List[TraceStep] = field(default_factory=list)
    
    # Summary stats
    started_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    completed_at: Optional[str] = None
    total_duration_ms: Optional[float] = None
    message_count: int = 0
    success: bool = True
    error: Optional[str] = None
    
    def add_step(
        self,
        step_type: str,
        details: Dict[str, Any] = None,
        duration_ms: float = None,
        success: bool = True,
        error: str = None
    ) -> TraceStep:
        """
        Add a step to the trace.
        
        Method: add_step — appends a new TraceStep to the trace.
        Called from: A2UIRuntime.stream_dashboard
        Invokes: TraceStep constructor
        Purpose: Record runtime events as they occur.
        """
        step = TraceStep(
            step_type=step_type,
            details=details or {},
            duration_ms=duration_ms,
            success=success,
            error=error,
        )
        self.steps.append(step)
        return step
    
    def complete(self, success: bool = True, error: str = None):
        """
        Mark the trace as complete.
        
        Method: complete — finalizes the trace with completion time.
        Called from: A2UIRuntime.stream_dashboard (end of stream)
        Invokes: datetime operations
        Purpose: Close out the trace with final stats.
        """
        self.completed_at = datetime.utcnow().isoformat()
        self.success = success
        self.error = error
        
        # Calculate total duration
        try:
            start = datetime.fromisoformat(self.started_at)
            end = datetime.fromisoformat(self.completed_at)
            self.total_duration_ms = (end - start).total_seconds() * 1000
        except Exception:
            pass
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert trace to dictionary for serialization.
        
        Method: to_dict — JSON-safe export.
        Called from: TraceStore.get_debug_bundle, API handlers
        Invokes: asdict
        Purpose: Enable JSON export for debugging.
        """
        return asdict(self)
    
    def to_json(self, indent: int = 2) -> str:
        """
        Export trace as JSON string.
        
        Method: to_json — formatted JSON export.
        Called from: API handlers
        Invokes: json.dumps
        Purpose: Human-readable trace export.
        """
        return json.dumps(self.to_dict(), indent=indent, default=str)


class TraceStore:
    """
    In-memory store for run traces.
    
    Class: TraceStore — persists and retrieves traces.
    Called from: A2UIRuntime, API handlers
    Invokes: RunTrace
    Purpose: Enable trace lookup for debugging without reading logs.
    """
    
    def __init__(self, max_traces: int = 100, persist_dir: Optional[Path] = None):
        """
        Initialize trace store.
        
        Args:
            max_traces: Maximum number of traces to keep (LRU eviction)
        """
        self._traces: Dict[str, RunTrace] = {}
        self._dashboard_traces: Dict[str, List[str]] = {}  # dashboard_id -> [trace_ids]
        self.max_traces = max_traces
        self.persist_dir = persist_dir or (Path(__file__).parent / ".traces")
        self.persist_dir.mkdir(exist_ok=True)
        self._load_existing()
    
    def create(self, dashboard_id: str, question: str) -> RunTrace:
        """
        Create a new trace for a dashboard run.
        
        Method: create — starts a new trace.
        Called from: A2UIRuntime.stream_dashboard
        Invokes: RunTrace constructor
        Purpose: Initialize trace at the start of a run.
        """
        trace = RunTrace(dashboard_id=dashboard_id, question=question)
        
        # Store trace
        self._traces[trace.trace_id] = trace
        
        # Link to dashboard
        if dashboard_id not in self._dashboard_traces:
            self._dashboard_traces[dashboard_id] = []
        self._dashboard_traces[dashboard_id].append(trace.trace_id)
        
        # Evict old traces if needed
        self._evict_if_needed()
        
        logger.debug("Created trace %s for dashboard %s", trace.trace_id, dashboard_id)
        return trace
    
    def get(self, trace_id: str) -> Optional[RunTrace]:
        """
        Get a trace by ID.
        
        Method: get — retrieve trace by ID.
        Called from: API handlers
        Invokes: dict lookup
        Purpose: Access specific trace for inspection.
        """
        return self._traces.get(trace_id)
    
    def get_for_dashboard(self, dashboard_id: str) -> List[RunTrace]:
        """
        Get all traces for a dashboard.
        
        Method: get_for_dashboard — list traces by dashboard.
        Called from: API handlers
        Invokes: dict lookups
        Purpose: View execution history for a dashboard.
        """
        trace_ids = self._dashboard_traces.get(dashboard_id, [])
        return [self._traces[tid] for tid in trace_ids if tid in self._traces]
    
    def get_latest(self, dashboard_id: str) -> Optional[RunTrace]:
        """
        Get the most recent trace for a dashboard.
        
        Method: get_latest — most recent trace.
        Called from: Debug bundle endpoint
        Invokes: get_for_dashboard
        Purpose: Quick access to latest run.
        """
        traces = self.get_for_dashboard(dashboard_id)
        return traces[-1] if traces else None
    
    def get_debug_bundle(self, dashboard_id: str) -> Dict[str, Any]:
        """
        Get a complete debug bundle for a dashboard.
        
        Method: get_debug_bundle — comprehensive debug export.
        Called from: Debug endpoint
        Invokes: get_latest, trace.to_dict
        Purpose: One-stop debugging without reading logs.
        
        Bundle includes:
        - Latest trace (full step history)
        - Final data model snapshot
        - Error details if any
        """
        trace = self.get_latest(dashboard_id)
        if not trace:
            return {"error": "No traces found for dashboard"}
        
        return {
            "dashboard_id": dashboard_id,
            "trace": trace.to_dict(),
            "summary": {
                "question": trace.question,
                "skill_id": trace.skill_id,
                "tickers": trace.tickers,
                "layout_override": trace.layout_override,
                "step_count": len(trace.steps),
                "message_count": trace.message_count,
                "total_duration_ms": trace.total_duration_ms,
                "success": trace.success,
                "error": trace.error,
            }
        }
    
    def _evict_if_needed(self):
        """Evict oldest traces if over capacity."""
        while len(self._traces) > self.max_traces:
            # Find oldest trace
            oldest_id = min(
                self._traces.keys(),
                key=lambda tid: self._traces[tid].started_at
            )
            del self._traces[oldest_id]
            
            # Clean up dashboard mapping
            for dash_id, trace_ids in list(self._dashboard_traces.items()):
                if oldest_id in trace_ids:
                    trace_ids.remove(oldest_id)
                    if not trace_ids:
                        del self._dashboard_traces[dash_id]
            # Remove persisted file
            persisted = self.persist_dir / f"{oldest_id}.json"
            if persisted.exists():
                try:
                    persisted.unlink()
                except Exception:
                    logger.warning("Failed to remove persisted trace %s", persisted)

    def persist(self, trace: RunTrace) -> None:
        """Persist a trace to disk so debug bundles survive restarts."""
        try:
            path = self.persist_dir / f"{trace.trace_id}.json"
            path.write_text(trace.to_json(indent=2), encoding="utf-8")
        except Exception as exc:
            logger.warning("Failed to persist trace %s: %s", trace.trace_id, exc)

    def _load_existing(self) -> None:
        """Load persisted traces from disk into memory."""
        try:
            for file in self.persist_dir.glob("*.json"):
                try:
                    payload = json.loads(file.read_text(encoding="utf-8"))
                    steps = [TraceStep(**step) for step in payload.get("steps", [])]
                    payload["steps"] = steps
                    trace = RunTrace(**payload)
                    self._traces[trace.trace_id] = trace
                    self._dashboard_traces.setdefault(trace.dashboard_id, []).append(trace.trace_id)
                except Exception as exc:
                    logger.warning("Failed to load trace file %s: %s", file, exc)
        except Exception as exc:
            logger.warning("Trace persistence load failed: %s", exc)
        self._evict_if_needed()


# Singleton store
_store: Optional[TraceStore] = None


def get_trace_store() -> TraceStore:
    """
    Get the trace store singleton.
    
    Function: get_trace_store — singleton accessor.
    Called from: A2UIRuntime, API handlers
    Invokes: TraceStore constructor (once)
    Purpose: Shared trace storage across requests.
    """
    global _store
    if _store is None:
        _store = TraceStore()
    return _store


__all__ = ["RunTrace", "TraceStep", "TraceStore", "get_trace_store"]
