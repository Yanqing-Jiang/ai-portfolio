"""In-memory session storage for Conversational Analytics."""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from threading import Lock

from ..config import settings


@dataclass
class Message:
    """A single message in the conversation."""
    role: str  # "user" or "assistant"
    content: str
    timestamp: float = field(default_factory=time.time)
    tool_calls: Optional[List[Dict[str, Any]]] = None
    tool_results: Optional[List[Dict[str, Any]]] = None


@dataclass
class PendingSelection:
    """A pending HITL selection request awaiting user response."""
    request_id: str
    skill_id: str
    options: List[Dict[str, Any]]
    resolved_slots: Dict[str, Any]
    ambiguous_slots: List[str]
    created_at: float = field(default_factory=time.time)


@dataclass
class Session:
    """A conversation session with history, context, and specialist outputs."""
    session_id: str
    messages: List[Message] = field(default_factory=list)
    context: Dict[str, Any] = field(default_factory=dict)
    specialist_outputs: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    last_accessed: float = field(default_factory=time.time)
    pending_selection: Optional[PendingSelection] = None
    
    def add_message(self, role: str, content: str, **kwargs) -> Message:
        """Add a message to the session."""
        msg = Message(role=role, content=content, **kwargs)
        self.messages.append(msg)
        self.last_accessed = time.time()
        
        # Trim history if too long
        max_messages = settings.max_history_messages
        if len(self.messages) > max_messages:
            self.messages = self.messages[-max_messages:]
            
        return msg
    
    def get_history_for_claude(self) -> List[Dict[str, Any]]:
        """Get message history formatted for Claude API."""
        history = []
        for msg in self.messages:
            # Skip empty/whitespace messages to avoid Claude 400s
            content = (msg.content or "").strip()
            if not content:
                continue
            history.append({
                "role": msg.role,
                "content": content
            })
        return history
    
    def is_expired(self) -> bool:
        """Check if session has expired based on TTL."""
        return (time.time() - self.last_accessed) > settings.session_ttl_seconds
    
    def update_context(self, key: str, value: Any) -> None:
        """Update session context data."""
        self.context[key] = value
        self.last_accessed = time.time()
    
    def set_pending_selection(
        self,
        request_id: str,
        skill_id: str,
        options: List[Dict[str, Any]],
        resolved_slots: Dict[str, Any],
        ambiguous_slots: List[str],
    ) -> None:
        """Function: set_pending_selection — stores a HITL selection request awaiting user response.
        Called from: agent when ambiguous slots are detected.
        Purpose: Enables the reply endpoint to validate and resume the agent."""
        self.pending_selection = PendingSelection(
            request_id=request_id,
            skill_id=skill_id,
            options=options,
            resolved_slots=resolved_slots,
            ambiguous_slots=ambiguous_slots,
        )
        self.last_accessed = time.time()
    
    def clear_pending_selection(self) -> None:
        """Function: clear_pending_selection — clears a pending HITL request after user response or timeout."""
        self.pending_selection = None
        self.last_accessed = time.time()
    
    def get_pending_selection(self) -> Optional[PendingSelection]:
        """Function: get_pending_selection — returns the pending HITL request, if any."""
        return self.pending_selection

    def set_specialist_output(self, specialist_id: str, payload: Dict[str, Any]) -> None:
        """Function: set_specialist_output — stores the latest output for a specialist run.
        Called from: supervisor orchestrator after a specialist completes.
        Invokes: updates in-memory map keyed by specialist id.
        Purpose: Preserve structured results for downstream supervisor synthesis and UI."""
        self.specialist_outputs[specialist_id] = payload
        self.last_accessed = time.time()

    def get_specialist_outputs(self) -> Dict[str, Any]:
        """Function: get_specialist_outputs — returns all recorded specialist outputs."""
        return self.specialist_outputs


class SessionStore:
    """Thread-safe in-memory session storage."""
    
    def __init__(self):
        self._sessions: Dict[str, Session] = {}
        self._lock = Lock()
    
    def get_or_create(self, session_id: str) -> Session:
        """Get existing session or create a new one."""
        with self._lock:
            # Clean up expired sessions occasionally
            self._cleanup_expired()
            
            if session_id not in self._sessions:
                self._sessions[session_id] = Session(session_id=session_id)
            else:
                self._sessions[session_id].last_accessed = time.time()
                
            return self._sessions[session_id]
    
    def get(self, session_id: str) -> Optional[Session]:
        """Get a session by ID, or None if not found/expired."""
        with self._lock:
            session = self._sessions.get(session_id)
            if session and not session.is_expired():
                session.last_accessed = time.time()
                return session
            return None
    
    def delete(self, session_id: str) -> bool:
        """Delete a session."""
        with self._lock:
            if session_id in self._sessions:
                del self._sessions[session_id]
                return True
            return False
    
    def _cleanup_expired(self) -> None:
        """Remove expired sessions (called within lock)."""
        expired = [
            sid for sid, session in self._sessions.items()
            if session.is_expired()
        ]
        for sid in expired:
            del self._sessions[sid]
    
    def clear_all(self) -> None:
        """Clear all sessions."""
        with self._lock:
            self._sessions.clear()


# Global session store instance
session_store = SessionStore()
