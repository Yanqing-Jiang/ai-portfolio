# --- Analytics Function/Class Map ---
# Module: metrics.py
# Purpose: Metrics collection and aggregation for analytics flows.
# Called from: analytics.flows.workflow, analytics.flows.planner_executor
# Invokes: time.perf_counter, statistics module
# Why: Provides standardized metrics collection for monitoring and alerting.
# Part of Phase 6: Observability implementation.
# --- End Analytics Function/Class Map ---

from __future__ import annotations

import time
import statistics
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Deque
from threading import Lock

__all__ = [
    "MetricsCollector",
    "FlowMetrics",
    "LaneMetrics",
    "ToolMetrics",
    "get_metrics_collector",
]


@dataclass
class ToolMetrics:
    """
    Dataclass: ToolMetrics
    Role: Metrics for individual tool invocations.
    Why: Tracks tool performance for optimization.
    """
    tool_name: str
    invocation_count: int = 0
    success_count: int = 0
    failure_count: int = 0
    cache_hit_count: int = 0
    total_latency_ms: float = 0
    min_latency_ms: float = float("inf")
    max_latency_ms: float = 0
    latencies: Deque[float] = field(default_factory=lambda: deque(maxlen=100))
    retry_count: int = 0

    def record_invocation(
        self,
        *,
        success: bool,
        latency_ms: float,
        from_cache: bool = False,
        retry_count: int = 0,
    ) -> None:
        """Record a tool invocation."""
        self.invocation_count += 1
        if success:
            self.success_count += 1
        else:
            self.failure_count += 1
        if from_cache:
            self.cache_hit_count += 1
        
        self.total_latency_ms += latency_ms
        self.latencies.append(latency_ms)
        self.min_latency_ms = min(self.min_latency_ms, latency_ms)
        self.max_latency_ms = max(self.max_latency_ms, latency_ms)
        self.retry_count += retry_count

    @property
    def avg_latency_ms(self) -> float:
        """Average latency across all invocations."""
        return self.total_latency_ms / self.invocation_count if self.invocation_count > 0 else 0

    @property
    def p95_latency_ms(self) -> float:
        """95th percentile latency."""
        if not self.latencies:
            return 0
        sorted_latencies = sorted(self.latencies)
        idx = int(len(sorted_latencies) * 0.95)
        return sorted_latencies[idx] if idx < len(sorted_latencies) else sorted_latencies[-1]

    @property
    def success_rate(self) -> float:
        """Success rate as percentage."""
        return (self.success_count / self.invocation_count * 100) if self.invocation_count > 0 else 0

    @property
    def cache_hit_rate(self) -> float:
        """Cache hit rate as percentage."""
        return (self.cache_hit_count / self.invocation_count * 100) if self.invocation_count > 0 else 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "tool_name": self.tool_name,
            "invocation_count": self.invocation_count,
            "success_count": self.success_count,
            "failure_count": self.failure_count,
            "cache_hit_count": self.cache_hit_count,
            "success_rate": round(self.success_rate, 2),
            "cache_hit_rate": round(self.cache_hit_rate, 2),
            "avg_latency_ms": round(self.avg_latency_ms, 2),
            "p95_latency_ms": round(self.p95_latency_ms, 2),
            "min_latency_ms": round(self.min_latency_ms, 2),
            "max_latency_ms": round(self.max_latency_ms, 2),
            "retry_count": self.retry_count,
        }


@dataclass
class LaneMetrics:
    """
    Dataclass: LaneMetrics
    Role: Metrics for analytics pipeline lanes.
    Why: Tracks lane performance and dependencies.
    """
    lane_name: str
    execution_count: int = 0
    success_count: int = 0
    failure_count: int = 0
    skip_count: int = 0
    reuse_count: int = 0
    total_latency_ms: float = 0
    min_latency_ms: float = float("inf")
    max_latency_ms: float = 0
    latencies: Deque[float] = field(default_factory=lambda: deque(maxlen=100))

    def record_execution(
        self,
        *,
        status: str,
        latency_ms: float,
        reused: bool = False,
    ) -> None:
        """Record a lane execution."""
        self.execution_count += 1
        
        if status == "completed":
            self.success_count += 1
        elif status == "failed":
            self.failure_count += 1
        elif status == "skipped":
            self.skip_count += 1
        
        if reused:
            self.reuse_count += 1
        
        self.total_latency_ms += latency_ms
        self.latencies.append(latency_ms)
        self.min_latency_ms = min(self.min_latency_ms, latency_ms)
        self.max_latency_ms = max(self.max_latency_ms, latency_ms)

    @property
    def avg_latency_ms(self) -> float:
        """Average latency across all executions."""
        return self.total_latency_ms / self.execution_count if self.execution_count > 0 else 0

    @property
    def p95_latency_ms(self) -> float:
        """95th percentile latency."""
        if not self.latencies:
            return 0
        sorted_latencies = sorted(self.latencies)
        idx = int(len(sorted_latencies) * 0.95)
        return sorted_latencies[idx] if idx < len(sorted_latencies) else sorted_latencies[-1]

    @property
    def success_rate(self) -> float:
        """Success rate as percentage."""
        return (self.success_count / self.execution_count * 100) if self.execution_count > 0 else 0

    @property
    def reuse_rate(self) -> float:
        """Reuse rate as percentage."""
        return (self.reuse_count / self.execution_count * 100) if self.execution_count > 0 else 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "lane_name": self.lane_name,
            "execution_count": self.execution_count,
            "success_count": self.success_count,
            "failure_count": self.failure_count,
            "skip_count": self.skip_count,
            "reuse_count": self.reuse_count,
            "success_rate": round(self.success_rate, 2),
            "reuse_rate": round(self.reuse_rate, 2),
            "avg_latency_ms": round(self.avg_latency_ms, 2),
            "p95_latency_ms": round(self.p95_latency_ms, 2),
            "min_latency_ms": round(self.min_latency_ms, 2),
            "max_latency_ms": round(self.max_latency_ms, 2),
        }


@dataclass
class FlowMetrics:
    """
    Dataclass: FlowMetrics
    Role: Metrics for complete analytics flows.
    Why: Tracks end-to-end flow performance.
    """
    flow_mode: str
    run_count: int = 0
    success_count: int = 0
    failure_count: int = 0
    redirect_count: int = 0
    cancellation_count: int = 0
    total_latency_ms: float = 0
    latencies: Deque[float] = field(default_factory=lambda: deque(maxlen=100))

    def record_run(
        self,
        *,
        status: str,
        latency_ms: float,
    ) -> None:
        """Record a flow run."""
        self.run_count += 1
        
        if status == "completed":
            self.success_count += 1
        elif status == "failed":
            self.failure_count += 1
        elif status == "redirect":
            self.redirect_count += 1
        elif status == "cancelled":
            self.cancellation_count += 1
        
        self.total_latency_ms += latency_ms
        self.latencies.append(latency_ms)

    @property
    def avg_latency_ms(self) -> float:
        """Average latency across all runs."""
        return self.total_latency_ms / self.run_count if self.run_count > 0 else 0

    @property
    def p95_latency_ms(self) -> float:
        """95th percentile latency."""
        if not self.latencies:
            return 0
        sorted_latencies = sorted(self.latencies)
        idx = int(len(sorted_latencies) * 0.95)
        return sorted_latencies[idx] if idx < len(sorted_latencies) else sorted_latencies[-1]

    @property
    def success_rate(self) -> float:
        """Success rate as percentage."""
        return (self.success_count / self.run_count * 100) if self.run_count > 0 else 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "flow_mode": self.flow_mode,
            "run_count": self.run_count,
            "success_count": self.success_count,
            "failure_count": self.failure_count,
            "redirect_count": self.redirect_count,
            "cancellation_count": self.cancellation_count,
            "success_rate": round(self.success_rate, 2),
            "avg_latency_ms": round(self.avg_latency_ms, 2),
            "p95_latency_ms": round(self.p95_latency_ms, 2),
        }


class MetricsCollector:
    """
    Class: MetricsCollector
    Role: Central metrics collection service.
    Called from: All analytics flows
    Why: Provides unified metrics collection and aggregation.
    """

    def __init__(self):
        self._lock = Lock()
        self._tool_metrics: Dict[str, ToolMetrics] = defaultdict(lambda: ToolMetrics(tool_name=""))
        self._lane_metrics: Dict[str, LaneMetrics] = defaultdict(lambda: LaneMetrics(lane_name=""))
        self._flow_metrics: Dict[str, FlowMetrics] = defaultdict(lambda: FlowMetrics(flow_mode=""))

    def record_tool_invocation(
        self,
        tool_name: str,
        *,
        success: bool,
        latency_ms: float,
        from_cache: bool = False,
        retry_count: int = 0,
    ) -> None:
        """Record a tool invocation."""
        with self._lock:
            metrics = self._tool_metrics[tool_name]
            if not metrics.tool_name:
                metrics.tool_name = tool_name
            metrics.record_invocation(
                success=success,
                latency_ms=latency_ms,
                from_cache=from_cache,
                retry_count=retry_count,
            )

    def record_lane_execution(
        self,
        lane_name: str,
        *,
        status: str,
        latency_ms: float,
        reused: bool = False,
    ) -> None:
        """Record a lane execution."""
        with self._lock:
            metrics = self._lane_metrics[lane_name]
            if not metrics.lane_name:
                metrics.lane_name = lane_name
            metrics.record_execution(
                status=status,
                latency_ms=latency_ms,
                reused=reused,
            )

    def record_flow_run(
        self,
        flow_mode: str,
        *,
        status: str,
        latency_ms: float,
    ) -> None:
        """Record a flow run."""
        with self._lock:
            metrics = self._flow_metrics[flow_mode]
            if not metrics.flow_mode:
                metrics.flow_mode = flow_mode
            metrics.record_run(
                status=status,
                latency_ms=latency_ms,
            )

    def get_tool_metrics(self, tool_name: Optional[str] = None) -> Dict[str, Any]:
        """Get tool metrics."""
        with self._lock:
            if tool_name:
                metrics = self._tool_metrics.get(tool_name)
                return metrics.to_dict() if metrics else {}
            return {name: m.to_dict() for name, m in self._tool_metrics.items()}

    def get_lane_metrics(self, lane_name: Optional[str] = None) -> Dict[str, Any]:
        """Get lane metrics."""
        with self._lock:
            if lane_name:
                metrics = self._lane_metrics.get(lane_name)
                return metrics.to_dict() if metrics else {}
            return {name: m.to_dict() for name, m in self._lane_metrics.items()}

    def get_flow_metrics(self, flow_mode: Optional[str] = None) -> Dict[str, Any]:
        """Get flow metrics."""
        with self._lock:
            if flow_mode:
                metrics = self._flow_metrics.get(flow_mode)
                return metrics.to_dict() if metrics else {}
            return {mode: m.to_dict() for mode, m in self._flow_metrics.items()}

    def get_all_metrics(self) -> Dict[str, Any]:
        """Get all metrics."""
        with self._lock:
            return {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "flows": {mode: m.to_dict() for mode, m in self._flow_metrics.items()},
                "lanes": {name: m.to_dict() for name, m in self._lane_metrics.items()},
                "tools": {name: m.to_dict() for name, m in self._tool_metrics.items()},
            }

    def reset(self) -> None:
        """Reset all metrics (for testing)."""
        with self._lock:
            self._tool_metrics.clear()
            self._lane_metrics.clear()
            self._flow_metrics.clear()


# Global metrics collector instance
_metrics_collector: Optional[MetricsCollector] = None


def get_metrics_collector() -> MetricsCollector:
    """
    Function: get_metrics_collector
    Called from: All analytics modules
    Why: Returns singleton metrics collector instance.
    """
    global _metrics_collector
    if _metrics_collector is None:
        _metrics_collector = MetricsCollector()
    return _metrics_collector

