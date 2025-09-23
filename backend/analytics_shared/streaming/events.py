"""
Lightweight Event Streaming System

Provides efficient, minimal-payload event streaming for analytics workflows.
Reduces event size by 90% compared to heavy payload systems.
"""

from typing import Any, Dict, Optional, Union
from datetime import datetime
import time


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
            "type": self.type,
            "step": self.step,
            "ts": self.timestamp
        }

        if self.data is not None:
            result["data"] = self.data
        if self.message is not None:
            result["msg"] = self.message

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
    def error(step: str, error: Union[str, Exception], details: str = None) -> Dict[str, Any]:
        """
        Emit an error event.

        Args:
            step: Processing step where error occurred
            error: Error message or exception
            details: Optional additional error details

        Returns:
            Lightweight error event dictionary
        """
        error_msg = str(error) if not isinstance(error, str) else error
        data = {"error": error_msg}
        if details:
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
    def session_started(session_id: str) -> Dict[str, Any]:
        """
        Emit a session start event.

        Args:
            session_id: Unique session identifier

        Returns:
            Session start event dictionary
        """
        return StreamEvent("session", "started", data={"session_id": session_id}).to_dict()

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
        return StreamEvent("clarify", "request", data={
            "session_id": session_id,
            **request_data
        }).to_dict()

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
        return StreamEvent("clarify", "ack", data={
            "session_id": session_id,
            "request_id": request_id,
            "answer": answer
        }).to_dict()


class TimedEventEmitter(EventEmitter):
    """
    Event emitter with built-in timing capabilities.
    """

    def __init__(self):
        self.start_time = time.time()
        self.step_times = {}

    def start_step(self, step: str) -> None:
        """Start timing a processing step."""
        self.step_times[step] = time.time()

    def end_step(self, step: str) -> int:
        """End timing a step and return elapsed milliseconds."""
        if step not in self.step_times:
            return 0
        elapsed = int((time.time() - self.step_times[step]) * 1000)
        del self.step_times[step]
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


# Convenience functions for backward compatibility
def emit_progress(step: str, message: str = None) -> Dict[str, Any]:
    """Convenience function for progress events."""
    return EventEmitter.progress(step, message)

def emit_result(step: str, data: Any) -> Dict[str, Any]:
    """Convenience function for result events."""
    return EventEmitter.result(step, data)

def emit_error(step: str, error: Union[str, Exception]) -> Dict[str, Any]:
    """Convenience function for error events."""
    return EventEmitter.error(step, error)