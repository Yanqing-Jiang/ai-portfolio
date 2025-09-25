"""
Lightweight Event Streaming System

Provides efficient, minimal-payload event streaming for analytics workflows.
Reduces event size by 90% compared to heavy payload systems.
"""

from typing import Any, Dict, List, Optional, Union
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
            "event": self.type,
            "data": {
                "step": self.step,
                "ts": self.timestamp
            }
        }

        if self.data is not None:
            if isinstance(self.data, dict):
                result["data"].update(self.data)
            else:
                result["data"]["payload"] = self.data
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