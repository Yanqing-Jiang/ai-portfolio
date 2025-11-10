# --- Analytics Function/Class Map ---
# Class: StreamEvent
#   Role: Lightweight event structure for streaming analytics workflows.
#   Called from: analytics.flows.agents_stream_bridge
#   Collaborators: analytics.validators.sanitize_for_json
#   Why: Supports downstream analytics workflows that rely on StreamEvent.
# Class: EventEmitter
#   Role: Lightweight event emitter with standardized event types.
#   Called from: analytics.agent_orchestrator.agent_runtime, analytics.agent_orchestrator.event_bus, analytics.flows.chart_revision, analytics.flows.instrumentation, +7 more
#   Collaborators: analytics.core.telemetry.catalog_trace, analytics.core.events.StreamEvent
#   Why: Provides simple factory methods for common event patterns.
# Class: TimedEventEmitter
#   Role: Event emitter with built-in timing capabilities.
#   Called from: analytics.flows.instrumentation, analytics.flows.planner_executor, tests.analytics.test_clarification_auto_fill, tests.analytics.test_intent_resolution_telemetry, +3 more
#   Collaborators: time.time, analytics.core.telemetry.step_timing
#   Why: Supports downstream analytics workflows that rely on TimedEventEmitter.
# --- End Analytics Function/Class Map ---
"""
Lightweight Event Streaming System

Provides efficient, minimal-payload event streaming for analytics workflows.
Reduces event size by 90% compared to heavy payload systems.
"""

from typing import Any, Dict, List, Optional, Union
from datetime import datetime
import time

from analytics.validators import sanitize_for_json

from . import telemetry

class StreamEvent:
    """
    Lightweight event structure for streaming analytics workflows.
    """
    def __init__(self, event_type: str, step: str, data: Any = None, message: str = None):
        self.type = event_type
        self.step = step
        self.data = data
        self.message = message
        self.timestamp = datetime.utcnow().isoformat()

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        result = {
            "event": self.type,
            "data": {
                "step": self.step,
                "ts": self.timestamp
            }
        }

        if self.data is not None:
            sanitized = sanitize_for_json(self.data)
            if isinstance(sanitized, dict):
                result["data"].update(sanitized)
            else:
                result["data"]["payload"] = sanitized
        if self.message is not None:
            result["data"]["message"] = self.message

        return result


class EventEmitter:
    """
    Lightweight event emitter with standardized event types.
    Provides simple factory methods for common event patterns.
    """

    @staticmethod
    def progress(step: str, message: str = None) -> Dict[str, Any]:
        """
        Emit a progress event indicating work in progress.

        Args:
            step: Current processing step
            message: Optional descriptive message

        Returns:
            Lightweight event dictionary (50-100 bytes)
        """
        return StreamEvent("progress", step, message=message).to_dict()

    @staticmethod
    def result(step: str, data: Any, key: str = None) -> Dict[str, Any]:
        """
        Emit a result event with essential data only.

        Args:
            step: Processing step that produced the result
            data: Essential result data (keep minimal)
            key: Optional data key for namespacing

        Returns:
            Lightweight event dictionary (100-200 bytes)
        """
        if key:
            wrapped_data = {key: data}
        else:
            wrapped_data = data

        return StreamEvent("result", step, data=wrapped_data).to_dict()

    @staticmethod
    def error(
        step: str,
        error: Union[str, Exception],
        details: Union[str, Dict[str, Any], None] = None,
        code: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Emit an error event.

        Args:
            step: Processing step where error occurred
            error: Error message or exception
            details: Optional additional error details
            code: Optional short error code for frontend surfacing

        Returns:
            Lightweight error event dictionary
        """
        error_msg = str(error) if not isinstance(error, str) else error
        data: Dict[str, Any] = {"error": error_msg}
        if code:
            data["code"] = code
        if details is not None:
            data["details"] = details

        return StreamEvent("error", step, data=data).to_dict()

    @staticmethod
    def status(step: str, message: str, elapsed_ms: int = None) -> Dict[str, Any]:
        """
        Emit a status update event.

        Args:
            step: Current processing step
            message: Status message
            elapsed_ms: Optional elapsed time in milliseconds

        Returns:
            Lightweight status event dictionary
        """
        data = {"msg": message}
        if elapsed_ms is not None:
            data["elapsed"] = elapsed_ms

        return StreamEvent("status", step, data=data).to_dict()

    @staticmethod
    def heartbeat(message: str = "still_running") -> Dict[str, Any]:
        """Emit a heartbeat keepalive event."""
        return StreamEvent("heartbeat", "keepalive", data={"message": message}).to_dict()

    @staticmethod
    def complete(step: str, summary: str = None, total_elapsed_ms: int = None) -> Dict[str, Any]:
        """
        Emit a completion event.

        Args:
            step: Completed processing step
            summary: Optional completion summary
            total_elapsed_ms: Optional total elapsed time

        Returns:
            Lightweight completion event dictionary
        """
        data = {}
        if summary:
            data["summary"] = summary
        if total_elapsed_ms is not None:
            data["total_elapsed"] = total_elapsed_ms

        return StreamEvent("complete", step, data=data).to_dict()

    @staticmethod
    def agent_turn_start(
        role: str,
        *,
        lane: Optional[str] = None,
        parallel_group: Optional[str] = None,
        retry_count: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        data: Dict[str, Any] = {"role": role}
        if lane:
            data["lane"] = lane
        if parallel_group:
            data["parallel_group"] = parallel_group
        if retry_count is not None:
            data["retry_count"] = retry_count
        if metadata:
            data.update(metadata)
        return StreamEvent("agent_turn_start", role, data=data).to_dict()

    @staticmethod
    def agent_turn_end(
        role: str,
        *,
        lane: Optional[str] = None,
        summary: Optional[Dict[str, Any]] = None,
        elapsed_ms: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        data: Dict[str, Any] = {"role": role}
        if lane:
            data["lane"] = lane
        if summary:
            data["summary"] = summary
        if elapsed_ms is not None:
            data["elapsed_ms"] = elapsed_ms
        if metadata:
            data.update(metadata)
        return StreamEvent("agent_turn_end", role, data=data).to_dict()

    @staticmethod
    def tool_retry(
        tool: str,
        *,
        attempt: int,
        reason: Optional[str] = None,
        error_code: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        data: Dict[str, Any] = {"tool": tool, "attempt": attempt}
        if reason:
            data["reason"] = reason
        if error_code:
            data["error_code"] = error_code
        if metadata:
            data.update(metadata)
        return StreamEvent("tool_retry", tool, data=data).to_dict()

    @staticmethod
    def session_started(session_id: str) -> Dict[str, Any]:
        """
        Emit a session start event.

        Args:
            session_id: Unique session identifier

        Returns:
            Session start event dictionary
        """
        return StreamEvent("session_started", "session", data={"session_id": session_id}).to_dict()

    @staticmethod
    def clarification_request(session_id: str, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Emit a clarification request event.

        Args:
            session_id: Session identifier
            request_data: Clarification request data

        Returns:
            Clarification request event dictionary
        """
        payload = {"session_id": session_id, **request_data}
        return StreamEvent("clarification_request", "clarification", data=payload).to_dict()

    @staticmethod
    def clarification_ack(session_id: str, request_id: str, answer: Any) -> Dict[str, Any]:
        """
        Emit a clarification acknowledgment event.

        Args:
            session_id: Session identifier
            request_id: Request identifier being acknowledged
            answer: User's answer

        Returns:
            Clarification acknowledgment event dictionary
        """
        return StreamEvent("clarification_ack", "clarification", data={
            "session_id": session_id,
            "request_id": request_id,
            "answer": answer
        }).to_dict()

    @staticmethod
    def intent_draft(confidence: float, clarifications_needed: bool = True, clarifications_count: int = 0) -> Dict[str, Any]:
        """
        Emit an intent draft event (clarifications needed).

        Args:
            confidence: Intent confidence score
            clarifications_needed: Whether clarifications are needed
            clarifications_count: Number of clarifications required

        Returns:
            Intent draft event dictionary
        """
        return StreamEvent("intent_draft", "intent_detection", data={
            "confidence": confidence,
            "clarifications_needed": clarifications_needed,
            "clarifications_count": clarifications_count
        }).to_dict()

    @staticmethod
    def intent_decided(key: str, confidence: float, clarifications_needed: bool = False) -> Dict[str, Any]:
        """
        Emit an intent decided event (no clarifications needed).

        Args:
            key: Intent key
            confidence: Intent confidence score
            clarifications_needed: Whether clarifications are needed

        Returns:
            Intent decided event dictionary
        """
        return StreamEvent("intent_decided", "intent_detection", data={
            "key": key,
            "confidence": confidence,
            "clarifications_needed": clarifications_needed
        }).to_dict()

    @staticmethod
    def intent_resolved(key: str, confidence: float, rounds: int = 0) -> Dict[str, Any]:
        """
        Emit an intent resolved event (after clarifications).

        Args:
            key: Intent key
            confidence: Intent confidence score
            rounds: Number of clarification rounds

        Returns:
            Intent resolved event dictionary
        """
        return StreamEvent("intent_resolved", "intent_detection", data={
            "key": key,
            "confidence": confidence,
            "rounds": rounds
        }).to_dict()

    @staticmethod
    def errors(error_list: List[str], step: str = None) -> Dict[str, Any]:
        """
        Emit an errors event.

        Args:
            error_list: List of error messages
            step: Optional step where errors occurred

        Returns:
            Errors event dictionary
        """
        data = {"errors": error_list}
        if step:
            data["step"] = step
        return StreamEvent("errors", step or "unknown", data=data).to_dict()

    @staticmethod
    def sql_generated(sql: str) -> Dict[str, Any]:
        """
        Emit a SQL generated event.

        Args:
            sql: Generated SQL query

        Returns:
            SQL generated event dictionary
        """
        return StreamEvent("sql_generated", "sql_compilation", data={"sql": sql}).to_dict()


    @staticmethod
    def catalog_trace(
        step: str,
        *,
        templates: List[Dict[str, Any]],
        intent_key: Optional[str] = None,
        query: Optional[str] = None,
        selected_template: Optional[str] = None,
        elapsed_ms: Optional[int] = None,
        session_id: Optional[str] = None,
        flow: Optional[str] = None,
    ) -> Dict[str, Any]:
        template_summaries: List[Dict[str, Any]] = []
        for item in templates:
            template_summaries.append({
                "id": str(item.get("id") or item.get("name") or item.get("slug") or "unknown"),
                "name": item.get("name"),
                "score": item.get("score"),
                "source": item.get("source"),
            })
        payload: Dict[str, Any] = {
            "templates": template_summaries,
            "selected_template": selected_template,
            "intent_key": intent_key,
            "query": query,
        }
        if elapsed_ms is not None:
            payload["elapsed_ms"] = elapsed_ms
        telemetry.catalog_trace(
            intent_key=intent_key,
            query=query,
            templates=template_summaries,
            selected_template=selected_template,
            elapsed_ms=elapsed_ms,
            session_id=session_id,
            flow=flow,
        )
        return StreamEvent("catalog_trace", step, data=payload).to_dict()

class TimedEventEmitter(EventEmitter):
    """
    Event emitter with built-in timing capabilities.
    """

    def __init__(self, *, session_id: Optional[str] = None, flow: Optional[str] = None):
        self.start_time = time.time()
        self.step_times: Dict[str, float] = {}
        self.session_id = session_id
        self.flow = flow

    def start_step(self, step: str) -> None:
        """Start timing a processing step."""
        self.step_times[step] = time.time()

    def end_step(self, step: str) -> int:
        """End timing a step and return elapsed milliseconds."""
        if step not in self.step_times:
            return 0
        elapsed = int((time.time() - self.step_times[step]) * 1000)
        del self.step_times[step]
        if elapsed > 0:
            telemetry.step_timing(
                step=step,
                elapsed_ms=elapsed,
                session_id=self.session_id,
                flow=self.flow,
            )
        return elapsed

    def timed_result(self, step: str, data: Any, key: str = None) -> Dict[str, Any]:
        """Emit a result with timing information."""
        elapsed = self.end_step(step)
        event = self.result(step, data, key)
        if elapsed > 0:
            event["elapsed"] = elapsed
        return event

    def timed_status(self, step: str, message: str) -> Dict[str, Any]:
        """Emit a status with timing information."""
        elapsed = self.end_step(step) if step in self.step_times else None
        return self.status(step, message, elapsed)
