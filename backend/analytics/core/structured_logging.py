# --- Analytics Function/Class Map ---
# Module: structured_logging.py
# Purpose: Structured logging for analytics flows with context propagation.
# Called from: analytics.flows.workflow, analytics.flows.multi_agent, analytics.flows.single_agent_tools
# Invokes: analytics.core.telemetry, logging.getLogger
# Why: Provides structured logging with automatic context injection for better observability.
# Part of Phase 6: Observability implementation.
# --- End Analytics Function/Class Map ---

from __future__ import annotations

import json
import logging
import time
from contextvars import ContextVar
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Mapping
from dataclasses import dataclass, field, asdict

__all__ = [
    "AnalyticsLogger",
    "LogContext",
    "set_log_context",
    "get_log_context",
    "clear_log_context",
    "log_flow_event",
    "log_lane_event",
    "log_tool_invocation",
    "log_cache_hit",
    "log_error",
]

# Context variable for thread-safe context propagation
_log_context: ContextVar[Optional["LogContext"]] = ContextVar("log_context", default=None)


@dataclass
class LogContext:
    """
    Dataclass: LogContext
    Role: Carries structured context through analytics flows.
    Why: Enables automatic injection of session, flow, and user context into logs.
    """
    session_id: Optional[str] = None
    flow_mode: Optional[str] = None
    user_id: Optional[str] = None
    query: Optional[str] = None
    follow_up_route: Optional[str] = None
    request_id: Optional[str] = None
    parent_span_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {k: v for k, v in asdict(self).items() if v is not None}


def set_log_context(context: LogContext) -> None:
    """
    Function: set_log_context
    Called from: workflow.py, multi_agent.py, single_agent_tools.py
    Why: Sets the context for subsequent log calls in the current execution context.
    """
    _log_context.set(context)


def get_log_context() -> Optional[LogContext]:
    """
    Function: get_log_context
    Called from: All logging functions
    Why: Retrieves the current context for automatic injection into logs.
    """
    return _log_context.get()


def clear_log_context() -> None:
    """
    Function: clear_log_context
    Called from: workflow.py (cleanup)
    Why: Clears context after flow completion to prevent context leakage.
    """
    _log_context.set(None)


class AnalyticsLogger:
    """
    Class: AnalyticsLogger
    Role: Structured logger with automatic context injection.
    Called from: All analytics flows
    Why: Provides consistent structured logging with automatic context propagation.
    """

    def __init__(self, name: str, enable_json: bool = True):
        self._logger = logging.getLogger(name)
        self._enable_json = enable_json

    def _build_log_entry(
        self,
        level: str,
        event_type: str,
        message: str,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """Build structured log entry with context."""
        entry: Dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": level,
            "event_type": event_type,
            "message": message,
            "logger": self._logger.name,
        }

        # Inject context
        context = get_log_context()
        if context:
            entry["context"] = context.to_dict()

        # Add custom fields
        if kwargs:
            entry["data"] = kwargs

        return entry

    def _emit(self, level: int, entry: Dict[str, Any]) -> None:
        """Emit log entry as JSON or formatted string."""
        if self._enable_json:
            self._logger.log(level, json.dumps(entry))
        else:
            msg = f"[{entry['event_type']}] {entry['message']}"
            if "data" in entry:
                msg += f" | {json.dumps(entry['data'])}"
            self._logger.log(level, msg)

    def debug(self, event_type: str, message: str, **kwargs: Any) -> None:
        """Log debug event."""
        entry = self._build_log_entry("DEBUG", event_type, message, **kwargs)
        self._emit(logging.DEBUG, entry)

    def info(self, event_type: str, message: str, **kwargs: Any) -> None:
        """Log info event."""
        entry = self._build_log_entry("INFO", event_type, message, **kwargs)
        self._emit(logging.INFO, entry)

    def warning(self, event_type: str, message: str, **kwargs: Any) -> None:
        """Log warning event."""
        entry = self._build_log_entry("WARNING", event_type, message, **kwargs)
        self._emit(logging.WARNING, entry)

    def error(self, event_type: str, message: str, **kwargs: Any) -> None:
        """Log error event."""
        entry = self._build_log_entry("ERROR", event_type, message, **kwargs)
        self._emit(logging.ERROR, entry)


# Module-level convenience functions

def log_flow_event(
    event_type: str,
    message: str,
    *,
    flow_mode: Optional[str] = None,
    session_id: Optional[str] = None,
    **kwargs: Any,
) -> None:
    """
    Function: log_flow_event
    Called from: workflow.py, multi_agent.py, single_agent_tools.py
    Why: Logs high-level flow events with automatic context.
    """
    logger = AnalyticsLogger("analytics.flows")
    logger.info(
        event_type,
        message,
        flow_mode=flow_mode,
        session_id=session_id,
        **kwargs,
    )


def log_lane_event(
    lane: str,
    event_type: str,
    message: str,
    *,
    status: Optional[str] = None,
    latency_ms: Optional[float] = None,
    from_cache: bool = False,
    **kwargs: Any,
) -> None:
    """
    Function: log_lane_event
    Called from: planner_executor.py, sequencer.py
    Why: Logs lane-specific events with standardized fields.
    """
    logger = AnalyticsLogger("analytics.lanes")
    logger.info(
        event_type,
        message,
        lane=lane,
        status=status,
        latency_ms=latency_ms,
        from_cache=from_cache,
        **kwargs,
    )


def log_tool_invocation(
    tool_name: str,
    *,
    status: str,
    latency_ms: float,
    from_cache: bool = False,
    retry_count: int = 0,
    error: Optional[str] = None,
    **kwargs: Any,
) -> None:
    """
    Function: log_tool_invocation
    Called from: planner_executor.py, pipeline_tools.py
    Why: Logs tool invocations with performance metrics.
    """
    logger = AnalyticsLogger("analytics.tools")
    level = "error" if status == "failed" else "info"
    getattr(logger, level)(
        "tool_invocation",
        f"Tool {tool_name} {status}",
        tool_name=tool_name,
        status=status,
        latency_ms=latency_ms,
        from_cache=from_cache,
        retry_count=retry_count,
        error=error,
        **kwargs,
    )


def log_cache_hit(
    lane: str,
    age_seconds: float,
    ttl_seconds: int,
    **kwargs: Any,
) -> None:
    """
    Function: log_cache_hit
    Called from: receipt_helpers.py, single_agent_tools.py
    Why: Logs cache reuse for monitoring cache effectiveness.
    """
    logger = AnalyticsLogger("analytics.cache")
    logger.info(
        "cache_hit",
        f"Lane {lane} served from cache",
        lane=lane,
        age_seconds=age_seconds,
        ttl_seconds=ttl_seconds,
        cache_utilization=age_seconds / ttl_seconds if ttl_seconds > 0 else 0,
        **kwargs,
    )


def log_error(
    error_type: str,
    message: str,
    *,
    exception: Optional[Exception] = None,
    recovery_action: Optional[str] = None,
    **kwargs: Any,
) -> None:
    """
    Function: log_error
    Called from: All error handlers
    Why: Logs errors with structured context for debugging.
    """
    logger = AnalyticsLogger("analytics.errors")
    error_data = {
        "error_type": error_type,
        "recovery_action": recovery_action,
        **kwargs,
    }
    if exception:
        error_data["exception_type"] = type(exception).__name__
        error_data["exception_message"] = str(exception)
    
    logger.error("error_occurred", message, **error_data)

