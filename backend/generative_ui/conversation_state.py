"""
Conversation State - Persistent state for multi-turn dashboard interactions.

Class: ConversationState
Called from: CommandRouter, dashboard routes
Invokes: n/a
Why: Enables context-aware conversation without repeated full queries.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional
import threading
import logging

logger = logging.getLogger(__name__)


@dataclass
class Message:
    """
    A single message in the conversation.
    
    Dataclass: Message
    Called from: ConversationState.add_message
    Why: Preserves conversation history for context-aware responses.
    """
    role: str  # "user" or "assistant"
    content: str
    timestamp: datetime = field(default_factory=datetime.utcnow)
    tool_calls: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass  
class ConversationState:
    """
    State for a single dashboard conversation session.
    
    Dataclass: ConversationState
    Called from: ConversationStore, CommandRouter
    Why: Maintains conversation history and context for multi-turn interactions.
    """
    dashboard_id: str
    messages: List[Message] = field(default_factory=list)
    
    # Current dashboard context
    skill_id: Optional[str] = None
    tickers: List[str] = field(default_factory=list)
    metric: str = "Revenue"
    time_range: str = "3M"
    
    # Layout state
    layout_preferences: Dict[str, Any] = field(default_factory=dict)
    visible_components: List[str] = field(default_factory=list)
    
    # Timestamps
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_active: datetime = field(default_factory=datetime.utcnow)

    def add_message(self, role: str, content: str, **kwargs) -> None:
        """
        Add a message to the conversation history.
        
        Method: add_message
        Called from: handle_query route, command handlers
        Why: Records conversation turns for context.
        """
        self.messages.append(Message(role=role, content=content, **kwargs))
        self.last_active = datetime.utcnow()
    
    def get_context(self) -> Dict[str, Any]:
        """
        Get current context for intent classification.
        
        Method: get_context
        Called from: CommandRouter.classify_intent
        Why: Provides LLM with necessary context to classify intent.
        """
        return {
            "skill_id": self.skill_id,
            "tickers": self.tickers,
            "metric": self.metric,
            "time_range": self.time_range,
            "visible_components": self.visible_components,
        }
    
    def get_recent_messages(self, count: int = 10) -> List[Dict[str, str]]:
        """
        Get recent messages for context.
        
        Method: get_recent_messages
        Called from: CommandRouter (for conversation history)
        Why: Limits context window size while preserving recent turns.
        """
        recent = self.messages[-count:] if len(self.messages) > count else self.messages
        return [{"role": m.role, "content": m.content} for m in recent]
    
    def update_context(
        self,
        skill_id: Optional[str] = None,
        tickers: Optional[List[str]] = None,
        metric: Optional[str] = None,
        time_range: Optional[str] = None,
        visible_components: Optional[List[str]] = None,
    ) -> None:
        """
        Update dashboard context after an action.
        
        Method: update_context
        Called from: Action handlers after modifying dashboard
        Why: Keeps conversation state synchronized with dashboard state.
        """
        if skill_id:
            self.skill_id = skill_id
        if tickers:
            self.tickers = tickers
        if metric:
            self.metric = metric
        if time_range:
            self.time_range = time_range
        if visible_components is not None:
            self.visible_components = visible_components
        self.last_active = datetime.utcnow()


class ConversationStore:
    """
    In-memory store for conversation states.
    
    Class: ConversationStore
    Called from: dashboard routes, CommandRouter
    Why: Manages conversation states per dashboard session.
    """
    
    def __init__(self, max_conversations: int = 1000):
        """
        Initialize the store with a max capacity.
        
        Args:
            max_conversations: Maximum number of conversations to keep in memory.
        """
        self._states: Dict[str, ConversationState] = {}
        self._lock = threading.Lock()
        self._max = max_conversations
    
    def get_or_create(self, dashboard_id: str) -> ConversationState:
        """
        Get existing state or create new one.
        
        Method: get_or_create
        Called from: handle_query route
        Why: Ensures every dashboard has a conversation state.
        """
        with self._lock:
            if dashboard_id not in self._states:
                # Evict old conversations if at capacity
                if len(self._states) >= self._max:
                    self._evict_oldest()
                self._states[dashboard_id] = ConversationState(dashboard_id=dashboard_id)
                logger.debug("Created conversation state for dashboard %s", dashboard_id)
            return self._states[dashboard_id]
    
    def get(self, dashboard_id: str) -> Optional[ConversationState]:
        """
        Get existing state without creating.
        
        Method: get
        Called from: Various handlers that need optional context
        Why: Avoids creating state for non-existent dashboards.
        """
        return self._states.get(dashboard_id)
    
    def delete(self, dashboard_id: str) -> None:
        """
        Delete a conversation state.
        
        Method: delete
        Called from: delete_dashboard route
        Why: Cleans up state when dashboard is deleted.
        """
        with self._lock:
            self._states.pop(dashboard_id, None)
            logger.debug("Deleted conversation state for dashboard %s", dashboard_id)
    
    def _evict_oldest(self) -> None:
        """
        Evict the least recently active conversation.
        
        Method: _evict_oldest
        Called from: get_or_create when at capacity
        Why: Prevents unbounded memory growth.
        """
        if not self._states:
            return
        oldest = min(self._states.values(), key=lambda s: s.last_active)
        del self._states[oldest.dashboard_id]
        logger.info("Evicted conversation for dashboard %s", oldest.dashboard_id)


# Singleton store
_store: Optional[ConversationStore] = None


def get_conversation_store() -> ConversationStore:
    """
    Get or create the singleton ConversationStore.
    
    Function: get_conversation_store
    Called from: dashboard routes, CommandRouter
    Why: Provides single source of truth for conversation states.
    """
    global _store
    if _store is None:
        _store = ConversationStore()
    return _store
