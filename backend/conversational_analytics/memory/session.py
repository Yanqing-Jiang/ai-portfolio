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
class Session:
    """A conversation session with history and context."""
    session_id: str
    messages: List[Message] = field(default_factory=list)
    context: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    last_accessed: float = field(default_factory=time.time)
    
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
